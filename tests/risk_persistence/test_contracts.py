import inspect
import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk import PortfolioPosition
from risk import RiskArtifactGenerator
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskChecksumGenerator
from risk import RiskContext
from risk import RiskSeverity
from risk import RiskSignal
from risk_persistence import RiskArtifactConflictError
from risk_persistence import RiskArtifactCorruptionError
from risk_persistence import RiskArtifactPersistenceError
from risk_persistence import RiskArtifactRepository
from risk_persistence import RiskArtifactSaveResult
from risk_persistence import RiskArtifactSaveStatus


class _MinimalRepositoryFake:
    def __init__(self):
        self.artifact = None

    def save(self, artifact):
        self.artifact = artifact
        return RiskArtifactSaveResult(
            artifact_id=artifact.artifact_id,
            checksum=artifact.checksum,
            status=RiskArtifactSaveStatus.INSERTED,
        )

    def get_by_artifact_id(self, artifact_id):
        if self.artifact is None or self.artifact.artifact_id != artifact_id:
            return None
        return self.artifact


class RiskArtifactPersistenceContractsTestCase(unittest.TestCase):

    def artifact(self):
        context = RiskContext(
            portfolio_id="portfolio_persistence_001",
            symbol="2330.TW",
            analysis_date=date(2026, 8, 15),
            feature_version="feature_set_v1",
            model_version=None,
            calculation_id="risk_calc_persistence_001",
        )
        signal = RiskSignal(
            risk_id="TECH_RISK_V1",
            symbol="2330.TW",
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.MEDIUM,
            trigger_reason="technical risk evidence",
            created_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id=context.portfolio_id,
            symbol=context.symbol,
            signals=(signal,),
            assessment_date=context.analysis_date,
        )
        artifact = RiskArtifactGenerator().generate(
            artifact_id="risk_artifact_persistence_001",
            position=PortfolioPosition(
                symbol="2330.TW",
                shares=Decimal("10"),
                average_cost=Decimal("650.00"),
                holding_type="whole_share",
                acquisition_date=date(2026, 1, 5),
                currency="TWD",
            ),
            context=context,
            assessment=assessment,
            created_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        )
        return artifact.__class__(
            artifact_id=artifact.artifact_id,
            position_identity=artifact.position_identity,
            risk_assessment=artifact.risk_assessment,
            signals=artifact.signals,
            feature_lineage=artifact.feature_lineage,
            calculation_metadata=artifact.calculation_metadata,
            created_at=artifact.created_at,
            checksum=RiskChecksumGenerator().generate(artifact, context),
        )

    def test_save_status_exact_vocabulary(self):
        self.assertEqual(
            tuple(status.value for status in RiskArtifactSaveStatus),
            ("INSERTED", "IDEMPOTENT"),
        )

    def test_save_result_inserted(self):
        result = RiskArtifactSaveResult(
            artifact_id="artifact_001",
            checksum="checksum_001",
            status=RiskArtifactSaveStatus.INSERTED,
        )

        self.assertEqual(result.artifact_id, "artifact_001")
        self.assertEqual(result.checksum, "checksum_001")
        self.assertEqual(result.status, RiskArtifactSaveStatus.INSERTED)

    def test_save_result_idempotent(self):
        result = RiskArtifactSaveResult(
            artifact_id="artifact_001",
            checksum="checksum_001",
            status="IDEMPOTENT",
        )

        self.assertEqual(result.status, RiskArtifactSaveStatus.IDEMPOTENT)

    def test_save_result_is_frozen(self):
        result = RiskArtifactSaveResult(
            artifact_id="artifact_001",
            checksum="checksum_001",
            status=RiskArtifactSaveStatus.INSERTED,
        )

        with self.assertRaises(FrozenInstanceError):
            result.status = RiskArtifactSaveStatus.IDEMPOTENT

    def test_save_result_rejects_invalid_artifact_id(self):
        invalid_values = ("", None, 123)
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(RiskArtifactPersistenceError, "artifact_id"):
                    RiskArtifactSaveResult(
                        artifact_id=value,
                        checksum="checksum_001",
                        status=RiskArtifactSaveStatus.INSERTED,
                    )

    def test_save_result_rejects_invalid_checksum(self):
        invalid_values = ("", None, 123)
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(RiskArtifactPersistenceError, "checksum"):
                    RiskArtifactSaveResult(
                        artifact_id="artifact_001",
                        checksum=value,
                        status=RiskArtifactSaveStatus.INSERTED,
                    )

    def test_save_result_rejects_invalid_status(self):
        with self.assertRaisesRegex(RiskArtifactPersistenceError, "status"):
            RiskArtifactSaveResult(
                artifact_id="artifact_001",
                checksum="checksum_001",
                status="UPDATED",
            )

    def test_error_hierarchy(self):
        self.assertTrue(issubclass(RiskArtifactConflictError, RiskArtifactPersistenceError))
        self.assertTrue(issubclass(RiskArtifactCorruptionError, RiskArtifactPersistenceError))
        self.assertFalse(issubclass(RiskArtifactConflictError, RiskArtifactCorruptionError))
        self.assertFalse(issubclass(RiskArtifactCorruptionError, RiskArtifactConflictError))

    def test_conflict_error_structured_data(self):
        error = RiskArtifactConflictError(
            artifact_id="artifact_001",
            existing_checksum="checksum_existing",
            incoming_checksum="checksum_incoming",
        )

        self.assertEqual(error.artifact_id, "artifact_001")
        self.assertEqual(error.existing_checksum, "checksum_existing")
        self.assertEqual(error.incoming_checksum, "checksum_incoming")
        self.assertNotIn("raw", str(error).lower())

    def test_corruption_error_structured_data(self):
        error = RiskArtifactCorruptionError(artifact_id="artifact_001")

        self.assertEqual(error.artifact_id, "artifact_001")
        self.assertNotIn("payload", str(error).lower())

    def test_runtime_protocol_compatibility(self):
        repository = _MinimalRepositoryFake()

        self.assertIsInstance(repository, RiskArtifactRepository)

    def test_protocol_save_and_get_shape(self):
        self.assertEqual(
            tuple(inspect.signature(RiskArtifactRepository.save).parameters),
            ("self", "artifact"),
        )
        self.assertEqual(
            tuple(inspect.signature(RiskArtifactRepository.get_by_artifact_id).parameters),
            ("self", "artifact_id"),
        )

    def test_get_missing_returns_none_semantic_with_tests_only_fake(self):
        repository = _MinimalRepositoryFake()

        self.assertIsNone(repository.get_by_artifact_id("missing_artifact"))

    def test_tests_only_fake_can_return_saved_domain_artifact(self):
        artifact = self.artifact()
        repository = _MinimalRepositoryFake()

        result = repository.save(artifact)

        self.assertEqual(result.status, RiskArtifactSaveStatus.INSERTED)
        self.assertIs(repository.get_by_artifact_id(artifact.artifact_id), artifact)

    def test_repository_protocol_has_no_query_or_mutation_apis(self):
        forbidden = (
            "exists",
            "list",
            "query",
            "latest",
            "history",
            "save_many",
            "update",
            "delete",
            "replace",
            "patch",
            "close",
            "__enter__",
            "__exit__",
        )
        for name in forbidden:
            with self.subTest(name=name):
                self.assertFalse(hasattr(RiskArtifactRepository, name))

    def test_public_exports(self):
        import risk_persistence

        self.assertIs(risk_persistence.RiskArtifactRepository, RiskArtifactRepository)
        self.assertIs(risk_persistence.RiskArtifactSaveResult, RiskArtifactSaveResult)
        self.assertIs(risk_persistence.RiskArtifactSaveStatus, RiskArtifactSaveStatus)
        self.assertIs(risk_persistence.RiskArtifactPersistenceError, RiskArtifactPersistenceError)
        self.assertIs(risk_persistence.RiskArtifactConflictError, RiskArtifactConflictError)
        self.assertIs(risk_persistence.RiskArtifactCorruptionError, RiskArtifactCorruptionError)

    def test_source_dependency_boundary(self):
        source = (SRC_PATH / "risk_persistence" / "contracts.py").read_text()

        forbidden = (
            "sqlite3",
            "pathlib",
            "json",
            "RiskArtifactCodec",
            "portfolio_generation",
            "risk_evaluation",
            "risk_oos",
            "risk_integration",
            "LiveDataStore",
            "ResearchDataStore",
            "yfinance",
            "open(",
            "Path(",
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "save_many",
            "delete",
            "update",
            "query",
            "latest",
            "TechnicalRiskEvidenceSnapshot",
            "PortfolioRiskGenerationRun",
            "PolicyRepository",
            "ActivationRegistry",
        )
        for forbidden_text in forbidden:
            with self.subTest(forbidden_text=forbidden_text):
                self.assertNotIn(forbidden_text, source)

    def test_risk_core_has_no_reverse_dependency(self):
        risk_source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "risk").glob("*.py"))
        )

        self.assertNotIn("risk_persistence", risk_source)


if __name__ == "__main__":
    unittest.main()
