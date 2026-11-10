"""Prometheus-метрики DocMind."""

from prometheus_client import Counter, Histogram

DOCUMENTS_UPLOADED = Counter(
    "docmind_documents_uploaded_total",
    "Number of uploaded documents",
)

DOCUMENTS_PROCESSED = Counter(
    "docmind_documents_processed_total",
    "Number of processed documents",
    ["status"],  # done | failed
)

LLM_EXTRACTIONS = Counter(
    "docmind_llm_extractions_total",
    "LLM extraction outcomes",
    ["result"],  # success | validation_error | request_error
)

PROCESS_DURATION = Histogram(
    "docmind_process_duration_seconds",
    "Document processing duration in seconds",
    # Хвост до 300 с: LLM на CPU обрабатывает документ десятки секунд. Если верхняя корзина
    # ниже реальной длительности, histogram_quantile «упирается» в неё и занижает p95/p99.
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)

EXTRACTOR_FALLBACK_TOTAL = Counter(
    "docmind_extractor_fallback_total",
    "Number of times the regex fallback extractor was used instead of LLM",
)

# route — шаблон пути (`/api/v1/documents/{document_id}`), а не реальный URL:
# иначе каждый UUID порождал бы новую серию (взрыв кардинальности).
HTTP_REQUESTS = Counter(
    "docmind_http_requests_total",
    "HTTP requests handled by the API",
    ["method", "route", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "docmind_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# Предсоздаём серии с известными значениями лейблов. Иначе Prometheus не видит
# метрику до первого события, и на дашборде rate()/increase() даёт «No data»,
# а первый инкремент теряется (rate не может посчитать скачок от несуществующего 0).
for _status in ("done", "failed"):
    DOCUMENTS_PROCESSED.labels(status=_status)
for _result in ("success", "validation_error", "request_error"):
    LLM_EXTRACTIONS.labels(result=_result)
