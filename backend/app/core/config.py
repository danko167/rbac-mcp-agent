from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    # Core
    database_url: str
    app_timezone: str
    log_level: str
    log_format: str
    log_redact_fields: list[str]

    # Web/API
    cors_allow_origins: list[str]
    login_rate_limit_attempts: int
    login_rate_limit_window_seconds: int
    sse_connect_rate_limit_attempts: int
    sse_connect_rate_limit_window_seconds: int
    sse_allow_query_token: bool

    # DB runtime
    db_pool_size: int
    db_max_overflow: int
    db_pool_timeout_seconds: int
    db_pool_recycle_seconds: int
    db_connect_timeout_seconds: int
    db_statement_timeout_ms: int
    db_lock_timeout_ms: int
    db_idle_tx_timeout_ms: int

    # MCP server
    mcp_host: str
    mcp_port: int

    # Agent
    agent_max_steps: int
    mcp_server_url: str
    llm_model: str
    reviewer_model: str
    transcription_model: str

    # Secrets
    openai_api_key: str | None
    jwt_secret: str
    jwt_exp_hours: int
    app_env: str


def _parse_csv(value: str | None) -> list[str]:
    """Parses a comma-separated string into a list of strings."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def get_settings() -> Settings:
    """Loads settings from environment variables with defaults."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required and must point to a PostgreSQL database")
    app_timezone = os.getenv("APP_TIMEZONE", "UTC")
    app_env = os.getenv("APP_ENV", "dev").lower()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "text").lower()
    log_redact_fields = _parse_csv(
        os.getenv(
            "LOG_REDACT_FIELDS",
            "password,token,secret,authorization,api_key,openai_api_key,jwt_secret",
        )
    )

    cors = _parse_csv(os.getenv("CORS_ALLOW_ORIGINS"))
    if not cors:
        cors = ["http://localhost:5173", "http://127.0.0.1:5173"]

    login_rate_limit_attempts = int(os.getenv("LOGIN_RATE_LIMIT_ATTEMPTS", "10"))
    login_rate_limit_window_seconds = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "60"))
    sse_connect_rate_limit_attempts = int(os.getenv("SSE_CONNECT_RATE_LIMIT_ATTEMPTS", "30"))
    sse_connect_rate_limit_window_seconds = int(os.getenv("SSE_CONNECT_RATE_LIMIT_WINDOW_SECONDS", "60"))
    sse_allow_query_token_default = app_env not in {"prod", "production"}
    sse_allow_query_token = _parse_bool(
        os.getenv("SSE_ALLOW_QUERY_TOKEN"),
        sse_allow_query_token_default,
    )

    db_pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
    db_max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    db_pool_timeout_seconds = int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30"))
    db_pool_recycle_seconds = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))
    db_connect_timeout_seconds = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "10"))
    db_statement_timeout_ms = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "15000"))
    db_lock_timeout_ms = int(os.getenv("DB_LOCK_TIMEOUT_MS", "5000"))
    db_idle_tx_timeout_ms = int(os.getenv("DB_IDLE_TX_TIMEOUT_MS", "30000"))

    mcp_host = os.getenv("MCP_HOST", "0.0.0.0")
    mcp_port = int(os.getenv("MCP_PORT", "8001"))

    agent_max_steps = int(os.getenv("AGENT_MAX_STEPS", "8"))
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp")

    llm_model = os.getenv("LLM_MODEL", "gpt-4.1-mini")
    reviewer_model = os.getenv("REVIEWER_MODEL", "gpt-4.1-mini")
    transcription_model = os.getenv("TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")

    openai_api_key = os.getenv("OPENAI_API_KEY")
    jwt_secret = os.getenv("JWT_SECRET", "dev-secret")
    jwt_exp_hours = int(os.getenv("JWT_EXP_HOURS", "24"))

    if app_env in {"prod", "production"} and jwt_secret == "dev-secret":
        raise RuntimeError("JWT_SECRET must be set to a non-default value in production")

    return Settings(
        database_url=database_url,
        app_timezone=app_timezone,
        log_level=log_level,
        log_format=log_format,
        log_redact_fields=log_redact_fields,
        cors_allow_origins=cors,
        login_rate_limit_attempts=login_rate_limit_attempts,
        login_rate_limit_window_seconds=login_rate_limit_window_seconds,
        sse_connect_rate_limit_attempts=sse_connect_rate_limit_attempts,
        sse_connect_rate_limit_window_seconds=sse_connect_rate_limit_window_seconds,
        sse_allow_query_token=sse_allow_query_token,
        db_pool_size=db_pool_size,
        db_max_overflow=db_max_overflow,
        db_pool_timeout_seconds=db_pool_timeout_seconds,
        db_pool_recycle_seconds=db_pool_recycle_seconds,
        db_connect_timeout_seconds=db_connect_timeout_seconds,
        db_statement_timeout_ms=db_statement_timeout_ms,
        db_lock_timeout_ms=db_lock_timeout_ms,
        db_idle_tx_timeout_ms=db_idle_tx_timeout_ms,
        mcp_host=mcp_host,
        mcp_port=mcp_port,
        agent_max_steps=agent_max_steps,
        mcp_server_url=mcp_server_url,
        llm_model=llm_model,
        reviewer_model=reviewer_model,
        transcription_model=transcription_model,
        openai_api_key=openai_api_key,
        jwt_secret=jwt_secret,
        jwt_exp_hours=jwt_exp_hours,
        app_env=app_env,
    )
