from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.db import SessionLocal
from app.db.models import Delegation, PermissionRequest, User, utcnow
from app.security.authz import resolve_identity
from app.services.permission_requests import decide_permission_request, permission_request_item
from mcp_app.security.deps import identity_from_bearer_with_db
from mcp_app.services.audit import log_tool_call


def _permission_request_item(db, pr: PermissionRequest) -> dict:
    base = permission_request_item(pr)
    requester = db.get(User, pr.requester_user_id)
    target = db.get(User, pr.target_user_id) if pr.target_user_id else None
    return {
        **base,
        "requester_email": requester.email if requester else None,
        "target_user_email": target.email if target else None,
    }


def _delegation_item(db, delegation: Delegation) -> dict:
    grantor = db.get(User, delegation.grantor_user_id)
    grantee = db.get(User, delegation.grantee_user_id)
    return {
        "id": delegation.id,
        "grantor_user_id": delegation.grantor_user_id,
        "grantor_email": grantor.email if grantor else None,
        "grantee_user_id": delegation.grantee_user_id,
        "grantee_email": grantee.email if grantee else None,
        "permission_name": delegation.permission_name,
        "expires_at": delegation.expires_at.isoformat() if delegation.expires_at else None,
        "revoked_at": delegation.revoked_at.isoformat() if delegation.revoked_at else None,
        "created_at": delegation.created_at.isoformat(),
    }


def _parse_expires_at(expires_at: str | None) -> datetime | None:
    value = (expires_at or "").strip()
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed_utc = parsed.astimezone(timezone.utc)
    if parsed_utc <= utcnow():
        raise ValueError("expires_at must be in the future")
    return parsed_utc


def _resolve_single_actionable_request_id(db, user_id: int) -> int:
    resolved = resolve_identity(db, user_id)
    is_admin_approver = "permissions:approve" in resolved.permissions

    stmt = (
        select(PermissionRequest)
        .where(PermissionRequest.status == "pending")
        .order_by(PermissionRequest.created_at.desc())
    )
    if is_admin_approver:
        rows = db.scalars(stmt).all()
    else:
        rows = db.scalars(
            stmt.where(
                PermissionRequest.request_kind == "delegation",
                PermissionRequest.target_user_id == user_id,
            )
        ).all()

    if len(rows) == 1:
        return int(rows[0].id)
    if len(rows) == 0:
        raise ValueError("No pending approval requests were found for you")
    raise ValueError("Multiple pending approval requests found; specify request_id")


def register(mcp):
    @mcp.tool()
    def approvals_requests_list(
        auth: str,
        status: str = "pending",
        agent_run_id: int | None = None,
    ):
        """
        List approval requests the current user can act on.
        - Admin approvers see all requests.
        - Non-admin users see delegation requests where they are target_user_id.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            resolved = resolve_identity(db, identity.user_id)
            is_admin_approver = "permissions:approve" in resolved.permissions

            stmt = select(PermissionRequest).order_by(PermissionRequest.created_at.desc())
            normalized_status = (status or "").strip().lower()
            if normalized_status:
                stmt = stmt.where(PermissionRequest.status == normalized_status)

            if is_admin_approver:
                rows = db.scalars(stmt).all()
            else:
                rows = db.scalars(
                    stmt.where(
                        PermissionRequest.request_kind == "delegation",
                        PermissionRequest.target_user_id == identity.user_id,
                    )
                ).all()

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="approvals.requests_list",
                args={"status": status},
                agent_run_id=agent_run_id,
            )

            return [_permission_request_item(db, row) for row in rows]

    @mcp.tool()
    def approvals_request_decide(
        auth: str,
        request_id: int | None = None,
        decision: str = "",
        reason: str | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Approve or reject a permission request.
        Admin approvers can decide all requests.
        Delegation targets can decide delegation requests where target_user_id == current user.
        """
        normalized_decision = (decision or "").strip().lower()
        if normalized_decision not in {"approve", "reject"}:
            raise ValueError("decision must be 'approve' or 'reject'")

        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            resolved = resolve_identity(db, identity.user_id)

            resolved_request_id = request_id
            if resolved_request_id is None:
                resolved_request_id = _resolve_single_actionable_request_id(db, identity.user_id)

            try:
                pr = decide_permission_request(
                    db,
                    actor=resolved,
                    request_id=resolved_request_id,
                    decision=normalized_decision,
                    reason=reason,
                )
            except ValueError as exc:
                message = str(exc).lower()
                if "not found" not in message and "already decided" not in message:
                    raise

                fallback_request_id = _resolve_single_actionable_request_id(db, identity.user_id)
                if fallback_request_id == resolved_request_id:
                    raise

                resolved_request_id = fallback_request_id
                pr = decide_permission_request(
                    db,
                    actor=resolved,
                    request_id=resolved_request_id,
                    decision=normalized_decision,
                    reason=reason,
                )

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="approvals.request_decide",
                args={"request_id": resolved_request_id, "decision": normalized_decision, "reason": reason},
                agent_run_id=agent_run_id,
            )

            return _permission_request_item(db, pr)

    @mcp.tool()
    def delegations_mine(
        auth: str,
        include_revoked: bool = False,
        agent_run_id: int | None = None,
    ):
        """
        List delegations where current user is account owner (grantor).
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)

            stmt = (
                select(Delegation)
                .where(Delegation.grantor_user_id == identity.user_id)
                .order_by(Delegation.created_at.desc())
            )
            now = utcnow()
            if not include_revoked:
                stmt = stmt.where(
                    Delegation.revoked_at.is_(None),
                    ((Delegation.expires_at.is_(None)) | (Delegation.expires_at > now)),
                )

            rows = db.scalars(stmt).all()

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="delegations.mine",
                args={"include_revoked": include_revoked},
                agent_run_id=agent_run_id,
            )

            return [_delegation_item(db, row) for row in rows]

    @mcp.tool()
    def delegations_update_expiration(
        auth: str,
        delegation_id: int,
        expires_at: str | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Update (or clear) expiration for a delegation.
        Allowed for account owner (grantor) and admin approvers.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            resolved = resolve_identity(db, identity.user_id)

            delegation = db.get(Delegation, delegation_id)
            if not delegation:
                raise ValueError("Delegation not found")

            is_admin_approver = "permissions:approve" in resolved.permissions
            is_owner = delegation.grantor_user_id == identity.user_id
            if not (is_admin_approver or is_owner):
                raise PermissionError("Not authorized to update this delegation")

            delegation.expires_at = _parse_expires_at(expires_at)

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="delegations.update_expiration",
                args={"delegation_id": delegation_id, "expires_at": expires_at},
                agent_run_id=agent_run_id,
            )

            return _delegation_item(db, delegation)

    @mcp.tool()
    def delegations_revoke(
        auth: str,
        delegation_id: int,
        agent_run_id: int | None = None,
    ):
        """
        Revoke a delegation.
        Allowed for account owner (grantor) and admin approvers.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            resolved = resolve_identity(db, identity.user_id)

            delegation = db.get(Delegation, delegation_id)
            if not delegation:
                raise ValueError("Delegation not found")

            is_admin_approver = "permissions:approve" in resolved.permissions
            is_owner = delegation.grantor_user_id == identity.user_id
            if not (is_admin_approver or is_owner):
                raise PermissionError("Not authorized to revoke this delegation")

            if delegation.revoked_at is None:
                delegation.revoked_at = utcnow()

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="delegations.revoke",
                args={"delegation_id": delegation_id},
                agent_run_id=agent_run_id,
            )

            return _delegation_item(db, delegation)
