from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_WEEKDAY_PHRASE_RE = re.compile(
    r"\b(?P<which>next|this)\s+(?P<wd>monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)
_NEXT_WEEK_RE = re.compile(r"\bnext\s+week\b", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def last_user_text(convo: List[Dict[str, Any]]) -> str:
    """Get the last user message text from the conversation."""
    for m in reversed(convo):
        if isinstance(m, dict) and m.get("role") == "user" and m.get("content"):
            return str(m["content"])
    return ""


def extract_relative_due_phrase(user_text: str) -> Optional[str]:
    """Extract relative due date phrase from user text."""
    if not user_text:
        return None

    if _NEXT_WEEK_RE.search(user_text):
        return "next week"

    m = _WEEKDAY_PHRASE_RE.search(user_text)
    if m:
        which = m.group("which").lower()
        wd = m.group("wd").lower()
        return f"{which} {wd}"

    return None


def apply_tasks_due_on_override(tool_name: str, args: Dict[str, Any], convo: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply due date override based on relative phrases in user text."""
    if tool_name not in {"tasks_create", "tasks_update", "tasks.create", "tasks.update"}:
        return args

    phrase = extract_relative_due_phrase(last_user_text(convo))
    if not phrase:
        return args

    due_on = args.get("due_on")

    if not due_on and phrase == "next week":
        args["due_on"] = phrase
        return args

    if isinstance(due_on, str) and _ISO_DATE_RE.match(due_on.strip()):
        args["due_on"] = phrase
        return args

    return args
