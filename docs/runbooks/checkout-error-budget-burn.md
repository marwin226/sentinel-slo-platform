# Runbook: checkout-api error budget burn

Alerts: `CheckoutAvailabilityBudgetBurnFast` (page), `CheckoutAvailabilityBudgetBurnSlow` (ticket).
SLO: 99.5% of checkout-api requests succeed (non-5xx) over 30 days → 0.5% error budget (~3h 36m of full outage).

## What the alert means
The service is consuming its 30-day error budget faster than sustainable. A fast burn
(14.4x over 1h, confirmed over 5m) exhausts ~2% of the monthly budget in one hour and will
empty it in ~2 days. A slow burn (6x over 6h) empties it in ~5 days. Users are seeing 5xx errors now.

## Triage in the first 5 minutes
1. Check whether a rollout is in progress: `kubectl argo rollouts get rollout checkout-api -n checkout`.
2. Compare error ratio by version in Grafana (dashboard "Sentinel / checkout-api SLO") or with
   `sum by (version) (rate(http_requests_total{service="checkout-api",code=~"5.."}[5m])) / sum by (version) (rate(http_requests_total{service="checkout-api"}[5m]))`.
3. If errors are concentrated in the newest version, it is a bad release: go to "Roll back a bad release".
4. If all versions are erroring equally, suspect a dependency, node or network problem: go to "Shared dependency failure".

## Roll back a bad release
The canary analysis normally aborts a bad release automatically. If it did not (for example the
rollout was already fully promoted):
1. Abort: `kubectl argo rollouts abort checkout-api -n checkout` — traffic returns to the stable ReplicaSet in seconds.
2. Revert the image tag commit in `deploy/checkout-api/overlays/<env>` so Git matches reality, otherwise Argo CD will re-sync the bad version.
3. Confirm the error ratio drops below 0.5% within 5 minutes.
Never hot-patch the live Rollout object with kubectl edit; Git is the source of truth.

## Shared dependency failure
1. Check pod restarts and node pressure: `kubectl get pods -n checkout -o wide`, `kubectl top nodes`.
2. Check for active chaos experiments: `kubectl get podchaos,networkchaos,stresschaos -A`. Pause any that are running.
3. Scale out if saturation is the cause: raise `replicas` in the overlay and let Argo CD sync.

## Communication
Post in #incidents within 10 minutes: impact, suspected cause, next update time. If more than 2% of
the monthly budget is burned, a blameless postmortem is required (template: docs/postmortems/TEMPLATE.md).
