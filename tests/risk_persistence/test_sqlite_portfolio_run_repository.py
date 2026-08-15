import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_persistence.sqlite_portfolio_run_repository as run_repository_module
from portfolio_generation import PortfolioRiskGenerationStatus
from risk_persistence import PortfolioRiskGenerationRunArtifactRef
from risk_persistence import PortfolioRiskGenerationRunConflictError
from risk_persistence import PortfolioRiskGenerationRunCorruptionError
from risk_persistence import PortfolioRiskGenerationRunIssue
from risk_persistence import PortfolioRiskGenerationRunMonitoringArtifactRef
from risk_persistence import PortfolioRiskGenerationRunPersistenceError
from risk_persistence import PortfolioRiskGenerationRunRecord
from risk_persistence import PortfolioRiskGenerationRunRecordCodec
from risk_persistence import PortfolioRiskGenerationRunRepository
from risk_persistence import PortfolioRiskGenerationRunSaveStatus
from risk_persistence import PortfolioRiskGenerationRunWarning
from risk_persistence import SQLitePortfolioRiskGenerationRunRepository


APPLICATION_ID = 0x41494952
SCHEMA_VERSION = 3


class SQLitePortfolioRiskGenerationRunRepositoryTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "risk_artifacts.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def repository(self, db_path=None, **kwargs):
        return SQLitePortfolioRiskGenerationRunRepository(db_path or self.db_path, **kwargs)

    def connection(self):
        return sqlite3.connect(self.db_path)

    def risk_ref(self, position_id="position_a", artifact_id=None, checksum=None):
        return PortfolioRiskGenerationRunArtifactRef(
            position_id=position_id,
            artifact_id=artifact_id or f"missing_risk_artifact_{position_id}",
            artifact_checksum=checksum or f"missing_risk_checksum_{position_id}",
        )

    def monitoring_ref(self, position_id="position_a", artifact_id=None):
        return PortfolioRiskGenerationRunMonitoringArtifactRef(
            position_id=position_id,
            artifact_id=artifact_id or f"missing_monitoring_artifact_{position_id}",
        )

    def record(self, **overrides):
        values = {
            "calculation_id": "portfolio_risk_calc_001",
            "generation_key": "portfolio_generation_001",
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
            "warnings": (PortfolioRiskGenerationRunWarning("RISK_EVALUATION", "風險提醒", "position_a"),),
            "created_at": datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        }
        values.update(overrides)
        return PortfolioRiskGenerationRunRecord(**values)

    def row_count(self):
        connection = self.connection()
        try:
            return connection.execute("SELECT COUNT(*) FROM portfolio_risk_generation_runs").fetchone()[0]
        finally:
            connection.close()

    def stored_row(self, calculation_id="portfolio_risk_calc_001"):
        connection = self.connection()
        try:
            return connection.execute(
                """
                SELECT calculation_id, record_checksum, payload_json
                FROM portfolio_risk_generation_runs
                WHERE calculation_id = ?
                """,
                (calculation_id,),
            ).fetchone()
        finally:
            connection.close()

    def update_run_row(self, calculation_id, *, record_checksum=None, payload_json=None, new_calculation_id=None):
        assignments = []
        parameters = []
        if record_checksum is not None:
            assignments.append("record_checksum = ?")
            parameters.append(record_checksum)
        if payload_json is not None:
            assignments.append("payload_json = ?")
            parameters.append(payload_json)
        if new_calculation_id is not None:
            assignments.append("calculation_id = ?")
            parameters.append(new_calculation_id)
        parameters.append(calculation_id)
        connection = self.connection()
        try:
            connection.execute(
                f"UPDATE portfolio_risk_generation_runs SET {', '.join(assignments)} WHERE calculation_id = ?",
                tuple(parameters),
            )
            connection.commit()
        finally:
            connection.close()

    def test_public_api_export_and_protocol_compatibility(self):
        repository = self.repository()

        import risk_persistence

        self.assertIs(
            risk_persistence.SQLitePortfolioRiskGenerationRunRepository,
            SQLitePortfolioRiskGenerationRunRepository,
        )
        self.assertIsInstance(repository, PortfolioRiskGenerationRunRepository)

    def test_constructor_validation_and_fresh_schema_v3(self):
        repository = self.repository(busy_timeout_ms=1234)

        self.assertEqual(
            repository._with_connection(lambda connection: connection.execute("PRAGMA busy_timeout").fetchone()[0]),
            1234,
        )
        connection = self.connection()
        try:
            self.assertEqual(connection.execute("PRAGMA application_id").fetchone()[0], APPLICATION_ID)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(
                tuple(
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table'
                          AND name NOT LIKE 'sqlite_%'
                        ORDER BY name
                        """
                    ).fetchall()
                ),
                ("portfolio_risk_generation_runs", "risk_artifacts", "technical_risk_artifact_index"),
            )
        finally:
            connection.close()

        with self.assertRaises(PortfolioRiskGenerationRunPersistenceError):
            SQLitePortfolioRiskGenerationRunRepository("")
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(PortfolioRiskGenerationRunPersistenceError):
                SQLitePortfolioRiskGenerationRunRepository(temp_dir)
            with self.assertRaises(PortfolioRiskGenerationRunPersistenceError):
                SQLitePortfolioRiskGenerationRunRepository(Path(temp_dir) / "missing" / "risk.db")
        with self.assertRaises(PortfolioRiskGenerationRunPersistenceError):
            self.repository(busy_timeout_ms=0)

    def test_save_inserted_get_and_full_codec_envelope(self):
        record = self.record()
        repository = self.repository()

        result = repository.save(record)

        self.assertEqual(result.status, PortfolioRiskGenerationRunSaveStatus.INSERTED)
        self.assertEqual(result.calculation_id, record.calculation_id)
        self.assertEqual(result.record_checksum, record.record_checksum)
        self.assertEqual(repository.get_by_calculation_id(record.calculation_id), record)
        row = self.stored_row(record.calculation_id)
        self.assertEqual(row[0], record.calculation_id)
        self.assertEqual(row[1], record.record_checksum)
        payload = json.loads(row[2])
        self.assertEqual(tuple(payload), ("codec_version", "record", "schema_version"))
        self.assertEqual(payload["record"]["record_checksum"], record.record_checksum)
        self.assertNotIn("serialization_checksum", payload)
        self.assertEqual(self.row_count(), 1)

    def test_save_idempotent_keeps_single_row(self):
        record = self.record()
        repository = self.repository()

        self.assertEqual(repository.save(record).status, PortfolioRiskGenerationRunSaveStatus.INSERTED)
        self.assertEqual(repository.save(record).status, PortfolioRiskGenerationRunSaveStatus.IDEMPOTENT)

        self.assertEqual(self.row_count(), 1)

    def test_same_calculation_id_different_record_conflicts(self):
        first = self.record()
        second = self.record(generation_key="portfolio_generation_002")
        repository = self.repository()

        repository.save(first)
        with self.assertRaises(PortfolioRiskGenerationRunConflictError) as context:
            repository.save(second)

        self.assertEqual(context.exception.calculation_id, first.calculation_id)
        self.assertEqual(context.exception.existing_checksum, first.record_checksum)
        self.assertEqual(context.exception.incoming_checksum, second.record_checksum)
        self.assertEqual(repository.get_by_calculation_id(first.calculation_id), first)
        self.assertEqual(self.row_count(), 1)

    def test_get_missing_and_invalid_calculation_id(self):
        repository = self.repository()

        self.assertIsNone(repository.get_by_calculation_id("missing_calculation"))
        for invalid in ("", None, 123):
            with self.subTest(invalid=invalid):
                with self.assertRaises(PortfolioRiskGenerationRunPersistenceError):
                    repository.get_by_calculation_id(invalid)

    def test_invalid_save_input_and_codec_self_validation_failure(self):
        repository = self.repository()

        with self.assertRaises(PortfolioRiskGenerationRunPersistenceError):
            repository.save(object())

        class BrokenCodec:
            def encode(self, record):
                return "{not-json"

            def decode(self, payload):
                return PortfolioRiskGenerationRunRecordCodec().decode(payload)

        with patch.object(run_repository_module, "PortfolioRiskGenerationRunRecordCodec", BrokenCodec):
            with self.assertRaises(PortfolioRiskGenerationRunPersistenceError):
                repository.save(self.record())

    def test_stored_malformed_payload_is_corruption_and_precedes_idempotency(self):
        record = self.record()
        repository = self.repository()
        repository.save(record)
        self.update_run_row(record.calculation_id, payload_json="{not-json")

        with self.assertRaises(PortfolioRiskGenerationRunCorruptionError):
            repository.get_by_calculation_id(record.calculation_id)
        with self.assertRaises(PortfolioRiskGenerationRunCorruptionError):
            repository.save(record)

    def test_stored_record_checksum_tamper_is_corruption(self):
        record = self.record()
        repository = self.repository()
        repository.save(record)
        payload = json.loads(self.stored_row(record.calculation_id)[2])
        payload["record"]["record_checksum"] = "tampered_record_checksum"
        self.update_run_row(
            record.calculation_id,
            payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False),
        )

        with self.assertRaises(PortfolioRiskGenerationRunCorruptionError):
            repository.get_by_calculation_id(record.calculation_id)

    def test_db_record_checksum_mismatch_is_corruption(self):
        record = self.record()
        repository = self.repository()
        repository.save(record)
        self.update_run_row(record.calculation_id, record_checksum="wrong_db_checksum")

        with self.assertRaises(PortfolioRiskGenerationRunCorruptionError):
            repository.get_by_calculation_id(record.calculation_id)

    def test_db_calculation_id_mismatch_is_corruption(self):
        record = self.record()
        repository = self.repository()
        repository.save(record)
        self.update_run_row(record.calculation_id, new_calculation_id="other_calculation")

        with self.assertRaises(PortfolioRiskGenerationRunCorruptionError):
            repository.get_by_calculation_id("other_calculation")

    def test_status_variants_round_trip(self):
        variants = (
            self.record(
                calculation_id="calc_monitoring_failed",
                status=PortfolioRiskGenerationStatus.MONITORING_FAILED,
                attempted_position_ids=("position_a", "position_b"),
                risk_evaluated_position_ids=("position_a", "position_b"),
                succeeded_position_ids=("position_a",),
                failed_position_ids=("position_b",),
                risk_artifact_refs=(self.risk_ref("position_a"), self.risk_ref("position_b")),
                monitoring_artifact_refs=(self.monitoring_ref("position_a"),),
                issues=(PortfolioRiskGenerationRunIssue("MONITORING", "monitoring failed", "position_b"),),
                warnings=(),
            ),
            self.record(
                calculation_id="calc_validation_failed",
                status=PortfolioRiskGenerationStatus.VALIDATION_FAILED,
                attempted_position_ids=(),
                risk_evaluated_position_ids=(),
                succeeded_position_ids=(),
                failed_position_ids=(),
                risk_artifact_refs=(),
                monitoring_artifact_refs=(),
                issues=(PortfolioRiskGenerationRunIssue("VALIDATION", "policy missing", None),),
                warnings=(),
            ),
            self.record(calculation_id="calc_already_generated", status=PortfolioRiskGenerationStatus.ALREADY_GENERATED),
        )
        repository = self.repository()

        for record in variants:
            with self.subTest(status=record.status):
                self.assertEqual(repository.save(record).status, PortfolioRiskGenerationRunSaveStatus.INSERTED)
                self.assertEqual(repository.get_by_calculation_id(record.calculation_id), record)

    def test_no_artifact_fk_validation_in_standalone_run_repository(self):
        record = self.record()
        repository = self.repository()

        self.assertEqual(repository.save(record).status, PortfolioRiskGenerationRunSaveStatus.INSERTED)
        self.assertEqual(repository.get_by_calculation_id(record.calculation_id), record)
        connection = self.connection()
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM risk_artifacts").fetchone()[0], 0)
        finally:
            connection.close()

    def test_repository_has_no_query_or_mutation_apis(self):
        repository = self.repository()
        forbidden = (
            "list",
            "history",
            "latest",
            "get_by_generation_key",
            "list_by_portfolio",
            "list_by_status",
            "delete",
            "update",
            "save_many",
            "close",
            "__enter__",
            "__exit__",
        )
        for name in forbidden:
            with self.subTest(name=name):
                self.assertFalse(hasattr(repository, name))

    def test_source_boundary(self):
        source = (SRC_PATH / "risk_persistence" / "sqlite_portfolio_run_repository.py").read_text()
        required = (
            "BEGIN IMMEDIATE",
            "PortfolioRiskGenerationRunRecordCodec",
            "initialize_or_verify_schema",
        )
        for text in required:
            with self.subTest(required=text):
                self.assertIn(text, source)
        forbidden = (
            "TechnicalRiskArtifactIndexRecord",
            "technical_position_id",
            "TechnicalRisk",
            "PortfolioRiskGenerationService",
            "risk_oos",
            "risk_integration",
            "dashboard",
            "scheduler",
            "alert",
            "activation",
            "data/production",
            "data/stocks.db",
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "INSERT OR REPLACE",
            "REPLACE INTO",
            "ON CONFLICT",
        )
        for text in forbidden:
            with self.subTest(forbidden=text):
                self.assertNotIn(text, source)


if __name__ == "__main__":
    unittest.main()
