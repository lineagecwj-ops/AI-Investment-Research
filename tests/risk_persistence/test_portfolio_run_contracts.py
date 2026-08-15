import inspect
import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from portfolio_generation import PortfolioRiskGenerationStatus
from risk_persistence import PORTFOLIO_RUN_RECORD_CODEC_VERSION_V1
from risk_persistence import PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V1
from risk_persistence import PortfolioRiskGenerationRunArtifactRef
from risk_persistence import PortfolioRiskGenerationRunConflictError
from risk_persistence import PortfolioRiskGenerationRunCorruptionError
from risk_persistence import PortfolioRiskGenerationRunIssue
from risk_persistence import PortfolioRiskGenerationRunMonitoringArtifactRef
from risk_persistence import PortfolioRiskGenerationRunPersistenceError
from risk_persistence import PortfolioRiskGenerationRunRecord
from risk_persistence import PortfolioRiskGenerationRunRecordCodec
from risk_persistence import PortfolioRiskGenerationRunRecordCodecError
from risk_persistence import PortfolioRiskGenerationRunRepository
from risk_persistence import PortfolioRiskGenerationRunSaveResult
from risk_persistence import PortfolioRiskGenerationRunSaveStatus
from risk_persistence import PortfolioRiskGenerationRunWarning


class _RunRepositoryFake:
    def __init__(self):
        self.record = None

    def save(self, record):
        self.record = record
        return PortfolioRiskGenerationRunSaveResult(
            calculation_id=record.calculation_id,
            record_checksum=record.record_checksum,
            status=PortfolioRiskGenerationRunSaveStatus.INSERTED,
        )

    def get_by_calculation_id(self, calculation_id):
        if self.record is None or self.record.calculation_id != calculation_id:
            return None
        return self.record


class PortfolioRiskGenerationRunContractsTestCase(unittest.TestCase):

    def risk_ref(self, position_id="position_a", artifact_id=None, checksum=None):
        return PortfolioRiskGenerationRunArtifactRef(
            position_id=position_id,
            artifact_id=artifact_id or f"risk_artifact_{position_id}",
            artifact_checksum=checksum or f"risk_checksum_{position_id}",
        )

    def monitoring_ref(self, position_id="position_a", artifact_id=None):
        return PortfolioRiskGenerationRunMonitoringArtifactRef(
            position_id=position_id,
            artifact_id=artifact_id or f"monitoring_artifact_{position_id}",
        )

    def issue(self, *, position_id="position_b"):
        return PortfolioRiskGenerationRunIssue(
            stage="MONITORING",
            message="monitoring failed",
            position_id=position_id,
        )

    def warning(self, *, position_id="position_a", message="risk warning"):
        return PortfolioRiskGenerationRunWarning(
            stage="RISK_EVALUATION",
            message=message,
            position_id=position_id,
        )

    def record(self, **overrides):
        values = {
            "calculation_id": "portfolio_risk_calc_001",
            "generation_key": "portfolio_risk_generation_001",
            "portfolio_id": "portfolio_001",
            "snapshot_id": "snapshot_001",
            "snapshot_checksum": "snapshot_checksum_001",
            "analysis_date": date(2026, 8, 15),
            "valuation_date": date(2026, 8, 14),
            "status": PortfolioRiskGenerationStatus.SUCCESS,
            "attempted_position_ids": ("position_a", "position_b"),
            "risk_evaluated_position_ids": ("position_a", "position_b"),
            "succeeded_position_ids": ("position_a", "position_b"),
            "failed_position_ids": (),
            "risk_artifact_refs": (self.risk_ref("position_a"), self.risk_ref("position_b")),
            "monitoring_artifact_refs": (self.monitoring_ref("position_a"), self.monitoring_ref("position_b")),
            "issues": (),
            "warnings": (self.warning(position_id="position_a"),),
            "created_at": datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        }
        values.update(overrides)
        return PortfolioRiskGenerationRunRecord(**values)

    def test_version_constants(self):
        self.assertEqual(PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V1, "1")
        self.assertEqual(PORTFOLIO_RUN_RECORD_CODEC_VERSION_V1, "1")

    def test_record_is_frozen(self):
        record = self.record()

        with self.assertRaises(FrozenInstanceError):
            record.status = PortfolioRiskGenerationStatus.MONITORING_FAILED

    def test_artifact_ref_is_frozen(self):
        ref = self.risk_ref()

        with self.assertRaises(FrozenInstanceError):
            ref.artifact_id = "other"

    def test_issue_and_warning_are_frozen(self):
        issue = self.issue()
        warning = self.warning()

        with self.assertRaises(FrozenInstanceError):
            issue.message = "other"
        with self.assertRaises(FrozenInstanceError):
            warning.message = "other"

    def test_success_record(self):
        record = self.record()

        self.assertEqual(record.status, PortfolioRiskGenerationStatus.SUCCESS)
        self.assertEqual(record.risk_evaluated_position_ids, ("position_a", "position_b"))
        self.assertTrue(record.record_checksum)

    def test_risk_evaluation_failed_partial_record(self):
        record = self.record(
            status=PortfolioRiskGenerationStatus.RISK_EVALUATION_FAILED,
            attempted_position_ids=("position_a", "position_b"),
            risk_evaluated_position_ids=("position_a",),
            succeeded_position_ids=("position_a",),
            failed_position_ids=("position_b",),
            risk_artifact_refs=(self.risk_ref("position_a"),),
            monitoring_artifact_refs=(self.monitoring_ref("position_a"),),
            issues=(PortfolioRiskGenerationRunIssue("RISK_EVALUATION", "risk failed", "position_b"),),
            warnings=(),
        )

        self.assertEqual(record.failed_position_ids, ("position_b",))
        self.assertEqual(tuple(ref.position_id for ref in record.risk_artifact_refs), ("position_a",))

    def test_monitoring_failed_allows_risk_evaluated_failed_overlap(self):
        record = self.record(
            status=PortfolioRiskGenerationStatus.MONITORING_FAILED,
            attempted_position_ids=("position_a", "position_b"),
            risk_evaluated_position_ids=("position_a", "position_b"),
            succeeded_position_ids=("position_a",),
            failed_position_ids=("position_b",),
            risk_artifact_refs=(self.risk_ref("position_a"), self.risk_ref("position_b")),
            monitoring_artifact_refs=(self.monitoring_ref("position_a"),),
            issues=(self.issue(position_id="position_b"),),
            warnings=(),
        )

        self.assertIn("position_b", record.risk_evaluated_position_ids)
        self.assertIn("position_b", record.failed_position_ids)
        self.assertEqual(tuple(ref.position_id for ref in record.monitoring_artifact_refs), ("position_a",))

    def test_validation_failed_empty_lifecycle(self):
        record = self.record(
            status=PortfolioRiskGenerationStatus.VALIDATION_FAILED,
            attempted_position_ids=(),
            risk_evaluated_position_ids=(),
            succeeded_position_ids=(),
            failed_position_ids=(),
            risk_artifact_refs=(),
            monitoring_artifact_refs=(),
            issues=(PortfolioRiskGenerationRunIssue("VALIDATION", "policy missing"),),
            warnings=(),
        )

        self.assertEqual(record.attempted_position_ids, ())
        self.assertEqual(record.risk_artifact_refs, ())

    def test_already_generated_status_is_legal(self):
        record = self.record(status=PortfolioRiskGenerationStatus.ALREADY_GENERATED)

        self.assertEqual(record.status, PortfolioRiskGenerationStatus.ALREADY_GENERATED)

    def test_same_symbol_different_position_ids_are_represented_by_position_id(self):
        record = self.record(
            attempted_position_ids=("position_a", "position_b"),
            risk_evaluated_position_ids=("position_a", "position_b"),
            succeeded_position_ids=("position_a", "position_b"),
            risk_artifact_refs=(
                self.risk_ref("position_a", artifact_id="risk_artifact_a"),
                self.risk_ref("position_b", artifact_id="risk_artifact_b"),
            ),
            monitoring_artifact_refs=(
                self.monitoring_ref("position_a", artifact_id="monitoring_artifact_a"),
                self.monitoring_ref("position_b", artifact_id="monitoring_artifact_b"),
            ),
        )

        self.assertEqual(tuple(ref.position_id for ref in record.risk_artifact_refs), ("position_a", "position_b"))

    def test_tuple_order_is_preserved(self):
        record = self.record(
            attempted_position_ids=("position_b", "position_a"),
            risk_evaluated_position_ids=("position_b", "position_a"),
            succeeded_position_ids=("position_b", "position_a"),
            risk_artifact_refs=(self.risk_ref("position_b"), self.risk_ref("position_a")),
            monitoring_artifact_refs=(self.monitoring_ref("position_b"), self.monitoring_ref("position_a")),
        )

        self.assertEqual(record.attempted_position_ids, ("position_b", "position_a"))

    def test_duplicate_position_ids_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "duplicates"):
            self.record(attempted_position_ids=("position_a", "position_a"))

    def test_subset_invariant_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "risk_evaluated_position_ids"):
            self.record(
                attempted_position_ids=("position_a",),
                risk_evaluated_position_ids=("position_a", "position_b"),
                risk_artifact_refs=(self.risk_ref("position_a"), self.risk_ref("position_b")),
            )

    def test_succeeded_and_failed_overlap_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "must not overlap"):
            self.record(failed_position_ids=("position_a",))

    def test_risk_artifact_ref_count_mismatch_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "risk_artifact_refs"):
            self.record(risk_artifact_refs=(self.risk_ref("position_a"),))

    def test_ref_position_pair_mismatch_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "position order"):
            self.record(risk_artifact_refs=(self.risk_ref("position_b"), self.risk_ref("position_a")))

    def test_monitoring_ref_count_mismatch_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "monitoring_artifact_refs"):
            self.record(monitoring_artifact_refs=(self.monitoring_ref("position_a"),))

    def test_duplicate_artifact_ids_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "duplicate artifact_id"):
            self.record(
                risk_artifact_refs=(
                    self.risk_ref("position_a", artifact_id="same_artifact"),
                    self.risk_ref("position_b", artifact_id="same_artifact"),
                )
            )

    def test_naive_created_at_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "timezone-aware"):
            self.record(created_at=datetime(2026, 8, 15, 12, 0))

    def test_datetime_used_as_date_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "analysis_date"):
            self.record(analysis_date=datetime(2026, 8, 15, 12, 0, tzinfo=UTC))

    def test_empty_required_string_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "calculation_id"):
            self.record(calculation_id="")

    def test_record_checksum_is_deterministic_and_semantic(self):
        first = self.record()
        second = self.record()
        changed = self.record(generation_key="portfolio_risk_generation_other")

        self.assertEqual(first.record_checksum, second.record_checksum)
        self.assertNotEqual(first.record_checksum, changed.record_checksum)

    def test_supplied_record_checksum_is_verified(self):
        valid = self.record()

        self.assertEqual(self.record(record_checksum=valid.record_checksum), valid)
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "record_checksum"):
            self.record(record_checksum="bad_checksum")

    def test_issue_warning_optional_position_id(self):
        issue = PortfolioRiskGenerationRunIssue(stage="VALIDATION", message="bad input", position_id=None)
        warning = PortfolioRiskGenerationRunWarning(stage="GENERATION", message="heads up", position_id=None)

        self.assertIsNone(issue.position_id)
        self.assertIsNone(warning.position_id)

    def test_save_status_exact_vocabulary(self):
        self.assertEqual(
            tuple(status.value for status in PortfolioRiskGenerationRunSaveStatus),
            ("INSERTED", "IDEMPOTENT"),
        )

    def test_save_result_frozen_and_validates(self):
        result = PortfolioRiskGenerationRunSaveResult(
            calculation_id="portfolio_risk_calc_001",
            record_checksum="checksum_001",
            status="IDEMPOTENT",
        )

        self.assertEqual(result.status, PortfolioRiskGenerationRunSaveStatus.IDEMPOTENT)
        with self.assertRaises(FrozenInstanceError):
            result.status = PortfolioRiskGenerationRunSaveStatus.INSERTED
        with self.assertRaisesRegex(PortfolioRiskGenerationRunPersistenceError, "status"):
            PortfolioRiskGenerationRunSaveResult("calc", "checksum", "UPDATED")

    def test_protocol_structural_compatibility(self):
        self.assertIsInstance(_RunRepositoryFake(), PortfolioRiskGenerationRunRepository)

    def test_repository_protocol_exact_method_names(self):
        methods = {
            name
            for name, value in inspect.getmembers(PortfolioRiskGenerationRunRepository, inspect.isfunction)
            if not name.startswith("_")
        }

        self.assertEqual(methods, {"save", "get_by_calculation_id"})

    def test_repository_protocol_has_no_query_mutation_apis(self):
        forbidden = ("list", "history", "latest", "delete", "update", "save_many", "transaction", "close")

        for name in forbidden:
            self.assertFalse(hasattr(PortfolioRiskGenerationRunRepository, name))

    def test_error_hierarchy(self):
        self.assertTrue(issubclass(PortfolioRiskGenerationRunConflictError, PortfolioRiskGenerationRunPersistenceError))
        self.assertTrue(issubclass(PortfolioRiskGenerationRunCorruptionError, PortfolioRiskGenerationRunPersistenceError))

    def test_conflict_and_corruption_errors_have_structured_fields(self):
        conflict = PortfolioRiskGenerationRunConflictError(
            "portfolio_risk_calc_001",
            "existing_checksum",
            "incoming_checksum",
        )
        corruption = PortfolioRiskGenerationRunCorruptionError("portfolio_risk_calc_001")

        self.assertEqual(conflict.calculation_id, "portfolio_risk_calc_001")
        self.assertEqual(conflict.existing_checksum, "existing_checksum")
        self.assertEqual(conflict.incoming_checksum, "incoming_checksum")
        self.assertEqual(corruption.calculation_id, "portfolio_risk_calc_001")

    def test_public_exports(self):
        exported = __import__("risk_persistence").__all__
        expected = (
            "PortfolioRiskGenerationRunRecord",
            "PortfolioRiskGenerationRunArtifactRef",
            "PortfolioRiskGenerationRunMonitoringArtifactRef",
            "PortfolioRiskGenerationRunIssue",
            "PortfolioRiskGenerationRunWarning",
            "PortfolioRiskGenerationRunRecordCodec",
            "PortfolioRiskGenerationRunRecordCodecError",
            "PortfolioRiskGenerationRunRepository",
            "PortfolioRiskGenerationRunSaveStatus",
            "PortfolioRiskGenerationRunSaveResult",
            "PortfolioRiskGenerationRunPersistenceError",
            "PortfolioRiskGenerationRunConflictError",
            "PortfolioRiskGenerationRunCorruptionError",
        )
        for name in expected:
            self.assertIn(name, exported)

    def test_no_sqlite_dependency_in_run_contracts(self):
        source = (SRC_PATH / "risk_persistence" / "portfolio_run_contracts.py").read_text()

        self.assertNotIn("sqlite3", source)
        self.assertNotIn("CREATE TABLE", source)
        self.assertNotIn("PRAGMA", source)


if __name__ == "__main__":
    unittest.main()
