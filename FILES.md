# Что в каком файле

Краткий путеводитель по проекту DocMind. Открывайте, когда нужно вспомнить, где что лежит.

---

## Корень

| Файл | Зачем |
|------|--------|
| `README.md` | Описание продукта: задача → решение → API → быстрый старт |
| `FILES.md` | Этот файл — карта исходников |
| `.github/workflows/ci.yml` | GitHub Actions CI: lint (Ruff) → unit-тесты (Python 3.12 + 3.13) → integration-тесты; `cancel-in-progress` для экономии runner-минут |
| `requirements.txt` | Python-зависимости runtime (FastAPI, SQLAlchemy, asyncpg, pika, tenacity, python-json-logger…) |
| `requirements-dev.txt` | Dev-зависимости: ruff, pytest-cov, httpx, testcontainers, pytest-asyncio |
| `ruff.toml` | Конфиг Ruff: select E/F/I/UP/B; format double-quotes |
| `Dockerfile` | Multi-stage: `builder` (pip + compilers) → `runtime` (пакеты + код); non-root `appuser` через `gosu` |
| `docker-entrypoint.sh` | Запускается как root: `chown /app/uploads → exec gosu appuser <cmd>`. Решает проблему прав на Docker volume при non-root пользователе |
| `docker-compose.yml` | api / worker + PostgreSQL + RabbitMQ + Ollama + мониторинг-стек; пароли из `.env` (`${VAR:?}` — обязательные), порты только на `127.0.0.1`, версии образов закреплены |
| `docker-compose.override.yml` | **Только dev**, подхватывается автоматически: `promtail` с монтированием `docker.sock`. Prod: `docker compose -f docker-compose.yml up -d` |
| `.dockerignore` | Не класть в context: `venv/`, `.env`, `uploads/`, `tests/`, `samples/`, `.git/` |
| `pytest.ini` | Настройки pytest: `testpaths`, addopts с покрытием; по умолчанию `-m "not integration"` |
| `alembic.ini` | Конфиг Alembic (миграции) |
| `.env.example` | Шаблон переменных окружения (в git); копировать в `.env` |
| `.env` | Локальные секреты и настройки (не в git) |
| `scripts/load_upload.ps1` | Нагрузка: повторный `POST /documents` через curl.exe |
| `scripts/measure_latency.ps1` | Замер latency upload/process |
| `scripts/run_eval.py` | Eval: classification + field accuracy на `eval/gold/cases.jsonl` |
| `scripts/generate_eval_cases.py` | Генерация gold-кейсов для eval |
| `eval/README.md` | Описание eval-набора и последних метрик |
| `eval/gold/cases.jsonl` | Gold-кейсы (text, expected_type, expected fields) |

---

## Docker

| Файл | Зачем |
|------|--------|
| `Dockerfile` | Stage 1 `builder`: системные deps + `pip install --prefix=/install`. Stage 2 `runtime`: копирует `/install`, `app/`, Alembic; non-root `appuser`; ENTRYPOINT = `docker-entrypoint.sh` |
| `docker-entrypoint.sh` | Entrypoint: запускается от root, исправляет права на примонтированный volume `/app/uploads`, затем `exec gosu appuser <cmd>` |
| `docker-compose.yml` | `api` / `worker` + PostgreSQL / RabbitMQ / Ollama + monitoring stack; shared volume uploads; healthchecks |
| `.dockerignore` | Ускоряет build и не тащит секреты/мусор в образ |

`api` при старте выполняет `alembic upgrade head`, затем uvicorn.  
`worker` — `python -m app.worker`; при SIGTERM завершает текущее сообщение и выходит.

---

## Monitoring

| Файл | Зачем |
|------|--------|
| `app/core/metrics.py` | Prometheus `Counter` / `Histogram`: upload, process (done/failed), LLM, latency, `extractor_fallback_total` |
| `app/main.py` | ASGI endpoint `/metrics` для API (Basic Auth) |
| `app/worker.py` | HTTP metrics на `:8001/metrics` |
| `monitoring/prometheus.yml` | Scrape `api:8000/metrics` (Basic Auth, пароль через `password_file`, который создаётся при старте контейнера из `METRICS_PASSWORD`), `worker:8001/metrics` и `rabbitmq:15692/metrics/detailed` (глубина очереди и DLQ по очередям) |
| `monitoring/loki-config.yml` | Конфиг Loki (порт 3100) |
| `monitoring/promtail-config.yml` | (dev, через `docker-compose.override.yml`) Docker SD → лейблы `container` / `compose_service` → push в Loki |
| `monitoring/grafana/provisioning/datasources/datasources.yml` | Datasources Prometheus + Loki |
| `monitoring/grafana/provisioning/dashboards/dashboards.yml` | Provider папки dashboards |
| `monitoring/grafana/dashboards/docmind-overview.json` | Dashboard DocMind Overview (34 панели, 6 блоков: обзор за период, конвейер, LLM/fallback, HTTP API, ресурсы, логи Loki); переменная `service` для логов, аннотации «Перезапуски». После правки JSON на Windows выполните `docker compose restart grafana` (авто-перечитывание на bind mount не срабатывает) |
| `scripts/load_upload.ps1` | Генерация нагрузки для демо метрик/логов; ключ API берёт из `-ApiKey`, `$env:API_KEY` или `.env` |

Порты с хоста (только `127.0.0.1`): Prometheus `9090`, Grafana `3000`, Loki `3100`, Promtail `9080`.

---

## `app/` — приложение

| Файл | Зачем |
|------|--------|
| `main.py` | FastAPI: `RequestIdMiddleware` (`X-Request-ID`), `MetricsAuthMiddleware`, монтирование API v1 и админки, `/metrics` |
| `worker.py` | RabbitMQ consumer: читает `document_id`, запускает `process_document`; graceful shutdown по SIGTERM/SIGINT; exponential backoff при реконнекте; метрики на `:8001` |

### `app/core/`

| Файл | Зачем |
|------|--------|
| `config.py` | Настройки из `.env`: БД (+ пул: `db_pool_size`, `max_overflow`, `pool_recycle`), LLM (`llm_timeout`), логи (`log_level`, `log_format`), RabbitMQ, метрики; `@model_validator` `validate_secrets`: **отказ старта** при пустом `api_key` / `admin_password` / `metrics_password` (fail closed), предупреждение о слабых значениях (`change-me`, `admin`) вне debug |
| `security.py` | `constant_time_equals(provided, expected)`: сравнение секретов за постоянное время; при пустом ожидаемом секрете всегда `False` (иначе `compare_digest("", "")` пускал бы по пустому ключу). Используется в API-ключе, админке и `/metrics` |
| `logging.py` | Логирование в stdout: plaintext или JSON (`LOG_FORMAT=json`) через python-json-logger; `request_id` ContextVar + Filter; заглушка шумных библиотек (pika, httpx, openai) |
| `metrics.py` | Prometheus Counter / Histogram: upload, process (done/failed), LLM outcomes, latency (корзины до 300 с), `extractor_fallback_total`, HTTP (`docmind_http_requests_total`, `docmind_http_request_duration_seconds`); серии с известными лейблами предсоздаются, чтобы `rate()` не давал «No data» |
| `http_metrics.py` | `HttpMetricsMiddleware` (чистый ASGI): метрики по шаблону роута (`/documents/{document_id}`), 404 → `unmatched`, необработанное исключение → 500, `/metrics` не учитывается |
| `exceptions.py` | Кастомные доменные исключения: `DocumentNotFoundError`, `DocumentProcessingError`, `EmptyDocumentError`, `StorageError`, `QueueError`, `ExtractionError` |

### `app/api/`

| Файл | Зачем |
|------|--------|
| `deps.py` | `require_api_key`: проверка заголовка `X-API-Key` через `constant_time_equals` (fail closed при пустом ключе) |
| `health_checks.py` | `check_database()` и `check_rabbitmq()` для readiness |
| `v1/router.py` | REST API v1: health/ready, `POST /documents` (upload), `GET /documents` (список + пагинация + фильтр по статусу), `GET /documents/{id}`, `POST /documents/{id}/process` |

### `app/admin/`

| Файл | Зачем |
|------|--------|
| `auth.py` | HTTP Basic Auth для HTML-админки |
| `router.py` | HTML-страницы: список документов с пагинацией и карточка с текстом / JSON-результатом |

### `app/db/`

| Файл | Зачем |
|------|--------|
| `base.py` | Базовый класс SQLAlchemy `Base` для моделей |
| `session.py` | Два движка из одного `DATABASE_URL`: `async_engine` (asyncpg) + `AsyncSessionLocal` + dependency `get_db` — для API; `sync_engine` (psycopg2, URL выводится через `_to_sync_url`) + `SessionLocal` — для worker, ручного `process` и Alembic. Пул настраивается (`pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`, `pool_pre_ping`) |

### `app/models/`

| Файл | Зачем |
|------|--------|
| `document.py` | ORM-модель `Document` + enum `DocumentStatus` / `DocumentType`; поля: UUID, filename, storage_path, extracted_text, extraction_result (JSONB), status (indexed), document_type, error_message, created_at / updated_at |
| `__init__.py` | Экспорт `Document` (нужен Alembic для autodiscovery) |

### `app/schemas/`

| Файл | Зачем |
|------|--------|
| `document.py` | Pydantic-схемы ответов: `DocumentCreateResponse`, `DocumentResponse`, `DocumentListResponse` (с полями `total` / `has_next`), `HealthResponse`, `ReadyResponse`. Enum `DocumentStatus` / `DocumentType` не дублируются — импортируются из `app/models/document.py` (единый источник истины) |
| `extraction.py` | Схемы сущностей: `PatientInfo`, `DiagnosisInfo`, `TreatmentInfo`, `MedicalExtraction`, `ExtractionResult` (с валидацией `confidence`) |

### `app/storage/`

| Файл | Зачем |
|------|--------|
| `documents.py` | Async-репозиторий: `add_document`, `get_document` (`populate_existing=True` — всегда свежая строка из БД, а не кэш сессии), `list_documents` (limit / offset / **status filter**, сортировка `created_at DESC, id DESC` — `id` как tie-breaker для стабильной пагинации), `count_documents` (**status filter**) |

### `app/queue/`

| Файл | Зачем |
|------|--------|
| `setup.py` | `declare_process_queues`: основная очередь + DLQ (`x-dead-letter-*`) |
| `publisher.py` | Публикация `{document_id, request_id}` в RabbitMQ; lazy-connect + один retry при обрыве. Доступ к общему соединению/каналу защищён `threading.RLock` — pika не потокобезопасна, а API вызывает publisher из пула потоков (`anyio.to_thread`) |

### `app/services/`

| Файл | Зачем |
|------|--------|
| `file_storage.py` | Async-запись PDF через `aiofiles`: пишет в `{uuid}.tmp`, затем атомарный `os.replace`; при `OSError` убирает tmp и бросает `StorageError`; `delete_upload` не падает при отсутствии файла |
| `pdf_extractor.py` | Извлечение текста из PDF через PyMuPDF (`fitz`) |
| `classifier.py` | Rule-based классификация типа документа по ключевым словам и score |
| `processor.py` | Синхронный пайплайн (sync `Session`, вызывается worker'ом и ручным `process`): `queued/uploaded → processing → done/failed`; бросает `DocumentNotFoundError` / `EmptyDocumentError`; при сбое делает `rollback()` перед записью статуса FAILED; логи, метрики done/failed и latency |
| `extractors/base.py` | Абстрактный интерфейс `EntityExtractor.extract(text, doc_type)` |
| `extractors/mock.py` | Regex/эвристики без LLM (детерминированный, удобен для тестов) |
| `extractors/llm.py` | LLM через OpenAI-compatible API; **retry до 3 раз** (tenacity, exponential backoff) при `APIConnectionError` / `OSError`; при HTTP-ошибке (`APIStatusError`, модель не поддерживает `response_format`) один повтор без `json_object`; нормализация и валидация ответа через Pydantic |
| `extractors/fallback.py` | `FallbackEntityExtractor(primary, secondary)` — при сбое primary автоматически переключается на secondary; помечает результат `extractor=regex_fallback`, снижает confidence, инкрементирует Prometheus-счётчик |
| `extractors/factory.py` | При `mock` → `MockEntityExtractor`; при `llm` → `FallbackEntityExtractor(LlmEntityExtractor, MockEntityExtractor)` — graceful degradation вместо FAILED |

### `app/templates/admin/`

| Файл | Зачем |
|------|--------|
| `base.html` | Общий layout и стили |
| `documents_list.html` | Таблица документов с пагинацией |
| `document_detail.html` | Полный текст + JSON `extraction_result` |

---

## `alembic/` — миграции БД

| Файл | Зачем |
|------|--------|
| `env.py` | Подключение Alembic к моделям; URL берётся из `Config` (`set_main_option`), если задан явно (так тесты направляют миграции в testcontainers), иначе из `settings.database_url`; asyncpg-URL конвертируется в psycopg2; `compare_type=True` |
| `script.py.mako` | Шаблон новой миграции |
| `versions/b539e13ac795_*.py` | Создание таблицы `documents` |
| `versions/bc1598f34896_*.py` | Rename `error_massage` → `error_message` |
| `versions/9998a5c995fd_*.py` | Колонка `extracted_text` |
| `versions/44594d1b883f_*.py` | Колонка `extraction_result` (JSONB) |

---

## `tests/` — тесты

### Unit-тесты (`tests/`)

| Файл | Что проверяет |
|------|----------------|
| `conftest.py` | Фикстуры: тексты документов, путь к sample PDF, `client` (starlette `TestClient` с замоканными async-FS / storage / queue — реальной БД нет, поэтому loop-конфликтов нет) |
| `test_classifier.py` | Rule-based классификатор (discharge / prescription / diagnosis / unknown) |
| `test_mock_extractor.py` | Mock-экстрактор: поля patient, diagnosis, treatment, confidence |
| `test_pdf_extractor.py` | Чтение реального sample PDF; FileNotFoundError для отсутствующего файла |
| `test_extraction_schema.py` | Pydantic-валидация: `confidence` в диапазоне, округление |
| `test_processor.py` | Пайплайн `process_document`: success, `DocumentNotFoundError`, пустой текст, ошибка экстрактора |
| `test_factory.py` | Фабрика: `mock` → `MockEntityExtractor`, `llm` → `FallbackEntityExtractor` с правильными primary/secondary, unknown → ValueError, case-insensitive |
| `test_fallback_extractor.py` | `FallbackEntityExtractor`: success без fallback, переключение на secondary, cap confidence ≤ 0.5, Prometheus-счётчик, сохранность данных |
| `test_exceptions.py` | Все 7 доменных исключений: поля, строки сообщений, иерархия наследования, ловля через `DocMindError` |
| `test_worker.py` | `handle_message` (success / malformed JSON / exception / missing key / invalid UUID / db.close всегда); `_connect_with_backoff` (3 сценария); `_handle_signal` устанавливает флаг |
| `test_llm_extractor.py` | `_extract_json_object` (чистый JSON / markdown / мусор), `_normalize_diagnosis_fields`, `_fill_from_text`, `LlmEntityExtractor.extract` (success / метрика / invalid JSON / ValidationError / retry на APIConnectionError / повтор без `json_object` при `APIStatusError`) |
| `test_documents_storage.py` | SQL-запросы через mock-сессию: limit, offset в stmt |
| `test_publisher.py` | RabbitMQ publisher: повторное использование канала, `basic_publish` вызывается; 8 параллельных потоков сериализуются блокировкой (в канале одновременно не больше одного publish) |
| `test_health.py` | Эндпоинты `/health` и `/health/ready`: ok / 503 / без API-ключа |
| `test_metrics_auth.py` | Basic Auth для `/metrics`: 401 без заголовка, 200 с верным ключом |
| `test_http_metrics.py` | HTTP-метрики: шаблон роута вместо реального URL, группировка 404, 500 при исключении, гистограмма, игнор `/metrics`, предсозданные серии |
| `test_security.py` | Безопасность: `constant_time_equals`; пустой API-ключ / пароль `/metrics` / пароль админки не дают обойти аутентификацию; `Settings` отказывается стартовать с пустым секретом и предупреждает о слабом; регрессия ReDoS в `MockEntityExtractor` (20 000 пробелов по всем полям < 2 с) |
| `test_admin.py` | HTML-админка: список документов, карточка, 401 без auth, 401 неверный пароль, 404, пустой extraction_result |
| `test_api.py` | API v1 полный цикл: upload (202, валидации, 503 при недоступной очереди), GET document, GET list (пагинация, фильтр по статусу, has_next), manual process (в т.ч. `DocumentProcessingError` → 422, а не 500); upload: 503 при `StorageError`, удаление файла при сбое записи в БД |

### Интеграционные тесты (`tests/integration/`)

Требуют Docker для тестов с PostgreSQL. При недоступном Docker — **SKIPPED**, не ERROR.  
Изоляция через `SAVEPOINT` (один контейнер на сессию, rollback после каждого теста).

Особенности async-тестов (выяснены на практике — каждый пункт был причиной реального падения):

- **Клиент — `httpx.AsyncClient` + `ASGITransport`, а не `TestClient`.** `TestClient` гонит приложение в своём event loop (отдельный поток), а соединение `asyncpg` в `db_session` привязано к loop pytest-asyncio → `attached to a different loop`. `ASGITransport` выполняет приложение в том же loop, что и тест.
- **Async-engine — на каждый тест, с `NullPool`.** Каждый тест получает свой event loop; общий session-scope пул переживал бы свой loop → `Event loop is closed`. Sync-engine с миграциями при этом остаётся session-scope.
- **Миграции идут в контейнер.** `alembic/env.py` уважает URL, заданный через `Config.set_main_option`; иначе они молча уехали бы в БД из `DATABASE_URL`.
- Внутри одной транзакции `now()` одинаков у всех строк — поэтому тесты порядка задают `created_at` явно.

```bash
pytest -m integration          # только интеграционные
pytest                         # только unit (по умолчанию)
```

| Файл | Что проверяет |
|------|----------------|
| `conftest.py` | `pg_container` (PostgreSQL 16 через testcontainers, session), `integration_sync_engine` (session; `alembic upgrade head` в контейнер), `integration_async_engine` (на каждый тест, `NullPool`), `db_session` (AsyncSession, SAVEPOINT-изоляция), `sync_db_session` (Session, SAVEPOINT — для `process_document`), `api_client` (`httpx.AsyncClient` + `ASGITransport` + `dependency_overrides[get_db]`) |
| `test_db_integration.py` | Реальный PostgreSQL: CRUD, JSONB round-trip, `list_documents` (фильтр / limit / offset / ordering по `created_at`, стабильный порядок при равных `created_at`), `count_documents` совпадает с `len(list)`, переходы статусов |
| `test_api_integration.py` | HTTP (async) + реальная БД: upload создаёт запись и отклоняет не-PDF / фейковые байты / пустой файл, GET возвращает данные и 404, `storage_path` не утекает в ответ, list с пагинацией, фильтром по статусу, 422 на неверный статус, 401 без API-ключа |
| `test_processor_integration.py` | Полный pipeline: sample PDF → DONE в реальной БД, JSONB заполнен, все sample-PDF проходят (smoke), `DocumentNotFoundError` для несуществующего id, ошибки экстрактора → FAILED + `error_message`, повторная обработка из FAILED работает |
| `test_file_storage_integration.py` | Реальная ФС: атомарность (нет `.tmp`-файлов после save), перезапись, крупный файл (1 МБ), round-trip save → delete, несколько документов независимы, реальный PDF читается PyMuPDF |

---

## `samples/` — тестовые PDF

| Файл | Содержимое |
|------|------------|
| `test_discharge.pdf` | Выписка: Ivan Ivanov, J06.9 |
| `test_prescription.pdf` | Рецепт: Maria Petrova, Ibuprofen 200mg |
| `test_rx_diagnosis.pdf` | Рецепт + диагноз на русском + лечение |

---

## Служебные папки (не коммитятся / генерируются)

| Путь | Зачем |
|------|--------|
| `venv/` | Виртуальное окружение Python |
| `uploads/` | Загруженные пользователем PDF |
| `htmlcov/` | HTML-отчёт покрытия (`pytest --cov`) |
| `.pytest_cache/` | Кэш pytest |
| `.ruff_cache/` | Кэш Ruff |
| `__pycache__/` | Байткод Python |

---

## Как читать код по слоям

1. **HTTP** → `app/api/v1/router.py`, `app/admin/router.py`
2. **Бизнес-пайплайн** → `app/services/processor.py`
3. **Очередь** → `app/queue/setup.py` + `publisher.py` + `app/worker.py` (DLQ, graceful shutdown)
4. **Данные** → `app/models/` + `app/storage/` + `app/schemas/`
5. **Конфиг** → `app/core/config.py` + `.env.example` / `.env`
6. **Исключения** → `app/core/exceptions.py`
7. **Логи** → `app/core/logging.py` (plaintext / JSON; вызовы в `main.py` / `worker.py`)
8. **Метрики** → `app/core/metrics.py` + `/metrics` + `monitoring/prometheus.yml`
9. **Логи в Grafana** → Promtail + Loki + `monitoring/grafana/`
10. **Docker** → `Dockerfile` + `docker-compose.yml` + `.dockerignore`
11. **Тесты unit** → `tests/*.py`
12. **Тесты integration** → `tests/integration/`
13. **Eval** → `scripts/run_eval.py` + `eval/gold/cases.jsonl`
