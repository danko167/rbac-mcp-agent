from __future__ import annotations

import json
import logging
from typing import Any

from app.db.db import SessionLocal
from agent.trace import create_agent_run, finalize_agent_run_ok, finalize_agent_run_error
from app.services.agent_run_meta import API_PROMPT_PREFIX
from mcp_app.services.audit import log_tool_call

logger = logging.getLogger("app.api_trace")


def record_api_action(
    *,
    user_id: int,
    action: str,
    args: dict[str, Any],
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """
    Persist a non-agent API action into existing AgentRun + ToolAudit trace storage
    so it appears in the current trace UI.
    """
    try:
        with SessionLocal() as db:
            run_id = create_agent_run(db, user_id=user_id, prompt=f"{API_PROMPT_PREFIX}{action}")
            log_tool_call(
                db,
                user_id=user_id,
                tool=f"api.{action}",
                args=args,
                agent_run_id=run_id,
            )

            if error:
                finalize_agent_run_error(db, run_id=run_id, error=error)
            else:
                output = json.dumps(result or {"ok": True}, default=str)
                finalize_agent_run_ok(db, run_id=run_id, output=output)
    except Exception:
        logger.exception("Failed to record API trace for action=%s user_id=%s", action, user_id)
