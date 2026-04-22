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
  leveraged_inverse_flag: boolean;
};

export type UniverseMember = {
  asset: Asset;
  rank: number;
  rationale: string;
};

export type UniverseVersion = {
  version_id: string;
  status: string;
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
