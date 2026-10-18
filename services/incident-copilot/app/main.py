"""incident-copilot — Alertmanager webhook receiver that writes the first-responder brief.

Flow: Alertmanager ──webhook──▶ copilot ──PromQL──▶ Prometheus (hard evidence)
                                       └─BM25──▶ runbooks (procedure)
                                       └─LLM (optional)──▶ brief ──▶ Slack / GitHub issue / API

Design rule: the copilot is *read-only*. It recommends; humans (or the SLO-gated
canary) act. That keeps an LLM out of the blast radius of production changes.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections import OrderedDict
from threading import Lock

from fastapi import BackgroundTasks, FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

from .evidence import PrometheusClient, suspect_version
from .llm import LLMClient
from .report import Incident, deterministic_brief, evidence_markdown, render_markdown
from .runbooks import BM25Index, load_chunks
from .sinks import open_github_issue, post_slack

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("incident-copilot")

INCIDENTS = Counter("copilot_incidents_total", "Incident briefs produced.", ("alertname", "brief_source"))
BRIEF_LATENCY = Histogram("copilot_brief_seconds", "Time from webhook to finished brief.", buckets=(0.1, 0.5, 1, 2, 5, 10, 30))


class Alert(BaseModel):
    status: str
    labels: dict[str, str]
    annotations: dict[str, str] = {}
    startsAt: str = ""
    fingerprint: str = ""


class AlertmanagerPayload(BaseModel):
    version: str = "4"
    status: str
    alerts: list[Alert]


def _split_camel(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name)


class Copilot:
    def __init__(self, prom: PrometheusClient, llm: LLMClient, index: BM25Index, max_incidents: int = 200):
        self.prom, self.llm, self.index = prom, llm, index
        self._incidents: OrderedDict[str, Incident] = OrderedDict()
        self._lock = Lock()
        self._max = max_incidents

    def handle(self, alert: Alert) -> Incident:
        start = time.perf_counter()
        labels = alert.labels
        service = labels.get("service", labels.get("job", "unknown"))
        fp = alert.fingerprint or f"{labels.get('alertname')}:{service}"

        if alert.status == "resolved":
            with self._lock:
                if fp in self._incidents:
                    self._incidents[fp].status = "resolved"
                    return self._incidents[fp]

        inc = Incident(
            fingerprint=fp,
            alertname=labels.get("alertname", "unknown"),
            service=service,
            severity=labels.get("severity", "unknown"),
            status=alert.status,
            started_at=alert.startsAt,
            summary=alert.annotations.get("summary", alert.annotations.get("description", "")),
        )
        inc.signals = self.prom.collect(service)
        inc.suspect_version = suspect_version(inc.signals)
        inc.runbook_hits = self._retrieve(inc, alert)

        text, _ = self.llm.summarise(evidence_markdown(inc))
        inc.brief, inc.brief_source = (text, f"llm:{self.llm.model}") if text else (deterministic_brief(inc), "deterministic")

        with self._lock:
            self._incidents[fp] = inc
            self._incidents.move_to_end(fp)
            while len(self._incidents) > self._max:
                self._incidents.popitem(last=False)

        INCIDENTS.labels(inc.alertname, inc.brief_source.split(":")[0]).inc()
        BRIEF_LATENCY.observe(time.perf_counter() - start)
        log.info(
            "brief ready alert=%s service=%s suspect=%s source=%s",
            inc.alertname,
            inc.service,
            inc.suspect_version,
            inc.brief_source,
        )
        return inc

    def _retrieve(self, inc: Incident, alert: Alert, k: int = 3) -> list:
        """Two-stage retrieval: the *action* procedure implied by the evidence first,
        then sections matching the alert itself. Evidence decides intent; BM25 finds the text."""
        action = (
            "bad release roll back abort canary newest version"
            if inc.suspect_version
            else "shared dependency failure node pressure network"
        )
        about = " ".join([_split_camel(inc.alertname), inc.summary, alert.annotations.get("runbook_hint", "")])
        hits, seen = [], set()
        for hit in self.index.search(action, k=1) + self.index.search(about, k=k):
            key = (hit.chunk.source, hit.chunk.heading)
            if key not in seen:
                seen.add(key)
                hits.append(hit)
        return hits[:k]

    def incidents(self) -> list[Incident]:
        with self._lock:
            return list(reversed(self._incidents.values()))


def build_copilot() -> Copilot:
    return Copilot(
        prom=PrometheusClient(os.getenv("PROMETHEUS_URL", "http://localhost:9090")),
        llm=LLMClient(
            base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=os.getenv("LLM_API_KEY") or None,
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        ),
        index=BM25Index(load_chunks(os.getenv("RUNBOOK_DIR", "docs/runbooks"))),
    )


app = FastAPI(title="incident-copilot")
copilot = build_copilot()


def _process(payload: AlertmanagerPayload) -> None:
    for alert in payload.alerts:
        try:
            inc = copilot.handle(alert)
        except Exception:
            log.exception("failed to handle alert %s", alert.labels.get("alertname"))
            continue
        if inc.status != "firing":
            continue
        md = render_markdown(inc)
        post_slack(os.getenv("SLACK_WEBHOOK_URL"), md)
        url = open_github_issue(
            os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY"), f"[incident] {inc.alertname} on {inc.service}", md
        )
        if url:
            log.info("opened issue %s", url)


@app.post("/webhook/alertmanager", status_code=202)
def alertmanager_webhook(payload: AlertmanagerPayload, background: BackgroundTasks) -> dict:
    # Ack immediately; Alertmanager retries on slow receivers.
    background.add_task(_process, payload)
    return {"accepted": len(payload.alerts)}


@app.get("/incidents")
def list_incidents() -> dict:
    return {"incidents": [i.to_dict() for i in copilot.incidents()]}


@app.get("/incidents/latest.md")
def latest_markdown() -> Response:
    items = copilot.incidents()
    body = render_markdown(items[0]) if items else "_no incidents yet_"
    return Response(body, media_type="text/markdown")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "llm": copilot.llm.enabled, "runbook_chunks": len(copilot.index.chunks)}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
