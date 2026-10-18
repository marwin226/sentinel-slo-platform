# Security model

| Layer | Control |
|---|---|
| Source | CODEOWNERS (enable branch protection on `main`), PR template with reliability checklist, Dependabot for actions/pip/docker/terraform |
| Build | Minimal multi-stage images, non-root UID 10001, no shell entrypoint; hadolint |
| Supply chain | Trivy (fail on fixable CRITICAL, SARIF to code scanning), BuildKit SBOM + SLSA provenance (`mode=max`), cosign **keyless** signing via GitHub OIDC (no keys to leak) |
| Admission | Kyverno: resources required, no `:latest`, `runAsNonRoot`, no privilege escalation, probes required, cosign signature verification for `ghcr.io/joshilfernandes/sentinel-*` (Audit by default so side-loaded kind images run; set `validationFailureAction: Enforce` on production clusters) |
| Runtime | `readOnlyRootFilesystem`, all capabilities dropped, `RuntimeDefault` seccomp, no service-account token automount, default-deny ingress NetworkPolicies |
| Cloud | Private node subnets, VPC flow logs, EKS audit logs, restricted API endpoint CIDRs, IaC scanned by Checkov + tflint |
| CI | Least-privilege `permissions:` per job; no cluster credentials in CI (GitOps pull model) |
| AI | Copilot is read-only, receives only metrics + runbooks (no customer data), LLM key optional and stored as a Kubernetes Secret |
