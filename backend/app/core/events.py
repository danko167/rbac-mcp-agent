from __future__ import annotations

import asyncio
import json
import logging
import select
import time
from collections import defaultdict
from typing import Any

import psycopg2
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.db import engine


_user_streams: dict[int, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
_server_shutting_down = False
_logger = logging.getLogger("app.core.events")
POSTGRES_NOTIFY_CHANNEL = "rbac_notifications"


def mark_server_running() -> None:
    global _server_shutting_down
    _server_shutting_down = False


def mark_server_shutting_down() -> None:
    global _server_shutting_down
    _server_shutting_down = True


def is_server_shutting_down() -> bool:
    return _server_shutting_down


def subscribe_user(user_id: int) -> asyncio.Queue[dict[str, Any]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
    _user_streams[user_id].add(queue)
    return queue


def unsubscribe_user(user_id: int, queue: asyncio.Queue[dict[str, Any]]) -> None:
    queues = _user_streams.get(user_id)
    if not queues:
        return
    queues.discard(queue)
    if not queues:
        _user_streams.pop(user_id, None)


def publish_user_event(user_id: int, event: dict[str, Any]) -> None:
    queues = _user_streams.get(user_id)
    if not queues:
        return

    for queue in list(queues):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except Exception:
                pass


def publish_postgres_event(db: Session, user_id: int, event: dict[str, Any]) -> None:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    payload = {"user_id": user_id, "event": event}
    try:
        db.execute(
            text("SELECT pg_notify(:channel, :payload)"),
            {"channel": POSTGRES_NOTIFY_CHANNEL, "payload": json.dumps(payload, default=str)},
        )
        _logger.info("Published PostgreSQL NOTIFY on %s for user_id=%s", POSTGRES_NOTIFY_CHANNEL, user_id)
    except Exception as exc:
        _logger.warning("Failed to publish PostgreSQL NOTIFY event: %s", exc)


def forward_postgres_events_forever() -> None:
    settings = get_settings()
    if engine.dialect.name != "postgresql":
        return

    _logger.info("Starting PostgreSQL LISTEN loop on channel=%s", POSTGRES_NOTIFY_CHANNEL)
    dsn = settings.database_url.replace("postgresql+psycopg2://", "postgresql://")

    while not is_server_shutting_down():
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(dsn)
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            cursor.execute(f"LISTEN {POSTGRES_NOTIFY_CHANNEL};")

            while not is_server_shutting_down():
                ready, _, _ = select.select([conn], [], [], 1)
                if not ready:
                    continue

                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    try:
                        data = json.loads(notify.payload)
                        user_id = int(data.get("user_id"))
                        event = data.get("event")
                        if isinstance(event, dict):
                            _logger.info("Received PostgreSQL NOTIFY for user_id=%s", user_id)
                            publish_user_event(user_id, event)
                    except Exception:
                        continue
        except Exception as exc:
            _logger.warning("PostgreSQL LISTEN loop error; retrying: %s", exc)
            time.sleep(1)
        finally:
            try:
                if cursor is not None:
                    cursor.close()
            except Exception:
                pass
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
