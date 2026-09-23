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
      Module      = "dns"
      ManagedBy   = "terraform"
    },
    var.tags,
  )
}

variable "hosted_zone_id" {
  description = "Route53 hosted zone the records are created in."
  type        = string
  default     = ""
}

variable "domain_name" {
  description = "Domain to point at the distribution."
  type        = string
  default     = ""
}

variable "distribution_domain_name" {
  description = "CloudFront domain the alias record targets."
  type        = string
  default     = ""
}
