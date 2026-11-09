# Sanctumly v9.3.1 — Token Optimization

This update preserves the supplied `app/prompts/system.py` prompt definitions,
including the full CORE identity block and the entire Cybersecurity/Hacker mode.
It does not modify Creator daily usage privileges or provider routing semantics.

## Changes

### 1. Bounded per-request context

- Standard accounts: 2,200 estimated history tokens + 2,600 estimated retrieved-context tokens.
- Creator: 4,500 estimated history tokens + 4,500 estimated retrieved-context tokens.
- Existing message-count ceilings remain: 10 standard / 12 Creator.
- Historical messages are selected newest-first and emitted chronologically.
- Retrieved URL, web-search, RAG, memory and therapist guidance share a context budget.
- The current user message is not trimmed by these historical-context budgets.
- These limits are per-request context controls, not daily quotas. Creator remains unlimited at the application usage level.

Token counts are conservative estimates using approximately 2.5 characters per token. This avoids adding a tokenizer dependency and intentionally budgets conservatively for mixed English/Serbian/code content. Actual provider usage is separately recorded.

### 2. GPT-OSS reasoning controls

All GPT-OSS text requests now send an explicit `reasoning_effort` using Groq's OpenAI-compatible `extra_body` mechanism:

- Normal requests: `GROQ_REASONING_DEFAULT` (default `low`).
- Research / high-complexity routes: `GROQ_REASONING_DEEP` (default `medium`).
- Cybersecurity mode: `GROQ_REASONING_CYBER` (default `high`).

Creator requests receive the same reasoning-effort policy, but Creator output-token caps and application usage limits remain unchanged (Creator text completion remains uncapped by the standard-account max-token setting).

### 3. Actual cache-aware Groq accounting

For supported GPT-OSS models, actual `prompt_tokens_details.cached_tokens` is captured. Only explicitly reported cached tokens receive the configured 50% input-price discount. Vision calls do not receive this text caching discount. If usage details are missing, cost falls back to estimated tokens without assuming a cache hit.

### 4. Routing telemetry and AI Control Center

`ai_routing_events` now records nullable fields for:

- prompt tokens
- cached prompt tokens
- completion tokens
- reasoning tokens
- estimated Groq provider cost
- reasoning effort

AI Control Center overview adds total input/output/reasoning tokens, Groq cache hit rate, estimated Groq provider cost and reasoning-effort distribution. Recent events include per-request usage metrics. Existing historical rows remain valid with null metrics.

### 5. Database migration

Startup adds the new nullable columns to an existing `ai_routing_events` table using an additive migration. No tables are dropped, no existing rows are rewritten, and no database reset is required.

## Railway variables

The defaults are defined in `app/config.py`; the same optional values are listed in `free-tier.example.env`. Railway Variables are not overwritten automatically. Set overrides only if needed.

```env
HISTORY_TOKEN_BUDGET=2200
CREATOR_HISTORY_TOKEN_BUDGET=4500
RETRIEVED_CONTEXT_TOKEN_BUDGET=2600
CREATOR_RETRIEVED_CONTEXT_TOKEN_BUDGET=4500
GROQ_REASONING_DEFAULT=low
GROQ_REASONING_DEEP=medium
GROQ_REASONING_CYBER=high
GROQ_PROMPT_CACHE_DISCOUNT=0.5
```

## Compatibility and safety

- Existing chat endpoint paths and response contracts are retained.
- Gemma 4 remains non-streaming upstream; the current SSE chunking contract remains unchanged.
- Groq automatic prompt caching requires no explicit cache API option. Cache savings are counted only when Groq reports cached tokens.
- No prompts, completions, usernames, session IDs, or credentials are added to routing telemetry.
- Existing shared Cloudflare Neuron accounting and Creator bypass behavior are retained.


## v9.3.1 correction

The AI Control Center's estimated Groq text cost is now aggregated only from Groq text-routing events, excluding other providers and any event explicitly labeled as a vision request.
