# Assistant action contract

Interpreter output is untrusted input. `capture_models.py` defines a closed, versioned Pydantic contract for `create_item`, `update_item_detail`, `create_responsibility`, `complete_responsibility`, `renew_responsibility`, `snooze_responsibility`, `create_relationship`, `add_safe_note`, `request_clarification`, and `no_action`.

Every action has a backend-assigned ID, source Capture, deterministic risk and confirmation decision, idempotency key, schema version, concise explanation, and only the target and fields appropriate for that discriminated action. Unknown action types, item types, detail keys, recurrence values, relationship values, arbitrary backend fields, and model-invented IDs fail validation.

Before confirmation, the review UI can submit limited corrections for user-facing values such as a display name, due date, reminder time, or note through `PATCH /proposals/{id}`. The server merges the correction into the existing typed action, rejects unknown or invalid fields, re-runs conflict detection and deterministic policy, and preserves the backend-assigned action identity and idempotency key. Editing is unavailable after execution starts or the proposal expires.

Delete, archive, protected-detail writes, account/financial changes, external integration changes, arbitrary history correction, document writes, and raw repository operations are absent. Neither the model nor a proposal edit can approve a proposal.

## Policy

- Low: clearly matched completion/snooze and bounded safe notes. Confirmation is still required.
- Medium: item/Person creation, safe detail updates, relationships, and new or recurring responsibilities. Confirmation is always required.
- High: conflicting current data, protected or consequential information, destructive operations, and integration changes. Capture execution is prohibited; the user is directed to the normal editor where appropriate.

`ActionPolicyService` owns the decision. Model confidence never changes authorization, ownership, reauthentication, confirmation, or grouping.

## Execution

`ActionExecutionService` verifies ownership, proposal state and expiry, re-runs policy, and executes in dependency order through `ItemApplicationService`, `ResponsibilityApplicationService`, `ResponsibilityLifecycleService`, and `RelationshipApplicationService`. Interpreters have no repository reference.

Each action result is durably appended to its proposal before the next action. Completed action IDs are skipped on retry. Partial completion creates reconciliation work and reports exactly which safe summaries succeeded. Reject never mutates Items or Responsibilities. Full automatic undo and arbitrary merge/split correction are deferred; users can adjust supported values before confirmation, reject, retry, select a different entity, dismiss, or open the resulting normal editor.
