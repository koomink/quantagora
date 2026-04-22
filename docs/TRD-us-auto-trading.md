# TRD: Technical Design for US-Listed Securities Auto-Trading Product

## 1. Architecture Overview

The system is a personal trading assistant for one Korean retail investor trading US-listed securities through Korea Investment Securities Open API. It uses scheduled signal generation, deterministic risk management, Telegram approval, broker execution, reconciliation, and tax ledger generation.

High-level flow:

```text
KIS Market Data
  -> Universe Engine
  -> Signal Engine
  -> LLM Research Agent
  -> Risk Manager
  -> Order Planner
  -> Telegram Approval Gate
  -> KIS Execution
  -> Reconciliation
  -> Portfolio / Tax Ledger / Reports
```

Risk exits bypass approval but must still be recorded and notified.

## 2. Recommended Stack

### Backend

- Python 3.11+
- FastAPI
- Pydantic
- SQLAlchemy or SQLModel
- PostgreSQL
- APScheduler for MVP scheduled jobs
- Redis optional for later async queues
- HTTPX for async API calls
- Uvicorn/Gunicorn

### Frontend

- React
- Vite
- TypeScript
- TanStack Query
- Zustand or lightweight state store
- Recharts or similar for dashboards

### Messaging

- Telegram Bot API
- Webhook mode preferred in production
- Polling acceptable in early local development

### Deployment

- Docker Compose
- Vultr Seoul VPS
- Nginx/Caddy reverse proxy
- TLS via Let's Encrypt
- Environment variables for secrets
- Daily database backup

## 3. Service Modules

### 3.1 Broker Adapter

Path proposal:

```text
backend/app/brokers/
  base.py
  kis.py
```

Interface:

```python
class BrokerAdapter:
    async def get_quote(self, symbol: str) -> Quote: ...
    async def get_candles(self, symbol: str, timeframe: str, start, end) -> list[Candle]: ...
    async def get_account(self) -> AccountSnapshot: ...
    async def get_positions(self) -> list[Position]: ...
    async def get_cash(self) -> CashSnapshot: ...
    async def place_order(self, order: PlannedOrder) -> BrokerOrder: ...
    async def cancel_order(self, broker_order_id: str) -> None: ...
    async def get_order(self, broker_order_id: str) -> BrokerOrder: ...
    async def get_fills(self, since) -> list[Fill]: ...
```

KIS adapter responsibilities:

- OAuth token issuance and refresh
- Hashkey generation where required
- Overseas stock quote endpoints
- Overseas stock order endpoints
- Overseas stock balance and fill endpoints
- API rate-limit handling
- Error normalization

### 3.2 Market Data Service

Responsibilities:

- Fetch and persist quotes/candles
- Mark data freshness
- Provide data to universe and signal engines
- Prevent trading on stale data
- Normalize timestamps to UTC
- Preserve exchange timezone metadata

### 3.3 Universe Engine

Responsibilities:

- Build candidate universe weekly
- Incorporate agent recommendations
- Apply eligibility filters
- Rank final candidates
- Persist active universe versions

Eligibility filter fields:

- `is_us_listed`
- `asset_type`
- `is_otc`
- `avg_dollar_volume`
- `bid_ask_spread_bps`
- `last_price`
- `corporate_action_flag`
- `supported_by_broker`
- `leveraged_inverse_flag`

Initial whitelist for leveraged/inverse ETFs:

```text
TQQQ, SQQQ, SOXL, SOXS, UPRO, SPXU
```

### 3.4 Signal Engine

Responsibilities:

- Generate swing/medium-term signals
- Avoid noisy intraday approval spam
- Produce structured signal candidates

Initial signal families:

- Trend following
- Pullback in uptrend
- Risk-on/risk-off regime
- Volatility filter
- Moving average regime
- Momentum confirmation

Output schema:

```json
{
  "symbol": "QQQ",
  "action": "BUY",
  "horizon": "swing",
  "confidence": 0.72,
  "target_weight": 0.12,
  "invalidation": "Close below 20D moving average",
  "rationale": "Trend and momentum aligned",
  "generated_at": "2026-04-22T00:00:00Z"
}
```

### 3.5 LLM Gateway

Provider abstraction:

```text
backend/app/llm/
  base.py
  openai_provider.py
  openrouter_provider.py
```

Configuration:

```yaml
llm:
  provider: openai
  model: gpt-5-mini
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
```

OpenRouter-compatible configuration:

```yaml
llm:
  provider: openrouter
  model: anthropic/claude-sonnet-4.5
  base_url: https://openrouter.ai/api/v1
  api_key_env: OPENROUTER_API_KEY
```

Responsibilities:

- Structured JSON outputs
- Explanation generation
- Universe recommendation summaries
- Trade rationale summaries
- Post-trade reviews

Restrictions:

- Cannot submit orders
- Cannot override risk manager
- Cannot mark a rejected risk check as approved
- Must include uncertainty where relevant

### 3.6 Risk Manager

Risk manager must be deterministic.

Inputs:

- Account snapshot
- Position snapshot
- Active risk policy
- Signal
- Quote
- Planned order
- Corporate action flags
- Existing open orders

Outputs:

- `APPROVED_FOR_HUMAN_REVIEW`
- `REJECTED`
- `AUTO_EXIT_REQUIRED`
- `BLOCK_NEW_ENTRIES`

Default policy:

```yaml
risk:
  max_account_exposure_pct: 90
  min_cash_buffer_pct: 10
  max_single_stock_pct: 10
  max_broad_etf_pct: 20
  max_sector_etf_pct: 15
  max_leveraged_inverse_total_pct: 15
  max_single_leveraged_inverse_pct: 7
  daily_loss_limit_pct: 1
  weekly_loss_limit_pct: 3
  monthly_loss_limit_pct: 8
  max_drawdown_stop_pct: 12
  same_symbol_cooldown_days: 3
```

Risk exit triggers:

- Hard stop-loss breach
- Portfolio loss limit breach
- Max drawdown breach
- Leveraged/inverse ETF holding limit breach
- Corporate action risk
- Broker/account state mismatch
- Abnormal spread/liquidity risk

### 3.7 Order Planner

Default order type:

- Marketable limit order

Inputs:

- Approved signal
- Account cash
- Target allocation
- Quote
- Risk policy
- Order configuration

Rules:

- No market orders by default
- Buy limit near ask with slippage cap
- Sell limit near bid with slippage cap
- Requote only within slippage cap
- Cancel on expiry
- Split large orders

Default configuration:

```yaml
orders:
  default_type: marketable_limit
  liquid_asset_slippage_bps: 15
  leveraged_inverse_slippage_bps: 30
  approval_expiry_minutes: 30
  order_expiry_minutes: 10
  avoid_open_minutes: 10
  avoid_close_minutes: 10
  split_order_notional_usd: 5000
```

### 3.8 Approval Gate

Telegram approval state machine:

```text
PENDING -> APPROVED -> STAGED -> SUBMITTED -> PARTIALLY_FILLED -> FILLED
PENDING -> REJECTED
PENDING -> EXPIRED
SUBMITTED -> CANCELLED
SUBMITTED -> FAILED
```

Approval payload:

```json
{
  "approval_id": "uuid",
  "symbol": "TQQQ",
  "action": "BUY",
  "quantity": 10,
  "limit_price": 55.12,
  "notional_usd": 551.20,
  "target_weight": 0.05,
  "expires_at": "2026-04-22T14:30:00Z"
}
```

Buttons:

- Approve
- Reject
- Snooze

Security requirements:

- Only configured Telegram user IDs can approve.
- Approval callback must verify token and user ID.
- Expired approvals cannot be executed.
- Approval logs must be immutable.

### 3.9 Execution Service

Responsibilities:

- Submit orders to KIS
- Retry only safe idempotent operations
- Never duplicate order submission without idempotency key
- Track broker order ID
- Poll order status when necessary
- Record all raw broker responses
- Trigger reconciliation after fills

### 3.10 Reconciliation Service

Responsibilities:

- Sync broker balances
- Sync positions
- Sync fills
- Compare internal ledger with broker account
- Raise alerts on mismatch
- Update tax ledger

Recommended cadence:

- After every order/fill event
- End of regular session
- Daily scheduled reconciliation

### 3.11 Tax Ledger

Responsibilities:

- Track lots
- Track cost basis
- Track disposal proceeds
- Track USD/KRW conversion
- Track fees
- Track dividends/distributions
- Track corporate action adjustments
- Export CSV/Excel

Lot method must be configurable if broker data supports it. MVP should follow broker-reported realized PnL where available and retain internal calculated lots for audit.

## 4. Data Model

Core tables:

```text
users
broker_accounts
assets
asset_universe_versions
asset_universe_members
market_quotes
candles
signals
llm_reports
risk_checks
approval_requests
planned_orders
broker_orders
fills
positions
cash_snapshots
portfolio_snapshots
tax_lots
tax_events
corporate_actions
dividends
system_events
audit_logs
```

Important constraints:

- `broker_orders.approval_request_id` required for normal entry orders
- risk-exit orders must reference `risk_check_id`
- all state transitions must be timestamped
- all broker raw responses stored in JSONB
- all money fields store currency explicitly

## 5. API Design

### Backend API

```text
GET  /api/portfolio/summary
GET  /api/universe/current
POST /api/universe/refresh
GET  /api/signals
POST /api/signals/scan
GET  /api/approvals
POST /api/approvals/{id}/approve
POST /api/approvals/{id}/reject
GET  /api/orders
GET  /api/orders/{id}
POST /api/orders/{id}/cancel
GET  /api/risk/status
GET  /api/tax/year/{year}
GET  /api/tax/year/{year}/export.csv
GET  /api/tax/year/{year}/export.xlsx
POST /api/webhooks/telegram
```

### Frontend Routes

```text
/dashboard
/universe
/signals
/approvals
/orders
/portfolio
/risk
/tax
/settings
```

All UI copy must be English.

## 6. Scheduling

Recommended MVP jobs:

```text
weekly_universe_refresh
daily_signal_scan
pre_market_approval_digest
regular_session_order_executor
order_status_poller
post_market_reconciliation
daily_tax_ledger_update
corporate_action_check
database_backup
```

Swing/medium-term design should avoid frequent intraday signal scans by default.

## 7. Security

- Secrets in environment variables or secret manager
- No secrets in frontend bundle
- Telegram approvals restricted to configured user IDs
- HTTPS required in production
- Admin dashboard protected by authentication
- Broker tokens encrypted at rest if persisted
- Audit log append-only
- Kill switch available from UI and Telegram
- Separate paper/live mode configuration

## 8. Observability

Required logs:

- KIS API requests/responses
- LLM prompts/responses
- Risk check decisions
- Approval events
- Order submissions
- Fills
- Reconciliation diffs
- Tax ledger updates
- System errors

Required alerts:

- Failed order submission
- Partial fill remaining after expiry
- Reconciliation mismatch
- Stale market data
- Token refresh failure
- Risk breach
- Telegram webhook failure
- Database backup failure

## 9. Environments

```text
local
paper
live
```

Rules:

- `local` can use mocked broker.
- `paper` uses KIS paper environment if supported for overseas stocks.
- `live` requires explicit configuration and startup confirmation.
- Live mode must display persistent warning in UI.

## 10. Migration from Current Project

The current project has useful pieces:

- Technical indicator tools
- Chart generation
- Agent-style analysis structure
- Existing benchmark data

Pieces to replace or heavily refactor:

- Flask web interface -> FastAPI + React
- Direct Yahoo Finance dependency -> KIS market data adapter first
- Decision agent that forces LONG/SHORT -> signal explainer only
- API key handling -> provider abstraction and secure config
- No execution layer -> broker adapter and execution service
- No risk manager -> deterministic risk manager
- No tax ledger -> dedicated tax module

## 11. Known Risks

- KIS overseas API rate limits may constrain universe scanning.
- Overseas real-time data availability may vary by endpoint and market.
- Broker-reported KRW tax data may not be complete for all reporting needs.
- Telegram webhook reliability must be monitored.
- Cloud server clock drift can affect session handling.
- Leveraged/inverse ETF behavior can be harmful for medium/long holding periods.
- LLM output can be wrong or unstable, so deterministic gates are mandatory.

