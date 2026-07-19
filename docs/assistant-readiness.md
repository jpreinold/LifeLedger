# Assistant readiness

Phase 14 establishes the internal assistant boundary, not an external assistant integration.

An authenticated LifeLedger web client can create a durable text Capture. Deterministic or provider-backed interpretation produces strict proposed actions using limited safe context. LifeLedger retrieves candidates, validates ownership and supported fields, applies deterministic risk policy, asks clarification, requires human confirmation, and executes only through application services. Failed, disabled, and over-budget captures remain recoverable.

Future Siri, Apple Shortcuts, Share Sheet, and private ChatGPT clients should terminate at a scoped External Assistant Gateway that creates Captures. They must never receive raw CRUD, repository, protected-detail, document-content, or lifecycle-history write access. Phase 15 must design OAuth client grants, revocation, external rate limits, client/source audit, and narrowly scoped capture APIs before any such client is enabled.

Not ready/implemented: external OAuth, public capture, Siri/Shortcuts/Share Sheet, GPT Actions, document/OCR/image/audio capture, protected writes, destructive or automatic execution, conversational retrieval, proactive intelligence, vector search/RAG, or multi-agent orchestration.
