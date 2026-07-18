# Guided tracking workflows

Guided tracking lets a user express a familiar goal and set up the existing LifeLedger primitives as one coherent experience. It reduces form and relationship decisions; it does not introduce a new backend domain, persistent workflow record, or scenario-specific API.

## Supported workflows

| Intent | Item | Responsibility | Default schedule | Optional document |
| --- | --- | --- | --- | --- |
| Track passport expiration | Passport | Passport renewal | Six months before expiration; one time | Passport scan or renewal receipt |
| Track vehicle registration | Vehicle | Registration renewal | One month before registration expiration; yearly | Registration document |
| Track a pet vaccination | Pet | `<vaccination name> vaccination` | Two weeks before the next due date; one time by default | Vaccination record |
| Track a subscription renewal | Subscription | Subscription renewal | Two weeks before the next billing date; recurrence follows billing frequency | Receipt, agreement, or cancellation policy |

The global Add drawer and Home quick starts expose all four. Compatible item Responsibility sections expose only the workflow for that item type and launch with that active item preselected. The generic Add item and Add reminder paths are unchanged.

## Architecture

- `frontend/src/lib/guidedWorkflows.ts` defines stable IDs, user-facing copy, steps, entity-registry mappings, reminder defaults, document guidance, relationship semantics, review copy, and completion copy.
- `frontend/src/components/GuidedWorkflowDrawer.tsx` owns the active in-memory form, progress, conflict choices, optional file, accessibility behavior, and completion UI.
- `frontend/src/lib/guidedWorkflowEngine.ts` composes the existing APIs, records completed operations, and retries only unfinished operations.
- The current record, dynamic-detail, protected-detail, reminder, relationship, attachment, and search-projection services remain authoritative.

No workflow state is serialized into record titles, categories, notes, browser storage, or opaque metadata. The engine correlation ID exists only for the active setup and idempotency requests.

## Primitive mapping

| Workflow value | Existing primitive |
| --- | --- |
| Passport holder | Passport `title` and `owner_name` |
| Passport expiration / issue date | `expiration_date` / `issue_date` record properties |
| Issuing country | `provider_or_brand` record property |
| Passport number | Encrypted legacy protected `document_number`; never a normal detail or search term |
| Vehicle name / make | Vehicle `title` / `provider_or_brand` |
| Vehicle model / year | Dynamic details `model` / `year` from the entity registry |
| License plate | Sensitive dynamic detail `license_plate`; masked and excluded from search |
| VIN | Encrypted legacy protected `vin`; never a normal detail or search term |
| Registration expiration / authority | Dynamic details `registration_expiration` / `registration_authority` |
| Pet name | Pet `title` |
| Breed / birthday / veterinarian | Dynamic details `breed` / `birthday` / `vet` |
| Vaccination, administered date, next due date, provider, notes | Existing maintenance reminder title, due date, `maintenance_details`, and notes |
| Subscription name / provider / renewal date | Subscription `title`, `provider_or_brand`, and `renewal_date` |
| Price / billing frequency / cancellation information / website | Dynamic details `cost`, `billing_cycle`, `cancellation_info`, and `website` |
| Passport, vehicle, and subscription responsibility | Existing renewal reminder and `renewal_details` |
| Pet vaccination responsibility | Existing maintenance reminder and `maintenance_details` with `maintenance_area=pet` |
| Item-to-responsibility connection | Existing `reminder_for` relationship |
| Optional file | Existing secure record attachment metadata and S3 quarantine/scan/clean workflow |

Every dynamic detail key above is registered in `entityRegistry.ts`. The workflow stores no hidden scenario marker. Search is refreshed by the normal item, detail, reminder, relationship, and document mutations and continues to exclude protected values.

## Existing-item safety

Only active items of the workflow's associated type are selectable. Existing item input is built from the full current item, so unrelated fields, tags, notes, documents, and links remain unchanged. A different visible value requires an explicit Keep current or Update item choice. Protected values are never revealed or prefilled; the user must type a replacement to request one.

## Idempotency and partial success

One in-memory correlation ID produces separate keys for item, responsibility, and document creation. The backend derives deterministic user-scoped IDs for those operations. The relationship service's canonical duplicate check remains authoritative, and an already-existing correct relationship is accepted as completed setup. Dynamic detail keys are unique within an item, so a repeated creation attempt cannot create a second concept with the same key.

The engine keeps successful item/reminder IDs, detail keys, relationship status, protected status, and document results in memory. Network or service failures are reported by stage. Retry skips completed work and calls only unfinished operations. The item remains accessible after a later child operation fails. A skipped document is reported as not included; an accepted upload retains the existing scanning state and is never described as clean before the scan finishes.

## Privacy and trust rules

- Protected plaintext lives only in active React state, is sent only to the protected endpoint, and is cleared when setup is discarded or completed.
- Protected drafts are never written to local/session storage, a URL, logs, cache metadata, search, or a persistent recovery object.
- Documents use the existing PDF/JPEG/PNG, 10 MB, ownership, KMS, quarantine, validation, malware-scan, preview, and exact-document navigation rules.
- Guided tracking performs no OCR, extraction, AI, medical interpretation, legal advice, or financial advice.
- Subscription copy discourages passwords, authentication codes, and full payment-card information. Passport uploads are optional and not pressured.

## Adding a future workflow

1. Confirm that the item type and every reusable detail concept exist in `entityRegistry.ts`. Add a stable registry detail only when the product concept is genuinely new.
2. Add one stable workflow ID and one configuration entry in `guidedWorkflows.ts`. Map all values to existing record, detail, protected, reminder, relationship, or document primitives.
3. Prefer existing reminder subtypes and relationship semantics. Stop and document the gap if the scenario cannot be represented accurately.
4. Add any narrowly needed builder branch to the shared mapping layer; do not copy the drawer or engine.
5. Add registry validation, builder, retry/idempotency, review-copy, global-entry, compatible-item, and privacy tests.
6. Update this document only after the workflow is implemented.

## Deferred

General event/history persistence, timelines, renewal history, household sharing, new owner/provider entities, OCR, document extraction, AI/RAG, automatic recommendations from document contents, new notification channels, two-way calendar sync, and additional workflows are not implemented.
