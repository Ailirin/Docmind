from fastapi import FastAPI

from app.admin.router import router as admin_router
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)


app.include_router(v1_router, prefix=settings.api_v1_prefix)
app.include_router(admin_router, prefix="/admin", tags=["admin"])
