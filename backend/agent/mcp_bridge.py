from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastmcp import Client as MCPClient
from fastmcp.exceptions import ToolError


logger = logging.getLogger("agent.mcp_bridge")
_normalization_drift_counts: dict[str, int] = {}


def mcp_tool_to_openai_function_tool(t: Any) -> Dict[str, Any]:
    """Convert an MCP tool definition to an OpenAI function/tool schema."""
    if isinstance(t, dict):
        name = t.get("name")
        description = t.get("description", "") or ""
        input_schema = t.get("inputSchema")
    else:
        name = getattr(t, "name", None)
        description = getattr(t, "description", "") or ""
        input_schema = getattr(t, "inputSchema", None)

    if not input_schema:
        input_schema = {"type": "object", "properties": {}}

    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": input_schema,
    }


def find_auth_me_tool_name(mcp_tools: List[Any]) -> Optional[str]:
    """Find the name of the auth_me tool among MCP tools."""
    names: List[str] = []
    for t in mcp_tools:
        if isinstance(t, dict) and t.get("name"):
            names.append(str(t["name"]))
        else:
            n = getattr(t, "name", None)
            if n:
                names.append(str(n))

    for candidate in ("auth_me", "auth.me"):
        if candidate in names:
            return candidate

    for n in names:
        if "auth" in n and "me" in n:
            return n

    return None


async def call_tool_safe(mcp: MCPClient, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Call a tool safely, capturing errors."""
    try:
        result = await mcp.call_tool(name, args)
        data = getattr(result, "data", None)
        if data is None:
            data = getattr(result, "content", None) or result
        return {"ok": True, "result": _normalize_tool_result(data, tool_name=name)}
    except ToolError as e:
        return {"ok": False, "error": str(e)}


def _record_normalization_drift(tool_name: str, reason: str) -> None:
    key = f"{tool_name}:{reason}"
    count = _normalization_drift_counts.get(key, 0) + 1
    _normalization_drift_counts[key] = count
    if count <= 3:
        logger.info("tool=%s | normalization_drift=%s | count=%s", tool_name, reason, count)


def _try_parse_json_text(value: Any, *, tool_name: str, reason: str) -> Any:
    if not isinstance(value, str):
        return value
    candidate = value.strip()
    if not candidate:
        return value

    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()

    if not candidate or candidate[0] not in "[{\"":
        return value

    try:
        decoded = json.loads(candidate)
        _record_normalization_drift(tool_name, reason)
        return decoded
    except Exception:
        pass

    try:
        decoded = ast.literal_eval(candidate)
        if isinstance(decoded, (dict, list, str, int, float, bool, type(None))):
            _record_normalization_drift(tool_name, f"{reason}_literal_eval")
            return decoded
    except Exception:
        pass

    return value


def _normalize_content_item(item: Any, *, tool_name: str) -> Any:
    if isinstance(item, dict) and "text" in item and isinstance(item.get("text"), str):
        return _try_parse_json_text(item["text"], tool_name=tool_name, reason="dict_text_wrapper")

    text = getattr(item, "text", None)
    if isinstance(text, str):
        return _try_parse_json_text(text, tool_name=tool_name, reason="object_text_wrapper")

    return item


def _normalize_tool_result(data: Any, *, tool_name: str) -> Any:
    if isinstance(data, list):
        is_content_wrapper_list = all(
            (isinstance(item, dict) and isinstance(item.get("text"), str))
            or isinstance(getattr(item, "text", None), str)
            for item in data
        )

        if is_content_wrapper_list:
            normalized_items = [_normalize_content_item(item, tool_name=tool_name) for item in data]
            _record_normalization_drift(tool_name, "content_wrapper_list")
            if len(normalized_items) == 1:
                only_item = normalized_items[0]
                if isinstance(only_item, dict) and (tool_name.endswith("_list") or tool_name.endswith(".list")):
                    _record_normalization_drift(tool_name, "singleton_list_preserved")
                    return [only_item]
                return only_item
            return normalized_items

        return [_normalize_tool_result(item, tool_name=tool_name) for item in data]

    if isinstance(data, dict) and "text" in data and isinstance(data.get("text"), str):
        decoded_text = _try_parse_json_text(data["text"], tool_name=tool_name, reason="dict_root_text")
        return _unwrap_result_envelope(decoded_text, tool_name=tool_name)

    if isinstance(data, dict):
        normalized_dict = {key: _normalize_tool_result(value, tool_name=tool_name) for key, value in data.items()}
        return _unwrap_result_envelope(normalized_dict, tool_name=tool_name)

    text = getattr(data, "text", None)
    if isinstance(text, str):
        decoded_text = _try_parse_json_text(text, tool_name=tool_name, reason="object_root_text")
        return _unwrap_result_envelope(decoded_text, tool_name=tool_name)

    decoded = _try_parse_json_text(data, tool_name=tool_name, reason="raw_text")
    return _unwrap_result_envelope(decoded, tool_name=tool_name)


def _unwrap_result_envelope(value: Any, *, tool_name: str) -> Any:
    current = value
    depth = 0
    while isinstance(current, dict) and depth < 3:
        depth += 1

        if "result" in current:
            has_only_result = len(current) == 1
            has_result_with_ok = set(current.keys()) <= {"result", "ok"}
            if has_only_result or has_result_with_ok:
                _record_normalization_drift(tool_name, "result_envelope")
                current = current.get("result")
                continue

        if "data" in current and len(current) == 1:
            _record_normalization_drift(tool_name, "data_envelope")
            current = current.get("data")
            continue

        break

    if isinstance(current, str):
        decoded = _try_parse_json_text(current, tool_name=tool_name, reason="envelope_string")
        if decoded is not current:
            return _unwrap_result_envelope(decoded, tool_name=tool_name)
    return current
