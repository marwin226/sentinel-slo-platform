"""OpenTelemetry tracing. Exports OTLP/HTTP when OTEL_EXPORTER_OTLP_ENDPOINT is set,
otherwise tracing is a no-op so local runs and tests stay dependency-free."""

from __future__ import annotations

import logging

from .config import Settings

log = logging.getLogger(__name__)


def setup_tracing(app, settings: Settings) -> bool:
    if not settings.otlp_endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:  # pragma: no cover - optional dependency
        log.warning("opentelemetry packages missing; tracing disabled")
        return False

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.version,
            # The build id is threaded through every span so a regression can be
            # pinned to the exact commit that introduced it.
            "build.id": settings.build_id,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,readyz,metrics")
    log.info("tracing enabled endpoint=%s", settings.otlp_endpoint)
    return True
