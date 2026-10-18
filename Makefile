.DEFAULT_GOAL := help
SHELL := /bin/bash
SERVICES := checkout-api incident-copilot

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install dev dependencies for both services
	@for s in $(SERVICES); do pip install -r services/$$s/requirements-dev.txt; done

lint: ## Ruff lint + format check
	ruff check services && ruff format --check services

test: ## Unit tests with coverage gate
	@for s in $(SERVICES); do (cd services/$$s && pytest -q --cov=app --cov-fail-under=80) || exit 1; done

slo: ## Regenerate Prometheus SLO rules from slo/*.yaml
	python scripts/generate_slo_rules.py

slo-test: ## promtool: validate + unit-test the alerting rules
	python scripts/generate_slo_rules.py --check
	promtool check rules observability/rules/*.yml
	promtool test rules observability/tests/*.test.yml

manifests: ## Render every Kustomize target and validate with kubeconform
	@for d in deploy/checkout-api/overlays/dev deploy/checkout-api/overlays/prod deploy/incident-copilot/base platform/observability; do \
	  kubectl kustomize $$d | kubeconform -strict -summary -kubernetes-version 1.33.0 -schema-location default \
	  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' || exit 1; done

check: lint test slo-test manifests ## Everything CI runs (minus image builds)

demo: ## 5-minute local demo: bad canary -> SLO alert -> AI incident brief (Docker only)
	docker compose up --build -d
	@echo "Waiting ~90s for the burn alert..."; sleep 90
	curl -s localhost:8081/incidents/latest.md || true

demo-down: ## Stop the local demo
	docker compose down -v

cluster: ## Local kind cluster + Argo CD + full platform via GitOps
	scripts/bootstrap.sh kind

bad-release: ## Stage a bad canary (15% errors) in the dev overlay — commit & push to roll it out
	scripts/release.sh bad 0.3.0-bad

good-release: ## Stage a healthy release in the dev overlay
	scripts/release.sh good 0.2.0

tf-plan: ## Terraform plan for the AWS EKS environment
	cd infra/terraform/aws && terraform init && terraform plan

.PHONY: help install lint test slo slo-test manifests check demo demo-down cluster bad-release good-release tf-plan
