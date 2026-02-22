from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class AgentRunRequest(BaseModel):
    """Schema for requesting an agent run."""
    prompt: Optional[str] = ""
    messages: Optional[List[Dict[str, Any]]] = None
    conversation_id: Optional[int] = None
    suppress_user_message: bool = False


class AgentRunResponse(BaseModel):
    """Schema for responding with an agent run ID."""
    run_id: int
    result: str
    conversation_id: int


class AgentTranscriptionRequest(BaseModel):
    """Schema for requesting speech-to-text transcription."""
    audio_base64: str
    mime_type: Optional[str] = None
    file_name: Optional[str] = None
    language: Optional[str] = None
    conversation_id: Optional[int] = None


class AgentTranscriptionResponse(BaseModel):
    """Schema for speech-to-text response."""
    text: str
    conversation_id: Optional[int] = None


class AgentRunListItem(BaseModel):
    """Schema for listing agent runs."""
    id: int
    conversation_id: Optional[int] = None
    prompt: str
    run_type: str
    action_name: Optional[str] = None
    created_at: str
    status: str
    specialist_key: Optional[str] = None
    final_output: Optional[str] = None


class ToolAuditItem(BaseModel):
    """Schema for tool audit items."""
    tool: str
    args: str
    created_at: str


class AgentRunDetail(BaseModel):
    """Schema for detailed agent run information."""
    id: int
    conversation_id: Optional[int] = None
    prompt: str
    run_type: str
    action_name: Optional[str] = None
    created_at: str
    status: str
    specialist_key: Optional[str] = None
    final_output: Optional[str] = None
    error: Optional[str] = None


class TokenUsageSummary(BaseModel):
    llm_input_tokens: int
    llm_output_tokens: int
    llm_total_tokens: int
    stt_input_tokens: int
    stt_output_tokens: int
    stt_total_tokens: int
    all_input_tokens: int
    all_output_tokens: int
    all_total_tokens: int


class ConversationListItem(BaseModel):
    """Schema for listing user conversations."""
    id: int
    kind: str
    title: str
    created_at: str
    updated_at: str
    run_count: int
    token_usage: TokenUsageSummary


class ConversationMessage(BaseModel):
    """Schema for a single chat message inside a conversation."""
    role: str
    content: str
    created_at: str


class ConversationDetailResponse(BaseModel):
    """Schema for returning a full conversation transcript."""
    id: int
    kind: str
    title: str
    created_at: str
    updated_at: str
    messages: List[ConversationMessage]


class ConversationCreateResponse(BaseModel):
    """Schema for creating a conversation."""
    id: int
    kind: str
    title: str
    created_at: str
    updated_at: str


class AgentRunDetailResponse(BaseModel):
    """Schema for responding with detailed agent run information."""
    run: AgentRunDetail
    tools: List[ToolAuditItem]


class AdminAgentRunListItem(BaseModel):
    """Schema for admin listing of agent runs."""
    id: int
    user_id: int
    prompt: str
    run_type: str
    action_name: Optional[str] = None
    created_at: str
    status: str
    specialist_key: Optional[str] = None
    final_output: Optional[str] = None
