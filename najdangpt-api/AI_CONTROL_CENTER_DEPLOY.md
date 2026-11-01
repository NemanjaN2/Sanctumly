# Deploying the Sanctumly AI Control Center

This release adds the Creator-only React AI Control Center to the existing Vercel frontend and its protected telemetry/control API to the Railway backend.

## Deploy order

1. Replace the Railway backend repository contents with this `najdangpt-api` folder and deploy. Wait for the service to reach `Application startup complete` and report API version `9.2.0`.
2. The normal SQLAlchemy startup calls `create_all`, which creates the additive `ai_routing_events` telemetry table. The manual override uses the existing `settings` table; no destructive migration or database reset is required.
3. Replace the Vercel frontend repository contents with this `najdangpt-frontend` folder and deploy. Existing Vercel SPA rewrites already support direct page loads at `/admin/ai-control`.
4. Sign in with the canonical Creator account and open `https://sanctumly.space/admin/ai-control` or use the new Creator-only sidebar link.

## Dashboard capabilities

- Shared Cloudflare Neuron ledger and UTC reset time.
- Groq and Serper configuration/observed status.
- Routing request, success, latency, fallback, and provider-distribution metrics.
- Latest 20 privacy-minimal routing events in the selected analytics period.
- Temporary global GPT-OSS override (15 minutes to 24 hours) and restore-to-automatic action.
- Automatic refresh every 30 seconds.

All dashboard API endpoints are protected by the backend `require_creator` dependency. The React page reuses the logged-in app session; it does not ask the user to paste a Bearer token. The frontend route guard is for navigation only—the backend remains authoritative.

## Manual override behavior

`Force GPT-OSS` affects text inference for all accounts, while normal per-account application limits and provider-side limits remain in effect. The override expires automatically. `Automatic` clears the override and restores the standard routing policy (Qwen primary when eligible, direct Groq for research/complex tasks, and Groq fallback when Cloudflare is unavailable/exhausted).

Do not use the manual override as a quota-reset mechanism. It does not add Neurons or change the shared Cloudflare ledger.

## Deployment safety

- Keep `CLOUDFLARE_API_TOKEN`, `GROQ_API_KEY`, and `SERPER_API_KEY` only in Railway private variables.
- Do not commit `.env`, live tokens, session IDs, or database URLs.
- Keep `free-tier.example.env` as a placeholder template only.
- No frontend dependencies were added by this dashboard release.
