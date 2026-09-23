# Ingestion module
#
# EventBridge schedules the same jobs that GitLab CI runs today. The handler is
# a thin wrapper over pokevend.jobs; no source adapter changes.
#
# Planned resources:
#   aws_lambda_function.refresh_machines
#   aws_lambda_function.collect_observations
#   aws_lambda_function.normalize          - triggered from SQS
#   aws_lambda_function.build_forecasts
#   aws_cloudwatch_event_rule.schedule     - cron, see ingest_schedule
#   aws_cloudwatch_event_target.*
#   aws_iam_role.ingestion                 - DynamoDB + SQS access

# Resources are intentionally not declared: the GitLab Pages MVP
# provisions nothing. See infrastructure/terraform/README.md.
