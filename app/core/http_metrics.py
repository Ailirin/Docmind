"""ASGI-middleware, собирающий HTTP-метрики (RPS, ошибки, латентность по роутам)."""

import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS

# Служебные пути не учитываем: скрейп Prometheus каждые 15 с заглушил бы реальный трафик.
_IGNORED_PREFIXES = ("/metrics",)
_UNMATCHED = "unmatched"


class HttpMetricsMiddleware:
    """
    Чистый ASGI-middleware (не BaseHTTPMiddleware): не буферизует тело ответа
    и после обработки видит scope["route"], куда роутер кладёт найденный маршрут.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"].startswith(_IGNORED_PREFIXES):
            await self.app(scope, receive, send)
            return

        status_code = 500  # если приложение упало до отправки ответа — это 500
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            # 404 и прочие несовпавшие пути группируем в одну серию.
            route_path = getattr(route, "path", None) or _UNMATCHED
            method = scope["method"]
            HTTP_REQUESTS.labels(method=method, route=route_path, status=str(status_code)).inc()
            HTTP_REQUEST_DURATION.labels(method=method, route=route_path).observe(
                time.perf_counter() - started
            )
