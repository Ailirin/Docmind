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


PROCESS_DURATION = Histogram(
    "docmind_process_duration_seconds",
    "Document processing duration in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)
