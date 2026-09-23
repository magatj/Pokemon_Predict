# Auth module
#
# Cognito for authenticated reporting. Anonymous reports stay possible; an
# account simply raises the weight a report can carry, because a repeat
# reporter with a history is more trustworthy than a one-off.
#
# Planned resources:
#   aws_cognito_user_pool.main
#   aws_cognito_user_pool_client.web
#   aws_cognito_identity_pool.main

# Resources are intentionally not declared: the GitLab Pages MVP
# provisions nothing. See infrastructure/terraform/README.md.
