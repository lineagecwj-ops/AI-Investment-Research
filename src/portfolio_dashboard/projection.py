from collections import Counter

from risk_monitoring.monitoring_artifact import RiskMonitoringArtifact

from portfolio_dashboard.formatter import format_optional_checksum
from portfolio_dashboard.formatter import format_value
from portfolio_dashboard.validation import PortfolioDashboardValidator
from portfolio_dashboard.view_model import AlertCandidateRow
from portfolio_dashboard.view_model import ArtifactLineageRow
from portfolio_dashboard.view_model import DashboardCount
from portfolio_dashboard.view_model import PortfolioOverviewProjection
from portfolio_dashboard.view_model import PortfolioRiskDashboardProjection
from portfolio_dashboard.view_model import PositionRiskProjection
from portfolio_dashboard.view_model import RiskEventRow


def build_portfolio_risk_dashboard_projection(
    artifacts: tuple[RiskMonitoringArtifact, ...],
    validator: PortfolioDashboardValidator | None = None,
) -> PortfolioRiskDashboardProjection:
    active_validator = validator or PortfolioDashboardValidator()
    active_validator.validate_artifacts(artifacts)

    ordered_artifacts = _sort_artifacts(artifacts)
    return PortfolioRiskDashboardProjection(
        overview=build_portfolio_overview_projection(ordered_artifacts),
        positions=build_position_risk_projections(ordered_artifacts),
        risk_event_rows=build_risk_event_rows(ordered_artifacts),
        alert_candidate_rows=build_alert_candidate_rows(ordered_artifacts),
        artifact_lineage_rows=build_artifact_lineage_rows(ordered_artifacts),
    )


def build_portfolio_overview_projection(
    artifacts: tuple[RiskMonitoringArtifact, ...],
) -> PortfolioOverviewProjection:
    latest_created_at = max((artifact.created_at for artifact in artifacts), default=None)
    return PortfolioOverviewProjection(
        portfolio_ids=tuple(sorted({artifact.portfolio_id for artifact in artifacts})),
        symbol_count=len({(artifact.portfolio_id, artifact.symbol) for artifact in artifacts}),
        artifact_count=len(artifacts),
        event_count=sum(len(artifact.events) for artifact in artifacts),
        alert_candidate_count=sum(len(artifact.alert_candidates) for artifact in artifacts),
        risk_level_counts=_count_values(artifact.overall_risk_level for artifact in artifacts),
        monitoring_state_counts=_count_values(format_value(artifact.monitoring_state) for artifact in artifacts),
        policy_version_counts=_count_values(artifact.policy_version for artifact in artifacts),
        latest_created_at=format_value(latest_created_at),
    )


def build_position_risk_projections(
    artifacts: tuple[RiskMonitoringArtifact, ...],
) -> tuple[PositionRiskProjection, ...]:
    rows = [
        PositionRiskProjection(
            portfolio_id=artifact.portfolio_id,
            symbol=artifact.symbol,
            artifact_id=artifact.artifact_id,
            monitoring_state=format_value(artifact.monitoring_state),
            overall_risk_level=artifact.overall_risk_level,
            event_count=len(artifact.events),
            alert_candidate_count=len(artifact.alert_candidates),
            policy_version=artifact.policy_version,
            source_risk_artifact_id=artifact.source_risk_artifact_id,
            source_risk_checksum=artifact.source_risk_checksum,
            created_at=format_value(artifact.created_at),
        )
        for artifact in artifacts
    ]
    return tuple(sorted(rows, key=lambda row: (row.portfolio_id, row.symbol, row.artifact_id)))


def build_risk_event_rows(
    artifacts: tuple[RiskMonitoringArtifact, ...],
) -> tuple[RiskEventRow, ...]:
    rows = []
    for artifact in artifacts:
        for event in artifact.events:
            rows.append(
                RiskEventRow(
                    portfolio_id=artifact.portfolio_id,
                    symbol=artifact.symbol,
                    artifact_id=artifact.artifact_id,
                    event_id=event.event_id,
                    source_risk_id=event.source_risk_id,
                    risk_category=format_value(event.risk_category),
                    risk_severity=format_value(event.risk_severity),
                    monitoring_state=format_value(event.monitoring_state),
                    reason=event.reason,
                    created_at=format_value(event.created_at),
                )
            )
    return tuple(sorted(rows, key=lambda row: (row.portfolio_id, row.symbol, row.artifact_id, row.event_id)))


def build_alert_candidate_rows(
    artifacts: tuple[RiskMonitoringArtifact, ...],
) -> tuple[AlertCandidateRow, ...]:
    rows = []
    for artifact in artifacts:
        for alert in artifact.alert_candidates:
            rows.append(
                AlertCandidateRow(
                    portfolio_id=artifact.portfolio_id,
                    symbol=artifact.symbol,
                    artifact_id=artifact.artifact_id,
                    alert_id=alert.alert_id,
                    alert_level=format_value(alert.alert_level),
                    alert_type=format_value(alert.alert_type),
                    reason=alert.reason,
                    source_event_ids=tuple(alert.source_event_ids),
                    created_at=format_value(alert.created_at),
                )
            )
    return tuple(sorted(rows, key=lambda row: (row.portfolio_id, row.symbol, row.artifact_id, row.alert_id)))


def build_artifact_lineage_rows(
    artifacts: tuple[RiskMonitoringArtifact, ...],
) -> tuple[ArtifactLineageRow, ...]:
    rows = [
        ArtifactLineageRow(
            portfolio_id=artifact.portfolio_id,
            symbol=artifact.symbol,
            artifact_id=artifact.artifact_id,
            source_risk_artifact_id=artifact.source_risk_artifact_id,
            source_risk_checksum=artifact.source_risk_checksum,
            artifact_checksum=format_optional_checksum(artifact.checksum),
            policy_version=artifact.policy_version,
            risk_artifact_id=format_value(artifact.lineage.get("risk_artifact_id")),
            risk_artifact_checksum=format_value(artifact.lineage.get("risk_artifact_checksum")),
            risk_assessment_date=format_value(artifact.lineage.get("risk_assessment_date")),
            risk_engine_feature_version=format_value(artifact.lineage.get("risk_engine_feature_version")),
            risk_engine_model_version=format_value(artifact.lineage.get("risk_engine_model_version")),
            risk_overall_level=format_value(artifact.lineage.get("risk_overall_level")),
            calculation_id=format_value(artifact.calculation_metadata.get("calculation_id")),
            created_at=format_value(artifact.created_at),
        )
        for artifact in artifacts
    ]
    return tuple(sorted(rows, key=lambda row: (row.portfolio_id, row.symbol, row.artifact_id)))


def _sort_artifacts(artifacts: tuple[RiskMonitoringArtifact, ...]) -> tuple[RiskMonitoringArtifact, ...]:
    return tuple(sorted(artifacts, key=lambda item: (item.portfolio_id, item.symbol, item.artifact_id)))


def _count_values(values) -> tuple[DashboardCount, ...]:
    counts = Counter(values)
    return tuple(DashboardCount(name=name, count=counts[name]) for name in sorted(counts))
