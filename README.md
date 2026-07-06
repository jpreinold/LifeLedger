# LifeLedger

LifeLedger is a private personal admin hub for tracking important reminders, renewals, maintenance tasks, and records.

LifeLedger now has a unified smart reminder experience across regular reminders, birthdays, renewals/expirations, and maintenance. It also has an in-app alert/attention foundation: the bell and Alert Center surface reminders that need attention, and alert state supports dismissing or snoozing those in-app alerts. The Daily Digest gives a short briefing of what needs attention today, what is due today, and what is coming up, using the same smart reminder labels and alert logic as the Alert Center. This is not push notification, email, SMS, or calendar sync delivery yet. Local development still defaults to JSON persistence and a local dev user; deployed reminders and digest preferences are protected by Amazon Cognito and scoped by user in DynamoDB.

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

## Life Admin Templates

The frontend includes a Life Admin Templates modal for curated shortcuts into the add experience. Each template declares an explicit target type: `generic`, `birthday`, `renewal`, `maintenance`, or `comingSoon`.

Choosing **Browse templates** opens searchable templates with recommended smart starters first. Generic templates prefill the normal reminder form. Smart birthday templates open the Birthday flow, smart renewal templates open the Renewal flow with the correct renewal kind preselected, and smart maintenance templates open the Maintenance flow with a safe date-based interval prefilled. Coming soon templates preview future areas without opening a form or storing data.

Templates create user-scoped reminders only after the user confirms the form. They do not send or accept `user_id`; the backend still assigns ownership from Cognito or local auth. Templates avoid sensitive fields and should not store policy numbers, account numbers, card numbers, SSNs, passwords, medical details, contact details, addresses, uploaded documents, or government ID numbers.

## Reminder Management

Reminders can be created, edited, completed, and deleted from the React app. Editing uses the authenticated `PUT /reminders/{id}` route and only sends user-editable reminder fields.

Reminder records store optional delivery preference fields: `reminder_lead_value`, `reminder_lead_unit`, and `reminder_time`. The UI defaults new reminders to 1 day before at 9:00 AM and supports same day, 1 day before, 1 week before, 1 month before, and a simple custom lead time. These fields now feed the in-app alert eligibility window and prepare LifeLedger for future notification, calendar, and email integrations; this phase still does not send push notifications, email, or SMS.

Reminder records also support `reminder_type`. Existing reminders default to `generic`; smart types are `birthday`, `renewal`, and `maintenance`. Birthday reminders may include `birthday_details`; they calculate the next birthday date, infer birth year when the user enters the age someone is turning, and show labels such as turning age or age unknown on cards and dashboard rows. Renewal reminders may include `renewal_details` for safe renewal, expiration, review, subscription, free trial, warranty, or document dates. Maintenance reminders may include `maintenance_details` with item name, maintenance area, last completed date, interval, next due date, and general instructions. Maintenance is date-based only; mileage-based and usage-based maintenance are not included yet.

The bell opens an in-app Alert Center backed by `GET /alerts`. Alerts are reminders that are active, have a due date, are overdue, due today, or inside their configured reminder timing window, and are not currently dismissed or snoozed. The same alert set powers the bell badge and Home dashboard Needs attention section. Alert actions can complete, dismiss for now, snooze until tomorrow morning, or open the existing edit flow.

The Home dashboard includes a Daily Digest card. Opening it shows a near-full-height briefing drawer with Needs attention, Due today, Coming up, and compact smart reminder summaries. Digest items open the existing reminder detail drawer. Digest preferences live in Settings and include enabled status, digest time, lookahead window, timezone, and last-seen tracking. These preferences prepare the app for future push notification scheduling, but browser push subscriptions, notification permissions, VAPID, scheduled sending, and calendar sync are not implemented yet.

The reminder list now uses the top status cards as filters: All active, Overdue, Due today, and Due this month. The smart type chips remain as the only chip row: All types, Reminders, Birthdays, Renewals, and Maintenance. Status cards and type chips combine, and empty states describe the active filter where possible.

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

- For local testing with `npm run backend`, use `VITE_AUTH_MODE=local` and `VITE_API_BASE_URL=http://localhost:8000`.
- `frontend/.env.local` can point to SAM local: `VITE_API_BASE_URL=http://127.0.0.1:3000`
- Use deployed API Gateway URLs only for Cloudflare production builds.
- Restart `npm run frontend` after changing `frontend/.env.local`; Vite reads env values at startup.
- `frontend/.env.local` is ignored by git and should not be committed.
- `frontend/.env.example` shows both local and production examples.

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
- `GET /alerts` requires authentication in Cognito mode.
- `POST /reminders/{id}/alert/dismiss` requires authentication in Cognito mode.
- `POST /reminders/{id}/alert/snooze` requires authentication in Cognito mode.
- `GET /preferences/digest` requires authentication in Cognito mode.
- `PUT /preferences/digest` requires authentication in Cognito mode.

## Backend Architecture

- FastAPI owns the routes in `backend/app/main.py`.
- Authentication helpers live in `backend/app/auth.py`.
- Pydantic validates request and response models in `backend/app/schemas.py`.
- Status, recurrence, and `next_due_date` logic live in `backend/app/recurrence.py`.
- Birthday reminder date, age, and label helpers live in `backend/app/birthdays.py`.
- Maintenance reminder interval, due-date, completion, and label helpers live in `backend/app/maintenance.py`.
- Route handlers depend on a repository abstraction, not a concrete storage backend.
- Local mode uses JSON-file persistence at `backend/data/reminders.json`.
- DynamoDB mode uses `DynamoReminderRepository` for AWS deployment.
- Config in `backend/app/config.py` chooses auth mode, persistence mode, CORS origins, table name, and local data path.
- Digest preferences use a separate user-scoped preferences repository with local JSON and DynamoDB implementations.
- Mangum adapts FastAPI to Lambda through `backend/lambda_handler.py`.
- `backend/template.yaml` describes the SAM serverless deployment shape.

Reminder records include an internal `user_id`. In local mode it is `local-dev-user`; in Cognito mode it is the Cognito `sub`. DynamoDB uses `user_id` as the partition key and reminder `id` as the sort key, so users cannot read or mutate each other's reminders through the repository layer. Reminder timing preferences, smart birthday fields, smart renewal fields, smart maintenance fields, and alert state fields such as `alert_dismissed_until`, `alert_snoozed_until`, and `alert_last_action_at` are stored on each reminder item without changing the DynamoDB key schema. Digest preferences are stored in a separate table keyed by `user_id`, so future notification scheduling can read per-user digest time, timezone, lookahead, enabled state, and last-seen state without changing reminder storage.

## Environment Variables

Backend local development works without setting any variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `local` | Names the runtime environment. |
| `AUTH_MODE` | `local` | Use `local` for dev/SAM local or `cognito` for deployed Cognito auth. |
| `LOCAL_DEV_USER_ID` | `local-dev-user` | User id assigned in local auth mode. |
| `PERSISTENCE_MODE` | `local` | Use `local` for JSON or `dynamodb` for DynamoDB. |
| `REMINDERS_TABLE_NAME` | `lifeledger-reminders-auth` | DynamoDB table name when DynamoDB mode is enabled. |
| `PREFERENCES_TABLE_NAME` | `lifeledger-preferences-auth` | DynamoDB preferences table name when DynamoDB mode is enabled. |
| `AWS_REGION` | `us-east-1` | Region used by the DynamoDB repository. Lambda also provides this automatically. |
| `LOCAL_DATA_FILE` | `backend/data/reminders.json` locally, `/tmp/lifeledger-reminders.json` in Lambda/SAM local | JSON file used when `PERSISTENCE_MODE=local`. |
| `LOCAL_PREFERENCES_FILE` | `backend/data/preferences.json` locally, `/tmp/lifeledger-preferences.json` in Lambda/SAM local | JSON file used for digest preferences when `PERSISTENCE_MODE=local`. |
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
- A DynamoDB table named `lifeledger-preferences-auth` with `user_id` partition key for Daily Digest preferences.
- `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` on the reminders table.

SAM local defaults to `AUTH_MODE=local` and `PERSISTENCE_MODE=local`, so it can serve `/health`, `/reminders`, and `/preferences/digest` without Cognito login, AWS credentials, or DynamoDB calls. In Lambda/SAM local mode, local JSON persistence writes to `/tmp/lifeledger-reminders.json` and `/tmp/lifeledger-preferences.json` because the function code directory may be read-only.

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

## Not In This Phase

This phase does not add push notifications, Google Calendar sync, email sending, secure vault features, AI/RAG, sensitive data fields, file uploads, social login, public registration, mileage-based maintenance, usage-based maintenance, supply inventory, or another frontend redesign. Do not store policy numbers, account numbers, card numbers, government ID numbers, passwords, medical details, or uploaded documents in reminders. Future smart reminder work may include usage-based maintenance, records, secure vault features, and calendar or notification integrations.
