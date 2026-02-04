from __future__ import annotations

import json
from typing import Any, Dict, List

from app.core.time import now_in_app_tz
from app.core.config import get_settings


def now_context() -> str:
    """Build a string with the current local time context."""
    settings = get_settings()
    now = now_in_app_tz()
    return (
        f"Current local time: {now.isoformat()}\n"
        f"Local date: {now.date().isoformat()}\n"
        f"Timezone: {settings.app_timezone}\n"
    )


def build_capabilities_text(perms: List[str], perms_status: str) -> str:
    """Build a capabilities description text based on permissions."""
    if perms_status != "ok":
        return "- (Unable to load permissions from auth_me; capabilities unknown)"

    p = set(perms)
    lines: List[str] = []

    notes = [label for k, label in [
        ("notes:list", "list"),
        ("notes:create", "create"),
        ("notes:update", "update"),
        ("notes:delete", "delete"),
    ] if k in p]
    if notes:
        lines.append(f"- Notes: {', '.join(notes)}")

    tasks = [label for k, label in [
        ("tasks:list", "list"),
        ("tasks:create", "create"),
        ("tasks:update", "update"),
        ("tasks:complete", "complete"),
        ("tasks:delete", "delete"),
    ] if k in p]
    if tasks:
        lines.append(f"- Tasks: {', '.join(tasks)}")

    if "weather:read" in p:
        lines.append("- Weather: read")
    if "agent:trace:view_all" in p:
        lines.append("- Admin: view all agent traces")

    return "\n".join(lines) if lines else "- (No tool permissions detected for this user)"


def build_system_prompt(*, perms_status: str, me_for_model: Dict[str, Any], capabilities_text: str) -> str:
    """Build the system prompt for the assistant, including permissions and capabilities context."""
    return (
        "You are a permission-aware assistant.\n"
        "- You may call tools.\n"
        "- Some tool calls may fail due to permissions.\n"
        "- Tool results will be provided back to you in messages starting with 'TOOL_RESULT'.\n"
        "- If a tool result payload contains {\"ok\": false, \"error\": ...}, explain politely "
        "that the user lacks permission and suggest alternatives.\n"
        "- Keep context from the conversation provided.\n\n"
        "PERMISSIONS FETCH STATUS:\n"
        f"{perms_status}\n\n"
        "USER PERMISSIONS (authoritative if status=ok):\n"
        f"{json.dumps(me_for_model, ensure_ascii=False)}\n\n"
        "CAPABILITIES (derived from permissions; do not contradict this):\n"
        f"{capabilities_text}\n\n"
        "TIME CONTEXT (authoritative):\n"
        + now_context()
        + "\n"
        "IMPORTANT TASK EDITING RULE:\n"
        "- If the user asks to modify an existing task (change due date/title/completed), do NOT create a new task.\n"
        "- Prefer tasks_update. If you need task_id, call tasks_list.\n\n"
        "DUE DATE RULE (TASKS):\n"
        "- due_on may be one of:\n"
        "  * 'today' or 'tomorrow'\n"
        "  * ISO format 'YYYY-MM-DD'\n"
        "  * natural phrases like 'next week', 'friday', 'this friday', 'next friday', 'next wednesday'\n"
        "- If the user gives a weekday/week phrase, pass it through as-is (do NOT guess ISO).\n\n"
        "WEATHER RULE:\n"
        "- Location matching is case-insensitive (\"prague\" == \"Prague\"). Do NOT ask to confirm capitalization.\n"
        "- Call weather_read if user asks about weather and gives a plausible place name.\n"
        "- Ask 'Which location?' only if location is missing or is relative (near me/here).\n"
        "- Always pass 'when' based on the user request:\n"
            "  * current/now -> when='now'\n"
            "  * today -> when='today'\n"
            "  * tomorrow -> when='tomorrow'\n"
            "  * next week / next 7 days -> when='next_7_days'\n"
            "  * next 14 days -> when='next_14_days'\n"
            "  * specific date -> when='YYYY-MM-DD'\n"
            "  * date range -> when='YYYY-MM-DD..YYYY-MM-DD'\n"
        "- Use granularity='auto' unless user asks otherwise.\n"
        "- When answering weather:\n"
        "  * If payload contains 'day', answer from 'day'.\n"
        "  * Else if payload contains 'daily', answer from 'daily'.\n"
        "  * Only use 'current' if it's a now/current question.\n"
        "- If no location is given (e.g. “what's the weather?”), ask: “Which location?”\n"
        "- Pass location exactly as a human place name.\n"
    )