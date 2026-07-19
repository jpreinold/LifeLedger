# Operational reliability

Phase 13 treats recoverable cross-store failures as durable reconciliation issues. The store is operational metadata, not a user-facing history feed, and never contains titles, notes, protected values, filenames, signed URLs, tokens, request bodies, search text, or raw exceptions.

## Reconciliation model

An issue has a deterministic `reconciliation_id`, authenticated `user_id`, domain, entity type and ID, issue type, detection and attempt timestamps, attempt count, status, severity, retryability, next retry time, correlation ID, safe summary, resolution, resolved time, and schema version. Statuses are `pending`, `retrying`, `resolved`, `requires_attention`, and `ignored`. Domains are `search`, `lifecycle`, `item_sync`, `document`, `relationship`, `account_deletion`, and `workflow`.

The DynamoDB table is keyed by issue ID and has status, user, domain, and due-retry indexes. Local development has atomic JSON parity. Detection is idempotent for a domain/entity/issue tuple. Unresolved rows never expire. Resolved and ignored rows receive a bounded TTL.

Targeted detection verifies missing or stale search projections, linked context, archived status, document projections and long-running scan/upload states, persisted lifecycle reconciliation flags, occurrence/item-date mismatches, invalid relationships, and incomplete account deletion. A daily detector visits bounded user/entity pages and stores cursors; it never runs an unbounded production scan and never invents workflow or lifecycle history.

## Repair and escalation

The retry Lambda runs hourly with a bounded batch. Export-artifact expiry runs every 15 minutes. A deeper bounded detector runs daily. Each issue is isolated so one failure cannot stop the batch. Repairs are safe, idempotent projection rebuilds or persisted deletion cleanup. Backoff is bounded exponential, retry count is limited, and persistent failures become `requires_attention`.

Automatic repair never reveals protected data, retries a destructive user decision, fabricates history, recreates deleted data, re-uploads a document, or chooses an ambiguous conflict. A successful operation resolves only the matching durable issue.

AWS-authenticated operators can use the maintenance CLI from `backend`:

```powershell
python reconcile.py report --status requires_attention --limit 50
python reconcile.py retry <safe-issue-id>
python reconcile.py resolve <safe-issue-id> --reason verified_repair
python reconcile.py ignore <safe-issue-id> --reason non_actionable
python reconcile.py detect-user --user-id <cognito-sub> --limit 100
python reconcile.py reconcile-user --user-id <cognito-sub> --limit 100 --dry-run
python reconcile.py reconcile-entity --user-id <cognito-sub> --entity-type record --entity-id <opaque-id> --dry-run
python reconcile.py sweep --limit 50 --dry-run
```

No ordinary-user or query-parameter admin endpoint is provided. Run dry-run first for a sweep and keep batch bounds explicit.

## Metrics and alarms

Embedded CloudWatch metrics include pending, retrying, requires-attention, resolutions, failed retries, oldest unresolved age, issues by domain, stuck-scanning documents, and incomplete account deletions. The dashboard combines those signals with Lambda errors and the account-operation dead-letter queue.

Alarms are deliberately aggregated to avoid storms: any scheduled Lambda error, persistent requires-attention count, unresolved age over 24 hours, at least five stuck documents, any incomplete deletion, any account-worker dead letter, and three production E2E failures in the evaluation window. The production workflow writes its result metric and a last-success timestamp when its restricted AWS role is configured.

## Privacy-safe operational events

Structured events are emitted for export, deletion, reconciliation, production E2E, and deployment verification. Permitted fields are operation/correlation IDs, domain, opaque entity ID, step, status, retryability, attempts, duration, environment, and version. Raw payloads and private content are prohibited.
## Phase 14 AI capture operations

Production OpenAI access is disabled unless `AI_PROVIDER=openai` and `AI_API_SECRET_ARN` names a Secrets Manager JSON object containing `api_key`. `AI_EMERGENCY_DISABLED=true` stops calls without losing Captures. User budgets default to $5/month and 50 requests/day; input/output caps are server settings. Rotate the secret in Secrets Manager without frontend changes and never print its value.

Privacy-safe dimensions may include Capture/proposal IDs, correlation ID, interpreter/model, action type, token counts, estimated cost, latency, and result category. Never log original text, prompts containing it, raw responses, clarification answers, notes, protected data, signed URLs, tokens, or credentials.

Deep reconciliation checks stuck interpreting Captures, stuck/partial executing proposals, expired executable proposals, completed proposals missing results, and duplicate provider-request charges. Ambiguity, rejected/prohibited actions, new confirmation, protected operations, and budget-denied calls are never automatic retries.

Free evaluation commands are in `docs/ai-evaluation.md`. Live evaluation is paid, explicit, and excluded from standard CI. Remaining Phase 13 live acceptance is tracked in `docs/deferred-production-acceptance.md`.
