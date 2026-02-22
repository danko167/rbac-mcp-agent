from pydantic import BaseModel
from typing import List

from app.schemas.agent import TokenUsageSummary


class TokenResponse(BaseModel):
    """Response model for authentication token."""
    access_token: str


class PermissionDetail(BaseModel):
    permission: str
    tool: str
    tool_label: str
    category: str
    category_label: str
    title: str
    description: str


class MeResponse(BaseModel):
    """Response model for authenticated user details."""
    id: int
    email: str
    roles: List[str]
    permissions: List[str]
    permission_details: List[PermissionDetail]
    timezone: str
    token_usage: TokenUsageSummary


class LoginRequest(BaseModel):
    """Request model for user login."""
    email: str
    password: str


class UpdateTimezoneRequest(BaseModel):
    """Request model for updating a user's timezone."""
    timezone: str | None

