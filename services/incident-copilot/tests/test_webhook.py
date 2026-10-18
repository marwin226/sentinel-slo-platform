from fastapi.testclient import TestClient

from app import main


def test_webhook_accepts_alertmanager_v4_payload(monkeypatch):
    handled = []
    monkeypatch.setattr(main.copilot, "handle", lambda a: handled.append(a) or _Stub())
    client = TestClient(main.app)
    payload = {
        "version": "4",
        "status": "firing",
        "receiver": "copilot",
        "groupLabels": {},
        "commonLabels": {},
        "commonAnnotations": {},
        "externalURL": "http://am",
        "groupKey": "{}",
        "truncatedAlerts": 0,
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "X", "service": "checkout-api"},
                "annotations": {},
                "startsAt": "2026-10-18T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "",
                "fingerprint": "f1",
            }
        ],
    }
    resp = client.post("/webhook/alertmanager", json=payload)
    assert resp.status_code == 202 and resp.json() == {"accepted": 1}
    assert handled and handled[0].fingerprint == "f1"


def test_health_reports_runbooks():
    body = TestClient(main.app).get("/healthz").json()
    assert body["status"] == "ok" and body["runbook_chunks"] > 0


class _Stub:
    status = "resolved"
