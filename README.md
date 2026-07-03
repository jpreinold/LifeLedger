# LifeLedger

LifeLedger is a personal life-admin PWA with a React frontend and Python backend for tracking reminders like car tag renewals, oil changes, annual checkups, birthdays, subscriptions, insurance renewals, and home maintenance.

Phase 3 adds authentication while keeping the Phase 1 reminder workflow and Phase 2 deployment shape intact. Local development still defaults to JSON persistence and a local dev user; deployed reminders are protected by Amazon Cognito and scoped by user in DynamoDB.

## Common Dev Commands

Preferred flow: run these from the repo root with npm.

```powershell
npm run backend
```

Starts the FastAPI backend on `http://localhost:8000`. Local auth is enabled by default with `AUTH_MODE=local` and `LOCAL_DEV_USER_ID=local-dev-user`.

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

Builds SAM and starts the SAM local API with `backend/env.local.json`. SAM local uses local auth and local JSON persistence unless explicitly overridden.

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

## Authentication

Phase 3 uses Amazon Cognito for deployed authentication:

- Public sign-up is disabled in Cognito.
- Users are created manually by an admin.
- The React app uses Cognito sign-in and sign-out through Amplify UI.
- The frontend sends `Authorization: Bearer <access token>` to the API.
- API Gateway validates the Cognito JWT before reminder routes reach Lambda.
- FastAPI still defensively extracts the Cognito `sub` claim and rejects missing user context when `AUTH_MODE=cognito`.
- The backend assigns `user_id` from the authenticated `sub`; the frontend never sends or controls `user_id`.
- Reminder responses do not expose `user_id`.

Local development uses `AUTH_MODE=local` and `LOCAL_DEV_USER_ID=local-dev-user`, so no Cognito login is needed for `npm run backend`, `npm run frontend`, or `npm run sam:local`.

## Creating The First Cognito User

After deploying the backend with `AuthMode=cognito`, create users from the AWS Console:

1. Open Amazon Cognito.
2. Open the LifeLedger user pool from the SAM stack output `UserPoolId`.
3. Go to **Users**.
4. Choose **Create user**.
5. Use the user's email address as the username/email.
6. Send or set a temporary password.
7. Have the user sign in at the Cloudflare frontend and complete the required password change.

AWS CLI equivalent:

```powershell
aws cognito-idp admin-create-user `
  --user-pool-id <user-pool-id> `
  --username <email-address> `
  --user-attributes Name=email,Value=<email-address> Name=email_verified,Value=true `
  --region us-east-1
```

## Cloudflare Pages Frontend Deployment

LifeLedger uses Cloudflare Pages for the deployed React/Vite frontend.

Cloudflare Pages settings:

| Setting | Value |
| --- | --- |
| Project source | GitHub repository: `LifeLedger` |
| Root directory | `frontend` |
| Framework preset | `Vite` |
| Build command | `npm run build` |
| Build output directory | `dist` |

Cloudflare Pages environment variables:

| Variable | Value |
| --- | --- |
| `VITE_API_BASE_URL` | `https://your-aws-api-gateway-url` |
| `VITE_AUTH_MODE` | `cognito` |
| `VITE_COGNITO_REGION` | `us-east-1` |
| `VITE_COGNITO_USER_POOL_ID` | SAM output `UserPoolId` |
| `VITE_COGNITO_USER_POOL_CLIENT_ID` | SAM output `UserPoolClientId` |

These `VITE_*` values are public frontend configuration. Do not put API keys, tokens, passwords, AWS credentials, or private values in Vite environment variables.

Local frontend configuration:

- `frontend/.env.local` can point to Uvicorn: `VITE_API_BASE_URL=http://localhost:8000`
- `frontend/.env.local` can point to SAM local: `VITE_API_BASE_URL=http://127.0.0.1:3000`
- Use `VITE_AUTH_MODE=local` or omit it for local development.
- `frontend/.env.local` is ignored by git and should not be committed.
- `frontend/.env.example` shows placeholder values for deployed Cognito configuration.

Deployed frontend flow:

- Cloudflare Pages injects `VITE_*` variables at build time.
- React signs the user in with Cognito.
- React calls the deployed AWS API Gateway URL with the Cognito access token.
- API Gateway validates the JWT and invokes Lambda.
- Lambda runs FastAPI through Mangum.
- DynamoDB stores reminders under the authenticated user's `user_id`.

## API Routes

- `GET /health` is public.
- `GET /reminders` requires authentication in Cognito mode.
- `POST /reminders` requires authentication in Cognito mode.
- `GET /reminders/{id}` requires authentication in Cognito mode.
- `PUT /reminders/{id}` requires authentication in Cognito mode.
- `DELETE /reminders/{id}` requires authentication in Cognito mode.
- `POST /reminders/{id}/complete` requires authentication in Cognito mode.

## Backend Architecture

- FastAPI owns the routes in `backend/app/main.py`.
- Authentication helpers live in `backend/app/auth.py`.
- Pydantic validates request and response models in `backend/app/schemas.py`.
- Status, recurrence, and `next_due_date` logic live in `backend/app/recurrence.py`.
- Route handlers depend on a repository abstraction, not a concrete storage backend.
- Local mode uses JSON-file persistence at `backend/data/reminders.json`.
- DynamoDB mode uses `DynamoReminderRepository` for AWS deployment.
- Config in `backend/app/config.py` chooses auth mode, persistence mode, CORS origins, table name, and local data path.
- Mangum adapts FastAPI to Lambda through `backend/lambda_handler.py`.
- `backend/template.yaml` describes the SAM serverless deployment shape.

Reminder records include an internal `user_id`. In local mode it is `local-dev-user`; in Cognito mode it is the Cognito `sub`. DynamoDB uses `user_id` as the partition key and reminder `id` as the sort key, so users cannot read or mutate each other's reminders through the repository layer.

## Environment Variables

Backend local development works without setting any variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `local` | Names the runtime environment. |
| `AUTH_MODE` | `local` | Use `local` for dev/SAM local or `cognito` for deployed Cognito auth. |
| `LOCAL_DEV_USER_ID` | `local-dev-user` | User id assigned in local auth mode. |
| `PERSISTENCE_MODE` | `local` | Use `local` for JSON or `dynamodb` for DynamoDB. |
| `REMINDERS_TABLE_NAME` | `lifeledger-reminders-auth` | DynamoDB table name when DynamoDB mode is enabled. |
| `AWS_REGION` | `us-east-1` | Region used by the DynamoDB repository. Lambda also provides this automatically. |
| `LOCAL_DATA_FILE` | `backend/data/reminders.json` locally, `/tmp/lifeledger-reminders.json` in Lambda/SAM local | JSON file used when `PERSISTENCE_MODE=local`. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://lifeledger.jpreinold.com,https://www.lifeledger.jpreinold.com` | Comma-separated frontend origins allowed to call the API. |

## Serverless Notes

The backend can still run locally with Uvicorn. Lambda support is additive: `backend/lambda_handler.py` imports the same FastAPI app and wraps it with Mangum.

The SAM template defines:

- A Cognito user pool with public sign-up disabled.
- A Cognito web app client without a client secret.
- An HTTP API with CORS and a Cognito JWT authorizer.
- An unauthenticated `OPTIONS /{proxy+}` route so browser preflight requests can complete before authenticated reminder calls.
- A Lambda function running FastAPI through Mangum.
- A DynamoDB table named `lifeledger-reminders-auth` with `user_id` partition key and `id` sort key.
- `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` on the reminders table.

SAM local defaults to `AUTH_MODE=local` and `PERSISTENCE_MODE=local`, so it can serve `/health` and `/reminders` without Cognito login, AWS credentials, or DynamoDB calls. In Lambda/SAM local mode, local JSON persistence writes to `/tmp/lifeledger-reminders.json` because the function code directory may be read-only.

High-level SAM commands:

```powershell
cd backend
sam build
sam local start-api --env-vars env.local.json
sam deploy --guided
```

For deployed auth and DynamoDB, use these SAM parameter values during deploy:

```text
AuthMode=cognito
PersistenceMode=dynamodb
RemindersTableName=lifeledger-reminders-auth
CorsAllowedOrigins=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://lifeledger.jpreinold.com,https://www.lifeledger.jpreinold.com
```

SAM guided deploy creates `backend/samconfig.toml` for your machine/account. That file is ignored by git because it can contain local deployment choices. Use `backend/samconfig.example.toml` as a safe reference, then run:

```powershell
cd backend
sam deploy --guided
```

## Deployment Checklist

- `npm run check` passes.
- Backend is deployed with `AuthMode=cognito` and `PersistenceMode=dynamodb`.
- AWS `/health` works without signing in.
- AWS `/reminders` rejects requests without a bearer token.
- Cognito admin-created user can sign in.
- Cloudflare Pages has all required `VITE_*` environment variables.
- Cloudflare frontend can load, create, complete, and delete reminders after sign-in.
- `frontend/.env.local`, AWS credentials, tokens, and local deployment files are not committed.

## Not In Phase 3

Phase 3 does not add vault features, AI/RAG, Google Calendar sync, social login, public registration, sensitive data fields, push notifications, or a frontend redesign.
