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
      Module      = "database"
      ManagedBy   = "terraform"
    },
    var.tags,
  )
}

variable "billing_mode" {
  description = "DynamoDB billing mode."
  type        = string
  default     = "PAY_PER_REQUEST"
}

variable "point_in_time_recovery" {
  description = "Enable PITR. Observation history cannot be reconstructed, so this stays on in prod."
  type        = bool
  default     = true
}
