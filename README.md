# LifeLedger

LifeLedger is a personal admin hub for tracking important reminders, renewals, maintenance tasks, and records.

LifeLedger now has a unified smart reminder experience across regular reminders, birthdays, renewals/expirations, and maintenance. It also has an in-app alert/attention foundation: the bell and Alert Center surface reminders that need attention, and alert state supports dismissing or snoozing those in-app alerts. The Daily Digest gives a short briefing of what needs attention today, what is due today, and what is coming up, using the same smart reminder labels and alert logic as the Alert Center. Optional Daily Digest push notifications can send one summary-level browser push at the user's selected digest time when there is meaningful reminder activity. Google Calendar sync is available as a one-way, per-reminder integration from LifeLedger to the user's selected Google Calendar. Records are now first-class, structured personal entities that users can create, view, edit, archive, restore, delete, preview, attach scanned PDF/JPEG/PNG files to after malware scanning, and link to related records and reminders. Guided tracking can compose those capabilities for passport expiration, vehicle registration, pet vaccination, and subscription renewal. Optional protected details are encrypted at the application layer before persistence. Google OAuth token bundles are also application-encrypted when encryption is enabled. Email, SMS, public sign-up, OCR, AI/RAG, file sharing, and unprompted automatic record-to-reminder generation are not included. Local development still defaults to JSON persistence and a local dev user; deployed reminders, records, linked items, record attachments, digest preferences, alert state, and push subscriptions are protected by Amazon Cognito and scoped by user in DynamoDB.

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

## Guided Tracking

The Add experience and compatible item Responsibility sections offer four guided workflows: passport expiration, vehicle registration, pet vaccination, and subscription renewal. Each uses one shared configuration-driven drawer to create or reuse the correct item, collect relevant details, create an ordinary reminder, connect it with the existing relationship API, and optionally upload a scanned document to the item.

Guided setup is recoverable rather than falsely transactional. Creation requests use user-scoped idempotency keys, successful operation IDs stay in active memory, and a retry runs only unfinished work. Protected drafts never enter local storage or persistent workflow state and are cleared when the flow closes. Existing generic item, reminder, detail, protected-detail, document, and related-item tools remain available. See [docs/guided-workflows.md](docs/guided-workflows.md) for mappings and extension rules.

## Reminder Management

Reminders can be created, edited, completed, and deleted from the React app. Editing uses the authenticated `PUT /reminders/{id}` route and only sends user-editable reminder fields.

Reminder records store optional delivery preference fields: `reminder_lead_value`, `reminder_lead_unit`, and `reminder_time`. The UI defaults new reminders to 1 day before at 9:00 AM and supports same day, 1 day before, 1 week before, 1 month before, and a simple custom lead time. These fields now feed the in-app alert eligibility window and prepare LifeLedger for future per-reminder delivery, calendar, and email integrations; this phase only sends the optional Daily Digest push summary, not per-reminder custom pushes, email, or SMS.

Reminder records also support `reminder_type`. Existing reminders default to `generic`; smart types are `birthday`, `renewal`, and `maintenance`. Birthday reminders may include `birthday_details`; they calculate the next birthday date, infer birth year when the user enters the age someone is turning, and show labels such as turning age or age unknown on cards and dashboard rows. Renewal reminders may include `renewal_details` for safe renewal, expiration, review, subscription, free trial, warranty, or document dates. Maintenance reminders may include `maintenance_details` with item name, maintenance area, last completed date, interval, next due date, and general instructions. Maintenance is date-based only; mileage-based and usage-based maintenance are not included yet.

The Reminders tab is now an Action Center. The backend returns a normalized derived reminder status from persisted reminder fields, and the frontend groups active reminders into Overdue, Due today, Due soon, and Later. Completed reminders are excluded from active groups and remain available through the Completed filter.

Reminder lifecycle state separates persisted state from derived urgency. Persisted fields include the meaningful `due_date`, completion metadata, optional `snoozed_until`, optional `archived_at`, and lightweight `lifecycle_events`. Derived statuses are calculated centrally as Completed, Overdue, Due today, Urgent, Upcoming, or Scheduled. The default windows are: overdue before the current local date, due today on the current local date, urgent within 7 calendar days, upcoming within 30 calendar days, and scheduled beyond 30 days. Date-only due dates stay date-only so local calendar dates do not shift through UTC conversion.

Snoozing sets `snoozed_until` and defers attention without changing `due_date`, renewal dates, expiration dates, or record dates. Clearing a snooze restores the effective attention date to the underlying important date. Renewing is distinct from completing: renewable reminders keep one reminder entity, record a `renewed` lifecycle event with the previous and new dates, clear obsolete snooze/alert state, advance the current active date, and update linked record renewal/expiration dates when they matched the prior cycle.

The bell still opens an in-app Alert Center backed by `GET /alerts`. Alerts are active reminders that are overdue, due today, or inside their configured reminder timing window and are not currently dismissed or snoozed. Alert actions can complete, dismiss for now, snooze until tomorrow morning, or open reminder details.

The Home dashboard includes a Daily Digest card. Opening it shows a near-full-height briefing drawer with Needs attention, Due today, Coming up, and compact smart reminder summaries. Digest items open the existing reminder detail drawer. Digest preferences live in Settings and include enabled status, digest time, lookahead window, timezone, and last-seen tracking. Push Notifications in Settings are optional and user-enabled; they use the same Daily Digest preferences and timezone, store subscriptions under the authenticated user only, and send summary-level content such as counts for needs attention, due today, and coming up. Google Calendar sync is one-way from LifeLedger to Google Calendar for reminders the user explicitly selects.

The reminder list uses top status cards as filters: Action Center, Overdue, Upcoming, and Completed. Smart type chips remain the type row: All types, Reminders, Birthdays, Renewals, and Maintenance. Status cards and type chips combine, empty states describe the active filter, and action buttons are disabled while lifecycle requests are in flight to reduce double submissions.

## Records Foundation

Records are source-of-truth personal details, separate from reminders. Users can create, view, edit, archive, restore, and delete records from the Records tab, the Home quick action, or the center plus action sheet. Records do not create reminders, alerts, push notifications, or calendar events yet.

Supported record types are `general`, `passport`, `driver_license`, `vehicle`, `insurance`, `appliance`, `pet`, `home`, `subscription`, and `warranty`. The shared safe model stores `record_type`, `title`, optional `subtitle`, `category`, optional owner/provider or brand, safe dates, `location_hint`, `notes`, normalized `tags`, `status`, and backend-owned timestamps.

Privacy guardrails are intentional. Normal record metadata stays safe and searchable: type, title, subtitle, category, owner display name, provider/brand, dates, broad location hint, non-sensitive notes, tags, and status. The frontend must not send `user_id`; the backend derives ownership from Cognito or local auth.

## Editable Dashboards And Dynamic Fields

LifeLedger treats Records and Reminders as editable dashboards rather than fixed database forms. Templates provide a small set of useful starting fields, while optional and custom fields can be added over time. Empty fields are hidden, sensitive values are encrypted and masked by default, and the interface reveals complexity only when the user needs it.

Record detail opens as a compact dashboard with Overview, Documents, and Linked items tabs. Overview shows populated essentials, important dates, additional details, notes, and history without blank rows or "not provided" placeholders. Documents and Linked Items remain first-class tabs backed by the existing secure attachment and linked-item systems.

Record templates are starting points, not forced schemas. Each record type defines required core fields, default suggested metadata, optional suggested metadata, dynamic field presets, sensitive field presets, and display order. The record form opens with Essentials first, then lets the user expand Dates, Additional details, and Notes. Existing populated optional fields remain visible when editing old records, so users do not need to recreate data.

Records support bounded dynamic fields embedded on the existing record item: `field_id`, `key`, `label`, `field_type`, `value`, `is_sensitive`, `display_order`, `select_options`, `created_at`, and `updated_at`. Supported field types are text, long text, date, number, money, phone, email, URL, boolean, and select. Dynamic fields intentionally do not support executable code, HTML, arbitrary JSON, nested schemas, file fields, password field types, SSNs, card/bank data, passwords, or recovery codes.

The storage tradeoff is deliberately cost-conscious: dynamic fields live on the existing user-scoped Records item instead of a new table. This keeps local JSON persistence, DynamoDB PAY_PER_REQUEST usage, ownership checks, backups, and deployment shape simple. The implementation avoids scans and does not add AI, OCR, embeddings, OpenSearch, Neptune, a vector database, automation, scheduled migrations, or another managed database.

Field privacy has three internal categories: system/indexed metadata needed for filtering and app behavior, private metadata that can appear in dashboards, and sensitive masked data. Users do not see or choose those categories in normal flows. Dynamic sensitive values are encrypted into the existing protected record envelope, masked as `••••••••` in the UI, and revealed only through owner-checked no-store API calls. Revealed values auto-hide after about 60 seconds, when the drawer closes, when the app loses visibility, and when the user navigates away or signs out. Revealed values are not persisted to browser storage or service-worker caches.

Quick Add remains available from the center plus action, Home, Records, Reminders, and Calendar date flows. Record Quick Add starts from the selected template with only essentials and high-value suggested fields visible, then opens the new record dashboard after save. Reminder add/edit uses compact sections for Essentials, Smart details, Schedule, and More options while preserving birthday, renewal, maintenance, Google Calendar, Daily Digest, push, and alert calculations.

Backward compatibility is adapter-based. Existing record metadata, protected-field payloads, documents, linked items, reminder calculations, Calendar sync, Daily Digest behavior, alert state, and push behavior continue to use their existing storage. Legacy protected fields remain revealable and clearable, while new sensitive dynamic fields share the same encrypted envelope without deleting legacy protected values.

## Linked Items Virtual Knowledge Graph

Linked Items make a record or reminder a personal hub for related LifeLedger items without adding a graph database or new AI service. The backend stores explicit user-created edges in the retained `lifeledger-linked-items-auth` DynamoDB table and resolves one-hop neighborhoods in the application layer with indexed DynamoDB queries. This keeps the feature low cost, simple to operate, and aligned with the existing user-scoped storage model.

Supported links are record-to-record and record-to-reminder. Record detail and edit views show linked records and reminders; reminder detail views show the records linked to that reminder. The mobile UI follows the same compact drawer patterns as records and reminders: choose Record or Reminder, search/filter items the user already owns, choose a relationship, optionally add a short label, and see the linked item appear immediately.

Relationships are explicit user choices such as insurance for, warranty for, renews, maintains, belongs to, covers, and related. LifeLedger does not infer links, create reminders from records, read protected fields for matching, or run AI/RAG over the graph in this phase. Linked item responses expose safe summaries only, never protected record values, attachment objects, or `user_id`.

Deleting a link removes only the connection. The source record, target record, or target reminder remains intact. Deleting a record or reminder cleans up its associated link rows so future one-hop queries do not return orphaned relationships.

The DynamoDB table is keyed by authenticated `user_id` plus `link_id`, with `SourceLinksIndex` and `TargetLinksIndex` for fast source/target lookups. The frontend never sends ownership fields; the API derives the user from Cognito/local auth, verifies both linked entities belong to that user, rejects self-links and duplicates, and stores only the relationship metadata. This virtual knowledge graph can support future search, dashboards, and AI retrieval, but those retrieval and inference features are intentionally not included yet.

## Encrypted Records And Security Boundary

Cognito authenticates deployed users before private routes reach the backend, and the FastAPI layer still derives ownership from the authenticated Cognito context. Repositories enforce user ownership with `user_id` partitioning, and the frontend never sends or controls `user_id`. DynamoDB server-side encryption with a customer-managed KMS key and point-in-time recovery are defense in depth. Protected record fields receive application-level envelope encryption before DynamoDB storage, and only the API Lambda receives KMS permissions to request data-key generation and decryption. The Daily Digest scheduled Lambda does not receive record-decryption permissions.

This is not zero-knowledge or end-to-end encryption. The authenticated LifeLedger backend can decrypt protected fields after it verifies that the record belongs to the current user and the user explicitly requests reveal. Ordinary list/detail APIs, Daily Digest, push payloads, calendar event descriptions, URLs, service-worker caches, and record cards do not include protected plaintext.

Protected fields are stored separately from normal metadata. Legacy protected fields are `document_number`, `license_number`, `vin`, `policy_number`, `member_number`, `serial_number`, `account_reference`, and `sensitive_notes`, with fields limited by record type. Dynamic sensitive fields are stored in the same encrypted protected envelope under an internal `dynamic_fields` payload and are returned masked by ordinary list/detail APIs. LifeLedger still does not support storing SSNs, payment card data, bank account or routing numbers, passwords, PINs, MFA or recovery codes, private keys, API keys, authentication credentials, highly sensitive medical records, OCR, AI/RAG, shared household access, file sharing, public links, reminder attachments, or global search over protected fields/files.

Protected record routes:

- `GET /records/{id}/protected/status` returns safe metadata only.
- `PUT /records/{id}/protected` replaces protected fields after ownership validation and immediate encryption.
- `GET /records/{id}/protected` explicitly reveals plaintext after ownership validation and returns `Cache-Control: no-store, private`.
- `DELETE /records/{id}/protected` clears the encrypted protected payload and leaves normal record metadata intact.

## Secure Record Document Storage

Records can have up to five active PDF, JPEG, or PNG attachments, each limited to 10 MB. The frontend never sends `user_id`; the backend derives ownership from Cognito/local auth, verifies the record belongs to that user, and stores attachment metadata in `lifeledger-record-attachments-auth` using `user_id` plus `<record_id>#<attachment_id>`. Normal attachment responses never include object keys, bucket names, KMS details, or presigned URLs.

This is not zero-knowledge or end-to-end encrypted storage. Authorized LifeLedger backend roles, Amazon S3, AWS KMS, and GuardDuty Malware Protection for S3 can access decrypted file contents for storage, scanning, validation, download, and deletion workflows. Do not upload passwords, private keys, seed phrases, recovery codes, banking secrets, payment-card data, or highly sensitive medical records.

Storage uses two retained private S3 buckets with Block Public Access on, Bucket owner enforced object ownership, no static website hosting, and SSE-KMS defaults using a separate customer-managed document key (`alias/${AWS::StackName}-documents`) with rotation enabled. Quarantine objects are written under `quarantine/<owner_hash>/<record_id>/<attachment_id>/object`; clean objects are written under `clean/<owner_hash>/<record_id>/<attachment_id>/object`. Original filenames are never used in object keys.

Upload flow:

- The browser requests `POST /records/{id}/attachments/upload-intent` with filename, MIME type, and size only.
- The backend validates extension, declared MIME type, size, attachment count, and record ownership, then creates pending metadata.
- The backend returns a short-lived presigned POST for one exact quarantine key, with content-length, content type, SSE-KMS, and document-key conditions.
- The browser posts the file directly to S3 and then calls `POST /records/{id}/attachments/{attachment_id}/complete`.
- Completion checks the exact object with `HeadObject`, including length, stored content type, SSE-KMS, and expected document KMS key. Invalid uploads are deleted and rejected.

Scan and promotion flow:

- GuardDuty Malware Protection protects the quarantine `quarantine/` prefix and managed tagging is enabled.
- Files stay unavailable until the object tag `GuardDutyMalwareScanStatus=NO_THREATS_FOUND` is present.
- `THREATS_FOUND`, `UNSUPPORTED`, `ACCESS_DENIED`, and `FAILED` never promote and never download.
- An EventBridge rule forwards official `GuardDuty Malware Protection Object Scan Result` events to the attachment scan finalizer Lambda.
- Attachment list/detail/refresh endpoints also reconcile the managed object tag, so delayed or missed EventBridge events recover safely.
- Before promotion, the backend re-checks size, content type, SSE-KMS, and magic bytes (`%PDF-`, PNG signature, or JPEG `FF D8 FF`), copies only clean files into the clean bucket with SSE-KMS, verifies the clean object, deletes quarantine, and marks the attachment available.

Download and delete flow:

- `POST /records/{id}/attachments/{attachment_id}/download-url` works only for owned attachments with `status=available` and a clean object key. It returns a fresh presigned GET URL valid for about 60 seconds with `Content-Disposition: attachment`, expected content type, and `Cache-Control: no-store, private`.
- `POST /records/{id}/attachments/{attachment_id}/preview-url` uses the same availability checks and returns a short-lived no-store presigned GET URL with `Content-Disposition: inline` for the in-app full-screen PDF/JPEG/PNG preview.
- List/detail endpoints return metadata only and no URLs.
- `DELETE /records/{id}/attachments/{attachment_id}` deletes quarantine and clean objects if present before removing metadata. Deleting a record cleans up associated attachment objects first and fails instead of silently orphaning known private objects.

Browser protections:

- Attachment API responses use `Cache-Control: no-store, private` and `Pragma: no-cache`.
- The service worker bypasses `/records/*/attachments*` and S3 presigned upload/download traffic.
- The frontend does not write attachment bytes, files, presigned URLs, or filenames to localStorage, sessionStorage, IndexedDB, Cache Storage, push notifications, digest content, calendar descriptions, or analytics.
- Cloudflare receives only public Vite configuration. AWS credentials, KMS material, bucket policies, and presigning stay in AWS.

Local development defaults to `DOCUMENT_STORAGE_MODE=disabled`. The accepted `local` value is reserved for a future explicit fake adapter and currently fails closed with the same "not configured" behavior; local uploaded files are not stored or presented as secure.

Operational setup:

1. Deploy the SAM stack with `DocumentStorageMode=s3` and `MalwareProtectionEnabled=true`.
2. Confirm the SAM-created `AWS::GuardDuty::MalwareProtectionPlan` is active for the quarantine bucket/prefix and managed tagging is enabled. If your account or Region blocks this resource, enable Malware Protection for S3 manually in GuardDuty for the quarantine bucket `quarantine/` prefix with tag objects enabled.
3. Redeploy Cloudflare Pages so the attachment UI and CSP updates are live.
4. Test with non-sensitive sample PDF/JPEG/PNG files only.

Production verification checklist:

- Both document buckets show Block all public access: On.
- Object Ownership is Bucket owner enforced.
- Default encryption is SSE-KMS with the LifeLedger document key and S3 Bucket Keys enabled.
- The document KMS key has rotation enabled and is retained.
- Quarantine lifecycle expires abandoned quarantine objects after about one day; clean documents do not expire.
- Clean bucket has no public policy and no static website hosting.
- GuardDuty Malware Protection protects the quarantine bucket/prefix and managed tagging is enabled.
- A clean sample file becomes available only after `NO_THREATS_FOUND`.
- Unsupported or password-protected files remain unavailable.
- Use only safe, industry-standard antivirus test procedures for malware-scan validation; do not create or download live malware on a personal machine.
- API and finalizer Lambda S3/KMS permissions are scoped to document buckets/prefixes and the document key.
- Digest Lambda has no document bucket, document key, or attachment-table access.
- Presigned upload and download URLs expire and are not logged.
- CloudTrail shows expected S3/KMS activity, and CloudWatch logs contain no filenames, URLs, object keys, file bytes, protected record values, tokens, or KMS data.
- Browser Cache Storage contains no attachment API responses or S3 objects.

Rollout and rollback:

- Roll out by deploying S3/KMS/DynamoDB resources, verifying GuardDuty tags, then deploying the frontend.
- If GuardDuty is absent, delayed, or broken, files remain scanning/unavailable. There is no "download anyway" fallback.
- Disabling frontend upload stops new uploads but does not delete stored attachments.
- Keep the document KMS key and both buckets retained during rollback. Do not schedule the document key for deletion.
- To preserve downloads/deletion while blocking new uploads, hide or disable the frontend upload control and keep backend storage resources/permissions in place.

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
- DynamoDB stores linked item edges under the authenticated user's `user_id` in a separate linked items table.

Frontend security headers are deployed through `frontend/public/_headers`, which Vite copies to `dist/_headers` for Cloudflare Pages. The CSP remains `Content-Security-Policy-Report-Only`; enforcement is not claimed and allows only the LifeLedger origin, the production API Gateway origin, and the Cognito User Pool endpoint for browser connections. CSP reports are accepted by the Cloudflare Pages Function at `frontend/functions/__csp-report.ts`. The service worker does not precache `index.html`, so document security headers are fetched from the network instead of being retained in an older Workbox cache. If a Cloudflare dashboard Transform Rule, Pages configuration, or Worker is also setting CSP, edit or remove that rule before relying on this policy; multiple CSP headers are combined by browsers, so an older policy such as `connect-src 'none'` can continue to report or enforce blocks even after this repository policy is added. If Cloudflare JavaScript Detections, Bot Fight Mode, or challenge injection is enabled, Cloudflare may inject inline `/cdn-cgi/challenge-platform/` scripts that conflict with strict `script-src 'self'`; disable that injection for LifeLedger or use a nonce-capable Worker before moving CSP from Report-Only to enforced mode. Before enforcement, collect at least 14 consecutive days of production reports, resolve all application-origin violations, verify Cognito, PWA assets and updates, API calls, S3 document previews, and Google Calendar OAuth in supported browsers, then deploy the same policy as `Content-Security-Policy` while retaining reporting.

## API Routes

- `GET /health` is public.
- `GET /reminders` requires authentication in Cognito mode.
- `POST /reminders` requires authentication in Cognito mode.
- `GET /reminders/{id}` requires authentication in Cognito mode.
- `PUT /reminders/{id}` requires authentication in Cognito mode.
- `DELETE /reminders/{id}` requires authentication in Cognito mode.
- `POST /reminders/{id}/complete` requires authentication in Cognito mode.
- `POST /reminders/{id}/snooze` requires authentication in Cognito mode and stores a temporary future `snoozed_until` without changing the underlying due date.
- `POST /reminders/{id}/snooze/clear` requires authentication in Cognito mode and clears reminder/alert snooze state.
- `POST /reminders/{id}/renew` requires authentication in Cognito mode, advances a renewable reminder to a new date, records lifecycle history, clears obsolete snooze state, and updates linked record dates when applicable.
- `GET /alerts` requires authentication in Cognito mode.
- `POST /reminders/{id}/alert/dismiss` requires authentication in Cognito mode.
- `POST /reminders/{id}/alert/snooze` requires authentication in Cognito mode.
- `GET /records` requires authentication in Cognito mode and returns active records by default. `include_archived=true` also returns archived records.
- `POST /records` requires authentication in Cognito mode and creates a record for the current user only. An optional `Idempotency-Key` makes safe retries resolve to the same user-scoped record.
- `GET /records/{id}` requires authentication in Cognito mode and returns only an owned record.
- `PUT /records/{id}` requires authentication in Cognito mode and updates only an owned record.
- `GET /records/{id}/protected/status` requires authentication in Cognito mode and returns safe protected-field status only for an owned record.
- PUT /records/{id}/protected requires authentication in Cognito mode and encrypts/replaces protected fields only for an owned record.
- PATCH /records/{id}/protected changes or removes selected protected details without replacing unaffected protected values.
- `GET /records/{id}/protected` requires authentication in Cognito mode, explicitly reveals protected fields only for an owned record, and returns no-store headers.
- `DELETE /records/{id}/protected` requires authentication in Cognito mode and clears only the encrypted protected payload for an owned record.
- `GET /records/{id}/attachments` requires authentication and returns safe attachment metadata only for an owned record.
- `POST /records/{id}/attachments/upload-intent` requires authentication and returns one short-lived presigned S3 POST for an owned record.
- `POST /records/{id}/attachments/{attachment_id}/complete` requires authentication and verifies the exact quarantine object before marking it scanning.
- `GET /records/{id}/attachments/{attachment_id}` requires authentication and returns safe attachment metadata/status only.
- `POST /records/{id}/attachments/{attachment_id}/refresh-status` requires authentication and reconciles the GuardDuty managed scan tag.
- `POST /records/{id}/attachments/{attachment_id}/download-url` requires authentication and returns a short-lived presigned GET URL only for available clean files.
- `POST /records/{id}/attachments/{attachment_id}/preview-url` requires the same ownership and clean-file checks and returns a short-lived inline preview URL for the full-screen viewer.
- `DELETE /records/{id}/attachments/{attachment_id}` requires authentication and deletes stored attachment objects before metadata removal.
- `POST /records/{id}/archive` requires authentication in Cognito mode and archives only an owned record.
- `POST /records/{id}/restore` requires authentication in Cognito mode and restores only an owned record.
- `DELETE /records/{id}` requires authentication in Cognito mode and deletes only an owned record.
- `GET /records/{id}/links` requires authentication and returns one-hop linked records and reminders for an owned record.
- `POST /records/{id}/links` requires authentication, verifies both entities are owned by the current user, rejects duplicates/self-links, and creates a record-to-record or record-to-reminder link.
- `DELETE /records/{id}/links/{link_id}` requires authentication and removes only the relationship row for an owned record; linked records and reminders are not deleted.
- `GET /reminders/{id}/links` requires authentication and returns one-hop linked records for an owned reminder.
- `DELETE /reminders/{id}/links/{link_id}` requires authentication and removes only the relationship row for an owned reminder.
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
- Local mode uses JSON-file persistence at `backend/data/reminders.json`, `backend/data/records.json`, and `backend/data/linked-items.json`.
- DynamoDB mode uses `DynamoReminderRepository`, `DynamoRecordRepository`, and `DynamoLinkedItemRepository` for AWS deployment.
- `backend/app/relationship_service.py` verifies ownership, creates explicit links, removes only links, and builds one-hop neighborhoods from safe entity summaries.
- Config in `backend/app/config.py` chooses auth mode, persistence mode, CORS origins, table names, local data paths, linked item storage, and backend-only Google OAuth settings.
- Application encryption lives in `backend/app/encryption_service.py`; Secrets Manager retrieval and process-level secret caching live in `backend/app/secret_provider.py`.
- Records use `RecordRepository`, `LocalRecordRepository`, and `DynamoRecordRepository`, all keyed by backend-derived `user_id`.
- Linked items use `LinkedItemRepository`, `LocalLinkedItemRepository`, and `DynamoLinkedItemRepository`, all keyed by backend-derived `user_id` and indexed by source/target lookup keys.
- Secure record attachments use `backend/app/attachments.py` for validation, S3, scan reconciliation, and clean promotion logic.
- Attachment metadata persistence uses `backend/app/attachments_repository.py`, with local JSON and DynamoDB implementations keyed by authenticated user and record.
- GuardDuty scan EventBridge events invoke `backend/attachment_scan_finalizer.py`, which reconciles the quarantine object tag and promotes only clean, validated files.
- Digest preferences use a separate user-scoped preferences repository with local JSON and DynamoDB implementations.
- Google Calendar connections and OAuth states use separate user-scoped/short-lived repositories with local JSON and DynamoDB implementations. Google token bundles are encrypted before storage when record encryption is enabled, with legacy plaintext token items migrated lazily.
- Mangum adapts FastAPI to Lambda through `backend/lambda_handler.py`.
- `backend/template.yaml` describes the SAM serverless deployment shape.

Reminder, record, linked item, and attachment metadata items include an internal `user_id`. In local mode it is `local-dev-user`; in Cognito mode it is the Cognito `sub`. DynamoDB uses `user_id` as the partition key and item `id` as the sort key for reminders and records, so users cannot read or mutate each other's data through the repository layer. Linked item rows use `user_id` plus `link_id`, with `SourceLinksIndex` and `TargetLinksIndex` for one-hop traversal without table scans. Attachment metadata uses `user_id` plus `<record_id>#<attachment_id>`, and the trusted scan finalizer can resolve a quarantine object through an owner-hash GSI without putting plaintext user ids in S3 keys. Reminder timing preferences, smart birthday fields, smart renewal fields, smart maintenance fields, lifecycle fields such as `snoozed_until`, `archived_at`, `completed_at`, and `lifecycle_events`, and alert state fields such as `alert_dismissed_until`, `alert_snoozed_until`, and `alert_last_action_at` are stored on each reminder item without changing the DynamoDB key schema. Records, linked items, and attachments are stored in separate retained tables so future search, dashboards, and AI retrieval can be added without overloading reminder storage. Digest preferences are stored in a separate table keyed by `user_id`, so future notification scheduling can read per-user digest time, timezone, lookahead, enabled state, and last-seen state without changing reminder storage. Google Calendar tokens are stored in a separate connection table keyed by `user_id`; OAuth state is stored server-side and expires before token exchange is allowed.

## Environment Variables

Backend local development works without setting any variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| APP_ENV | local | Names the runtime environment. Production deployments must explicitly use production. |
| APP_COMPONENT | api | Identifies api, digest, or attachment_finalizer so production startup validates only the controls that component requires. SAM sets this automatically. |
| `AUTH_MODE` | `local` | Use `local` for dev/SAM local or `cognito` for deployed Cognito auth. |
| `LOCAL_DEV_USER_ID` | `local-dev-user` | User id assigned in local auth mode. |
| `PERSISTENCE_MODE` | `local` | Use `local` for JSON or `dynamodb` for DynamoDB. |
| `REMINDERS_TABLE_NAME` | `lifeledger-reminders-auth` | DynamoDB table name when DynamoDB mode is enabled. |
| `RECORDS_TABLE_NAME` | `lifeledger-records-auth` | DynamoDB records table name when DynamoDB mode is enabled. |
| `RECORD_ATTACHMENTS_TABLE_NAME` | `lifeledger-record-attachments-auth` | DynamoDB record attachments metadata table name when DynamoDB mode is enabled. |
| `LINKED_ITEMS_TABLE_NAME` | `lifeledger-linked-items-auth` | DynamoDB linked item edge table name when DynamoDB mode is enabled. |
| `PREFERENCES_TABLE_NAME` | `lifeledger-preferences-auth` | DynamoDB preferences table name when DynamoDB mode is enabled. |
| `AWS_REGION` | `us-east-1` | Region used by the DynamoDB repository. Lambda also provides this automatically. |
| `LOCAL_DATA_FILE` | `backend/data/reminders.json` locally, `/tmp/lifeledger-reminders.json` in Lambda/SAM local | JSON file used when `PERSISTENCE_MODE=local`. |
| `LOCAL_RECORDS_FILE` | `backend/data/records.json` locally, `/tmp/lifeledger-records.json` in Lambda/SAM local | JSON file used for records when `PERSISTENCE_MODE=local`. |
| `LOCAL_RECORD_ATTACHMENTS_FILE` | `backend/data/record-attachments.json` locally, `/tmp/lifeledger-record-attachments.json` in Lambda/SAM local | JSON file used for attachment metadata when `PERSISTENCE_MODE=local`. |
| `LOCAL_LINKED_ITEMS_FILE` | `backend/data/linked-items.json` locally, `/tmp/lifeledger-linked-items.json` in Lambda/SAM local | JSON file used for linked items when `PERSISTENCE_MODE=local`. |
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
| `ALLOW_PLAINTEXT_PRODUCTION_SECRETS` | `false` | Legacy local/test compatibility only; production rejects plaintext secret providers even when this flag is set. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://lifeledger.jpreinold.com,https://www.lifeledger.jpreinold.com` | Comma-separated frontend origins allowed to call the API. |
| `DOCUMENT_STORAGE_MODE` | `disabled` locally, `s3` when `APP_ENV=production` unless overridden | `disabled`, `local`, or `s3`. Local/SAM local defaults to disabled; production should use `s3`. |
| `DOCUMENTS_QUARANTINE_BUCKET` | empty | Private quarantine S3 bucket used for untrusted browser uploads. SAM sets this from the stack bucket. |
| `DOCUMENTS_CLEAN_BUCKET` | empty | Private clean S3 bucket used only after clean scan and validation. SAM sets this from the stack bucket. |
| `DOCUMENTS_KMS_KEY_ARN` | empty | Dedicated document KMS key ARN used for S3 SSE-KMS. SAM sets this from the stack key output. |
| `ATTACHMENT_MAX_SIZE_BYTES` | `10485760` | Maximum attachment size, 10 MB by default. |
| `ATTACHMENT_MAX_PER_RECORD` | `5` | Maximum active attachments per record. |

SAM parameters include `LinkedItemsTableName`, `RecordEncryptionMode`, `DocumentStorageMode`, `MalwareProtectionEnabled`, `GoogleOAuthSecretArn`, `VapidPublicKey`, `PushSecretArn`, and `VapidSubject`; Cloudflare Pages uses only public `VITE_*` values such as `VITE_VAPID_PUBLIC_KEY`.

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
- A separate retained customer-managed symmetric document KMS key with rotation enabled and alias `alias/${AWS::StackName}-documents`.
- A DynamoDB table named `lifeledger-reminders-auth` with `user_id` partition key and `id` sort key.
- A DynamoDB table named `lifeledger-records-auth` with `user_id` partition key and `id` sort key.
- A DynamoDB table named `lifeledger-record-attachments-auth` with `user_id` partition key, `<record_id>#<attachment_id>` sort key, PITR, SSE-KMS, and an owner-hash GSI for trusted scan finalization.
- A DynamoDB table named `lifeledger-linked-items-auth` with `user_id` partition key, `link_id` sort key, `SourceLinksIndex`, and `TargetLinksIndex` for one-hop linked item traversal.
- A DynamoDB table named `lifeledger-preferences-auth` with `user_id` partition key for Daily Digest preferences.
- A DynamoDB table named `lifeledger-google-calendar-connections-auth` with `user_id` partition key for backend-only Google Calendar tokens.
- A DynamoDB table named `lifeledger-google-oauth-states-auth` with `state` partition key for expiring OAuth state validation.
- Customer-managed DynamoDB SSE-KMS and point-in-time recovery on retained data tables.
- Two retained private S3 document buckets: quarantine for presigned browser uploads and clean for scan-passed downloads.
- S3 Block Public Access, Bucket owner enforced object ownership, SSE-KMS document-key defaults, bucket-key support, insecure-transport denies, and incorrect-encryption denies on document buckets.
- GuardDuty Malware Protection for S3 on the quarantine `quarantine/` prefix with managed object tagging when `MalwareProtectionEnabled=true`.
- An attachment scan finalizer Lambda and EventBridge rule for `GuardDuty Malware Protection Object Scan Result` events.
- API Lambda DynamoDB permissions include the linked items table; Digest and attachment finalizer Lambdas do not receive linked item table access.
- API Lambda permissions for `kms:GenerateDataKey` and `kms:Decrypt` are scoped to the stack KMS key and require encryption context `app=lifeledger`.
- API and finalizer Lambda document S3/KMS permissions are scoped to the document buckets, `quarantine/*` and `clean/*` prefixes, and the document KMS key through S3.
- API Lambda Secrets Manager access is scoped to `GoogleOAuthSecretArn` and `PushSecretArn`; the Digest push Lambda may read only `PushSecretArn` and does not receive record KMS decrypt permissions.
- `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` on the KMS key and retained DynamoDB tables.

`backend/env.local.json` explicitly sets `APP_ENV=local`, `AUTH_MODE=local`, `PERSISTENCE_MODE=local`, disabled record encryption, and disabled document storage for SAM local, so it can serve `/health`, `/reminders`, `/records`, `/records/{id}/links`, and `/preferences/digest` without Cognito login, AWS credentials, or DynamoDB calls. In Lambda/SAM local mode, local JSON persistence writes to `/tmp/lifeledger-reminders.json`, `/tmp/lifeledger-records.json`, `/tmp/lifeledger-linked-items.json`, `/tmp/lifeledger-preferences.json`, `/tmp/lifeledger-push-subscriptions.json`, `/tmp/lifeledger-google-calendar-connections.json`, and `/tmp/lifeledger-google-oauth-states.json` because the function code directory may be read-only.

Production deployments now fail closed at three layers: secure SAM defaults, CloudFormation rules, and runtime component validation. `AppEnv=production` rejects local auth, local persistence, disabled protected-record encryption, missing Cognito/KMS/document configuration, localhost or wildcard CORS origins, and local plaintext secret providers. Local development remains available only through explicit `APP_ENV=local` configuration.

Search reconciliation is safe to rerun and never decrypts protected values. Rebuild one source item with `python backfill_search.py --user-id <user-id> --entity-type record --entity-id <record-id>`. Rebuild a bounded user scope, retry persisted projection failures, update stale versions, and delete verified orphans with `python backfill_search.py --user-id <user-id> --limit 1000`. Use `--dry-run` to count without writes. If the limit truncates any source collection, the command deliberately skips orphan deletion rather than risk deleting a valid projection; rerun with a sufficient bound.

Pre-deployment validation:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_sam_config.py -q
sam validate --lint --template-file template.yaml
sam build
```

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

SAM guided deploy creates `backend/samconfig.toml` for your machine/account. That file is ignored by git because it can contain local deployment choices. Use `backend/samconfig.example.toml` as a safe reference, then run:

```powershell
cd backend
sam deploy --guided
```


CI requires no application secrets. `.github/workflows/ci.yml` installs dependencies from the lock/requirements files and runs backend tests, import/package validation, SAM lint validation, frontend tests, standalone type checking, lint, and the production build. It does not deploy.
## Deployment Checklist

- `npm run check` passes.
- Backend is deployed with `AppEnv=production`, `AuthMode=cognito`, `PersistenceMode=dynamodb`, `RecordEncryptionMode=kms`, `DocumentStorageMode=s3`, malware protection enabled, HTTPS-only CORS origins, and the linked items table parameter.
- AWS `/health` works without signing in.
- AWS `/reminders` rejects requests without a bearer token.
- AWS /records rejects requests without a bearer token.
- A deployment attempt with any production/local mode combination is rejected, and an insecure production runtime configuration fails before serving requests.
- S3 Block Public Access and default KMS encryption are enabled for both document buckets, and scanning documents cannot receive preview/download URLs.
- Cognito admin-created user can sign in.
- Cloudflare Pages has all required `VITE_*` environment variables, including `VITE_VAPID_PUBLIC_KEY` for push subscriptions.
- Cloudflare frontend can load, create, complete, and delete reminders after sign-in.
- Cloudflare frontend can create, edit, archive, restore, and delete records after sign-in.
- Cloudflare frontend can link a record to another record, link a record to a reminder, open a linked item, and remove only the link after sign-in.
- AWS is redeployed with the records table, linked items table, push subscription table, scheduled sender, KMS key, secret ARN parameters, Google Calendar connection/state tables, and Google OAuth backend parameters.
- Cloudflare is redeployed with `VITE_VAPID_PUBLIC_KEY` and the updated Calendar sync, Records UI, and Linked Items UI.
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

This phase does not add two-way Google Calendar sync, Google Calendar import, Google Calendar edit ingestion, attendees, shared calendars, email sending, SMS, password-manager functionality, AI/RAG, OCR, global search over protected fields/files, multi-hop graph traversal, file sharing, public links, Office documents, archives, audio/video, reminder attachments, social login, public registration, mileage-based maintenance, usage-based maintenance, supply inventory, automatic record-to-reminder generation, custom per-reminder push rules, notification history, shared households, roles/admin dashboards, or another frontend redesign. Do not store SSNs, payment card numbers, bank account or routing numbers, passwords, PINs, MFA/recovery codes, private keys, API keys, authentication credentials, highly sensitive medical records, or secret/recovery documents in reminders, records, linked item labels, or attachments. Future smart reminder work may include usage-based maintenance, search, AI retrieval over safe summaries, and calendar or notification integrations.
