terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.69"
    }
  }

  # Remote state with native S3 locking (no DynamoDB table needed on Terraform >= 1.10).
  # Uncomment after creating the bucket once:
  # backend "s3" {
  #   bucket       = "sentinel-tfstate-<account-id>"
  #   key          = "sentinel/eks/terraform.tfstate"
  #   region       = "eu-central-1"
  #   encrypt      = true
  #   use_lockfile = true
  # }
}

provider "aws" {
  region = var.region

  # FinOps: every resource is attributable to a project, environment and owner.
  default_tags {
    tags = {
      Project     = "sentinel-slo-platform"
      Environment = var.environment
      Owner       = var.owner
      ManagedBy   = "terraform"
      CostCenter  = "platform-sre"
    }
  }
}
