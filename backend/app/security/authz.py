from dataclasses import dataclass
from sqlalchemy import select
from app.db.models import User


@dataclass(frozen=True)
class Identity:
    user_id: int
    permissions: set[str]


def resolve_identity(db, user_id: int) -> Identity:
    """Resolve the identity of a user by their ID."""
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise PermissionError("User not found")

    perms = {p.name for r in (user.roles or []) for p in (r.permissions or [])}
    return Identity(user.id, perms)


def require(identity: Identity, perm: str):
    """Check if the identity has the required permission."""
    if perm not in identity.permissions:
        raise PermissionError("You don't have permission to perform this action.")
