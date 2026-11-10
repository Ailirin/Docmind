"""Настройки приложения из переменных окружения и файла .env."""

import warnings

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Значения-заглушки, которые нельзя оставлять в продакшне (по полю — набор слабых значений).
# admin_password: "change-me" задаётся в docker-compose/.env.example, поэтому тоже считается слабым.
_INSECURE_DEFAULTS: dict[str, frozenset[str]] = {
    "api_key": frozenset({"change-me"}),
    "admin_password": frozenset({"admin", "change-me"}),
    "metrics_password": frozenset({"change-me"}),
}

# Секреты, которые не могут быть пустыми ни при каких условиях (даже в debug).
_REQUIRED_SECRETS = ("api_key", "admin_password", "metrics_password")


class Settings(BaseSettings):
    # extra="ignore": .env общий с docker compose и содержит переменные, которых нет в
    # Settings (POSTGRES_PASSWORD, GRAFANA_ADMIN_PASSWORD и т.п.); иначе приложение не стартует.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Приложение ---
    app_name: str = "DocMind"
    app_version: str = "0.1.0"
    debug: bool = False

    # --- API ---
    api_v1_prefix: str = "/api/v1"
    api_key: str = "change-me"
    upload_dir: str = "uploads"
    max_upload_bytes: int = 20 * 1024 * 1024  # 20 МБ

    # --- База данных ---
    database_url: str = "postgresql+asyncpg://docmind:docmind@localhost:5432/docmind"
    db_pool_size: int = 10  # кол-во постоянных соединений в пуле
    db_max_overflow: int = 20  # доп. соединения сверх pool_size
    db_pool_timeout: int = 30  # секунд ожидания свободного соединения
    db_pool_recycle: int = 1800  # секунд до принудительного пересоздания

    # --- Экстрактор ---
    extractor_provider: str = "mock"
    llm_api_key: str | None = None
    llm_model: str = "llama3.2:1b"
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_timeout: int = 60  # секунд таймаут запроса к LLM

    # --- RabbitMQ ---
    rabbitmq_url: str = "amqp://docmind:docmind@localhost:5672/"
    rabbitmq_queue: str = "documents.process"
    rabbitmq_dlq: str = "documents.process.dlq"

    # --- Админка ---
    admin_username: str = "admin"
    admin_password: str = "admin"

    # --- Метрики ---
    metrics_username: str = "metrics"
    metrics_password: str = "change-me"

    # --- Логирование ---
    log_level: str = "INFO"
    log_format: str = "text"  # "text" | "json"

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        """
        Fail closed для пустых секретов, предупреждение для слабых.

        Пустой секрет — это ошибка конфигурации (например, в docker-compose
        `API_KEY: ${API_KEY}` при незаданной переменной даёт пустую строку),
        поэтому приложение отказывается стартовать, а не работает без защиты.
        """
        for field in _REQUIRED_SECRETS:
            if not (getattr(self, field, "") or "").strip():
                raise ValueError(
                    f"[DocMind] SECURITY: '{field}' не может быть пустым. "
                    f"Задайте переменную окружения {field.upper()}."
                )

        if self.debug:
            return self
        for field, insecure_values in _INSECURE_DEFAULTS.items():
            actual = getattr(self, field, None)
            if actual in insecure_values:
                warnings.warn(
                    f"[DocMind] SECURITY: '{field}' использует небезопасное значение по умолчанию. "
                    f"Установите переменную окружения перед деплоем.",
                    stacklevel=2,
                )
        return self


settings = Settings()
