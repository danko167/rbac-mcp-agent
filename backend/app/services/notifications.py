from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import publish_postgres_event, publish_user_event
from app.db.models import Notification


def create_notification(
    db: Session,
    user_id: int,
    event_type: str,
    payload: dict[str, Any],
    enqueue: bool = True,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        event_type=event_type,
        payload=json.dumps(payload, default=str),
        is_read=False,
    )
    db.add(notification)
    db.flush()

    if enqueue:
        event = {
            "notification_id": notification.id,
            "event_type": event_type,
            "payload": payload,
            "created_at": notification.created_at.isoformat(),
        }
        publish_user_event(user_id, event)
        publish_postgres_event(db, user_id, event)

    return notification


def publish_notification_update(db: Session, notification: Notification) -> None:
    try:
        payload = json.loads(notification.payload)
    except Exception:
        payload = {"raw": notification.payload}

    event = {
        "notification_id": notification.id,
        "id": notification.id,
        "event_type": notification.event_type,
        "payload": payload,
        "created_at": notification.created_at.isoformat(),
        "is_read": bool(notification.is_read),
    }
    publish_user_event(notification.user_id, event)
    publish_postgres_event(db, notification.user_id, event)


def list_user_notifications(db: Session, user_id: int, limit: int = 100) -> list[Notification]:
    return db.scalars(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()
