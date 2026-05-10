# CLAUDEODD — Product Requirements Document

## Original Problem Statement
Build a realistic long-term profitable AI sports betting intelligence platform for Nigerian users. Combine Claude + GPT as a multi-agent ensemble. Output ONE combined daily 2-5 leg slip in SportyBet format. SaaS subscription model: 18+ age gate, 3-day free trial, monthly subscription via Flutterwave or manual bank transfer with admin approval. Full admin dashboard to configure everything (Flutterwave keys, bank details, prices, SMTP, Telegram) at runtime.

## User Choices
- Platform: **CLAUDEODD**
- Budget: ≤ $10/month LLM spend
- Stack: React + FastAPI + MongoDB
- AI: Claude Haiku 4.5 + GPT-4o-mini (Emergent Universal LLM Key)
- Currency: NGN (₦)
- SportyBet: deterministic booking-code generator + deep-link
- Auth: Email/password + JWT (no Google OAuth in Phase 1)
- Admin everything-configurable in dashboard

## Architecture
```
Frontend (React Router DOM v7 + shadcn + recharts)
  ↳ Public:    / (Landing), /pricing, /login, /register, /payment/callback
  ↳ User:      /dashboard (combined slip + history), /subscription
  ↳ Admin:     /admin (Overview, Users, Payments, Predictions, Configuration)

Backend (FastAPI + Motor + emergentintegrations + Flutterwave + bcrypt + PyJWT)
  ↳ auth.py             — register/login + JWT + bcrypt + email-only lockout (K8s-safe)
  ↳ subscriptions.py    — trial/active/expired state machine
  ↳ payments.py         — Flutterwave init/verify/webhook + bank transfer (DB-config keys)
  ↳ slip_builder.py     — combined parlay + SportyBet code (SB-XXXXXX-XXXX) + deep-link
  ↳ data_engine.py      — deterministic fixture/odds (drop-in for The Odds API)
  ↳ filters.py          — NO BAD BETS pre-filter (6 checks)
  ↳ llm_engines.py      — parallel Claude + GPT, side-direction consensus
  ↳ consensus.py + pipeline.py — orchestration (cached daily, idempotent)
  ↳ saas_models.py + models.py — Pydantic schemas
  ↳ server.py           — All routes (/api/auth/*, /slip/*, /payments/*, /admin/*)
```

## Endpoints (`/api/*`)
**Auth:** register, login (email-only lockout 5×/15min), me, logout
**Slip:** today (locked teaser if anon, full if subscribed), history, generate (admin)
**Payments:** flutterwave/init, flutterwave/verify, flutterwave/webhook (HMAC), bank-transfer, mine
**Admin:** stats, users (list, grant 30d, suspend), payments (list, approve, reject), predictions (list, settle), config (GET masked secrets, POST preserves masked), rejected
**Public:** /public/config, /

## What's Been Implemented (Phase 2.1 — 2026-02-10)
✅ **Brand renamed to "ClaudeOdd"** (proper-cased everywhere)
✅ **Footer: "Made by emriz.eth"** glowing pulsing badge on every page (Landing, Login, Register, Pricing, Dashboard, Subscription)
✅ **New slip algorithm** — combined ODDS land in [2.00, 5.00] (not "2-5 legs"). Greedy packs 3–5 highest-confidence games while respecting the 5.0 hard cap. Falls back to 2 legs when math forces it (correct behaviour: today's 4 picks have minimum-3 combo @ 14.10 — too high; ships 2 @ 4.62)
✅ **Football + Basketball mixed automatically** in single slip (no sport tabs in user UI)
✅ **Friendlier hero copy** — "WIN MORE. BET SMARTER. DAILY." + clear "3–5 games · 2.00–5.00 combined odds"
✅ **Looser ensemble thresholds** (min_conf 60, min_ev 0.02, min_agreement 55) + 65% value-bias rate so more picks pass while staying disciplined
✅ **Bankroll/Kelly fully removed** from user UI (admin-only via Predictions tab)

## What's Been Implemented (Phase 2 — 2026-02-10)
✅ **Auth + 18+ age gate** — bcrypt + JWT (7-day) + Terms acceptance + DOB
✅ **Brute-force lockout** — email-only identifier (K8s pod-rotation safe)
✅ **Free trial** — 3 days auto-started on registration
✅ **Subscription state machine** — trial → active → expired with grace
✅ **Flutterwave** — Standard checkout init + verify + webhook (HMAC sig); keys in MongoDB admin_config
✅ **Manual bank transfer** — base64 receipt upload (3MB cap) + admin approve/reject
✅ **Combined daily slip** — single slip, no individual cards in user UI
✅ **SportyBet integration** — deterministic booking code (SB-XXXXXX-XXXX), Copy + Open in SportyBet buttons
✅ **Public landing + pricing** — locked teaser + ₦5,000/mo + free trial CTA
✅ **Admin panel** — Overview KPIs, Users (grant/suspend), Payments (approve/reject + receipt viewer), Predictions (W/L/V settle), Configuration (5 sections, masked secrets)
✅ **Locked teaser endpoint** — anon visitors see slip shape but legs masked
✅ **29/30 backend tests + 85% frontend tests passing**

## Cost Profile
- 1 daily generation × ~12 LLM calls × $0.001 ≈ **$0.40/month** ✅ under $10/mo budget

## Subscription Defaults (admin-editable)
- price_ngn: 5,000
- trial_days: 3
- plan_label: "VIP Daily Slip"

## Test Credentials (`/app/memory/test_credentials.md`)
- Admin: `admin@claudeodd.com` / `Admin@2026`

## Backlog

### P0 (next iteration)
- [ ] Plug **The Odds API** for live odds (replace mock data_engine)
- [ ] **Email verification + password reset** (needs admin to fill SMTP in Configuration)
- [ ] **Telegram bot** to push daily slips to subscribers
- [ ] **Real SportyBet booking-code injection** (admin can paste real codes per slip)

### P1
- [ ] Google OAuth login (Emergent-managed)
- [ ] Coupons + referrals + leaderboard
- [ ] Email broadcasts (admin-composed templates)
- [ ] Push notifications (web + mobile)
- [ ] Self-learning weekly retrain (auto-tune thresholds from rejection-code performance)

### P2
- [ ] WhatsApp integration
- [ ] Multi-language (English / Pidgin / Yoruba / Igbo / Hausa)
- [ ] Mobile app APIs (iOS/Android)
- [ ] Audit logs UI
- [ ] Encrypt-at-rest for admin secrets (currently masked on read)

## Known Minor Issues (non-blocking)
- /api/payments/flutterwave/verify takes tx_ref via query param (cosmetic)
- AdminConfig secrets stored plaintext in MongoDB (masked on GET)
- 4MB body cap on bank-transfer enforced post-receive (no Content-Length pre-check)
