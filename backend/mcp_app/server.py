from __future__ import annotations

import logging
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

from app.core.config import get_settings
from app.core.logging import configure_logging
from mcp_app.tools.registry import register_all_tools

load_dotenv()

settings = get_settings()
configure_logging(settings.log_level)

logger = logging.getLogger("mcp_app.server")

mcp = FastMCP("RBAC MCP Server", json_response=True)

# Register tool modules
register_all_tools(mcp)

# Run the MCP server
if __name__ == "__main__":
    import uvicorn

    # Create the FastAPI app instance
    app = mcp.streamable_http_app()
    logger.info("Starting MCP server on %s:%s", settings.mcp_host, settings.mcp_port)
    uvicorn.run(app, host=settings.mcp_host, port=settings.mcp_port)
