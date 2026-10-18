# Cost notes (FinOps)

Rough monthly cost of the **dev** EKS environment in eu-central-1. Prices change: confirm with the AWS Pricing
Calculator before applying.

| Item | Approx. |
|---|---|
| EKS control plane ($0.10/h) | ~$73 |
| 3 × Spot `t3/m5 .large` nodes | ~$45–70 (Spot) vs ~$200 on-demand |
| 1 NAT gateway + data processing | ~$40+ |
| CloudWatch (flow + control-plane logs) | a few $ |

Built-in controls: Spot capacity with 4 instance types (better availability), single NAT in non-prod, `default_tags`
for cost allocation (activate the `Project` tag as a cost allocation tag in Billing), and an AWS Budget alert at
80% forecast / 100% actual. The free path is the kind cluster or `docker compose`.
