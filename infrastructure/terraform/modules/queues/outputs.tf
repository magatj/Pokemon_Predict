output "queue_name" {
  description = "Ingestion queue name."
  value       = "${local.name_prefix}-ingest"
}

output "dlq_name" {
  description = "Dead-letter queue name."
  value       = "${local.name_prefix}-ingest-dlq"
}
