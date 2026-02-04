from pydantic import BaseModel
from typing import List


class TokenResponse(BaseModel):
    """Response model for authentication token."""
    access_token: str


class MeResponse(BaseModel):
    """Response model for authenticated user details."""
    id: int
    email: str
    roles: List[str]
    permissions: List[str]


class LoginRequest(BaseModel):
    """Request model for user login."""
    email: str
    password: str


class TokenResponse(BaseModel):
    """Response model for authentication token."""
    access_token: str


class MeResponse(BaseModel):
    """Response model for authenticated user details."""
    id: int
    email: str
    roles: List[str]
    permissions: List[str]

