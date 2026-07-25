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
- Unit- и API-тесты (pytest), CI на GitHub Actions

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
| CI | GitHub Actions |
| Инфра | Docker Compose |

---

## Структура проекта

```text
DocMind/
├── app/
│   ├── main.py                 # точка входа FastAPI
│   ├── worker.py               # consumer RabbitMQ
│   ├── admin/                  # HTML-админка
│   ├── api/v1/                 # REST API v1
│   ├── core/config.py          # настройки из .env
│   ├── db/                     # engine, session, Base
│   ├── models/                 # SQLAlchemy-модели
│   ├── schemas/                # Pydantic-схемы API и extraction
│   ├── services/
│   │   ├── file_storage.py     # сохранение PDF
│   │   ├── pdf_extractor.py    # текст из PDF
│   │   ├── classifier.py       # тип документа
│   │   ├── processor.py        # пайплайн обработки
│   │   └── extractors/         # mock + llm + factory
│   ├── storage/                # репозиторий документов
│   ├── queue/                  # публикация в RabbitMQ
│   └── templates/admin/        # Jinja2-шаблоны
├── alembic/                    # миграции БД
├── samples/                    # тестовые PDF
├── tests/                      # pytest
├── .github/workflows/ci.yml    # CI
├── docker-compose.yml          # Postgres, Ollama, RabbitMQ
├── requirements.txt
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
```

Для облака Mistral (вместо Ollama):

```env
EXTRACTOR_PROVIDER=llm
LLM_BASE_URL=https://api.mistral.ai/v1
LLM_MODEL=mistral-small-latest
LLM_API_KEY=ваш_ключ
```

Секреты не коммитьте: `.env` уже в `.gitignore`.

### 3. Инфраструктура

```powershell
docker compose up -d
docker compose ps
```

Поднимаются:

| Сервис | Порт | Назначение |
|--------|------|------------|
| `docmind-db` | 5432 | PostgreSQL |
| `docmind-rabbitmq` | 5672, 15672 | AMQP + Management UI |
| `docmind-ollama` | 11434 | Локальный LLM (опционально) |

RabbitMQ UI: http://localhost:15672  
Логин / пароль: `docmind` / `docmind`

### 4. Модель для Ollama (если нужен LLM)

```powershell
docker exec -it docmind-ollama ollama pull llama3.2:1b
docker exec -it docmind-ollama ollama list
```

В `.env`: `EXTRACTOR_PROVIDER=llm`, `LLM_MODEL=llama3.2:1b`.

Рекомендуется лёгкая модель (`llama3.2:1b` ≈ 1.3 GB): полные `mistral` на CPU/Docker Desktop часто убиваются OOM.

### 5. Миграции БД

```powershell
alembic upgrade head
```

### 6. Запуск API и worker

Терминал 1:

```powershell
uvicorn app.main:app --reload
```

Терминал 2:

```powershell
python -m app.worker
```

- Swagger: http://127.0.0.1:8000/docs  
- Админка: http://127.0.0.1:8000/admin/documents  
- Health: http://127.0.0.1:8000/api/v1/health  

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

## CI

Workflow: `.github/workflows/ci.yml`

- Триггеры: `push` / `pull_request` в `main` или `master`
- Python 3.12, `pip install -r requirements.txt`, `pytest -v`
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
| Worker не обрабатывает | Запущен ли `python -m app.worker`, очередь в UI RabbitMQ |
| LLM `signal: killed` | OOM — используйте `llama3.2:1b`, уменьшите число моделей в Ollama |
| Битый JSON от LLM | Включён json mode / парсер в `llm.py`; для демо — `EXTRACTOR_PROVIDER=mock` |
| `ModuleNotFoundError: app` | Запуск из корня проекта; есть `pytest.ini` |

---

## Что можно добавить дальше

- Docker-образы для `api` и `worker` в Compose
- Prometheus / Grafana (метрики очереди, latency, failed)
- Eval-набор и честные метрики качества классификации / сущностей
- Auth для админки
- Dead-letter queue для «ядовитых» сообщений
- Object storage (S3/MinIO) вместо локального `uploads/`

---

## Лицензия

Учебный проект. При использовании PyMuPDF учитывайте условия лицензии AGPL / коммерческой лицензии Artifex в зависимости от сценария распространения.
