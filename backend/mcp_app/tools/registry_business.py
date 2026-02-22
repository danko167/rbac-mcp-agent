from __future__ import annotations

from mcp_app.tools import alarms, approvals, notes, permission_requests, tasks, weather
from mcp_app.tools.registry_common import register_modules


BUSINESS_TOOL_MODULES = (
    notes,
    tasks,
    weather,
    alarms,
    permission_requests,
    approvals,
)


def register_business_tools(mcp) -> None:
    register_modules(mcp, BUSINESS_TOOL_MODULES)
