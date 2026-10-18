"""checkout-api — a small, production-shaped service that Sentinel deploys and protects.

It exposes RED metrics (Rate, Errors, Duration) labelled with the service version,
OpenTelemetry traces, health probes, and a *fault injection* switch so a "bad
release" can be simulated on demand to prove the SLO-gated canary rolls it back.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field
from starlette.routing import Match

from .config import Settings, get_settings
from .faults import FaultInjector
from .metrics import BUILD_INFO, IN_FLIGHT, REQUEST_LATENCY, REQUESTS
from .telemetry import setup_tracing

settings: Settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
log = logging.getLogger("checkout-api")

app = FastAPI(title="checkout-api", version=settings.version)
faults = FaultInjector(settings.fault_error_rate, settings.fault_latency_ms, settings.fault_seed)
setup_tracing(app, settings)
BUILD_INFO.labels(service=settings.service_name, version=settings.version, build_id=settings.build_id).set(1)

CATALOG = {
    "sku-espresso": {"name": "Espresso beans 1kg", "price_eur": 24.90},
    "sku-grinder": {"name": "Burr grinder", "price_eur": 129.00},
    "sku-kettle": {"name": "Gooseneck kettle", "price_eur": 59.50},
}

# Probe/metrics endpoints are excluded from the SLI: they are not user journeys.
_UNMEASURED = {"/metrics", "/healthz", "/readyz"}


def _route_template(request: Request) -> str:
    """Resolve the route *template* (e.g. /api/v1/checkout) to keep label cardinality bounded.
    Works even when the handler never ran (injected faults short-circuit before routing)."""
    route = request.scope.get("route")
    if route is not None:
        return getattr(route, "path", "unmatched")
    for candidate in app.router.routes:
        match, _ = candidate.matches(request.scope)
        if match == Match.FULL:
            return getattr(candidate, "path", "unmatched")
    return "unmatched"


@app.middleware("http")
async def red_metrics(request: Request, call_next):
    if request.url.path in _UNMEASURED:
        return await call_next(request)

    labels = {"service": settings.service_name, "version": settings.version, "method": request.method}
    IN_FLIGHT.labels(**labels).inc()
    start = time.perf_counter()
    status = 500
    try:
        # Fault injection happens *inside* the measured window so the SLI sees it,
        # exactly like a real regression would be seen.
        delay = faults.latency_seconds()
        if delay:
            await asyncio.sleep(delay)
        if faults.should_fail():
            status = 503
            return Response('{"detail":"injected fault"}', status_code=503, media_type="application/json")
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route_path = _route_template(request)
        elapsed = time.perf_counter() - start
        REQUESTS.labels(**labels, route=route_path, code=str(status)).inc()
        REQUEST_LATENCY.labels(**labels, route=route_path).observe(elapsed)
        IN_FLIGHT.labels(**labels).dec()


class CheckoutItem(BaseModel):
    sku: str
    quantity: int = Field(ge=1, le=20)


class CheckoutRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    items: list[CheckoutItem] = Field(min_length=1, max_length=50)


class CheckoutResponse(BaseModel):
    order_id: str
    total_eur: float
    version: str


@app.get("/healthz")
def healthz() -> dict:
    """Liveness: the process is up. Never depends on downstreams."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict:
    """Readiness: safe to receive traffic."""
    return {"status": "ready", "version": settings.version}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/products")
def list_products() -> dict:
    return {"products": [{"sku": k, **v} for k, v in CATALOG.items()]}


@app.post("/api/v1/checkout", response_model=CheckoutResponse)
def checkout(req: CheckoutRequest) -> CheckoutResponse:
    total = 0.0
    for item in req.items:
        product = CATALOG.get(item.sku)
        if product is None:
            # 4xx is the *client's* fault and does not burn the error budget.
            raise HTTPException(status_code=422, detail=f"unknown sku {item.sku}")
        total += product["price_eur"] * item.quantity
    order_id = f"ord_{uuid.uuid4().hex[:12]}"
    log.info("order placed order_id=%s items=%d", order_id, len(req.items))
    return CheckoutResponse(order_id=order_id, total_eur=round(total, 2), version=settings.version)
