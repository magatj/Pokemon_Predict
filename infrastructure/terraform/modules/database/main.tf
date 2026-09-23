# Database module
#
# DynamoDB replaces the JSON/JSONL DataStore. The access patterns the code
# already uses map directly:
#
#   machines      PK=machineId                     - load_machines / save_machines
#   observations  PK=machineId, SK=observedAt      - observations_for_machine
#                 plus fingerprint as a unique key for de-duplication
#   forecasts     PK=machineId                     - save_forecasts / load_forecasts
#
# Planned resources:
#   aws_dynamodb_table.machines
#   aws_dynamodb_table.observations   - GSI on fingerprint, TTL on stale rows
#   aws_dynamodb_table.forecasts

# Resources are intentionally not declared: the GitLab Pages MVP
# provisions nothing. See infrastructure/terraform/README.md.
