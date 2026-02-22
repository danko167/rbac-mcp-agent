from __future__ import annotations

import json
from typing import Any, Callable, Dict, List

from openai import OpenAI
from agent.responses_parse import extract_output_text


def as_assistant_tool_result_message(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Format a tool result as an assistant message."""
    return {
        "role": "assistant",
        "content": (
            "TOOL_RESULT\n"
            f"tool: {tool_name}\n"
            f"payload: {json.dumps(payload, default=str)}"
        ),
    }


def extract_tool_results_from_messages(msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract tool results from assistant messages."""
    out: List[Dict[str, Any]] = []
    for m in msgs:
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        content = m.get("content")
        if not isinstance(content, str) or not content.startswith("TOOL_RESULT"):
            continue

        tool_name = None
        payload_json = None
        for line in content.splitlines():
            if line.startswith("tool:"):
                tool_name = line.split("tool:", 1)[1].strip()
            elif line.startswith("payload:"):
                payload_json = line.split("payload:", 1)[1].strip()

        if not tool_name or not payload_json:
            continue

        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {"ok": False, "error": "Could not parse tool payload JSON"}

        out.append({"tool": tool_name, **payload})
    return out


def compact_evidence(tool_results: List[Dict[str, Any]], max_chars: int = 6000) -> str:
    """Compact tool results into a concise evidence string."""
    lines: List[str] = []
    for tr in tool_results:
        tool = tr.get("tool")
        ok = tr.get("ok")
        if ok is True:
            s = json.dumps(tr.get("result"), default=str, ensure_ascii=False)
            if len(s) > 1500:
                s = s[:1500] + "…(truncated)"
            lines.append(f"- {tool}: ok=true result={s}")
        else:
            lines.append(f"- {tool}: ok=false error={tr.get('error') or 'Tool failed'}")

    evidence = "\n".join(lines)
    return evidence if len(evidence) <= max_chars else evidence[:max_chars] + "\n…(evidence truncated)"


def should_run_reviewer(tool_results: List[Dict[str, Any]]) -> bool:
    """Decide if a reviewer should be run based on tool results."""
    if not tool_results:
        return False
    if any(tr.get("ok") is False for tr in tool_results):
        return True
    if any(tr.get("ok") is True for tr in tool_results):
        return True
    return False


def review_and_rewrite_final_answer(
    oai: OpenAI,
    *,
    model: str,
    final_text: str,
    evidence: str,
    on_response: Callable[[Any], None] | None = None,
) -> str:
    """Use a reviewer model to rewrite the final answer based on evidence."""
    reviewer_system = (
        "You are a strict reviewer for an assistant that used tools.\n"
        "Rewrite the assistant's final answer to be accurate and grounded ONLY in the evidence.\n"
        "Rules:\n"
        "- Do NOT add new facts not present in the evidence.\n"
        "- Do NOT claim an action succeeded unless evidence shows ok=true for the relevant tool.\n"
        "- Do NOT claim an action failed unless evidence shows ok=false for the relevant action tool.\n"
        "- If evidence shows ok=true for a mutation tool (e.g. *.create, *.update, *.delete, *.cancel, *.complete, *.decide, *.revoke, *.set), you MUST clearly state that the action was completed.\n"
        "- When a mutation tool succeeded, do NOT ask the user whether they want to perform that same action.\n"
        "- If only list/read tools ran, summarize current state from those results without inventing attempted mutations.\n"
        "- If evidence shows ok=false, explain politely.\n"
        "- Keep it concise.\n"
    )

    reviewer_user = (
        "EVIDENCE (authoritative):\n"
        f"{evidence}\n\n"
        "DRAFT ANSWER TO FIX:\n"
        f"{final_text}\n\n"
        "Return ONLY the rewritten final answer."
    )

    resp = oai.responses.create(
        model=model,
        input=[
            {"role": "system", "content": reviewer_system},
            {"role": "user", "content": reviewer_user},
        ],
    )
    if on_response:
        on_response(resp)
    rewritten = extract_output_text(resp).strip()
    return rewritten or final_text
