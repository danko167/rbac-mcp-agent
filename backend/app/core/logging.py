from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configures the logging for the application."""
    root = logging.getLogger()

    # Prevent double configuration (uvicorn, reloads, tests, etc.)
    if root.handlers:
        return

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
