from dataclasses import dataclass
from sqlalchemy import select
from app.db.models import User, Delegation, PermissionGrant
from app.db.models import utcnow


@dataclass
class AuthorizationError(PermissionError):
    code: str
    explanation: str
    next_actions: list[str]

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "explanation": self.explanation,
            "next_actions": self.next_actions,
        }


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
    extra = db.scalars(
        select(PermissionGrant).where(PermissionGrant.user_id == user_id)
    ).all()
    perms |= {g.permission_name for g in extra}
    return Identity(user.id, perms)


def authorize(db, actor: Identity, permission_name: str, target_user_id: int | None = None) -> int:
    """
    Centralized authorization for actor/target actions.

    Returns effective target user id when authorized.
    Raises AuthorizationError with typed reasons when denied.
    """
    target = target_user_id if target_user_id is not None else actor.user_id

    if permission_name not in actor.permissions:
        raise AuthorizationError(
            code="MISSING_PERMISSION",
            explanation=f"Missing required permission: {permission_name}",
            next_actions=[
                "Request this permission via permission request workflow.",
                "Try an operation you are already permitted to perform.",
            ],
        )

    if target == actor.user_id:
        return target

    for_others_permission = f"{permission_name}.for_others"
    if for_others_permission not in actor.permissions:
        raise AuthorizationError(
            code="MISSING_PERMISSION",
            explanation=(
                f"To act on behalf of another user, you need: {for_others_permission}"
            ),
            next_actions=[
                "Request permission to act on behalf of other users (.for_others).",
                "Run the action for your own account instead.",
            ],
        )

    now = utcnow()
    delegation = db.scalar(
        select(Delegation).where(
            Delegation.grantor_user_id == target,
            Delegation.grantee_user_id == actor.user_id,
            Delegation.permission_name == for_others_permission,
            Delegation.revoked_at.is_(None),
            (Delegation.expires_at.is_(None) | (Delegation.expires_at > now)),
        )
    )
    if not delegation:
        raise AuthorizationError(
            code="MISSING_DELEGATION",
            explanation=(
                f"No active delegation from account owner {target} allows you to use {for_others_permission} on their behalf."
            ),
            next_actions=[
                "Ask the account owner to delegate this action to you.",
                "Choose an account owner who has already delegated this action to you.",
            ],
        )

    target_identity = resolve_identity(db, target)
    required_target_receive: dict[str, str] = {
        "tasks:create": "tasks:receive",
        "alarms:set": "alarms:receive",
    }
    target_permission = required_target_receive.get(permission_name)
    if target_permission and target_permission not in target_identity.permissions:
        raise AuthorizationError(
            code="TARGET_LACKS_ACCESS",
            explanation=f"The selected account owner does not have required access: {target_permission}",
            next_actions=[
                "Choose a different account owner.",
                "Have an admin grant the owner this required receive permission.",
            ],
        )

    return target


def require(identity: Identity, perm: str):
    """Check if the identity has the required permission."""
    if perm not in identity.permissions:
        raise AuthorizationError(
            code="MISSING_PERMISSION",
            explanation=f"Missing required permission: {perm}",
            next_actions=["Request access to this permission."],
        )
