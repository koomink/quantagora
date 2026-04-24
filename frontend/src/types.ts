export type RuntimeSettings = {
  environment: string;
  broker: string;
  brokerMode: string;
  llmProvider: string;
  llmModel: string;
  tradingSession: string;
};

export type MarketStatus = {
  exchange: string;
  timezone: string;
  nowUtc: string;
  nowLocal: string;
  marketDate: string;
  state: string;
  isOpen: boolean;
  regularSessionOnlyAllowed: boolean;
  reason: string;
  sessionOpenUtc: string | null;
  sessionCloseUtc: string | null;
  nextOpenUtc: string;
  nextCloseUtc: string;
};

export type PortfolioSummary = {
  asOf: string;
  baseCurrency: string;
  accountMode: string;
  grossExposurePct: number;
  cashBufferPct: number;
  positions: unknown[];
  status: string;
};

export type Asset = {
  symbol: string;
  name: string;
  asset_type: string;
  exchange: string;
  is_us_listed: boolean;
  is_otc: boolean;
  leveraged_inverse_flag: boolean;
  supported_by_broker: boolean;
};

export type UniverseMember = {
  asset: Asset;
  rank: number;
  rationale: string;
  eligibility: {
    score?: number;
    warnings?: string[];
    metrics?: {
      latestPrice?: string | null;
      spreadBps?: string | null;
      avgDollarVolume?: string | null;
      historyDays?: number;
    };
  };
};

export type UniverseVersion = {
  version_id: string;
  status: string;
  source: string;
  generated_at: string | null;
  activated_at: string | null;
  metadata: {
    acceptedCount?: number;
    rejectedCount?: number;
  };
  rejected_candidates: Array<{
    symbol: string;
    reasons: string[];
  }>;
  members: UniverseMember[];
};

export type SignalRecord = {
  signalId: string;
  symbol: string;
  action: string;
  strategy: string;
  horizon: string;
  confidence: number;
  targetWeight: number;
  source: string;
  status: string;
  rationale: string;
  invalidation: string;
  generatedAt: string;
  expiresAt: string;
  indicators: {
    sma20?: number | null;
    sma50?: number | null;
    sma200?: number | null;
    rsi14?: number | null;
    roc20?: number | null;
    macd?: number | null;
    macd_signal?: number | null;
    macd_hist?: number | null;
    atr14_pct?: number | null;
    realized_vol20?: number | null;
  };
  regime: {
    benchmark_symbol?: string;
    state?: string;
    reason?: string;
  };
  metadata: Record<string, unknown>;
};

export type SignalList = {
  items: SignalRecord[];
  status: string;
  summary: {
    count: number;
    activeCount: number;
    expiredCount: number;
  };
};

export type LlmReportRecord = {
  report_id: string;
  report_type: string;
  entity_type: string;
  entity_id: string;
  provider: string;
  model: string;
  status: string;
  prompt_version: string;
  fallback_used: boolean;
  generated_at: string;
  error_message: string | null;
  report: {
    summary?: string;
    key_drivers?: string[];
    risk_flags?: string[];
    selection_discipline?: string;
    uncertainty?: string;
    setup?: string;
    confirmations?: string[];
    invalidation_focus?: string;
    outcome?: string;
    what_worked?: string[];
    what_to_improve?: string[];
    follow_ups?: string[];
    risk_decision_locked?: boolean;
  };
};

export type LlmReportList = {
  items: LlmReportRecord[];
  status: string;
};

export type RiskStatus = {
  state: string;
  newEntriesAllowed: boolean;
  reason: string;
  policy: Record<string, number>;
};

export type ApprovalList = {
  items: unknown[];
  status: string;
};
