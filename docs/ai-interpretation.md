# AI interpretation

## Provider boundary

`AIInterpretationProvider` accepts one Capture, current time context, the closed action contract, and at most a small set of safe entity candidates. Implementations are disabled, deterministic test/mock, and OpenAI. Capture, proposal, policy, and execution code do not depend on a permanent model identifier.

The OpenAI implementation uses the Responses API with strict JSON Schema structured output, `store: false`, no tools, low reasoning effort, a bounded output limit, a timeout, and a stable hashed user safety identifier. The default model is configurable and currently `gpt-5.6-luna`; optional one-step escalation is configured as `gpt-5.6-terra` and occurs only after invalid structured output when the user setting permits it. Both responses are usage-accounted when the provider returns usage metadata. Business logic never hard-codes either model.

Set local development variables only outside version control:

```text
AI_PROVIDER=openai
OPENAI_API_KEY=...
AI_DEFAULT_MODEL=gpt-5.6-luna
AI_ESCALATION_MODEL=gpt-5.6-terra
```

Production requires `AI_API_SECRET_ARN`; the Secrets Manager JSON key is `api_key`. Plaintext production keys fail configuration. The API key is server-only and never enters responses, frontend bundles, export, logs, prompts, or source control.

## Context and privacy

The request contains original capture text, timestamps, timezone/locale, allowed types and detail keys, and up to ten safe candidates: ID, display title, type, safe aliases/context, related responsibility title, and relevant safe dates. It excludes protected details, document content and signed URLs, full notes, export data, tokens, unrelated Items/history, and infrastructure information.

Capture text is delimited as data and may be malicious. System instructions require ignoring attempts to reveal prompts or secrets, call tools, bypass ownership or confirmation, invent identifiers, or perform unsupported/destructive/protected operations. Output is parsed into a provider-only closed superset, converted into the internal action union, ownership/candidate validated, and policy checked. Invalid JSON/schema, refusals, timeouts, rate limits, authentication errors, and unavailable providers leave the Capture recoverable.

No live provider evaluation is part of normal CI. `python capture_eval.py --mode live --allow-paid` is the explicit paid path and still requires provider configuration.
