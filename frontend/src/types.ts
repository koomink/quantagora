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
