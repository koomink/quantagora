import { useEffect, useMemo, useState } from "react";

import {
  fetchApprovals,
  fetchMarketStatus,
  fetchPortfolioSummary,
  fetchRiskStatus,
  fetchRuntimeSettings,
  fetchUniverse,
  refreshUniverse
} from "./api";
import type {
  ApprovalList,
  MarketStatus,
  PortfolioSummary,
  RiskStatus,
  RuntimeSettings,
  UniverseVersion
} from "./types";

type DashboardData = {
  runtime: RuntimeSettings;
  market: MarketStatus;
  portfolio: PortfolioSummary;
  universe: UniverseVersion;
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

function App() {
  const [adminToken, setAdminToken] = useState(() => {
    return localStorage.getItem("quantagora.adminToken") ?? "dev-admin-token";
  });
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshingUniverse, setIsRefreshingUniverse] = useState(false);

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
      const [runtime, market, portfolio, universe, risk, approvals] = await Promise.all([
        fetchRuntimeSettings(nextToken),
        fetchMarketStatus(nextToken),
        fetchPortfolioSummary(nextToken),
        fetchUniverse(nextToken),
        fetchRiskStatus(nextToken),
        fetchApprovals(nextToken)
      ]);
      setData({ runtime, market, portfolio, universe, risk, approvals });
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

  useEffect(() => {
    void loadDashboard();
  }, []);

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
      </section>
    </main>
  );
}

export default App;
