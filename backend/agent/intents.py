from __future__ import annotations

from typing import Any, Dict, List


def is_capabilities_question(convo: List[Dict[str, Any]]) -> bool:
    if not convo:
        return False
    last = convo[-1]
    if not isinstance(last, dict) or last.get("role") != "user":
        return False
    content = (last.get("content") or "").strip().lower()
    return content in {
        "what can i do?",
        "what can i do",
        "help",
        "commands",
        "capabilities",
        "what are my permissions?",
        "what are my permissions",
    }


def is_alarm_cancel_intent(convo: List[Dict[str, Any]]) -> bool:
    if not convo:
        return False
    last = convo[-1]
    if not isinstance(last, dict) or last.get("role") != "user":
        return False
    text = str(last.get("content") or "").strip().lower()
    cancel_words = ("cancel", "stop", "delete", "remove")
    if not any(word in text for word in cancel_words):
        return False
    if "alarm" in text:
        return True
    return any(token in text for token in ("it", "one", "first", "second", "third", "1st", "2nd", "3rd"))


def is_alarm_show_intent(convo: List[Dict[str, Any]]) -> bool:
    if not convo:
        return False
    last = convo[-1]
    if not isinstance(last, dict) or last.get("role") != "user":
        return False
    text = str(last.get("content") or "").strip().lower()
    if "alarm" not in text:
        return False
    return any(token in text for token in ("show", "list", "what", "which", "have", "active", "upcoming"))


def is_alarm_set_intent(convo: List[Dict[str, Any]]) -> bool:
    if not convo:
        return False
    last = convo[-1]
    if not isinstance(last, dict) or last.get("role") != "user":
        return False
    text = str(last.get("content") or "").strip().lower()
    if "alarm" not in text:
        return False
    return any(token in text for token in ("set", "create", "add", "schedule", "remind"))
