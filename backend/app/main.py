from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time
import uuid

import anyio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.runtime_state import mark_shutdown_completed, mark_shutdown_started, mark_startup
from app.core.time import detect_server_timezone_name
from app.core.logging import configure_logging, reset_request_id, set_request_id
from app.db.db import engine, SessionLocal
from app.db.models import Base, User
from app.db.seed import seed
from app.security.authz import AuthorizationError
from app.services.alarms import process_due_alarms_once
from app.core.events import forward_postgres_events_forever, mark_server_running, mark_server_shutting_down
from .api.routes import router as api_router

settings = get_settings()
configure_logging(
    settings.log_level,
    log_format=settings.log_format,
    redact_fields=settings.log_redact_fields,
)

logger = logging.getLogger("app.main")


def backfill_user_timezones(db: Session) -> int:
    """
    One-time startup sweep:
    - if user.timezone is missing/invalid, set server timezone.
    Returns number of rows changed.
    """
    server_tz = detect_server_timezone_name()
    users = db.scalars(select(User)).all()

    changed = 0
    for user in users:
        tz_name = (user.timezone or "").strip()
        if not tz_name:
            user.timezone = server_tz
            changed += 1
            continue

        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(tz_name)
        except Exception:
            user.timezone = server_tz
            changed += 1

    return changed


def startup_sync() -> None:
    """Sync part of the startup process."""
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.scalar(select(User)):
            seed(db)

    with SessionLocal.begin() as db:
        changed = backfill_user_timezones(db)
        if changed:
            logger.info("Timezone startup sweep updated %s user(s)", changed)


def shutdown_sync() -> None:
    """Sync part of the shutdown process."""
    try:
        engine.dispose()
    except Exception:
        pass


def process_due_alarms_sync() -> None:
    with SessionLocal.begin() as db:
        process_due_alarms_once(db)


async def alarm_loop() -> None:
    while True:
        await anyio.to_thread.run_sync(process_due_alarms_sync)
        await anyio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    mark_startup()
    mark_server_running()
    await anyio.to_thread.run_sync(startup_sync)
    async with anyio.create_task_group() as tg:
        tg.start_soon(alarm_loop)
        tg.start_soon(anyio.to_thread.run_sync, forward_postgres_events_forever)
        yield
        shutdown_started_at = time.perf_counter()
        mark_shutdown_started()
        mark_server_shutting_down()
        tg.cancel_scope.cancel()
    await anyio.to_thread.run_sync(shutdown_sync)
    shutdown_duration_ms = (time.perf_counter() - shutdown_started_at) * 1000
    mark_shutdown_completed(shutdown_duration_ms)


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    app = FastAPI(title="RBAC MCP Agent API", lifespan=lifespan)

    external_dir = Path(__file__).resolve().parents[2] / "external"
    if external_dir.exists():
        app.mount("/external", StaticFiles(directory=str(external_dir)), name="external")

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = set_request_id(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "Request completed %s %s -> %s in %.2fms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "Request failed %s %s in %.2fms",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        finally:
            reset_request_id(token)

    # Exception handlers
    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError):
        logger.info("403 %s %s (%s)", request.method, request.url.path, str(exc) or "PermissionError")
        if isinstance(exc, AuthorizationError):
            return JSONResponse(status_code=403, content={"detail": exc.as_dict()})
        return JSONResponse(status_code=403, content={"detail": "Not authorized"})

    @app.exception_handler(JWTError)
    async def jwt_error_handler(request: Request, exc: JWTError):
        logger.info("401 %s %s (%s)", request.method, request.url.path, str(exc) or "JWTError")
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.info("%s %s %s (%s)", exc.status_code, request.method, request.url.path, str(exc.detail))
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("500 %s %s (%s)", request.method, request.url.path, str(exc))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # Include API routes
    app.include_router(api_router)
    return app

# Create the FastAPI app instance
app = create_app()
