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
      Module      = "api"
      ManagedBy   = "terraform"
    },
    var.tags,
  )
}

variable "compute" {
  description = "Which compute backs the API."
  type        = string
  default     = "lambda"

  validation {
    condition     = contains(["lambda", "app_runner"], var.compute)
    error_message = "compute must be lambda or app_runner."
  }
}

variable "observations_table_name" {
  description = "DynamoDB table the API writes observations to."
  type        = string
}

variable "cognito_user_pool_arn" {
  description = "Cognito pool used to authorise reporting; empty allows anonymous."
  type        = string
  default     = ""
}
