FROM python:3.12-slim

WORKDIR /app

# системные зависимости для PyMuPDF / psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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