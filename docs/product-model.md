# LifeLedger product model

LifeLedger is a trusted personal operating system for the important information, responsibilities, dates, documents, and relationships in a person's life. The product vocabulary below is the user-facing layer over the existing generic persistence model.

## Current concepts

| Concept | User-facing meaning | Current internal implementation | Implemented now | Deferred, invariants, and future dependency |
| --- | --- | --- | --- | --- |
| Item | A real-world thing the user wants to keep track of, such as a vehicle, pet, home, passport, policy, subscription, or warranty. | Existing `Record` model and record APIs. | The entity registry maps every `record_type` to stable product behavior and presents unknown types as Other item. | Existing data must remain visible; `Record` stays internal. Guided item bundles may compose current APIs later, without per-type tables or routes. |
| Detail | Current information that describes an item. | A safe fixed record property or `DynamicField`. | The registry supplies compact, type-specific suggestions; Add another detail provides the generic escape hatch. | Detail creation must not expose field-source mechanics. Future guided flows should reuse the same detail definitions. |
| Protected detail | A detail that needs encryption, explicit reveal, and search exclusion. | Existing protected record payload or sensitive dynamic field. | Suggested sensitive details are protected by default and use the existing protected-data flow. | Protected values are never indexed, logged, or kept in browser storage. Future flows must preserve reveal and re-hide behavior. |
| Responsibility | Something the user needs to do or remain aware of for an item. | Existing `Reminder` related through the current link API. | Item screens present connected reminders as Responsibilities; four guided tracking flows can create and connect one in context. | Existing reminder lifecycle and authorization remain authoritative. Guided creation does not introduce a second reminder model. |
| Reminder | The familiar global list and notification schedule for responsibilities and standalone dates. | Existing reminder types, lifecycle, alerts, recurrence, calendar, and push behavior. | Global navigation and notification settings retain Reminder language. | Complete, snooze, renew, archive, and delivery semantics do not change; future responsibility flows must call these APIs. |
| Document | A file or supporting material related to an item or responsibility. | Existing `RecordAttachment` storage, scanning, preview, download, and relationship behavior. | User-facing uploads, messages, errors, search results, and accessibility labels say Document. | `Attachment` remains internal. Future guided prompts must keep current scanning, exact-navigation, and privacy protections. |
| Related item | An item, responsibility, or document connected to the current context. | Existing `LinkedItem` and relationship APIs. | Friendly relationship labels and contextual defaults replace raw enums; guided flows create the supported `reminder_for` relationship without exposing the enum. | Links never imply deletion or ownership. Manual relationship editing and removal keep their existing semantics and scoping. |
| Lifecycle event | A meaningful occurrence such as created, completed, renewed, snoozed, reopened, date changed, or supporting document added. | Append-only `ResponsibilityEvent` ledger with user, responsibility, optional item, and occurrence scope. | Reminder History and item Activity read the real paginated ledger; current state remains separate. | Static timestamps and the legacy capped array are never promoted into pretend history. General item version history remains deferred. |
| Owner | Who or what an item primarily concerns. | Existing `owner_name` plus registry ownership capability. | Relevant item types can present owner context without requiring it. | Ownership stays optional and user-scoped. Household sharing and multi-user permissions require a later authorization design. |
| Provider | A person or organization providing a service. | Existing provider/brand fields, provider-like details, and relationships. | Relevant item types can present and suggest provider details. | No provider table is introduced. A dedicated Provider item waits until persistence can represent it without overloading unrelated fields. |

## Source of truth and compatibility

`frontend/src/lib/entityRegistry.ts` is the product source of truth for supported item types, labels, icons, suggested details, sections, responsibilities, document guidance, capabilities, and default secondary categories. `frontend/src/lib/terminology.ts` centralizes cross-cutting product labels and presentation helpers. Backend enums and TypeScript API response types retain their existing internal names.

`record_type` identifies the core item kind. `category` is optional secondary organization in the product experience even though the current API keeps a non-empty compatibility default. New items receive a distinct registry category; edits preserve stored category values. Duplicate and legacy categories are hidden in presentation rather than rewritten. No normal read performs a migration.

Every current backend record type has a registry definition. The generic `general` type and unknown runtime values present as “Other item,” without discarding stored details. Person and Provider are useful future types, but this phase does not silently map them to unrelated fields or add new persistence semantics.

## Guided tracking workflows

`frontend/src/lib/guidedWorkflows.ts` is the scenario configuration source for passport expiration, vehicle registration, pet vaccination, and subscription renewal. It references the entity registry rather than redefining item capabilities. `GuidedWorkflowDrawer` provides one five-step experience, and `guidedWorkflowEngine.ts` composes the existing item, detail, protected-detail, reminder, relationship, and document APIs.

Guided tracking is orchestration, not a new persisted domain. No serialized workflow draft is stored on an item. A responsibility remains an ordinary editable reminder and now carries only a stable bounded workflow ID where Phase 12 needs an unambiguous item-date mapping. A document remains a scanned record attachment, and the connection remains a user-scoped `reminder_for` link. Existing generic Add item, Add reminder, custom detail, protected detail, document, and related-item paths remain available.

The workflow engine keeps its correlation ID, successful object IDs, operation status, and protected draft values in active component memory only. Item, reminder, and document creation use operation-specific idempotency keys. Correct pre-existing relationships and duplicate dynamic-detail retries are treated as completed work. A retry calls only unfinished operations and reports document scanning separately from upload completion. Closing an unfinished flow clears its in-memory state; protected plaintext is never written to browser storage, URLs, logs, search, or persistent workflow state.

Existing-item setup starts from the selected compatible active item, preserves unrelated fields, and requires an explicit keep-or-update choice for conflicting visible values. Protected values are never prefilled; entering a replacement is the explicit replacement action. Archived and incompatible items are not offered.

## Product rules for future phases

Phase 13 does not change this product model. Account export/deletion and reconciliation are operational capabilities around the existing user-owned entities, not new Items, Responsibilities, Documents, workflows, or user-facing history types. Reconciliation never appears as an ordinary-user dashboard and never manufactures lifecycle facts.

- Future guided tracking flows must extend the shared configuration and engine, compose the existing APIs, and map every suggested detail to the entity registry.
- Suggested details should reduce setup work; custom details remain the escape hatch for information the registry does not anticipate.
- Relationships should be inferred from the action context whenever safe, with manual editing kept secondary.
- Extend responsibility history only through the focused lifecycle service and explicit event types. Do not derive events from static timestamps or expose operational audit noise.
- Future ownership, provider, and household features must preserve current authorization, private-value, and user-scoping invariants.
