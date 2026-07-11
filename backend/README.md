# LifeLedger Backend

FastAPI backend for LifeLedger reminders and records. Local JSON persistence works by default, deployed mode uses Cognito-authenticated, user-scoped DynamoDB storage, and smart reminder fields support birthdays, renewal/expiration, maintenance, in-app alerts, Daily Digest preferences, optional Daily Digest push notifications, and one-way Google Calendar sync foundations without changing the reminders table key schema. Records are first-class structured entities in their own repository/table and remain separate from reminders.

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
- `POST /reminders/{id}/complete` requires authentication in Cognito mode.
- `GET /preferences/digest` and `PUT /preferences/digest` require authentication in Cognito mode.
- `GET /records`, `POST /records`, `GET /records/{id}`, `PUT /records/{id}`, `POST /records/{id}/archive`, `POST /records/{id}/restore`, and `DELETE /records/{id}` require authentication in Cognito mode and are scoped to the authenticated user.
- `GET /push/config`, `GET /push/status`, `GET /push/subscriptions`, `POST /push/subscriptions`, `POST /push/test`, and `DELETE /push/subscriptions/{id}` require authentication in Cognito mode and are scoped to the authenticated user.
- `GET /integrations/google-calendar/status`, `POST /integrations/google-calendar/connect`, `POST /integrations/google-calendar/callback`, and `DELETE /integrations/google-calendar/disconnect` require authentication in Cognito mode and are scoped to the authenticated user.
- `POST /reminders/{id}/calendar-sync/enable` and `POST /reminders/{id}/calendar-sync/disable` require authentication and only operate on reminders owned by the authenticated user.

## Architecture

- `app/main.py` owns the FastAPI app and route handlers.
- `app/auth.py` extracts the current user from local config or Cognito claims.
- `app/schemas.py` owns Pydantic validation and API shapes.
- `app/models.py` owns the internal reminder model, including internal `user_id`.
- `app/models.py` also owns the internal record model, including internal `user_id`.
- `app/recurrence.py` owns status calculation, recurrence, and `next_due_date`.
- `app/repository.py` defines the repository protocol and local JSON repository.
- `app/records_repository.py` defines the record repository protocol and local JSON repository.
- `app/dynamo_repository.py` implements DynamoDB repositories with `user_id` plus `id` keys.
- `app/config.py` reads environment configuration with local-safe defaults.
- `app/repository_factory.py` selects repositories in one place.
- `app/google_calendar_repository.py` stores backend-only Google Calendar connections and OAuth states in local JSON or DynamoDB.
- `app/google_calendar_service.py` builds Google OAuth URLs, exchanges/refreshes tokens, and creates/updates/deletes all-day Calendar events.
- `lambda_handler.py` wraps FastAPI with Mangum for AWS Lambda.
- `template.yaml` defines the AWS SAM deployment shape.

The route layer stays unaware of whether reminders or records are stored in JSON files or DynamoDB. It only receives a current user context and passes `user_id` into the repository layer. The frontend never sends or controls `user_id`.

Record schemas are safe-by-default. They support `general`, `passport`, `driver_license`, `vehicle`, `insurance`, `appliance`, `pet`, `home`, `subscription`, and `warranty` types, plus safe text/date/tag fields. They intentionally omit passport numbers, driver license numbers, SSNs, payment card numbers, bank account numbers, insurance policy numbers, VINs, passwords, credentials, API keys, uploaded documents, OCR, and AI/RAG fields.

## Environment Variables

Local development does not require environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `local` | Runtime environment name. |
| `AUTH_MODE` | `local` | `local` uses `LOCAL_DEV_USER_ID`; `cognito` requires Cognito claims. |
| `LOCAL_DEV_USER_ID` | `local-dev-user` | User id assigned to local requests. |
| `PERSISTENCE_MODE` | `local` | `local` uses JSON; `dynamodb` uses DynamoDB. |
| `REMINDERS_TABLE_NAME` | `lifeledger-reminders-auth` | DynamoDB table name. |
| `RECORDS_TABLE_NAME` | `lifeledger-records-auth` | DynamoDB records table name. |
| `AWS_REGION` | `us-east-1` | DynamoDB region. Lambda also provides this automatically. |
| `LOCAL_DATA_FILE` | `backend/data/reminders.json` locally, `/tmp/lifeledger-reminders.json` in Lambda/SAM local | JSON file used when `PERSISTENCE_MODE=local`. |
| `LOCAL_RECORDS_FILE` | `backend/data/records.json` locally, `/tmp/lifeledger-records.json` in Lambda/SAM local | JSON file used for records when `PERSISTENCE_MODE=local`. |
| `PREFERENCES_TABLE_NAME` | `lifeledger-preferences-auth` | DynamoDB preferences table name. |
| `PUSH_SUBSCRIPTIONS_TABLE_NAME` | `lifeledger-push-subscriptions-auth` | DynamoDB push subscriptions table name. |
| `LOCAL_PREFERENCES_FILE` | `backend/data/preferences.json` locally, `/tmp/lifeledger-preferences.json` in Lambda/SAM local | JSON file used for digest preferences in local persistence. |
| `LOCAL_PUSH_SUBSCRIPTIONS_FILE` | `backend/data/push-subscriptions.json` locally, `/tmp/lifeledger-push-subscriptions.json` in Lambda/SAM local | JSON file used for push subscriptions in local persistence. |
| `GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME` | `lifeledger-google-calendar-connections-auth` | DynamoDB Google Calendar connection table name. |
| `GOOGLE_OAUTH_STATES_TABLE_NAME` | `lifeledger-google-oauth-states-auth` | DynamoDB OAuth state table name. |
| `LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE` | `backend/data/google-calendar-connections.json` locally, `/tmp/lifeledger-google-calendar-connections.json` in Lambda/SAM local | JSON file used for Google Calendar connections in local persistence. |
| `LOCAL_GOOGLE_OAUTH_STATES_FILE` | `backend/data/google-oauth-states.json` locally, `/tmp/lifeledger-google-oauth-states.json` in Lambda/SAM local | JSON file used for OAuth states in local persistence. |
| `GOOGLE_CLIENT_ID` | empty | Google OAuth web client ID for Calendar sync. |
| `GOOGLE_CLIENT_SECRET` | empty | Google OAuth web client secret. Backend-only; do not commit or expose to frontend env vars. |
| `GOOGLE_OAUTH_REDIRECT_URI` | empty | Authorized Google OAuth redirect URI used for code exchange. |
| `GOOGLE_CALENDAR_SCOPES` | `https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly` | Calendar event write scope plus CalendarList read-only scope for the Settings picker. |
| `VAPID_PUBLIC_KEY` | empty | Public VAPID key. |
| `VAPID_PRIVATE_KEY` | empty | Private VAPID key used only by the backend sender. Do not commit it. |
| `VAPID_SUBJECT` | empty | VAPID contact subject such as `mailto:you@example.com`. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://lifeledger.jpreinold.com,https://www.lifeledger.jpreinold.com` | Comma-separated frontend origins allowed to call the API. |

Generate VAPID keys with `npx web-push generate-vapid-keys`. The backend receives `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_SUBJECT`; the frontend receives only `VITE_VAPID_PUBLIC_KEY`. Google Calendar sync requires a Google Cloud OAuth web client, an OAuth consent screen/test users for private beta, and an authorized redirect URI that exactly matches `GOOGLE_OAUTH_REDIRECT_URI`. The Google client secret stays backend-only. Existing Google Calendar connections may need to reconnect once to grant the CalendarList read-only scope used by the calendar picker.

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
$env:LOCAL_RECORDS_FILE = "data/records.json"
python -m uvicorn app.main:app --reload --port 8000
```

DynamoDB mode is only used when explicitly enabled:

```powershell
$env:PERSISTENCE_MODE = "dynamodb"
$env:REMINDERS_TABLE_NAME = "lifeledger-reminders-auth"
$env:RECORDS_TABLE_NAME = "lifeledger-records-auth"
$env:AWS_REGION = "us-east-1"
python -m uvicorn app.main:app --reload --port 8000
```

Do not use DynamoDB mode locally unless AWS credentials and the auth-scoped table are configured.

Reminder and record items are scoped by `user_id`. The deployed DynamoDB tables use `user_id` as the partition key and item `id` as the sort key. The records table is separate from reminders and retained for future document, search, AI, and record-linked reminder work.

## Serverless Deployment Shape

`lambda_handler.py` exposes:

```python
handler = Mangum(app)
```

SAM uses that handler and routes HTTP API requests into the same FastAPI app. The template also creates Cognito resources, an HTTP API JWT authorizer, an unauthenticated `OPTIONS /{proxy+}` route for browser preflight, retained DynamoDB tables for reminders, records, preferences, push subscriptions, Google Calendar connections, and OAuth states, a scheduled Daily Digest push Lambda, and CRUD permissions for the Lambda functions.

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
http://127.0.0.1:3000/records
```

When local persistence runs inside Lambda or SAM local, JSON data writes to `/tmp/lifeledger-reminders.json`, `/tmp/lifeledger-records.json`, and the other `/tmp/lifeledger-*.json` persistence files because the function task directory may be read-only.

Run the scheduled Daily Digest push logic manually in local/dev without exposing a route:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python run_digest_push.py
```

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
RecordsTableName=lifeledger-records-auth
CorsAllowedOrigins=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://lifeledger.jpreinold.com,https://www.lifeledger.jpreinold.com
VapidPublicKey=<public-vapid-key>
VapidPrivateKey=<private-vapid-key>
VapidSubject=mailto:you@example.com
GoogleClientId=<google-oauth-web-client-id>
GoogleClientSecret=<google-oauth-web-client-secret>
GoogleOAuthRedirectUri=<authorized-google-oauth-redirect-uri>
GoogleCalendarScopes=https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly
```

`sam deploy --guided` creates `samconfig.toml` for your local AWS account and deployment choices. That file is ignored by git. Use `samconfig.example.toml` as a safe reference that does not include credentials, account IDs, or local profile names.
