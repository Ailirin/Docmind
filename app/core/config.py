"""Настройки приложения из переменных окружения и файла .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "DocMind"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    upload_dir: str = "uploads"
    database_url: str = "postgresql+psycopg2://docmind:docmind@localhost:5432/docmind"
    extractor_provider: str = "mock"
    llm_api_key: str | None = None
    llm_model: str = "llama3.2:1b"
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    rabbitmq_url: str = "amqp://docmind:docmind@localhost:5672/"
    rabbitmq_queue: str = "documents.process"
    rabbitmq_dlq: str = "documents.process.dlq"


settings = Settings()
