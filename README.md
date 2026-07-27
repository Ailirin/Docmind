# DocMind

Сервис асинхронной обработки медицинских документов в формате PDF.

DocMind принимает выписки, рецепты и диагнозы, извлекает текст, определяет тип документа, достаёт структурированные сущности (пациент, диагноз МКБ, лечение) и сохраняет результат в PostgreSQL. Тяжёлая обработка выполняется в отдельном worker через RabbitMQ — API сразу отвечает `202 Accepted`.

Проект учебный / портфолио: архитектура близка к продакшен-паттернам (версионированный REST API, миграции, очередь, LLM с валидацией, тесты, CI).

---

## Возможности

- Загрузка PDF через REST API (`multipart/form-data`)
- Сохранение файла на диск под именем `{uuid}.pdf` (без path traversal и коллизий имён)
- Метаданные и статусы в PostgreSQL (SQLAlchemy + Alembic)
- Асинхронная обработка через RabbitMQ + отдельный worker-процесс
- Извлечение текста: **PyMuPDF**
- Классификация типа документа: rule-based (ключевые слова)
- Извлечение сущностей:
  - **mock** — детерминированный regex-экстрактор (для разработки и тестов)
  - **llm** — OpenAI-compatible API (Ollama в Docker или облако Mistral)
- Валидация ответа LLM через Pydantic-схемы
- HTML-админка: список документов и страница деталей (полный текст + JSON результата)
- Структурированное логирование в stdout (API, worker, processor, очередь)
- Unit- и API-тесты (pytest), lint (Ruff) и CI на GitHub Actions

---

## Архитектура

```text
Клиент
  │
  ▼
FastAPI  POST /api/v1/documents
  │  1) сохранить PDF → uploads/
  │  2) запись в PostgreSQL (status=queued)
  │  3) publish {document_id} → RabbitMQ
  │
  └────────────► 202 Accepted + id
                      │
                      ▼
                 RabbitMQ queue
                 documents.process
                      │
                      ▼
                   Worker
                      │
                      ├─ PyMuPDF → текст
                      ├─ classify → discharge | prescription | diagnosis | unknown
                      ├─ extractor (mock | llm) → сущности
                      └─ UPDATE documents (done | failed)
```

**Жизненный цикл статуса:**  
`uploaded` → `queued` → `processing` → `done` | `failed`

На практике после upload статус сразу `queued` (файл на диске, задача в очереди).

---

## Стек

| Слой | Технологии |
|------|------------|
| API | FastAPI, Uvicorn, Pydantic, Pydantic Settings |
| БД | PostgreSQL 16, SQLAlchemy 2.0, Alembic |
| Очередь | RabbitMQ 3 (management UI), pika |
| PDF | PyMuPDF (`fitz`) |
| LLM | OpenAI Python SDK → Ollama / Mistral (OpenAI-compatible) |
| Админка | Jinja2 |
| Тесты | pytest, httpx / TestClient |
| Линтинг | Ruff (`check` + `format`) |
| CI | GitHub Actions (lint + test) |
| Инфра | Docker Compose, multi-stage Dockerfile |
| Observability | stdout-логи (уровень через `LOG_LEVEL`) |

---

## Структура проекта

```text
DocMind/
├── app/
│   ├── main.py                 # точка входа FastAPI + configure_logging()
│   ├── worker.py               # consumer RabbitMQ + логи
│   ├── admin/                  # HTML-админка
│   ├── api/v1/                 # REST API v1
│   ├── core/
│   │   ├── config.py           # настройки из .env
│   │   └── logging.py          # единая настройка логов (stdout)
│   ├── db/                     # engine, session, Base
│   ├── models/                 # SQLAlchemy-модели
│   ├── schemas/                # Pydantic-схемы API и extraction
│   ├── services/
│   │   ├── file_storage.py     # сохранение PDF
│   │   ├── pdf_extractor.py    # текст из PDF
│   │   ├── classifier.py       # тип документа
│   │   ├── processor.py        # пайплайн обработки + логи статусов
│   │   └── extractors/         # mock + llm + factory
│   ├── storage/                # репозиторий документов
│   ├── queue/                  # публикация в RabbitMQ + логи
│   └── templates/admin/        # Jinja2-шаблоны
├── alembic/                    # миграции БД
├── samples/                    # тестовые PDF
├── tests/                      # pytest
├── .github/workflows/ci.yml    # CI: Ruff + pytest
├── docker-compose.yml          # Postgres, RabbitMQ, Ollama, api, worker
├── Dockerfile                  # multi-stage: builder + runtime
├── .dockerignore               # что не копировать в build-context
├── ruff.toml                   # правила Ruff
├── requirements.txt
├── requirements-dev.txt        # ruff и прочие dev-зависимости
├── pytest.ini
└── .env                        # локальные секреты (не в git)
```

---

## Требования

- Python 3.12+ (локально допускается 3.14; CI использует 3.12)
- Docker Desktop / Docker Compose
- Git (опционально)

---

## Быстрый старт

### 1. Клонирование и виртуальное окружение

```powershell
cd D:\Project\DocMind
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Переменные окружения

Создайте файл `.env` в корне:

```env
APP_NAME=DocMind
APP_VERSION=0.1.0
API_V1_PREFIX=/api/v1
UPLOAD_DIR=uploads

DATABASE_URL=postgresql+psycopg2://docmind:docmind@localhost:5432/docmind

# mock — без LLM; llm — Ollama/Mistral
EXTRACTOR_PROVIDER=mock

LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=llama3.2:1b
LLM_API_KEY=ollama

RABBITMQ_URL=amqp://docmind:docmind@localhost:5672/
RABBITMQ_QUEUE=documents.process

# уровень логов: DEBUG | INFO | WARNING | ERROR
LOG_LEVEL=INFO
```

Для облака Mistral (вместо Ollama):

```env
EXTRACTOR_PROVIDER=llm
LLM_BASE_URL=https://api.mistral.ai/v1
LLM_MODEL=mistral-small-latest
LLM_API_KEY=ваш_ключ
```

Секреты не коммитьте: `.env` уже в `.gitignore`.

### 3. Запуск через Docker Compose (рекомендуется для демо)

Один образ собирается из `Dockerfile` и используется и для `api`, и для `worker` (разный `command`).

```powershell
docker compose up -d --build
docker compose ps
```

Поднимаются:

| Сервис | Порт | Назначение |
|--------|------|------------|
| `docmind-db` | 5432 | PostgreSQL |
| `docmind-rabbitmq` | 5672, 15672 | AMQP + Management UI |
| `docmind-ollama` | 11434 | Локальный LLM (опционально) |
| `docmind-api` | 8000 | FastAPI (`alembic upgrade head` при старте) |
| `docmind-worker` | — | Consumer очереди |

- API / Swagger: http://127.0.0.1:8000/docs  
- Админка: http://127.0.0.1:8000/admin/documents  
- RabbitMQ UI: http://localhost:15672 (`docmind` / `docmind`)

Логи:

```powershell
docker compose logs -f api
docker compose logs -f worker
```

Переменные для контейнеров заданы в `docker-compose.yml` (хосты `db`, `rabbitmq`, `ollama`, не `localhost`). Для смены провайдера LLM поменяйте `EXTRACTOR_PROVIDER` / `LLM_*` у сервисов `api` и `worker`.

### 4. Модель для Ollama (если нужен LLM)

```powershell
docker exec -it docmind-ollama ollama pull llama3.2:1b
docker exec -it docmind-ollama ollama list
```

В compose / `.env`: `EXTRACTOR_PROVIDER=llm`, `LLM_MODEL=llama3.2:1b`.

Рекомендуется лёгкая модель (`llama3.2:1b` ≈ 1.3 GB): полные `mistral` на CPU/Docker Desktop часто убиваются OOM.

### 5. Локальная разработка (API/worker на хосте)

Если нужен hot-reload: поднимите только инфраструктуру и запускайте Python локально.

```powershell
docker compose up -d db rabbitmq ollama
alembic upgrade head
```

Терминал 1:

```powershell
uvicorn app.main:app --reload
```

Терминал 2:

```powershell
python -m app.worker
```

В `.env` для локального режима хосты — `localhost` (см. пример выше).

- Swagger: http://127.0.0.1:8000/docs  
- Админка: http://127.0.0.1:8000/admin/documents  
- Health: http://127.0.0.1:8000/api/v1/health  

---

## Docker: multi-stage сборка

`Dockerfile` — **двухстадийный** (multi-stage), один образ на `api` и `worker`.

| Stage | База | Что делает |
|-------|------|------------|
| `builder` | `python:3.12-slim` | `build-essential`, `libpq-dev`; `pip install --prefix=/install -r requirements.txt` |
| `runtime` | `python:3.12-slim` | копирует только `/install` → `/usr/local`, код `app/` + Alembic; **без** компиляторов |

Зачем так:
- меньший итоговый образ (нет toolchain в runtime);
- меньше attack surface;
- `api` и `worker` разделяют один build (`build: .` в Compose), отличаются только `command`.

Поведение в Compose:
- `api`: `alembic upgrade head && uvicorn ...`
- `worker`: `python -m app.worker` (есть retry подключения к RabbitMQ)
- общий volume `docmind_uploads` → `/app/uploads`
- healthcheck у `db` / `rabbitmq`; worker ждёт healthy deps + старт api

`.dockerignore` исключает из контекста сборки: `venv/`, `.git/`, `.env`, `uploads/`, `tests/`, `samples/`, `.github/` и т.п. — быстрее build и секреты не попадают в образ.

Сборка вручную:

```powershell
docker build -t docmind:local .
docker compose up -d --build
```

---
## Логирование

Логи пишутся в **stdout** (удобно для локального запуска и Docker). Единая настройка — `app/core/logging.py`; вызывается при старте API (`app/main.py`) и worker (`app/worker.py`).

Уровень задаётся переменной `LOG_LEVEL` (по умолчанию `INFO`).

Формат строки:

```text
2026-07-27 10:15:00,123 INFO [docmind.api.v1] upload accepted doc_id=... filename=...
```

Ключевые логгеры:

| Logger | Где | Что пишет |
|--------|-----|-----------|
| `docmind.api.v1` | `app/api/v1/router.py` | upload, enqueue, ручной process |
| `docmind.queue.publisher` | `app/queue/publisher.py` | публикация в RabbitMQ |
| `docmind.worker` | `app/worker.py` | старт, ack/nack, ошибки сообщений |
| `docmind.processor` | `app/services/processor.py` | start / classified / done / failed |

Проверка локально: загрузите PDF через Swagger и смотрите терминалы API и worker. В Docker:

```powershell
docker compose logs -f api
docker compose logs -f worker
```

---

## API

Префикс версии: `/api/v1`.

| Метод | Путь | Код | Описание |
|--------|------|-----|----------|
| `GET` | `/health` | 200 | Liveness |
| `POST` | `/documents` | 202 | Загрузка PDF → файл + БД + очередь |
| `GET` | `/documents/{id}` | 200 / 404 | Метаданные, статус, текст, `extraction_result` |
| `POST` | `/documents/{id}/process` | 200 / 422 | Ручной повтор обработки (без очереди) |

### Пример сценария

1. `POST /api/v1/documents` — прикрепить PDF из `samples/`  
2. Ответ: `{ "id": "...", "status": "queued", ... }`  
3. Worker в логах: `Processing` → `Done`  
4. `GET /api/v1/documents/{id}` — `status: done`, заполнены `extracted_text` и `extraction_result`  

Ошибки upload:

- не PDF → `400`
- пустой файл → `400`
- очередь недоступна → `503`, документ помечается `failed`

---

## Модель данных документа

Основные поля таблицы `documents`:

| Поле | Смысл |
|------|--------|
| `id` | UUID |
| `filename` | Оригинальное имя файла |
| `storage_path` | Путь на диске |
| `status` | Жизненный цикл обработки |
| `document_type` | `discharge` / `prescription` / `diagnosis` / `unknown` |
| `extracted_text` | Текст из PDF |
| `extraction_result` | JSONB: сущности + meta экстрактора |
| `error_message` | Причина `failed` |
| `created_at` / `updated_at` | UTC timestamps |

Индексы: `status`, `created_at`.

### Пример `extraction_result`

```json
{
  "document_type": "prescription",
  "extractor": "llm",
  "confidence": 0.8,
  "data": {
    "patient": { "full_name": "Anna Smirnova" },
    "diagnosis": { "code": "J03.9", "name": "Острый тонзиллит" },
    "treatment": {
      "medication": "Ibuprofen",
      "dosage": "200 mg tablets, twice daily"
    },
    "document_date": "2026-05-01",
    "raw_notes": null
  }
}
```

`raw_notes` — опциональное поле для неструктурированных остатков; полный текст документа хранится в `extracted_text`.

---

## Извлечение сущностей

Интерфейс `EntityExtractor` + фабрика по `EXTRACTOR_PROVIDER`:

| Provider | Класс | Когда использовать |
|----------|--------|---------------------|
| `mock` | `MockEntityExtractor` | Локальная разработка, CI, стабильные демо |
| `llm` | `LlmEntityExtractor` | Ollama / Mistral; ответ валидируется `MedicalExtraction` |

Граница ответственности:

- **правила** — классификация типа документа;
- **LLM / mock** — сущности из текста;
- **Pydantic** — контракт и отсечение битого JSON.

---

## Тестовые PDF

| Файл | Назначение |
|------|------------|
| `samples/test_discharge.pdf` | Выписка (Ivan Ivanov, J06.9) |
| `samples/test_prescription.pdf` | Рецепт без отдельного акцента на МКБ |
| `samples/test_rx_diagnosis.pdf` | Рецепт + диагноз на русском + лечение |

---

## Админка

- Список: `/admin/documents`  
- Карточка: `/admin/documents/{id}` — полный текст и pretty-printed JSON  

Без аутентификации (только для локальной отладки).

---

## Тесты

```powershell
pytest -v
```

Покрытие:

- классификатор (`test_classifier.py`)
- mock-экстрактор (`test_mock_extractor.py`)
- PDF-extractor (`test_pdf_extractor.py`)
- Pydantic-схемы (`test_extraction_schema.py`)
- API через `TestClient` с моками БД/очереди/диска (`test_api.py`)

Конфиг: `pytest.ini` (`pythonpath = .`).

---

## Линтинг (Ruff)

В проекте один линтер/форматтер — **Ruff** (вместо flake8 + isort + black).

| Файл | Роль |
|------|------|
| `requirements-dev.txt` | `ruff==0.12.5` (только для разработки и CI lint) |
| `ruff.toml` | правила `check` + `format` |

Установка:

```powershell
pip install -r requirements-dev.txt
```

Проверка (то же, что в CI):

```powershell
ruff check app tests
ruff format --check app tests
```

Автоисправление:

```powershell
ruff check --fix app tests
ruff format app tests
```

Что включено в `ruff.toml`:

| Набор | Смысл |
|-------|--------|
| `E` | pycodestyle errors |
| `F` | pyflakes (неиспользуемые импорты и т.п.) |
| `I` | isort (порядок импортов) |
| `UP` | pyupgrade (современный синтаксис Python) |
| `B` | flake8-bugbear |

Исключения:

- `E501` — длина строки пока не блокирует
- `B008` — FastAPI-идиома `Depends(...)` / `File(...)` в defaults
- `tests/*` — разрешён `assert` (`B011`)
- `alembic/*` — миграции не линтим строго

Target: Python 3.12, `line-length = 100`, кавычки double.

Ruff **не** ставится в runtime-образ: в Docker/`requirements.txt` его нет, только в `requirements-dev.txt` и job `lint`.

---

## CI

Workflow: `.github/workflows/ci.yml`

- Триггеры: `push` / `pull_request` в `main` / `master` / `develop`
- Job `lint`: Python 3.12 → `pip install -r requirements-dev.txt` → `ruff check` + `ruff format --check`
- Job `test`: Python 3.12 → `pip install -r requirements.txt` → `pytest -v`
- Jobs независимы: lint не тянет зависимости приложения, test не ставит Ruff
- Без поднятия Postgres/Rabbit/Ollama — API-тесты используют моки

---

## Миграции

```powershell
alembic revision --autogenerate -m "описание"
alembic upgrade head
alembic downgrade -1
```

История включает создание таблицы `documents`, переименование `error_message`, поля `extracted_text` и `extraction_result` (JSONB).

---

## Типичные проблемы

| Симптом | Что проверить |
|---------|----------------|
| `Connection refused` :5432 / :5672 | `docker compose up -d`, `docker compose ps` |
| Worker не обрабатывает | Запущен ли worker (Compose или `python -m app.worker`), очередь в UI RabbitMQ |
| Worker падает при старте Compose | Смотрите retry в логах; RabbitMQ должен стать healthy |
| LLM `signal: killed` | OOM — используйте `llama3.2:1b`, уменьшите число моделей в Ollama |
| Битый JSON от LLM | Включён json mode / парсер в `llm.py`; для демо — `EXTRACTOR_PROVIDER=mock` |
| `ModuleNotFoundError: app` | Запуск из корня проекта; есть `pytest.ini` |
| Сборка Docker тянет `venv` / огромный context | Проверьте `.dockerignore` |
| В контейнере нет `.env` | Нормально: переменные задаются в `docker-compose.yml` |

---

## Что можно добавить дальше

- Prometheus / Grafana (метрики очереди, latency, failed)
- JSON-логи + централизованный сбор (Loki / ELK)
- `request_id` / корреляция HTTP ↔ worker по `document_id`
- Eval-набор и честные метрики качества классификации / сущностей
- Auth для админки
- Dead-letter queue для «ядовитых» сообщений
- Object storage (S3/MinIO) вместо локального `uploads/`

---

## Лицензия

Учебный проект. При использовании PyMuPDF учитывайте условия лицензии AGPL / коммерческой лицензии Artifex в зависимости от сценария распространения.
