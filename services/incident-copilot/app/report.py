"""Turns an Alertmanager alert + evidence + runbook hits into an incident brief."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .evidence import Signal
from .runbooks import Hit


@dataclass
class Incident:
    fingerprint: str
    alertname: str
    service: str
    severity: str
    status: str
    started_at: str
    summary: str
    signals: list[Signal] = field(default_factory=list)
    runbook_hits: list[Hit] = field(default_factory=list)
    suspect_version: str | None = None
    brief: str = ""
    brief_source: str = "deterministic"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {
            "fingerprint": self.fingerprint,
            "alertname": self.alertname,
            "service": self.service,
            "severity": self.severity,
            "status": self.status,
            "started_at": self.started_at,
            "suspect_version": self.suspect_version,
            "brief_source": self.brief_source,
            "brief": self.brief,
            "runbooks": [{"source": h.chunk.source, "section": h.chunk.heading, "score": h.score} for h in self.runbook_hits],
            "evidence": [
                {
                    "name": s.name,
                    "query": s.query,
                    "error": s.error,
                    "series": [{"labels": lbl, "value": v} for lbl, v in s.series],
                }
                for s in self.signals
            ],
            "created_at": self.created_at,
        }


def _fmt(name: str, value: float) -> str:
    if math.isnan(value):
        return "n/a"
    if "remaining" in name and value <= 0:
        return "0% (exhausted)"
    if "ratio" in name or "remaining" in name:
        return f"{value * 100:.2f}%"
    if "seconds" in name:
        return f"{value * 1000:.0f} ms"
    if "burn_rate" in name:
        return f"{value:.1f}x"
    return f"{value:.2f}/s"


def evidence_markdown(inc: Incident) -> str:
    lines = [
        f"### Alert `{inc.alertname}` ({inc.severity}) on `{inc.service}`",
        f"Summary: {inc.summary}",
        f"Started: {inc.started_at}",
        "",
        "### Evidence (Prometheus, instant queries)",
    ]
    for s in inc.signals:
        if s.error:
            lines.append(f"- **{s.name}**: query failed ({s.error})")
            continue
        if not s.series:
            lines.append(f"- **{s.name}**: no data")
            continue
        parts = ", ".join(
            f"{lbl.get('version') or lbl.get('slo') or lbl.get('service', 'all')}={_fmt(s.name, v)}" for lbl, v in s.series
        )
        lines.append(f"- **{s.name}**: {parts}")
    lines.append(f"- **suspect_version**: {inc.suspect_version or 'none identified'}")
    lines += ["", "### Relevant runbook sections"]
    for h in inc.runbook_hits:
        snippet = " ".join(h.chunk.text.split())[:400]
        lines.append(f"- [{h.chunk.heading}] ({h.chunk.source}): {snippet}")
    if not inc.runbook_hits:
        lines.append("- none matched")
    return "\n".join(lines)


def deterministic_brief(inc: Incident) -> str:
    steps = []
    if inc.suspect_version:
        steps.append(
            f"Treat version `{inc.suspect_version}` as the prime suspect: confirm the canary was "
            "aborted (`kubectl argo rollouts get rollout checkout-api -n checkout`) or abort it."
        )
    for h in inc.runbook_hits[:2]:
        steps.append(f"Follow [{h.chunk.heading}].")
    steps.append("Post an update in the incident channel and open a postmortem doc if the budget burn exceeds 2%.")
    cause = (
        f"Errors are concentrated in version `{inc.suspect_version}`."
        if inc.suspect_version
        else "No single version stands out; suspect a shared dependency or infra."
    )
    return "\n".join(
        [
            f"**Impact** `{inc.service}` is burning error budget ({inc.alertname}, {inc.severity}).",
            f"**Likely cause** {cause}",
            "**Recommended next steps**",
            *[f"- {s}" for s in steps],
            "**Confidence** "
            + (
                "medium — version-scoped error data supports it."
                if inc.suspect_version
                else "low — evidence does not isolate a cause."
            ),
        ]
    )


def render_markdown(inc: Incident) -> str:
    return "\n".join(
        [
            f"## 🚨 {inc.alertname} — {inc.service}",
            f"_severity: {inc.severity} · status: {inc.status} · brief by: {inc.brief_source}_",
            "",
            inc.brief,
            "",
            "<details><summary>Evidence & queries</summary>",
            "",
            evidence_markdown(inc),
            "",
            "```promql",
            *[f"# {s.name}\n{s.query}" for s in inc.signals],
            "```",
            "</details>",
        ]
    )
