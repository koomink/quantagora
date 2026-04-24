import type {
  ApprovalList,
  LlmReportRecord,
  LlmReportList,
  MarketStatus,
  PortfolioSummary,
  RiskStatus,
  RuntimeSettings,
  SignalList,
  UniverseVersion
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(
  path: string,
  adminToken: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": adminToken,
      ...options.headers
    }
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function fetchRuntimeSettings(adminToken: string): Promise<RuntimeSettings> {
  return request<RuntimeSettings>("/api/settings/runtime", adminToken);
}

export function fetchPortfolioSummary(adminToken: string): Promise<PortfolioSummary> {
  return request<PortfolioSummary>("/api/portfolio/summary", adminToken);
}

export function fetchMarketStatus(adminToken: string): Promise<MarketStatus> {
  return request<MarketStatus>("/api/market/status", adminToken);
}

export function fetchUniverse(adminToken: string): Promise<UniverseVersion> {
  return request<UniverseVersion>("/api/universe/current", adminToken);
}

export function refreshUniverse(adminToken: string): Promise<UniverseVersion> {
  return request<UniverseVersion>("/api/universe/refresh", adminToken, {
    method: "POST",
    body: JSON.stringify({
      fetch_market_data: true,
      force_new_version: false
    })
  });
}

export function fetchRiskStatus(adminToken: string): Promise<RiskStatus> {
  return request<RiskStatus>("/api/risk/status", adminToken);
}

export function fetchSignals(adminToken: string): Promise<SignalList> {
  return request<SignalList>("/api/signals", adminToken);
}

export function scanSignals(adminToken: string): Promise<SignalList> {
  return request<SignalList>("/api/signals/scan", adminToken, {
    method: "POST",
    body: JSON.stringify({
      ignore_cooldown: false
    })
  });
}

export function fetchLlmReports(adminToken: string): Promise<LlmReportList> {
  return request<LlmReportList>("/api/llm/reports?limit=20", adminToken);
}

export function generateUniverseReport(adminToken: string): Promise<LlmReportRecord> {
  return request<LlmReportRecord>("/api/llm/reports/universe/current", adminToken, {
    method: "POST"
  });
}

export function generateTradeRationale(
  adminToken: string,
  signalId: string
): Promise<LlmReportRecord> {
  return request<LlmReportRecord>(`/api/llm/reports/signals/${signalId}`, adminToken, {
    method: "POST"
  });
}

export function fetchApprovals(adminToken: string): Promise<ApprovalList> {
  return request<ApprovalList>("/api/approvals", adminToken);
}
