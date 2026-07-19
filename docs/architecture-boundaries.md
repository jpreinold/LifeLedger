# Architecture boundaries

Phase 13 preserves the Phase 9–12 public model and API while reducing orchestration risk. `Record`, `Reminder`, attachment, link, and lifecycle persistence names remain compatibility details; the product still presents Items, Responsibilities, Documents, and lifecycle history.

## Backend

FastAPI startup owns middleware, exception behavior, CORS, and router inclusion. Shared dependency composition and response helpers live in `route_support.py`; handlers live in health/version, records, reminders, lifecycle, documents, relationships, search, preferences, integrations, push, and account router modules. Paths, status codes, response models, authentication, no-store headers, and OpenAPI paths are characterized before and after extraction. Router modules do not import `main.py`, so application startup has no circular route dependency.

Routes authenticate, validate input, call an application service, and map known failures. Focused concrete services own export, deletion, integration cleanup, reconciliation, lifecycle, and search projection coordination. Repositories own persistence and bounded pagination, not product orchestration. Startup factories remain lazy so imports and tests do not contact AWS or create mutable global resources.

Operational maintenance is an AWS-authenticated Lambda/CLI capability, not an ordinary-user API. Future routes belong to the smallest existing context; an unrelated catch-all router or HTTP exception inside a repository requires explicit justification.

## Frontend

The authenticated shell still coordinates item, reminder, drawer, and workflow state, while Phase 13 account behavior is isolated under `features/account`, safe page history under `features/navigation`, and Settings plus push/calendar orchestration under `features/settings`. Account API types and requests remain independent of Settings integrations. Existing lazy boundaries for search, workflows, history, item/reminder drawers, and PDF code remain intact. A large global-state framework was intentionally not introduced.

The shared API client owns the base URL, bearer/correlation headers, abort signals, no-content parsing, normalized safe errors, and authentication-expiry notification. It never automatically retries unsafe writes. S3 upload remains specialized because it uses a presigned cross-origin request instead of the LifeLedger API.

Post-deployment verification follows the deployed frontend's bounded JavaScript dependency graph and fails unless it contains the exact API stack output URL. This detects a stale Cloudflare Pages API build setting without exposing credentials.

## Navigation decision

Only the safe main page is routeable through `?page=`. Refresh and browser back preserve Home, Items, Reminders, Calendar, Search, or Settings, and unknown values fail to Home. Existing OAuth/digest query parameters are preserved. Item/reminder drawers, exact-document target, protected values, and form drafts remain in memory; this avoids exposing private content or destabilizing current PWA/document behavior. Exact-document navigation therefore retains the tested Phase 12 coordinator rather than moving protected or temporary state into URLs.

## Rules for future additions

- Register each new user-owned store in the centralized account inventory with bounded list/count/delete and explicit export/retention behavior.
- Add a reconciliation detector only for persisted, verifiable evidence and a repairer only when it is idempotent and unambiguous.
- Add route characterization before moving a public endpoint.
- Keep private values out of URL, search, logs, reconciliation summaries, alerts, and browser persistence.
- Keep operations bounded and cursor-based; do not add production table scans.
- Preserve repository ownership scoping and service-layer orchestration.
- Measure entry and lazy chunks before collapsing a frontend feature boundary.

## Phase 14 assistant boundary

Capture adds one deliberate chain: authenticated route → `CaptureApplicationService` → deterministic/provider interpretation → strict proposal → entity/policy validation → clarification/confirmation → `ActionExecutionService` → existing item, responsibility lifecycle, relationship, history, and search services. AI providers have no repository and cannot approve or execute. The execution service never exposes raw record/reminder routes to a model.

`features/capture` owns the frontend Inbox and quick-capture surface behind a lazy page boundary. Capture text and answers remain component/network state, use no-store responses, and never enter route query text or browser persistence. `route_support.py` composes the service graph; `routers/captures.py` contains the authenticated HTTP mapping.
