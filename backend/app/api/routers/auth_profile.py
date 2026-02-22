from __future__ import annotations

import logging

from zoneinfo import ZoneInfo, available_timezones

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import build_permission_view
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.time import effective_user_timezone
from app.db.db import get_db
from app.db.models import User
from app.schemas.auth import LoginRequest, MeResponse, TokenResponse, UpdateTimezoneRequest
from app.security.authz import resolve_identity
from app.security.deps import get_current_user_required
from app.security.security import create_token, verify_password
from app.services.token_usage import get_user_usage_summary

router = APIRouter()
logger = logging.getLogger("app.api.auth")
_settings = get_settings()
_login_rate_limiter = SlidingWindowRateLimiter(
    max_requests=_settings.login_rate_limit_attempts,
    window_seconds=_settings.login_rate_limit_window_seconds,
)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    limiter_key = f"{client_ip}:{(payload.email or '').strip().lower()}"
    decision = _login_rate_limiter.evaluate(limiter_key)
    if not decision.allowed:
        logger.warning("Login rate limit exceeded for email=%s client_ip=%s", payload.email, client_ip)
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        logger.warning("Login failed for email=%s client_ip=%s", payload.email, client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    logger.info("Login succeeded for user_id=%s client_ip=%s", user.id, client_ip)
    return {"access_token": create_token(user.id)}


@router.get("/me", response_model=MeResponse)
def me(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    identity = resolve_identity(db, user.id)
    sorted_permissions = sorted(list(identity.permissions))
    usage_summary = get_user_usage_summary(db, user_id=user.id)

    return {
        "id": user.id,
        "email": user.email,
        "roles": [r.name for r in user.roles],
        "permissions": sorted_permissions,
        "permission_details": [build_permission_view(permission) for permission in sorted_permissions],
        "timezone": effective_user_timezone(user.timezone),
        "token_usage": usage_summary,
    }


@router.get("/timezones", response_model=list[str])
def list_timezones(
    user: User = Depends(get_current_user_required),
):
    _ = user
    return sorted(available_timezones())


@router.put("/me/timezone", response_model=MeResponse)
def update_my_timezone(
    payload: UpdateTimezoneRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    timezone_name = (payload.timezone or "").strip()
    if not timezone_name:
        raise HTTPException(status_code=400, detail="timezone is required")

    try:
        ZoneInfo(timezone_name)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timezone")

    user.timezone = timezone_name
    db.commit()
    db.refresh(user)

    identity = resolve_identity(db, user.id)
    sorted_permissions = sorted(list(identity.permissions))
    usage_summary = get_user_usage_summary(db, user_id=user.id)

    return {
        "id": user.id,
        "email": user.email,
        "roles": [r.name for r in user.roles],
        "permissions": sorted_permissions,
        "permission_details": [build_permission_view(permission) for permission in sorted_permissions],
        "timezone": effective_user_timezone(user.timezone),
        "token_usage": usage_summary,
    }
