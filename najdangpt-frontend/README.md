# Sanctumly Web Frontend

React 19 + Vite frontend for Sanctumly. The existing API client modules and backend contracts are retained.

## Requirements

- Node.js 20.19+ or 22.12+
- npm

## Local development

```bash
npm install
cp .env.example .env.local
npm run dev
```

By default, the frontend connects to the production API at `https://sanctumly-production.up.railway.app`. Set `VITE_API_URL` in `.env.local` to point to another API environment. Do not commit secrets or real `.env` files.

## Production build

```bash
npm run build
npm run preview
```

The production bundle is generated in `dist/`. Vercel rewrites are retained in `vercel.json`.

## Refreshed visual system

The web interface now uses the Sanctumly midnight-violet palette shared with the iOS and Android applications: `#0E0B1D`, `#2A1E4D`, `#5A3B8C`, `#8B7CC7`, `#C9C2E3`, and `#3A3A52`. Shared overrides live in `src/theme-refresh.css`. The app shell, chat composer, voice view, welcome state, landing page, login, wellness and admin surfaces are styled from this system.

The launcher/PWA artwork in `public/` uses the updated matte emblem. The service worker cache version was advanced so deployed clients can fetch the refreshed assets.

## Existing backend

The backend remains in `../najdangpt-api/`. This frontend refresh does not change API routes, authentication payloads, chat/session identifiers, upload formats, streaming protocol, speech endpoints, or mood tracking requests.
