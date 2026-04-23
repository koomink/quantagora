# Tasks: US-Listed Securities Auto-Trading Product

## Phase 0: Product and Safety Foundation

- [ ] Confirm KIS Open API account setup and overseas stock API availability.
- [ ] Confirm paper/live environment support for overseas stock orders.
- [ ] Confirm exact overseas order types supported by KIS.
- [ ] Confirm quote latency and real-time/delayed status for US markets.
- [ ] Define initial leveraged/inverse ETF whitelist.
- [ ] Define initial risk policy values.
- [ ] Define Telegram approval expiry and message format.
- [ ] Decide final deployment target: Vultr Seoul or Oracle Cloud.
- [ ] Create environment variable contract for secrets.

## Phase 1: Repository Restructure

- [x] Create backend FastAPI app skeleton.
- [x] Create frontend React + Vite + TypeScript app skeleton.
- [x] Add Docker Compose for backend, frontend, PostgreSQL.
- [x] Add configuration loader for local/paper/live environments.
- [x] Add structured logging.
- [x] Add baseline authentication for admin UI.
- [x] Add `.env.example`.
- [x] Add CI lint/test commands.

## Phase 2: Database and Domain Models

- [x] Add PostgreSQL schema migration tooling.
- [x] Create `assets` table.
- [x] Create `market_quotes` table.
- [x] Create `candles` table.
- [x] Create `asset_universe_versions` table.
- [x] Create `asset_universe_members` table.
- [x] Create `signals` table.
- [x] Create `risk_checks` table.
- [x] Create `approval_requests` table.
- [x] Create `planned_orders` table.
- [x] Create `broker_orders` table.
- [x] Create `fills` table.
- [x] Create `positions` table.
- [x] Create `cash_snapshots` table.
- [x] Create `portfolio_snapshots` table.
- [x] Create `tax_lots` table.
- [x] Create `tax_events` table.
- [x] Create `corporate_actions` table.
- [x] Create `audit_logs` table.

## Phase 3: KIS Broker Adapter

- [x] Implement broker adapter interface.
- [x] Implement KIS OAuth token flow.
- [x] Implement KIS token refresh.
- [x] Implement KIS quote fetch for overseas stocks.
- [x] Implement KIS candle fetch for overseas stocks.
- [x] Implement KIS account balance fetch.
- [x] Implement KIS overseas position fetch.
- [x] Implement KIS buying power fetch.
- [x] Implement KIS overseas order submission.
- [x] Implement KIS order cancellation.
- [x] Implement KIS order status lookup.
- [x] Implement KIS fill history lookup.
- [x] Normalize KIS API errors.
- [x] Add rate-limit handling.
- [x] Store raw broker responses for audit.
- [x] Add mocked broker adapter for local testing.

## Phase 4: Market Data and Calendar

- [x] Add US market calendar module.
- [x] Store all timestamps in UTC.
- [x] Display market status in English UI.
- [x] Implement regular-session-only guard.
- [x] Implement stale data detection.
- [x] Implement quote snapshot persistence.
- [x] Implement candle backfill job.
- [x] Implement daily market data refresh.

## Phase 5: Universe Engine

- [x] Implement candidate source from KIS market data.
- [x] Implement agent-recommended candidate input.
- [x] Add asset eligibility filter.
- [x] Add liquidity filter.
- [x] Add bid-ask spread filter.
- [x] Add price threshold filter.
- [x] Add OTC exclusion.
- [x] Add unsupported product exclusion.
- [x] Add leveraged/inverse ETF whitelist.
- [x] Add weekly universe versioning.
- [x] Add manual universe refresh API.
- [x] Add universe dashboard.

## Phase 6: Signal Engine

- [ ] Define structured signal schema.
- [ ] Port useful technical indicator code from current project.
- [ ] Implement trend-following signal.
- [ ] Implement pullback signal.
- [ ] Implement volatility regime filter.
- [ ] Implement momentum confirmation.
- [ ] Add same-symbol cooldown.
- [ ] Add daily scan scheduler.
- [ ] Store generated signals.
- [ ] Add signal detail UI.

## Phase 7: LLM Provider Layer

- [ ] Add LLM provider interface.
- [ ] Implement OpenAI provider.
- [ ] Implement OpenRouter-compatible provider.
- [ ] Add structured JSON response validation.
- [ ] Add prompt templates for universe rationale.
- [ ] Add prompt templates for trade rationale.
- [ ] Add prompt templates for post-trade review.
- [ ] Store LLM reports.
- [ ] Add fallback behavior when LLM fails.
- [ ] Ensure LLM cannot override risk decisions.

## Phase 8: Risk Manager

- [ ] Implement risk policy config.
- [ ] Add account exposure check.
- [ ] Add cash buffer check.
- [ ] Add single-stock max weight check.
- [ ] Add ETF max weight check.
- [ ] Add leveraged/inverse total exposure check.
- [ ] Add single leveraged/inverse exposure check.
- [ ] Add daily loss limit.
- [ ] Add weekly loss limit.
- [ ] Add monthly loss limit.
- [ ] Add max drawdown stop.
- [ ] Add spread/liquidity risk check.
- [ ] Add stale signal check.
- [ ] Add broker/account mismatch check.
- [ ] Add risk-exit decision output.
- [ ] Persist every risk check.
- [ ] Add risk dashboard.

## Phase 9: Order Planner

- [ ] Implement marketable limit order planner.
- [ ] Add buy limit price calculation.
- [ ] Add sell limit price calculation.
- [ ] Add slippage cap configuration.
- [ ] Add leveraged/inverse ETF slippage policy.
- [ ] Add no-market-order default.
- [ ] Add order expiry.
- [ ] Add order split threshold.
- [ ] Add avoid-open window.
- [ ] Add avoid-close window.
- [ ] Add planned order persistence.

## Phase 10: Telegram Approval Gate

- [ ] Create Telegram bot.
- [ ] Configure allowed Telegram user IDs.
- [ ] Implement approval request creation.
- [ ] Implement English approval message template.
- [ ] Add Approve button.
- [ ] Add Reject button.
- [ ] Add Snooze button.
- [ ] Implement webhook endpoint.
- [ ] Verify callback user ID.
- [ ] Enforce approval expiry.
- [ ] Log all approval events.
- [ ] Add approval dashboard.
- [ ] Add daily approval request cap.

## Phase 11: Execution Service

- [ ] Implement approved-order executor.
- [ ] Implement risk-exit auto executor.
- [ ] Prevent duplicate submissions with idempotency keys.
- [ ] Submit orders only during regular session.
- [ ] Poll order status.
- [ ] Handle partial fills.
- [ ] Cancel expired orders.
- [ ] Notify Telegram on submission/fill/failure.
- [ ] Persist broker order state transitions.
- [ ] Add open orders UI.

## Phase 12: Reconciliation

- [ ] Sync positions after fills.
- [ ] Sync cash after fills.
- [ ] Sync open orders.
- [ ] Compare internal ledger with KIS account.
- [ ] Detect mismatches.
- [ ] Alert on mismatches.
- [ ] Add post-market reconciliation job.
- [ ] Add reconciliation dashboard section.

## Phase 13: Tax and Reporting

- [ ] Define tax event schema.
- [ ] Record every fill into tax ledger.
- [ ] Store USD price and fees.
- [ ] Store KRW converted values where available.
- [ ] Store applied FX rate.
- [ ] Track acquisition and disposal dates.
- [ ] Track realized gain/loss.
- [ ] Track dividends/distributions.
- [ ] Track withholding tax where available.
- [ ] Implement split/reverse split adjustments.
- [ ] Implement ticker change handling.
- [ ] Add annual tax summary screen.
- [ ] Add CSV export.
- [ ] Add Excel export.
- [ ] Add broker statement reconciliation checklist.

## Phase 14: Corporate Actions

- [ ] Add corporate action data ingestion strategy.
- [ ] Detect dividends/distributions.
- [ ] Detect split/reverse split.
- [ ] Detect ticker changes.
- [ ] Pause new orders for affected symbols.
- [ ] Notify user of corporate action review requirement.
- [ ] Update tax ledger after corporate action adjustment.

## Phase 15: Frontend UI

- [ ] Create English-only layout.
- [ ] Build dashboard page.
- [ ] Build universe page.
- [ ] Build signal page.
- [ ] Build approval page.
- [ ] Build order page.
- [ ] Build portfolio page.
- [ ] Build risk page.
- [ ] Build tax page.
- [ ] Build settings page.
- [ ] Add live/paper mode indicator.
- [ ] Add kill switch control.
- [ ] Add responsive layout.

## Phase 16: Deployment

- [ ] Create production Docker Compose file.
- [ ] Configure Nginx or Caddy.
- [ ] Configure TLS.
- [ ] Configure systemd service or Docker restart policy.
- [ ] Configure database backup.
- [ ] Configure log rotation.
- [ ] Configure health checks.
- [ ] Configure Telegram webhook URL.
- [ ] Deploy to Vultr Seoul MVP server.
- [ ] Document Oracle Cloud alternative deployment.

## Phase 17: Testing

- [ ] Unit test risk manager.
- [ ] Unit test order planner.
- [ ] Unit test approval expiry.
- [ ] Unit test tax ledger calculations.
- [ ] Unit test KIS error normalization.
- [ ] Integration test mocked broker order flow.
- [ ] Integration test Telegram approval flow.
- [ ] Integration test reconciliation mismatch.
- [ ] Backtest initial strategy.
- [ ] Paper trade for minimum 4 weeks.
- [ ] Review all live-mode safety gates before enabling live orders.

## Phase 18: Live Readiness Checklist

- [ ] KIS live credentials configured.
- [ ] Telegram user allowlist verified.
- [ ] Kill switch tested.
- [ ] Regular-session guard tested.
- [ ] Market order disabled by default.
- [ ] Risk exits tested in paper mode.
- [ ] New-entry orders require approval.
- [ ] Tax ledger export tested.
- [ ] Daily backup verified.
- [ ] Reconciliation alert tested.
- [ ] First live trade size capped to minimal notional.
