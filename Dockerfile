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

# на случай, если PyMuPDF попросит системные библиотеки
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# копируем только установленные пакеты, без компиляторов
COPY --from=builder /install /usr/local

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# каталог загрузок внутри контейнера
RUN mkdir -p /app/uploads

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

# дефолт - API; worker переопределит command в compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]