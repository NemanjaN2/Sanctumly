# Sanctumly adaptive model routing

## Text routing

- Primary: Cloudflare Workers AI `@cf/qwen/qwen3-30b-a3b-fp8`.
- Direct reasoning route: Groq `openai/gpt-oss-120b` for prompts matched by the deterministic high-complexity rules in `app/ai/router.py`.
- Research synthesis: Groq GPT-OSS when the existing Serper search flow ran for the request.
- Fallback: Groq GPT-OSS when Cloudflare credentials are missing, Cloudflare is temporarily unavailable, its daily Neuron allocation is exhausted, or Sanctumly reaches its provider safety threshold.
- Images, transcription and TTS remain on their existing Groq paths. The Cloudflare Qwen model configured here is the text-generation path.

## Creator identity and limits

Creator is resolved from the authenticated server-side account record. The canonical creator is the account whose username is `father` and whose `is_creator` database flag is true. The application creates/maintains this account from the `FATHER_PASSWORD` Railway variable. Client-supplied usernames alone never grant Creator privileges.

Creator bypasses Sanctumly per-user daily quotas, the per-user AI budget, and the hourly chat-message limiter. This does not bypass Cloudflare account-wide Neuron quotas or Groq organization-level limits.

## Shared Cloudflare accounting

`provider_daily_usage` is keyed by provider and UTC date, not by username. Every Sanctumly account therefore contributes to one Cloudflare Neuron ledger. Reservations are acquired under a database row lock before inference and reconciled against `usage.neurons` from the Cloudflare response afterwards. Concurrent requests share the same ledger across Railway instances that use the same PostgreSQL database.

The Cloudflare Free allocation is 10,000 Neurons/day. Sanctumly defaults to a 9,000-Neuron internal cutoff, leaving a 1,000-Neuron safety buffer. The ledger automatically uses a new row on the next UTC date. If Cloudflare reports quota exhaustion earlier (for example, because another application used the same Cloudflare account), the provider circuit breaker marks Qwen exhausted for the rest of that UTC day and all accounts switch to Groq.

The app's ledger only observes Sanctumly traffic. It cannot see unrelated Playground/API usage outside Sanctumly. The Cloudflare provider-side quota response remains the final guard for such external usage. Qwen's documented context window is 32,768 tokens; the configured `CLOUDFLARE_CREATOR_MAX_OUTPUT_TOKENS` is a per-response generation ceiling, not a daily message/budget quota.

## Railway variables

Required for Qwen primary routing:

```text
CLOUDFLARE_ACCOUNT_ID=<Cloudflare account ID>
CLOUDFLARE_API_TOKEN=<Workers AI API token>
```

Optional routing controls (defaults shown):

```text
CLOUDFLARE_MODEL=@cf/qwen/qwen3-30b-a3b-fp8
CLOUDFLARE_DAILY_NEURON_BUDGET=9000
CLOUDFLARE_NEURONS_PER_ESTIMATED_TOKEN=0.04
CLOUDFLARE_MIN_NEURON_RESERVATION=10
CLOUDFLARE_FAILURE_COOLDOWN_SECONDS=60
CLOUDFLARE_FREE_MAX_OUTPUT_TOKENS=1024
CLOUDFLARE_CREATOR_MAX_OUTPUT_TOKENS=4096
GROQ_MODEL=openai/gpt-oss-120b
```

Keep both provider credentials private in Railway. Never put them in the frontend, source control, issue reports, or chat messages.

## Diagnostics

The creator-only endpoint `GET /chat/provider-status` reports the shared Cloudflare ledger status, usage estimate, budget, and UTC reset time. It does not expose provider credentials.

Text responses also include additive metadata fields: `provider`, `model`, `routing_reason`, and `fallback_used`. Existing response fields are retained.

## Streaming behavior

`POST /chat/stream` keeps the existing SSE event schema, but the upstream model request is non-streaming. The completed answer is then emitted as small SSE text pieces. This is intentional for the first rollout: it avoids the Cloudflare streaming response duplication observed in the earlier tests and keeps the existing mobile/web event contract. The UI receives the same concatenated answer but the first text event arrives after model generation completes.

## Current scope and next infrastructure step

This version implements Cloudflare Qwen → Groq GPT-OSS. Oracle is not active because this backend package does not yet have a deployed Oracle OpenAI-compatible inference endpoint or its credentials. It can be added as the next provider without changing the client contracts.

## Tests

Run with the project's requirements installed:

```bash
python -m unittest discover -s tests -v
```


## AI Control Center (v9.2.0 baseline, extended in v9.3.1)

The Creator-only React dashboard is part of the Vercel frontend at:

`/admin/ai-control`

The route is displayed only for the canonical Creator account in the UI, and every dashboard data/control API call is independently protected by the backend `require_creator` dependency. The frontend reuses the app's existing Bearer session token from its authentication helper; it does not ask the user to paste a token into the dashboard.

### Dashboard endpoints

- `GET /admin/ai-control/overview?days=7` — provider configuration/observed state, shared Cloudflare usage, routing distributions, fallback counts, request latency, search usage, and the latest 20 privacy-minimal routing events in the selected period.
- `PUT /admin/ai-control/override` — set a temporary routing override. Body: `{"mode":"groq","duration_minutes":60}` to force GPT-OSS for 15–1440 minutes, or `{"mode":"auto"}` to restore adaptive routing.

Overrides are stored in the existing `settings` table and expire automatically. The override affects text inference only; it does not bypass regular-account application limits, Cloudflare quota protections, or provider-side rate limits. This is a global override that affects all Sanctumly accounts.

### Routing telemetry

The additive `ai_routing_events` table records provider, model, route reason, fallback flag, success, account type (creator/standard), latency, and measured Neurons when available. It deliberately does not store prompt text, completion text, usernames, session IDs, or credentials. Existing deployments create the new table during the normal SQLAlchemy `init_db()` startup.

Groq's status is inferred from its most recent recorded request, not an active synthetic provider probe. Historical routing analytics begin accumulating after the AI Control Center routing-event table is deployed; token/cache fields are populated from v9.3.0 onward.


## Token optimization (v9.3.1)

- The supplied static-first `CORE + MODE + CONTEXT` prompt implementation is retained without editing the CORE identity wording or Hacker mode.
- Standard requests use an estimated history budget of 2,200 tokens and retrieved-context budget of 2,600 tokens; Creator uses 4,500 for each. These are per-request context bounds, not daily account quotas.
- History still has the 10-message standard / 12-message Creator ceiling, with additional token and per-message character guards. The current user message is never discarded by history trimming.
- URL content, search results, RAG chunks, conversation memory and therapist guidance share the retrieved-context budget.
- GPT-OSS reasoning effort is explicit: normal low, research/complex medium, Cybersecurity mode high. Cybersecurity mode routes directly to GPT-OSS rather than Qwen's `/no_think` path.
- Groq GPT-OSS cache usage is read from `usage.prompt_tokens_details.cached_tokens`. Only reported cached tokens get the configured 50% discount. Cache savings are stored in routing events and exposed in the Creator AI Control Center.
- `ai_routing_events` receives nullable additive columns at startup; existing rows remain readable. No database reset is required.


## v9.3.1 telemetry correction

The `estimated_groq_text_cost_usd` dashboard aggregate filters to `provider = groq` and excludes any event marked `vision_request`. It is intentionally a Groq text-routing metric, not a total across every provider or modality.
