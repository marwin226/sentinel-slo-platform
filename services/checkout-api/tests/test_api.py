import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app import main
from app.faults import FaultInjector


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "faults", FaultInjector())
    return TestClient(main.app)


def _count(route: str, code: str) -> float:
    value = REGISTRY.get_sample_value(
        "http_requests_total",
        {
            "service": "checkout-api",
            "version": main.settings.version,
            "method": "POST" if "checkout" in route else "GET",
            "route": route,
            "code": code,
        },
    )
    return value or 0.0


def test_probes(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").status_code == 200


def test_products(client):
    body = client.get("/api/v1/products").json()
    assert {p["sku"] for p in body["products"]} == {"sku-espresso", "sku-grinder", "sku-kettle"}


def test_checkout_totals(client):
    resp = client.post(
        "/api/v1/checkout",
        json={"customer_id": "c1", "items": [{"sku": "sku-espresso", "quantity": 2}, {"sku": "sku-kettle", "quantity": 1}]},
    )
    assert resp.status_code == 200
    assert resp.json()["total_eur"] == 109.30
    assert resp.json()["order_id"].startswith("ord_")


def test_unknown_sku_is_client_error(client):
    resp = client.post("/api/v1/checkout", json={"customer_id": "c1", "items": [{"sku": "nope", "quantity": 1}]})
    assert resp.status_code == 422


def test_validation(client):
    resp = client.post("/api/v1/checkout", json={"customer_id": "c1", "items": [{"sku": "sku-kettle", "quantity": 99}]})
    assert resp.status_code == 422


def test_metrics_recorded_with_route_template(client):
    before = _count("/api/v1/products", "200")
    client.get("/api/v1/products")
    assert _count("/api/v1/products", "200") == before + 1


def test_probes_do_not_pollute_sli(client):
    client.get("/healthz")
    assert (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"service": "checkout-api", "version": main.settings.version, "method": "GET", "route": "/healthz", "code": "200"},
        )
        is None
    )


def test_injected_fault_is_measured_as_5xx(monkeypatch):
    monkeypatch.setattr(main, "faults", FaultInjector(error_rate=1.0))
    client = TestClient(main.app)
    before = _count("/api/v1/checkout", "503")
    resp = client.post("/api/v1/checkout", json={"customer_id": "c1", "items": [{"sku": "sku-kettle", "quantity": 1}]})
    assert resp.status_code == 503
    # route template resolved even though the handler never ran
    assert _count("/api/v1/checkout", "503") == before + 1


def test_metrics_endpoint_exposes_build_info(client):
    text = client.get("/metrics").text
    assert "app_build_info" in text
    assert "http_request_duration_seconds_bucket" in text
