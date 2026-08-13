from dataclasses import asdict

import streamlit as st

from portfolio_dashboard.view_model import AlertCandidateRow
from portfolio_dashboard.view_model import ArtifactLineageRow
from portfolio_dashboard.view_model import PortfolioRiskDashboardProjection
from portfolio_dashboard.view_model import PositionRiskProjection
from portfolio_dashboard.view_model import RiskEventRow


EMPTY_STATE_MESSAGE = "尚未載入 Portfolio Risk Monitoring Artifact。"
VALIDATION_ERROR_TITLE = "Portfolio Risk artifact validation failed."
READ_ONLY_CAPTION = (
    "Read-only artifact view. This page displays existing monitoring metadata only."
)


def render_portfolio_risk_dashboard(
    projection: PortfolioRiskDashboardProjection | None = None,
    validation_error: Exception | str | None = None,
) -> None:
    st.header("Portfolio Risk（風險檢視）")
    st.caption(READ_ONLY_CAPTION)

    if validation_error is not None:
        render_validation_error_state(validation_error)
        return
    if projection is None or projection.overview.artifact_count == 0:
        render_empty_state()
        return

    render_overview(projection)
    render_position_risk_table(projection)
    render_risk_event_table(projection)
    render_alert_candidate_table(projection)
    render_artifact_lineage_table(projection)


def render_empty_state() -> None:
    st.info(EMPTY_STATE_MESSAGE)


def render_validation_error_state(error: Exception | str) -> None:
    st.error(VALIDATION_ERROR_TITLE)
    st.caption(str(error))


def render_overview(projection: PortfolioRiskDashboardProjection) -> None:
    rows = build_overview_metric_rows(projection)
    metric_columns = st.columns(4)
    for index, row in enumerate(rows[:4]):
        metric_columns[index].metric(row["Metric"], row["Value"])

    with st.expander("Overview metadata", expanded=False):
        st.dataframe(rows, width="stretch", hide_index=True)
        st.markdown("#### Risk Level Counts")
        st.dataframe(build_count_rows(projection.overview.risk_level_counts), width="stretch", hide_index=True)
        st.markdown("#### Monitoring State Counts")
        st.dataframe(build_count_rows(projection.overview.monitoring_state_counts), width="stretch", hide_index=True)
        st.markdown("#### Policy Version Counts")
        st.dataframe(build_count_rows(projection.overview.policy_version_counts), width="stretch", hide_index=True)


def render_position_risk_table(projection: PortfolioRiskDashboardProjection) -> None:
    st.markdown("### Position Risk")
    rows = build_position_table_rows(projection.positions)
    _render_table_or_empty(rows, "No position risk rows.")


def render_risk_event_table(projection: PortfolioRiskDashboardProjection) -> None:
    st.markdown("### Risk Events")
    rows = build_risk_event_table_rows(projection.risk_event_rows)
    _render_table_or_empty(rows, "No risk event rows.")


def render_alert_candidate_table(projection: PortfolioRiskDashboardProjection) -> None:
    st.markdown("### Alert Candidates")
    rows = build_alert_candidate_table_rows(projection.alert_candidate_rows)
    _render_table_or_empty(rows, "No alert candidate rows.")


def render_artifact_lineage_table(projection: PortfolioRiskDashboardProjection) -> None:
    st.markdown("### Artifact Lineage")
    rows = build_artifact_lineage_table_rows(projection.artifact_lineage_rows)
    _render_table_or_empty(rows, "No artifact lineage rows.")


def build_overview_metric_rows(projection: PortfolioRiskDashboardProjection) -> list[dict[str, object]]:
    overview = projection.overview
    return [
        {"Metric": "Portfolios", "Value": ", ".join(overview.portfolio_ids) or "N/A"},
        {"Metric": "Symbols", "Value": overview.symbol_count},
        {"Metric": "Artifacts", "Value": overview.artifact_count},
        {"Metric": "Events", "Value": overview.event_count},
        {"Metric": "Alert Candidates", "Value": overview.alert_candidate_count},
        {"Metric": "Latest Created At", "Value": overview.latest_created_at},
    ]


def build_count_rows(counts) -> list[dict[str, object]]:
    return [{"Name": item.name, "Count": item.count} for item in counts]


def build_position_table_rows(rows: tuple[PositionRiskProjection, ...]) -> list[dict[str, object]]:
    return [asdict(row) for row in rows]


def build_risk_event_table_rows(rows: tuple[RiskEventRow, ...]) -> list[dict[str, object]]:
    return [asdict(row) for row in rows]


def build_alert_candidate_table_rows(rows: tuple[AlertCandidateRow, ...]) -> list[dict[str, object]]:
    return [
        {
            **asdict(row),
            "source_event_ids": ", ".join(row.source_event_ids),
        }
        for row in rows
    ]


def build_artifact_lineage_table_rows(rows: tuple[ArtifactLineageRow, ...]) -> list[dict[str, object]]:
    return [asdict(row) for row in rows]


def _render_table_or_empty(rows: list[dict[str, object]], empty_message: str) -> None:
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info(empty_message)
