variable "project" {
  description = "Project name used to prefix resource names."
  type        = string
  default     = "pokemon-vending-forecast"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "prod"
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-west-2"
}

variable "ingest_schedule" {
  description = "EventBridge schedule for the ingestion functions."
  type        = string
  default     = "rate(30 minutes)"
}

variable "domain_name" {
  description = "Optional custom domain."
  type        = string
  default     = ""
}

variable "hosted_zone_id" {
  description = "Route53 hosted zone id when a custom domain is used."
  type        = string
  default     = ""
}

variable "alert_email" {
  description = "Address subscribed to CloudWatch alerts."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Extra tags applied to every resource."
  type        = map(string)
  default     = {}
}
