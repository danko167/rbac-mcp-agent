from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class PermissionRequestCreate(BaseModel):
    request_kind: Literal["permission", "delegation"]
    permission_name: str
    target_user_id: int | None = None
    note: str | None = None


class PermissionRequestDecision(BaseModel):
    reason: str | None = None


class PermissionRequestItem(BaseModel):
    id: int
    requester_user_id: int
    request_kind: str
    permission_name: str
    target_user_id: int | None
    status: str
    decision_reason: str | None
    decided_by_user_id: int | None
    created_at: str
    decided_at: str | None


class NotificationItem(BaseModel):
    id: int
    event_type: str
    payload: dict[str, Any]
    is_read: bool
    created_at: str
