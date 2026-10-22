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
    ["result"],
)

PROCESS_DURATION = Histogram(
    "docmind_process_duration_seconds",
    "Document processing duration in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)

EXTRACTOR_FALLBACK_TOTAL = Counter(
    "docmind_extractor_fallback_total",
    "Number of times the regex fallback extractor was used instead of LLM",
)
