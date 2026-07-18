# LifeLedger Backend

FastAPI backend for LifeLedger reminders and records. Local JSON persistence works for explicit local development; deployed mode uses Cognito-authenticated, user-scoped DynamoDB storage, and smart reminder fields support birthdays, renewal/expiration, maintenance, in-app alerts, Daily Digest preferences, optional Daily Digest push notifications, and one-way Google Calendar sync foundations without changing the reminders table key schema. Records are first-class structured entities in their own repository/table and can link to related records and reminders through explicit user-created linked item edges. Records can also have secure PDF/JPEG/PNG attachments stored in private S3 quarantine/clean buckets after malware scanning and file validation. Optional protected record details and Google OAuth token bundles are application-encrypted before persistence when encryption is configured.

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
- `POST /reminders/{id}/snooze`, `POST /reminders/{id}/snooze/clear`, and `POST /reminders/{id}/renew` require authentication in Cognito mode, verify reminder ownership, validate dates/transitions, and append lightweight lifecycle history.
- `GET /preferences/digest` and `PUT /preferences/digest` require authentication in Cognito mode.
- `GET /records`, `POST /records`, `GET /records/{id}`, `PUT /records/{id}`, `POST /records/{id}/archive`, `POST /records/{id}/restore`, and `DELETE /records/{id}` require authentication in Cognito mode and are scoped to the authenticated user.
- `GET /records/{id}/links`, `POST /records/{id}/links`, and `DELETE /records/{id}/links/{link_id}` require authentication, verify record ownership, and manage only explicit relationship rows.
- `GET /reminders/{id}/links` and `DELETE /reminders/{id}/links/{link_id}` require authentication, verify reminder ownership, and return/remove only one-hop linked record relationships.
- `GET /records/{id}/protected/status`, `PUT /records/{id}/protected`, `GET /records/{id}/protected`, and `DELETE /records/{id}/protected` require authentication, verify record ownership, keep protected values out of standard record responses, and reveal plaintext only through the explicit no-store reveal route.
- `GET /records/{id}/attachments`, `POST /records/{id}/attachments/upload-intent`, `POST /records/{id}/attachments/{attachment_id}/complete`, `GET /records/{id}/attachments/{attachment_id}`, `POST /records/{id}/attachments/{attachment_id}/refresh-status`, `POST /records/{id}/attachments/{attachment_id}/download-url`, `POST /records/{id}/attachments/{attachment_id}/preview-url`, and `DELETE /records/{id}/attachments/{attachment_id}` require authentication, verify record ownership, return no-store responses, and never expose permanent S3 object paths.
- `GET /push/config`, `GET /push/status`, `GET /push/subscriptions`, `POST /push/subscriptions`, `POST /push/test`, and `DELETE /push/subscriptions/{id}` require authentication in Cognito mode and are scoped to the authenticated user.
- `GET /integrations/google-calendar/status`, `POST /integrations/google-calendar/connect`, `POST /integrations/google-calendar/callback`, and `DELETE /integrations/google-calendar/disconnect` require authentication in Cognito mode and are scoped to the authenticated user.
- `POST /reminders/{id}/calendar-sync/enable` and `POST /reminders/{id}/calendar-sync/disable` require authentication and only operate on reminders owned by the authenticated user.

## Architecture

- `app/main.py` owns the FastAPI app and route handlers.
- `app/auth.py` extracts the current user from local config or Cognito claims.
- `app/schemas.py` owns Pydantic validation and API shapes.
- `app/models.py` owns the internal reminder model, including internal `user_id`.
- `app/models.py` also owns the internal record model, including internal `user_id`.
- `app/recurrence.py` owns derived reminder status calculation, effective attention date, recurrence, and `next_due_date`.
- `app/reminder_lifecycle.py` appends lightweight lifecycle events and guards repeated lifecycle actions.
- `app/repository.py` defines the repository protocol and local JSON repository.
- `app/records_repository.py` defines the record repository protocol and local JSON repository.
- `app/linked_items_repository.py` defines linked item local JSON and DynamoDB repositories with user-scoped source/target indexes.
- `app/relationship_service.py` verifies ownership, creates explicit record links, removes link rows, and builds safe one-hop neighborhoods.
- `app/dynamo_repository.py` implements DynamoDB repositories with `user_id` plus `id` keys.
- `app/config.py` reads environment configuration with local-safe defaults.
- `app/encryption_service.py` provides AES-256-GCM envelope encryption for protected record fields and Google token bundles, with local and KMS modes.
- `app/attachments.py` validates attachment policy, creates presigned S3 upload/download operations, reconciles GuardDuty scan tags, verifies magic bytes, and promotes clean files.
- `app/attachments_repository.py` persists attachment metadata locally or in DynamoDB using authenticated user and record scope.
- `attachment_scan_finalizer.py` handles GuardDuty EventBridge object scan result events and reuses the same fail-closed promotion logic.
- `app/secret_provider.py` retrieves Google OAuth and push private secrets from AWS Secrets Manager with process-level caching.
- `app/repository_factory.py` selects repositories in one place.
- `app/google_calendar_repository.py` stores backend-only Google Calendar connections and OAuth states in local JSON or DynamoDB.
- `app/google_calendar_service.py` builds Google OAuth URLs, exchanges/refreshes tokens, and creates/updates/deletes all-day Calendar events.
- `lambda_handler.py` wraps FastAPI with Mangum for AWS Lambda.
- `template.yaml` defines the AWS SAM deployment shape.

The route layer stays unaware of whether reminders, records, or linked items are stored in JSON files or DynamoDB. It only receives a current user context and passes `user_id` into the repository layer. The frontend never sends or controls `user_id`.
Reminder lifecycle APIs keep persisted state backward compatible. Existing reminder rows missing `snoozed_until`, `archived_at`, `effective_attention_date`, or `lifecycle_events` still validate with safe defaults. The API response derives `status` and `effective_attention_date` on read, so the database does not store redundant urgency labels that can drift from date rules.

Normal record schemas are safe-by-default. They support `general`, `passport`, `driver_license`, `vehicle`, `insurance`, `appliance`, `pet`, `home`, `subscription`, and `warranty` types, plus safe text/date/tag fields. Linked item responses use safe summaries only and never include protected values, attachment objects, or `user_id`. Protected fields are handled by dedicated write/reveal schemas and encrypted before storage. Attachments are not zero-knowledge storage: authorized backend services, S3, KMS, and GuardDuty can access decrypted file contents for storage, scanning, validation, preview, download, and deletion. Do not store SSNs, payment card data, banking data, passwords, PINs, recovery codes, private keys, API keys, authentication credentials, highly sensitive medical records, secret/recovery documents, OCR, or AI/RAG data.

Linked Items are a virtual knowledge graph, not a graph database. The backend persists explicit record-to-record and record-to-reminder edges in DynamoDB, queries the source and target GSIs for one-hop neighborhoods, and returns grouped safe summaries to the UI. Deleting a link deletes only that edge; deleting a record or reminder also removes its edge rows so no orphaned relationships remain. No AI inference, protected-field matching, multi-hop traversal, or automatic record-to-reminder generation happens in this phase.

## Environment Variables

Local development does not require environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| APP_ENV | local | Runtime environment name; production deployment must explicitly use production. |
| APP_COMPONENT | api | Component-specific startup validation (api, digest, or attachment_finalizer); SAM sets this automatically. |
| `AUTH_MODE` | `local` | `local` uses `LOCAL_DEV_USER_ID`; `cognito` requires Cognito claims. |
| `LOCAL_DEV_USER_ID` | `local-dev-user` | User id assigned to local requests. |
| `PERSISTENCE_MODE` | `local` | `local` uses JSON; `dynamodb` uses DynamoDB. |
| `REMINDERS_TABLE_NAME` | `lifeledger-reminders-auth` | DynamoDB table name. |
| `RECORDS_TABLE_NAME` | `lifeledger-records-auth` | DynamoDB records table name. |
| `RECORD_ATTACHMENTS_TABLE_NAME` | `lifeledger-record-attachments-auth` | DynamoDB record attachments metadata table name. |
| `LINKED_ITEMS_TABLE_NAME` | `lifeledger-linked-items-auth` | DynamoDB linked item edge table name. |
| `AWS_REGION` | `us-east-1` | DynamoDB region. Lambda also provides this automatically. |
| `LOCAL_DATA_FILE` | `backend/data/reminders.json` locally, `/tmp/lifeledger-reminders.json` in Lambda/SAM local | JSON file used when `PERSISTENCE_MODE=local`. |
| `LOCAL_RECORDS_FILE` | `backend/data/records.json` locally, `/tmp/lifeledger-records.json` in Lambda/SAM local | JSON file used for records when `PERSISTENCE_MODE=local`. |
| `LOCAL_RECORD_ATTACHMENTS_FILE` | `backend/data/record-attachments.json` locally, `/tmp/lifeledger-record-attachments.json` in Lambda/SAM local | JSON file used for attachment metadata in local persistence. |
| `LOCAL_LINKED_ITEMS_FILE` | `backend/data/linked-items.json` locally, `/tmp/lifeledger-linked-items.json` in Lambda/SAM local | JSON file used for linked item persistence. |
| `PREFERENCES_TABLE_NAME` | `lifeledger-preferences-auth` | DynamoDB preferences table name. |
| `PUSH_SUBSCRIPTIONS_TABLE_NAME` | `lifeledger-push-subscriptions-auth` | DynamoDB push subscriptions table name. |
| `LOCAL_PREFERENCES_FILE` | `backend/data/preferences.json` locally, `/tmp/lifeledger-preferences.json` in Lambda/SAM local | JSON file used for digest preferences in local persistence. |
| `LOCAL_PUSH_SUBSCRIPTIONS_FILE` | `backend/data/push-subscriptions.json` locally, `/tmp/lifeledger-push-subscriptions.json` in Lambda/SAM local | JSON file used for push subscriptions in local persistence. |
| `GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME` | `lifeledger-google-calendar-connections-auth` | DynamoDB Google Calendar connection table name. |
| `GOOGLE_OAUTH_STATES_TABLE_NAME` | `lifeledger-google-oauth-states-auth` | DynamoDB OAuth state table name. |
| `LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE` | `backend/data/google-calendar-connections.json` locally, `/tmp/lifeledger-google-calendar-connections.json` in Lambda/SAM local | JSON file used for Google Calendar connections in local persistence. |
| `LOCAL_GOOGLE_OAUTH_STATES_FILE` | `backend/data/google-oauth-states.json` locally, `/tmp/lifeledger-google-oauth-states.json` in Lambda/SAM local | JSON file used for OAuth states in local persistence. |
| `RECORD_ENCRYPTION_MODE` | `disabled` | `disabled`, `local`, or `kms`. Production should use `kms`. |
| `DATA_ENCRYPTION_KMS_KEY_ARN` | empty | KMS key ARN used by the API Lambda in `kms` mode. |
| `LOCAL_RECORDS_ENCRYPTION_KEY` | empty | Base64-encoded 32-byte local wrapping key for local protected-record testing. Never commit it. |
| `GOOGLE_CLIENT_ID` | empty | Google OAuth web client ID for Calendar sync. |
| `GOOGLE_OAUTH_SECRET_ARN` | empty | Secrets Manager ARN for JSON `{"client_secret":"..."}` in production. |
| `GOOGLE_CLIENT_SECRET` | empty | Local-only plaintext fallback. Production defaults to disallow plaintext fallback. |
| `GOOGLE_OAUTH_REDIRECT_URI` | empty | Authorized Google OAuth redirect URI used for code exchange. |
| `GOOGLE_CALENDAR_SCOPES` | `https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly` | Calendar event write scope plus CalendarList read-only scope for the Settings picker. |
| `VAPID_PUBLIC_KEY` | empty | Public VAPID key. |
| `PUSH_SECRET_ARN` | empty | Secrets Manager ARN for JSON `{"vapid_private_key":"..."}` in production. |
| `VAPID_PRIVATE_KEY` | empty | Local-only plaintext fallback. Do not commit it. |
| `VAPID_SUBJECT` | empty | VAPID contact subject such as `mailto:you@example.com`. |
| `ALLOW_PLAINTEXT_PRODUCTION_SECRETS` | `false` | Legacy local/test compatibility only. Production always rejects plaintext secret providers. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://lifeledger.jpreinold.com,https://www.lifeledger.jpreinold.com` | Comma-separated frontend origins allowed to call the API. |
| `DOCUMENT_STORAGE_MODE` | `disabled` locally, `s3` in production defaults | `disabled`, `local`, or `s3`. Local/SAM local is explicitly disabled. |
| `DOCUMENTS_QUARANTINE_BUCKET` | empty | Private S3 quarantine bucket for presigned browser uploads. |
| `DOCUMENTS_CLEAN_BUCKET` | empty | Private S3 clean bucket for scan-passed validated downloads. |
| `DOCUMENTS_KMS_KEY_ARN` | empty | Dedicated document KMS key ARN for S3 SSE-KMS. |
| `ATTACHMENT_MAX_SIZE_BYTES` | `10485760` | Maximum attachment size, 10 MB by default. |
| `ATTACHMENT_MAX_PER_RECORD` | `5` | Maximum active attachments per record. |

`DOCUMENT_STORAGE_MODE=local` is accepted for future compatibility but currently fails closed like `disabled`; this backend does not present local temp files as secure document storage.

Generate VAPID keys with `npx web-push generate-vapid-keys`. The backend receives `VAPID_PUBLIC_KEY`, `PUSH_SECRET_ARN`, and `VAPID_SUBJECT`; the frontend receives only `VITE_VAPID_PUBLIC_KEY`. Google Calendar sync requires a Google Cloud OAuth web client, an OAuth consent screen/test users for private beta, and an authorized redirect URI that exactly matches `GOOGLE_OAUTH_REDIRECT_URI`. The Google client secret and VAPID private key stay backend-only in Secrets Manager for production. Existing Google Calendar connections may need to reconnect once to grant the CalendarList read-only scope used by the calendar picker.

Local protected-field testing can use a generated base64 32-byte key:

```powershell
$keyBytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($keyBytes)
$env:RECORD_ENCRYPTION_MODE = "local"
$env:LOCAL_RECORDS_ENCRYPTION_KEY = [Convert]::ToBase64String($keyBytes)
python -m uvicorn app.main:app --reload --port 8000
```

If local encryption is enabled without a key, protected-field writes fail closed. Existing non-protected records continue to work.

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
$env:LOCAL_LINKED_ITEMS_FILE = "data/linked-items.json"
python -m uvicorn app.main:app --reload --port 8000
```

DynamoDB mode is only used when explicitly enabled:

```powershell
$env:PERSISTENCE_MODE = "dynamodb"
$env:REMINDERS_TABLE_NAME = "lifeledger-reminders-auth"
$env:RECORDS_TABLE_NAME = "lifeledger-records-auth"
$env:LINKED_ITEMS_TABLE_NAME = "lifeledger-linked-items-auth"
$env:AWS_REGION = "us-east-1"
python -m uvicorn app.main:app --reload --port 8000
```

Do not use DynamoDB mode locally unless AWS credentials and the auth-scoped table are configured.

Reminder, record, and linked item rows are scoped by `user_id`. The deployed reminder and record tables use `user_id` as the partition key and item `id` as the sort key. The linked items table uses `user_id` plus `link_id`, with `SourceLinksIndex` and `TargetLinksIndex` for one-hop traversal without scans. The records and linked items tables are separate from reminders and retained for future document, search, dashboard, and AI retrieval work.

## Serverless Deployment Shape

`lambda_handler.py` exposes:

```python
handler = Mangum(app)
```

SAM uses that handler and routes HTTP API requests into the same FastAPI app. The template also creates Cognito resources, an HTTP API JWT authorizer, an unauthenticated `OPTIONS /{proxy+}` route for browser preflight, a retained customer-managed data KMS key and alias, a separate retained document KMS key and alias, retained DynamoDB tables for reminders, records, linked items, record attachments, preferences, push subscriptions, Google Calendar connections, and OAuth states, retained private S3 quarantine/clean document buckets, a GuardDuty Malware Protection plan with managed tagging, an EventBridge scan-result finalizer Lambda, a scheduled Daily Digest push Lambda, and scoped CRUD/KMS/S3/Secrets Manager permissions for the Lambda functions. The API Lambda can use the linked items table and the data KMS key with encryption context `app=lifeledger`; the Digest push Lambda can read only the push secret and cannot decrypt protected records or access linked items/document buckets.

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
http://127.0.0.1:3000/records/{record_id}/links
```

When local persistence runs inside Lambda or SAM local, JSON data writes to `/tmp/lifeledger-reminders.json`, `/tmp/lifeledger-records.json`, `/tmp/lifeledger-linked-items.json`, and the other `/tmp/lifeledger-*.json` persistence files because the function task directory may be read-only.

Run the scheduled Daily Digest push logic manually in local/dev without exposing a route:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python run_digest_push.py
```

Production startup rejects local auth/persistence, disabled protected-record encryption, missing Cognito/KMS/document settings, unsafe CORS origins, and prohibited local secret providers before serving requests. backend/env.local.json keeps local development explicit and unchanged.

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
RecordEncryptionMode=kms
DocumentStorageMode=s3
MalwareProtectionEnabled=true
RemindersTableName=lifeledger-reminders-auth
RecordsTableName=lifeledger-records-auth
RecordAttachmentsTableName=lifeledger-record-attachments-auth
LinkedItemsTableName=lifeledger-linked-items-auth
CorsAllowedOrigins=https://lifeledger.jpreinold.com,https://www.lifeledger.jpreinold.com
VapidPublicKey=<public-vapid-key>
PushSecretArn=<secrets-manager-arn-with-vapid_private_key>
VapidSubject=mailto:you@example.com
GoogleClientId=<google-oauth-web-client-id>
GoogleOAuthSecretArn=<secrets-manager-arn-with-client_secret>
GoogleOAuthRedirectUri=<authorized-google-oauth-redirect-uri>
GoogleCalendarScopes=https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly
```

`sam deploy --guided` creates `samconfig.toml` for your local AWS account and deployment choices. That file is ignored by git. Use `samconfig.example.toml` as a fail-closed production reference that does not include credentials or local profile names. Replace its placeholder account IDs, secret ARNs, and public client values before use.

## Search Projection Reconciliation

Projection failures are persisted as safe identifiers only. Rebuild one item:

```powershell
python backfill_search.py --user-id <user-id> --entity-type record --entity-id <record-id>
```

Rebuild a user's bounded source set, retry failures, repair stale projection versions, and remove verified orphans:

```powershell
python backfill_search.py --user-id <user-id> --limit 1000
```

Add `--dry-run` for a read-only count. If the bound truncates a source collection, orphan deletion is skipped for safety. Protected payloads are never decrypted or indexed by reconciliation.