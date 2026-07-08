# LifeLedger Backend

FastAPI backend for LifeLedger reminders. Local JSON persistence works by default, deployed mode uses Cognito-authenticated, user-scoped DynamoDB storage, and smart reminder fields support birthdays, renewal/expiration, maintenance, in-app alerts, Daily Digest preferences, and optional Daily Digest push notifications without changing the reminders table key schema.

## Run Locally

Preferred root command:

```powershell
cd D:\CodingProjects\LifeLedger
npm run backend
```

Manual PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for Swagger docs.

Local backend auth defaults to `AUTH_MODE=local`, so reminder routes use `LOCAL_DEV_USER_ID=local-dev-user` and do not require Cognito.

## Routes

- `GET /health` is public.
- `GET /reminders` requires authentication in Cognito mode.
- `POST /reminders` requires authentication in Cognito mode.
- `GET /reminders/{id}` requires authentication in Cognito mode.
- `PUT /reminders/{id}` requires authentication in Cognito mode.
- `DELETE /reminders/{id}` requires authentication in Cognito mode.
- `POST /reminders/{id}/complete` requires authentication in Cognito mode.`r`n- `GET /preferences/digest` and `PUT /preferences/digest` require authentication in Cognito mode.`r`n- `GET /push/config`, `GET /push/subscriptions`, `POST /push/subscriptions`, and `DELETE /push/subscriptions/{id}` require authentication in Cognito mode and are scoped to the authenticated user.

## Architecture

- `app/main.py` owns the FastAPI app and route handlers.
- `app/auth.py` extracts the current user from local config or Cognito claims.
- `app/schemas.py` owns Pydantic validation and API shapes.
- `app/models.py` owns the internal reminder model, including internal `user_id`.
- `app/recurrence.py` owns status calculation, recurrence, and `next_due_date`.
- `app/repository.py` defines the repository protocol and local JSON repository.
- `app/dynamo_repository.py` implements the DynamoDB repository with `user_id` plus `id` keys.
- `app/config.py` reads environment configuration with local-safe defaults.
- `app/repository_factory.py` selects the repository in one place.
- `lambda_handler.py` wraps FastAPI with Mangum for AWS Lambda.
- `template.yaml` defines the AWS SAM deployment shape.

The route layer stays unaware of whether reminders are stored in a JSON file or DynamoDB. It only receives a current user context and passes `user_id` into the repository layer.

## Environment Variables

Local development does not require environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `local` | Runtime environment name. |
| `AUTH_MODE` | `local` | `local` uses `LOCAL_DEV_USER_ID`; `cognito` requires Cognito claims. |
| `LOCAL_DEV_USER_ID` | `local-dev-user` | User id assigned to local requests. |
| `PERSISTENCE_MODE` | `local` | `local` uses JSON; `dynamodb` uses DynamoDB. |
| `REMINDERS_TABLE_NAME` | `lifeledger-reminders-auth` | DynamoDB table name. |
| `AWS_REGION` | `us-east-1` | DynamoDB region. Lambda also provides this automatically. |
| `LOCAL_DATA_FILE` | `backend/data/reminders.json` locally, `/tmp/lifeledger-reminders.json` in Lambda/SAM local | JSON file used when `PERSISTENCE_MODE=local`. |`r`n| `PREFERENCES_TABLE_NAME` | `lifeledger-preferences-auth` | DynamoDB preferences table name. |`r`n| `PUSH_SUBSCRIPTIONS_TABLE_NAME` | `lifeledger-push-subscriptions-auth` | DynamoDB push subscriptions table name. |`r`n| `LOCAL_PREFERENCES_FILE` | `backend/data/preferences.json` locally, `/tmp/lifeledger-preferences.json` in Lambda/SAM local | JSON file used for digest preferences in local persistence. |`r`n| `LOCAL_PUSH_SUBSCRIPTIONS_FILE` | `backend/data/push-subscriptions.json` locally, `/tmp/lifeledger-push-subscriptions.json` in Lambda/SAM local | JSON file used for push subscriptions in local persistence. |`r`n| `VAPID_PUBLIC_KEY` | empty | Public VAPID key. |`r`n| `VAPID_PRIVATE_KEY` | empty | Private VAPID key used only by the backend sender. |`r`n| `VAPID_SUBJECT` | empty | VAPID contact subject such as `mailto:you@example.com`. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://lifeledger.jpreinold.com,https://www.lifeledger.jpreinold.com` | Comma-separated frontend origins allowed to call the API. |

## Authentication Modes

Local mode:

```powershell
$env:AUTH_MODE = "local"
$env:LOCAL_DEV_USER_ID = "local-dev-user"
python -m uvicorn app.main:app --reload --port 8000
```

Cognito mode:

```powershell
$env:AUTH_MODE = "cognito"
python -m uvicorn app.main:app --reload --port 8000
```

In Cognito mode, API Gateway should validate the JWT before Lambda receives the request. FastAPI also checks for the Cognito `sub` claim in the API Gateway event and returns `401` if it is missing.

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
$env:REMINDERS_TABLE_NAME = "lifeledger-reminders-auth"
$env:AWS_REGION = "us-east-1"
python -m uvicorn app.main:app --reload --port 8000
```

Do not use DynamoDB mode locally unless AWS credentials and the auth-scoped table are configured.

Reminder records are scoped by `user_id`. The deployed DynamoDB table uses `user_id` as the partition key and reminder `id` as the sort key. The table is intentionally new for Phase 3 so the old id-only table schema does not need to be changed in place.

## Serverless Deployment Shape

`lambda_handler.py` exposes:

```python
handler = Mangum(app)
```

SAM uses that handler and routes HTTP API requests into the same FastAPI app. The template also creates Cognito resources, an HTTP API JWT authorizer, an unauthenticated `OPTIONS /{proxy+}` route for browser preflight, retained DynamoDB tables for reminders, preferences, and push subscriptions, a scheduled Daily Digest push Lambda, and CRUD permissions for the Lambda functions.

SAM local uses `backend/env.local.json`, which sets local auth and local persistence:

```powershell
cd backend
sam build
sam local start-api --env-vars env.local.json
```

Then open:

```text
http://127.0.0.1:3000/health
http://127.0.0.1:3000/reminders
```

When local persistence runs inside Lambda or SAM local, JSON data writes to `/tmp/lifeledger-reminders.json` because the function task directory may be read-only.

Deploy with Cognito and DynamoDB:

```powershell
cd backend
sam build
sam deploy --guided
```

Use these parameter values for deployed auth:

```text
AuthMode=cognito
PersistenceMode=dynamodb
RemindersTableName=lifeledger-reminders-auth
CorsAllowedOrigins=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://lifeledger.jpreinold.com,https://www.lifeledger.jpreinold.com
```

`sam deploy --guided` creates `samconfig.toml` for your local AWS account and deployment choices. That file is ignored by git. Use `samconfig.example.toml` as a safe reference that does not include credentials, account IDs, or local profile names.
