from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import TokenUsageEvent


def _to_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except Exception:
        return 0


def empty_usage_summary() -> dict[str, int]:
    return {
        "llm_input_tokens": 0,
        "llm_output_tokens": 0,
        "llm_total_tokens": 0,
        "stt_input_tokens": 0,
        "stt_output_tokens": 0,
        "stt_total_tokens": 0,
        "all_input_tokens": 0,
        "all_output_tokens": 0,
        "all_total_tokens": 0,
    }


def extract_openai_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")

    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    if not isinstance(usage, dict):
        usage = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    input_tokens = _to_int(
        usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or usage.get("prompt_token_count")
    )
    output_tokens = _to_int(
        usage.get("output_tokens")
        or usage.get("completion_tokens")
        or usage.get("completion_token_count")
    )
    total_tokens = _to_int(usage.get("total_tokens"))

    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def record_usage_event(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    conversation_id: int | None = None,
    agent_run_id: int | None = None,
    provider: str = "openai",
) -> None:
    if input_tokens <= 0 and output_tokens <= 0 and total_tokens <= 0:
        return

    event = TokenUsageEvent(
        user_id=user_id,
        conversation_id=conversation_id,
        agent_run_id=agent_run_id,
        event_type=event_type,
        provider=provider,
        model=model,
        input_tokens=max(0, input_tokens),
        output_tokens=max(0, output_tokens),
        total_tokens=max(0, total_tokens),
    )
    db.add(event)


def summarize_usage_events(events: list[TokenUsageEvent]) -> dict[str, int]:
    totals = empty_usage_summary()

    for event in events:
        prefix = "llm" if event.event_type == "llm" else "stt"
        totals[f"{prefix}_input_tokens"] += _to_int(event.input_tokens)
        totals[f"{prefix}_output_tokens"] += _to_int(event.output_tokens)
        totals[f"{prefix}_total_tokens"] += _to_int(event.total_tokens)

    totals["all_input_tokens"] = totals["llm_input_tokens"] + totals["stt_input_tokens"]
    totals["all_output_tokens"] = totals["llm_output_tokens"] + totals["stt_output_tokens"]
    totals["all_total_tokens"] = totals["llm_total_tokens"] + totals["stt_total_tokens"]
    return totals


def get_user_usage_summary(db: Session, *, user_id: int) -> dict[str, int]:
    rows = db.execute(
        select(
            TokenUsageEvent.event_type,
            func.coalesce(func.sum(TokenUsageEvent.input_tokens), 0),
            func.coalesce(func.sum(TokenUsageEvent.output_tokens), 0),
            func.coalesce(func.sum(TokenUsageEvent.total_tokens), 0),
        ).where(TokenUsageEvent.user_id == user_id)
        .group_by(TokenUsageEvent.event_type)
    ).all()

    totals = empty_usage_summary()
    for event_type, input_sum, output_sum, total_sum in rows:
        prefix = "llm" if event_type == "llm" else "stt"
        totals[f"{prefix}_input_tokens"] += _to_int(input_sum)
        totals[f"{prefix}_output_tokens"] += _to_int(output_sum)
        totals[f"{prefix}_total_tokens"] += _to_int(total_sum)

    totals["all_input_tokens"] = totals["llm_input_tokens"] + totals["stt_input_tokens"]
    totals["all_output_tokens"] = totals["llm_output_tokens"] + totals["stt_output_tokens"]
    totals["all_total_tokens"] = totals["llm_total_tokens"] + totals["stt_total_tokens"]
    return totals


def get_conversation_usage_summaries(
    db: Session,
    *,
    user_id: int,
    conversation_ids: list[int],
) -> dict[int, dict[str, int]]:
    if not conversation_ids:
        return {}

    rows = db.execute(
        select(
            TokenUsageEvent.conversation_id,
            TokenUsageEvent.event_type,
            func.coalesce(func.sum(TokenUsageEvent.input_tokens), 0),
            func.coalesce(func.sum(TokenUsageEvent.output_tokens), 0),
            func.coalesce(func.sum(TokenUsageEvent.total_tokens), 0),
        ).where(
            TokenUsageEvent.user_id == user_id,
            TokenUsageEvent.conversation_id.in_(conversation_ids),
        )
        .group_by(TokenUsageEvent.conversation_id, TokenUsageEvent.event_type)
    ).all()

    summaries: dict[int, dict[str, int]] = {}
    for conversation_id, event_type, input_sum, output_sum, total_sum in rows:
        if conversation_id is None:
            continue

        summary = summaries.setdefault(int(conversation_id), empty_usage_summary())
        prefix = "llm" if event_type == "llm" else "stt"
        summary[f"{prefix}_input_tokens"] += _to_int(input_sum)
        summary[f"{prefix}_output_tokens"] += _to_int(output_sum)
        summary[f"{prefix}_total_tokens"] += _to_int(total_sum)

    for summary in summaries.values():
        summary["all_input_tokens"] = summary["llm_input_tokens"] + summary["stt_input_tokens"]
        summary["all_output_tokens"] = summary["llm_output_tokens"] + summary["stt_output_tokens"]
        summary["all_total_tokens"] = summary["llm_total_tokens"] + summary["stt_total_tokens"]

    return summaries
