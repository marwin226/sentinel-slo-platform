from pathlib import Path

import httpx

from app.evidence import PrometheusClient, Signal, queries_for, suspect_version
from app.llm import LLMClient
from app.main import Alert, Copilot
from app.report import render_markdown
from app.runbooks import BM25Index, load_chunks

RUNBOOKS = Path(__file__).resolve().parents[3] / "docs" / "runbooks"


def fake_prometheus(request: httpx.Request) -> httpx.Response:
    q = request.url.params["query"]
    if 'code=~"5.."' in q and "by (version)" in q:
        result = [
            {"metric": {"version": "v1.4.0"}, "value": [0, "0.001"]},
            {"metric": {"version": "v1.5.0"}, "value": [0, "0.21"]},
        ]
    elif "histogram_quantile" in q:
        result = [
            {"metric": {"version": "v1.4.0"}, "value": [0, "0.08"]},
            {"metric": {"version": "v1.5.0"}, "value": [0, "0.09"]},
        ]
    elif "burn_rate" in q:
        result = [{"metric": {"service": "checkout-api", "slo": "availability"}, "value": [0, "18.7"]}]
    else:
        result = []
    return httpx.Response(200, json={"status": "success", "data": {"resultType": "vector", "result": result}})


def make_copilot(llm_transport=None, api_key=None) -> Copilot:
    return Copilot(
        prom=PrometheusClient("http://prom", transport=httpx.MockTransport(fake_prometheus)),
        llm=LLMClient("http://llm", api_key=api_key, model="test-model", transport=llm_transport),
        index=BM25Index(load_chunks(RUNBOOKS)),
    )


ALERT = Alert(
    status="firing",
    labels={"alertname": "CheckoutAvailabilityBudgetBurnFast", "service": "checkout-api", "severity": "page"},
    annotations={"summary": "checkout-api is burning its availability error budget 14.4x too fast"},
    startsAt="2026-10-18T10:00:00Z",
    fingerprint="abc123",
)


def test_runbook_chunks_load():
    chunks = load_chunks(RUNBOOKS)
    assert len(chunks) >= 8
    assert any("Roll back a bad release" in c.heading for c in chunks)


def test_bm25_finds_rollback_procedure():
    index = BM25Index(load_chunks(RUNBOOKS))
    hits = index.search("bad release rollback canary abort", k=2)
    assert "Roll back a bad release" in hits[0].chunk.heading


def test_bm25_finds_crashloop():
    index = BM25Index(load_chunks(RUNBOOKS))
    assert "crash" in index.search("OOMKilled exit code 137", k=1)[0].chunk.heading.lower()


def test_suspect_version_identifies_outlier():
    s = Signal("error_ratio_by_version_5m", "q", [({"version": "v1"}, 0.001), ({"version": "v2"}, 0.2)])
    assert suspect_version([s]) == "v2"


def test_suspect_version_none_when_uniform():
    s = Signal("error_ratio_by_version_5m", "q", [({"version": "v1"}, 0.1), ({"version": "v2"}, 0.11)])
    assert suspect_version([s]) is None


def test_queries_are_escaped():
    assert '"' not in queries_for('evil"svc')["request_rate_by_version_5m"].split('service="')[1].split('"}')[0]


def test_deterministic_brief_without_llm():
    inc = make_copilot().handle(ALERT)
    assert inc.suspect_version == "v1.5.0"
    assert inc.brief_source == "deterministic"
    assert "v1.5.0" in inc.brief
    assert "Roll back a bad release" in inc.runbook_hits[0].chunk.heading
    md = render_markdown(inc)
    assert "21.00%" in md and "18.7x" in md and "```promql" in md


def test_llm_brief_used_when_available():
    seen = {}

    def llm(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "**Impact** test brief"}}]})

    inc = make_copilot(httpx.MockTransport(llm), api_key="k").handle(ALERT)
    assert inc.brief_source == "llm:test-model"
    assert inc.brief == "**Impact** test brief"
    # evidence, not guesses, is what the model receives
    assert "v1.5.0=21.00%" in seen["body"]


def test_llm_failure_falls_back():
    inc = make_copilot(httpx.MockTransport(lambda r: httpx.Response(500)), api_key="k").handle(ALERT)
    assert inc.brief_source == "deterministic"


def test_resolved_alert_updates_status():
    cp = make_copilot()
    cp.handle(ALERT)
    resolved = cp.handle(ALERT.model_copy(update={"status": "resolved"}))
    assert resolved.status == "resolved"
    assert len(cp.incidents()) == 1


def test_prometheus_down_is_reported_not_raised():
    def down(request):
        raise httpx.ConnectError("refused")

    cp = Copilot(
        PrometheusClient("http://prom", transport=httpx.MockTransport(down)),
        LLMClient("http://llm", None, "m"),
        BM25Index(load_chunks(RUNBOOKS)),
    )
    inc = cp.handle(ALERT)
    assert all(s.error for s in inc.signals)
    assert "low" in inc.brief
