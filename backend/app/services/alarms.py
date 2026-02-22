from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Alarm, utcnow
from app.services.notifications import create_notification


def process_due_alarms_once(db: Session) -> int:
    now = utcnow()
    due = db.scalars(
        select(Alarm).where(
            Alarm.fired_at.is_(None),
            Alarm.canceled_at.is_(None),
            Alarm.fire_at <= now,
        )
    ).all()

    for alarm in due:
        alarm.fired_at = now
        create_notification(
            db,
            user_id=alarm.target_user_id,
            event_type="alarm.fired",
            payload={
                "alarm_id": alarm.id,
                "title": alarm.title,
                "fire_at": alarm.fire_at.isoformat(),
            },
        )

    return len(due)
