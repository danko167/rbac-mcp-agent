from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_state_lock = Lock()
_runtime_state: dict[str, object] = {
    "started_at": None,
    "shutdown_started_at": None,
    "shutdown_completed_at": None,
    "shutdown_duration_ms": None,
    "startup_count": 0,
    "shutdown_count": 0,
    "is_shutting_down": False,
}


def mark_startup() -> None:
    with _state_lock:
        _runtime_state["started_at"] = _utcnow_iso()
        _runtime_state["shutdown_started_at"] = None
        _runtime_state["shutdown_completed_at"] = None
        _runtime_state["shutdown_duration_ms"] = None
        _runtime_state["startup_count"] = int(_runtime_state["startup_count"]) + 1
        _runtime_state["is_shutting_down"] = False


def mark_shutdown_started() -> str:
    with _state_lock:
        shutdown_started_at = _utcnow_iso()
        _runtime_state["shutdown_started_at"] = shutdown_started_at
        _runtime_state["is_shutting_down"] = True
        return shutdown_started_at


def mark_shutdown_completed(duration_ms: float) -> None:
    with _state_lock:
        _runtime_state["shutdown_completed_at"] = _utcnow_iso()
        _runtime_state["shutdown_duration_ms"] = round(duration_ms, 2)
        _runtime_state["shutdown_count"] = int(_runtime_state["shutdown_count"]) + 1


def snapshot_runtime_state() -> dict[str, object]:
    with _state_lock:
        return dict(_runtime_state)
