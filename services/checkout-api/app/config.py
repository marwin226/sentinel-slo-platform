from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


@dataclass(frozen=True)
class Settings:
    service_name: str
    version: str
    build_id: str
    log_level: str
    fault_error_rate: float
    fault_latency_ms: float
    fault_seed: int | None
    otlp_endpoint: str | None


@lru_cache
def get_settings() -> Settings:
    seed = os.getenv("FAULT_SEED")
    return Settings(
        service_name=os.getenv("SERVICE_NAME", "checkout-api"),
        version=os.getenv("APP_VERSION", "dev"),
        build_id=os.getenv("BUILD_ID", "local"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        fault_error_rate=_float("FAULT_ERROR_RATE", 0.0),
        fault_latency_ms=_float("FAULT_LATENCY_MS", 0.0),
        fault_seed=int(seed) if seed else None,
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or None,
    )
