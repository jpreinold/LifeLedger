# LifeLedger

LifeLedger is a private personal admin hub for tracking important reminders, renewals, maintenance tasks, and records.

LifeLedger now has a unified smart reminder experience across regular reminders, birthdays, renewals/expirations, and maintenance. It also has an in-app alert/attention foundation: the bell and Alert Center surface reminders that need attention, and alert state supports dismissing or snoozing those in-app alerts. The Daily Digest gives a short briefing of what needs attention today, what is due today, and what is coming up, using the same smart reminder labels and alert logic as the Alert Center. Optional Daily Digest push notifications can send one summary-level browser push at the user's selected digest time when there is meaningful reminder activity. Google Calendar sync is available as a one-way, per-reminder integration from LifeLedger to the user's selected Google Calendar. Records are now first-class, structured personal entities that users can create, view, edit, archive, restore, and delete, with optional protected details encrypted at the application layer before persistence. Google OAuth token bundles are also application-encrypted when encryption is enabled. Email, SMS, public sign-up, document uploads, AI, and automatic record-to-reminder generation are not included. Local development still defaults to JSON persistence and a local dev user; deployed reminders, records, digest preferences, alert state, and push subscriptions are protected by Amazon Cognito and scoped by user in DynamoDB.

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

Reminder records store optional delivery preference fields: `reminder_lead_value`, `reminder_lead_unit`, and `reminder_time`. The UI defaults new reminders to 1 day before at 9:00 AM and supports same day, 1 day before, 1 week before, 1 month before, and a simple custom lead time. These fields now feed the in-app alert eligibility window and prepare LifeLedger for future per-reminder delivery, calendar, and email integrations; this phase only sends the optional Daily Digest push summary, not per-reminder custom pushes, email, or SMS.

Reminder records also support `reminder_type`. Existing reminders default to `generic`; smart types are `birthday`, `renewal`, and `maintenance`. Birthday reminders may include `birthday_details`; they calculate the next birthday date, infer birth year when the user enters the age someone is turning, and show labels such as turning age or age unknown on cards and dashboard rows. Renewal reminders may include `renewal_details` for safe renewal, expiration, review, subscription, free trial, warranty, or document dates. Maintenance reminders may include `maintenance_details` with item name, maintenance area, last completed date, interval, next due date, and general instructions. Maintenance is date-based only; mileage-based and usage-based maintenance are not included yet.

The bell opens an in-app Alert Center backed by `GET /alerts`. Alerts are reminders that are active, have a due date, are overdue, due today, or inside their configured reminder timing window, and are not currently dismissed or snoozed. The same alert set powers the bell badge and Home dashboard Needs attention section. Alert actions can complete, dismiss for now, snooze until tomorrow morning, or open the existing edit flow.

The Home dashboard includes a Daily Digest card. Opening it shows a near-full-height briefing drawer with Needs attention, Due today, Coming up, and compact smart reminder summaries. Digest items open the existing reminder detail drawer. Digest preferences live in Settings and include enabled status, digest time, lookahead window, timezone, and last-seen tracking. Push Notifications in Settings are optional and user-enabled; they use the same Daily Digest preferences and timezone, store subscriptions under the authenticated user only, and send summary-level content such as counts for needs attention, due today, and coming up. Google Calendar sync is one-way from LifeLedger to Google Calendar for reminders the user explicitly selects.

The reminder list now uses the top status cards as filters: All active, Overdue, Due today, and Due this month. The smart type chips remain as the only chip row: All types, Reminders, Birthdays, Renewals, and Maintenance. Status cards and type chips combine, and empty states describe the active filter where possible.

## Records Foundation

Records are source-of-truth personal details, separate from reminders. Users can create, view, edit, archive, restore, and delete records from the Records tab, the Home quick action, or the center plus action sheet. Records do not create reminders, alerts, push notifications, or calendar events yet.

Supported record types are `general`, `passport`, `driver_license`, `vehicle`, `insurance`, `appliance`, `pet`, `home`, `subscription`, and `warranty`. The shared safe model stores `record_type`, `title`, optional `subtitle`, `category`, optional owner/provider or brand, safe dates, `location_hint`, `notes`, normalized `tags`, `status`, and backend-owned timestamps.

Privacy guardrails are intentional. Normal record metadata stays safe and searchable: type, title, subtitle, category, owner display name, provider/brand, dates, broad location hint, non-sensitive notes, tags, and status. The frontend must not send `user_id`; the backend derives ownership from Cognito or local auth.

## Encrypted Records And Security Boundary

Cognito authenticates deployed users before private routes reach the backend, and the FastAPI layer still derives ownership from the authenticated Cognito context. Repositories enforce user ownership with `user_id` partitioning, and the frontend never sends or controls `user_id`. DynamoDB server-side encryption with a customer-managed KMS key and point-in-time recovery are defense in depth. Protected record fields receive application-level envelope encryption before DynamoDB storage, and only the API Lambda receives KMS permissions to request data-key generation and decryption. The Daily Digest scheduled Lambda does not receive record-decryption permissions.

This is not zero-knowledge or end-to-end encryption. The authenticated LifeLedger backend can decrypt protected fields after it verifies that the record belongs to the current user and the user explicitly requests reveal. Ordinary list/detail APIs, Daily Digest, push payloads, calendar event descriptions, URLs, service-worker caches, and record cards do not include protected plaintext.

Protected fields are stored separately from normal metadata. Supported protected fields are `document_number`, `license_number`, `vin`, `policy_number`, `member_number`, `serial_number`, `account_reference`, and `sensitive_notes`, with fields limited by record type. LifeLedger still does not support storing SSNs, payment card data, bank account or routing numbers, passwords, PINs, MFA or recovery codes, private keys, API keys, authentication credentials, highly sensitive medical records, file uploads, images, scans, OCR, AI/RAG, shared household access, or global search over protected fields.

Protected record routes:

- `GET /records/{id}/protected/status` returns safe metadata only.
- `PUT /records/{id}/protected` replaces protected fields after ownership validation and immediate encryption.
- `GET /records/{id}/protected` explicitly reveals plaintext after ownership validation and returns `Cache-Control: no-store, private`.
- `DELETE /records/{id}/protected` clears the encrypted protected payload and leaves normal record metadata intact.

Envelope encryption flow:

1. The backend serializes the protected payload as canonical UTF-8 JSON.
2. In KMS mode, the API Lambda calls KMS `GenerateDataKey` for the LifeLedger data key. In local mode, a per-payload data key is wrapped with `LOCAL_RECORDS_ENCRYPTION_KEY`.
3. The backend encrypts locally with AES-256-GCM and a fresh 12-byte nonce.
4. Authenticated additional data uses non-secret context: `app=lifeledger`, `purpose`, hashed owner id, resource id, and encryption version.
5. DynamoDB stores ciphertext, encrypted data key, nonce, encryption version, key reference, protected field names, and protected update time. Plaintext protected fields and plaintext data keys are not stored.

Google Calendar OAuth tokens use the same encryption service with `purpose=google-oauth-token`, owner hash, and `resource_id=google-calendar`. Legacy connection items with plaintext `access_token` or `refresh_token` are migrated lazily after the owned connection is loaded: LifeLedger encrypts the token bundle, writes encrypted token fields, then removes plaintext token attributes only after the encrypted save succeeds.

## Google Calendar Sync

Google Calendar sync is one-way: LifeLedger creates, updates, and deletes Google Calendar events for selected LifeLedger reminders only. LifeLedger does not read Google Calendar events, import events, process Google Calendar edits, or invite attendees in this MVP. Synced reminders are all-day events on the user's selected writable Google Calendar. The primary calendar is the default until the user chooses a different calendar in Settings.

Setup requires a Google Cloud project:

1. Configure the OAuth consent screen and add private-beta test users as needed.
2. Create an OAuth client of type **Web application**.
3. Add the authorized redirect URI. It must exactly match `GOOGLE_OAUTH_REDIRECT_URI`. For the frontend callback flow, this should be the LifeLedger frontend URL that receives `code` and `state`.
4. Store the OAuth client secret in AWS Secrets Manager as `{"client_secret":"..."}` and deploy the backend with `GOOGLE_CLIENT_ID`, `GOOGLE_OAUTH_SECRET_ARN`, `GOOGLE_OAUTH_REDIRECT_URI`, and `GOOGLE_CALENDAR_SCOPES`. The default scopes are `https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly`.

Existing Google Calendar connections created before the calendar picker may need to reconnect once so Google grants the CalendarList read-only scope needed to show writable calendars.

The Google client secret is backend-only secret material and should live in AWS Secrets Manager in production. Do not put it in Cloudflare, Vite, browser storage, Lambda plaintext environment variables, SAM config, or git. Cloudflare Pages does not need Google OAuth client configuration for this flow; the frontend starts OAuth by calling the authenticated backend.

When Google Calendar is not configured, Settings shows a friendly not-configured state and the rest of the app continues to work.

## Push Notifications

Generate VAPID keys when setting up browser push:

```powershell
npx web-push generate-vapid-keys
```

Cloudflare Pages gets only `VITE_VAPID_PUBLIC_KEY`. AWS/SAM gets `VapidPublicKey`, `VapidSubject`, and `PushSecretArn`. Store the VAPID private key in AWS Secrets Manager as `{"vapid_private_key":"..."}`. The private key is backend-only secret material and must not be committed or placed in production Lambda plaintext environment variables.

To enable push, deploy both sides with those values, open Settings, and use **Enable push notifications** in the Push Notifications section. After the browser grants permission and an active subscription appears, use **Send test push** to send a summary-only notification to the current signed-in user. The test payload contains no reminder details and opens `/?openDigest=1`.

Troubleshooting notes:

- Browser unsupported: use a browser/PWA install mode that supports service workers, Notification, and Push API.
- Permission denied: re-enable notifications for the site in browser settings.
- Frontend key missing: set `VITE_VAPID_PUBLIC_KEY` in Cloudflare or `frontend/.env.local`, then rebuild/restart Vite.
- Backend config missing: deploy AWS/SAM with `VapidPublicKey`, `PushSecretArn`, and `VapidSubject`.
- No active subscription: click **Enable push notifications** first.
- Digest disabled: turn Daily Digest back on in Settings.
- Digest not due yet: scheduled sends only run near the saved local digest time.
- Empty digest: scheduled sends skip users with no meaningful digest content.
- Duplicate already sent today: scheduled sends skip a user after a successful Daily Digest push for that user's local day.

For local/dev scheduler verification without waiting for EventBridge:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python run_digest_push.py
```

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
| `VITE_VAPID_PUBLIC_KEY` | Public VAPID key for browser Push API subscription |

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
- DynamoDB stores records under the authenticated user's `user_id` in a separate records table.

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
- `GET /records` requires authentication in Cognito mode and returns active records by default. `include_archived=true` also returns archived records.
- `POST /records` requires authentication in Cognito mode and creates a record for the current user only.
- `GET /records/{id}` requires authentication in Cognito mode and returns only an owned record.
- `PUT /records/{id}` requires authentication in Cognito mode and updates only an owned record.
- `GET /records/{id}/protected/status` requires authentication in Cognito mode and returns safe protected-field status only for an owned record.
- `PUT /records/{id}/protected` requires authentication in Cognito mode and encrypts/replaces protected fields only for an owned record.
- `GET /records/{id}/protected` requires authentication in Cognito mode, explicitly reveals protected fields only for an owned record, and returns no-store headers.
- `DELETE /records/{id}/protected` requires authentication in Cognito mode and clears only the encrypted protected payload for an owned record.
- `POST /records/{id}/archive` requires authentication in Cognito mode and archives only an owned record.
- `POST /records/{id}/restore` requires authentication in Cognito mode and restores only an owned record.
- `DELETE /records/{id}` requires authentication in Cognito mode and deletes only an owned record.
- `GET /preferences/digest` requires authentication in Cognito mode.
- `PUT /preferences/digest` requires authentication in Cognito mode.
- `GET /push/config` requires authentication in Cognito mode.
- `GET /push/status` requires authentication in Cognito mode and returns safe diagnostics for the current user only.
- `GET /push/subscriptions` requires authentication in Cognito mode and returns only the current user's active subscriptions.
- `POST /push/subscriptions` requires authentication in Cognito mode and stores/updates only the current user's subscription. The frontend must not send `user_id`.
- `POST /push/test` requires authentication in Cognito mode and sends a summary-only test push to the current user's active subscriptions only.
- `DELETE /push/subscriptions/{subscription_id}` requires authentication in Cognito mode and disables only a subscription owned by the current user.
- `GET /integrations/google-calendar/status` requires authentication and returns the current user's safe Google Calendar connection status.
- `POST /integrations/google-calendar/connect` requires authentication and returns a Google OAuth authorization URL.
- `POST /integrations/google-calendar/callback` requires authentication and exchanges an authorization code after validating a user-scoped, expiring OAuth state.
- `DELETE /integrations/google-calendar/disconnect` requires authentication and disconnects only the current user's Google Calendar integration.
- `POST /reminders/{id}/calendar-sync/enable` requires authentication and creates an all-day Google Calendar event for an owned reminder.
- `POST /reminders/{id}/calendar-sync/disable` requires authentication and deletes or safely clears the owned reminder's Google Calendar event metadata.

## Backend Architecture

- FastAPI owns the routes in `backend/app/main.py`.
- Authentication helpers live in `backend/app/auth.py`.
- Pydantic validates request and response models in `backend/app/schemas.py`.
- Status, recurrence, and `next_due_date` logic live in `backend/app/recurrence.py`.
- Birthday reminder date, age, and label helpers live in `backend/app/birthdays.py`.
- Maintenance reminder interval, due-date, completion, and label helpers live in `backend/app/maintenance.py`.
- Route handlers depend on a repository abstraction, not a concrete storage backend.
- Local mode uses JSON-file persistence at `backend/data/reminders.json` and `backend/data/records.json`.
- DynamoDB mode uses `DynamoReminderRepository` and `DynamoRecordRepository` for AWS deployment.
- Config in `backend/app/config.py` chooses auth mode, persistence mode, CORS origins, table names, local data paths, and backend-only Google OAuth settings.
- Application encryption lives in `backend/app/encryption_service.py`; Secrets Manager retrieval and process-level secret caching live in `backend/app/secret_provider.py`.
- Records use `RecordRepository`, `LocalRecordRepository`, and `DynamoRecordRepository`, all keyed by backend-derived `user_id`.
- Digest preferences use a separate user-scoped preferences repository with local JSON and DynamoDB implementations.
- Google Calendar connections and OAuth states use separate user-scoped/short-lived repositories with local JSON and DynamoDB implementations. Google token bundles are encrypted before storage when record encryption is enabled, with legacy plaintext token items migrated lazily.
- Mangum adapts FastAPI to Lambda through `backend/lambda_handler.py`.
- `backend/template.yaml` describes the SAM serverless deployment shape.

Reminder and record items include an internal `user_id`. In local mode it is `local-dev-user`; in Cognito mode it is the Cognito `sub`. DynamoDB uses `user_id` as the partition key and item `id` as the sort key for reminders and records, so users cannot read or mutate each other's data through the repository layer. Reminder timing preferences, smart birthday fields, smart renewal fields, smart maintenance fields, and alert state fields such as `alert_dismissed_until`, `alert_snoozed_until`, and `alert_last_action_at` are stored on each reminder item without changing the DynamoDB key schema. Records are stored in a separate retained table so future documents, search, AI, and reminder links can be added without overloading reminder storage. Digest preferences are stored in a separate table keyed by `user_id`, so future notification scheduling can read per-user digest time, timezone, lookahead, enabled state, and last-seen state without changing reminder storage. Google Calendar tokens are stored in a separate connection table keyed by `user_id`; OAuth state is stored server-side and expires before token exchange is allowed.

## Environment Variables

Backend local development works without setting any variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `local` | Names the runtime environment. |
| `AUTH_MODE` | `local` | Use `local` for dev/SAM local or `cognito` for deployed Cognito auth. |
| `LOCAL_DEV_USER_ID` | `local-dev-user` | User id assigned in local auth mode. |
| `PERSISTENCE_MODE` | `local` | Use `local` for JSON or `dynamodb` for DynamoDB. |
| `REMINDERS_TABLE_NAME` | `lifeledger-reminders-auth` | DynamoDB table name when DynamoDB mode is enabled. |
| `RECORDS_TABLE_NAME` | `lifeledger-records-auth` | DynamoDB records table name when DynamoDB mode is enabled. |
| `PREFERENCES_TABLE_NAME` | `lifeledger-preferences-auth` | DynamoDB preferences table name when DynamoDB mode is enabled. |
| `AWS_REGION` | `us-east-1` | Region used by the DynamoDB repository. Lambda also provides this automatically. |
| `LOCAL_DATA_FILE` | `backend/data/reminders.json` locally, `/tmp/lifeledger-reminders.json` in Lambda/SAM local | JSON file used when `PERSISTENCE_MODE=local`. |
| `LOCAL_RECORDS_FILE` | `backend/data/records.json` locally, `/tmp/lifeledger-records.json` in Lambda/SAM local | JSON file used for records when `PERSISTENCE_MODE=local`. |
| `LOCAL_PREFERENCES_FILE` | `backend/data/preferences.json` locally, `/tmp/lifeledger-preferences.json` in Lambda/SAM local | JSON file used for digest preferences when `PERSISTENCE_MODE=local`. |
| `PUSH_SUBSCRIPTIONS_TABLE_NAME` | `lifeledger-push-subscriptions-auth` | DynamoDB push subscriptions table name when DynamoDB mode is enabled. |
| `LOCAL_PUSH_SUBSCRIPTIONS_FILE` | `backend/data/push-subscriptions.json` locally, `/tmp/lifeledger-push-subscriptions.json` in Lambda/SAM local | JSON file used for push subscriptions when `PERSISTENCE_MODE=local`. |
| `GOOGLE_CALENDAR_CONNECTIONS_TABLE_NAME` | `lifeledger-google-calendar-connections-auth` | DynamoDB Google Calendar connection table name when DynamoDB mode is enabled. |
| `GOOGLE_OAUTH_STATES_TABLE_NAME` | `lifeledger-google-oauth-states-auth` | DynamoDB OAuth state table name when DynamoDB mode is enabled. |
| `LOCAL_GOOGLE_CALENDAR_CONNECTIONS_FILE` | `backend/data/google-calendar-connections.json` locally, `/tmp/lifeledger-google-calendar-connections.json` in Lambda/SAM local | JSON file used for Google Calendar connections when `PERSISTENCE_MODE=local`. |
| `LOCAL_GOOGLE_OAUTH_STATES_FILE` | `backend/data/google-oauth-states.json` locally, `/tmp/lifeledger-google-oauth-states.json` in Lambda/SAM local | JSON file used for OAuth states when `PERSISTENCE_MODE=local`. |
| `RECORD_ENCRYPTION_MODE` | `disabled` | `disabled`, `local`, or `kms`. Production should use `kms`; local protected-field testing can use `local`. |
| `DATA_ENCRYPTION_KMS_KEY_ARN` | empty | KMS key ARN used in `kms` mode. SAM sets this from the stack key output. |
| `LOCAL_RECORDS_ENCRYPTION_KEY` | empty | Base64-encoded 32-byte local wrapping key for `RECORD_ENCRYPTION_MODE=local`. Never commit a real key. |
| `GOOGLE_CLIENT_ID` | empty | Google OAuth web client ID for Calendar sync. Backend/SAM only. |
| `GOOGLE_OAUTH_SECRET_ARN` | empty | Secrets Manager ARN for JSON `{"client_secret":"..."}` in production. |
| `GOOGLE_CLIENT_SECRET` | empty | Local-only plaintext fallback for development. Production disallows plaintext fallback unless explicitly overridden. |
| `GOOGLE_OAUTH_REDIRECT_URI` | empty | OAuth redirect URI registered in Google Cloud and used during code exchange. |
| `GOOGLE_CALENDAR_SCOPES` | `https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly` | Calendar event write scope plus CalendarList read-only scope for the Settings picker. |
| `VAPID_PUBLIC_KEY` | empty | Public VAPID key. Also set `VITE_VAPID_PUBLIC_KEY` in the frontend. |
| `PUSH_SECRET_ARN` | empty | Secrets Manager ARN for JSON `{"vapid_private_key":"..."}` in production. |
| `VAPID_PRIVATE_KEY` | empty | Local-only plaintext fallback for development. Do not commit a real value. |
| `VAPID_SUBJECT` | empty | VAPID contact subject, such as `mailto:you@example.com`. |
| `ALLOW_PLAINTEXT_PRODUCTION_SECRETS` | `false` | Set only for deliberate emergency compatibility. Production should use Secrets Manager. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://lifeledger.jpreinold.com,https://www.lifeledger.jpreinold.com` | Comma-separated frontend origins allowed to call the API. |

SAM parameters use `RecordEncryptionMode`, `GoogleOAuthSecretArn`, `VapidPublicKey`, `PushSecretArn`, and `VapidSubject`; Cloudflare Pages uses only `VITE_VAPID_PUBLIC_KEY`.

Local protected-field testing:

```powershell
$keyBytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($keyBytes)
$env:RECORD_ENCRYPTION_MODE = "local"
$env:LOCAL_RECORDS_ENCRYPTION_KEY = [Convert]::ToBase64String($keyBytes)
npm run backend
```

If `RECORD_ENCRYPTION_MODE=local` is set without `LOCAL_RECORDS_ENCRYPTION_KEY`, protected-field writes fail closed with `Protected record storage is not configured for this environment.` Existing non-protected records continue to work. Do not put a local encryption key in SAM, CloudFormation parameters, Cloudflare, GitHub, or git.

## Serverless Notes

The backend can still run locally with Uvicorn. Lambda support is additive: `backend/lambda_handler.py` imports the same FastAPI app and wraps it with Mangum.

The SAM template defines:

- A Cognito user pool with public sign-up disabled.
- A Cognito web app client without a client secret.
- An HTTP API with CORS and a Cognito JWT authorizer.
- An unauthenticated `OPTIONS /{proxy+}` route so browser preflight requests can complete before authenticated reminder calls.
- A Lambda function running FastAPI through Mangum.
- A retained customer-managed symmetric KMS key with rotation enabled and alias `alias/${AWS::StackName}-data`.
- A DynamoDB table named `lifeledger-reminders-auth` with `user_id` partition key and `id` sort key.
- A DynamoDB table named `lifeledger-records-auth` with `user_id` partition key and `id` sort key.
- A DynamoDB table named `lifeledger-preferences-auth` with `user_id` partition key for Daily Digest preferences.
- A DynamoDB table named `lifeledger-google-calendar-connections-auth` with `user_id` partition key for backend-only Google Calendar tokens.
- A DynamoDB table named `lifeledger-google-oauth-states-auth` with `state` partition key for expiring OAuth state validation.
- Customer-managed DynamoDB SSE-KMS and point-in-time recovery on retained data tables.
- API Lambda permissions for `kms:GenerateDataKey` and `kms:Decrypt` are scoped to the stack KMS key and require encryption context `app=lifeledger`.
- API Lambda Secrets Manager access is scoped to `GoogleOAuthSecretArn` and `PushSecretArn`; the Digest push Lambda may read only `PushSecretArn` and does not receive record KMS decrypt permissions.
- `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` on the KMS key and retained DynamoDB tables.

SAM local defaults to `AUTH_MODE=local` and `PERSISTENCE_MODE=local`, so it can serve `/health`, `/reminders`, `/records`, and `/preferences/digest` without Cognito login, AWS credentials, or DynamoDB calls. In Lambda/SAM local mode, local JSON persistence writes to `/tmp/lifeledger-reminders.json`, `/tmp/lifeledger-records.json`, `/tmp/lifeledger-preferences.json`, `/tmp/lifeledger-push-subscriptions.json`, `/tmp/lifeledger-google-calendar-connections.json`, and `/tmp/lifeledger-google-oauth-states.json` because the function code directory may be read-only.

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
RecordEncryptionMode=kms
RemindersTableName=lifeledger-reminders-auth
RecordsTableName=lifeledger-records-auth
CorsAllowedOrigins=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://lifeledger.jpreinold.com,https://www.lifeledger.jpreinold.com
VapidPublicKey=<public-vapid-key>
PushSecretArn=<secrets-manager-arn-with-vapid_private_key>
VapidSubject=mailto:you@example.com
GoogleClientId=<google-oauth-web-client-id>
GoogleOAuthSecretArn=<secrets-manager-arn-with-client_secret>
GoogleOAuthRedirectUri=<authorized-google-oauth-redirect-uri>
GoogleCalendarScopes=https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendarlist.readonly
```

SAM guided deploy creates `backend/samconfig.toml` for your machine/account. That file is ignored by git because it can contain local deployment choices. Use `backend/samconfig.example.toml` as a safe reference, then run:

```powershell
cd backend
sam deploy --guided
```

## Deployment Checklist

- `npm run check` passes.
- Backend is deployed with `AuthMode=cognito`, `PersistenceMode=dynamodb`, and `RecordEncryptionMode=kms`.
- AWS `/health` works without signing in.
- AWS `/reminders` rejects requests without a bearer token.
- AWS `/records` rejects requests without a bearer token.
- Cognito admin-created user can sign in.
- Cloudflare Pages has all required `VITE_*` environment variables, including `VITE_VAPID_PUBLIC_KEY` for push subscriptions.
- Cloudflare frontend can load, create, complete, and delete reminders after sign-in.
- Cloudflare frontend can create, edit, archive, restore, and delete records after sign-in.
- AWS is redeployed with the records table, push subscription table, scheduled sender, KMS key, secret ARN parameters, Google Calendar connection/state tables, and Google OAuth backend parameters.
- Cloudflare is redeployed with `VITE_VAPID_PUBLIC_KEY` and the updated Calendar sync and Records UI.
- Settings shows short, user-facing push and Google Calendar statuses; technical diagnostics are not part of the normal UI.
- Enabling push creates an active subscription, and **Send test push** delivers a summary-only test notification.
- The scheduled digest sender can be run or observed and does not duplicate pushes for the same local day.
- Google Calendar connect, callback, per-reminder sync, edit update, disable cleanup, and disconnect flows are tested with a private-beta Google account.
- `frontend/.env.local`, AWS credentials, Google secrets, OAuth tokens, and local deployment files are not committed.

Production security verification:

- KMS key exists, has rotation enabled, and is retained.
- API Lambda has limited KMS access to the LifeLedger key; Digest Lambda lacks record-decryption access.
- `GOOGLE_OAUTH_SECRET_ARN` and `PUSH_SECRET_ARN` are present, while plaintext `GOOGLE_CLIENT_SECRET` and `VAPID_PRIVATE_KEY` are absent from production Lambda environments.
- Secrets Manager secret JSON shapes are `{"client_secret":"..."}` and `{"vapid_private_key":"..."}`.
- A protected record DynamoDB item contains ciphertext, encrypted data key, nonce, and safe field names only.
- A Google Calendar connection item contains no plaintext `access_token` or `refresh_token` after migration.
- Reveal works only for the owning authenticated user and returns no-store headers.
- DynamoDB PITR is enabled on retained data tables.
- CloudTrail shows expected KMS activity, and CloudWatch logs do not contain protected plaintext, OAuth tokens, Google client secret, VAPID private key, ciphertext, encrypted data keys, or KMS plaintext data keys.

Rollback notes:

- Disabling or deleting the KMS key makes encrypted protected records and encrypted Google token bundles unavailable.
- The KMS key is retained and should not be scheduled for deletion automatically.
- Rollbacks should not remove encrypted fields or delete protected payloads.
- Legacy Google token support remains in place for this phase so existing connections can migrate safely.
- Keep `protected_encryption_version` and token encryption version fields for future migrations.

## Not In This Phase

This phase does not add two-way Google Calendar sync, Google Calendar import, Google Calendar edit ingestion, attendees, shared calendars, email sending, SMS, password-manager functionality, AI/RAG, OCR, global search over protected fields, file uploads, photos, social login, public registration, mileage-based maintenance, usage-based maintenance, supply inventory, automatic record-to-reminder generation, custom per-reminder push rules, notification history, shared households, roles/admin dashboards, or another frontend redesign. Do not store SSNs, payment card numbers, bank account or routing numbers, passwords, PINs, MFA/recovery codes, private keys, API keys, authentication credentials, highly sensitive medical records, or uploaded documents in reminders or records. Future smart reminder work may include usage-based maintenance, record-linked reminders, secure file storage, search, AI, and calendar or notification integrations.
