from __future__ import annotations

from sqlalchemy import select

from app.db.db import SessionLocal
from app.db.models import PermissionRequest
from app.security.authz import require
from app.services.permission_requests import create_permission_request, permission_request_item
from mcp_app.security.deps import identity_from_bearer_with_db
from mcp_app.services.audit import log_tool_call


def register(mcp):
    @mcp.tool()
    def permission_requests_create(
        auth: str,
        request_kind: str,
        permission_name: str,
        target_user_id: int | None = None,
        agent_run_id: int | None = None,
    ):
        """
        Create a permission/delegation request.
        """
        if request_kind not in {"permission", "delegation"}:
            raise ValueError("request_kind must be 'permission' or 'delegation'")

        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            require(identity, "permissions:request")
            req = create_permission_request(
                db,
                requester_user_id=identity.user_id,
                request_kind=request_kind,
                permission_name=permission_name,
                target_user_id=target_user_id,
            )

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="permission_requests.create",
                args={
                    "request_kind": req.request_kind,
                    "permission_name": req.permission_name,
                    "target_user_id": target_user_id,
                },
                agent_run_id=agent_run_id,
            )

            return permission_request_item(req)

    @mcp.tool()
    def permission_requests_mine(auth: str, agent_run_id: int | None = None):
        """
        List current user's permission requests.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            require(identity, "permissions:request")

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="permission_requests.mine",
                args={},
                agent_run_id=agent_run_id,
            )

            rows = db.scalars(
                select(PermissionRequest)
                .where(PermissionRequest.requester_user_id == identity.user_id)
                .order_by(PermissionRequest.created_at.desc())
            ).all()

            return [permission_request_item(r) for r in rows]
