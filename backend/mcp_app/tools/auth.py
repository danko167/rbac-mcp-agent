from __future__ import annotations

from sqlalchemy import select

from app.db.db import SessionLocal
from app.db.models import User, user_roles, role_permissions
from mcp_app.security.deps import identity_from_bearer_with_db
from mcp_app.services.audit import log_tool_call


def register(mcp):
    @mcp.tool()
    def auth_me(auth: str, agent_run_id: int | None = None):
        """
        Get information about the authenticated user.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)

            user = db.scalar(select(User).where(User.id == identity.user_id))
            if not user:
                raise PermissionError("User not found")

            role_names = [r.name for r in (user.roles or [])]
            perms = {p.name for r in (user.roles or []) for p in (r.permissions or [])}

            ur_count = db.execute(
                select(user_roles.c.user_id).where(user_roles.c.user_id == identity.user_id)
            ).all()
            rp_count = db.execute(select(role_permissions.c.role_id)).all()

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="auth.me",
                args={},
                agent_run_id=agent_run_id,
            )

            return {
                "user_id": identity.user_id,
                "roles": role_names,
                "permissions": sorted(perms),
                "debug": {
                    "user_roles_rows_for_user": len(ur_count),
                    "role_permissions_rows_total": len(rp_count),
                },
            }
