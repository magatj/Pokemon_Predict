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
      Module      = "monitoring"
      ManagedBy   = "terraform"
    },
    var.tags,
  )
}

variable "alert_email" {
  description = "Address subscribed to the alert topic."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch log retention."
  type        = number
  default     = 30
}

variable "stale_forecast_hours" {
  description = "Hours without fresh forecast output before alarming."
  type        = number
  default     = 6
}
