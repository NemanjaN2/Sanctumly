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
