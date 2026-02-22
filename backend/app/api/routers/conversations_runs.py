from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.db import get_db
from app.db.models import AgentRun, Conversation, ToolAudit, utcnow
from app.schemas.agent import (
    AgentRunDetailResponse,
    AgentRunListItem,
    ConversationCreateResponse,
    ConversationDetailResponse,
    ConversationListItem,
)
from app.security.deps import get_current_user_id
from app.services.agent_run_meta import action_name_from_prompt, run_type_from_prompt
from app.services.conversations import (
    CONVERSATION_KIND_APPROVALS,
    CONVERSATION_KIND_DEFAULT,
    default_title_for_conversation_kind,
    normalize_conversation_kind,
)
from app.services.token_usage import empty_usage_summary, get_conversation_usage_summaries

router = APIRouter()


def _get_or_create_approvals_conversation(db: Session, user_id: int) -> Conversation:
    existing = db.scalar(
        select(Conversation)
        .where(
            Conversation.user_id == user_id,
            Conversation.kind == CONVERSATION_KIND_APPROVALS,
        )
        .order_by(Conversation.updated_at.desc())
    )
    if existing:
        return existing

    conversation = Conversation(
        user_id=user_id,
        kind=CONVERSATION_KIND_APPROVALS,
        title=default_title_for_conversation_kind(CONVERSATION_KIND_APPROVALS),
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.post("/agent/conversations", response_model=ConversationCreateResponse)
def create_conversation(
    kind: str = Query(default=CONVERSATION_KIND_DEFAULT),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    normalized_kind = normalize_conversation_kind(kind)

    if normalized_kind == CONVERSATION_KIND_APPROVALS:
        conversation = _get_or_create_approvals_conversation(db, user_id=user_id)
        return {
            "id": conversation.id,
            "kind": conversation.kind or CONVERSATION_KIND_DEFAULT,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
        }

    conversation = Conversation(
        user_id=user_id,
        kind=normalized_kind,
        title=default_title_for_conversation_kind(normalized_kind),
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return {
        "id": conversation.id,
        "kind": conversation.kind or CONVERSATION_KIND_DEFAULT,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


@router.get("/agent/conversations/approvals", response_model=ConversationCreateResponse)
def get_or_create_approvals_conversation(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    conversation = _get_or_create_approvals_conversation(db, user_id=user_id)
    return {
        "id": conversation.id,
        "kind": conversation.kind or CONVERSATION_KIND_DEFAULT,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


@router.get("/agent/conversations", response_model=list[ConversationListItem])
def list_my_conversations(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    conversations = db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    ).all()

    conversation_ids = [conversation.id for conversation in conversations]
    usage_by_conversation = get_conversation_usage_summaries(
        db,
        user_id=user_id,
        conversation_ids=conversation_ids,
    )

    run_counts: dict[int, int] = {}
    if conversation_ids:
        run_count_rows = db.execute(
            select(AgentRun.conversation_id, func.count(AgentRun.id))
            .where(AgentRun.conversation_id.in_(conversation_ids))
            .group_by(AgentRun.conversation_id)
        ).all()
        run_counts = {
            int(conversation_id): int(count)
            for conversation_id, count in run_count_rows
            if conversation_id is not None
        }

    return [
        {
            "id": c.id,
            "kind": c.kind or CONVERSATION_KIND_DEFAULT,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
            "run_count": run_counts.get(c.id, 0),
            "token_usage": usage_by_conversation.get(c.id, empty_usage_summary()),
        }
        for c in conversations
    ]


@router.get("/agent/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_my_conversation(
    conversation_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user_id:
        raise HTTPException(status_code=404, detail="Not found")

    runs = db.scalars(
        select(AgentRun)
        .where(AgentRun.conversation_id == conversation_id)
        .order_by(AgentRun.started_at.asc())
    ).all()

    messages: list[dict[str, str]] = []
    for run in runs:
        messages.append(
            {
                "role": "user",
                "content": run.prompt,
                "created_at": run.started_at.isoformat(),
            }
        )

        assistant_content = (run.final_output or "").strip()
        if not assistant_content and run.error:
            assistant_content = f"Error: {run.error}"

        if assistant_content:
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_content,
                    "created_at": (run.finished_at or run.started_at).isoformat(),
                }
            )

    return {
        "id": conversation.id,
        "kind": conversation.kind or CONVERSATION_KIND_DEFAULT,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
        "messages": messages,
    }


@router.delete("/agent/conversations/{conversation_id}")
def delete_my_conversation(
    conversation_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user_id:
        raise HTTPException(status_code=404, detail="Not found")
    if conversation.kind == CONVERSATION_KIND_APPROVALS:
        raise HTTPException(status_code=400, detail="Approvals conversation cannot be deleted")

    runs = db.scalars(
        select(AgentRun).where(AgentRun.conversation_id == conversation_id)
    ).all()
    for run in runs:
        run.conversation_id = None

    db.delete(conversation)
    db.commit()

    return {"ok": True}


@router.get("/agent/runs", response_model=list[AgentRunListItem])
def list_my_runs(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    runs = db.scalars(
        select(AgentRun)
        .where(AgentRun.user_id == user_id)
        .order_by(AgentRun.started_at.desc())
    ).all()

    return [
        {
            "id": r.id,
            "conversation_id": r.conversation_id,
            "prompt": r.prompt,
            "run_type": run_type_from_prompt(r.prompt),
            "action_name": action_name_from_prompt(r.prompt),
            "created_at": r.started_at.isoformat(),
            "status": r.status,
            "specialist_key": r.specialist_key,
            "final_output": r.final_output,
        }
        for r in runs
    ]


@router.get("/agent/runs/{run_id}", response_model=AgentRunDetailResponse)
def get_my_run(
    run_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    run = db.get(AgentRun, run_id)
    if not run or run.user_id != user_id:
        raise HTTPException(status_code=404, detail="Not found")

    tools = db.scalars(
        select(ToolAudit)
        .where(ToolAudit.agent_run_id == run_id)
        .order_by(ToolAudit.created_at.asc())
    ).all()

    return {
        "run": {
            "id": run.id,
            "conversation_id": run.conversation_id,
            "prompt": run.prompt,
            "run_type": run_type_from_prompt(run.prompt),
            "action_name": action_name_from_prompt(run.prompt),
            "created_at": run.started_at.isoformat(),
            "status": getattr(run, "status", "ok"),
            "specialist_key": run.specialist_key,
            "final_output": run.final_output,
            "error": getattr(run, "error", None),
        },
        "tools": [
            {"tool": t.tool_name, "args": t.arguments, "created_at": t.created_at.isoformat()}
            for t in tools
        ],
    }
