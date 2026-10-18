"""RED metrics. Label cardinality is bounded on purpose: route templates, not raw paths."""

from prometheus_client import Counter, Gauge, Histogram

_BASE = ("service", "version", "method")

REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests served, by route template and status code.",
    (*_BASE, "route", "code"),
)

# Buckets bracket the 300ms latency SLO threshold so the SLI is exact at that boundary.
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    (*_BASE, "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 2.5, 5.0),
)

IN_FLIGHT = Gauge("http_requests_in_flight", "In-flight HTTP requests.", _BASE)

BUILD_INFO = Gauge("app_build_info", "Build metadata; always 1.", ("service", "version", "build_id"))
