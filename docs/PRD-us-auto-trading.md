# PRD: US-Listed Securities Auto-Trading Product for Korean Retail Investor

## 1. Product Summary

이 제품은 한국 거주 개인투자자 1인이 한국투자증권 Open API를 통해 미국상장증권을 분석하고, Telegram 승인 게이트를 거쳐 정규장 주문을 실행하는 개인용 자동매매 보조 시스템이다.

기존 QuantAgent 프로젝트의 멀티 에이전트 분석 구조를 차용하되, 실거래 제품에서는 LLM이 직접 주문을 실행하지 않는다. LLM과 agent는 universe 후보 선정, 신호 설명, 리포트 생성, 사후 분석을 담당하고, 실제 주문은 deterministic risk manager와 human approval gate를 통과한 경우에만 실행된다.

## 2. Goals

- 한국투자증권 Open API 기반 미국주식/ETF 매매 지원
- 미국 상장 보통주, ETF, 레버리지 ETF, 인버스 ETF를 포함한 자동 universe 선정
- Swing to medium/long-term 전략에 맞는 낮은 빈도의 승인 기반 매매
- Telegram one-click approval 기반 주문 승인
- 현금계좌만 고려하고 마진, 미수, 공매도는 배제
- 정규장 거래만 지원
- 주문은 marketable limit order를 기본으로 하며 시장가는 기본 금지
- 위험 청산 조건은 승인 없이 자동 실행 가능
- 세금/손익 리포트를 핵심 기능으로 제공
- 모든 제품 UI는 English-only로 제공
- 개인용 클라우드 배포를 고려한 저비용 운영

## 3. Non-Goals

- 다중 사용자 SaaS 제공
- 투자자문/투자일임 서비스 제공
- 국내주식 자동매매
- 옵션, 선물, CFD, 암호화폐 거래
- 프리마켓/애프터마켓 거래
- 완전 자동 신규 진입
- HFT 또는 초단타 매매
- 마진/신용/공매도 기반 전략

## 4. Target User

- 한국 거주 개인투자자 1인
- 운용자금 초기 1천만원-1억원
- 향후 운용자금 증가 가능
- 미국 상장 증권, 특히 ETF와 레버리지/인버스 ETF를 활용한 스윙-중장기 운용 지향
- 본인이 Telegram으로 주문 승인 여부를 직접 결정

## 5. Product Scope

### 5.1 Supported Broker

- Primary broker: Korea Investment Securities Open API
- Supported API domains:
  - Overseas stock order/account
  - Overseas stock quotes
  - Overseas stock minute/daily candles
  - Overseas stock real-time quote/order notifications where available
  - Account balance and buying power
  - Order/fill history

### 5.2 Supported Assets

- US-listed common stocks
- US-listed ETFs
- Leveraged ETFs
- Inverse ETFs

Initial leveraged/inverse ETF whitelist:

- `TQQQ`, `SQQQ`
- `SOXL`, `SOXS`
- `UPRO`, `SPXU`

The system may recommend additional universe candidates, but all candidates must pass eligibility and risk filters before becoming tradable.

### 5.3 Trading Session

- US regular session only
- No pre-market trading
- No after-hours trading
- UI displays times in English with clear timezone labels
- Internal scheduling must use `America/New_York` market calendar and store timestamps in UTC

## 6. Core User Flows

### 6.1 Universe Selection

1. System scans KIS market data and existing watchlist.
2. Agents propose candidate assets.
3. Eligibility filter removes unsupported or unsafe assets.
4. Risk filter applies liquidity, spread, volatility, and asset-type limits.
5. User reviews the generated universe summary.
6. Approved universe becomes active for signal scanning.

Default cadence:

- Universe refresh: weekly
- Preferred timing: Sunday night KST or before Monday US regular session
- Manual refresh allowed

### 6.2 Signal Review and Approval

1. System scans active universe after market close or before next regular session.
2. Signal engine generates buy/sell/rebalance candidates.
3. LLM agent generates concise explanation.
4. Risk manager validates the proposed action.
5. If valid, Telegram sends an approval card.
6. User approves or rejects.
7. If approved, order planner stages a marketable limit order for the next valid regular session.
8. Execution service submits order to KIS.
9. Reconciliation service records fills, cash, position, and tax ledger entries.

Default cadence:

- Signal scan: once per trading day
- Expected Telegram approval requests: 0-3 per week
- Hard cap: 1 approval request per day by default
- Exceptional hard cap: 2 per day if explicitly configured
- Same-symbol cooldown: 3-5 trading days
- No response before expiry means auto-cancel

### 6.3 Risk Exit

Risk exits may be executed automatically without Telegram approval. The system must still notify the user immediately.

Allowed automatic exits:

- Hard stop-loss breach
- Portfolio daily/weekly/monthly loss breach
- Max drawdown breach
- Leveraged/inverse ETF holding-period breach
- Corporate action risk flag
- Abnormal spread/liquidity condition requiring exposure reduction
- Broker/account state mismatch requiring exposure reduction

## 7. Functional Requirements

### 7.1 Market Data

- Fetch overseas stock quotes from KIS.
- Fetch historical candles for signal generation.
- Store daily and minute-level market data needed by the strategy.
- Detect stale data and prevent trading on stale data.
- Maintain exchange calendar and holiday awareness.

### 7.2 Universe Engine

- Produce weekly candidate list.
- Rank assets by trend, liquidity, volatility, momentum, and agent assessment.
- Apply explicit eligibility filters:
  - US-listed assets only
  - OTC excluded
  - Unsupported product types excluded
  - Minimum average dollar volume
  - Maximum bid-ask spread
  - Minimum price threshold
  - Corporate action risk check
- Apply leveraged/inverse ETF policy.

### 7.3 Signal Engine

- Generate swing/medium-term signals from price and volume data.
- Support technical indicators, trend, volatility, drawdown, and regime filters.
- Separate signal generation from order execution.
- Output structured signal payload:
  - symbol
  - action
  - confidence
  - horizon
  - rationale
  - invalidation condition
  - proposed allocation

### 7.4 LLM Research Agent

- Explain candidate selection and trade rationale.
- Summarize risk factors in plain English UI text.
- Produce structured JSON outputs for downstream services.
- Never bypass risk manager.
- Never directly submit orders.
- Support OpenAI and OpenRouter-compatible providers.

### 7.5 Risk Manager

Recommended default policy:

- Account exposure max: 80-90%
- Cash buffer min: 10%
- Single common stock max: 10%
- Broad-market ETF max: 20%
- Sector ETF max: 15%
- Total leveraged/inverse ETF max: 15%
- Single leveraged/inverse ETF max: 5-7%
- Daily loss limit: 1%
- Weekly loss limit: 3%
- Monthly loss limit: 6-8%
- Max drawdown stop: 10-12%
- New entries blocked after loss limit breach
- Risk exits may continue after breach

Risk manager must validate:

- Cash availability
- Position size
- Asset type policy
- Existing exposure
- Order notional
- Spread and liquidity
- Signal age
- Account and position consistency

### 7.6 Order Planner

Default order type: marketable limit order.

Recommended behavior:

- Buy limit: current ask or `mid + slippage_cap`
- Sell limit: current bid or `mid - slippage_cap`
- Never use market order by default
- No automatic market-order fallback
- Requote if unfilled after configured interval
- Cancel if max slippage exceeded
- Split orders above configured notional threshold
- Avoid first 5-15 minutes after open by default
- Avoid last 5-10 minutes before close by default

Default slippage caps:

- Highly liquid stocks/ETFs: 5-15 bps
- Leveraged/inverse ETFs: 10-30 bps

### 7.7 Approval Gate

Telegram message must include:

- Symbol and asset name
- Action: Buy, Sell, Rebalance, Risk Exit Notice
- Proposed quantity and notional
- Limit price
- Expected portfolio weight after trade
- Key rationale
- Key risk
- Approval expiry time
- Buttons: Approve, Reject, Snooze

For risk exits, Telegram message must indicate that execution is automatic and include reason and fill status.

### 7.8 Execution and Reconciliation

- Submit approved orders to KIS.
- Track order status.
- Handle partial fills.
- Cancel expired orders.
- Record all requests and broker responses.
- Reconcile positions and cash after fills.
- Detect mismatches and alert user.

### 7.9 Tax and Reporting

Tax reporting is a core feature.

Must track:

- USD execution price
- USD fees
- KRW converted amount
- Applied FX rate
- Acquisition date
- Disposal date
- Realized gain/loss
- Dividends/distributions
- Withholding tax where available
- Split/reverse split adjustments
- Ticker changes

Reports:

- Annual realized gain/loss report
- Trade ledger CSV
- Tax support Excel export
- Dividend/distribution report
- Portfolio performance report

The report is a tax-support artifact, not a final tax filing guarantee. Broker annual statements remain the source for final reconciliation.

### 7.10 Corporate Actions

Corporate actions are events such as dividend, distribution, stock split, reverse split, merger, spin-off, ticker change, delisting, and ETF distribution.

MVP support:

- Record dividends/distributions
- Reflect split/reverse split on quantity and cost basis
- Detect ticker changes when possible
- Pause new orders for affected symbols until reviewed

## 8. UI Requirements

- UI language: English only
- Dashboard:
  - Portfolio summary
  - Cash and exposure
  - Active universe
  - Pending approvals
  - Open orders
  - Risk status
  - Tax summary
- Trade detail view:
  - Signal rationale
  - Risk checks
  - Order plan
  - Approval history
  - Fill history
- Risk dashboard:
  - Daily/weekly/monthly PnL
  - Drawdown
  - Exposure by asset type
  - Leveraged/inverse ETF exposure
  - Rule breaches
- Tax dashboard:
  - Realized gain/loss
  - Dividends
  - Export controls

## 9. Deployment Requirements

Primary MVP deployment:

- Vultr Seoul VPS
- Docker Compose
- FastAPI backend
- React frontend
- PostgreSQL database
- Scheduled workers
- Telegram bot integration

Oracle Cloud Free Tier can be used for cost-minimal testing, but Vultr is recommended for simpler and more predictable MVP operation.

## 10. Success Metrics

- No unapproved new-entry live orders
- 100% of submitted live orders traceable to approval or risk-exit rule
- Daily reconciliation success
- Tax ledger generated for every fill
- No trades outside US regular session
- No margin or short exposure
- Approval request frequency remains manageable, target 0-3 per week
- Risk rule breach notifications delivered reliably

## 11. Open Questions

- Exact KIS API rate limits for the selected account and app
- Whether KIS overseas quote data is real-time, delayed, or mixed by market/session
- Exact supported overseas order types for US stocks and ETFs
- FX conversion source and whether broker-provided KRW values are sufficient for all tax reports
- Final initial universe size and ranking model
- Exact Telegram approval expiry duration

