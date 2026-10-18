# Runbook: checkout-api latency SLO

Alerts: `CheckoutLatencyBudgetBurnFast`, `CheckoutLatencyBudgetBurnSlow`.
SLO: 99% of checkout-api requests complete in under 300 ms over 30 days.

## What the alert means
Too many requests are slower than 300 ms. Latency regressions are usually caused by a new
release (an N+1 query, a missing cache), CPU throttling, or a slow downstream.

## Triage latency
1. Compare p99 by version: `histogram_quantile(0.99, sum by (version, le) (rate(http_request_duration_seconds_bucket{service="checkout-api"}[5m])))`.
2. If only the newest version is slow, treat it as a bad release and abort the rollout (see the error budget runbook, "Roll back a bad release").
3. Check CPU throttling: `rate(container_cpu_cfs_throttled_periods_total{namespace="checkout"}[5m])`. If high, the CPU limit is too tight; raise it in the base Rollout and sync.
4. Open a trace for a slow request in Grafana Tempo and find the longest span.

## Network latency injected by chaos
A `NetworkChaos` latency experiment adds delay to every packet. List them with
`kubectl get networkchaos -A` and delete the experiment to stop it immediately.
