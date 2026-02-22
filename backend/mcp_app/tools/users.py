from __future__ import annotations

from sqlalchemy import select

from app.db.db import SessionLocal
from app.db.models import User
from app.security.authz import require
from mcp_app.security.deps import identity_from_bearer_with_db
from mcp_app.services.audit import log_tool_call


def register(mcp):
    @mcp.tool()
    def users_list(auth: str, query: str | None = None, agent_run_id: int | None = None):
        """
        List users for lookup flows (for example, delegation/approval targeting).
        Optional query filters by email substring.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            require(identity, "permissions:request")

            stmt = select(User).order_by(User.email.asc())
            q = (query or "").strip().lower()
            if q:
                users = db.scalars(stmt.where(User.email.ilike(f"%{q}%"))).all()
            else:
                users = db.scalars(stmt).all()

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="users.list",
                args={"query": query},
                agent_run_id=agent_run_id,
            )

            return [{"id": u.id, "email": u.email} for u in users]
