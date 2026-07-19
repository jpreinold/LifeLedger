# Capture entity resolution

LifeLedger retrieves candidates; the model may rank only those candidates. `EntityResolutionService` uses normalized exact/phrase title matching, safe alias matching, bounded results from the current search projection system, item type context, active status, existing one-hop responsibility relationships, recent confirmed proposal targets, and known responsibility titles. Archived Items and Responsibilities are excluded.

Candidate context is deliberately small: backend-owned ID, display title, item type, safe aliases, optional Person relationship context, one relevant responsibility title/ID, and safe dates. Protected fields, document contents/URLs, full notes, full history, and unrelated account data are never candidate context.

Multiple similarly strong people or responsibilities require a durable clarification. The UI asks “Which Alex did you mean?” and shows labels, not internal IDs or enums. Answers are checked against opaque option IDs derived from the proposal and retrieved candidates, then targets and policy are revalidated. No match remains unresolved when creation is uncertain. Materially ambiguous dates and existing-value conflicts are never silently guessed; conflicting high-risk updates must use the normal editor.

Recently completed/partially completed proposals provide a small deterministic ranking boost for their already confirmed targets. Richer workflow-specific retrieval remains a bounded future improvement. Vector search, RAG, document retrieval, and whole-account context are intentionally absent.
