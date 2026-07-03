# LifeLedger

LifeLedger is a personal life-admin PWA with a React frontend and Python backend for tracking reminders like car tag renewals, oil changes, annual checkups, birthdays, subscriptions, insurance renewals, and home maintenance.

Phase 2 keeps the working Phase 1 reminder app intact while making the backend easier to explain as an AWS/serverless Python project.

## Run Locally

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

If you are using Git Bash:

```bash
cd /d/CodingProjects/LifeLedger/backend
source .venv/Scripts/activate
python -m uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

The frontend runs at `http://localhost:5173` and calls `http://localhost:8000` by default. API docs are available at `http://localhost:8000/docs`.

## Common Dev Commands

Preferred flow: run these from the repo root with npm.

```powershell
npm run backend
```

Starts the FastAPI backend on `http://localhost:8000`.

```powershell
npm run frontend
```

Starts the Vite frontend on `http://localhost:5173`.

```powershell
npm run test:backend
```

Runs the backend pytest suite.

```powershell
npm run sam:local
```

Sets `AWS_PROFILE=lifeledger`, sets `AWS_REGION=us-east-1`, builds SAM, and starts the SAM local API with `env.local.json`.

```powershell
npm run check
```

Runs backend tests, frontend build, and frontend lint when the lint script exists.

Daily startup:

```powershell
cd D:\CodingProjects\LifeLedger
npm run backend
```

In a second terminal:

```powershell
cd D:\CodingProjects\LifeLedger
npm run frontend
```

## Cloudflare Pages Frontend Deployment

LifeLedger uses Cloudflare Pages for the deployed React/Vite frontend. Do not deploy the frontend to Vercel or Netlify for this project.

Cloudflare Pages settings:

| Setting | Value |
| --- | --- |
| Project source | GitHub repository: `LifeLedger` |
| Root directory | `frontend` |
| Framework preset | `Vite` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Environment variable | `VITE_API_BASE_URL=https://your-aws-api-gateway-url` |

`VITE_API_BASE_URL` is public frontend configuration. It should contain the public AWS API Gateway base URL only. Do not put API keys, tokens, passwords, AWS credentials, or private values in Vite environment variables.

Local frontend API configuration:

- `frontend/.env.local` can point to Uvicorn local backend: `VITE_API_BASE_URL=http://localhost:8000`
- `frontend/.env.local` can point to SAM local: `VITE_API_BASE_URL=http://127.0.0.1:3000`
- `frontend/.env.local` is ignored by git and should not be committed.
- `frontend/.env.example` shows the required variable with a placeholder value.

Deployed frontend flow:

- Cloudflare Pages injects `VITE_API_BASE_URL` at build time.
- The React app calls the deployed AWS API Gateway URL.
- API Gateway invokes Lambda.
- Lambda runs FastAPI through Mangum.
- DynamoDB stores deployed reminders.

Before deploying the frontend:

- AWS backend is deployed.
- `/health` works on the AWS API Gateway URL.
- `/reminders` works on the AWS API Gateway URL.
- Cloudflare Pages has `VITE_API_BASE_URL` set.
- `npm run check` passes.
- `frontend/.env.local` is not committed.

## API Routes

- `GET /health`
- `GET /reminders`
- `POST /reminders`
- `GET /reminders/{id}`
- `PUT /reminders/{id}`
- `DELETE /reminders/{id}`
- `POST /reminders/{id}/complete`

## Backend Architecture

- FastAPI owns the routes in `backend/app/main.py`.
- Pydantic validates request and response models in `backend/app/schemas.py`.
- Status, recurrence, and `next_due_date` logic live in `backend/app/recurrence.py`.
- Route handlers depend on a repository abstraction, not a concrete storage backend.
- Local mode uses JSON-file persistence at `backend/data/reminders.json`.
- DynamoDB mode uses `DynamoReminderRepository` for AWS deployment.
- Config in `backend/app/config.py` chooses the persistence mode.
- Mangum adapts FastAPI to Lambda through `backend/lambda_handler.py`.
- `backend/template.yaml` describes the SAM serverless deployment shape.

## Environment Variables

Local development works without setting any variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `local` | Names the runtime environment. |
| `PERSISTENCE_MODE` | `local` | Use `local` for JSON or `dynamodb` for DynamoDB. |
| `REMINDERS_TABLE_NAME` | `lifeledger-reminders` | DynamoDB table name when DynamoDB mode is enabled. |
| `AWS_REGION` | `us-east-1` | Region used by the DynamoDB repository. Lambda also provides this automatically. |
| `LOCAL_DATA_FILE` | `backend/data/reminders.json` locally, `/tmp/lifeledger-reminders.json` in Lambda/SAM local | JSON file used when `PERSISTENCE_MODE=local`. |

## Serverless Notes

The backend can still run locally with Uvicorn. Lambda support is additive: `backend/lambda_handler.py` imports the same FastAPI app and wraps it with Mangum.

The SAM template defines a Lambda function, HTTP API events, a DynamoDB table with `id` as the partition key, and DynamoDB permissions for the function. The template defaults to `PERSISTENCE_MODE=local`, so `sam local start-api` can serve `/health` and `/reminders` without AWS credentials or DynamoDB calls. In Lambda/SAM local mode, local JSON persistence writes to `/tmp/lifeledger-reminders.json` because the function code directory may be read-only.

For this single-user MVP, `id` is acceptable as the DynamoDB partition key. A future multi-user version should likely use `user_id` as the partition key and reminder id as the sort key after authentication exists.

High-level SAM commands:

```powershell
cd backend
sam build
sam local start-api
sam deploy --guided
```

To test SAM local with explicit environment variables:

```powershell
sam local start-api --env-vars env.local.json
```

To deploy with DynamoDB persistence, explicitly override `PersistenceMode=dynamodb` during `sam deploy --guided` or with SAM parameter overrides.

SAM guided deploy creates `backend/samconfig.toml` for your machine/account. That file is ignored by git because it can contain local deployment choices. Use `backend/samconfig.example.toml` as a safe reference, then run:

```powershell
cd backend
sam deploy --guided
```

Deployment is not required for Phase 2 completion.

## Not In Phase 2

Phase 2 does not add AI, RAG, Google Calendar sync, OAuth, authentication, secure vault storage, credit card storage, insurance documents, multiple users, push notifications, or a frontend redesign.
