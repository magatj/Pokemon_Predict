variable "project" {
  description = "Project name used to prefix resource names."
  type        = string
  default     = "pokemon-vending-forecast"
}

variable "environment" {
  description = "Deployment environment (dev or prod)."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "tags" {
  description = "Tags applied to every resource in this module."
  type        = map(string)
  default     = {}
}

locals {
  name_prefix = "${var.project}-${var.environment}"

  tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      Module      = "ingestion"
      ManagedBy   = "terraform"
    },
    var.tags,
  )
}

variable "ingest_schedule" {
  description = "EventBridge schedule expression, mirroring the GitLab pipeline schedule."
  type        = string
  default     = "rate(30 minutes)"
}

variable "queue_arn" {
  description = "SQS queue raw payloads are handed to for normalization."
  type        = string
}

variable "table_names" {
  description = "DynamoDB tables the ingestion functions may access."
  type        = map(string)
}

variable "reddit_secret_arn" {
  description = "Secrets Manager ARN holding Reddit OAuth credentials. Empty leaves the source SOURCE_SKIPPED."
  type        = string
  default     = ""
}
