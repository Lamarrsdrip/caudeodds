# ClaudeOdds — PRD

## Original Problem Statement
Build a realistic, long-term profitable AI sports betting intelligence SaaS using a multi-agent ensemble (Claude + GPT). Users pay a monthly subscription (₦5,000/month) for one combined daily slip with total odds 2.0–5.0, mixing football & basketball, plus a SportyBet booking code. Trial is 3 days. Brand: "ClaudeOdds" with "Made by emriz.eth" footer.

## CRITICAL: Real-money production app
The user has emphasized this is NOT a demo. People bet real money. Every fixture, every price, every booking code MUST be real, not synthetic.

## Architecture
- Backend: FastAPI + MongoDB + Motor (async)
- Frontend: React (CRA) + Tailwind + shadcn/ui
- AI: Anthropic Claude Haiku 4.5 + OpenAI GPT-4o-mini via Emergent LLM Key
- Sports data: The Odds API (free tier, key in backend/.env as THE_ODDS_API_KEY)
- Payments: Flutterwave (sandbox by default) + manual bank transfer with admin proof approval
- PWA: manifest, install prompt, transparent logo

## Implemented (Cumulative)

### Phase 1 — Core SaaS (earlier sessions)
- JWT auth (register/login/me/logout, brute-force protection by email)
- 3-day free trial on registration
- Subscription gating, paid status check
- Admin panel: stats, users, payments approval, configuration, predictions, rejected log
- Flutterwave init/verify/webhook + bank transfer proof flow
- Multi-agent AI pipeline: Research (Claude) → Quant (GPT) → Tactical (Claude) → Consensus
- Slip builder: greedy-pack 3-5 picks into 2.0-5.0 combined odds
- PWA install prompt, dark theme, EmrizFooter brand
- Branding: "ClaudeOdds" + "AI BETTING COMPANION" tagline

### Phase 2 — Real data refactor (this session, 2026-05-10)
- ✅ **Real fixtures via The Odds API** — replaced mock `data_engine.py` (was generating synthetic team names from a hardcoded pool) with real bookmaker-aggregated fixtures from `https://api.the-odds-api.com/v4`. New file `odds_api_service.py` fetches 7 football leagues (EPL, La Liga, Serie A, Bundesliga, Ligue 1, Champions League, Europa League) + 2 basketball leagues (NBA, EuroLeague). Caches active sports list. Aggregates odds across 5-15 books, derives sharp/public split + liquidity + volatility from book dispersion.
- ✅ **No more fake SportyBet codes** — removed `make_sportybet_code()` (hash-based fake generator). Slip now ships with empty `sportybet_code` by default. Admin pastes the real code from SportyBet into a new admin field; subscribers see "Booking code being prepared" with manual-entry instructions until then.
- ✅ **New endpoints**: `GET /api/admin/slip/code`, `POST /api/admin/slip/code`. New collection `claudeodd_slip_codes` (keyed by date).
- ✅ **Background-job pipeline** — `/api/slip/generate` was timing out at the K8s ingress (~60s) because real-data pipeline takes 90-180s. Now returns `{status:'running', job_id}` in <1s and runs the ensemble in `asyncio.create_task`. New polling endpoint `GET /api/slip/generate/status/{job_id}`. Frontend `AdminPredictions` polls every 4s until completion. New collection `claudeodd_jobs`.
- ✅ **Event-loop responsiveness fix** — LLM calls (LiteLLM/emergentintegrations) were blocking the asyncio event loop, making the entire app feel slow during pipeline runs. Wrapped each call in `asyncio.to_thread(...)` so other API requests stay responsive (verified <15ms response times during a running pipeline).
- ✅ **Updated LLM prompts** — research/quant/tactical agents now treat bookmaker market dispersion as the PRIMARY signal (instead of expecting injury/xG/weather data which the free tier doesn't provide). Lowered research-quality threshold from 35 to 25.
- ✅ **Logo wired** — `/logo-icon.png` (background-removed user upload) now renders in `AppHeader` on every page.
- ✅ **Polished**: data-testids added to admin SportyBet code controls; `LOCKED` placeholder removed from teaser code; concurrency raised from 6→12 ensemble workers.

## Validated
- Real fixtures verified end-to-end: Nottingham Forest vs Newcastle, AC Milan vs Atalanta, Bayern Munich vs Eintracht Frankfurt, 76ers vs Knicks, Fiorentina vs Genoa, Mallorca vs Villarreal, Crystal Palace vs Everton, Rayo Vallecano vs Girona, Oviedo vs Getafe (2026-05-10/11).
- Pipeline run: 16 real fixtures analyzed → 7 picks → combined odds 4.0, conf 89%, EV +18.5%.
- Background job pattern confirmed: POST returns in <1s, polling resolves to completed status.
- Concurrent responsiveness during pipeline: /api/auth/me and /api/slip/today both respond in 12-14ms.
- Admin SportyBet code endpoints + UI (input → publish → live indicator → reflect in subscriber slip).
- 17/19 backend pytest cases pass.

## Backlog / Roadmap

### P0 (blockers for production confidence)
- **Cron schedule for daily run** — currently admin must click "Force Re-Generate" each day. Add a daily cron (e.g. APScheduler) that auto-runs the pipeline at a fixed UTC hour and notifies admin to paste the SportyBet code.
- **Brute-force lockout fix** for K8s IP-rotation (carry-over from iter_2; current workaround uses email as identifier).

### P1 (revenue / UX)
- Web Push notifications when admin publishes the SportyBet code (the moment subscribers most need a ping).
- Live Flutterwave keys configuration UI (currently sandbox).
- Admin payment-proof viewer + larger image preview.
- Slip history performance: paginate beyond 60-day window.

### P2 (data depth)
- Integrate API-Football for injury/lineup/form/xG data — would significantly improve pick approval rate and confidence (currently the AI rejects ~50% of fixtures due to thin context).
- Historical accuracy dashboard (won/lost/void per day, ROI tracking).
- Push the daily slip to a Telegram channel as well.

## Tech Choices Locked In
- DON'T modify supervisor configs.
- DON'T break CORS.
- DO use REACT_APP_BACKEND_URL on the frontend; MONGO_URL/DB_NAME on the backend.
- DO route all backend endpoints through `/api`.

## Production Note
The user has deployed this app to https://probability-vault.emergent.host. Bug reports should be checked against both preview AND production environments. Code fixes happen in preview only — production is updated via the platform's deploy step (not in this agent's scope).
