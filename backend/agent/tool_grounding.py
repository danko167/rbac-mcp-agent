from __future__ import annotations

from typing import Any, Dict, List


def normalize_tool_name(name: str) -> str:
    return (name or "").strip().replace(".", "_").lower()


def latest_success_result(tool_results: List[Dict[str, Any]], tool_name: str) -> Any | None:
    latest: Any | None = None
    expected = normalize_tool_name(tool_name)
    for tool_result in tool_results:
        current = normalize_tool_name(str(tool_result.get("tool") or ""))
        if tool_result.get("ok") is True and current == expected:
            latest = tool_result.get("result")
    return latest


def summarize_alarms_for_user(alarms: list[dict[str, Any]]) -> str:
    if not alarms:
        return "You currently have no active alarms."
    if len(alarms) == 1:
        first = alarms[0]
        title = first.get("title")
        fire_at = first.get("fire_at_local") or first.get("fire_at")
        creator_email = first.get("creator_email")
        if isinstance(title, str) and isinstance(fire_at, str):
            if isinstance(creator_email, str) and creator_email.strip():
                return f'You have one active alarm titled "{title}" set for {fire_at} (set by {creator_email}).'
            return f'You have one active alarm titled "{title}" set for {fire_at}.'
        return "You have one active alarm."

    lines = ["You have these active alarms:"]
    for idx, alarm in enumerate(alarms[:5], start=1):
        title = alarm.get("title")
        fire_at = alarm.get("fire_at_local") or alarm.get("fire_at")
        creator_email = alarm.get("creator_email")
        if isinstance(title, str) and isinstance(fire_at, str):
            if isinstance(creator_email, str) and creator_email.strip():
                lines.append(f'{idx}. "{title}" at {fire_at} (set by {creator_email})')
            else:
                lines.append(f'{idx}. "{title}" at {fire_at}')
        elif isinstance(title, str):
            lines.append(f'{idx}. "{title}"')
        else:
            lines.append(f"{idx}. Alarm {alarm.get('id', idx)}")
    return "\n".join(lines)


def mutation_success_text(tool_results: List[Dict[str, Any]]) -> str | None:
    """Return deterministic success text for mutation tools when evidence is explicit."""
    success_tools = [
        tool_result
        for tool_result in tool_results
        if tool_result.get("ok") is True and isinstance(tool_result.get("tool"), str)
    ]
    if not success_tools:
        return None

    last = success_tools[-1]
    tool = normalize_tool_name(str(last.get("tool") or ""))
    result = last.get("result")

    if tool in {"alarms_cancel", "alarms_cancel_by_title"}:
        if isinstance(result, dict):
            title = result.get("title")
            if isinstance(title, str) and title.strip():
                return f'Cancelled alarm "{title}".'
        return "Alarm cancelled successfully."

    if tool == "alarms_delete":
        return "Alarm deleted successfully."

    if tool == "alarms_update":
        if isinstance(result, dict):
            title = result.get("title")
            fire_at = result.get("fire_at_local") or result.get("fire_at")
            if isinstance(title, str) and isinstance(fire_at, str):
                return f'Alarm updated: "{title}" at {fire_at}.'
        return "Alarm updated successfully."

    if tool == "alarms_set":
        if isinstance(result, dict):
            title = result.get("title")
            fire_at = result.get("fire_at_local") or result.get("fire_at")
            if isinstance(title, str) and isinstance(fire_at, str):
                return f'Alarm set: "{title}" at {fire_at}.'
        return "Alarm set successfully."

    return None
