from __future__ import annotations

from sqlalchemy.orm import Session

from app.security.authz import resolve_identity, Identity
from app.db.models import User
from app.core.time import set_current_timezone
from mcp_app.security.auth import user_id_from_auth_header


def identity_from_bearer_with_db(db: Session, auth: str) -> Identity:
    """
    Resolve an Identity from a Bearer token in the Authorization header.
    """
    user_id = user_id_from_auth_header({"Authorization": auth})
    user = db.get(User, user_id)
    set_current_timezone(user.timezone if user else None)
    return resolve_identity(db, user_id)
