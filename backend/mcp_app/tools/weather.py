from __future__ import annotations

from app.db.db import SessionLocal
from app.security.authz import require
from mcp_app.security.deps import identity_from_bearer_with_db
from mcp_app.services.audit import log_tool_call
from mcp_app.services.weather_service import read_weather


def register(mcp):
    @mcp.tool()
    def weather_read(
        auth: str,
        location: str,
        when: str | None = None,
        granularity: str = "auto",
        agent_run_id: int | None = None,
    ):
        """
        Get weather information for a specified location and time.
        """
        with SessionLocal.begin() as db:
            identity = identity_from_bearer_with_db(db, auth)
            require(identity, "weather:read")

            log_tool_call(
                db,
                user_id=identity.user_id,
                tool="weather.read",
                args={"location": location, "when": when, "granularity": granularity},
                agent_run_id=agent_run_id,
            )

        # read_weather is external IO; keep it outside the DB transaction
        return read_weather(location=location, when=when, granularity=granularity)
