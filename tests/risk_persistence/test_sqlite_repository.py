import json
import sqlite3
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk.risk_artifact_codec as codec_module
from portfolio_generation import TechnicalRiskArtifactAdapter
from risk import HoldingType
from risk import PortfolioPosition
from risk import RiskArtifact
from risk import RiskArtifactCodec
from risk import RiskArtifactGenerator
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskChecksumGenerator
from risk import RiskContext
from risk import RiskSeverity
from risk import RiskSignal
from risk_evaluation import ProducedRiskSignal
from risk_evaluation import TechnicalRiskProductionResult
from risk_persistence import RiskArtifactConflictError
from risk_persistence import RiskArtifactCorruptionError
from risk_persistence import RiskArtifactPersistenceError
from risk_persistence import RiskArtifactRepository
from risk_persistence import RiskArtifactSaveStatus
from risk_persistence import SQLiteRiskArtifactRepository


APPLICATION_ID = 0x41494952
SCHEMA_VERSION = 2


class SQLiteRiskArtifactRepositoryTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "risk_artifacts.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def repository(self, db_path=None, **kwargs):
        return SQLiteRiskArtifactRepository(db_path or self.db_path, **kwargs)

    def created_at(self, hour=12):
        return datetime(2026, 8, 15, hour, 0, tzinfo=UTC)

    def analysis_date(self):
        return date(2026, 8, 15)

    def context(self, **overrides):
        values = {
            "portfolio_id": "portfolio_sqlite_001",
            "symbol": "2330.TW",
            "analysis_date": self.analysis_date(),
            "feature_version": "feature_set_v1",
            "model_version": "risk_model_v1",
            "calculation_id": "risk_calc_sqlite_001",
        }
        values.update(overrides)
        return RiskContext(**values)

    def position(self, **overrides):
        values = {
            "symbol": "2330.TW",
            "shares": Decimal("10.00"),
            "average_cost": Decimal("650.50"),
            "holding_type": HoldingType.FRACTIONAL_SHARE,
            "acquisition_date": date(2026, 1, 5),
            "currency": "TWD",
        }
        values.update(overrides)
        return PortfolioPosition(**values)

    def signal(self, *, severity=RiskSeverity.MEDIUM, symbol="2330.TW", reason="technical risk evidence"):
        return RiskSignal(
            risk_id="TECH_TREND_WEAKENING_V1",
            symbol=symbol,
            category=RiskCategory.TECHNICAL,
            severity=severity,
            trigger_reason=reason,
            created_at=self.created_at(),
        )

    def artifact(self, *, artifact_id="risk_artifact_sqlite_001", severity=RiskSeverity.MEDIUM, **overrides):
        context = overrides.pop("context", self.context())
        position = overrides.pop("position", self.position())
        signal = self.signal(severity=severity, symbol=context.symbol)
        assessment = RiskAssessment.from_signals(
            portfolio_id=context.portfolio_id,
            symbol=context.symbol,
            signals=(signal,),
            assessment_date=context.analysis_date,
        )
        artifact = RiskArtifactGenerator().generate(
            artifact_id=artifact_id,
            position=position,
            context=context,
            assessment=assessment,
            created_at=overrides.pop("created_at", self.created_at()),
        )
        artifact = replace(
            artifact,
            feature_lineage={
                **artifact.feature_lineage,
                **overrides.pop("feature_lineage", {}),
            },
            calculation_metadata={
                **artifact.calculation_metadata,
                **overrides.pop("calculation_metadata", {}),
            },
        )
        checksum = RiskChecksumGenerator().generate(artifact, context)
        return replace(artifact, checksum=checksum)

    def technical_artifact(self):
        context = self.context(feature_version="technical_risk_feature_set_v1", model_version=None)
        signal = RiskSignal(
            risk_id="TECHNICAL_DOWNSIDE_RISK_V1",
            symbol="2330.TW",
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.HIGH,
            trigger_reason="technical downside risk evidence: TREND_WEAKNESS",
            created_at=self.created_at(),
        )
        produced_signal = ProducedRiskSignal(
            signal=signal,
            policy_id="TECH_RISK_POLICY_V1",
            policy_version="v1",
            producer_version="TECHNICAL_RISK_SIGNAL_PRODUCER_V1",
            source_feature_ids=("TECH_AS_OF_CLOSE_V1", "TECH_SMA20_V1", "TECH_SMA60_V1", "TECH_RSI14_V1"),
            source_checksums=("close_checksum", "sma20_checksum", "sma60_checksum", "rsi14_checksum"),
            calculation_id="risk_calc_sqlite_001",
            policy_checksum="policy_checksum_001",
            evaluation_id="technical_eval_001",
            evaluation_checksum="evaluation_checksum_001",
            portfolio_id="portfolio_sqlite_001",
            position_id="position_001",
            as_of_date=self.analysis_date(),
            valuation_date=date(2026, 8, 14),
        )
        result = TechnicalRiskProductionResult(
            produced_signal=produced_signal,
            risk_assessment=RiskAssessment.from_signals(
                portfolio_id="portfolio_sqlite_001",
                symbol="2330.TW",
                signals=(signal,),
                assessment_date=self.analysis_date(),
            ),
        )
        return TechnicalRiskArtifactAdapter().build(
            result=result,
            context=context,
            position=self.position(),
            artifact_id="technical_risk_artifact_sqlite_001",
            created_at=self.created_at(13),
        )

    def connection(self):
        return sqlite3.connect(self.db_path)

    def row_count(self):
        connection = self.connection()
        try:
            return connection.execute("SELECT COUNT(*) FROM risk_artifacts").fetchone()[0]
        finally:
            connection.close()

    def stored_payload(self, artifact_id="risk_artifact_sqlite_001"):
        connection = self.connection()
        try:
            return connection.execute(
                "SELECT payload_json FROM risk_artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()[0]
        finally:
            connection.close()

    def update_stored_payload(self, artifact_id, payload_json):
        connection = self.connection()
        try:
            connection.execute(
                "UPDATE risk_artifacts SET payload_json = ? WHERE artifact_id = ?",
                (payload_json, artifact_id),
            )
            connection.commit()
        finally:
            connection.close()

    def test_new_db_initialization_sets_schema_identity_and_pragmas(self):
        repository = self.repository()

        self.assertIsInstance(repository, RiskArtifactRepository)
        connection = self.connection()
        try:
            self.assertEqual(connection.execute("PRAGMA application_id").fetchone()[0], APPLICATION_ID)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
            connection.execute("PRAGMA foreign_keys=ON")
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            columns = tuple(row[1] for row in connection.execute("PRAGMA table_info(risk_artifacts)").fetchall())
            self.assertEqual(columns, ("artifact_id", "artifact_checksum", "payload_json"))
            tables = tuple(
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
            )
            self.assertEqual(tables, ("risk_artifacts", "technical_risk_artifact_index"))
        finally:
            connection.close()

    def test_busy_timeout_override(self):
        repository = self.repository(busy_timeout_ms=1234)

        self.assertEqual(
            repository._with_connection(lambda connection: connection.execute("PRAGMA busy_timeout").fetchone()[0]),
            1234,
        )

    def test_constructor_rejects_invalid_inputs(self):
        with self.assertRaisesRegex(RiskArtifactPersistenceError, "db_path"):
            SQLiteRiskArtifactRepository("")
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(RiskArtifactPersistenceError, "directory"):
                SQLiteRiskArtifactRepository(temp_dir)
            with self.assertRaisesRegex(RiskArtifactPersistenceError, "parent"):
                SQLiteRiskArtifactRepository(Path(temp_dir) / "missing" / "risk.db")
        with self.assertRaisesRegex(RiskArtifactPersistenceError, "busy_timeout"):
            self.repository(busy_timeout_ms=0)

    def test_save_inserted_and_get_round_trip(self):
        artifact = self.artifact()
        repository = self.repository()

        result = repository.save(artifact)

        self.assertEqual(result.status, RiskArtifactSaveStatus.INSERTED)
        self.assertEqual(result.artifact_id, artifact.artifact_id)
        self.assertEqual(result.checksum, artifact.checksum)
        self.assertEqual(repository.get_by_artifact_id(artifact.artifact_id), artifact)
        self.assertEqual(self.row_count(), 1)

    def test_save_idempotent_keeps_single_row(self):
        artifact = self.artifact()
        repository = self.repository()

        self.assertEqual(repository.save(artifact).status, RiskArtifactSaveStatus.INSERTED)
        self.assertEqual(repository.save(artifact).status, RiskArtifactSaveStatus.IDEMPOTENT)

        self.assertEqual(self.row_count(), 1)
        self.assertEqual(repository.get_by_artifact_id(artifact.artifact_id), artifact)

    def test_get_missing_returns_none_and_invalid_get_id_rejected(self):
        repository = self.repository()

        self.assertIsNone(repository.get_by_artifact_id("missing"))
        for invalid in ("", None, 123):
            with self.subTest(invalid=invalid):
                with self.assertRaises(RiskArtifactPersistenceError):
                    repository.get_by_artifact_id(invalid)

    def test_save_rejects_non_artifact_and_missing_checksum(self):
        repository = self.repository()

        with self.assertRaisesRegex(RiskArtifactPersistenceError, "RiskArtifact"):
            repository.save(object())
        with self.assertRaisesRegex(RiskArtifactPersistenceError, "checksum"):
            repository.save(replace(self.artifact(), checksum=None))

    def test_same_id_different_checksum_conflicts_and_preserves_original(self):
        first = self.artifact()
        second_context = self.context(calculation_id="risk_calc_sqlite_002")
        second = self.artifact(
            artifact_id=first.artifact_id,
            context=second_context,
            calculation_metadata={"calculation_id": "risk_calc_sqlite_002"},
        )
        repository = self.repository()

        repository.save(first)
        with self.assertRaises(RiskArtifactConflictError) as context:
            repository.save(second)

        self.assertEqual(context.exception.artifact_id, first.artifact_id)
        self.assertEqual(context.exception.existing_checksum, first.checksum)
        self.assertEqual(context.exception.incoming_checksum, second.checksum)
        self.assertEqual(repository.get_by_artifact_id(first.artifact_id), first)
        self.assertEqual(self.row_count(), 1)

    def test_two_repository_instances_share_same_db(self):
        artifact = self.artifact()
        first = self.repository()
        second = self.repository()

        self.assertEqual(first.save(artifact).status, RiskArtifactSaveStatus.INSERTED)
        self.assertEqual(second.save(artifact).status, RiskArtifactSaveStatus.IDEMPOTENT)
        self.assertEqual(second.get_by_artifact_id(artifact.artifact_id), artifact)

    def test_low_medium_high_round_trip(self):
        for severity in (RiskSeverity.LOW, RiskSeverity.MEDIUM, RiskSeverity.HIGH):
            with self.subTest(severity=severity):
                db_path = Path(self.temp_dir.name) / f"{severity.value.lower()}.db"
                artifact = self.artifact(artifact_id=f"artifact_{severity.value}", severity=severity)
                repository = self.repository(db_path)

                repository.save(artifact)

                decoded = repository.get_by_artifact_id(artifact.artifact_id)
                self.assertEqual(decoded.signals[0].severity, severity)
                self.assertEqual(decoded.risk_assessment.overall_risk_level, severity)

    def test_technical_artifact_lineage_round_trip(self):
        artifact = self.technical_artifact()
        repository = self.repository()

        repository.save(artifact)
        decoded = repository.get_by_artifact_id(artifact.artifact_id)

        self.assertEqual(decoded.calculation_metadata["technical_policy_id"], "TECH_RISK_POLICY_V1")
        self.assertEqual(decoded.calculation_metadata["technical_policy_version"], "v1")
        self.assertEqual(decoded.calculation_metadata["technical_policy_checksum"], "policy_checksum_001")
        self.assertEqual(decoded.calculation_metadata["technical_evaluation_id"], "technical_eval_001")
        self.assertEqual(decoded.calculation_metadata["technical_evaluation_checksum"], "evaluation_checksum_001")
        self.assertEqual(decoded.calculation_metadata["technical_position_id"], "position_001")
        self.assertEqual(decoded.calculation_metadata["technical_as_of_date"], "2026-08-15")
        self.assertEqual(decoded.calculation_metadata["technical_valuation_date"], "2026-08-14")
        self.assertEqual(decoded.calculation_metadata["technical_calculation_id"], "risk_calc_sqlite_001")
        self.assertEqual(decoded.calculation_metadata["technical_producer_version"], "TECHNICAL_RISK_SIGNAL_PRODUCER_V1")
        self.assertEqual(
            tuple(zip(
                decoded.feature_lineage["technical_source_feature_ids"],
                decoded.feature_lineage["technical_source_checksums"],
            )),
            tuple(zip(
                artifact.feature_lineage["technical_source_feature_ids"],
                artifact.feature_lineage["technical_source_checksums"],
            )),
        )

    def test_malformed_payload_corruption_blocks_get_and_idempotency(self):
        artifact = self.artifact()
        repository = self.repository()
        repository.save(artifact)
        self.update_stored_payload(artifact.artifact_id, "{not-json")

        with self.assertRaises(RiskArtifactCorruptionError):
            repository.get_by_artifact_id(artifact.artifact_id)
        with self.assertRaises(RiskArtifactCorruptionError):
            repository.save(artifact)

    def test_serialization_checksum_corruption(self):
        artifact = self.artifact()
        repository = self.repository()
        repository.save(artifact)
        payload = json.loads(self.stored_payload(artifact.artifact_id))
        payload["artifact"]["signals"][0]["trigger_reason"] = "changed without checksum"
        self.update_stored_payload(artifact.artifact_id, codec_module.canonical_json_dumps(payload))

        with self.assertRaises(RiskArtifactCorruptionError):
            repository.get_by_artifact_id(artifact.artifact_id)

    def test_domain_checksum_corruption(self):
        artifact = self.artifact()
        repository = self.repository()
        repository.save(artifact)
        payload = json.loads(self.stored_payload(artifact.artifact_id))
        payload["artifact"]["checksum"] = "wrong_domain_checksum"
        payload["serialization_checksum"] = codec_module.serialization_checksum(payload)
        self.update_stored_payload(artifact.artifact_id, codec_module.canonical_json_dumps(payload))

        with self.assertRaises(RiskArtifactCorruptionError):
            repository.get_by_artifact_id(artifact.artifact_id)

    def test_db_checksum_column_mismatch_corruption(self):
        artifact = self.artifact()
        repository = self.repository()
        repository.save(artifact)
        connection = self.connection()
        try:
            connection.execute(
                "UPDATE risk_artifacts SET artifact_checksum = ? WHERE artifact_id = ?",
                ("wrong_column_checksum", artifact.artifact_id),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactCorruptionError):
            repository.get_by_artifact_id(artifact.artifact_id)

    def test_payload_artifact_id_mismatch_corruption(self):
        artifact = self.artifact()
        replacement = self.artifact(artifact_id="different_payload_artifact")
        repository = self.repository()
        repository.save(artifact)
        self.update_stored_payload(artifact.artifact_id, RiskArtifactCodec().encode(replacement))

        with self.assertRaises(RiskArtifactCorruptionError):
            repository.get_by_artifact_id(artifact.artifact_id)

    def test_corruption_precedes_conflict(self):
        first = self.artifact()
        second_context = self.context(calculation_id="risk_calc_sqlite_002")
        second = self.artifact(
            artifact_id=first.artifact_id,
            context=second_context,
            calculation_metadata={"calculation_id": "risk_calc_sqlite_002"},
        )
        repository = self.repository()
        repository.save(first)
        self.update_stored_payload(first.artifact_id, "{not-json")

        with self.assertRaises(RiskArtifactCorruptionError):
            repository.save(second)

    def test_wrong_existing_db_rejected_without_pollution(self):
        connection = self.connection()
        try:
            connection.execute("CREATE TABLE foo (id TEXT PRIMARY KEY)")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.repository()

        connection = self.connection()
        try:
            tables = tuple(
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
            )
        finally:
            connection.close()
        self.assertEqual(tables, ("foo",))

    def test_future_schema_version_rejected(self):
        connection = self.connection()
        try:
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute("PRAGMA user_version=3")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.repository()

    def test_wrong_schema_shape_rejected(self):
        connection = self.connection()
        try:
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute("CREATE TABLE risk_artifacts (artifact_id TEXT PRIMARY KEY)")
            connection.execute("PRAGMA user_version=1")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.repository()

    def test_public_api_export(self):
        import risk_persistence

        self.assertIs(risk_persistence.SQLiteRiskArtifactRepository, SQLiteRiskArtifactRepository)

    def test_repository_has_no_query_or_mutation_apis(self):
        repository = self.repository()
        forbidden = (
            "list_by_portfolio",
            "list_by_position",
            "list_latest",
            "history",
            "query",
            "delete",
            "update",
            "save_many",
            "transaction",
            "close",
            "__enter__",
            "__exit__",
        )
        for name in forbidden:
            with self.subTest(name=name):
                self.assertFalse(hasattr(repository, name))

    def test_source_boundary_and_no_technical_branching(self):
        source = (SRC_PATH / "risk_persistence" / "sqlite_repository.py").read_text()
        allowed = (
            "sqlite3",
            "RiskArtifactCodec",
            "RiskArtifactCodecError",
            "RiskArtifactRepository",
        )
        for text in allowed:
            self.assertIn(text, source)
        forbidden = (
            "portfolio_generation",
            "risk_evaluation",
            "risk_oos",
            "risk_integration",
            "LiveDataStore",
            "ResearchDataStore",
            "yfinance",
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "list_by_portfolio",
            "list_by_position",
            "list_latest",
            "technical_position_id",
            "technical_policy_id",
            "TechnicalRisk",
            "INSERT OR REPLACE",
            "REPLACE INTO",
            "ON CONFLICT",
        )
        for text in forbidden:
            with self.subTest(text=text):
                self.assertNotIn(text, source)

    def test_production_paths_are_not_created_or_referenced(self):
        source = (SRC_PATH / "risk_persistence" / "sqlite_repository.py").read_text()
        tests = Path(__file__).read_text()
        forbidden_paths = (
            "data/" + "production",
            "data/" + "stocks.db",
            "data/" + "live",
            "data/" + "research",
        )

        for forbidden_path in forbidden_paths:
            with self.subTest(forbidden_path=forbidden_path):
                self.assertNotIn(forbidden_path, source)


if __name__ == "__main__":
    unittest.main()
