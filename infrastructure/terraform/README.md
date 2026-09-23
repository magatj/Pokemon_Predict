# Infrastructure

AWS migration scaffold. **Nothing here is provisioned for the GitLab Pages MVP.**

The MVP runs entirely on GitLab: scheduled CI does the ingestion and
forecasting, and Pages serves the generated JSON plus the React bundle. These
modules describe the target architecture for when the project needs a write API
and a real database.

```
EventBridge -> Lambda (discovery / community ingestion)
                 |
                SQS
                 |
        Normalization Lambda
                 |
             DynamoDB
                 |
         Forecast service
                 |
   API Gateway -> FastAPI -> React -> CloudFront
```

## Layout

| Path | Purpose |
|---|---|
| `modules/frontend` | S3 bucket + CloudFront distribution for the built SPA |
| `modules/api` | API Gateway + Lambda/App Runner running the FastAPI app |
| `modules/database` | DynamoDB tables for machines, observations and forecasts |
| `modules/ingestion` | Scheduled ingestion Lambdas (the same Python package) |
| `modules/queues` | SQS queue + dead-letter queue between ingest and normalize |
| `modules/auth` | Cognito user pool for authenticated reporting |
| `modules/monitoring` | CloudWatch log groups, metrics and alarms |
| `modules/dns` | Route53 records and an ACM certificate |
| `environments/dev` | Development wiring |
| `environments/prod` | Production wiring |

Each module currently declares its variables, outputs and intended resources as
commented blocks. `terraform fmt -check -recursive` and `terraform validate`
both pass, so the scaffold stays honest as it is filled in.

## Why the adapters do not change

`apps/ingestion/pokevend` has no GitLab-specific code. The jobs are plain
functions over a `DataStore` interface, so the Lambda handler is a thin wrapper:

```python
from pokevend.jobs import refresh_machines

def handler(event, context):
    return {"machines": refresh_machines.run(verify=True)}
```

Replacing `DataStore` with a DynamoDB-backed implementation of the same methods
is the only substantive change. The source adapters, normalizers and forecast
engine are portable as-is.
