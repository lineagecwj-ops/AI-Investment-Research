import sys
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from portfolio_dashboard.formatter import contains_forbidden_wording
from portfolio_dashboard.streamlit_view import EMPTY_STATE_MESSAGE
from portfolio_dashboard.streamlit_view import READ_ONLY_CAPTION
from portfolio_dashboard.streamlit_view import VALIDATION_ERROR_TITLE
from portfolio_dashboard.streamlit_view import build_alert_candidate_table_rows
from portfolio_dashboard.streamlit_view import build_artifact_lineage_table_rows
from portfolio_dashboard.streamlit_view import build_overview_metric_rows
from portfolio_dashboard.streamlit_view import build_position_table_rows
from portfolio_dashboard.streamlit_view import build_risk_event_table_rows
from portfolio_dashboard.streamlit_view import render_warning_metadata
from portfolio_dashboard.streamlit_view import render_empty_state
from portfolio_dashboard.streamlit_view import render_portfolio_risk_dashboard
from portfolio_dashboard.streamlit_view import render_validation_error_state
from portfolio_dashboard.view_model import AlertCandidateRow
from portfolio_dashboard.view_model import ArtifactLineageRow
from portfolio_dashboard.view_model import DashboardCount
from portfolio_dashboard.view_model import PortfolioOverviewProjection
from portfolio_dashboard.view_model import PortfolioRiskDashboardProjection
from portfolio_dashboard.view_model import PositionRiskProjection
from portfolio_dashboard.view_model import RiskEventRow


class PortfolioDashboardStreamlitViewTestCase(unittest.TestCase):

    def projection(self):
        created_at = datetime(2026, 8, 13, 12, 0, tzinfo=UTC).isoformat()
        return PortfolioRiskDashboardProjection(
            overview=PortfolioOverviewProjection(
                portfolio_ids=("portfolio_synthetic_001",),
                symbol_count=1,
                artifact_count=1,
                event_count=1,
                alert_candidate_count=1,
                risk_level_counts=(DashboardCount("HIGH", 1),),
                monitoring_state_counts=(DashboardCount("REVIEW_REQUIRED", 1),),
                policy_version_counts=(DashboardCount("policy_v1", 1),),
                latest_created_at=created_at,
            ),
            positions=(
                PositionRiskProjection(
                    portfolio_id="portfolio_synthetic_001",
                    symbol="2330.TW",
                    artifact_id="monitoring_artifact_001",
                    monitoring_state="REVIEW_REQUIRED",
                    overall_risk_level="HIGH",
                    event_count=1,
                    alert_candidate_count=1,
                    policy_version="policy_v1",
                    source_risk_artifact_id="risk_artifact_001",
                    source_risk_checksum="risk_checksum_001",
                    created_at=created_at,
                ),
            ),
            risk_event_rows=(
                RiskEventRow(
                    portfolio_id="portfolio_synthetic_001",
                    symbol="2330.TW",
                    artifact_id="monitoring_artifact_001",
                    event_id="event_001",
                    source_risk_id="TECH_RISK_001",
                    risk_category="technical",
                    risk_severity="HIGH",
                    monitoring_state="REVIEW_REQUIRED",
                    reason="synthetic review metadata",
                    created_at=created_at,
                ),
            ),
            alert_candidate_rows=(
                AlertCandidateRow(
                    portfolio_id="portfolio_synthetic_001",
                    symbol="2330.TW",
                    artifact_id="monitoring_artifact_001",
                    alert_id="alert_001",
                    alert_level="REVIEW",
                    alert_type="RISK_REVIEW",
                    reason="synthetic review metadata",
                    source_event_ids=("event_001",),
                    created_at=created_at,
                ),
            ),
            artifact_lineage_rows=(
                ArtifactLineageRow(
                    portfolio_id="portfolio_synthetic_001",
                    symbol="2330.TW",
                    artifact_id="monitoring_artifact_001",
                    source_risk_artifact_id="risk_artifact_001",
                    source_risk_checksum="risk_checksum_001",
                    artifact_checksum="monitoring_checksum_001",
                    policy_version="policy_v1",
                    risk_artifact_id="risk_artifact_001",
                    risk_artifact_checksum="risk_checksum_001",
                    risk_assessment_date="2026-08-13",
                    risk_engine_feature_version="feature_set_v1",
                    risk_engine_model_version="baseline_model_v1",
                    risk_overall_level="HIGH",
                    calculation_id="monitoring_calc_001",
                    created_at=created_at,
                ),
            ),
        )

    def test_renderer_accepts_projection(self):
        projection = self.projection()

        with patch("portfolio_dashboard.streamlit_view.st") as streamlit_mock:
            streamlit_mock.columns.return_value = [streamlit_mock, streamlit_mock, streamlit_mock, streamlit_mock]
            streamlit_mock.expander.return_value.__enter__.return_value = streamlit_mock
            streamlit_mock.expander.return_value.__exit__.return_value = False

            render_portfolio_risk_dashboard(projection)

        streamlit_mock.header.assert_called_once_with("Portfolio Risk（風險檢視）")
        self.assertTrue(streamlit_mock.dataframe.called)

    def test_renderer_accepts_projection_with_warning_metadata(self):
        projection = self.projection()
        warning_metadata = {"artifact_count": 1, "stale_warning": False}

        with patch("portfolio_dashboard.streamlit_view.st") as streamlit_mock:
            streamlit_mock.columns.return_value = [streamlit_mock, streamlit_mock, streamlit_mock, streamlit_mock]
            streamlit_mock.expander.return_value.__enter__.return_value = streamlit_mock
            streamlit_mock.expander.return_value.__exit__.return_value = False

            render_portfolio_risk_dashboard(projection, warning_metadata=warning_metadata)

        streamlit_mock.header.assert_called_once_with("Portfolio Risk（風險檢視）")
        self.assertTrue(streamlit_mock.dataframe.called)

    def test_empty_state(self):
        with patch("portfolio_dashboard.streamlit_view.st") as streamlit_mock:
            render_empty_state()

        streamlit_mock.info.assert_called_once_with(EMPTY_STATE_MESSAGE)

    def test_validation_error_state(self):
        with patch("portfolio_dashboard.streamlit_view.st") as streamlit_mock:
            render_validation_error_state("synthetic validation error")

        streamlit_mock.error.assert_called_once_with(VALIDATION_ERROR_TITLE)
        streamlit_mock.caption.assert_called_once_with("synthetic validation error")

    def test_repository_error_rendering(self):
        with patch("portfolio_dashboard.streamlit_view.st") as streamlit_mock:
            render_portfolio_risk_dashboard(validation_error="synthetic repository error")

        streamlit_mock.error.assert_called_once_with(VALIDATION_ERROR_TITLE)
        streamlit_mock.caption.assert_any_call("synthetic repository error")

    def test_warning_metadata_rendering(self):
        warning_metadata = {
            "artifact_count": 1,
            "stale_warning": True,
            "stale_artifact_ids": ("artifact_a", "artifact_b"),
        }

        with patch("portfolio_dashboard.streamlit_view.st") as streamlit_mock:
            streamlit_mock.expander.return_value.__enter__.return_value = streamlit_mock
            streamlit_mock.expander.return_value.__exit__.return_value = False

            render_warning_metadata(warning_metadata)

        streamlit_mock.warning.assert_called_once_with("Portfolio Risk artifact metadata requires review.")
        self.assertTrue(streamlit_mock.dataframe.called)

    def test_table_rendering_helpers(self):
        projection = self.projection()

        overview_rows = build_overview_metric_rows(projection)
        position_rows = build_position_table_rows(projection.positions)
        event_rows = build_risk_event_table_rows(projection.risk_event_rows)
        alert_rows = build_alert_candidate_table_rows(projection.alert_candidate_rows)
        lineage_rows = build_artifact_lineage_table_rows(projection.artifact_lineage_rows)

        self.assertEqual(overview_rows[0]["Metric"], "Portfolios")
        self.assertEqual(position_rows[0]["symbol"], "2330.TW")
        self.assertEqual(event_rows[0]["event_id"], "event_001")
        self.assertEqual(alert_rows[0]["source_event_ids"], "event_001")
        self.assertEqual(lineage_rows[0]["risk_artifact_id"], "risk_artifact_001")

    def test_safe_wording(self):
        texts = (
            EMPTY_STATE_MESSAGE,
            VALIDATION_ERROR_TITLE,
            READ_ONLY_CAPTION,
            "Artifact input metadata",
            "Portfolio Risk artifact metadata requires review.",
            "Portfolio Risk（風險檢視）",
            "Position Risk",
            "Risk Events",
            "Alert Candidates",
            "Artifact Lineage",
        )

        for text in texts:
            self.assertFalse(contains_forbidden_wording(text))

    def test_portfolio_streamlit_view_does_not_import_runtime_boundaries(self):
        source = (SRC_PATH / "portfolio_dashboard" / "streamlit_view.py").read_text()

        forbidden_imports = (
            "sqlite3",
            "LiveDataStore",
            "live_data_store",
            "ResearchDataStore",
            "research_data_store",
            "swing_scanner",
            "scanner_service",
            "pdf_export",
            "yfinance",
            "RiskMonitoringEngine",
            "RiskMonitoringArtifactGenerator",
            "RiskArtifactGenerator",
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
