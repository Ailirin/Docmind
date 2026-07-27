from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # проверяет соединение перед выдачей из пула
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency FastAPI:  одна сессия на запрос, потом закрытие."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
