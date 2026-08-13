import sys
import unittest
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from portfolio_artifacts import canonical_json_dumps
from portfolio_artifacts import serialize_risk_monitoring_artifact
from portfolio_artifacts import serialized_payload_checksum
from portfolio_dashboard.artifact_provider import DEFAULT_RISK_MONITORING_ARTIFACT_ROOT
from portfolio_dashboard.artifact_provider import PortfolioDashboardProviderResult
from portfolio_dashboard.artifact_provider import load_portfolio_risk_dashboard
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


class PortfolioDashboardArtifactProviderTestCase(unittest.TestCase):

    def created_at(self, hour=12):
        return datetime(2026, 8, 13, hour, 0, tzinfo=UTC)

    def risk_context(self, *, portfolio_id="portfolio_synthetic_001", symbol="2330.TW"):
        return RiskContext(
            portfolio_id=portfolio_id,
            symbol=symbol,
            analysis_date=date(2026, 8, 13),
            feature_version="feature_set_v1",
            model_version="baseline_model_v1",
            calculation_id=f"risk_calc_{symbol}",
        )

    def monitoring_context(
        self,
        *,
        portfolio_id="portfolio_synthetic_001",
        symbol="2330.TW",
        source_artifact_id="risk_artifact_001",
    ):
        return RiskMonitoringContext(
            portfolio_id=portfolio_id,
            symbol=symbol,
            monitoring_date=date(2026, 8, 13),
            source_risk_artifact_id=source_artifact_id,
            risk_artifact_checksum=f"{source_artifact_id}_checksum",
            monitoring_policy_version="policy_v1",
            calculation_id=f"monitoring_calc_{symbol}",
        )

    def risk_artifact(
        self,
        *,
        portfolio_id="portfolio_synthetic_001",
        symbol="2330.TW",
        artifact_id="risk_artifact_001",
    ):
        signal = RiskSignal(
            risk_id=f"TECH_RISK_{symbol}",
            symbol=symbol,
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.HIGH,
            trigger_reason="synthetic risk review metadata",
            created_at=self.created_at(),
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id=portfolio_id,
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
            context=self.risk_context(portfolio_id=portfolio_id, symbol=symbol),
            assessment=assessment,
            created_at=self.created_at(),
        )

    def event(self, *, portfolio_id="portfolio_synthetic_001", symbol="2330.TW", event_id="event_001"):
        return RiskMonitoringEvent(
            event_id=event_id,
            portfolio_id=portfolio_id,
            symbol=symbol,
            source_risk_id=f"TECH_RISK_{symbol}",
            risk_category=RiskCategory.TECHNICAL,
            risk_severity=RiskSeverity.HIGH,
            monitoring_state=MonitoringState.REVIEW_REQUIRED,
            reason="synthetic risk review metadata",
            created_at=self.created_at(),
        )

    def alert(
        self,
        *,
        portfolio_id="portfolio_synthetic_001",
        symbol="2330.TW",
        alert_id="alert_001",
        event_id="event_001",
    ):
        return AlertCandidate(
            alert_id=alert_id,
            portfolio_id=portfolio_id,
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
        portfolio_id="portfolio_synthetic_001",
        symbol="2330.TW",
        artifact_id="monitoring_artifact_001",
        source_artifact_id="risk_artifact_001",
        event_id="event_001",
        alert_id="alert_001",
        hour=12,
    ):
        risk_artifact = self.risk_artifact(
            portfolio_id=portfolio_id,
            symbol=symbol,
            artifact_id=source_artifact_id,
        )
        return RiskMonitoringArtifactGenerator().generate(
            artifact_id=artifact_id,
            risk_artifact=risk_artifact,
            context=self.monitoring_context(
                portfolio_id=portfolio_id,
                symbol=symbol,
                source_artifact_id=source_artifact_id,
            ),
            monitoring_state=MonitoringState.REVIEW_REQUIRED,
            events=(self.event(portfolio_id=portfolio_id, symbol=symbol, event_id=event_id),),
            alert_candidates=(
                self.alert(portfolio_id=portfolio_id, symbol=symbol, alert_id=alert_id, event_id=event_id),
            ),
            created_at=self.created_at(hour),
            checksum=f"{artifact_id}_checksum",
        )

    def write_artifact(self, root: Path, artifact, *, payload_mutator=None):
        payload = serialize_risk_monitoring_artifact(artifact)
        if payload_mutator is not None:
            payload_mutator(payload)
        path = root / "artifacts" / artifact.portfolio_id / artifact.symbol / f"{artifact.artifact_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(canonical_json_dumps(payload), encoding="utf-8")
        return path

    def test_missing_root_returns_empty_state_ready_result(self):
        with TemporaryDirectory() as temp_dir:
            result = load_portfolio_risk_dashboard(Path(temp_dir) / "missing")

        self.assertTrue(result.success)
        self.assertTrue(result.is_empty)
        self.assertIsNone(result.error)
        self.assertEqual(result.projection.overview.artifact_count, 0)

    def test_empty_repository_returns_empty_projection(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            (root / "artifacts").mkdir(parents=True)

            result = load_portfolio_risk_dashboard(root)

        self.assertTrue(result.success)
        self.assertTrue(result.is_empty)
        self.assertEqual(result.projection.positions, ())

    def test_valid_persisted_artifact_returns_dashboard_projection(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            artifact = self.artifact()
            self.write_artifact(root, artifact)

            result = load_portfolio_risk_dashboard(root)

        self.assertTrue(result.success)
        self.assertIsInstance(result, PortfolioDashboardProviderResult)
        self.assertEqual(result.projection.overview.artifact_count, 1)
        self.assertEqual(result.projection.positions[0].artifact_id, artifact.artifact_id)

    def test_corrupt_artifact_returns_safe_error(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            path = root / "artifacts" / "portfolio" / "2330.TW" / "bad.json"
            path.parent.mkdir(parents=True)
            path.write_text("{bad json", encoding="utf-8")

            result = load_portfolio_risk_dashboard(root)

        self.assertFalse(result.success)
        self.assertIsNone(result.projection)
        self.assertIn("Invalid artifact JSON", result.error)

    def test_checksum_mismatch_returns_safe_error(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            artifact = self.artifact()
            self.write_artifact(
                root,
                artifact,
                payload_mutator=lambda payload: payload["events"][0].__setitem__("reason", "changed"),
            )

            result = load_portfolio_risk_dashboard(root)

        self.assertFalse(result.success)
        self.assertIsNone(result.projection)
        self.assertIn("Invalid serialized artifact payload", result.error)

    def test_unsupported_schema_returns_safe_error(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            artifact = self.artifact()
            self.write_artifact(
                root,
                artifact,
                payload_mutator=lambda payload: (
                    payload.__setitem__("schema_version", "999"),
                    payload.__setitem__("serialization_checksum", serialized_payload_checksum(payload)),
                ),
            )

            result = load_portfolio_risk_dashboard(root)

        self.assertFalse(result.success)
        self.assertIn("Invalid serialized artifact payload", result.error)

    def test_duplicate_artifact_returns_safe_error(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            first = self.artifact(artifact_id="duplicate_artifact")
            second = self.artifact(
                portfolio_id="portfolio_b",
                symbol="2454.TW",
                artifact_id="duplicate_artifact",
                source_artifact_id="risk_b",
                event_id="event_b",
                alert_id="alert_b",
            )
            self.write_artifact(root, first)
            self.write_artifact(root, second)

            result = load_portfolio_risk_dashboard(root)

        self.assertFalse(result.success)
        self.assertIn("Duplicate risk monitoring artifact_id", result.error)

    def test_warning_metadata_propagated(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            self.write_artifact(root, self.artifact())

            result = load_portfolio_risk_dashboard(root)

        self.assertTrue(result.success)
        self.assertEqual(result.warning_metadata["artifact_count"], 1)
        self.assertFalse(result.warning_metadata["stale_warning"])
        self.assertFalse(result.has_warning)

    def test_provider_deterministic(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            second = self.artifact(
                symbol="2454.TW",
                artifact_id="artifact_b",
                source_artifact_id="risk_b",
                event_id="event_b",
                alert_id="alert_b",
                hour=17,
            )
            first = self.artifact(
                symbol="2330.TW",
                artifact_id="artifact_a",
                source_artifact_id="risk_a",
                event_id="event_a",
                alert_id="alert_a",
                hour=1,
            )
            self.write_artifact(root, second)
            self.write_artifact(root, first)

            result = load_portfolio_risk_dashboard(root)

        self.assertTrue(result.success)
        self.assertEqual(
            tuple(row.artifact_id for row in result.projection.positions),
            ("artifact_a", "artifact_b"),
        )

    def test_provider_does_not_mutate_persisted_artifact_payload(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            path = self.write_artifact(root, self.artifact())
            original_payload = path.read_text(encoding="utf-8")

            result = load_portfolio_risk_dashboard(root)

            self.assertTrue(result.success)
            self.assertEqual(path.read_text(encoding="utf-8"), original_payload)

    def test_provider_module_does_not_import_runtime_boundaries(self):
        source = (SRC_PATH / "portfolio_dashboard" / "artifact_provider.py").read_text()

        forbidden_terms = (
            "sqlite3",
            "LiveDataStore",
            "live_data_store",
            "ResearchDataStore",
            "research_data_store",
            "scanner",
            "pdf_export",
            "yfinance",
            "RiskMonitoringEngine",
            "RiskArtifactGenerator",
            "RiskMonitoringArtifactGenerator",
            "save_artifact",
            "delete_artifact",
            "update_artifact",
            "latest artifact",
            "best artifact",
            "preferred artifact",
            "selected artifact",
            "ranking",
        )
        for forbidden in forbidden_terms:
            self.assertNotIn(forbidden, source)

    def test_app_py_minimal_portfolio_provider_wiring(self):
        app_source = (PROJECT_ROOT / "app.py").read_text()
        portfolio_section = app_source[
            app_source.index("    with portfolio_risk_tab:"):
            app_source.index("    with universe_tab:")
        ]

        self.assertIn("from portfolio_dashboard.artifact_provider import load_portfolio_risk_dashboard", app_source)
        self.assertIn("portfolio_risk_result = load_portfolio_risk_dashboard()", portfolio_section)
        self.assertIn("projection=portfolio_risk_result.projection", portfolio_section)
        self.assertIn("validation_error=portfolio_risk_result.error", portfolio_section)
        self.assertIn("warning_metadata=portfolio_risk_result.warning_metadata", portfolio_section)

        forbidden_terms = (
            "Path(",
            "RiskMonitoringArtifactRepository",
            "json",
            "schema_version",
            "checksum",
            "load_portfolio_artifacts",
            "latest",
            "best",
            "preferred",
            "selected",
            "ranking",
        )
        for forbidden in forbidden_terms:
            self.assertNotIn(forbidden, portfolio_section)

    def test_default_artifact_root_contract(self):
        self.assertEqual(
            DEFAULT_RISK_MONITORING_ARTIFACT_ROOT.as_posix(),
            "data/portfolio_artifacts/risk_monitoring",
        )


if __name__ == "__main__":
    unittest.main()
