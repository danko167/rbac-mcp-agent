from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text

from app.core.runtime_state import snapshot_runtime_state
from app.db.db import SessionLocal
from app.security.deps import get_current_user_id, require_permission

router = APIRouter(tags=["ops"])
logger = logging.getLogger("app.api.health")


@router.get("/healthz")
def healthz():
    state = snapshot_runtime_state()
    return {
        "status": "ok",
        "is_shutting_down": bool(state.get("is_shutting_down", False)),
        "runtime": state,
    }


@router.get("/readyz")
def readyz(response: Response):
    state = snapshot_runtime_state()
    if bool(state.get("is_shutting_down", False)):
        response.status_code = 503
        return {
            "status": "not_ready",
            "reason": "shutdown_in_progress",
            "runtime": state,
        }

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        response.status_code = 503
        return {
            "status": "not_ready",
            "reason": "database_unavailable",
            "runtime": state,
        }

    return {
        "status": "ready",
        "runtime": state,
    }


@router.get("/metrics/runtime")
def runtime_metrics(
    _: int = Depends(get_current_user_id),
    __: object = Depends(require_permission("agent:trace:view_all")),
):
    return snapshot_runtime_state()
