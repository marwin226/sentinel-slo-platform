# Game day GD-001 — does a bad release get detected and explained?

**Date:** 2026-10-18 · **Environment:** local stack (same components as `docker compose up`)

## Hypothesis
A release that returns 5xx for a large share of its requests will (a) trigger the fast-burn page within 5
minutes, (b) be identified as the suspect version by the incident copilot, and (c) the copilot will point the
responder at the rollback procedure first.

## Method
- Stable `checkout-api` v1.4.0 at ~6 req/s; canary v1.5.0 with `FAULT_ERROR_RATE=0.4` at ~4 req/s (60/40 split).
- Prometheus 3.5.0 evaluating the generated SLO rules every 15 s; Alertmanager 0.28.1 → copilot webhook.
- No LLM key: deterministic brief mode.

## Results
| Expectation | Observed | Pass |
|---|---|---|
| Fast-burn page < 5 min | `CheckoutAvailabilityBudgetBurnFast` firing ~30 s after load started (1h burn 33.8x) | ✅ |
| Copilot names the bad version | suspect `1.5.0` (37.6% errors vs 0.00% for 1.4.0) | ✅ |
| Rollback procedure ranked first | first iteration ranked "What the alert means" first | ❌ → fixed |
| Rollback procedure ranked first (re-run) | "Roll back a bad release" ranked first | ✅ |
| Canary gate would abort | gate PromQL: canary burn 69x (limit 2x); stable passes | ✅ |

Output: [sample incident brief](../demo/sample-incident-brief.md).

## Findings & fixes
1. **Healthy versions were missing from the error-ratio evidence** (a ratio with no 5xx series returns nothing),
   making the brief look one-sided. Fixed with `(errors or total * 0) / total` so healthy versions show 0.00%.
2. **Lexical retrieval picked the explanatory section over the action.** Fixed with two-stage retrieval
   (the evidence decides intent — "bad release" vs "shared dependency" — then BM25 finds the text), light
   stemming, and heading boosting. Covered by a unit test so it cannot regress.
3. With only minutes of data, the 30-day "budget remaining" goes deeply negative; it is now rendered as
   "0% (exhausted)" instead of a confusing -3000%.

## Next game day
GD-002 on the kind cluster: Chaos Mesh pod-kill schedule (`platform/chaos/game-day.yaml`, H1) — expectation:
zero SLO impact thanks to readiness probes, preStop drain and the PDB.
