# QuantAgora

QuantAgora is a personal US-listed securities trading assistant for a Korean retail investor using the Korea Investment Securities Open API.

This repository started from an older research-oriented multi-agent trading project, but it is being refactored into a production-oriented product with deterministic risk controls, approval-gated execution, and operational tooling for real trading.

## Product Scope

- Broker: Korea Investment Securities Open API
- Assets: US-listed common stocks, ETFs, leveraged ETFs, inverse ETFs
- Trading style: swing to medium-term
- Account mode: cash only
- Session scope: US regular session only
- Approval model: human approval for new entries and rebalances, automatic risk exits allowed later
- UI language: English
- Operator: single personal user

## Current Implementation Status

Implemented so far:

- Phase 1: FastAPI + React scaffold
- Phase 2: PostgreSQL trading schema and Alembic setup
- Phase 3: KIS broker adapter
- Phase 4: market calendar and market data persistence
- Phase 5: universe engine
- Phase 6: signal engine
- Phase 7: LLM provider layer and report generation

Not implemented yet:

- Phase 8+: risk manager execution flow, Telegram approval gate, order planner, execution service, reconciliation, tax/reporting, deployment hardening

## Architecture

High-level flow:

```text
KIS Market Data
  -> Universe Engine
  -> Signal Engine
  -> Risk Manager
  -> Approval Gate
  -> Order Planner
  -> KIS Execution
  -> Reconciliation
  -> Portfolio / Tax / Reports
```

Current backend modules:

```text
backend/app/
  api/routes/         FastAPI routes
  brokers/            KIS adapter and broker interface
  core/               settings, logging, auth
  db/                 SQLAlchemy models and sessions
  domain/             Pydantic domain models
  services/
    market_calendar.py
    market_data.py
    universe.py
    indicators.py
    signal_engine.py
    llm_reports.py
    scheduler.py
    risk_policy.py
  llm/                provider abstraction, prompts, structured report validation
```

Current frontend:

```text
frontend/src/
  App.tsx
  api.ts
  types.ts
  styles.css
```

## Technology Stack

Backend:

- Python 3.11
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL
- HTTPX
- APScheduler

Frontend:

- React
- Vite
- TypeScript

Broker and infra:

- Korea Investment Securities Open API
- Docker Compose for local infrastructure

## Features Implemented

### 1. Broker Adapter

- KIS OAuth token handling
- hashkey support
- quote, candle, balance, position, buying power, order, cancel, fill interfaces
- paper/live mode routing
- normalized broker response models

### 2. Market Data

- US regular-session market calendar
- holiday and early-close handling
- quote snapshot persistence
- daily candle backfill
- daily refresh API
- stale quote detection

### 3. Universe Engine

- configured seed universe
- KIS market-data-backed candidate source
- optional agent candidate input
- eligibility filters:
  - US listing
  - OTC exclusion
  - broker support
  - supported asset type
  - price range
  - liquidity threshold
  - bid-ask spread threshold
  - leveraged/inverse ETF whitelist
- weekly universe versioning
- manual universe refresh API
- universe dashboard section in the frontend

### 4. Signal Engine

- structured signal schema
- technical indicators:
  - SMA
  - EMA
  - RSI
  - ROC
  - MACD
  - ATR
  - realized volatility
- signal families:
  - trend following
  - pullback in uptrend
- regime filter:
  - benchmark 200D moving average
  - realized volatility gate
- momentum confirmation
- same-symbol cooldown
- signal persistence to database
- daily scan scheduler hook
- signal list and detail panel in the frontend

### 5. LLM Provider Layer

- OpenAI provider
- OpenRouter-compatible provider
- strict JSON response validation with Pydantic schemas
- prompt templates for:
  - universe rationale
  - trade rationale
  - post-trade review
- `llm_reports` persistence
- fallback reports when provider credentials or responses fail
- hard guard that explanation output cannot override deterministic risk decisions
- frontend controls for generating universe and signal explanations

## API Endpoints Available

Current implemented endpoints:

```text
GET  /api/health
GET  /api/settings/runtime
GET  /api/portfolio/summary

GET  /api/market/status
GET  /api/market/quotes/{symbol}/latest
POST /api/market/quotes/{symbol}/snapshot
POST /api/market/candles/{symbol}/backfill
POST /api/market/refresh/daily

GET  /api/universe/current
POST /api/universe/refresh

GET  /api/signals
POST /api/signals/scan

GET  /api/llm/reports
POST /api/llm/reports/universe/current
POST /api/llm/reports/signals/{signal_id}
POST /api/llm/reports/post-trade-review

GET  /api/risk/status
GET  /api/approvals
POST /api/approvals/{approval_id}/approve
POST /api/approvals/{approval_id}/reject
```

Notes:

- approval endpoints are still placeholders
- risk status is still policy/status level, not full deterministic risk validation
- signal scan and universe refresh require a reachable PostgreSQL database with stored candle data

## Local Development

### 1. Backend environment

```bash
make backend-venv
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill at least:

```bash
DATABASE_URL=postgresql+psycopg://...
PROCESS_ROLE=api
ADMIN_API_TOKEN=...

KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_ACCOUNT_NO=...
KIS_ACCOUNT_PRODUCT_CODE=...
KIS_MODE=paper
```

Optional signal scheduler settings:

```bash
SIGNAL_SCHEDULER_ENABLED=false
PROCESS_ROLE=api
SIGNAL_SCAN_HOUR_UTC=21
SIGNAL_SCAN_MINUTE_UTC=15
```

Production note:

- Run API workers with `PROCESS_ROLE=api`.
- Run exactly one dedicated scheduler process with `PROCESS_ROLE=scheduler` and `SIGNAL_SCHEDULER_ENABLED=true`.
- Use `PROCESS_ROLE=all_in_one` only for single-process local runs.

Optional LLM settings:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
LLM_MODEL=gpt-5-mini
LLM_BASE_URL=
LLM_TIMEOUT_SECONDS=20
OPENROUTER_SITE_URL=
OPENROUTER_APP_NAME=QuantAgora
```

### 3. Run database migrations

```bash
make db-upgrade
```

### 4. Start backend

```bash
make backend-dev
```

Backend default URL:

```text
http://localhost:8000
```

### 5. Start frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend default URL:

```text
http://localhost:5173
```

### 6. Run checks

```bash
make check
```

## Configuration Highlights

Universe-related:

- `UNIVERSE_SEED_SYMBOLS`
- `UNIVERSE_MAX_MEMBERS`
- `UNIVERSE_MIN_PRICE_USD`
- `UNIVERSE_MAX_PRICE_USD`
- `UNIVERSE_MIN_AVG_DOLLAR_VOLUME_USD`
- `UNIVERSE_MAX_BID_ASK_SPREAD_BPS`
- `UNIVERSE_LIQUIDITY_LOOKBACK_DAYS`
- `UNIVERSE_LEVERAGED_INVERSE_WHITELIST`

Signal-related:

- `SIGNAL_LOOKBACK_DAYS`
- `SIGNAL_MIN_HISTORY_DAYS`
- `SIGNAL_EXPIRY_DAYS`
- `SIGNAL_PULLBACK_LOOKBACK_DAYS`
- `SIGNAL_SCHEDULER_ENABLED`
- `SIGNAL_SCAN_HOUR_UTC`
- `SIGNAL_SCAN_MINUTE_UTC`
- `SIGNAL_VOLATILITY_MAX_ANNUALIZED`
- `SIGNAL_LEVERAGED_VOLATILITY_MAX_ANNUALIZED`

LLM-related:

- `LLM_PROVIDER`
- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `LLM_MODEL`
- `LLM_BASE_URL`
- `LLM_TIMEOUT_SECONDS`
- `OPENROUTER_SITE_URL`
- `OPENROUTER_APP_NAME`

Market-calendar-related:

- `MARKET_EXTRA_CLOSED_DATES`
- `MARKET_EXTRA_EARLY_CLOSE_DATES`
- `MARKET_QUOTE_STALE_SECONDS`

## Product Documents

- [PRD](docs/PRD-us-auto-trading.md)
- [TRD](docs/TRD-us-auto-trading.md)
- [Tasks](docs/TASKS-us-auto-trading.md)

## Safety and Current Limitations

- This is not ready for unattended live trading.
- Telegram approval gate is not implemented yet.
- Full deterministic risk checks before order creation are not implemented yet.
- Order planning and execution orchestration are not implemented yet.
- Tax ledger and reconciliation are not implemented yet.
- LLM output is explanation-only and cannot change risk decisions, signal action, or position sizing.
- Signal logic is MVP-level and should be treated as an initial framework, not a validated production strategy.
- Calendar logic is rule-based with override settings, not yet sourced from a live exchange calendar feed.
- KIS live end-to-end behavior has not yet been fully smoke-tested against a real account in this repository flow.

## Repository Context

Some legacy research/demo files from the original QuantAgent codebase are still present in the repository root. They are not the current product path.

The current product implementation is centered on:

- `backend/`
- `frontend/`
- `docs/`

## License

Review the repository license and any upstream license obligations from the original project before external distribution.
