"""Общие FastAPI-зависимости для API."""

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.core.security import constant_time_equals


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

    if not constant_time_equals(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
