output "site_bucket" {
  description = "S3 bucket the built frontend is uploaded to."
  value       = module.frontend.bucket_name
}

output "site_domain" {
  description = "Domain the dashboard is served from."
  value       = module.frontend.distribution_domain
}

output "api_base_url" {
  description = "Value for the frontend's VITE_SUBMISSION_ENDPOINT."
  value       = module.api.api_base_url
}

output "ingest_schedule" {
  description = "Effective ingestion schedule."
  value       = module.ingestion.schedule_expression
}
