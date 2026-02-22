from __future__ import annotations

from fastapi import HTTPException


CONVERSATION_KIND_DEFAULT = "default"
CONVERSATION_KIND_APPROVALS = "approvals"


def normalize_conversation_kind(kind_raw: str | None) -> str:
    kind = (kind_raw or CONVERSATION_KIND_DEFAULT).strip().lower()
    if kind not in {CONVERSATION_KIND_DEFAULT, CONVERSATION_KIND_APPROVALS}:
        raise HTTPException(status_code=400, detail="Unsupported conversation kind")
    return kind


def default_title_for_conversation_kind(kind: str) -> str:
    if kind == CONVERSATION_KIND_APPROVALS:
        return "Approvals assistant"
    return "New conversation"


def conversation_title_from_prompt(prompt: str) -> str:
    title = " ".join((prompt or "").split()).strip()
    if not title:
        return default_title_for_conversation_kind(CONVERSATION_KIND_DEFAULT)
    return title[:80]
