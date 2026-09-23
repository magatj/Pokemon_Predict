output "alerts_topic_name" {
  description = "SNS topic alarms publish to."
  value       = "${local.name_prefix}-alerts"
}
