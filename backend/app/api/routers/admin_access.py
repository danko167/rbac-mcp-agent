from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.db import get_db
from app.db.models import AgentRun, Delegation, Permission, Role, ToolAudit, User, utcnow
from app.schemas.agent import AdminAgentRunListItem, AgentRunDetailResponse
from app.security.deps import get_current_user_id, require_permission
from app.services.agent_run_meta import action_name_from_prompt, run_type_from_prompt
from app.services.api_trace import record_api_action

router = APIRouter()
DEFAULT_ADMIN_LIMIT = 100
MAX_ADMIN_LIMIT = 500


def _role_item(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "permissions": sorted([p.name for p in role.permissions]),
    }


def _permission_item(permission: Permission) -> dict:
    return {
        "id": permission.id,
        "name": permission.name,
    }


def _user_role_item(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "roles": sorted([r.name for r in user.roles]),
    }


def _delegation_item(db: Session, delegation: Delegation) -> dict:
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


def _delegation_item_with_user_map(delegation: Delegation, user_map: dict[int, User]) -> dict:
    grantor = user_map.get(delegation.grantor_user_id)
    grantee = user_map.get(delegation.grantee_user_id)
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


@router.get("/admin/agent/runs", response_model=list[AdminAgentRunListItem])
def admin_runs(
    limit: int = Query(default=DEFAULT_ADMIN_LIMIT, ge=1, le=MAX_ADMIN_LIMIT),
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("agent:trace:view_all")),
    db: Session = Depends(get_db),
):
    runs = db.scalars(
        select(AgentRun)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "prompt": r.prompt,
            "run_type": run_type_from_prompt(r.prompt),
            "action_name": action_name_from_prompt(r.prompt),
            "created_at": r.started_at.isoformat(),
            "status": r.status,
            "specialist_key": r.specialist_key,
            "final_output": r.final_output,
        }
        for r in runs
    ]


@router.get("/admin/rbac/roles")
def admin_list_roles(
    limit: int = Query(default=DEFAULT_ADMIN_LIMIT, ge=1, le=MAX_ADMIN_LIMIT),
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    roles = db.scalars(
        select(Role)
        .options(selectinload(Role.permissions))
        .order_by(Role.name.asc())
        .limit(limit)
    ).all()
    return [_role_item(r) for r in roles]


@router.get("/admin/rbac/permissions")
def admin_list_permissions(
    limit: int = Query(default=DEFAULT_ADMIN_LIMIT, ge=1, le=MAX_ADMIN_LIMIT),
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    permissions = db.scalars(
        select(Permission)
        .order_by(Permission.name.asc())
        .limit(limit)
    ).all()
    return [_permission_item(p) for p in permissions]


@router.get("/admin/rbac/users")
def admin_list_users_with_roles(
    limit: int = Query(default=DEFAULT_ADMIN_LIMIT, ge=1, le=MAX_ADMIN_LIMIT),
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    users = db.scalars(
        select(User)
        .options(selectinload(User.roles))
        .order_by(User.email.asc())
        .limit(limit)
    ).all()
    return [_user_role_item(u) for u in users]


@router.post("/admin/rbac/roles/{role_id}/permissions/{permission_id}")
def admin_assign_permission_to_role(
    role_id: int,
    permission_id: int,
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    permission = db.get(Permission, permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")

    if permission not in role.permissions:
        role.permissions.append(permission)
        db.commit()

    record_api_action(
        user_id=user_id,
        action="admin.rbac.role_permission.assign",
        args={"role_id": role_id, "permission_id": permission_id},
        result={"ok": True},
    )

    return _role_item(role)


@router.delete("/admin/rbac/roles/{role_id}/permissions/{permission_id}")
def admin_unassign_permission_from_role(
    role_id: int,
    permission_id: int,
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    permission = db.get(Permission, permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")

    if permission in role.permissions:
        role.permissions.remove(permission)
        db.commit()

    record_api_action(
        user_id=user_id,
        action="admin.rbac.role_permission.unassign",
        args={"role_id": role_id, "permission_id": permission_id},
        result={"ok": True},
    )

    return _role_item(role)


@router.post("/admin/rbac/users/{target_user_id}/roles/{role_id}")
def admin_assign_role_to_user(
    target_user_id: int,
    role_id: int,
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    user = db.get(User, target_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role not in user.roles:
        user.roles.append(role)
        db.commit()

    record_api_action(
        user_id=user_id,
        action="admin.rbac.user_role.assign",
        args={"target_user_id": target_user_id, "role_id": role_id},
        result={"ok": True},
    )

    return _user_role_item(user)


@router.delete("/admin/rbac/users/{target_user_id}/roles/{role_id}")
def admin_unassign_role_from_user(
    target_user_id: int,
    role_id: int,
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    user = db.get(User, target_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role in user.roles:
        user.roles.remove(role)
        db.commit()

    record_api_action(
        user_id=user_id,
        action="admin.rbac.user_role.unassign",
        args={"target_user_id": target_user_id, "role_id": role_id},
        result={"ok": True},
    )

    return _user_role_item(user)


@router.get("/admin/rbac/delegations")
def admin_list_delegations(
    include_revoked: bool = False,
    limit: int = Query(default=DEFAULT_ADMIN_LIMIT, ge=1, le=MAX_ADMIN_LIMIT),
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    stmt = select(Delegation).order_by(Delegation.created_at.desc())
    now = utcnow()
    if not include_revoked:
        stmt = stmt.where(
            Delegation.revoked_at.is_(None),
            ((Delegation.expires_at.is_(None)) | (Delegation.expires_at > now)),
        )
    stmt = stmt.limit(limit)

    delegations = db.scalars(stmt).all()
    if not delegations:
        return []

    related_user_ids = {
        delegation.grantor_user_id
        for delegation in delegations
    } | {
        delegation.grantee_user_id
        for delegation in delegations
    }
    users = db.scalars(select(User).where(User.id.in_(related_user_ids))).all()
    user_map = {user.id: user for user in users}
    return [_delegation_item_with_user_map(d, user_map) for d in delegations]


@router.post("/admin/rbac/delegations")
def admin_create_delegation(
    payload: dict = Body(...),
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    grantor_user_id = payload.get("grantor_user_id")
    grantee_user_id = payload.get("grantee_user_id")
    permission_name = (payload.get("permission_name") or "").strip()
    expires_at_raw = (payload.get("expires_at") or "").strip()

    if not isinstance(grantor_user_id, int) or not isinstance(grantee_user_id, int):
        raise HTTPException(
            status_code=400,
            detail="Both account owner and acting user are required",
        )
    if grantor_user_id == grantee_user_id:
        raise HTTPException(
            status_code=400,
            detail="Account owner and acting user must be different users",
        )
    if not permission_name:
        raise HTTPException(status_code=400, detail="permission_name is required")
    if not permission_name.endswith(".for_others"):
        raise HTTPException(
            status_code=400,
            detail="Delegated action must be an 'act on behalf of others' permission (ends with .for_others)",
        )

    expires_at = None
    if expires_at_raw:
        try:
            parsed = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            expires_at = parsed.astimezone(timezone.utc)
        except Exception:
            raise HTTPException(status_code=400, detail="expires_at must be ISO-8601 datetime")

        if expires_at <= utcnow():
            raise HTTPException(status_code=400, detail="expires_at must be in the future")

    grantor = db.get(User, grantor_user_id)
    if not grantor:
        raise HTTPException(status_code=404, detail="Account owner not found")
    grantee = db.get(User, grantee_user_id)
    if not grantee:
        raise HTTPException(status_code=404, detail="Acting user not found")

    permission = db.scalar(select(Permission).where(Permission.name == permission_name))
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")

    existing = db.scalar(
        select(Delegation).where(
            Delegation.grantor_user_id == grantor_user_id,
            Delegation.grantee_user_id == grantee_user_id,
            Delegation.permission_name == permission_name,
            Delegation.revoked_at.is_(None),
        )
    )
    if existing:
        return _delegation_item(db, existing)

    delegation = Delegation(
        grantor_user_id=grantor_user_id,
        grantee_user_id=grantee_user_id,
        permission_name=permission_name,
        expires_at=expires_at,
    )
    db.add(delegation)
    db.commit()

    record_api_action(
        user_id=user_id,
        action="admin.rbac.delegation.create",
        args={
            "grantor_user_id": grantor_user_id,
            "grantee_user_id": grantee_user_id,
            "permission_name": permission_name,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
        result={"delegation_id": delegation.id},
    )

    return _delegation_item(db, delegation)


@router.delete("/admin/rbac/delegations/{delegation_id}")
def admin_revoke_delegation(
    delegation_id: int,
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("permissions:approve")),
    db: Session = Depends(get_db),
):
    delegation = db.get(Delegation, delegation_id)
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")

    if delegation.revoked_at is None:
        delegation.revoked_at = utcnow()
        db.commit()

    record_api_action(
        user_id=user_id,
        action="admin.rbac.delegation.revoke",
        args={"delegation_id": delegation_id},
        result={"ok": True},
    )

    return _delegation_item(db, delegation)


@router.get("/admin/agent/runs/{run_id}", response_model=AgentRunDetailResponse)
def admin_run_detail(
    run_id: int,
    user_id: int = Depends(get_current_user_id),
    _: object = Depends(require_permission("agent:trace:view_all")),
    db: Session = Depends(get_db),
):
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Not found")

    tools = db.scalars(
        select(ToolAudit)
        .where(ToolAudit.agent_run_id == run_id)
        .order_by(ToolAudit.created_at.asc())
    ).all()

    return {
        "run": {
            "id": run.id,
            "user_id": run.user_id,
            "conversation_id": run.conversation_id,
            "prompt": run.prompt,
            "run_type": run_type_from_prompt(run.prompt),
            "action_name": action_name_from_prompt(run.prompt),
            "created_at": run.started_at.isoformat(),
            "status": getattr(run, "status", "ok"),
            "specialist_key": run.specialist_key,
            "final_output": run.final_output,
            "error": getattr(run, "error", None),
        },
        "tools": [
            {"tool": t.tool_name, "args": t.arguments, "created_at": t.created_at.isoformat()}
            for t in tools
        ],
    }
