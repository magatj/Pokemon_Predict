# Monitoring module
#
# Ingestion must never fail silently, which is the same rule the source-health
# file enforces in the MVP. These alarms are the AWS equivalent.
#
# Planned resources:
#   aws_cloudwatch_log_group.*        - one per function
#   aws_cloudwatch_metric_alarm.ingestion_errors
#   aws_cloudwatch_metric_alarm.dlq_not_empty
#   aws_cloudwatch_metric_alarm.stale_forecasts   - no fresh data in N hours
#   aws_sns_topic.alerts

# Resources are intentionally not declared: the GitLab Pages MVP
# provisions nothing. See infrastructure/terraform/README.md.
