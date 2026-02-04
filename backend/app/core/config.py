from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # Core
    database_url: str
    app_timezone: str
    log_level: str

    # Web/API
    cors_allow_origins: list[str]

    # MCP server
    mcp_host: str
    mcp_port: int

    # Agent
    agent_max_steps: int
    mcp_server_url: str
    llm_model: str
    reviewer_model: str

    # Secrets
    openai_api_key: str | None


def _default_sqlite_url() -> str:
    """Constructs the default SQLite database URL pointing to app.db in the backend directory."""
    backend_dir = Path(__file__).resolve().parent.parent
    db_path = backend_dir / "app.db"
    return f"sqlite:///{db_path.as_posix()}"


def _parse_csv(value: str | None) -> list[str]:
    """Parses a comma-separated string into a list of strings."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def get_settings() -> Settings:
    """Loads settings from environment variables with defaults."""
    database_url = os.getenv("DATABASE_URL") or _default_sqlite_url()
    app_timezone = os.getenv("APP_TIMEZONE", "UTC")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    cors = _parse_csv(os.getenv("CORS_ALLOW_ORIGINS"))
    if not cors:
        cors = ["http://localhost:5173", "http://127.0.0.1:5173"]

    mcp_host = os.getenv("MCP_HOST", "0.0.0.0")
    mcp_port = int(os.getenv("MCP_PORT", "8001"))

    agent_max_steps = int(os.getenv("AGENT_MAX_STEPS", "8"))
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp")

    llm_model = os.getenv("LLM_MODEL", "gpt-4.1-mini")
    reviewer_model = os.getenv("REVIEWER_MODEL", "gpt-4.1-mini")

    openai_api_key = os.getenv("OPENAI_API_KEY")

    return Settings(
        database_url=database_url,
        app_timezone=app_timezone,
        log_level=log_level,
        cors_allow_origins=cors,
        mcp_host=mcp_host,
        mcp_port=mcp_port,
        agent_max_steps=agent_max_steps,
        mcp_server_url=mcp_server_url,
        llm_model=llm_model,
        reviewer_model=reviewer_model,
        openai_api_key=openai_api_key,
    )
