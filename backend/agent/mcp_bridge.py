from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastmcp import Client as MCPClient
from fastmcp.exceptions import ToolError


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
        return {"ok": True, "result": data}
    except ToolError as e:
        return {"ok": False, "error": str(e)}
