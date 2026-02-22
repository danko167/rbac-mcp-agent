from __future__ import annotations

from fastapi import Depends
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.db import get_db
from app.db.models import User
from app.security.authz import Identity, require, resolve_identity
from app.security.security import decode_token


auth_scheme = HTTPBearer()


def get_bearer_token(
    creds: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> str:
    return creds.credentials


def get_current_user_id(
    token: str = Depends(get_bearer_token),
) -> int:
    return decode_token(token)


def get_current_identity(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Identity:
    return resolve_identity(db, user_id)


def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User | None:
    return db.get(User, user_id)


def get_current_user_required(
    user: User | None = Depends(get_current_user),
) -> User:
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    return user


def require_permission(permission_name: str):
    def _dependency(identity: Identity = Depends(get_current_identity)) -> Identity:
        require(identity, permission_name)
        return identity

    return _dependency
