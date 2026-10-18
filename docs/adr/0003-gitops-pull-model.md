# ADR 0003 — GitOps pull model with Argo CD

**Status:** accepted · **Date:** 2026-10-18

## Context
Pushing to clusters from CI (`kubectl apply` with a long-lived kubeconfig secret) gives CI cluster-admin
credentials, allows drift, and makes "what is running?" a question for the cluster instead of for Git.

## Decision
CI never talks to a cluster. It builds, scans, signs and then **commits** the new image tag to the environment
overlay. Argo CD (app-of-apps) pulls and reconciles with `selfHeal` and `prune`. Promotion to prod is a pull
request that copies a tag already proven in dev. Rollback is `git revert`.

## Consequences
+ No cluster credentials in CI; full audit trail in Git history; drift is corrected automatically.
+ The whole platform (Prometheus, Kyverno, Rollouts, Chaos Mesh…) is reproducible from one `kubectl apply`.
− Two-step deploy latency (commit → sync, ~1-3 min) — acceptable, and the canary takes longer anyway.
