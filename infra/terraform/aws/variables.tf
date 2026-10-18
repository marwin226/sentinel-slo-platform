variable "region" {
  description = "AWS region. Frankfurt by default (data residency for EU users)."
  type        = string
  default     = "eu-central-1"
}

variable "environment" {
  description = "Environment name, used in resource names and tags."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}

variable "owner" {
  description = "Team or person accountable for this stack (cost allocation tag)."
  type        = string
  default     = "joshil.fernandes"
}

variable "kubernetes_version" {
  description = "EKS control plane version."
  type        = string
  default     = "1.33"
}

variable "vpc_cidr" {
  description = "CIDR for the VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "node_instance_types" {
  description = "Instance types for the Spot node group. Several types = better Spot availability."
  type        = list(string)
  default     = ["t3.large", "t3a.large", "m5.large", "m5a.large"]
}

variable "node_capacity" {
  description = "Min / desired / max nodes in the workload node group."
  type        = object({ min = number, desired = number, max = number })
  default     = { min = 2, desired = 3, max = 6 }
}

variable "monthly_budget_usd" {
  description = "Monthly AWS budget; alerts at 80% forecast and 100% actual."
  type        = number
  default     = 150
}

variable "budget_alert_email" {
  description = "Where budget alerts are sent."
  type        = string
  default     = "joshilfernandes@gmail.com"
}

variable "cluster_admin_cidrs" {
  description = "CIDRs allowed to reach the public EKS API endpoint. Restrict to your IP."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
