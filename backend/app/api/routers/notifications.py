from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import is_server_shutting_down, subscribe_user, unsubscribe_user
from app.core.config import get_settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.db.db import SessionLocal, get_db
from app.db.models import Notification
from app.schemas.v2 import NotificationItem
from app.security.authz import require, resolve_identity
from app.security.deps import get_current_user_id
from app.security.security import decode_token
from app.services.api_trace import record_api_action

router = APIRouter()
auth = HTTPBearer()
auth_optional = HTTPBearer(auto_error=False)
SSE_QUEUE_TIMEOUT_SECONDS = 1
SSE_MAX_STREAM_SECONDS = 300
logger = logging.getLogger("app.notifications")
settings = get_settings()
_sse_connect_rate_limiter = SlidingWindowRateLimiter(
    max_requests=settings.sse_connect_rate_limit_attempts,
    window_seconds=settings.sse_connect_rate_limit_window_seconds,
)


def _notification_item(n: Notification) -> dict:
    try:
        payload = json.loads(n.payload)
    except Exception:
        payload = {"raw": n.payload}
    return {
        "id": n.id,
        "event_type": n.event_type,
        "payload": payload,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat(),
    }


@router.get("/notifications", response_model=list[NotificationItem])
def list_notifications(
    limit: int = Query(default=100, ge=1, le=500),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    identity = resolve_identity(db, user_id)
    require(identity, "notifications:list")

    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()
    record_api_action(
        user_id=user_id,
        action="notifications.list",
        args={"limit": limit},
        result={"count": len(rows)},
    )
    return [_notification_item(n) for n in rows]


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    identity = resolve_identity(db, user_id)
    require(identity, "notifications:list")

    n = db.get(Notification, notification_id)
    if not n or n.user_id != user_id:
        raise HTTPException(status_code=404, detail="Not found")
    n.is_read = True
    db.commit()
    record_api_action(
        user_id=user_id,
        action="notifications.read",
        args={"notification_id": notification_id},
        result={"ok": True},
    )
    return {"ok": True}


@router.get("/api/events/stream")
async def events_stream(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(auth_optional),
    token: str | None = Query(default=None),
):
    client_ip = request.client.host if request.client else "unknown"
    decision = _sse_connect_rate_limiter.evaluate(f"{client_ip}:sse")
    if not decision.allowed:
        logger.warning("SSE connect rate limit exceeded for client_ip=%s", client_ip)
        raise HTTPException(
            status_code=429,
            detail="Too many SSE connection attempts. Try again later.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    if creds:
        user_id = decode_token(creds.credentials)
    elif token:
        if not settings.sse_allow_query_token:
            logger.warning("Rejected SSE query-token auth for client_ip=%s", client_ip)
            raise HTTPException(
                status_code=401,
                detail="Query-token auth is disabled. Use Authorization header.",
            )
        logger.warning("SSE query-token auth is deprecated; use Authorization header. client_ip=%s", client_ip)
        user_id = decode_token(token)
    else:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    record_api_action(
        user_id=user_id,
        action="events.stream.connect",
        args={"transport": "sse"},
        result={"ok": True},
    )
    logger.info("SSE stream connected for user_id=%s", user_id)

    with SessionLocal() as db:
        identity = resolve_identity(db, user_id)
        require(identity, "notifications:list")

    queue = subscribe_user(user_id)
    last_seen_id = 0

    async def event_generator():
        nonlocal last_seen_id
        started_at = time.monotonic()
        try:
            yield "event: ready\ndata: {\"ok\": true}\n\n"

            with SessionLocal() as db2:
                unread = db2.scalars(
                    select(Notification)
                    .where(
                        Notification.user_id == user_id,
                        Notification.is_read.is_(False),
                    )
                    .order_by(Notification.id.asc())
                    .limit(100)
                ).all()
                for n in unread:
                    item = _notification_item(n)
                    item["notification_id"] = n.id
                    if n.id > last_seen_id:
                        last_seen_id = n.id
                    yield f"data: {json.dumps(item, default=str)}\n\n"

            while True:
                if (time.monotonic() - started_at) >= SSE_MAX_STREAM_SECONDS:
                    break
                if is_server_shutting_down():
                    break
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=SSE_QUEUE_TIMEOUT_SECONDS)
                    n_id = event.get("notification_id")
                    if isinstance(n_id, int) and n_id > last_seen_id:
                        last_seen_id = n_id
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                except asyncio.TimeoutError:
                    if is_server_shutting_down():
                        break
                    if await request.is_disconnected():
                        break
                    with SessionLocal() as db2:
                        newer = db2.scalars(
                            select(Notification)
                            .where(
                                Notification.user_id == user_id,
                                Notification.id > last_seen_id,
                            )
                            .order_by(Notification.id.asc())
                        ).all()
                        if newer:
                            logger.info(
                                "SSE catch-up loaded %s newer notification(s) for user_id=%s",
                                len(newer),
                                user_id,
                            )
                        for n in newer:
                            item = _notification_item(n)
                            item["notification_id"] = n.id
                            last_seen_id = n.id
                            yield f"data: {json.dumps(item, default=str)}\n\n"

                    yield ": keepalive\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            unsubscribe_user(user_id, queue)
            logger.info("SSE stream disconnected for user_id=%s", user_id)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)
