import { useEffect, useMemo, useState } from "react";

import {
  fetchApprovals,
  fetchLlmReports,
  fetchMarketStatus,
  fetchPortfolioSummary,
  fetchRiskStatus,
  fetchRuntimeSettings,
  fetchSignals,
  scanSignals,
  generateTradeRationale,
  generateUniverseReport,
  fetchUniverse,
  refreshUniverse
} from "./api";
import type {
  ApprovalList,
  LlmReportList,
  LlmReportRecord,
  MarketStatus,
  PortfolioSummary,
  RiskStatus,
  RuntimeSettings,
  SignalList,
  SignalRecord,
  UniverseVersion
} from "./types";

type DashboardData = {
  runtime: RuntimeSettings;
  market: MarketStatus;
  portfolio: PortfolioSummary;
  universe: UniverseVersion;
  signals: SignalList;
  llm: LlmReportList;
  risk: RiskStatus;
  approvals: ApprovalList;
};

const navItems = ["Dashboard", "Universe", "Signals", "Approvals", "Orders", "Risk", "Tax"];

function Icon({ name }: { name: "refresh" | "shield" | "bolt" | "check" }) {
  const paths = {
    refresh: "M4 4v5h.6A7 7 0 1 0 6 3.8L4 6.1M20 20v-5h-.6A7 7 0 1 1 18 20.2L20 17.9",
    shield: "M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6l7-3z",
    bolt: "M13 2L4 14h7l-1 8 9-12h-7l1-8z",
    check: "M20 6L9 17l-5-5"
  };

  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="icon">
      <path d={paths[name]} />
    </svg>
  );
}

function formatDateTime(value?: string | null) {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZoneName: "short"
  }).format(new Date(value));
}

function formatDollarMetric(value?: string | null) {
  if (!value) return "No data";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "No data";
  return new Intl.NumberFormat("en", {
    currency: "USD",
    maximumFractionDigits: 1,
    notation: "compact",
    style: "currency"
  }).format(numeric);
}

function formatPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return value.toFixed(2);
}

function App() {
  const [adminToken, setAdminToken] = useState(() => {
    return localStorage.getItem("quantagora.adminToken") ?? "dev-admin-token";
  });
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshingUniverse, setIsRefreshingUniverse] = useState(false);
  const [isScanningSignals, setIsScanningSignals] = useState(false);
  const [isGeneratingUniverseReport, setIsGeneratingUniverseReport] = useState(false);
  const [isGeneratingTradeReport, setIsGeneratingTradeReport] = useState(false);
  const [selectedSignalId, setSelectedSignalId] = useState<string | null>(null);

  const lastUpdated = useMemo(() => {
    if (!data) return "Not loaded";
    return new Intl.DateTimeFormat("en", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZoneName: "short"
    }).format(new Date(data.portfolio.asOf));
  }, [data]);

  async function loadDashboard(nextToken = adminToken) {
    setIsLoading(true);
    setError(null);
    try {
      const [signals, runtime, market, portfolio, universe, llm, risk, approvals] =
        await Promise.all([
        fetchSignals(nextToken),
        fetchRuntimeSettings(nextToken),
        fetchMarketStatus(nextToken),
        fetchPortfolioSummary(nextToken),
        fetchUniverse(nextToken),
        fetchLlmReports(nextToken),
        fetchRiskStatus(nextToken),
        fetchApprovals(nextToken)
        ]);
      setData({
        runtime,
        market,
        portfolio,
        universe,
        signals,
        llm,
        risk,
        approvals
      });
      setSelectedSignalId(signals.items[0]?.signalId ?? null);
      localStorage.setItem("quantagora.adminToken", nextToken);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load dashboard.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleUniverseRefresh() {
    setIsRefreshingUniverse(true);
    setError(null);
    try {
      const universe = await refreshUniverse(adminToken);
      setData((current) => (current ? { ...current, universe } : current));
    } catch (refreshError) {
      setError(
        refreshError instanceof Error ? refreshError.message : "Unable to refresh universe."
      );
    } finally {
      setIsRefreshingUniverse(false);
    }
  }

  async function handleSignalScan() {
    setIsScanningSignals(true);
    setError(null);
    try {
      const signals = await scanSignals(adminToken);
      setData((current) => (current ? { ...current, signals } : current));
      setSelectedSignalId(signals.items[0]?.signalId ?? null);
    } catch (scanError) {
      setError(scanError instanceof Error ? scanError.message : "Unable to scan signals.");
    } finally {
      setIsScanningSignals(false);
    }
  }

  async function handleUniverseReport() {
    setIsGeneratingUniverseReport(true);
    setError(null);
    try {
      const report = await generateUniverseReport(adminToken);
      setData((current) =>
        current
          ? { ...current, llm: { ...current.llm, items: [report, ...current.llm.items] } }
          : current
      );
    } catch (reportError) {
      setError(
        reportError instanceof Error
          ? reportError.message
          : "Unable to generate universe explanation."
      );
    } finally {
      setIsGeneratingUniverseReport(false);
    }
  }

  async function handleTradeReport() {
    if (!selectedSignal) return;
    setIsGeneratingTradeReport(true);
    setError(null);
    try {
      const report = await generateTradeRationale(adminToken, selectedSignal.signalId);
      setData((current) =>
        current
          ? { ...current, llm: { ...current.llm, items: [report, ...current.llm.items] } }
          : current
      );
    } catch (reportError) {
      setError(
        reportError instanceof Error ? reportError.message : "Unable to generate trade explanation."
      );
    } finally {
      setIsGeneratingTradeReport(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  const selectedSignal = useMemo<SignalRecord | null>(() => {
    if (!data?.signals.items.length) return null;
    return (
      data.signals.items.find((signal) => signal.signalId === selectedSignalId) ??
      data.signals.items[0]
    );
  }, [data?.signals.items, selectedSignalId]);

  const latestUniverseReport = useMemo<LlmReportRecord | null>(() => {
    if (!data?.llm.items.length) return null;
    return data.llm.items.find((report) => report.report_type === "universe_rationale") ?? null;
  }, [data?.llm.items]);

  const selectedSignalReport = useMemo<LlmReportRecord | null>(() => {
    if (!data?.llm.items.length || !selectedSignal) return null;
    return (
      data.llm.items.find(
        (report) =>
          report.report_type === "trade_rationale" && report.entity_id === selectedSignal.signalId
      ) ?? null
    );
  }, [data?.llm.items, selectedSignal]);

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">Q</span>
          <span>
            <strong>QuantAgora</strong>
            <small>Trading Assistant</small>
          </span>
        </div>
        <nav className="nav-list" aria-label="Primary navigation">
          {navItems.map((item, index) => (
            <button className={index === 0 ? "nav-item active" : "nav-item"} key={item}>
              {item}
            </button>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Personal cash account</p>
            <h1>Operations Dashboard</h1>
          </div>
          <div className="topbar-actions">
            <input
              aria-label="Admin token"
              className="token-input"
              value={adminToken}
              onChange={(event) => setAdminToken(event.target.value)}
              type="password"
            />
            <button className="icon-button" onClick={() => void loadDashboard()} title="Refresh">
              <Icon name="refresh" />
            </button>
          </div>
        </header>

        {error ? <div className="alert">{error}</div> : null}

        <section className="status-grid" aria-busy={isLoading}>
          <article className="metric-card">
            <span className="metric-label">Market Status</span>
            <strong className={data?.market.isOpen ? "market-open" : "market-closed"}>
              {data?.market.state.replaceAll("_", " ") ?? "Loading"}
            </strong>
            <small>{data?.market.reason ?? "US regular session only"}</small>
          </article>
          <article className="metric-card">
            <span className="metric-label">Gross Exposure</span>
            <strong>{data?.portfolio.grossExposurePct ?? 0}%</strong>
            <small>{data?.portfolio.accountMode ?? "cash_only"}</small>
          </article>
          <article className="metric-card">
            <span className="metric-label">Cash Buffer</span>
            <strong>{data?.portfolio.cashBufferPct ?? 0}%</strong>
            <small>{data?.portfolio.baseCurrency ?? "USD"} base currency</small>
          </article>
          <article className="metric-card">
            <span className="metric-label">Pending Approvals</span>
            <strong>{data?.approvals.items.length ?? 0}</strong>
            <small>{data?.approvals.status ?? "Loading"}</small>
          </article>
          <article className="metric-card">
            <span className="metric-label">Universe Assets</span>
            <strong>{data?.universe.members.length ?? 0}</strong>
            <small>{data?.universe.version_id ?? "Loading"}</small>
          </article>
          <article className="metric-card">
            <span className="metric-label">Signal Candidates</span>
            <strong>{data?.signals.summary.activeCount ?? 0}</strong>
            <small>{data?.signals.status ?? "Loading"}</small>
          </article>
        </section>

        <section className="content-grid">
          <article className="panel wide">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Active universe</p>
                <h2>
                  {data?.universe.status === "bootstrap"
                    ? "Bootstrap Watchlist"
                    : "Filtered Watchlist"}
                </h2>
              </div>
              <button
                className="text-button"
                disabled={isRefreshingUniverse}
                onClick={() => void handleUniverseRefresh()}
                type="button"
              >
                <Icon name="refresh" />
                {isRefreshingUniverse ? "Refreshing" : "Refresh"}
              </button>
            </div>
            <div className="panel-actions">
              <button
                className="text-button"
                disabled={isGeneratingUniverseReport}
                onClick={() => void handleUniverseReport()}
                type="button"
              >
                <Icon name="bolt" />
                {isGeneratingUniverseReport ? "Explaining" : "Explain"}
              </button>
            </div>
            <div className="universe-summary">
              <span>Source: {data?.universe.source ?? "system"}</span>
              <span>Generated: {formatDateTime(data?.universe.generated_at)}</span>
              <span>Rejected: {data?.universe.rejected_candidates.length ?? 0}</span>
            </div>
            <div className="asset-table">
              <div className="asset-row table-head">
                <span>Rank</span>
                <span>Symbol</span>
                <span>Type</span>
                <span>Liquidity</span>
                <span>Rationale</span>
              </div>
              {data?.universe.members.map((member) => (
                <div className="asset-row" key={member.asset.symbol}>
                  <span>{member.rank}</span>
                  <strong>{member.asset.symbol}</strong>
                  <span>{member.asset.asset_type.replaceAll("_", " ")}</span>
                  <span>{formatDollarMetric(member.eligibility.metrics?.avgDollarVolume)}</span>
                  <span>{member.rationale}</span>
                </div>
              ))}
            </div>
            {data?.universe.rejected_candidates.length ? (
              <div className="rejection-list">
                <span>Recently rejected</span>
                {data.universe.rejected_candidates.slice(0, 6).map((candidate) => (
                  <small key={candidate.symbol}>
                    {candidate.symbol}: {candidate.reasons.join(", ")}
                  </small>
                ))}
              </div>
            ) : null}
            {latestUniverseReport ? (
              <div className="report-card">
                <div className="report-header">
                  <strong>Universe Explanation</strong>
                  <span className={latestUniverseReport.fallback_used ? "report-badge fallback" : "report-badge"}>
                    {latestUniverseReport.status}
                  </span>
                </div>
                <p>{latestUniverseReport.report.summary}</p>
                <div className="report-grid">
                  <span>Key drivers</span>
                  <strong>
                    {(latestUniverseReport.report.key_drivers ?? []).join(" | ") || "N/A"}
                  </strong>
                  <span>Risk flags</span>
                  <strong>
                    {(latestUniverseReport.report.risk_flags ?? []).join(" | ") || "None"}
                  </strong>
                  <span>Discipline</span>
                  <strong>{latestUniverseReport.report.selection_discipline ?? "N/A"}</strong>
                  <span>Uncertainty</span>
                  <strong>{latestUniverseReport.report.uncertainty ?? "N/A"}</strong>
                </div>
              </div>
            ) : null}
          </article>

          <article className="panel">
            <div className="panel-header compact">
              <h2>Risk Gate</h2>
              <Icon name="shield" />
            </div>
            <p className="risk-state">{data?.risk.state ?? "Loading"}</p>
            <p className="muted">{data?.risk.reason ?? "Loading risk policy."}</p>
            <div className="policy-list">
              <span>Max exposure</span>
              <strong>{data?.risk.policy.max_account_exposure_pct ?? 90}%</strong>
              <span>Cash buffer</span>
              <strong>{data?.risk.policy.min_cash_buffer_pct ?? 10}%</strong>
              <span>Single leveraged ETF</span>
              <strong>{data?.risk.policy.max_single_leveraged_inverse_pct ?? 7}%</strong>
            </div>
          </article>

          <article className="panel">
            <div className="panel-header compact">
              <h2>Execution Mode</h2>
              <Icon name="bolt" />
            </div>
            <ul className="check-list">
              <li>
                <Icon name="check" />
                Marketable limit orders only
              </li>
              <li>
                <Icon name="check" />
                Telegram approval required
              </li>
              <li>
                <Icon name="check" />
                Risk exits may run automatically
              </li>
            </ul>
            <div className="session-box">
              <span>Next regular close</span>
              <strong>{formatDateTime(data?.market.nextCloseUtc)}</strong>
              <span>Next regular open</span>
              <strong>{formatDateTime(data?.market.nextOpenUtc)}</strong>
            </div>
            <p className="timestamp">Last updated: {lastUpdated}</p>
          </article>
        </section>

        <section className="signals-grid">
          <article className="panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Signal engine</p>
                <h2>Latest Candidates</h2>
              </div>
              <button
                className="text-button"
                disabled={isScanningSignals}
                onClick={() => void handleSignalScan()}
                type="button"
              >
                <Icon name="refresh" />
                {isScanningSignals ? "Scanning" : "Scan"}
              </button>
            </div>
            <div className="signal-list">
              {data?.signals.items.length ? (
                data.signals.items.map((signal) => (
                  <button
                    className={
                      selectedSignal?.signalId === signal.signalId
                        ? "signal-row active"
                        : "signal-row"
                    }
                    key={signal.signalId}
                    onClick={() => setSelectedSignalId(signal.signalId)}
                    type="button"
                  >
                    <span>{signal.symbol}</span>
                    <span>{signal.strategy.replaceAll("_", " ")}</span>
                    <span>{formatPercent(signal.confidence)}</span>
                    <span>{signal.regime.state ?? "unknown"}</span>
                    <span>{formatDateTime(signal.generatedAt)}</span>
                  </button>
                ))
              ) : (
                <div className="empty-state">No stored signal candidates.</div>
              )}
            </div>
          </article>

          <article className="panel">
            <div className="panel-header compact">
              <h2>Signal Detail</h2>
              <Icon name="bolt" />
            </div>
            {selectedSignal ? (
              <div className="signal-detail">
                <div className="panel-actions">
                  <button
                    className="text-button"
                    disabled={isGeneratingTradeReport}
                    onClick={() => void handleTradeReport()}
                    type="button"
                  >
                    <Icon name="bolt" />
                    {isGeneratingTradeReport ? "Explaining" : "Explain"}
                  </button>
                </div>
                <div className="signal-detail-top">
                  <strong>{selectedSignal.symbol}</strong>
                  <span>{selectedSignal.strategy.replaceAll("_", " ")}</span>
                </div>
                <div className="policy-list">
                  <span>Action</span>
                  <strong>{selectedSignal.action}</strong>
                  <span>Confidence</span>
                  <strong>{formatPercent(selectedSignal.confidence)}</strong>
                  <span>Target Weight</span>
                  <strong>{formatPercent(selectedSignal.targetWeight)}</strong>
                  <span>Horizon</span>
                  <strong>{selectedSignal.horizon.replaceAll("_", " ")}</strong>
                  <span>Expires</span>
                  <strong>{formatDateTime(selectedSignal.expiresAt)}</strong>
                </div>
                <p>{selectedSignal.rationale}</p>
                <div className="signal-meta-grid">
                  <span>RSI 14</span>
                  <strong>{formatNumber(selectedSignal.indicators.rsi14)}</strong>
                  <span>ROC 20</span>
                  <strong>{formatNumber(selectedSignal.indicators.roc20)}</strong>
                  <span>MACD Hist</span>
                  <strong>{formatNumber(selectedSignal.indicators.macd_hist)}</strong>
                  <span>Realized Vol 20</span>
                  <strong>{formatPercent(selectedSignal.indicators.realized_vol20)}</strong>
                  <span>ATR 14 %</span>
                  <strong>{formatPercent(selectedSignal.indicators.atr14_pct)}</strong>
                  <span>Regime</span>
                  <strong>{selectedSignal.regime.state ?? "unknown"}</strong>
                </div>
                <div className="rejection-list">
                  <span>Invalidation</span>
                  <small>{selectedSignal.invalidation}</small>
                  <small>{selectedSignal.regime.reason ?? "No regime note."}</small>
                </div>
                {selectedSignalReport ? (
                  <div className="report-card">
                    <div className="report-header">
                      <strong>Trade Explanation</strong>
                      <span className={selectedSignalReport.fallback_used ? "report-badge fallback" : "report-badge"}>
                        {selectedSignalReport.status}
                      </span>
                    </div>
                    <p>{selectedSignalReport.report.summary}</p>
                    <div className="report-grid">
                      <span>Setup</span>
                      <strong>{selectedSignalReport.report.setup ?? "N/A"}</strong>
                      <span>Confirmations</span>
                      <strong>
                        {(selectedSignalReport.report.confirmations ?? []).join(" | ") || "N/A"}
                      </strong>
                      <span>Risk flags</span>
                      <strong>
                        {(selectedSignalReport.report.risk_flags ?? []).join(" | ") || "None"}
                      </strong>
                      <span>Uncertainty</span>
                      <strong>{selectedSignalReport.report.uncertainty ?? "N/A"}</strong>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="empty-state">Select a candidate to inspect its signal details.</div>
            )}
          </article>
        </section>
      </section>
    </main>
  );
}

export default App;
