from __future__ import annotations

from datetime import datetime, timezone, timedelta
import re

from sqlalchemy import select, func, update, delete

from app.core.time import current_tzinfo, current_timezone_name
from app.db.db import SessionLocal
from app.db.models import Alarm, User
from app.security.authz import authorize, require
from mcp_app.security.deps import identity_from_bearer_with_db
from mcp_app.services.audit import log_tool_call


def _parse_fire_at(value: str) -> datetime:
    raw = (value or "").strip().lower()
    relative_raw = re.sub(r"[\s,.;:!?]+$", "", raw)

    app_tz = current_tzinfo()

    relative_match = re.match(
        (
            r"^(?:in\s+)?(\d+)\s*"
            r"(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)"
            r"\s*(?:from\s+now)?$"
        ),
        relative_raw,
    )
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        unit_normalized = unit.rstrip("s")
        now_local = datetime.now(app_tz)
        if unit_normalized in {"second", "sec", "s"}:
            target_local = now_local.replace(microsecond=0)
            target_local = target_local + timedelta(seconds=amount)
        elif unit_normalized in {"minute", "min", "m"}:
            target_local = now_local.replace(microsecond=0)
            target_local = target_local + timedelta(minutes=amount)
        else:
            target_local = now_local.replace(microsecond=0)
            target_local = target_local + timedelta(hours=amount)
        return target_local.astimezone(timezone.utc)

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception as e:
        raise ValueError(
            "fire_at must be ISO-8601 datetime or relative phrase like '30 seconds from now' or 'in 1 min'"
        ) from e

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=app_tz)

    # Store consistently in UTC
    return dt.astimezone(timezone.utc)


def register(mcp):
    @mcp.tool()
    def alarms_set(
        auth: str,
        title: str,
        fire_at: str,
        target_user_id: int | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Schedule an alarm for yourself or a delegated target user.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            effective_target = authorize(db, identity, "alarms:set", target_user_id=target_user_id)

            alarm = Alarm(
                creator_user_id=identity.user_id,
                target_user_id=effective_target,
                title=title,
                fire_at=_parse_fire_at(fire_at),
            )
            db.add(alarm)
            db.flush()

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="alarms.set",
                args={"title": title, "fire_at": fire_at, "target_user_id": target_user_id},
                agent_run_id=agent_run_id,
            )

            app_tz_name = current_timezone_name()
            app_tz = current_tzinfo()

            return {
                "id": alarm.id,
                "title": alarm.title,
                "target_user_id": alarm.target_user_id,
                "fire_at": alarm.fire_at.astimezone(app_tz).isoformat(),
                "fire_at_utc": alarm.fire_at.astimezone(timezone.utc).isoformat(),
                "fire_at_local": alarm.fire_at.astimezone(app_tz).isoformat(),
                "local_timezone": app_tz_name,
            }

    @mcp.tool()
    def alarms_list(auth: str, target_user_id: int | None = None, agent_run_id: int | None = None):
        """
        List alarms for yourself or, when delegated, for a target user.
        Use target_user_id when the user asks about another account.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            if target_user_id is None or target_user_id == identity.user_id:
                require(identity, "alarms:receive")
                effective_target_user_id = identity.user_id
            else:
                effective_target_user_id = authorize(
                    db,
                    identity,
                    "alarms:set",
                    target_user_id=target_user_id,
                )

            rows = db.scalars(
                select(Alarm)
                .where(
                    Alarm.target_user_id == effective_target_user_id,
                    Alarm.canceled_at.is_(None),
                    Alarm.fired_at.is_(None),
                )
                .order_by(Alarm.fire_at.asc())
            ).all()

            creator_ids = {a.creator_user_id for a in rows}
            creator_rows = db.execute(
                select(User.id, User.email).where(User.id.in_(creator_ids))
            ).all() if creator_ids else []
            creator_email_by_id = {int(row.id): row.email for row in creator_rows}

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="alarms.list",
                args={"target_user_id": target_user_id},
                agent_run_id=agent_run_id,
            )

            app_tz_name = current_timezone_name()
            app_tz = current_tzinfo()

            return [
                {
                    "id": a.id,
                    "title": a.title,
                    "creator_user_id": a.creator_user_id,
                    "creator_email": creator_email_by_id.get(a.creator_user_id),
                    "target_user_id": a.target_user_id,
                    "fire_at": a.fire_at.astimezone(app_tz).isoformat(),
                    "fire_at_utc": a.fire_at.astimezone(timezone.utc).isoformat(),
                    "fire_at_local": a.fire_at.astimezone(app_tz).isoformat(),
                    "local_timezone": app_tz_name,
                    "fired_at": a.fired_at.astimezone(app_tz).isoformat() if a.fired_at else None,
                    "fired_at_utc": a.fired_at.astimezone(timezone.utc).isoformat() if a.fired_at else None,
                    "fired_at_local": a.fired_at.astimezone(app_tz).isoformat() if a.fired_at else None,
                }
                for a in rows
            ]

    @mcp.tool()
    def alarms_cancel(auth: str, alarm_id: int, agent_run_id: int | None = None):
        """
        Cancel an active alarm visible to the current user.
        Allowed for the alarm creator and the target recipient.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            alarm = db.scalar(
                select(Alarm).where(
                    Alarm.id == alarm_id,
                    Alarm.canceled_at.is_(None),
                    Alarm.fired_at.is_(None),
                )
            )
            if not alarm:
                raise ValueError("Alarm not found")

            is_creator = alarm.creator_user_id == identity.user_id
            is_target = alarm.target_user_id == identity.user_id
            if not (is_creator or is_target):
                raise ValueError("Alarm not found")

            if is_creator:
                require(identity, "alarms:set")
            else:
                require(identity, "alarms:receive")

            alarm.canceled_at = datetime.now(timezone.utc)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="alarms.cancel",
                args={"alarm_id": alarm_id},
                agent_run_id=agent_run_id,
            )

            return {"ok": True}

    @mcp.tool()
    def alarms_cancel_by_title(auth: str, title: str, agent_run_id: int | None = None):
        """
        Cancel a single active alarm by exact title match (case-insensitive).
        Allowed for alarms visible to the current user.
        """
        normalized_title = (title or "").strip()
        if not normalized_title:
            raise ValueError("title is required")

        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)

            rows = db.scalars(
                select(Alarm)
                .where(
                    Alarm.canceled_at.is_(None),
                    Alarm.fired_at.is_(None),
                    func.lower(Alarm.title) == normalized_title.lower(),
                    ((Alarm.target_user_id == identity.user_id) | (Alarm.creator_user_id == identity.user_id)),
                )
                .order_by(Alarm.fire_at.asc())
            ).all()

            if not rows:
                raise ValueError("Alarm not found")

            if len(rows) > 1:
                app_tz = current_tzinfo()
                matches = [
                    {
                        "id": row.id,
                        "title": row.title,
                        "fire_at": row.fire_at.astimezone(app_tz).isoformat(),
                    }
                    for row in rows[:5]
                ]
                raise ValueError(f"Multiple alarms match this title: {matches}")

            alarm = rows[0]
            is_creator = alarm.creator_user_id == identity.user_id
            if is_creator:
                require(identity, "alarms:set")
            else:
                require(identity, "alarms:receive")

            alarm.canceled_at = datetime.now(timezone.utc)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="alarms.cancel_by_title",
                args={"title": normalized_title, "alarm_id": alarm.id},
                agent_run_id=agent_run_id,
            )

            app_tz_name = current_timezone_name()
            app_tz = current_tzinfo()

            return {
                "ok": True,
                "id": alarm.id,
                "title": alarm.title,
                "fire_at": alarm.fire_at.astimezone(app_tz).isoformat(),
                "fire_at_utc": alarm.fire_at.astimezone(timezone.utc).isoformat(),
                "fire_at_local": alarm.fire_at.astimezone(app_tz).isoformat(),
                "local_timezone": app_tz_name,
            }

    @mcp.tool()
    def alarms_update(
        auth: str,
        alarm_id: int,
        title: str | None = None,
        fire_at: str | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Update an active alarm by ID (title and/or fire_at).
        Allowed for the alarm creator and the target recipient.
        """
        values: dict[str, object] = {}
        if title is not None:
            normalized_title = title.strip()
            if not normalized_title:
                raise ValueError("title cannot be empty")
            values["title"] = normalized_title
        if fire_at is not None:
            values["fire_at"] = _parse_fire_at(fire_at)
        if not values:
            raise ValueError("No fields provided to update")

        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)

            alarm = db.scalar(
                select(Alarm).where(
                    Alarm.id == alarm_id,
                    Alarm.canceled_at.is_(None),
                    Alarm.fired_at.is_(None),
                )
            )
            if not alarm:
                raise ValueError("Alarm not found")

            is_creator = alarm.creator_user_id == identity.user_id
            is_target = alarm.target_user_id == identity.user_id
            if not (is_creator or is_target):
                raise ValueError("Alarm not found")

            if is_creator:
                require(identity, "alarms:set")
            else:
                require(identity, "alarms:receive")

            row = db.execute(
                update(Alarm)
                .where(Alarm.id == alarm_id)
                .values(**values)
                .returning(Alarm.id, Alarm.title, Alarm.fire_at, Alarm.target_user_id)
            ).first()
            if not row:
                raise ValueError("Alarm not found")

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="alarms.update",
                args={"alarm_id": alarm_id, "title": title, "fire_at": fire_at},
                agent_run_id=agent_run_id,
            )

            app_tz_name = current_timezone_name()
            app_tz = current_tzinfo()

            return {
                "id": row.id,
                "title": row.title,
                "target_user_id": row.target_user_id,
                "fire_at": row.fire_at.astimezone(app_tz).isoformat(),
                "fire_at_utc": row.fire_at.astimezone(timezone.utc).isoformat(),
                "fire_at_local": row.fire_at.astimezone(app_tz).isoformat(),
                "local_timezone": app_tz_name,
            }

    @mcp.tool()
    def alarms_delete(auth: str, alarm_id: int, agent_run_id: int | None = None):
        """
        Delete an alarm by ID.
        Allowed for the alarm creator and the target recipient.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)

            alarm = db.scalar(select(Alarm).where(Alarm.id == alarm_id))
            if not alarm:
                raise ValueError("Alarm not found")

            is_creator = alarm.creator_user_id == identity.user_id
            is_target = alarm.target_user_id == identity.user_id
            if not (is_creator or is_target):
                raise ValueError("Alarm not found")

            if is_creator:
                require(identity, "alarms:set")
            else:
                require(identity, "alarms:receive")

            res = db.execute(delete(Alarm).where(Alarm.id == alarm_id))
            if res.rowcount == 0:
                raise ValueError("Alarm not found")

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="alarms.delete",
                args={"alarm_id": alarm_id},
                agent_run_id=agent_run_id,
            )

            return {"ok": True}
