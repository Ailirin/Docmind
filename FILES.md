# Что в каком файле

Краткий путеводитель по проекту DocMind. Открывайте, когда нужно вспомнить, где что лежит.

---

## Корень

| Файл | Зачем |
|------|--------|
| `README.md` | Полное описание проекта, запуск, API, архитектура |
| `FILES.md` | Этот файл — карта исходников |
| `requirements.txt` | Python-зависимости |
| `docker-compose.yml` | Postgres, RabbitMQ, Ollama |
| `pytest.ini` | Настройки pytest (`pythonpath`, `testpaths`) |
| `alembic.ini` | Конфиг Alembic (миграции) |
| `.env` | Локальные секреты и настройки (не в git) |
| `.gitignore` | Что не коммитить (`.env`, `venv`, `uploads`, кэш) |

---

## `.github/`

| Файл | Зачем |
|------|--------|
| `workflows/ci.yml` | CI: установка зависимостей + `pytest` на push/PR |

---

## `app/` — приложение

| Файл | Зачем |
|------|--------|
| `main.py` | Создаёт FastAPI-приложение, подключает API и админку |
| `worker.py` | Consumer RabbitMQ: читает `document_id`, вызывает `process_document` |

### `app/core/`

| Файл | Зачем |
|------|--------|
| `config.py` | Настройки из `.env` (БД, LLM, очередь, пути) |

### `app/api/`

| Файл | Зачем |
|------|--------|
| `v1/router.py` | REST API v1: health, upload, get, process |

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
| `publisher.py` | Публикация задачи `{document_id}` в RabbitMQ |

### `app/services/`

| Файл | Зачем |
|------|--------|
| `file_storage.py` | Сохранение PDF на диск как `{uuid}.pdf` |
| `pdf_extractor.py` | Достаёт текст из PDF (PyMuPDF) |
| `classifier.py` | Rule-based классификация типа документа |
| `processor.py` | Пайплайн: текст → тип → сущности → запись в БД |
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
| `test_api.py` | API: TestClient + моки диска/БД/очереди |

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
| `__pycache__/` | Байткод Python |

---

## Как читать код по слоям

1. **HTTP** → `app/api/v1/router.py`, `app/admin/router.py`  
2. **Бизнес-пайплайн** → `app/services/processor.py`  
3. **Очередь** → `app/queue/publisher.py` + `app/worker.py`  
4. **Данные** → `app/models/` + `app/storage/` + `app/schemas/`  
5. **Конфиг** → `app/core/config.py` + `.env`  
