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

### Phase 5 — PWA auto-update + Public ROI + Next-day rollover (2026-05-10)
- **PWA auto-update** — `sw.js` now stamps `BUILD_VERSION`, handles `SKIP_WAITING` messages, broadcasts `SW_ACTIVATED` and clears stale Cache Storage on activate. New `PwaUpdater.jsx` component polls for updates every 60s, listens for `controllerchange`, and shows a "New version installed — refreshing…" toast that auto-reloads in 1.5s. Reload only fires when an existing controller is replaced (real update), not on first install — preventing reload loops.
- **Public ROI Tracker** — new public endpoint `GET /api/public/roi?days=30` (no auth) aggregates settled slips into totals (slips_settled, won, lost, void, pending, profit_units, roi_pct, win_rate_pct) plus per-day outcome history. Rendered on `/` via `PublicRoiTracker.jsx` with KPI strip + 14-row history list — honest, transparent track-record for free-to-paid conversion.
- **Next-day rollover** — refactored `GET /api/slip/today` with `_build_slip_for_date` helper + `_should_rollover` triggers (all settled OR ≥22:00 UTC OR latest kickoff +3h past + settled). When today is done, returns `is_tomorrow:true` with tomorrow's slip, or `awaiting_tomorrow:true` if not yet generated. Dashboard renders dedicated cards ("TOMORROW'S COMBINED SLIP" + Next-day rollover badge OR awaiting card).
- **Tomorrow pre-gen cron** — scheduler.py adds `_run_tomorrow_pregen` job running daily at 22:00 UTC so tomorrow's slip is ready the moment today's slate ends.
- **Admin Pre-Gen Tomorrow** button on `/admin/predictions` → `POST /api/slip/generate?date=tomorrow`. Endpoint also accepts explicit `YYYY-MM-DD` dates with proper 400 on invalid input.

### Phase 8 — Non-destructive Force Re-Generate + fixture-sync enrichment + strict date scope (2026-05-11)
- **CRITICAL UX FIX — Force Re-Generate no longer wipes a working slip**: `slip_generate(force=true)` previously called `picks_col.delete_many` BEFORE knowing whether the new run produced picks. Now only deletes when `new picks >= 1`. Sets `job.kept_old=true` and toasts "Re-run produced 0 picks — KEPT existing slip intact".
- **CRITICAL DATA FIX — fixture-sync picks now ship with real data_richness**: `fixture_sync_service.run_ai_for_new_odds` rebuilt Fixture from cached odds without enrichment → `data_richness=0.0` → slip-quality gate (≥40%) suppressed valid picks. Now calls `_enrich_one(db, fx)` (parallel, capped at 6) before `run_ensemble`.
- **CRITICAL DATE-SCOPE FIX**: `odds_api_service.fetch_real_fixtures_for_today` was including fixtures whose UTC date was between `target_day` and `target_day + 2 days` ("today or tomorrow window"). This caused Force Re-Generate for today to pull tomorrow's matches and pick e.g. "Celta Vigo vs Levante" (tomorrow's match) as a "today" pick. Now strictly `ct.date() != target_day → skip`. Today's pipeline only analyzes today's matches; tomorrow's matches are handled by the separate `tomorrow_pregen` cron and `date=tomorrow` admin button.
- **Defensive `build_slip` guard**: even if legacy DB rows have a kickoff date that doesn't match `slip.date`, new helper `_filter_picks_to_date()` drops them before slip construction. Self-heals production data without manual cleanup.

### Phase 7A — Admin hardening + persistence + email plumbing (2026-05-11)
- **CRITICAL FIX — admin password persistence**: `seed_admin` in `auth.py` previously re-wrote the admin's password to `ADMIN_PASSWORD` env var on every restart whenever the hash didn't match. Now it only seeds on first run; existing admin passwords are NEVER overwritten. Emergency recovery via `ADMIN_FORCE_PASSWORD_RESET=1` env var. Verified end-to-end: change password → restart backend → new password works, old password rejected.
- **Password change** endpoint `POST /api/auth/password/change` + **force-logout**: JWT now carries `password_version` claim; `get_current_user` rejects tokens whose `pwv` is older than the user's current version. Password change bumps version, instantly invalidating every other open session. Rotated token returned to caller so the originating tab stays signed in.
- **SMTP service** (`email_service.py`): smtplib + ssl based, no extra deps. Classifies errors into `MISSING_CONFIG / WRONG_PASSWORD / INVALID_APP_PASSWORD / SMTP_BLOCKED / TLS_ERROR / TIMEOUT / HOST_NOT_FOUND / BAD_RECIPIENT / BAD_SENDER / UNKNOWN` for actionable admin UX.
- **`POST /api/admin/smtp/test`** verifies credentials without sending. **`POST /api/admin/smtp/send-test`** delivers a real test email and persists to `db.email_logs`.
- **Welcome email** fire-and-forget on `POST /api/auth/register` — never blocks registration even if SMTP is down/missing, always logged to `db.email_logs`.
- **Password-changed confirmation email** sent on successful `/auth/password/change`.
- **Login activity log** (`db.login_activity`): every login attempt (success + failure) recorded with `email, ip, ua, success, reason, ts`. Endpoints `GET /api/admin/activity` (all users) and `GET /api/auth/activity` (self).
- **Admin Security Center** at `/admin/security`: Change Password card, SMTP test/send card with Connected ✅ / Failed ❌ status + clear error chip, Email Delivery Log table, Login Activity table.

### Phase 7B — Email Center + advanced security (Backlog, not yet built)
- Bulk Email Center: send to all users / filtered selection / saved templates (welcome, announcement, maintenance, promotion)
- Login notification email on every successful login (rate-limited to 1/hour)
- Suspicious-login detection (new IP/country/UA → email user)
- Forgot/reset password flow (token via email)
- Rate limiting on /auth/register (per IP)
- CSP / Content-Security-Policy + helmet-equivalent headers
- AES-encrypted SMTP password storage in admin_config (currently plaintext, only admin can read)

### Phase 6 — Fixture-first pipeline / "Never Empty" dashboard (2026-05-10)
- **Problem**: dashboard appeared "broken" when bookmakers hadn't posted tomorrow's odds yet (typically before 18:00 UTC), even though scheduled matches existed.
- **Solution**: separated MATCH SCHEDULE (always available days ahead from API-Football/API-Basketball) from BETTING ODDS (drip-fed by bookmakers throughout the day).
- New service `fixture_sync_service.py` runs every 15 min and stages: **schedule sync → odds enrichment → AI analysis**. New collection `claudeodd_schedule` holds fixtures with `odds_status` (`waiting`/`available`) and `ai_status` (`pending`/`analyzing`/`ready`/`rejected`/`failed`).
- **New endpoint** `GET /api/schedule/upcoming?days=3` (public) returns the schedule with status badges + per-day summary counts. `POST /api/admin/schedule/sync` triggers the cycle on demand (admin only).
- **New frontend component** `UpcomingFixtures.jsx` on Dashboard: date tabs (Today/Tomorrow/+1), summary chips, fixture rows with colour-coded badges (yellow=WAITING FOR ODDS / blue+spin=ANALYZING / green=READY / gray=NO BET / orange=RETRYING). Auto-polls every 60s so users watch fixtures flip from waiting → ready the moment bookmakers price them. Result: dashboard is **never empty when matches actually exist**.
- Verified: 14 real fixtures fetched across 3 days from API-Football in preview (Napoli vs Bologna, Tottenham vs Leeds, etc.).

## Validated
- 100% pass on iter_3 / iter_4 / iter_5 / **iter_6** testing-agent runs (32 backend pytest passing + 3 expected skips; comprehensive frontend audit desktop+mobile 390x844, 0 console errors across /, /dashboard, /admin/predictions, /pricing, /subscription)
- iter_6: Phase-5 features (PWA auto-update / Public ROI / Next-day rollover) all verified end-to-end via public URL
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
