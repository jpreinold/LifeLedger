# LifeLedger Backend

FastAPI backend for the LifeLedger reminder MVP. Phase 2 keeps local JSON persistence working by default while adding Lambda, SAM, and DynamoDB readiness.

## Run Locally

PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Git Bash:

```bash
cd /d/CodingProjects/LifeLedger/backend
source .venv/Scripts/activate
python -m uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for Swagger docs.

## Routes

- `GET /health`
- `GET /reminders`
- `POST /reminders`
- `GET /reminders/{id}`
- `PUT /reminders/{id}`
- `DELETE /reminders/{id}`
- `POST /reminders/{id}/complete`

## Architecture

- `app/main.py` owns the FastAPI app and route handlers.
- `app/schemas.py` owns Pydantic validation and API shapes.
- `app/models.py` owns the internal reminder model.
- `app/recurrence.py` owns status calculation, recurrence, and `next_due_date`.
- `app/repository.py` defines the repository protocol and local JSON repository.
- `app/dynamo_repository.py` implements the DynamoDB repository.
- `app/config.py` reads environment configuration with local-safe defaults.
- `app/repository_factory.py` selects the repository in one place.
- `lambda_handler.py` wraps FastAPI with Mangum for AWS Lambda.
- `template.yaml` defines the AWS SAM deployment shape.

The route layer stays unaware of whether reminders are stored in a JSON file or DynamoDB.

## Environment Variables

Local development does not require environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `local` | Runtime environment name. |
| `PERSISTENCE_MODE` | `local` | `local` uses JSON; `dynamodb` uses DynamoDB. |
| `REMINDERS_TABLE_NAME` | `lifeledger-reminders` | DynamoDB table name. |
| `AWS_REGION` | `us-east-1` | DynamoDB region. Lambda also provides this automatically. |
| `LOCAL_DATA_FILE` | `backend/data/reminders.json` locally, `/tmp/lifeledger-reminders.json` in Lambda/SAM local | JSON file used when `PERSISTENCE_MODE=local`. |

## Persistence Modes

Local mode is the default:

```powershell
$env:PERSISTENCE_MODE = "local"
$env:LOCAL_DATA_FILE = "data/reminders.json"
python -m uvicorn app.main:app --reload --port 8000
```

DynamoDB mode is only used when explicitly enabled:

```powershell
$env:PERSISTENCE_MODE = "dynamodb"
$env:REMINDERS_TABLE_NAME = "lifeledger-reminders"
$env:AWS_REGION = "us-east-1"
python -m uvicorn app.main:app --reload --port 8000
```

Do not use DynamoDB mode locally unless AWS credentials and a table are configured.

For this single-user MVP, the DynamoDB table uses `id` as the partition key. A future multi-user version should likely use `user_id` as the partition key and reminder id as the sort key after authentication exists.

## Serverless Deployment Shape

`lambda_handler.py` exposes:

```python
handler = Mangum(app)
```

SAM uses that handler and routes HTTP API requests into the same FastAPI app. The template also creates a DynamoDB table and grants the Lambda function CRUD permissions.

The SAM template defaults to `PERSISTENCE_MODE=local`, so local SAM testing does not call DynamoDB and does not require AWS credentials:

```powershell
cd backend
sam build
sam local start-api
```

Then open:

```text
http://127.0.0.1:3000/health
http://127.0.0.1:3000/reminders
```

When local persistence runs inside Lambda or SAM local, JSON data writes to `/tmp/lifeledger-reminders.json` because the function task directory may be read-only.

You can also pass the checked-in local env file explicitly:

```powershell
sam local start-api --env-vars env.local.json
```

High-level deploy commands:

```powershell
cd backend
sam build
sam deploy --guided
```

To deploy with DynamoDB persistence, explicitly set `PersistenceMode=dynamodb` during guided deploy or with SAM parameter overrides.

`sam deploy --guided` creates `samconfig.toml` for your local AWS account and deployment choices. That file is ignored by git. Use `samconfig.example.toml` as a safe reference that does not include credentials, account IDs, or local profile names.

Deployment is optional for Phase 2; the local Uvicorn workflow remains the primary development path.
