# CLAUDEODD — Product Requirements Document

## Original Problem Statement
Build a realistic long-term profitable AI sports betting intelligence system using BOTH Claude API and GPT API as a multi-agent ensemble. Goal: maximum probability edge, disciplined filtering, sustainable profitability, high-confidence daily slips (2–5/day), low-risk decision-making, consistent long-term ROI. NOT fake 90% win rates.

## User Choices
- Platform name: **CLAUDEODD**
- Budget: ≤ $10/month total
- Stack: React + FastAPI + MongoDB (deployable on this platform)
- AI Models: Claude Haiku 4.5 + GPT-4o-mini (via Emergent Universal LLM Key)
- Data: Deterministic mock fixture/odds engine (designed to plug The Odds API in later)
- Auth: None (single-user dashboard)

## Architecture
```
Frontend (React + shadcn + recharts)
  ↳ Bloomberg-terminal dark UI · Chivo / IBM Plex / JetBrains Mono
  ↳ Tabs: Today's Picks | History | Analytics | Rejected | Settings

Backend (FastAPI + MongoDB + emergentintegrations)
  ↳ data_engine.py     — deterministic fixture/odds simulator
  ↳ filters.py         — NO BAD BETS pre-filter (6 checks)
  ↳ llm_engines.py     — Claude + GPT in parallel via asyncio.gather
  ↳ consensus.py       — side-direction agreement + EV/conf gates
  ↳ staking.py         — fractional Kelly + risk classifier
  ↳ pipeline.py        — daily orchestration, idempotent per UTC date
  ↳ server.py          — REST API
```

## Core Endpoints
- `POST /api/picks/generate?force=bool` — runs ensemble (cached per day)
- `GET  /api/picks/today` — today's approved picks
- `GET  /api/picks/history` — historical picks (filters: sport, status)
- `POST /api/picks/{id}/settle` — mark won/lost/void
- `GET  /api/picks/parlay` — combined daily slip
- `GET  /api/analytics/roi` — bankroll curve + KPIs
- `GET  /api/analytics/rejected` — filter rejection log
- `GET  /api/analytics/sharp` — line movement & sharp money signals
- `GET/POST /api/config` — Settings (bankroll, kelly, thresholds)

## What's Been Implemented (2026-02-10)
✅ Multi-agent ensemble: Claude Haiku 4.5 + GPT-4o-mini analyze each fixture in parallel  
✅ Side-direction consensus check (HOME/AWAY/OVER/UNDER/BTTS-Y/BTTS-N)  
✅ "NO BAD BETS" ultra-filter: liquidity, volatility, line trap, injury chaos, sharp/public conflict, public extremes  
✅ EV gate, confidence gate, agreement gate, narrative-risk gate, trap-flag gate  
✅ Fractional Kelly stake (default 0.25) with confidence weighting and 5% bankroll cap  
✅ Daily idempotent pipeline (cached per UTC date)  
✅ Bloomberg-terminal dashboard: marquee, picks board, parlay accumulator, history, analytics, rejected log, settings  
✅ Recharts bankroll curve with signal-green area  
✅ Settle workflow (won / lost / void) updating ROI  
✅ 16/16 backend pytest passing · all critical frontend flows verified  

## Cost Profile (under user's $10/mo budget)
- 1 generation/day × ~12 LLM calls × ~$0.001 = ~**$0.40/month** projected  
- User can run more aggressively (force) without breaking budget

## Discipline Defaults
- min_confidence = 70%
- min_agreement = 65%
- min_ev = 0.03 (3%)
- max_picks_per_day = 5
- kelly_fraction = 0.25 (quarter Kelly)
- bankroll_cap_per_bet = 5%

## Backlog (Future Phases)

### P0 (next priorities)
- [ ] Plug **The Odds API** as live data source (replace mock data_engine; keep schema)
- [ ] Self-learning weekly retrain: track which rejection codes are over/under-firing and adjust thresholds automatically
- [ ] WebSocket live odds updates

### P1
- [ ] Auto-settle picks via real result feed (TheSportsDB / API-Football)
- [ ] Bookmaker API integration for placing bets
- [ ] Push/email alerts for new picks
- [ ] Multi-bankroll segmentation (separate sports / risk tiers)

### P2
- [ ] Allow undo settle (reset to pending)
- [ ] Settled pick cards show all 3 settle buttons with active highlight
- [ ] Per-day generation rate limiter (cost protection)
- [ ] User auth (JWT + multi-account)
- [ ] Portfolio export (CSV / JSON)

## Known Minor Issues
- None blocking. All testing-agent issues fixed in iteration 1.
