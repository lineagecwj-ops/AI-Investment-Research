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

from portfolio_dashboard import PortfolioDashboardValidationError
from portfolio_dashboard import build_portfolio_risk_dashboard_projection
from portfolio_dashboard.formatter import EMPTY_DISPLAY
from portfolio_dashboard.formatter import format_checksum
from portfolio_dashboard.formatter import format_datetime
from portfolio_dashboard.formatter import format_enum
from portfolio_dashboard.formatter import validate_no_forbidden_wording
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


class PortfolioDashboardProjectionTestCase(unittest.TestCase):

    def created_at(self, hour=12):
        return datetime(2026, 8, 13, hour, 0, tzinfo=UTC)

    def risk_context(self, symbol="2330.TW", calculation_id="risk_calc_001"):
        return RiskContext(
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            analysis_date=date(2026, 8, 13),
            feature_version="feature_set_v1",
            model_version="baseline_model_v1",
            calculation_id=calculation_id,
        )

    def monitoring_context(self, symbol="2330.TW", source_artifact_id="risk_artifact_001", calculation_id="monitoring_calc_001"):
        return RiskMonitoringContext(
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            monitoring_date=date(2026, 8, 13),
            source_risk_artifact_id=source_artifact_id,
            risk_artifact_checksum=f"{source_artifact_id}_checksum",
            monitoring_policy_version="policy_v1",
            calculation_id=calculation_id,
        )

    def risk_artifact(self, *, symbol="2330.TW", artifact_id="risk_artifact_001", severity=RiskSeverity.HIGH):
        created_at = self.created_at()
        position = PortfolioPosition(
            symbol=symbol,
            shares=Decimal("10"),
            average_cost=Decimal("650.00"),
            holding_type="whole_share",
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )
        signal = RiskSignal(
            risk_id=f"TECH_RISK_{symbol}",
            symbol=symbol,
            category=RiskCategory.TECHNICAL,
            severity=severity,
            trigger_reason="synthetic risk review metadata",
            created_at=created_at,
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            signals=(signal,),
            assessment_date=date(2026, 8, 13),
        )
        return RiskArtifactGenerator().generate(
            artifact_id=artifact_id,
            position=position,
            context=self.risk_context(symbol=symbol),
            assessment=assessment,
            created_at=created_at,
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
        state=MonitoringState.REVIEW_REQUIRED,
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
        context = self.monitoring_context(
            symbol=symbol,
            source_artifact_id=source_artifact_id,
            calculation_id=f"monitoring_calc_{symbol}",
        )
        events = (self.event(symbol=symbol, event_id=event_id, severity=severity),)
        alerts = (self.alert(symbol=symbol, alert_id=alert_id, event_id=event_id),) if with_alert else ()
        artifact = RiskMonitoringArtifactGenerator().generate(
            artifact_id=artifact_id,
            risk_artifact=risk_artifact,
            context=context,
            monitoring_state=state,
            events=events,
            alert_candidates=alerts,
            created_at=self.created_at(hour),
            checksum=f"{artifact_id}_checksum",
        )
        return artifact

    def test_builds_dashboard_projection_from_monitoring_artifacts(self):
        projection = build_portfolio_risk_dashboard_projection(
            (
                self.artifact(symbol="2330.TW", artifact_id="monitoring_b", source_artifact_id="risk_b", event_id="event_b", alert_id="alert_b"),
                self.artifact(symbol="2454.TW", artifact_id="monitoring_a", source_artifact_id="risk_a", event_id="event_a", alert_id="alert_a", severity=RiskSeverity.MEDIUM, state=MonitoringState.WATCH, with_alert=False, hour=13),
            )
        )

        self.assertEqual(projection.overview.portfolio_ids, ("portfolio_synthetic_001",))
        self.assertEqual(projection.overview.symbol_count, 2)
        self.assertEqual(projection.overview.artifact_count, 2)
        self.assertEqual(projection.overview.event_count, 2)
        self.assertEqual(projection.overview.alert_candidate_count, 1)
        self.assertEqual(projection.overview.latest_created_at, "2026-08-13T13:00:00+00:00")
        self.assertEqual(tuple(row.symbol for row in projection.positions), ("2330.TW", "2454.TW"))
        self.assertEqual(tuple(row.event_id for row in projection.risk_event_rows), ("event_b", "event_a"))
        self.assertEqual(tuple(row.alert_id for row in projection.alert_candidate_rows), ("alert_b",))

    def test_display_counts_are_grouped_from_artifact_metadata(self):
        projection = build_portfolio_risk_dashboard_projection(
            (
                self.artifact(symbol="2330.TW", artifact_id="monitoring_high", source_artifact_id="risk_high", event_id="event_high", alert_id="alert_high"),
                self.artifact(symbol="2454.TW", artifact_id="monitoring_medium", source_artifact_id="risk_medium", event_id="event_medium", alert_id="alert_medium", severity=RiskSeverity.MEDIUM, state=MonitoringState.WATCH, with_alert=False),
            )
        )

        risk_counts = {item.name: item.count for item in projection.overview.risk_level_counts}
        state_counts = {item.name: item.count for item in projection.overview.monitoring_state_counts}

        self.assertEqual(risk_counts, {"HIGH": 1, "MEDIUM": 1})
        self.assertEqual(state_counts, {"REVIEW_REQUIRED": 1, "WATCH": 1})

    def test_lineage_rows_preserve_source_metadata(self):
        projection = build_portfolio_risk_dashboard_projection(
            (self.artifact(artifact_id="monitoring_lineage", source_artifact_id="risk_lineage"),)
        )

        row = projection.artifact_lineage_rows[0]

        self.assertEqual(row.artifact_id, "monitoring_lineage")
        self.assertEqual(row.source_risk_artifact_id, "risk_lineage")
        self.assertEqual(row.source_risk_checksum, "risk_lineage_checksum")
        self.assertEqual(row.risk_artifact_id, "risk_lineage")
        self.assertEqual(row.risk_artifact_checksum, "risk_lineage_checksum")
        self.assertEqual(row.risk_engine_feature_version, "feature_set_v1")
        self.assertEqual(row.risk_engine_model_version, "baseline_model_v1")

    def test_empty_artifact_tuple_builds_empty_projection(self):
        projection = build_portfolio_risk_dashboard_projection(())

        self.assertEqual(projection.overview.portfolio_ids, ())
        self.assertEqual(projection.overview.symbol_count, 0)
        self.assertEqual(projection.overview.artifact_count, 0)
        self.assertEqual(projection.overview.event_count, 0)
        self.assertEqual(projection.overview.alert_candidate_count, 0)
        self.assertEqual(projection.overview.latest_created_at, EMPTY_DISPLAY)
        self.assertEqual(projection.positions, ())
        self.assertEqual(projection.risk_event_rows, ())
        self.assertEqual(projection.alert_candidate_rows, ())
        self.assertEqual(projection.artifact_lineage_rows, ())

    def test_multiple_symbols_sort_deterministically_by_portfolio_symbol_artifact(self):
        projection = build_portfolio_risk_dashboard_projection(
            (
                self.artifact(symbol="2454.TW", artifact_id="monitoring_2454_b", source_artifact_id="risk_2454_b", event_id="event_2454_b", alert_id="alert_2454_b"),
                self.artifact(symbol="2330.TW", artifact_id="monitoring_2330", source_artifact_id="risk_2330", event_id="event_2330", alert_id="alert_2330"),
                self.artifact(symbol="2454.TW", artifact_id="monitoring_2454_a", source_artifact_id="risk_2454_a", event_id="event_2454_a", alert_id="alert_2454_a"),
            )
        )

        self.assertEqual(
            tuple((row.symbol, row.artifact_id) for row in projection.positions),
            (
                ("2330.TW", "monitoring_2330"),
                ("2454.TW", "monitoring_2454_a"),
                ("2454.TW", "monitoring_2454_b"),
            ),
        )

    def test_formatter_safety_helpers(self):
        now = self.created_at()

        self.assertEqual(format_enum(MonitoringState.REVIEW_REQUIRED), "REVIEW_REQUIRED")
        self.assertEqual(format_datetime(now), "2026-08-13T12:00:00+00:00")
        self.assertEqual(format_checksum("checksum_001"), "checksum_001")
        self.assertEqual(format_checksum(None), EMPTY_DISPLAY)

        with self.assertRaisesRegex(ValueError, "forbidden term"):
            validate_no_forbidden_wording("這不是建議買的欄位")

    def test_rejects_non_tuple_input(self):
        with self.assertRaisesRegex(PortfolioDashboardValidationError, "tuple"):
            build_portfolio_risk_dashboard_projection([self.artifact()])

    def test_rejects_duplicate_artifact_ids(self):
        first = self.artifact(artifact_id="duplicate_artifact")
        second = self.artifact(
            symbol="2454.TW",
            artifact_id="duplicate_artifact",
            source_artifact_id="risk_duplicate_2454",
            event_id="event_duplicate_2454",
            alert_id="alert_duplicate_2454",
        )

        with self.assertRaisesRegex(PortfolioDashboardValidationError, "duplicate artifact_id"):
            build_portfolio_risk_dashboard_projection((first, second))

    def test_rejects_incompatible_artifact_missing_required_fields(self):
        incompatible = SimpleNamespace(
            artifact_id="not_a_monitoring_artifact",
            portfolio_id="portfolio_synthetic_001",
        )

        with self.assertRaisesRegex(PortfolioDashboardValidationError, "missing required dashboard fields"):
            build_portfolio_risk_dashboard_projection((incompatible,))

    def test_rejects_lineage_missing_required_fields(self):
        artifact = self.artifact()
        bad_artifact = replace(
            artifact,
            lineage={
                "risk_artifact_id": artifact.source_risk_artifact_id,
                "risk_artifact_checksum": artifact.source_risk_checksum,
            },
        )

        with self.assertRaisesRegex(PortfolioDashboardValidationError, "lineage missing required fields"):
            build_portfolio_risk_dashboard_projection((bad_artifact,))

    def test_rejects_lineage_checksum_mismatch(self):
        artifact = self.artifact()
        bad_artifact = replace(
            artifact,
            lineage={
                **artifact.lineage,
                "risk_artifact_checksum": "different_checksum",
            },
        )

        with self.assertRaisesRegex(PortfolioDashboardValidationError, "lineage checksum mismatch"):
            build_portfolio_risk_dashboard_projection((bad_artifact,))

    def test_rejects_empty_artifact_checksum_when_provided(self):
        artifact = replace(self.artifact(), checksum="")

        with self.assertRaisesRegex(PortfolioDashboardValidationError, "checksum cannot be empty"):
            build_portfolio_risk_dashboard_projection((artifact,))

    def test_rejects_alert_candidate_with_unknown_event_reference(self):
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
            calculation_metadata={
                **artifact.calculation_metadata,
                "alert_candidate_count": 1,
            },
        )

        with self.assertRaisesRegex(PortfolioDashboardValidationError, "unknown monitoring event"):
            build_portfolio_risk_dashboard_projection((bad_artifact,))

    def test_rejects_forbidden_trading_semantics(self):
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
            calculation_metadata={
                **artifact.calculation_metadata,
                "event_count": 1,
                "alert_candidate_count": 0,
            },
        )

        with self.assertRaisesRegex(PortfolioDashboardValidationError, "forbidden term"):
            build_portfolio_risk_dashboard_projection((bad_artifact,))

    def test_rejects_chinese_forbidden_trading_semantics(self):
        bad_alert = AlertCandidate(
            alert_id="alert_bad_chinese",
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            alert_level=AlertLevel.REVIEW,
            alert_type=AlertType.RISK_REVIEW,
            reason="這不是推薦內容但應該被擋下",
            source_event_ids=("event_001",),
            created_at=self.created_at(),
        )
        artifact = self.artifact()
        bad_artifact = replace(
            artifact,
            alert_candidates=(bad_alert,),
            calculation_metadata={
                **artifact.calculation_metadata,
                "alert_candidate_count": 1,
            },
        )

        with self.assertRaisesRegex(PortfolioDashboardValidationError, "推薦"):
            build_portfolio_risk_dashboard_projection((bad_artifact,))

    def test_portfolio_dashboard_modules_do_not_import_runtime_boundaries(self):
        source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "portfolio_dashboard").glob("*.py"))
        )

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
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
