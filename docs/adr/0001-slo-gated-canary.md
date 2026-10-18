# ADR 0001 — Error budget, not a static threshold, gates releases

**Status:** accepted · **Date:** 2026-10-18

## Context
Canary analysis is often written as "error rate < 1%". That number is arbitrary, disconnected from what users
were promised, and silently wrong when the SLO changes.

## Decision
The canary gate is expressed as an **error-budget burn rate**: the canary's 5xx ratio divided by the budget
(1 − 0.995). A canary may burn at most **2x** the sustainable rate; p99 latency must stay under the 300 ms SLO
threshold. Every query is scoped to the canary's `rollouts_pod_template_hash` (relabelled onto metrics by the
PodMonitor) so stable traffic can never dilute a bad build. Analysis runs in the background for the whole rollout
with `failureLimit: 1` (two bad 30 s measurements abort).

## Consequences
+ One number (the SLO) drives alerting, release safety and dashboards.
+ A bad build is aborted after roughly one minute of exposure at 25% weight.
− Low-traffic services produce noisy ratios; the `canary-has-traffic` metric guards against judging on no data.
− Replica-ratio traffic splitting is approximate; Gateway API weighted routing is on the roadmap.
