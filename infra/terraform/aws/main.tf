locals {
  name = "sentinel-${var.environment}"
  azs  = slice(data.aws_availability_zones.available.names, 0, 3)
}

data "aws_availability_zones" "available" {
  state = "available"
}

# ---------------------------------------------------------------------------
# Network: 3 AZs, private subnets for nodes, public subnets for load balancers.
# One NAT gateway in dev (cost), one per AZ in prod (availability).
# ---------------------------------------------------------------------------
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.16"

  name = local.name
  cidr = var.vpc_cidr
  azs  = local.azs

  private_subnets = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, 48 + i)]

  enable_nat_gateway     = true
  single_nat_gateway     = var.environment != "prod"
  one_nat_gateway_per_az = var.environment == "prod"
  enable_dns_hostnames   = true

  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true
  flow_log_max_aggregation_interval    = 60

  public_subnet_tags  = { "kubernetes.io/role/elb" = 1 }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = 1 }
}

# ---------------------------------------------------------------------------
# EKS: managed control plane, Spot managed node group, EKS Pod Identity,
# control-plane audit logs, secrets envelope-encrypted with KMS (module default).
# ---------------------------------------------------------------------------
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.29"

  cluster_name    = local.name
  cluster_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access       = true
  cluster_endpoint_public_access_cidrs = var.cluster_admin_cidrs

  enable_cluster_creator_admin_permissions = true
  cluster_enabled_log_types                = ["api", "audit", "authenticator"]

  cluster_addons = {
    coredns                = { most_recent = true }
    kube-proxy             = { most_recent = true }
    vpc-cni                = { most_recent = true, before_compute = true }
    eks-pod-identity-agent = { most_recent = true }
  }

  eks_managed_node_groups = {
    workloads = {
      ami_type       = "AL2023_x86_64_STANDARD"
      capacity_type  = "SPOT" # FinOps: ~60-70% cheaper; workloads are stateless and PDB-protected
      instance_types = var.node_instance_types

      min_size     = var.node_capacity.min
      desired_size = var.node_capacity.desired
      max_size     = var.node_capacity.max

      labels = { "sentinel.dev/pool" = "workloads" }

      update_config = { max_unavailable_percentage = 33 }
    }
  }
}

# ---------------------------------------------------------------------------
# FinOps guardrail: a budget that warns before the bill surprises anyone.
# ---------------------------------------------------------------------------
resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = ["user:Project$sentinel-slo-platform"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }
}
