# Capture Inbox

Phase 14 adds an authenticated, text-only Capture Inbox. A Capture preserves the exact original statement before LifeLedger has safely organized it. The active source is `lifeledger_web`; shortcut, ChatGPT, Share Sheet, file, image, URL, audio, and document capture are not active.

## Lifecycle

`new` → `interpreting` → `needs_clarification` or `ready_for_review` → `executing` → `completed`.

Failures become `failed` and remain retriable. Users can dismiss unresolved captures. The Inbox groups needs-input, review-ready, processing, failed, and recently completed captures and uses cursor-bounded reads. Original text, clarifications, and proposed values are returned with `Cache-Control: no-store, private`. They are never placed in URLs or browser storage.

Creation requires an idempotency key. A duplicate key for the same authenticated user returns the original Capture. Retry creates a new versioned proposal without repeating already completed actions. Completed and dismissed temporary proposal state is eligible for bounded DynamoDB TTL cleanup after expiry; unresolved captures never expire silently. Account deletion remains the authoritative cleanup for all Capture data.

## Product behavior

Home and Add offer “What should LifeLedger remember?” The user submits one or more plain-text sentences with browser time, locale, and timezone context. LifeLedger tries its small deterministic grammar first, then an enabled and budget-eligible AI provider. If neither path can organize the statement, the original remains in “Could not organize” with a safe explanation.

The review shows the original statement, a concise summary, user-facing proposed changes, conflicts, questions, and safe results. Before confirmation, supported user-facing values can be adjusted in place; the backend strictly revalidates every adjustment and re-runs policy. It never shows prompts, JSON, model confidence numbers, tokens, action IDs, enum choices, dynamic-field keys, repository terms, or hidden reasoning.

Natural-language capture is not for passwords, authentication or recovery codes, full card data, passport numbers, full VINs, or other protected identifiers. This warning is a guardrail, not a claim of perfect sensitive-value detection.

## API

- `POST /captures`, `GET /captures`, `GET /captures/{id}`
- `POST /captures/{id}/interpret`, `/retry`, and `/dismiss`
- `GET /proposals/{id}`
- `PATCH /proposals/{id}` for a bounded, pre-confirmation action adjustment
- `POST /proposals/{id}/clarifications`, `/approve`, and `/reject`
- `GET /ai-usage`, `GET/PUT /ai-settings`

All routes use existing Cognito/local authentication and backend-derived ownership. There is no public or external-assistant capture endpoint.
