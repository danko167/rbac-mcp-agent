from __future__ import annotations

from mcp_app.tools import auth, users
from mcp_app.tools.registry_common import register_modules


SYSTEM_TOOL_MODULES = (
    auth,
    users,
)


def register_system_tools(mcp) -> None:
    register_modules(mcp, SYSTEM_TOOL_MODULES)
