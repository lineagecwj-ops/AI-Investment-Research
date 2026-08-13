from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardCount:
    """Display count for dashboard summary sections."""

    name: str
    count: int


@dataclass(frozen=True)
class PortfolioOverviewProjection:
    portfolio_ids: tuple[str, ...]
    symbol_count: int
    artifact_count: int
    event_count: int
    alert_candidate_count: int
    risk_level_counts: tuple[DashboardCount, ...]
    monitoring_state_counts: tuple[DashboardCount, ...]
    policy_version_counts: tuple[DashboardCount, ...]
    latest_created_at: str


@dataclass(frozen=True)
class PositionRiskProjection:
    portfolio_id: str
    symbol: str
    artifact_id: str
    monitoring_state: str
    overall_risk_level: str
    event_count: int
    alert_candidate_count: int
    policy_version: str
    source_risk_artifact_id: str
    source_risk_checksum: str
    created_at: str


@dataclass(frozen=True)
class RiskEventRow:
    portfolio_id: str
    symbol: str
    artifact_id: str
    event_id: str
    source_risk_id: str
    risk_category: str
    risk_severity: str
    monitoring_state: str
    reason: str
    created_at: str


@dataclass(frozen=True)
class AlertCandidateRow:
    portfolio_id: str
    symbol: str
    artifact_id: str
    alert_id: str
    alert_level: str
    alert_type: str
    reason: str
    source_event_ids: tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class ArtifactLineageRow:
    portfolio_id: str
    symbol: str
    artifact_id: str
    source_risk_artifact_id: str
    source_risk_checksum: str
    artifact_checksum: str
    policy_version: str
    risk_artifact_id: str
    risk_artifact_checksum: str
    risk_assessment_date: str
    risk_engine_feature_version: str
    risk_engine_model_version: str
    risk_overall_level: str
    calculation_id: str
    created_at: str


@dataclass(frozen=True)
class PortfolioRiskDashboardProjection:
    overview: PortfolioOverviewProjection
    positions: tuple[PositionRiskProjection, ...]
    risk_event_rows: tuple[RiskEventRow, ...]
    alert_candidate_rows: tuple[AlertCandidateRow, ...]
    artifact_lineage_rows: tuple[ArtifactLineageRow, ...]
