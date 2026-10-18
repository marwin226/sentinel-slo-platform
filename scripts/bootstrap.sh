#!/usr/bin/env bash
# Bootstrap a cluster into GitOps: install Argo CD, point it at this repo, done.
# Usage: scripts/bootstrap.sh [kind|current]
#   kind     create a local kind cluster first and side-load locally built images (default)
#   current  use the current kubectl context (e.g. EKS after `terraform apply`)
set -euo pipefail

MODE="${1:-kind}"
ARGOCD_CHART_VERSION="10.7.1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

need() { command -v "$1" >/dev/null || { echo "missing dependency: $1" >&2; exit 1; }; }
need kubectl; need helm

if [[ "$MODE" == "kind" ]]; then
  need kind; need docker
  kind get clusters | grep -qx sentinel || kind create cluster --config "$ROOT/infra/kind/kind-config.yaml"
  echo "==> building images and loading them into kind (no registry needed)"
  docker build -t ghcr.io/joshilfernandes/sentinel-checkout-api:0.1.0 "$ROOT/services/checkout-api"
  docker build -t ghcr.io/joshilfernandes/sentinel-incident-copilot:0.1.0 -f "$ROOT/services/incident-copilot/Dockerfile" "$ROOT"
  kind load docker-image --name sentinel \
    ghcr.io/joshilfernandes/sentinel-checkout-api:0.1.0 \
    ghcr.io/joshilfernandes/sentinel-incident-copilot:0.1.0
fi

echo "==> installing Argo CD ${ARGOCD_CHART_VERSION}"
helm repo add argo https://argoproj.github.io/argo-helm >/dev/null
helm repo update argo >/dev/null
helm upgrade --install argocd argo/argo-cd --version "$ARGOCD_CHART_VERSION" \
  --namespace argocd --create-namespace --wait \
  --set configs.params."server\.insecure"=true

echo "==> handing the cluster over to Git (app-of-apps)"
kubectl apply -f "$ROOT/platform/argocd/root-app.yaml"

cat <<MSG

Sentinel is bootstrapping. Watch it converge:
  kubectl get applications -n argocd -w
Argo CD UI:   kubectl -n argocd port-forward svc/argocd-server 8080:80
              password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
Grafana:      kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80   (admin / sentinel-demo)
Rollouts UI:  kubectl -n argo-rollouts port-forward svc/argo-rollouts-dashboard 3100:3100
MSG
