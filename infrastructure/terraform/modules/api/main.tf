# API module
#
# The FastAPI write API, which is what replaces the local-only observation
# submission on GitLab Pages. POST /api/v1/observations is the endpoint the
# frontend's ObservationSubmissionService already knows how to call.
#
# Planned resources:
#   aws_lambda_function.api        - FastAPI via Mangum, or App Runner instead
#   aws_apigatewayv2_api.http      - HTTP API in front of it
#   aws_apigatewayv2_stage.default - auto-deploy stage
#   aws_lambda_permission.api      - let API Gateway invoke the function
#   aws_iam_role.api               - execution role, DynamoDB access only

# Resources are intentionally not declared: the GitLab Pages MVP
# provisions nothing. See infrastructure/terraform/README.md.
