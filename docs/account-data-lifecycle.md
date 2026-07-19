# Account data lifecycle

Phase 13 uses one executable account-data inventory for export, deletion, and deletion verification. A new store must be registered once in `account_inventory_factory.py`; adding a separate hand-maintained export or deletion list is prohibited.

## Registered inventory

| Store or external resource | Ownership and pagination | Export | Deletion / retention |
| --- | --- | --- | --- |
| Records/items, normal and dynamic details, protected metadata | `user_id`, bounded repository pages | Yes; protected plaintext only by explicit confirmed request | Delete after dependent data |
| Reminders/responsibilities, occurrences, alert/digest and calendar mapping state | `user_id`, bounded pages | Yes | Delete after lifecycle and links |
| Responsibility history | `user_id`, bounded history pages | Yes | Delete before reminders |
| Relationships | `user_id`, bounded link pages | Yes | Delete before source entities |
| Document metadata | `user_id`, bounded attachment pages | Yes | Delete with objects |
| Quarantine/raw, promoted clean, and retained rejected S3 objects | owner-scoped keys | Clean user documents are copied into the archive | Delete before metadata completes |
| Search projections and projection-failure rows | `user_id`, bounded repository pages | No; derived/internal | Delete and verify zero |
| Saved views | `user_id`, bounded pages | Yes | Delete |
| Preferences and alert/digest state | `user_id`, direct item | Yes | Delete |
| Push subscriptions | `user_id`, bounded pages | Integration metadata only, without endpoints/secrets | Revoke/delete |
| Google Calendar connection, tokens, mappings and OAuth state | `user_id`, direct/bounded indexes | Non-secret integration metadata only | Remove mapped events when possible, revoke token, delete encrypted token/OAuth state |
| Reconciliation issues | `user_id`, bounded user index | No; operational | Delete during account cleanup; recreate only an incomplete-deletion issue when needed |
| Export jobs, deletion jobs and account lifecycle state | `user_id` + operation key | No | Kept only while work is resumable, then removed |
| Export artifacts | user-hashed S3 prefix plus random operation key, bounded prefix listing | The artifact itself | Delete on expiry and during deletion, including artifacts orphaned before job-row update |
| Cognito identity | Cognito `sub` resolved to the pool username | Never | Deleted only after every data cleanup and verification step |
| Captures, proposals/results, clarifications, safe AI usage, AI settings | `user_id`, bounded assistant-table pages | Yes, as portable user-owned JSON | Delete and verify each kind; temporary resolved proposal state may use TTL |

There is no server-side recent-view store or separate workflow-draft store. Guided workflow correlation state remains in active browser memory. Idempotency is stored on its owning entities and operations rather than in a separate user table.

## Export

The user requests an asynchronous ZIP from Settings. The archive contains `manifest.json`, per-store JSON files, and an optional `documents/` tree using opaque entity IDs rather than filenames. The manifest has schema/version metadata, job timestamps, referential IDs, and an explicit protected-content flag.

Protected plaintext is excluded by default. Including it requires an explicit checkbox and confirmation plus recent authentication where Cognito supplies `auth_time`. LifeLedger does not claim custom archive encryption. A plaintext-inclusive export instead receives a stronger warning and a shorter authenticated download window.

Artifacts use strong random keys in a private, KMS-encrypted S3 bucket with public access blocked. Downloads are short-lived, user-scoped presigned responses with `Cache-Control: no-store`; URLs and contents are never logged or emailed. Standard exports expire in 60 minutes and protected-content exports in 15 minutes. A 15-minute indexed janitor removes expired artifacts, S3 lifecycle is a one-day backstop, and account deletion removes all remaining artifacts. Duplicate concurrent export requests return the existing active job; a failed retry reuses its job ID.

Exports omit Cognito credentials, access/refresh tokens, encryption keys, presigned URLs, AWS scan internals, secret values, operational logs, and other users' data.

## Deletion

The user must type `DELETE MY ACCOUNT`, sees an export-first option, and must have recent authentication where supported. Deletion is asynchronous and immediately moves the account to `deleting`; ordinary reads, writes, reconciliation, and integration activity are blocked except for account status. There is no cancellation grace period, and successful identity cleanup ends authentication.

The durable, idempotent sequence is:

1. Persist the request and block writes.
2. Revoke push subscriptions and Google integration state, including token revocation where supported.
3. Delete lifecycle history and occurrences.
4. Delete relationships.
5. Delete raw/quarantine, promoted clean, rejected, and export S3 objects, then document metadata.
6. Delete search projections and saved views.
7. Delete preferences, alert/digest state, mappings, OAuth states, reconciliation data, and remaining integration state.
8. Delete reminders and records.
9. Verify every registered store by safe count.
10. Delete Cognito identity last.
11. Remove resumable operation rows and retain a seven-day non-identifying operation receipt for queue idempotency.

Every step is `pending`, `in_progress`, `complete`, or `failed` and can be rerun. A cleanup failure leaves the account in `deletion_requires_attention`, persists one retryable reconciliation issue, and never reports completion. Scheduled repair resumes the same deletion job. A completed step is skipped only if verification still reports zero, preventing stale state from hiding recreated data.

Verification returns store names and counts only. It never includes titles, notes, filenames, object keys, protected values, or identity attributes. Completion requires zero registered data, removed external credentials and S3 objects, Cognito completion, and no unresolved deletion issue.

## Retention statement

LifeLedger does not claim instant physical erasure or formal regulatory compliance. During a failed or active request it retains the minimum operation and safe reconciliation state needed to resume. After verified completion it deletes those user-scoped rows. A seven-day receipt contains only the random deletion operation ID, completion timestamp, and safe terminal status so duplicate queue delivery remains idempotent; it has no user ID. Cloud provider backups and logs follow configured infrastructure retention and are not used to reconstruct a deleted account. No title, note, protected value, document name/content, token, IP address, or user ID is retained in the terminal receipt.
## Phase 14 assistant data

The centralized inventory registers Captures, action proposals (including safe action results), clarification questions/answers, safe AI usage rows, and AI settings. Exports include those user-owned portable JSON rows. Hidden prompts, provider secrets, API keys, internal safety instructions, and hidden reasoning are neither stored nor exported.

Deletion removes each assistant kind in bounded, idempotent user-scoped batches and verifies every count reaches zero before identity cleanup. Related reconciliation issues remain covered by the existing reconciliation inventory. Proposal/clarification TTL is defense-in-depth for expired temporary state; it never replaces account deletion, and unresolved Captures do not expire silently.
