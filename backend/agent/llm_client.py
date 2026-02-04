from __future__ import annotations

from openai import OpenAI
from app.core.config import get_settings


def get_openai_client() -> OpenAI:
    """Get an OpenAI client instance."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=settings.openai_api_key)
