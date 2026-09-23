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
      Module      = "queues"
      ManagedBy   = "terraform"
    },
    var.tags,
  )
}

variable "max_receive_count" {
  description = "Deliveries before a message is moved to the dead-letter queue."
  type        = number
  default     = 5
}

variable "visibility_timeout_seconds" {
  description = "Must exceed the normalization function timeout."
  type        = number
  default     = 120
}
