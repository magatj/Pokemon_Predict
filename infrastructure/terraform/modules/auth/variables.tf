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
      Module      = "auth"
      ManagedBy   = "terraform"
    },
    var.tags,
  )
}

variable "allow_anonymous_reports" {
  description = "Whether unauthenticated observations are accepted."
  type        = bool
  default     = true
}
