from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.db import get_db
from app.db.models import PermissionRequest
from app.schemas.v2 import PermissionRequestCreate, PermissionRequestDecision, PermissionRequestItem
from app.security.authz import Identity
from app.security.deps import get_current_user_id, require_permission
from app.services.api_trace import record_api_action
from app.services.permission_requests import (
    create_permission_request as create_permission_request_record,
    decide_permission_request as decide_permission_request_record,
    permission_request_item,
)

router = APIRouter()
DEFAULT_ADMIN_LIMIT = 100
MAX_ADMIN_LIMIT = 500


@router.post("/permission-requests", response_model=PermissionRequestItem)
def create_permission_request(
    payload: PermissionRequestCreate,
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:request")),
    db: Session = Depends(get_db),
):
    try:
        pr = create_permission_request_record(
            db,
            requester_user_id=user_id,
            request_kind=payload.request_kind,
            permission_name=payload.permission_name,
            target_user_id=payload.target_user_id,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=400, detail=message)

    record_api_action(
        user_id=user_id,
        action="permission_requests.create",
        args={
            "request_kind": pr.request_kind,
            "permission_name": pr.permission_name,
            "target_user_id": pr.target_user_id,
        },
        result={"request_id": pr.id, "status": pr.status},
    )

    return permission_request_item(pr)


@router.get("/permission-requests/mine", response_model=list[PermissionRequestItem])
def list_my_permission_requests(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(PermissionRequest)
        .where(PermissionRequest.requester_user_id == user_id)
        .order_by(PermissionRequest.created_at.desc())
    ).all()
    record_api_action(
        user_id=user_id,
        action="permission_requests.mine",
        args={},
        result={"count": len(rows)},
    )
    return [permission_request_item(r) for r in rows]


@router.get("/admin/permission-requests", response_model=list[PermissionRequestItem])
def list_permission_requests_admin(
    status: str | None = None,
    limit: int = Query(default=DEFAULT_ADMIN_LIMIT, ge=1, le=MAX_ADMIN_LIMIT),
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    stmt = select(PermissionRequest).order_by(PermissionRequest.created_at.desc())
    if status:
        stmt = stmt.where(PermissionRequest.status == status)
    rows = db.scalars(stmt.limit(limit)).all()
    record_api_action(
        user_id=user_id,
        action="admin.permission_requests.list",
        args={"status": status},
        result={"count": len(rows)},
    )
    return [permission_request_item(r) for r in rows]


@router.post("/admin/permission-requests/{request_id}/approve", response_model=PermissionRequestItem)
def approve_permission_request(
    request_id: int,
    payload: PermissionRequestDecision,
    user_id: int = Depends(get_current_user_id),
    identity: Identity = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    try:
        pr = decide_permission_request_record(
            db,
            actor=identity,
            request_id=request_id,
            decision="approve",
            reason=payload.reason,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=400, detail=message)

    record_api_action(
        user_id=user_id,
        action="admin.permission_requests.approve",
        args={"request_id": request_id, "reason": payload.reason},
        result={"status": pr.status, "requester_user_id": pr.requester_user_id},
    )
    return permission_request_item(pr)


@router.post("/admin/permission-requests/{request_id}/reject", response_model=PermissionRequestItem)
def reject_permission_request(
    request_id: int,
    payload: PermissionRequestDecision,
    user_id: int = Depends(get_current_user_id),
    identity: Identity = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    try:
        pr = decide_permission_request_record(
            db,
            actor=identity,
            request_id=request_id,
            decision="reject",
            reason=payload.reason,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=400, detail=message)

    record_api_action(
        user_id=user_id,
        action="admin.permission_requests.reject",
        args={"request_id": request_id, "reason": payload.reason},
        result={"status": pr.status, "requester_user_id": pr.requester_user_id},
    )
    return permission_request_item(pr)
