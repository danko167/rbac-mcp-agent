from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class AgentRunRequest(BaseModel):
    """Schema for requesting an agent run."""
    prompt: Optional[str] = ""
    messages: Optional[List[Dict[str, Any]]] = None


class AgentRunResponse(BaseModel):
    """Schema for responding with an agent run ID."""
    run_id: int
    result: str


class AgentRunListItem(BaseModel):
    """Schema for listing agent runs."""
    id: int
    prompt: str
    created_at: str
    status: str
    final_output: Optional[str] = None


class ToolAuditItem(BaseModel):
    """Schema for tool audit items."""
    tool: str
    args: str
    created_at: str


class AgentRunDetail(BaseModel):
    """Schema for detailed agent run information."""
    id: int
    prompt: str
    created_at: str
    status: str
    final_output: Optional[str] = None
    error: Optional[str] = None


class AgentRunDetailResponse(BaseModel):
    """Schema for responding with detailed agent run information."""
    run: AgentRunDetail
    tools: List[ToolAuditItem]


class AdminAgentRunListItem(BaseModel):
    """Schema for admin listing of agent runs."""
    id: int
    user_id: int
    prompt: str
    created_at: str
    status: str
    final_output: Optional[str] = None
