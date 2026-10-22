# ===== stage 1: зависимости =====
FROM python:3.12-slim AS builder

WORKDIR /build

# системные зависимости для PyMuPDF / psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ===== stage 2: runtime =====
FROM python:3.12-slim AS runtime

WORKDIR /app

# системные зависимости runtime + su-exec для безопасного drop-привилегий
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# копируем только установленные пакеты, без компиляторов
COPY --from=builder /install /usr/local

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# non-root пользователь: контейнер запускает процесс от appuser (не root)
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --no-create-home appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appgroup /app

# Entrypoint: запускается как root, исправляет права на примонтированный
# volume /app/uploads, затем делает exec su-exec appuser <cmd>.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
# дефолт - API; worker переопределит command в compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]