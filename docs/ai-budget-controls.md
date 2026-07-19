# AI budget controls

Deterministic interpretation runs before AI by default and does not consume provider budget. The per-user defaults are:

- AI enabled
- $5.00 estimated monthly budget
- 50 provider requests per day
- 2,000 estimated input-token preflight limit
- 1,200 output-token request cap
- one configured clarification call and at most one configured model escalation

The server checks the emergency disable, user setting, input ceiling, daily count, and current monthly estimate before any provider request. Budget or disabled denial makes no provider call and leaves the original Capture in the Inbox.

Usage rows contain user/capture references, provider request ID, provider/model, input/output token counts, estimated cost, safe result category, and billing day/month. They never contain capture text, prompts, responses, clarification answers, notes, protected values, or credentials. Provider request IDs produce deterministic usage IDs, preventing a retried response from being charged twice in LifeLedger accounting.

Estimated cost uses configurable per-million-token rates. It is a guardrail, not an invoice. Unknown-model pricing is recorded as zero and requires operational configuration review. Settings shows estimated spend and request counts but normal Capture UI does not show token data.

Deployment defaults and ceilings are configurable with `AI_DEFAULT_MONTHLY_BUDGET_USD`, `AI_DEFAULT_DAILY_REQUEST_LIMIT`, `AI_INPUT_TOKEN_LIMIT`, `AI_OUTPUT_TOKEN_LIMIT`, `AI_MAX_CLARIFICATION_CALLS`, `AI_MODEL_PRICING_JSON`, and the emergency `AI_EMERGENCY_DISABLED` switch. Per-user settings can lower or raise the monthly and daily defaults only within the server-side schema bounds.
