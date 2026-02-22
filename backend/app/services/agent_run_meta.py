from __future__ import annotations


API_PROMPT_PREFIX = "[api] "


def run_type_from_prompt(prompt: str | None) -> str:
    if (prompt or "").startswith(API_PROMPT_PREFIX):
        return "api_action"
    return "agent"


def action_name_from_prompt(prompt: str | None) -> str | None:
    text = (prompt or "")
    if not text.startswith(API_PROMPT_PREFIX):
        return None
    action_name = text[len(API_PROMPT_PREFIX):].strip()
    return action_name or None
