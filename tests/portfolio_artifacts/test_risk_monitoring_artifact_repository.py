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

from portfolio_artifacts import ArtifactRef
from portfolio_artifacts import RiskMonitoringArtifactRepository
from portfolio_artifacts import RiskMonitoringArtifactRepositoryError
from portfolio_artifacts import canonical_json_dumps
from portfolio_artifacts import serialize_risk_monitoring_artifact
from portfolio_artifacts import serialized_payload_checksum
from portfolio_dashboard import PortfolioArtifactInputRequest
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


class RiskMonitoringArtifactRepositoryTestCase(unittest.TestCase):

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
        severity=RiskSeverity.HIGH,
    ):
        signal = RiskSignal(
            risk_id=f"TECH_RISK_{symbol}",
            symbol=symbol,
            category=RiskCategory.TECHNICAL,
            severity=severity,
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
            context=replace(self.risk_context(symbol), portfolio_id=portfolio_id),
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
            created_at=self.created_at(),
            checksum=f"{artifact_id}_checksum",
        )

    def write_artifact(self, root: Path, artifact, *, payload_mutator=None, filename=None):
        payload = serialize_risk_monitoring_artifact(artifact)
        if payload_mutator is not None:
            payload_mutator(payload)
        artifact_path = (
            root
            / "artifacts"
            / artifact.portfolio_id
            / artifact.symbol
            / (filename or f"{artifact.artifact_id}.json")
        )
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(canonical_json_dumps(payload), encoding="utf-8")
        return artifact_path

    def test_missing_root_returns_safe_empty_behavior(self):
        with TemporaryDirectory() as temp_dir:
            repository = RiskMonitoringArtifactRepository(Path(temp_dir) / "missing")

            self.assertEqual(repository.list_artifacts(), ())
            self.assertEqual(repository.load_portfolio_artifacts(), ())

    def test_empty_root_returns_empty_tuple(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            (root / "artifacts").mkdir(parents=True)
            repository = RiskMonitoringArtifactRepository(root)

            self.assertEqual(repository.list_artifacts(), ())
            self.assertEqual(repository.load_portfolio_artifacts(), ())

    def test_valid_json_artifact_load(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            artifact = self.artifact()
            path = self.write_artifact(root, artifact)
            repository = RiskMonitoringArtifactRepository(root)

            refs = repository.list_artifacts()
            artifacts = repository.load_portfolio_artifacts()

            self.assertEqual(refs, (ArtifactRef(artifact.artifact_id, artifact.portfolio_id, artifact.symbol, path, "1"),))
            self.assertEqual(artifacts, (artifact,))

    def test_multiple_artifacts_have_deterministic_ordering(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            second = self.artifact(
                portfolio_id="portfolio_b",
                symbol="2454.TW",
                artifact_id="artifact_b",
                source_artifact_id="risk_b",
                event_id="event_b",
                alert_id="alert_b",
            )
            first = self.artifact(
                portfolio_id="portfolio_a",
                symbol="2330.TW",
                artifact_id="artifact_a",
                source_artifact_id="risk_a",
                event_id="event_a",
                alert_id="alert_a",
            )
            self.write_artifact(root, second)
            self.write_artifact(root, first)
            repository = RiskMonitoringArtifactRepository(root)

            self.assertEqual(
                tuple(ref.artifact_id for ref in repository.list_artifacts()),
                ("artifact_a", "artifact_b"),
            )
            self.assertEqual(
                tuple(artifact.artifact_id for artifact in repository.load_portfolio_artifacts()),
                ("artifact_a", "artifact_b"),
            )

    def test_portfolio_filter(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            first = self.artifact(portfolio_id="portfolio_a", artifact_id="artifact_a")
            second = self.artifact(
                portfolio_id="portfolio_b",
                symbol="2454.TW",
                artifact_id="artifact_b",
                source_artifact_id="risk_b",
                event_id="event_b",
                alert_id="alert_b",
            )
            self.write_artifact(root, first)
            self.write_artifact(root, second)
            repository = RiskMonitoringArtifactRepository(root)

            self.assertEqual(
                tuple(ref.artifact_id for ref in repository.list_artifacts(portfolio_id="portfolio_b")),
                ("artifact_b",),
            )
            self.assertEqual(
                tuple(artifact.portfolio_id for artifact in repository.load_portfolio_artifacts("portfolio_b")),
                ("portfolio_b",),
            )

    def test_corrupt_json_rejection(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            artifact_path = root / "artifacts" / "portfolio" / "2330.TW" / "bad.json"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_text("{bad json", encoding="utf-8")
            repository = RiskMonitoringArtifactRepository(root)

            with self.assertRaises(RiskMonitoringArtifactRepositoryError):
                repository.load_portfolio_artifacts()

    def test_unsupported_schema_version_rejection(self):
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
            repository = RiskMonitoringArtifactRepository(root)

            with self.assertRaises(RiskMonitoringArtifactRepositoryError):
                repository.load_portfolio_artifacts()

    def test_serialization_checksum_mismatch_rejection(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            artifact = self.artifact()
            self.write_artifact(
                root,
                artifact,
                payload_mutator=lambda payload: payload["events"][0].__setitem__(
                    "reason",
                    "changed after checksum",
                ),
            )
            repository = RiskMonitoringArtifactRepository(root)

            with self.assertRaises(RiskMonitoringArtifactRepositoryError):
                repository.load_portfolio_artifacts()

    def test_duplicate_artifact_id_rejection(self):
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
            repository = RiskMonitoringArtifactRepository(root)

            with self.assertRaises(RiskMonitoringArtifactRepositoryError) as context:
                repository.list_artifacts()

            self.assertIn("Duplicate risk monitoring artifact_id", str(context.exception))

    def test_missing_required_field_rejection(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            artifact = self.artifact()
            self.write_artifact(root, artifact, payload_mutator=lambda payload: payload.pop("lineage"))
            repository = RiskMonitoringArtifactRepository(root)

            with self.assertRaises(RiskMonitoringArtifactRepositoryError):
                repository.load_portfolio_artifacts()

    def test_unrelated_files_are_ignored(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            artifact = self.artifact()
            self.write_artifact(root, artifact)
            unrelated = root / "artifacts" / "portfolio" / "2330.TW" / "notes.txt"
            unrelated.parent.mkdir(parents=True, exist_ok=True)
            unrelated.write_text("ignore me", encoding="utf-8")
            repository = RiskMonitoringArtifactRepository(root)

            self.assertEqual(tuple(ref.artifact_id for ref in repository.list_artifacts()), (artifact.artifact_id,))

    def test_temp_and_hidden_files_are_ignored(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            artifact = self.artifact()
            self.write_artifact(root, artifact)
            hidden = root / "artifacts" / "portfolio" / "2330.TW" / ".hidden.json"
            temp = root / "artifacts" / "portfolio" / "2330.TW" / "artifact.tmp.json"
            hidden.parent.mkdir(parents=True, exist_ok=True)
            hidden.write_text("{bad json", encoding="utf-8")
            temp.write_text("{bad json", encoding="utf-8")
            repository = RiskMonitoringArtifactRepository(root)

            self.assertEqual(tuple(ref.artifact_id for ref in repository.list_artifacts()), (artifact.artifact_id,))

    def test_symlink_escape_is_ignored_when_supported(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            root = temp_path / "risk_monitoring"
            artifact = self.artifact()
            self.write_artifact(root, artifact)
            external = temp_path / "external.json"
            external.write_text("{bad json", encoding="utf-8")
            link = root / "artifacts" / "portfolio" / "2330.TW" / "escape.json"
            link.parent.mkdir(parents=True, exist_ok=True)
            try:
                link.symlink_to(external)
            except OSError:
                self.skipTest("Filesystem does not support symlink creation in this environment.")
            repository = RiskMonitoringArtifactRepository(root)

            self.assertEqual(tuple(ref.artifact_id for ref in repository.list_artifacts()), (artifact.artifact_id,))

    def test_repository_is_read_only(self):
        repository = RiskMonitoringArtifactRepository("/tmp/nonexistent")

        self.assertFalse(hasattr(repository, "save_artifact"))
        self.assertFalse(hasattr(repository, "delete_artifact"))
        self.assertFalse(hasattr(repository, "update_artifact"))
        self.assertFalse(hasattr(repository, "get_latest_artifact"))
        self.assertFalse(hasattr(repository, "select_best_artifact"))

    def test_loaded_tuple_is_dashboard_input_compatible(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "risk_monitoring"
            artifact = self.artifact()
            self.write_artifact(root, artifact)
            repository = RiskMonitoringArtifactRepository(root)

            result = build_portfolio_dashboard_input(
                PortfolioArtifactInputRequest(artifacts=repository.load_portfolio_artifacts())
            )

            self.assertTrue(result.success)
            self.assertEqual(result.projection.overview.artifact_count, 1)
            self.assertEqual(result.projection.positions[0].artifact_id, artifact.artifact_id)

    def test_repository_module_does_not_import_forbidden_runtime_boundaries(self):
        source = (SRC_PATH / "portfolio_artifacts" / "repository.py").read_text()

        forbidden_terms = (
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
            "save_artifact",
            "delete_artifact",
            "update_artifact",
            "get_latest_artifact",
            "select_best_artifact",
        )
        for forbidden in forbidden_terms:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
