"""Точка входа FastAPI: логирование, монтирование API v1 и HTML-админки."""

from uuid import uuid4

from fastapi import FastAPI, Request, Response
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


app.add_middleware(RequestIdMiddleware)

app.include_router(v1_router, prefix=settings.api_v1_prefix)
app.include_router(admin_router, prefix="/admin", tags=["admin"])

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
