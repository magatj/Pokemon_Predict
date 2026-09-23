# prod environment.
#
# NOT APPLIED for the GitLab Pages MVP. `terraform plan` here describes the
# target AWS architecture; the MVP provisions nothing.

module "database" {
  source = "../../modules/database"

  project                = var.project
  environment            = var.environment
  tags                   = var.tags
  point_in_time_recovery = true
}

module "queues" {
  source = "../../modules/queues"

  project     = var.project
  environment = var.environment
  tags        = var.tags
}

module "ingestion" {
  source = "../../modules/ingestion"

  project         = var.project
  environment     = var.environment
  tags            = var.tags
  ingest_schedule = var.ingest_schedule
  queue_arn       = module.queues.queue_name

  table_names = {
    machines     = module.database.machines_table_name
    observations = module.database.observations_table_name
    forecasts    = module.database.forecasts_table_name
  }
}

module "auth" {
  source = "../../modules/auth"

  project     = var.project
  environment = var.environment
  tags        = var.tags
}

module "api" {
  source = "../../modules/api"

  project                 = var.project
  environment             = var.environment
  tags                    = var.tags
  observations_table_name = module.database.observations_table_name
  cognito_user_pool_arn   = module.auth.user_pool_arn
}

module "frontend" {
  source = "../../modules/frontend"

  project     = var.project
  environment = var.environment
  tags        = var.tags
  domain_name = var.domain_name
}

module "dns" {
  source = "../../modules/dns"

  project                  = var.project
  environment              = var.environment
  tags                     = var.tags
  domain_name              = var.domain_name
  hosted_zone_id           = var.hosted_zone_id
  distribution_domain_name = module.frontend.distribution_domain
}

module "monitoring" {
  source = "../../modules/monitoring"

  project     = var.project
  environment = var.environment
  tags        = var.tags
  alert_email = var.alert_email
}
