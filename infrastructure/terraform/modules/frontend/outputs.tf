output "bucket_name" {
  description = "Name of the S3 bucket serving the site."
  value       = "${local.name_prefix}-site"
}

output "distribution_domain" {
  description = "Public domain the site is served from."
  value       = var.domain_name != "" ? var.domain_name : "PENDING-cloudfront-domain"
}
