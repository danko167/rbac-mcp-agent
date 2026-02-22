from __future__ import annotations

import base64
import binascii
import io
import logging

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from agent.llm_client import get_openai_client
from agent.runtime import run_agent
from agent.specialists import route_agent_profile
from agent.trace import create_agent_run, finalize_agent_run_error, finalize_agent_run_ok
from app.core.config import get_settings
from app.core.time import effective_user_timezone, timezone_context
from app.db.db import get_db
from app.db.models import Conversation, User, utcnow
from app.schemas.agent import (
    AgentRunRequest,
    AgentRunResponse,
    AgentTranscriptionRequest,
    AgentTranscriptionResponse,
)
from app.security.deps import get_bearer_token, get_current_user_required
from app.services.conversations import (
    CONVERSATION_KIND_DEFAULT,
    conversation_title_from_prompt,
    default_title_for_conversation_kind,
)
from app.services.token_usage import extract_openai_usage, record_usage_event

router = APIRouter()
MAX_TRANSCRIBE_AUDIO_BYTES = 3 * 1024 * 1024
logger = logging.getLogger("app.api.agent_execution")


@router.post("/agent/run", response_model=AgentRunResponse)
def run_agent_endpoint(
    jwt_token: str = Depends(get_bearer_token),
    user: User = Depends(get_current_user_required),
    body: AgentRunRequest = Body(default_factory=AgentRunRequest),
    db: Session = Depends(get_db),
):
    user_id = user.id

    prompt = (body.prompt or "").strip()
    messages = body.messages
    conversation_id = body.conversation_id
    suppress_user_message = bool(body.suppress_user_message)

    effective_prompt = prompt
    if (not effective_prompt) and messages and isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user" and message.get("content"):
                effective_prompt = str(message["content"])
                break

    conversation: Conversation
    if conversation_id is not None:
        existing_conversation = db.get(Conversation, conversation_id)
        if not existing_conversation or existing_conversation.user_id != user_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conversation = existing_conversation
    else:
        conversation = Conversation(
            user_id=user_id,
            kind=CONVERSATION_KIND_DEFAULT,
            title=conversation_title_from_prompt(effective_prompt),
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    if conversation.title == "New conversation" and (effective_prompt or "").strip():
        conversation.title = conversation_title_from_prompt(effective_prompt)
        db.commit()
        db.refresh(conversation)

    profile = route_agent_profile(
        messages if (messages and isinstance(messages, list) and len(messages) > 0)
        else [{"role": "user", "content": effective_prompt or ""}]
    )

    persisted_prompt = "" if suppress_user_message else (effective_prompt or "")

    run_id = create_agent_run(
        db,
        user_id=user_id,
        prompt=persisted_prompt,
        conversation_id=conversation.id,
        specialist_key=profile.key,
    )

    try:
        with timezone_context(effective_user_timezone(user.timezone)):
            run_result = run_agent(
                prompt=effective_prompt or "",
                jwt_token=jwt_token,
                agent_run_id=run_id,
                messages=messages,
            )
    except RuntimeError as exc:
        logger.warning("Agent run failed with runtime error for user_id=%s: %s", user_id, exc)
        finalize_agent_run_error(db, run_id=run_id, error=f"{type(exc).__name__}: {exc}")
        conversation.updated_at = utcnow()
        db.commit()
        if "Client failed to connect" in str(exc):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Agent tool backend is currently unavailable (MCP server is not reachable). "
                    "Start the MCP server and try again."
                ),
            )
        raise
    except Exception as exc:
        logger.exception("Agent run failed with unexpected error for user_id=%s", user_id)
        finalize_agent_run_error(db, run_id=run_id, error=f"{type(exc).__name__}: {exc}")
        conversation.updated_at = utcnow()
        db.commit()
        raise

    finalize_agent_run_ok(db, run_id=run_id, output=run_result.text)
    record_usage_event(
        db,
        user_id=user_id,
        conversation_id=conversation.id,
        agent_run_id=run_id,
        event_type="llm",
        model=get_settings().llm_model,
        input_tokens=run_result.usage.get("input_tokens", 0),
        output_tokens=run_result.usage.get("output_tokens", 0),
        total_tokens=run_result.usage.get("total_tokens", 0),
    )
    conversation.updated_at = utcnow()
    db.commit()
    return {"run_id": run_id, "result": run_result.text, "conversation_id": conversation.id}


@router.post("/agent/transcribe", response_model=AgentTranscriptionResponse)
def transcribe_agent_audio(
    body: AgentTranscriptionRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    user_id = user.id

    b64 = (body.audio_base64 or "").strip()
    if not b64:
        raise HTTPException(status_code=400, detail="audio_base64 is required")

    try:
        audio_bytes = base64.b64decode(b64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(status_code=400, detail="Invalid audio payload")

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio payload is empty")

    if len(audio_bytes) > MAX_TRANSCRIBE_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio too large. Max size is {MAX_TRANSCRIBE_AUDIO_BYTES // (1024 * 1024)} MB",
        )

    file_name = (body.file_name or "speech.webm").strip() or "speech.webm"
    settings = get_settings()
    client = get_openai_client()

    file_obj = io.BytesIO(audio_bytes)
    file_obj.name = file_name

    try:
        language = (body.language or "en").strip() or "en"
        response = client.audio.transcriptions.create(
            model=settings.transcription_model,
            file=file_obj,
            language=language,
        )
    except Exception as exc:
        logger.warning("Audio transcription failed for user_id=%s: %s", user_id, exc)
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}")

    text = (getattr(response, "text", None) or "").strip()
    usage = extract_openai_usage(response)
    conversation_id = body.conversation_id
    conversation: Conversation | None = None
    if conversation_id is not None:
        existing = db.get(Conversation, conversation_id)
        if existing and existing.user_id == user_id:
            conversation = existing
        elif existing and existing.user_id != user_id:
            raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation is None:
        conversation = Conversation(
            user_id=user_id,
            kind=CONVERSATION_KIND_DEFAULT,
            title=default_title_for_conversation_kind(CONVERSATION_KIND_DEFAULT),
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    conversation.updated_at = utcnow()
    conversation_id = conversation.id

    record_usage_event(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        event_type="transcription",
        model=settings.transcription_model,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )
    db.commit()
    return {"text": text, "conversation_id": conversation_id}
