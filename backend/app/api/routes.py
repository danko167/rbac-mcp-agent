from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.db import get_db
from app.db.models import User, AgentRun, ToolAudit
from app.security.security import verify_password, create_token, decode_token
from app.security.authz import resolve_identity, require
from agent.runtime import run_agent
from agent.trace import create_agent_run, finalize_agent_run_ok, finalize_agent_run_error

from app.schemas.auth import LoginRequest, TokenResponse, MeResponse
from app.schemas.agent import (
    AgentRunRequest,
    AgentRunResponse,
    AgentRunListItem,
    AgentRunDetailResponse,
    AdminAgentRunListItem,
)

# API Router
router = APIRouter()
auth = HTTPBearer()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user and return JWT token.
    """
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_token(user.id)}


@router.get("/me", response_model=MeResponse)
def me(
    creds: HTTPAuthorizationCredentials = Depends(auth),
    db: Session = Depends(get_db),
):
    """
    Get current authenticated user's information.
    """
    user_id = decode_token(creds.credentials)

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Not found")

    identity = resolve_identity(db, user_id)

    return {
        "id": user.id,
        "email": user.email,
        "roles": [r.name for r in user.roles],
        "permissions": sorted(list(identity.permissions)),
    }


@router.post("/agent/run", response_model=AgentRunResponse)
def run_agent_endpoint(
    creds: HTTPAuthorizationCredentials = Depends(auth),
    body: AgentRunRequest = Body(default_factory=AgentRunRequest),
    db: Session = Depends(get_db),
):
    """
    Run an agent with the provided prompt and messages.
    """
    jwt_token = creds.credentials
    user_id = decode_token(jwt_token)

    prompt = (body.prompt or "").strip()
    messages = body.messages

    effective_prompt = prompt
    if (not effective_prompt) and messages and isinstance(messages, list):
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user" and m.get("content"):
                effective_prompt = str(m["content"])
                break

    run_id = create_agent_run(db, user_id=user_id, prompt=effective_prompt or "")

    try:
        output = run_agent(
            prompt=effective_prompt or "",
            jwt_token=jwt_token,
            agent_run_id=run_id,
            messages=messages,
        )
    except Exception as e:
        finalize_agent_run_error(db, run_id=run_id, error=f"{type(e).__name__}: {e}")
        raise

    finalize_agent_run_ok(db, run_id=run_id, output=output)
    return {"run_id": run_id, "result": output}


# --- User trace viewer ---
@router.get("/agent/runs", response_model=list[AgentRunListItem])
def list_my_runs(
    creds: HTTPAuthorizationCredentials = Depends(auth),
    db: Session = Depends(get_db),
):
    """
    List agent runs for the current authenticated user.
    """
    user_id = decode_token(creds.credentials)

    runs = db.scalars(
        select(AgentRun)
        .where(AgentRun.user_id == user_id)
        .order_by(AgentRun.started_at.desc())
    ).all()

    return [
        {
            "id": r.id,
            "prompt": r.prompt,
            "created_at": r.started_at.isoformat(),
            "status": r.status,
            "final_output": r.final_output,
        }
        for r in runs
    ]


@router.get("/agent/runs/{run_id}", response_model=AgentRunDetailResponse)
def get_my_run(
    run_id: int,
    creds: HTTPAuthorizationCredentials = Depends(auth),
    db: Session = Depends(get_db),
):
    """
    Get details of a specific agent run for the current authenticated user.
    """
    user_id = decode_token(creds.credentials)

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
            "prompt": run.prompt,
            "created_at": run.started_at.isoformat(),
            "status": getattr(run, "status", "ok"),
            "final_output": run.final_output,
            "error": getattr(run, "error", None),
        },
        "tools": [
            {"tool": t.tool_name, "args": t.arguments, "created_at": t.created_at.isoformat()}
            for t in tools
        ],
    }


# --- Admin trace viewer ---
@router.get("/admin/agent/runs", response_model=list[AdminAgentRunListItem])
def admin_runs(
    creds: HTTPAuthorizationCredentials = Depends(auth),
    db: Session = Depends(get_db),
):
    """
    List all agent runs (admin only).
    """
    user_id = decode_token(creds.credentials)

    identity = resolve_identity(db, user_id)
    require(identity, "agent:trace:view_all")

    runs = db.scalars(select(AgentRun).order_by(AgentRun.started_at.desc())).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "prompt": r.prompt,
            "created_at": r.started_at.isoformat(),
            "status": r.status,
            "final_output": r.final_output,
        }
        for r in runs
    ]


@router.get("/admin/agent/runs/{run_id}", response_model=AgentRunDetailResponse)
def admin_run_detail(
    run_id: int,
    creds: HTTPAuthorizationCredentials = Depends(auth),
    db: Session = Depends(get_db),
):
    """
    Get details of a specific agent run (admin only).
    """
    user_id = decode_token(creds.credentials)

    identity = resolve_identity(db, user_id)
    require(identity, "agent:trace:view_all")

    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Not found")

    tools = db.scalars(
        select(ToolAudit)
        .where(ToolAudit.agent_run_id == run_id)
        .order_by(ToolAudit.created_at.asc())
    ).all()

    return {
        "run": {
            "id": run.id,
            "user_id": run.user_id,
            "prompt": run.prompt,
            "created_at": run.started_at.isoformat(),
            "status": getattr(run, "status", "ok"),
            "final_output": run.final_output,
            "error": getattr(run, "error", None),
        },
        "tools": [
            {"tool": t.tool_name, "args": t.arguments, "created_at": t.created_at.isoformat()}
            for t in tools
        ],
    }
