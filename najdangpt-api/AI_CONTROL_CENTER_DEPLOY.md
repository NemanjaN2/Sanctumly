# Deploying the Sanctumly AI Control Center

This backend release retains the Creator-only AI Control Center and adds token-aware context budgets, cache-aware usage telemetry, Groq reasoning controls, and additive database columns.

## Deploy order

1. Replace the Railway backend repository contents with this `najdangpt-api` folder and deploy. Wait for the service to reach `Application startup complete` and report API version `9.4.0`.
2. The normal SQLAlchemy startup creates missing tables and runs an additive migration for nullable token/cache telemetry columns on existing `ai_routing_events` tables. The manual override uses the existing `settings` table. No destructive migration or database reset is required.
3. Replace the Vercel frontend repository contents with this `najdangpt-frontend` folder and deploy. Existing Vercel SPA rewrites already support direct page loads at `/admin/ai-control`.
4. Sign in with the canonical Creator account and open `https://sanctumly.space/admin/ai-control` or use the new Creator-only sidebar link.

## Dashboard capabilities

- Shared Cloudflare Neuron ledger and UTC reset time.
- Groq and Serper configuration/observed status.
- Routing request, success, latency, fallback, provider-distribution, input/output/reasoning token, cache-hit, cache-savings and estimated Groq-cost metrics.
- Latest 20 privacy-minimal routing events in the selected analytics period.
- Temporary global GPT-OSS override (15 minutes to 24 hours) and restore-to-automatic action.
- Automatic refresh every 30 seconds.

## Retained v9.3.1 token optimizations

See `TOKEN_OPTIMIZATION_v9.3.1.md` for request-history/context budgets, reasoning-effort policy, and cache-aware accounting. The prompt file is not changed by this update; the supplied CORE and all four mode definitions remain intact.

All dashboard API endpoints are protected by the backend `require_creator` dependency. The React page reuses the logged-in app session; it does not ask the user to paste a Bearer token. The frontend route guard is for navigation only—the backend remains authoritative.

## Manual override behavior

`Force GPT-OSS` affects text inference for all accounts, while normal per-account application limits and provider-side limits remain in effect. The override expires automatically. `Automatic` clears the override and restores the standard routing policy (Gemma 4 primary when eligible, direct Groq for research/complex tasks, and Groq fallback when Cloudflare is unavailable/exhausted).

Do not use the manual override as a quota-reset mechanism. It does not add Neurons or change the shared Cloudflare ledger.

## Deployment safety

- Keep `CLOUDFLARE_API_TOKEN`, `GROQ_API_KEY`, and `SERPER_API_KEY` only in Railway private variables.
- Do not commit `.env`, live tokens, session IDs, or database URLs.
- Keep `free-tier.example.env` as a placeholder template only.
- No frontend dependencies were added by this dashboard release.


## Retained v9.3.1 correction

- The AI Control Center's `estimated_groq_text_cost_usd` aggregate now explicitly filters to Groq text-routing events and excludes events labeled `vision_request`, so the Groq-only metric cannot accidentally include other providers.
- The additive migration test now verifies `cache_savings_usd` as well as the other nullable telemetry columns.


## v9.4.0 Cloudflare Gemma 4 migration

- Cloudflare primary model is `@cf/google/gemma-4-26b-a4b-it`.
- The known legacy Qwen3-30B Railway model setting is mapped to Gemma 4 at startup as a safety measure. Update Railway `CLOUDFLARE_MODEL` explicitly to `@cf/google/gemma-4-26b-a4b-it`.
- Gemma's chat template is configured with `enable_thinking=false` for ordinary chat; research, complex work and Creator cybersecurity continue to use Groq GPT-OSS.
- Groq GPT-OSS-120B remains the fallback. Existing quotas, shared Cloudflare Neuron tracking, Creator exemptions, context budgets, model-independent prompts and client SSE format remain unchanged.
- `app/prompts/system.py` was not modified.
