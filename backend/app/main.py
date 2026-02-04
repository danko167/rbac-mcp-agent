from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
import logging

import anyio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.db import engine, SessionLocal
from app.db.models import Base, User
from app.db.seed import seed
from .api.routes import router as api_router

settings = get_settings()
configure_logging(settings.log_level)

logger = logging.getLogger("app.main")


def startup_sync() -> None:
    """Sync part of the startup process."""
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.scalar(select(User)):
            seed(db)


def shutdown_sync() -> None:
    """Sync part of the shutdown process."""
    try:
        engine.dispose()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    await anyio.to_thread.run_sync(startup_sync)
    yield
    await anyio.to_thread.run_sync(shutdown_sync)


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    app = FastAPI(title="RBAC MCP Agent API", lifespan=lifespan)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError):
        logger.info("403 %s %s (%s)", request.method, request.url.path, str(exc) or "PermissionError")
        return JSONResponse(status_code=403, content={"detail": "Not authorized"})

    @app.exception_handler(JWTError)
    async def jwt_error_handler(request: Request, exc: JWTError):
        logger.info("401 %s %s (%s)", request.method, request.url.path, str(exc) or "JWTError")
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.info("%s %s %s (%s)", exc.status_code, request.method, request.url.path, str(exc.detail))
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    # Include API routes
    app.include_router(api_router)
    return app

# Create the FastAPI app instance
app = create_app()
