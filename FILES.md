# Что в каком файле

Краткий путеводитель по проекту DocMind. Открывайте, когда нужно вспомнить, где что лежит.

---

## Корень

| Файл | Зачем |
|------|--------|
| `README.md` | Полное описание проекта, запуск, API, логи, метрики, Loki, Docker, CI |
| `FILES.md` | Этот файл — карта исходников |
| `requirements.txt` | Python-зависимости runtime (API, worker, метрики, тесты) |
| `requirements-dev.txt` | Dev-зависимости: сейчас `ruff==0.12.5` |
| `ruff.toml` | Конфиг Ruff: select E/F/I/UP/B, ignore E501/B008, format |
| `Dockerfile` | Multi-stage: `builder` (pip + compilers) → `runtime` (только пакеты + код) |
| `docker-compose.yml` | App + Prometheus, Grafana, Loki, Promtail |
| `.dockerignore` | Не класть в context: `venv/`, `.env`, `uploads/`, `tests/`, `samples/`, `.git/` |
| `scripts/load_upload.ps1` | Нагрузка: повторный `POST /documents` через curl.exe |
| `scripts/run_eval.py` | Eval: classification + field accuracy на `eval/gold/cases.jsonl` |
| `eval/README.md` | Описание eval-набора и последних метрик |
| `eval/gold/cases.jsonl` | Gold-кейсы (JSON-массив: text, expected_type, expected fields) |
| `pytest.ini` | Настройки pytest (`pythonpath`, `testpaths`) |
| `alembic.ini` | Конфиг Alembic (миграции) |
| `.env.example` | Шаблон переменных окружения (в git); копировать в `.env` |
| `.env` | Локальные секреты и настройки (не в git), опционально `LOG_LEVEL` |
| `.gitignore` | Что не коммитить (`.env`, `venv`, `uploads`, кэш) |

---

## Docker

| Файл | Зачем |
|------|--------|
| `Dockerfile` | Stage 1 `builder`: системные deps + `pip install --prefix=/install`. Stage 2 `runtime`: копирует `/install`, `app/`, Alembic; CMD = uvicorn |
| `docker-compose.yml` | `api` / `worker` + monitoring stack; shared volume uploads; healthchecks db/rabbitmq |
| `.dockerignore` | Ускоряет build и не тащит секреты/мусор в образ |

Compose: `api` делает `alembic upgrade head` при старте; `worker` — `python -m app.worker`.

---

## Monitoring

| Файл | Зачем |
|------|--------|
| `app/core/metrics.py` | Prometheus `Counter` / `Histogram` |
| `app/main.py` | ASGI endpoint `/metrics/` для API |
| `app/worker.py` | HTTP metrics на `:8001/metrics` |
| `monitoring/prometheus.yml` | Scrape `api:8000/metrics/` и `worker:8001/metrics` |
| `monitoring/loki-config.yml` | Конфиг Loki (порт 3100) |
| `monitoring/promtail-config.yml` | Docker SD → лейблы `container` / `compose_service` → push в Loki |
| `monitoring/grafana/provisioning/datasources/datasources.yml` | Datasources Prometheus + Loki |
| `monitoring/grafana/provisioning/dashboards/dashboards.yml` | Provider папки dashboards |
| `monitoring/grafana/dashboards/docmind-overview.json` | Dashboard DocMind Overview |
| `scripts/load_upload.ps1` | Генерация нагрузки для демо метрик/логов |

Порты с хоста: Prometheus `9090`, Grafana `3000`, Loki `3100`, Promtail `9080`.  
Внутри Docker-сети Grafana ходит на `http://prometheus:9090` и `http://loki:3100`.

LogQL только в datasource Loki. Примеры: `{compose_service="api"}`, `{compose_service=~"api|worker"} |= "request_id="`.

---

## Линтинг

| Файл | Зачем |
|------|--------|
| `requirements-dev.txt` | Ставится локально и в CI job `lint`; не нужен в Docker runtime |
| `ruff.toml` | Единый линтер + форматтер: `ruff check`, `ruff format` |
| `.github/workflows/ci.yml` | Job `lint` гоняет Ruff до/параллельно с `test` |

Команды: `ruff check app tests`, `ruff format --check app tests` (или `--fix` / `ruff format` для правок).

---

## `.github/`

| Файл | Зачем |
|------|--------|
| `workflows/ci.yml` | CI: job `lint` (Ruff из `requirements-dev.txt`) + job `test` (pytest из `requirements.txt`) |

---

## `app/` — приложение

| Файл | Зачем |
|------|--------|
| `main.py` | FastAPI, `RequestIdMiddleware` (`X-Request-ID`), API/админка, `/metrics/` |
| `worker.py` | Consumer: `document_id` + `request_id`; при ошибке `nack` → DLQ; метрики `:8001` |

### `app/core/`

| Файл | Зачем |
|------|--------|
| `config.py` | Настройки из `.env` (БД, LLM, `rabbitmq_queue` / `rabbitmq_dlq`, пути) |
| `logging.py` | stdout-логи, `request_id` ContextVar + Filter, хелперы set/get/clear |
| `metrics.py` | Prometheus-счётчики и histogram для upload/process |

### `app/api/`

| Файл | Зачем |
|------|--------|
| `v1/router.py` | REST API v1: health, upload, get, process; логи upload / enqueue / manual process |

### `app/admin/`

| Файл | Зачем |
|------|--------|
| `router.py` | HTML-админка: список документов и карточка по id |

### `app/db/`

| Файл | Зачем |
|------|--------|
| `base.py` | Базовый класс SQLAlchemy `Base` для моделей |
| `session.py` | Engine, Session, dependency `get_db` |

### `app/models/`

| Файл | Зачем |
|------|--------|
| `document.py` | ORM-модель `Document` + enum статусов/типов (таблица БД) |
| `__init__.py` | Экспорт моделей (нужно для Alembic) |

### `app/schemas/`

| Файл | Зачем |
|------|--------|
| `document.py` | Pydantic-схемы ответов API (контракт JSON) |
| `extraction.py` | Схемы сущностей: patient, diagnosis, treatment, ExtractionResult |

### `app/storage/`

| Файл | Зачем |
|------|--------|
| `documents.py` | Репозиторий: add / get / list документов через Session |

### `app/queue/`

| Файл | Зачем |
|------|--------|
| `setup.py` | `declare_process_queues`: основная очередь + DLQ (`x-dead-letter-*`) |
| `publisher.py` | Публикация `{document_id, request_id}` в RabbitMQ |

### `app/services/`

| Файл | Зачем |
|------|--------|
| `file_storage.py` | Сохранение PDF на диск как `{uuid}.pdf` |
| `pdf_extractor.py` | Достаёт текст из PDF (PyMuPDF) |
| `classifier.py` | Rule-based классификация типа документа (без слишком общих токенов вроде `mg`) |
| `processor.py` | Пайплайн: текст → тип → сущности → запись в БД; логи, счётчики done/failed и latency |
| `extractors/base.py` | Абстрактный интерфейс экстрактора сущностей |
| `extractors/mock.py` | Regex/эвристики без LLM (стабильно для тестов) |
| `extractors/llm.py` | Вызов LLM + парсинг JSON + валидация Pydantic |
| `extractors/factory.py` | Выбор mock/llm по `EXTRACTOR_PROVIDER` |

### `app/templates/admin/`

| Файл | Зачем |
|------|--------|
| `base.html` | Общий layout и стили админки |
| `documents_list.html` | Таблица всех документов |
| `document_detail.html` | Полный текст и JSON `extraction_result` |

---

## `alembic/` — миграции БД

| Файл | Зачем |
|------|--------|
| `env.py` | Подключение Alembic к `settings.database_url` и моделям |
| `script.py.mako` | Шаблон новой миграции |
| `versions/b539e13ac795_*.py` | Создание таблицы `documents` |
| `versions/bc1598f34896_*.py` | Rename `error_massage` → `error_message` |
| `versions/9998a5c995fd_*.py` | Колонка `extracted_text` |
| `versions/44594d1b883f_*.py` | Колонка `extraction_result` (JSONB) |

---

## `tests/` — тесты

| Файл | Зачем |
|------|--------|
| `conftest.py` | Общие фикстуры (тексты, путь к sample PDF) |
| `test_classifier.py` | Unit: классификация типа |
| `test_mock_extractor.py` | Unit: mock-извлечение сущностей |
| `test_pdf_extractor.py` | Unit: чтение PDF / отсутствие файла |
| `test_extraction_schema.py` | Unit: валидация Pydantic (`confidence`) |
| `test_processor.py` | Unit: пайплайн `process_document` (success / failed / not found) |
| `test_factory.py` | Unit: выбор mock/llm/unknown по `EXTRACTOR_PROVIDER` |
| `test_api.py` | API: TestClient + моки диска/БД/очереди, в т.ч. manual process |

---

## `samples/` — тестовые PDF

| Файл | Зачем |
|------|--------|
| `test_discharge.pdf` | Выписка (Ivan Ivanov, J06.9) |
| `test_prescription.pdf` | Рецепт (Maria Petrova) |
| `test_rx_diagnosis.pdf` | Рецепт + диагноз на русском + лечение |

---

## Служебные папки (не коммитятся / генерируются)

| Путь | Зачем |
|------|--------|
| `venv/` | Виртуальное окружение Python |
| `uploads/` | Загруженные пользователем PDF |
| `.pytest_cache/` | Кэш pytest |
| `.ruff_cache/` | Кэш Ruff |
| `__pycache__/` | Байткод Python |

---

## Как читать код по слоям

1. **HTTP** → `app/api/v1/router.py`, `app/admin/router.py`  
2. **Бизнес-пайплайн** → `app/services/processor.py`  
3. **Очередь** → `app/queue/setup.py` + `publisher.py` + `app/worker.py` (DLQ)  
4. **Данные** → `app/models/` + `app/storage/` + `app/schemas/`  
5. **Конфиг** → `app/core/config.py` + `.env.example` / `.env`  
6. **Логи** → `app/core/logging.py` (+ вызовы в `main.py` / `worker.py`)  
7. **Метрики** → `app/core/metrics.py` + `/metrics/` + `monitoring/prometheus.yml`  
8. **Логи в Grafana** → Promtail + Loki + `monitoring/grafana/`  
9. **Docker** → `Dockerfile` + `docker-compose.yml` + `.dockerignore`  
10. **Нагрузка** → `scripts/load_upload.ps1`  
11. **Eval** → `scripts/run_eval.py` + `eval/gold/cases.jsonl`  
