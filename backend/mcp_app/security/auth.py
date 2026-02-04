from __future__ import annotations

from app.security.security import decode_token


def user_id_from_auth_header(headers: dict) -> int:
    """
    Extract and decode a Bearer token from the Authorization header to get the user ID.
    """
    auth = headers.get("authorization") or headers.get("Authorization")
    if not auth or not str(auth).lower().startswith("bearer "):
        raise PermissionError("Missing Authorization: Bearer <token>")

    token = str(auth).split(" ", 1)[1]
    return decode_token(token)
