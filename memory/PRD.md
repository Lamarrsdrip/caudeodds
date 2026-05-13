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

### Phase 12 — Teaser protection + WIN/LOSS labels + admin button split (2026-05-11)

- **Teaser cannot leak picks**: `/api/slip/today` for unauthenticated users now NULLs out `odds`, `combined_odds`, `confidence`, `edge_pct`, `expected_value`, `sportybet_code` and replaces with `odds_range` (0.5-wide band like "1.5–2.0") + `combined_odds_range` (e.g. "2.0–3.0") + `confidence_band` ("ELITE"/"HIGH"/"MEDIUM"/"LOW"). Team names already replaced with "🔒 Locked". Cannot be reverse-engineered.
- **DailySlip + admin UI** updated to handle the null/range values gracefully (shows 🔒 or the range string when locked).
- **WIN/LOSS/VOID result labels**: `/api/schedule/upcoming` now joins fixture rows with their settled pick status. `UpcomingFixtures.jsx` renders **WIN ✅ / LOSS ❌ / VOID ⚪** badges next to finished matches. Auto-settlement service already writes `status='won'|'lost'|'void'` after the match grades.
- **Admin button split**:
  - **Run Daily Ensemble** (primary green, default flow) — runs AI on today's existing fixture pool. Append-only; never wipes anything.
  - **Force Re-Generate (debug)** — now requires a confirmation modal warning "DEBUG ACTION: burns LLM credits". Append-only after Phase 11 so safe to use, just expensive.
  - **Pre-Gen Tomorrow** — unchanged.
  - **Heal Bad Data** — unchanged.
- **3 new pytest cases** in `tests/test_phase12_teaser_protection.py`. Full regression: **60 passed / 1 expected skip**.



User requirement: "NEVER delete old predictions when generating new ones. Force Generate should ONLY append/add."

- **Force Generate is now strictly APPEND-ONLY**: `slip_generate` upserts picks by natural key `(date + match + kickoff)`. Existing picks are preserved (id + status retained for settlement continuity). New job stats expose `inserted_new` + `refreshed_existing`. The destructive `picks_col.delete_many({"date": date_str})` call is gone forever.
- **3-hour kickoff deadline enforcer** in `self_heal_bad_data`: any schedule entry within 3h of kickoff that's still `pending`/`analyzing` is finalized — if odds never arrived → `ai_status='no_prediction'` with `no_prediction_reason='odds_never_published'`. If odds are there → reset to pending for immediate retry.
- **Stuck-analyzing recovery**: schedule entries in `ai_status='analyzing'` for >15 min (process crash mid-flight) are reset to `pending` so the next cron tick retries.
- **Lifecycle badges** in `/api/schedule/upcoming`: added `live` (kicked off, <3h ago), `completed` (>3h since kickoff), `no_prediction`. Total 8 distinct badges, each with its own colour-coded UI chip.
- **Frontend grouping**: `UpcomingFixtures.jsx` now visually separates fixtures into Upcoming / Predictions / No Prediction / Live Now / Finished sections so users never see mixed states.
- **6 new pytest cases** in `tests/test_phase11_lifecycle.py` verifying append-only contract, stuck recovery, deadline finalization, summary keys. Full regression: **57 passed / 1 expected skip**.



User reported the Emergent Universal Key credits draining heavily. Each fixture
previously burned **3 LLM calls** (Claude research + GPT-4o-mini quant + Claude
reasoning) on every cron tick.

Optimisations shipped:
- **24h LLM ensemble result cache** (`db.llm_ensemble_cache`) keyed by `(fixture.id + odds_signature_hash)`. Same fixture won't re-burn credits within 24 hours; cache invalidates automatically when odds shift ≥ 0.1 on any leg. Env-tunable via `ENSEMBLE_CACHE_TTL`.
- **Skip the (most expensive) tactical Reasoning agent when research_quality_score < 50** — saves 1 of 3 calls on every thin-signal fixture. The quant call alone is sufficient since consensus will reject these anyway.
- **Pre-LLM odds-range drop in `filters.py`**: any fixture whose best 1X2 price exceeds 4.5 is rejected BEFORE the LLM is invoked — these can't possibly produce a 2.0-5.0 slip leg, so analyzing them wastes credits.
- **Admin Usage dashboard** now exposes `llm_ensemble_cache_entries` so you can see how many fixtures are being served from cache (every hit = $0).

**Expected savings**: on a typical day with 15 fixtures analyzed across 4 cron ticks, this drops from `15 × 4 × 3 = 180` LLM calls/day to `15 × 1 × 2.5 ≈ 37` LLM calls/day — **~80% reduction** in LLM credit burn.

**Honest verdict on "does higher API spend improve win rate?": NO.** Past ~3-5% data_richness, you're paying for noise. The Odds API closing line is near-efficient; what moves win rate is **discipline** (rejecting weak edges, sticking to safer markets), not more LLM calls. So Phase 10 prioritizes cost reduction + selective discipline.

**Cost optimizations**:
- **Hard MongoDB cache on `fetch_odds`** — was previously cache-less (the free 500/mo quota would burn in ~2 hours). Now: 60-min TTL off-peak, 15-min near kickoffs, env-tunable via `ODDS_TTL_OFFPEAK` / `ODDS_TTL_PEAK`.
- **Fixture-sync cron 15 min → 30 min** — schedule changes slowly; halving the poll halves the worst-case API burn.
- **Frontend `UpcomingFixtures` poll 60 s → 120 s + visibility-aware** — tabs left open in background no longer hit the API.
- **Live Odds API quota tracking** — every `fetch_odds` response writes `x-requests-remaining` to `db.odds_api_usage` for the admin dashboard.

**New admin dashboards**:
- `GET /api/admin/usage` — surfaces Odds-API remaining, cache entries, picks-per-7-days, fixture-sync runs/24h, and budget advice.
- `GET /api/admin/apibasketball/diagnostic` — hits `/status`, `/timezone`, `/seasons`, `/leagues`, `/teams?season=current`, `/games` with your stored key and returns the LITERAL provider response (status, errors, rate-limit headers, results count, sample row) so you can see EXACTLY what's blocked.
- New `/admin/usage` page with KPI strip + budget-advice card + "Run Diagnostic" button rendering raw endpoint results.

**Match analysis engine improvements**:
- **Home-advantage bias guard** (`consensus.py`): AWAY picks against clear home favorites (home @ ≤ 1.70) are rejected outright when data_richness < 0.6. Counter-bias 1pp EV penalty on AWAY picks across the board (since LLMs over-rate visiting form historically).
- **Adverse line-move trap detection** (`consensus.py`): if the line drifted >15% against our pick in the last hour AND data_richness < 0.7, reject as sharp-money trap.
- **Always-1-pick fallback** preserved via `slip_builder._select_picks` last-resort branch.

**Bug fixes (Phase 10D)**:
- `consensus.py`: `richness` was referenced before definition in my home-bias block (lint F821). Fixed by hoisting to `richness_early` at function top.
- `odds_api_service.py`: `time` module not imported (lint F821 on `time.time()` cache stamps). Added.
- `odds_api_service.py`: dead `next_day` variable removed (was leftover from old date-window code).
- 7 new pytest cases in `tests/test_phase10_cost_audit.py`. Full regression: **52 passed / 1 expected skip**.


- **Root-cause fix for "today's picks vanished" + "tomorrow's match showing under today"**: every fixture-sync cycle (and every admin Force Re-Generate) now runs `self_heal_bad_data()` first which:
  - **A) Drops mistagged picks**: any row in `claudeodd_picks` whose `kickoff` UTC-date doesn't match `pick.date` is deleted. Auto-removes legacy Celta-Vigo-on-today rows.
  - **B) Resets orphan schedule entries**: any `claudeodd_schedule` row with `ai_status='ready'` and a `pick_id` that no longer exists in `claudeodd_picks` (e.g. wiped by old destructive Force Re-Gen) gets reset to `ai_status='pending'` and `pick_id=null` so the next AI run rebuilds the missing pick.
- New admin endpoint `POST /api/admin/schedule/heal` exposes this on demand. New **"Heal Bad Data"** button on `/admin/predictions` (orange chip) — one click cleans + re-syncs + re-AIs. Toast reports "Healed · dropped N mistagged picks, reset M orphan schedule entries".
- Force Re-Generate now also calls self-heal before the pipeline so a single click fixes BOTH the underlying bad data AND regenerates the slip.
- 4 new pytest cases in `tests/test_phase9_self_heal.py`. Full regression: **45 passed / 1 expected skip**.

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

### Phase 13 — Teaser fix + Anti-trial-abuse + Referral program (2026-05-13)
- **Teaser fix (P0)**: locked `/api/slip/today` now hides the bet (match, league, market, selection_label) but exposes the real `odds` per leg and `combined_odds`, exactly as the user requested ("blur the bet and leave the odds"). Frontend renders the selection with a `blur-sm` mask + 🔒 prompt. SportyBet code remains hidden.
- **Device fingerprint**: new users send a FingerprintJS visitor ID (`device_fingerprint`) with registration. Duplicate fingerprints → `409 Conflict` to stop users from making fresh accounts after their trial expires. Stored on `users.device_fingerprint` with a sparse index.
- **Referral program** (new module `backend/referrals.py`):
  - Every user gets a unique `referral_code` (8-char base32) at registration; legacy users get one auto-backfilled on first call to `/api/referral/me`.
  - Registering with a valid `referral_code` → referee gets **5-day trial** instead of the default 3; referrer gets **+1 day** added to their active subscription/trial, plus `referrals_count` incremented.
  - New endpoints: `GET /api/referral/me` (code, share link, count, list of referees, reward rules) and `GET /api/referral/validate?code=...` (public live validation for the register form).
  - Frontend: Register page accepts `?ref=CODE` URL prefill, live-validates with green/red indicators, shows "5 days free unlocked thanks to <name>" bonus banner. New `ReferralCard` on the Dashboard shows code, share link (one-tap copy), referral count, and the list of referred users with their signup dates.
- Tests: `backend/tests/test_phase13_referrals.py` (5 tests) and updated `test_phase12_teaser_protection.py` (3 tests) — all green.

### Phase 14 — Custom referral codes + expired-user history preview (2026-05-13)
- **Custom referral code/word**: new `PUT /api/referral/code` lets users set a vanity code (4–20 chars, A–Z + 0–9, must contain a letter, reserved words like `ADMIN/CLAUDEODDS/FREE/VIP` blocked, uniqueness enforced). Frontend ReferralCard now has a ✏️ pencil edit button → inline input with live normalization, Save/Cancel, and helper text describing the rules.
- **Expired-user history preview**: `/api/slip/history` no longer returns `402` for expired users. Instead it returns the **same per-leg payload as the teaser** — match/league/market/selection redacted, but **per-leg odds and WIN/LOSS status visible**, plus combined odds and the won/lost summary. The dashboard History tab now shows a "Subscription Inactive" banner with a "Subscribe to see the picks →" CTA and renders each leg with a blurred pick + the leg's real odds + a green `✓ WON` / red `✗ LOST` pill. Active subscribers still see the full unredacted history exactly as before.
- Tests: `backend/tests/test_phase14_custom_code_and_history.py` (9 tests) — all green. Full referral + teaser + history regression now stands at **17 passing**.

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
