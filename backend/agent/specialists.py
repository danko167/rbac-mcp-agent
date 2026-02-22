from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Sequence


@dataclass(frozen=True)
class AgentProfile:
    key: str
    name: str
    allowed_prefixes: tuple[str, ...]
    instruction: str


GENERAL_PROFILE = AgentProfile(
    key="general",
    name="General Agent",
    allowed_prefixes=(),
    instruction=(
        "Handle mixed-domain requests and choose tools based on user intent and permissions."
    ),
)

WORK_PROFILE = AgentProfile(
    key="work",
    name="Work Agent",
    allowed_prefixes=(
        "notes_",
        "tasks_",
        "alarms_",
        "weather_",
        "auth_",
        "users_",
        "permission_requests_",
        "approvals_",
        "delegations_",
    ),
    instruction=(
        "Focus on user productivity: notes, tasks, alarms, and weather. "
        "Avoid governance workflows unless user explicitly requests them."
    ),
)

GOVERNANCE_PROFILE = AgentProfile(
    key="governance",
    name="Governance Agent",
    allowed_prefixes=("permission_requests_", "approvals_", "delegations_", "users_", "auth_"),
    instruction=(
        "Focus on access governance: permission requests, approvals, delegations, and user lookup. "
        "Avoid creating or managing work items unless user explicitly asks for that."
    ),
)


def _last_user_text(convo: List[dict[str, Any]]) -> str:
    for message in reversed(convo):
        if isinstance(message, dict) and message.get("role") == "user":
            return str(message.get("content") or "").strip().lower()
    return ""


def route_agent_profile(convo: List[dict[str, Any]]) -> AgentProfile:
    text = _last_user_text(convo)
    if not text:
        return GENERAL_PROFILE

    governance_keywords = (
        "permission",
        "permisson",
        "approve",
        "approval",
        "reject",
        "delegation",
        "delegate",
        "access",
        "grant",
        "revoke",
        "role",
    )
    work_keywords = (
        "task",
        "note",
        "alarm",
        "weather",
        "todo",
    )

    governance_hits = sum(1 for keyword in governance_keywords if keyword in text)
    work_hits = sum(1 for keyword in work_keywords if keyword in text)

    if governance_hits > work_hits and governance_hits > 0:
        return GOVERNANCE_PROFILE
    if work_hits > governance_hits and work_hits > 0:
        return WORK_PROFILE
    return GENERAL_PROFILE


def is_tool_allowed(profile: AgentProfile, tool_name: str) -> bool:
    if profile.key == "general":
        return True
    return any(tool_name.startswith(prefix) for prefix in profile.allowed_prefixes)


def _tool_name(tool: Any) -> str:
    if isinstance(tool, dict):
        return str(tool.get("name") or "")
    return str(getattr(tool, "name", "") or "")


def filter_tools_for_profile(tools: Sequence[Any], profile: AgentProfile) -> list[Any]:
    if profile.key == "general":
        return list(tools)
    return [tool for tool in tools if is_tool_allowed(profile, _tool_name(tool))]
