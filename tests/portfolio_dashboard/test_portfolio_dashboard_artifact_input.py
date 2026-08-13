import sys
import unittest
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from portfolio_dashboard import PortfolioArtifactInputRequest
from portfolio_dashboard import PortfolioArtifactInputErrorCode
from portfolio_dashboard import PortfolioRiskDashboardProjection
from portfolio_dashboard import build_portfolio_dashboard_input
from risk import PortfolioPosition
from risk import RiskAssessment
from risk import RiskArtifactGenerator
from risk import RiskCategory
from risk import RiskContext
from risk import RiskSeverity
from risk import RiskSignal
from risk_monitoring import AlertCandidate
from risk_monitoring import AlertLevel
from risk_monitoring import AlertType
from risk_monitoring import MonitoringState
from risk_monitoring import RiskMonitoringArtifactGenerator
from risk_monitoring import RiskMonitoringContext
from risk_monitoring import RiskMonitoringEvent


class PortfolioDashboardArtifactInputTestCase(unittest.TestCase):

    def created_at(self, hour=12):
        return datetime(2026, 8, 13, hour, 0, tzinfo=UTC)

    def risk_context(self, symbol="2330.TW"):
        return RiskContext(
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            analysis_date=date(2026, 8, 13),
            feature_version="feature_set_v1",
            model_version="baseline_model_v1",
            calculation_id=f"risk_calc_{symbol}",
        )

    def monitoring_context(self, symbol="2330.TW", source_artifact_id="risk_artifact_001"):
        return RiskMonitoringContext(
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            monitoring_date=date(2026, 8, 13),
            source_risk_artifact_id=source_artifact_id,
            risk_artifact_checksum=f"{source_artifact_id}_checksum",
            monitoring_policy_version="policy_v1",
            calculation_id=f"monitoring_calc_{symbol}",
        )

    def risk_artifact(self, *, symbol="2330.TW", artifact_id="risk_artifact_001", severity=RiskSeverity.HIGH):
        signal = RiskSignal(
            risk_id=f"TECH_RISK_{symbol}",
            symbol=symbol,
            category=RiskCategory.TECHNICAL,
            severity=severity,
            trigger_reason="synthetic risk review metadata",
            created_at=self.created_at(),
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            signals=(signal,),
            assessment_date=date(2026, 8, 13),
        )
        return RiskArtifactGenerator().generate(
            artifact_id=artifact_id,
            position=PortfolioPosition(
                symbol=symbol,
                shares=Decimal("10"),
                average_cost=Decimal("650.00"),
                holding_type="whole_share",
                acquisition_date=date(2026, 1, 5),
                currency="TWD",
            ),
            context=self.risk_context(symbol),
            assessment=assessment,
            created_at=self.created_at(),
        )

    def event(self, *, symbol="2330.TW", event_id="event_001", severity=RiskSeverity.HIGH):
        return RiskMonitoringEvent(
            event_id=event_id,
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            source_risk_id=f"TECH_RISK_{symbol}",
            risk_category=RiskCategory.TECHNICAL,
            risk_severity=severity,
            monitoring_state=MonitoringState.REVIEW_REQUIRED,
            reason="synthetic risk review metadata",
            created_at=self.created_at(),
        )

    def alert(self, *, symbol="2330.TW", alert_id="alert_001", event_id="event_001"):
        return AlertCandidate(
            alert_id=alert_id,
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            alert_level=AlertLevel.REVIEW,
            alert_type=AlertType.RISK_REVIEW,
            reason="synthetic review metadata",
            source_event_ids=(event_id,),
            created_at=self.created_at(),
        )

    def artifact(
        self,
        *,
        symbol="2330.TW",
        artifact_id="monitoring_artifact_001",
        source_artifact_id="risk_artifact_001",
        severity=RiskSeverity.HIGH,
        event_id="event_001",
        alert_id="alert_001",
        with_alert=True,
        hour=12,
    ):
        risk_artifact = self.risk_artifact(
            symbol=symbol,
            artifact_id=source_artifact_id,
            severity=severity,
        )
        events = (self.event(symbol=symbol, event_id=event_id, severity=severity),)
        alerts = (self.alert(symbol=symbol, alert_id=alert_id, event_id=event_id),) if with_alert else ()
        return RiskMonitoringArtifactGenerator().generate(
            artifact_id=artifact_id,
            risk_artifact=risk_artifact,
            context=self.monitoring_context(symbol=symbol, source_artifact_id=source_artifact_id),
            monitoring_state=MonitoringState.REVIEW_REQUIRED,
            events=events,
            alert_candidates=alerts,
            created_at=self.created_at(hour),
            checksum=f"{artifact_id}_checksum",
        )

    def build_result(self, artifacts):
        return build_portfolio_dashboard_input(PortfolioArtifactInputRequest(artifacts=artifacts))

    def build_result_with_reference_time(self, artifacts, *, stale_warning_days=None):
        return build_portfolio_dashboard_input(
            PortfolioArtifactInputRequest(
                artifacts=artifacts,
                reference_time=self.created_at(18),
                stale_warning_days=stale_warning_days,
            )
        )

    def test_valid_artifact_tuple_returns_success_result(self):
        result = self.build_result((self.artifact(),))

        self.assertTrue(result.success)
        self.assertIsInstance(result.projection, PortfolioRiskDashboardProjection)
        self.assertIsNone(result.validation_error)
        self.assertIsNone(result.validation_error_code)
        self.assertEqual(result.warning_metadata["artifact_count"], 1)
        self.assertFalse(result.warning_metadata["stale_warning"])

    def test_valid_tuple_returns_dashboard_projection(self):
        result = self.build_result((self.artifact(symbol="2330.TW"),))

        self.assertEqual(result.projection.overview.artifact_count, 1)
        self.assertEqual(result.projection.positions[0].symbol, "2330.TW")

    def test_empty_tuple_returns_empty_projection(self):
        result = self.build_result(())

        self.assertTrue(result.success)
        self.assertEqual(result.projection.overview.artifact_count, 0)
        self.assertEqual(result.projection.positions, ())

    def test_original_artifacts_are_not_mutated(self):
        artifact = self.artifact()
        original_events = artifact.events
        original_alerts = artifact.alert_candidates

        result = self.build_result((artifact,))

        self.assertTrue(result.success)
        self.assertIs(artifact.events, original_events)
        self.assertIs(artifact.alert_candidates, original_alerts)
        self.assertEqual(artifact.artifact_id, "monitoring_artifact_001")

    def test_duplicate_artifact_id_returns_structured_validation_error(self):
        artifact = self.artifact(artifact_id="duplicate_artifact")
        duplicate = self.artifact(
            symbol="2454.TW",
            artifact_id="duplicate_artifact",
            source_artifact_id="risk_2454",
            event_id="event_2454",
            alert_id="alert_2454",
        )

        result = self.build_result((artifact, duplicate))

        self.assertFalse(result.success)
        self.assertIsNone(result.projection)
        self.assertIn("duplicate artifact_id", result.validation_error)
        self.assertEqual(result.validation_error_code, PortfolioArtifactInputErrorCode.DUPLICATE_ARTIFACT)

    def test_lineage_mismatch_returns_structured_validation_error(self):
        artifact = self.artifact()
        bad_artifact = replace(artifact, lineage={**artifact.lineage, "risk_artifact_id": "different_risk"})

        result = self.build_result((bad_artifact,))

        self.assertFalse(result.success)
        self.assertIn("lineage risk artifact mismatch", result.validation_error)
        self.assertEqual(result.validation_error_code, PortfolioArtifactInputErrorCode.LINEAGE_MISMATCH)

    def test_checksum_mismatch_returns_structured_validation_error(self):
        artifact = self.artifact()
        bad_artifact = replace(artifact, lineage={**artifact.lineage, "risk_artifact_checksum": "bad_checksum"})

        result = self.build_result((bad_artifact,))

        self.assertFalse(result.success)
        self.assertIn("lineage checksum mismatch", result.validation_error)
        self.assertEqual(result.validation_error_code, PortfolioArtifactInputErrorCode.CHECKSUM_MISMATCH)

    def test_incompatible_artifact_returns_structured_validation_error(self):
        result = self.build_result((SimpleNamespace(artifact_id="not_enough"),))

        self.assertFalse(result.success)
        self.assertIn("missing required dashboard fields", result.validation_error)
        self.assertEqual(result.validation_error_code, PortfolioArtifactInputErrorCode.INCOMPATIBLE_ARTIFACT)

    def test_event_reference_mismatch_returns_structured_validation_error(self):
        artifact = self.artifact()
        bad_alert = AlertCandidate(
            alert_id="alert_bad",
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            alert_level=AlertLevel.REVIEW,
            alert_type=AlertType.RISK_REVIEW,
            reason="synthetic review metadata",
            source_event_ids=("missing_event",),
            created_at=self.created_at(),
        )
        bad_artifact = replace(
            artifact,
            alert_candidates=(bad_alert,),
            calculation_metadata={**artifact.calculation_metadata, "alert_candidate_count": 1},
        )

        result = self.build_result((bad_artifact,))

        self.assertFalse(result.success)
        self.assertIn("unknown monitoring event", result.validation_error)
        self.assertEqual(result.validation_error_code, PortfolioArtifactInputErrorCode.EVENT_REFERENCE_MISMATCH)

    def test_forbidden_wording_returns_structured_validation_error(self):
        bad_event = RiskMonitoringEvent(
            event_id="event_bad",
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            source_risk_id="TECH_RISK_2330.TW",
            risk_category=RiskCategory.TECHNICAL,
            risk_severity=RiskSeverity.HIGH,
            monitoring_state=MonitoringState.REVIEW_REQUIRED,
            reason="synthetic buy wording should fail",
            created_at=self.created_at(),
        )
        artifact = self.artifact(with_alert=False)
        bad_artifact = replace(
            artifact,
            events=(bad_event,),
            calculation_metadata={**artifact.calculation_metadata, "event_count": 1, "alert_candidate_count": 0},
        )

        result = self.build_result((bad_artifact,))

        self.assertFalse(result.success)
        self.assertIn("forbidden term", result.validation_error)
        self.assertEqual(result.validation_error_code, PortfolioArtifactInputErrorCode.FORBIDDEN_WORDING)

    def test_deterministic_projection_result(self):
        result = self.build_result(
            (
                self.artifact(symbol="2454.TW", artifact_id="monitoring_b", source_artifact_id="risk_b", event_id="event_b", alert_id="alert_b"),
                self.artifact(symbol="2330.TW", artifact_id="monitoring_a", source_artifact_id="risk_a", event_id="event_a", alert_id="alert_a"),
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(tuple(row.symbol for row in result.projection.positions), ("2330.TW", "2454.TW"))
        self.assertEqual(tuple(row.event_id for row in result.projection.risk_event_rows), ("event_a", "event_b"))

    def test_warning_metadata_does_not_make_success_false(self):
        result = self.build_result_with_reference_time((self.artifact(),))

        self.assertTrue(result.success)
        self.assertEqual(result.warning_metadata["reference_time"], "2026-08-13T18:00:00+00:00")
        self.assertEqual(result.warning_metadata["latest_created_at"], "2026-08-13T12:00:00+00:00")
        self.assertEqual(result.warning_metadata["oldest_created_at"], "2026-08-13T12:00:00+00:00")
        self.assertFalse(result.warning_metadata["stale_warning"])

    def test_stale_metadata_warning_does_not_reject_artifact(self):
        artifact = replace(
            self.artifact(artifact_id="old_artifact", hour=1),
            created_at=datetime(2026, 8, 12, 1, 0, tzinfo=UTC),
        )
        result = self.build_result_with_reference_time((artifact,), stale_warning_days=0)

        self.assertTrue(result.success)
        self.assertTrue(result.warning_metadata["stale_warning"])
        self.assertEqual(result.warning_metadata["stale_artifact_ids"], ("old_artifact",))

    def test_reference_time_age_metadata_is_deterministic(self):
        first = self.artifact(artifact_id="artifact_early", source_artifact_id="risk_early", event_id="event_early", alert_id="alert_early", hour=1)
        second = self.artifact(symbol="2454.TW", artifact_id="artifact_late", source_artifact_id="risk_late", event_id="event_late", alert_id="alert_late", hour=17)

        result = self.build_result_with_reference_time((second, first))

        self.assertTrue(result.success)
        self.assertEqual(result.warning_metadata["oldest_created_at"], "2026-08-13T01:00:00+00:00")
        self.assertEqual(result.warning_metadata["latest_created_at"], "2026-08-13T17:00:00+00:00")
        self.assertEqual(result.warning_metadata["max_artifact_age_days"], 0)
        self.assertEqual(result.warning_metadata["min_artifact_age_days"], 0)

    def test_same_symbol_multiple_artifacts_are_deterministic_not_selected(self):
        first = self.artifact(
            symbol="2330.TW",
            artifact_id="monitoring_2330_a",
            source_artifact_id="risk_2330_a",
            event_id="event_2330_a",
            alert_id="alert_2330_a",
            hour=17,
        )
        second = self.artifact(
            symbol="2330.TW",
            artifact_id="monitoring_2330_b",
            source_artifact_id="risk_2330_b",
            event_id="event_2330_b",
            alert_id="alert_2330_b",
            hour=1,
        )

        result = self.build_result((second, first))

        self.assertTrue(result.success)
        self.assertEqual(
            tuple(row.artifact_id for row in result.projection.positions),
            ("monitoring_2330_a", "monitoring_2330_b"),
        )
        self.assertEqual(result.projection.overview.artifact_count, 2)

    def test_artifact_input_module_does_not_import_runtime_boundaries(self):
        source = (SRC_PATH / "portfolio_dashboard" / "artifact_input.py").read_text()

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
            "RiskArtifactGenerator",
            "RiskMonitoringArtifactGenerator",
            "open(",
            "json",
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
