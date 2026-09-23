output "machines_table_name" {
  description = "Machines table name."
  value       = "${local.name_prefix}-machines"
}

output "observations_table_name" {
  description = "Observations table name."
  value       = "${local.name_prefix}-observations"
}

output "forecasts_table_name" {
  description = "Forecasts table name."
  value       = "${local.name_prefix}-forecasts"
}
