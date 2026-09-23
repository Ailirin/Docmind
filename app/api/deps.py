"""Общие FastAPI-зависимости для API."""

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Проверяет заголовок X-API-Key.
    Header(default=None) = если заголовка нет, будет None, а не 422.
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    ok = secrets.compare_digest(
        x_api_key.encode("utf-8"),
        settings.api_key.encode("utf-8"),
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
