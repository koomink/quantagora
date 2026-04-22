from app.domain.models import Asset, AssetType, UniverseMember, UniverseVersion

LEVERAGED_INVERSE_WHITELIST = {"TQQQ", "SQQQ", "SOXL", "SOXS", "UPRO", "SPXU"}


def get_current_universe() -> UniverseVersion:
    members = [
        UniverseMember(
            rank=1,
            asset=Asset(
                symbol="SPY",
                name="SPDR S&P 500 ETF Trust",
                asset_type=AssetType.BROAD_ETF,
                exchange="NYSEARCA",
            ),
            rationale="Baseline broad-market ETF used as a liquidity and regime anchor.",
        ),
        UniverseMember(
            rank=2,
            asset=Asset(
                symbol="QQQ",
                name="Invesco QQQ Trust",
                asset_type=AssetType.BROAD_ETF,
                exchange="NASDAQ",
            ),
            rationale="Highly liquid growth benchmark for swing and medium-term signals.",
        ),
        UniverseMember(
            rank=3,
            asset=Asset(
                symbol="TQQQ",
                name="ProShares UltraPro QQQ",
                asset_type=AssetType.LEVERAGED_ETF,
                exchange="NASDAQ",
                leveraged_inverse_flag=True,
            ),
            rationale="Whitelisted leveraged ETF with strict exposure limits.",
        ),
        UniverseMember(
            rank=4,
            asset=Asset(
                symbol="SQQQ",
                name="ProShares UltraPro Short QQQ",
                asset_type=AssetType.INVERSE_ETF,
                exchange="NASDAQ",
                leveraged_inverse_flag=True,
            ),
            rationale="Whitelisted inverse ETF for risk-off exposure under strict limits.",
        ),
    ]
    return UniverseVersion(version_id="bootstrap", status="bootstrap", members=members)
