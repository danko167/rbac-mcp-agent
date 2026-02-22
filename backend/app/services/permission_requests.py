from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Delegation,
    Notification,
    Permission,
    PermissionGrant,
    PermissionRequest,
    User,
    role_permissions,
    user_roles,
    utcnow,
)
from app.security.authz import Identity
from app.services.notifications import create_notification, publish_notification_update


def permission_request_item(pr: PermissionRequest) -> dict:
    return {
        "id": pr.id,
        "requester_user_id": pr.requester_user_id,
        "request_kind": pr.request_kind,
        "permission_name": pr.permission_name,
        "target_user_id": pr.target_user_id,
        "status": pr.status,
        "decision_reason": pr.decision_reason,
        "decided_by_user_id": pr.decided_by_user_id,
        "created_at": pr.created_at.isoformat(),
        "decided_at": pr.decided_at.isoformat() if pr.decided_at else None,
    }


def _normalize_create_inputs(
    db: Session,
    requester_user_id: int,
    request_kind: str,
    permission_name: str,
    target_user_id: int | None,
) -> tuple[str, str, User | None]:
    normalized_kind = request_kind
    normalized_permission_name = permission_name

    if normalized_kind == "permission" and target_user_id is not None:
        candidate_permission_name = (
            normalized_permission_name
            if normalized_permission_name.endswith(".for_others")
            else f"{normalized_permission_name}.for_others"
        )
        candidate_permission = db.scalar(select(Permission).where(Permission.name == candidate_permission_name))
        if not candidate_permission:
            raise ValueError(
                "target_user_id was provided, but no matching delegation permission exists. "
                "Use a '.for_others' permission or remove target_user_id."
            )
        normalized_kind = "delegation"
        normalized_permission_name = candidate_permission_name

    if normalized_kind == "delegation" and target_user_id is None:
        raise ValueError("target_user_id is required for delegation requests")
    if normalized_kind == "permission" and normalized_permission_name.endswith(".for_others"):
        raise ValueError("'.for_others' permissions must be requested as delegation with target_user_id")
    if normalized_kind == "delegation" and not normalized_permission_name.endswith(".for_others"):
        raise ValueError("Delegation requests must be for '.for_others' permissions")
    if normalized_kind == "delegation" and target_user_id == requester_user_id:
        raise ValueError("target_user_id must be a different user for delegation requests")

    target_user: User | None = None
    if normalized_kind == "delegation":
        target_user = db.get(User, target_user_id)
        if not target_user:
            raise ValueError("Target user not found")

    permission = db.scalar(select(Permission).where(Permission.name == normalized_permission_name))
    if not permission:
        raise ValueError("Permission not found")

    return normalized_kind, normalized_permission_name, target_user


def create_permission_request(
    db: Session,
    *,
    requester_user_id: int,
    request_kind: str,
    permission_name: str,
    target_user_id: int | None,
) -> PermissionRequest:
    normalized_kind, normalized_permission_name, target_user = _normalize_create_inputs(
        db,
        requester_user_id,
        request_kind,
        permission_name,
        target_user_id,
    )

    req = PermissionRequest(
        requester_user_id=requester_user_id,
        request_kind=normalized_kind,
        permission_name=normalized_permission_name,
        target_user_id=target_user_id,
        status="pending",
    )
    db.add(req)
    db.flush()

    requester = db.get(User, requester_user_id)

    notification_payload = {
        "request_id": req.id,
        "requester_user_id": requester_user_id,
        "requester_email": requester.email if requester else None,
        "request_kind": req.request_kind,
        "permission_name": req.permission_name,
        "target_user_id": req.target_user_id,
    }
    notified_user_ids: set[int] = set()

    if req.request_kind == "delegation" and target_user is not None:
        create_notification(
            db,
            user_id=target_user.id,
            event_type="permission.request.created",
            payload=notification_payload,
        )
        notified_user_ids.add(target_user.id)

    approver_permission_id = db.scalar(
        select(Permission.id).where(Permission.name == "permissions:approve")
    )
    approver_user_ids: set[int] = set()

    if approver_permission_id is not None:
        role_rows = db.execute(
            select(user_roles.c.user_id)
            .join(role_permissions, user_roles.c.role_id == role_permissions.c.role_id)
            .where(role_permissions.c.permission_id == approver_permission_id)
        ).all()
        approver_user_ids |= {int(row.user_id) for row in role_rows}

    grant_rows = db.execute(
        select(PermissionGrant.user_id).where(PermissionGrant.permission_name == "permissions:approve")
    ).all()
    approver_user_ids |= {int(row.user_id) for row in grant_rows}

    for approver_user_id in approver_user_ids:
        if approver_user_id not in notified_user_ids:
            create_notification(
                db,
                user_id=approver_user_id,
                event_type="permission.request.created",
                payload=notification_payload,
            )

    return req


def _apply_approval_grants(db: Session, pr: PermissionRequest, actor_user_id: int) -> None:
    if pr.request_kind == "permission":
        if pr.permission_name.endswith(".for_others"):
            raise ValueError("Invalid request: '.for_others' permissions must use delegation request kind")
        existing = db.scalar(
            select(PermissionGrant).where(
                PermissionGrant.user_id == pr.requester_user_id,
                PermissionGrant.permission_name == pr.permission_name,
            )
        )
        if not existing:
            db.add(
                PermissionGrant(
                    user_id=pr.requester_user_id,
                    permission_name=pr.permission_name,
                    granted_by_user_id=actor_user_id,
                )
            )
        return

    if pr.request_kind != "delegation":
        raise ValueError("Unsupported request kind")

    if pr.target_user_id is None:
        raise ValueError("Delegation request missing target_user_id")

    if not pr.permission_name.endswith(".for_others"):
        raise ValueError("Delegation request permission must end with .for_others")

    permission = db.scalar(select(Permission).where(Permission.name == pr.permission_name))
    if not permission:
        raise ValueError("Permission not found")

    existing = db.scalar(
        select(Delegation).where(
            Delegation.grantor_user_id == pr.target_user_id,
            Delegation.grantee_user_id == pr.requester_user_id,
            Delegation.permission_name == pr.permission_name,
            Delegation.revoked_at.is_(None),
        )
    )
    if not existing:
        db.add(
            Delegation(
                grantor_user_id=pr.target_user_id,
                grantee_user_id=pr.requester_user_id,
                permission_name=pr.permission_name,
            )
        )

    granted_permission_names = {pr.permission_name}
    base_permission_name = pr.permission_name.removesuffix(".for_others")
    if base_permission_name and base_permission_name != pr.permission_name:
        base_permission = db.scalar(select(Permission).where(Permission.name == base_permission_name))
        if base_permission:
            granted_permission_names.add(base_permission_name)

    for permission_name in granted_permission_names:
        existing_grant = db.scalar(
            select(PermissionGrant).where(
                PermissionGrant.user_id == pr.requester_user_id,
                PermissionGrant.permission_name == permission_name,
            )
        )
        if not existing_grant:
            db.add(
                PermissionGrant(
                    user_id=pr.requester_user_id,
                    permission_name=permission_name,
                    granted_by_user_id=actor_user_id,
                )
            )


def decide_permission_request(
    db: Session,
    *,
    actor: Identity,
    request_id: int,
    decision: str,
    reason: str | None = None,
) -> PermissionRequest:
    normalized_decision = (decision or "").strip().lower()
    if normalized_decision not in {"approve", "reject"}:
        raise ValueError("decision must be 'approve' or 'reject'")

    pr = db.get(PermissionRequest, request_id)
    if not pr:
        raise ValueError("Permission request not found")
    if pr.status != "pending":
        raise ValueError("Request already decided")

    can_admin_decide = "permissions:approve" in actor.permissions
    can_target_decide = pr.request_kind == "delegation" and pr.target_user_id == actor.user_id
    if not (can_admin_decide or can_target_decide):
        raise PermissionError("Not authorized to decide this request")

    if normalized_decision == "approve":
        if pr.request_kind == "permission" and not can_admin_decide:
            raise PermissionError("Only admin approvers can approve permission requests")
        _apply_approval_grants(db, pr, actor.user_id)
        pr.status = "approved"
    else:
        pr.status = "rejected"

    pr.decision_reason = reason
    pr.decided_by_user_id = actor.user_id
    pr.decided_at = utcnow()

    requester = db.get(User, pr.requester_user_id)

    decision_payload = {
        "request_id": pr.id,
        "requester_user_id": pr.requester_user_id,
        "requester_email": requester.email if requester else None,
        "permission_name": pr.permission_name,
        "request_kind": pr.request_kind,
        "target_user_id": pr.target_user_id,
        "decided_by_user_id": actor.user_id,
    }
    decision_recipient_user_ids = {pr.requester_user_id, actor.user_id}
    for recipient_user_id in decision_recipient_user_ids:
        create_notification(
            db,
            user_id=recipient_user_id,
            event_type=f"permission.request.{pr.status}",
            payload=decision_payload,
        )

    mark_request_created_notifications_read(
        db,
        user_id=actor.user_id,
        request_id=request_id,
    )
    return pr


def mark_request_created_notifications_read(db: Session, *, user_id: int, request_id: int) -> int:
    rows = db.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.event_type == "permission.request.created",
            Notification.is_read.is_(False),
        )
    ).all()

    changed = 0
    for row in rows:
        try:
            payload = json.loads(row.payload)
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("request_id") == request_id:
            row.is_read = True
            publish_notification_update(db, row)
            changed += 1
    return changed
