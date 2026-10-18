# Sample incident brief (real output)

Captured on 2026-10-18 from the same components `docker compose up` starts (run as local processes): stable v1.4.0 and a bad canary v1.5.0 (40% injected 5xx) under synthetic load. Prometheus fired the SLO burn alert ~30 s after traffic started; Alertmanager delivered it to the copilot, which produced the brief below from live PromQL results, with no LLM key configured (deterministic mode).

## 🚨 CheckoutAvailabilityBudgetBurnSlow — checkout-api
_severity: ticket · status: firing · brief by: deterministic_

**Impact** `checkout-api` is burning error budget (CheckoutAvailabilityBudgetBurnSlow, ticket).
**Likely cause** Errors are concentrated in version `1.5.0`.
**Recommended next steps**
- Treat version `1.5.0` as the prime suspect: confirm the canary was aborted (`kubectl argo rollouts get rollout checkout-api -n checkout`) or abort it.
- Follow [Runbook: checkout-api error budget burn › Roll back a bad release].
- Follow [Runbook: checkout-api error budget burn › What the alert means].
- Post an update in the incident channel and open a postmortem doc if the budget burn exceeds 2%.
**Confidence** medium — version-scoped error data supports it.

<details><summary>Evidence & queries</summary>

### Alert `CheckoutAvailabilityBudgetBurnSlow` (ticket) on `checkout-api`
Summary: checkout-api is burning its availability error budget too fast (ticket)
Started: 2026-10-18T10:17:54.893Z

### Evidence (Prometheus, instant queries)
- **error_ratio_by_version_5m**: 1.5.0=37.58%, 1.4.0=0.00%
- **p99_latency_seconds_by_version_5m**: 1.4.0=10 ms, 1.5.0=10 ms
- **request_rate_by_version_5m**: 1.4.0=3.53/s, 1.5.0=2.29/s
- **burn_rate_1h_by_slo**: availability=29.6x, latency=0.0x
- **error_budget_remaining_30d_by_slo**: availability=0% (exhausted), latency=100.00%
- **suspect_version**: 1.5.0

### Relevant runbook sections
- [Runbook: checkout-api error budget burn › Roll back a bad release] (checkout-error-budget-burn.md): The canary analysis normally aborts a bad release automatically. If it did not (for example the rollout was already fully promoted): 1. Abort: `kubectl argo rollouts abort checkout-api -n checkout` — traffic returns to the stable ReplicaSet in seconds. 2. Revert the image tag commit in `deploy/checkout-api/overlays/<env>` so Git matches reality, otherwise Argo CD will re-sync the bad version. 3. C
- [Runbook: checkout-api error budget burn › What the alert means] (checkout-error-budget-burn.md): The service is consuming its 30-day error budget faster than sustainable. A fast burn (14.4x over 1h, confirmed over 5m) exhausts ~2% of the monthly budget in one hour and will empty it in ~2 days. A slow burn (6x over 6h) empties it in ~5 days. Users are seeing 5xx errors now.
- [Runbook: checkout-api error budget burn › Communication] (checkout-error-budget-burn.md): Post in #incidents within 10 minutes: impact, suspected cause, next update time. If more than 2% of the monthly budget is burned, a blameless postmortem is required (template: docs/postmortems/TEMPLATE.md).

```promql
# error_ratio_by_version_5m
(sum by (version) (rate(http_requests_total{service="checkout-api",code=~"5.."}[5m])) or sum by (version) (rate(http_requests_total{service="checkout-api"}[5m])) * 0) / sum by (version) (rate(http_requests_total{service="checkout-api"}[5m]))
# p99_latency_seconds_by_version_5m
histogram_quantile(0.99, sum by (version, le) (rate(http_request_duration_seconds_bucket{service="checkout-api"}[5m])))
# request_rate_by_version_5m
sum by (version) (rate(http_requests_total{service="checkout-api"}[5m]))
# burn_rate_1h_by_slo
slo:burn_rate:ratio_rate1h{service="checkout-api"}
# error_budget_remaining_30d_by_slo
slo:error_budget_remaining:ratio{service="checkout-api"}
```
</details>