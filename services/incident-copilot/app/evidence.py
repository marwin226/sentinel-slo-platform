"""Collects hard evidence from Prometheus *before* any LLM is involved.

The copilot never asks a model to guess numbers: every figure in a report comes
from a PromQL query listed here, and the query text is included in the report so
a human can re-run it.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import httpx

log = logging.getLogger(__name__)


@dataclass
class Signal:
    name: str
    query: str
    # one entry per series: (labels, value)
    series: list[tuple[dict[str, str], float]] = field(default_factory=list)
    error: str | None = None


def queries_for(service: str) -> dict[str, str]:
    s = service.replace('"', "")
    return {
        # `or ... * 0` keeps healthy versions in the result with an explicit 0% error ratio
        "error_ratio_by_version_5m": (
            f'(sum by (version) (rate(http_requests_total{{service="{s}",code=~"5.."}}[5m]))'
            f' or sum by (version) (rate(http_requests_total{{service="{s}"}}[5m])) * 0)'
            f' / sum by (version) (rate(http_requests_total{{service="{s}"}}[5m]))'
        ),
        "p99_latency_seconds_by_version_5m": (
            f'histogram_quantile(0.99, sum by (version, le) (rate(http_request_duration_seconds_bucket{{service="{s}"}}[5m])))'
        ),
        "request_rate_by_version_5m": f'sum by (version) (rate(http_requests_total{{service="{s}"}}[5m]))',
        "burn_rate_1h_by_slo": f'slo:burn_rate:ratio_rate1h{{service="{s}"}}',
        "error_budget_remaining_30d_by_slo": f'slo:error_budget_remaining:ratio{{service="{s}"}}',
    }


class PrometheusClient:
    def __init__(self, base_url: str, timeout: float = 5.0, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport)

    def instant(self, name: str, query: str) -> Signal:
        signal = Signal(name=name, query=query)
        try:
            resp = self._client.get("/api/v1/query", params={"query": query})
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("status") != "success":
                signal.error = payload.get("error", "query failed")
                return signal
            for item in payload["data"]["result"]:
                try:
                    value = float(item["value"][1])
                except (KeyError, ValueError, IndexError):
                    continue
                signal.series.append((item.get("metric", {}), value))
        except httpx.HTTPError as exc:
            log.warning("prometheus query %s failed: %s", name, exc)
            signal.error = str(exc)
        return signal

    def collect(self, service: str) -> list[Signal]:
        return [self.instant(name, q) for name, q in queries_for(service).items()]


def suspect_version(signals: list[Signal]) -> str | None:
    """The version whose error ratio is highest — and meaningfully above its peers."""
    errors = next((s for s in signals if s.name == "error_ratio_by_version_5m"), None)
    if not errors or not errors.series:
        return None
    ranked = sorted(
        ((labels.get("version", "unknown"), v) for labels, v in errors.series if not math.isnan(v)),
        key=lambda x: x[1],
        reverse=True,
    )
    if not ranked or ranked[0][1] <= 0:
        return None
    if len(ranked) == 1 or ranked[0][1] >= 2 * max(ranked[1][1], 0.001):
        return ranked[0][0]
    return None
