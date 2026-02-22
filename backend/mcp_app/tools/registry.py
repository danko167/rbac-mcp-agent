from __future__ import annotations

from mcp_app.tools.registry_business import register_business_tools
from mcp_app.tools.registry_system import register_system_tools


def register_all_tools(mcp) -> None:
    register_system_tools(mcp)
    register_business_tools(mcp)
