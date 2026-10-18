#!/usr/bin/env bash
# GitOps release helper for the canary demo. Edits the dev overlay; commit + push and
# Argo CD rolls it out through the SLO-gated canary.
#   scripts/release.sh good 0.2.0          healthy release -> promoted step by step
#   scripts/release.sh bad  0.3.0-bad      15% errors      -> analysis fails, auto-rollback
#   scripts/release.sh slow 0.3.0-slow     +450ms latency  -> p99 gate fails, auto-rollback
set -euo pipefail
KIND="${1:?good|bad|slow}"; VERSION="${2:?version}"
PATCH="$(cd "$(dirname "$0")/.." && pwd)/deploy/checkout-api/overlays/dev/release-patch.yaml"
need() { command -v "$1" >/dev/null || { echo "missing dependency: $1 (https://github.com/mikefarah/yq)" >&2; exit 1; }; }
need yq

case "$KIND" in
  good) ERR=0;    LAT=0 ;;
  bad)  ERR=0.15; LAT=0 ;;
  slow) ERR=0;    LAT=450 ;;
  *) echo "unknown release kind: $KIND" >&2; exit 1 ;;
esac

set_env() { yq -i "(.[] | select(.path == \"/spec/template/spec/containers/0/env/$1/value\")).value = \"$2\"" "$PATCH"; }
set_env 0 "$VERSION"
set_env 1 "$(git rev-parse --short HEAD 2>/dev/null || echo local)"
set_env 2 "$ERR"
set_env 3 "$LAT"
echo "dev overlay now releases version=$VERSION error_rate=$ERR latency_ms=$LAT"
echo "next: git commit -am 'release: $VERSION' && git push   # then: kubectl argo rollouts get rollout checkout-api -n checkout -w"
