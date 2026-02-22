from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User, Role, Permission
from app.security.security import hash_password


BASIC_PERMS = [
    "weather:read",
    "notes:list", "notes:create", "notes:update", "notes:delete",
    "notifications:list",
    "permissions:request",
    "tasks:receive",
    "alarms:receive",
]

PRO_EXTRA_PERMS = [
    "tasks:list", "tasks:create", "tasks:update", "tasks:complete", "tasks:delete",
    "tasks:create.for_others",
    "notes:create.for_others",
    "alarms:set",
    "alarms:set.for_others",
]

ADMIN_EXTRA_PERMS = [
    "agent:trace:view_all",
    "permissions:approve",
]

ROLE_TO_PERMS: dict[str, list[str]] = {
    "basic": BASIC_PERMS,
    "pro": BASIC_PERMS + PRO_EXTRA_PERMS,
    "admin": BASIC_PERMS + PRO_EXTRA_PERMS + ADMIN_EXTRA_PERMS,
}

DEFAULT_USERS = [
    ("alice@example.com", "password", ["basic"]),
    ("bob@example.com", "password", ["pro"]),
    ("admin@example.com", "admin", ["admin"]),
]


def _get_or_create_permission(db: Session, name: str) -> Permission:
    """
    Get or create a Permission by name.
    """
    perm = db.scalar(select(Permission).where(Permission.name == name))
    if perm:
        return perm
    perm = Permission(name=name)
    db.add(perm)
    return perm


def _get_or_create_role(db: Session, name: str) -> Role:
    """
    Get or create a Role by name.
    """
    role = db.scalar(select(Role).where(Role.name == name))
    if role:
        return role
    role = Role(name=name)
    db.add(role)
    return role


def _get_or_create_user(db: Session, email: str) -> User:
    """
    Get or create a User by email.
    """
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(email=email, password_hash="")
    db.add(user)
    return user


def seed(db: Session) -> None:
    """
    Idempotent seeding:
    - ensures permissions exist
    - ensures roles exist and have correct permissions
    - ensures users exist and have correct roles
    """
    # 1) Ensure permissions exist
    perm_objs: dict[str, Permission] = {}
    all_perm_names = sorted({p for perms in ROLE_TO_PERMS.values() for p in perms})
    for p in all_perm_names:
        perm_objs[p] = _get_or_create_permission(db, p)

    # 2) Ensure roles exist and have correct permission sets
    role_objs: dict[str, Role] = {}
    for role_name, perm_names in ROLE_TO_PERMS.items():
        role = _get_or_create_role(db, role_name)
        role.permissions = [perm_objs[p] for p in perm_names]  # overwrite to desired set
        role_objs[role_name] = role

    # Flush so roles/permissions have PKs before linking users
    db.flush()

    # 3) Ensure users exist and have correct roles (and password if empty)
    for email, password, roles in DEFAULT_USERS:
        user = _get_or_create_user(db, email=email)

        # If already seeded but missing password_hash (or you changed schema), set it.
        if not user.password_hash:
            user.password_hash = hash_password(password)

        user.roles = [role_objs[r] for r in roles]

    db.commit()
