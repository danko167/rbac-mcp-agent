from __future__ import annotations

import json
from typing import Any, Dict, List


def extract_output_text(resp: Any) -> str:
    """Extract output text from a response object."""
    out_text = getattr(resp, "output_text", None)
    if isinstance(out_text, str) and out_text.strip():
        return out_text.strip()

    parts: List[str] = []
    output = getattr(resp, "output", None) or []
    for item in output:
        if isinstance(item, dict):
            itype = item.get("type")
            text = item.get("text")
        else:
            itype = getattr(item, "type", None)
            text = getattr(item, "text", None)

        if itype in ("output_text", "text") and text:
            parts.append(str(text))

    return "\n".join(parts).strip()


def extract_function_calls(resp: Any) -> List[Dict[str, Any]]:
    """Extract function/tool calls from a response object."""
    calls: List[Dict[str, Any]] = []
    output = getattr(resp, "output", None) or []

    for item in output:
        if isinstance(item, dict):
            itype = item.get("type")
            name = item.get("name")
            arguments = item.get("arguments", "{}")
            call_id = item.get("id")
        else:
            itype = getattr(item, "type", None)
            name = getattr(item, "name", None)
            arguments = getattr(item, "arguments", "{}")
            call_id = getattr(item, "id", None)

        if itype not in ("function_call", "tool_call"):
            continue

        calls.append({"id": call_id, "name": name, "arguments": arguments or "{}"})

    return calls


def decode_call_arguments(raw_args: Any) -> Dict[str, Any]:
    """Decode function/tool call arguments from raw input."""
    if isinstance(raw_args, str):
        try:
            return json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            return {}
    if isinstance(raw_args, dict):
        return raw_args
    return {}
