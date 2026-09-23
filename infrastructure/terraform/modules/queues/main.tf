# Queues module
#
# Decouples fetching from normalization so a slow or failing parser cannot
# block ingestion, and a poison payload lands in the DLQ instead of being
# retried forever.
#
# Planned resources:
#   aws_sqs_queue.ingest
#   aws_sqs_queue.ingest_dlq
#   aws_sqs_queue_redrive_policy.ingest

# Resources are intentionally not declared: the GitLab Pages MVP
# provisions nothing. See infrastructure/terraform/README.md.
