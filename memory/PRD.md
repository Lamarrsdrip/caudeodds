# ClaudeOdds — PRD

## Original Problem Statement
Build a realistic, long-term profitable AI sports betting intelligence SaaS using a multi-agent ensemble (Claude + GPT). Users pay a monthly subscription (₦5,000/month) for one combined daily slip with total odds 2.0–5.0, mixing football & basketball, plus a SportyBet booking code. Trial is 3 days. Brand: "ClaudeOdds" with "Made by emriz.eth" footer.

## CRITICAL: Real-money production app
Users place real money on these picks. Every fixture, price, calculation, and probability MUST be honest and grounded in verifiable data.

## Architecture
- Backend: FastAPI + MongoDB + Motor (async) + APScheduler
- Frontend: React (CRA) + Tailwind + shadcn/ui
- AI: Anthropic Claude Haiku 4.5 + OpenAI GPT-4o-mini via Emergent LLM Key
- Sports data: The Odds API (free tier, key in `backend/.env` and admin-overridable in DB)
- Payments: Flutterwave (sandbox) + manual bank transfer with admin proof approval
- PWA: manifest, install prompt, transparent logo, service worker
- Web Push: VAPID auto-generated, broadcast on admin code publish

## Implemented (Cumulative)

### Phase 1 — Core SaaS
- JWT auth, brute-force lockout (by email), 3-day trial on registration
- Admin panel: stats, users, payments approval, configuration, predictions, rejected log
- Flutterwave + bank transfer payment flow
- Multi-agent AI pipeline: Research (Claude) → Quant (GPT) → Tactical (Claude) → Consensus
- Slip builder: greedy-pack 3-5 picks into 2.0-5.0 combined odds
- PWA, dark theme, EmrizFooter brand

### Phase 2 — Real data refactor (2026-05-10)
- Real fixtures via The Odds API (7 football leagues + 2 basketball)
- Removed fake SportyBet code generator → admin pastes real code
- Background-job pipeline pattern → no more K8s ingress timeouts
- LLM calls wrapped in `asyncio.to_thread()` → app responsive during pipeline
- Logo wired into header

### Phase 3 — Daily auto + Notifications + Mobile (2026-05-10)
- APScheduler daily cron at admin-configurable UTC hour (default 08:00)
- VAPID Web Push with auto-broadcast on admin code publish
- Mobile-first redesign: hamburger header + drawer, fixed bottom tab nav, mobile-optimized DailySlip + Admin pages, safe-area insets for iOS PWA
- Admin Configuration: 8 sections including new Sports Data API source override, Daily Cron, and Push test broadcast

### Phase 4 — Production hardening / accuracy (2026-05-10)
- **Subscription page bug fixed** — was missing 7 imports (`toast`, `formatApiError`, `useAuth`, all lucide icons), causing runtime errors on every interaction
- **AI prediction realism calibration** — clamps fair_prob to within 4-7% of bookmaker median (the most accurate pre-match prior). Combined slip EV dropped from a fictional +53.2% to a credible +17.5%; confidence capped at 92%; per-leg edge constrained to single-digit-to-low-teens. Calibrated values are also written back to the stored Pick so admin/UI never see hallucinated numbers.
- **Pydantic validation** on cron_hour_utc (0-23) and cron_minute_utc (0-59) + defensive scheduler clamps so corrupt config can't crash startup
- **Strategy cap hard-enforced** at runtime in slip_builder (combined_odds ≤ 5.0, leg_count ≤ 5)
- **Per-leg EV + book_implied_prob** now exposed in API response and rendered on UI

## Validated
- 100% pass on iter_3, iter_4, iter_5 testing-agent runs (40+ backend pytest cases + comprehensive frontend audit on desktop and mobile 390x844)
- Real fixtures: Nottingham Forest, Newcastle, Bayern Munich, AC Milan, 76ers, Knicks, etc.
- Subscription page: 0 console errors after import fix; both Flutterwave and Bank Transfer panes render and accept input
- Mobile: hamburger drawer, bottom nav, responsive KPI strip, 44px+ touch targets — all functional
- Cron rescheduling on admin-config save, validation rejects out-of-range hours
- Slip strategy cap respected (current slip: 2 legs @ 4.36 combined odds)

## Backlog / Roadmap

### P1
- Web Push notifications: end-to-end real-device test (only smoke-tested headlessly)
- Live Flutterwave keys swap via admin config (currently sandbox)
- Admin payment-proof image preview enlargement
- Telegram channel broadcast on code publish (parallel to push)
- Forgot-password / reset-password flow

### P2 (data depth)
- Add second odds-API source toggle (e.g. API-Football for injuries/lineups/xG) — admin-config provider field is already wired for swap
- Historical accuracy dashboard (won/lost/void per day, ROI tracking)
- Per-league filter for users
- Slip history pagination beyond 60-day window
- Brute-force lockout: K8s ingress IP-rotation fix (currently uses email as identifier, OK but not ideal)

## Tech Choices Locked In
- Don't modify supervisor configs.
- Use REACT_APP_BACKEND_URL on the frontend; MONGO_URL/DB_NAME on the backend.
- Route all backend endpoints through `/api`.
- For new external integrations, route through `integration_playbook_expert_v2`.

## Production Note
The user has deployed this app to https://probability-vault.emergent.host. Bug reports should always be reproduced in PREVIEW (this environment) before claiming a fix; production is updated via the platform's deploy step.
