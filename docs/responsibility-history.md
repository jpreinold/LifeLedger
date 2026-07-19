# Responsibility history and renewal ledger

LifeLedger separates current responsibility state from a durable, user-visible history of meaningful lifecycle actions. The ledger is focused: it is not a technical audit log or a general event-sourcing platform.

## Domain model

- A **responsibility** is the existing user-owned `Reminder`: a task, renewal, service need, or date that needs attention.
- An **occurrence** is one actionable cycle of a responsibility. A recurring completion closes the current occurrence and deterministically opens the next one. Reopening a completed one-time responsibility also opens a new occurrence.
- A **lifecycle event** is an immutable, meaningful action. Initial types are responsibility created, completed, renewed, snoozed, snooze cleared, reopened, due date changed, supporting document added, and the reserved honest legacy baseline `history_tracking_started`.
- **Current state** is what is true now: current due date, completion state, schedule, alert state, and current item date. **History** records what happened: effective/completion date, prior and next due dates, private note, connected item snapshot, and safe document references.

No migration is required for legacy reminders. Their current state remains valid, but old timestamps and the legacy capped lifecycle array are not converted into ledger events. New history begins only when a real Phase 12 action is recorded. The baseline event type exists for an explicit future backfill; normal reads never fabricate it.

## Persistence and access patterns

Deployed history uses the retained, point-in-time-recoverable `ResponsibilityHistoryTable`, encrypted with the existing application KMS key. Its primary key is `user_id` + `event_id`. Three indexes provide bounded queries:

- `ReminderHistoryIndex`: `reminder_partition` + `event_sort`, newest first.
- `ItemActivityIndex`: `item_partition` + `event_sort`, newest first.
- `HistoryIdempotencyIndex`: a SHA-256 user-and-operation-key partition for replay lookup.

The API exposes one event by ID, cursor-paginated reminder History, and cursor-paginated item Activity. All keys and indexes are user-scoped. Local development uses a JSON sidecar next to the configured reminder file and implements the same ordering, idempotency, pagination, rollback, and deletion behavior.

History entries contain bounded, validated fields rather than arbitrary metadata. They exclude protected record payloads, document bytes, object keys, signed URLs, authentication data, search queries, and full request payloads. Notes are limited to 500 characters, returned with `no-store`, excluded from search, notifications, and operational logs.

## Transactions, idempotency, and recurrence

`ResponsibilityLifecycleService` coordinates reminder state and history. DynamoDB writes the reminder update and append-only event in one `TransactWriteItems` call, with an expected reminder version and immutable-event condition. Local persistence rolls the reminder back if event append fails. Deterministic event IDs plus scoped operation keys prevent duplicate events. A supplied occurrence ID rejects a stale double submission even when a new operation key is used.

The existing recurrence rules remain authoritative. Weekly, monthly, quarterly, and yearly schedules advance from the prior due date and skip elapsed cycles through the current date; month-end values clamp according to the existing recurrence helper. Maintenance intervals advance from the user-selected completion date. Snooze changes only the effective attention date. Recurring completion preserves the prior occurrence event and creates a deterministic current occurrence ID for the advanced due date. One-time completion stays completed; reopen keeps the old event and creates a distinct next occurrence.

## Renewal and item-date synchronization

Renewal records the renewal date, previous due/expiration date, and accepted next date before changing current state. The shared mapping in `responsibility_sync.py` uses stable Phase 10/11 keys:

| Workflow | Current item target |
| --- | --- |
| Passport expiration | `expiration_date` |
| Vehicle registration | `registration_expiration` |
| Pet vaccination | `next_vaccination_due_date` |
| Subscription renewal | `renewal_date` |

The mapping updates an existing key or creates one stable dynamic field; it never creates a duplicate. A value is changed only when it is empty, still equals the accepted previous date, or already equals the next date. Conflicting or archived item state is not overwritten. The lifecycle event keeps the accepted mapping key so reconciliation does not depend on the reminder's already-advanced date. Reminder and item search projections are refreshed after the transaction; notes and protected details remain excluded.

Item-date, search, and document operations cannot all share the reminder/history transaction. Existing event flags remain read-compatible, while Phase 13 also detects unresolved flags into the durable operational reconciliation store. Failures are repaired only from persisted operation evidence. The same operation key replays the existing event rather than appending another.

## Supporting document evidence

Completion and renewal may optionally use an already connected active item's secure document flow. The responsibility action succeeds first. Upload intent, S3 quarantine upload, completion, malware scan, and promotion remain external and are never described as atomic with DynamoDB.

Only after attachment metadata exists does the service append `supporting_document_added`, referencing the document ID and related completion/renewal event. A failed upload does not undo the lifecycle action; the UI retains a document-only retry. Scanning evidence appears pending, rejected/failed evidence is not presented as valid, and deleted metadata resolves to “Document no longer available” without deleting historical facts. Old documents are neither deleted nor automatically replaced.

## Reconciliation and retention

`POST /reminders/{id}/history/reconcile` repairs one responsibility. `POST /responsibility-history/reconcile` processes one user's responsibilities in bounded pages. Both support `dry_run=true`, are safe to repeat, and repair only persisted operation evidence: item dates, search projections, and document-reference status. They never infer a missing completion or renewal from timestamps, logs, or current state.

Deleting a responsibility deletes its ledger entries after the existing confirmation. Archiving retains history. Deleting an item follows current relationship/document cleanup; responsibility history remains readable from any retained responsibility using safe title snapshots, while deleted evidence becomes unavailable. Phase 13 account deletion deletes history before reminders and verifies the history store is empty before identity removal. See [account-data-lifecycle.md](account-data-lifecycle.md).

## Frontend loading and bundle budget

The authenticated Amplify shell, Guided Workflow drawer, Calendar, Search, record/reminder detail drawers, lifecycle action drawer, and History/Activity panel load through feature boundaries with accessible status text. History does not load until the user expands it, and pages default to ten entries. PDF preview remains in its own document chunk.

The bundle budget is: no application entry chunk above Vite's 500 KB advisory threshold; PDF code remains isolated; optional workflows and history must not be pulled into the initial local-mode shell. The Phase 12 production build produces a 373.55 KB main application chunk, 469.14 KB lazy Amplify core chunk, 114.29 KB Amplify UI chunk, 107.20 KB MUI chunk, 330.03 KB PDF chunk, 21.56 KB guided workflow chunk, 8.86 KB lifecycle action chunk, and 6.23 KB History/Activity chunk. Vite's 500 KB chunk warning is cleared. The PDF worker remains a 2.21 MB separately loaded worker asset. Recheck these boundaries after dependency upgrades; do not raise the warning threshold to hide regressions.

## End-to-end acceptance

Local/CI mode uses Playwright with deterministic API interception and no credentials:

```powershell
cd frontend
npx playwright install chromium
npm run test:e2e:local
```

Deployed mode is explicit and uses only environment/CI secrets:

```powershell
$env:E2E_BASE_URL='https://frontend.example'
$env:E2E_API_BASE_URL='https://api.example'
$env:E2E_USERNAME='dedicated-test-account@example.com'
$env:E2E_PASSWORD='set-outside-the-repository'
$env:E2E_ACCOUNT_GROUP='lifeledger-e2e'
npm run test:e2e:deployed
```

The deployed harness also refuses an account outside the expected dedicated Cognito group and verifies search cleanup. Credentials, tokens, protected values, signed URLs, videos, traces, and authentication state are not committed. See [production-e2e.md](production-e2e.md) for the protected manual workflow and safety rules.

## Extending a future workflow

Add the workflow ID and item date key to the shared workflow/entity registry mapping, build its responsibility through the existing guided engine, and call the lifecycle service for every meaningful action. Do not append events from clients or route handlers, do not add arbitrary metadata, and do not derive historical actions from current item fields.
