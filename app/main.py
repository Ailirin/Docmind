"""Точка входа FastAPI: логирование, монтирование API v1 и HTML-админки."""

import base64
import secrets
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import PlainTextResponse
from prometheus_client import make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware

from app.admin.router import router as admin_router
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.logging import clear_request_id, configure_logging, set_request_id

configure_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1) взять из зоголовка или сгенерировать новый
        incoming = request.headers.get("X-Request-ID")
        request_id = incoming.strip() if incoming and incoming.strip() else str(uuid4())

        # 2) положить в ContextVar (логи подхватят)
        token = set_request_id(request_id)
        try:
            response: Response = await call_next(request)
            # 3) отдать клиенту тот же id
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # 4) обязательно сбросить, иначе id "прилипнет" к следующему запросу
            clear_request_id(token)


class MetricsAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/metrics"):
            auth = request.headers.get("Authorization")
            if not auth or not auth.startswith("Basic "):
                return PlainTextResponse(
                    "Unauthorized",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    headers={"WWW-Authenticate": "Basic"},
                )

            try:
                raw = base64.b64decode(auth.removeprefix("Basic ")).decode("utf-8")
                username, _, password = raw.partition(":")
            except Exception:
                return PlainTextResponse(
                    "Unauthorized",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    headers={"WWW-Authenticate": "Basic"},
                )

            user_ok = secrets.compare_digest(
                username.encode("utf-8"),
                settings.metrics_username.encode("utf-8"),
            )
            pass_ok = secrets.compare_digest(
                password.encode("utf-8"),
                settings.metrics_password.encode("utf-8"),
            )
            if not (user_ok and pass_ok):
                return PlainTextResponse(
                    "Unauthorized",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    headers={"WWW-Authenticate": "Basic"},
                )
        return await call_next(request)


app.add_middleware(MetricsAuthMiddleware)
app.add_middleware(RequestIdMiddleware)

app.include_router(v1_router, prefix=settings.api_v1_prefix)
app.include_router(admin_router, prefix="/admin", tags=["admin"])

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
