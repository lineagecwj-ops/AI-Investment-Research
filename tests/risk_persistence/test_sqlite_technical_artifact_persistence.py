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
from risk_persistence import RiskArtifactIndexCorruptionError
from risk_persistence import RiskArtifactPersistenceError
from risk_persistence import RiskArtifactSaveStatus
from risk_persistence import SQLiteRiskArtifactRepository
from risk_persistence import SQLiteTechnicalRiskArtifactPersistenceCoordinator
from risk_persistence import SQLiteTechnicalRiskArtifactQueryRepository
from risk_persistence import TechnicalRiskArtifactIndexRecord


APPLICATION_ID = 0x41494952
SCHEMA_VERSION_V1 = 1

V1_CREATE_RISK_ARTIFACTS_TABLE_SQL = """
CREATE TABLE risk_artifacts (
    artifact_id TEXT PRIMARY KEY CHECK (artifact_id <> ''),
    artifact_checksum TEXT NOT NULL CHECK (artifact_checksum <> ''),
    payload_json TEXT NOT NULL CHECK (payload_json <> '')
)
"""


class SQLiteTechnicalRiskArtifactPersistenceCoordinatorTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "risk_artifacts.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def coordinator(self, db_path=None, **kwargs):
        return SQLiteTechnicalRiskArtifactPersistenceCoordinator(db_path or self.db_path, **kwargs)

    def core_repository(self):
        return SQLiteRiskArtifactRepository(self.db_path)

    def query_repository(self):
        return SQLiteTechnicalRiskArtifactQueryRepository(self.db_path)

    def connection(self):
        return sqlite3.connect(self.db_path)

    def created_at(self, hour=12):
        return datetime(2026, 8, 15, hour, 0, tzinfo=UTC)

    def context(
        self,
        *,
        portfolio_id="portfolio_atomic_001",
        symbol="2330.TW",
        calculation_id=None,
    ):
        return RiskContext(
            portfolio_id=portfolio_id,
            symbol=symbol,
            analysis_date=date(2026, 8, 15),
            feature_version="technical_risk_feature_set_v1",
            model_version=None,
            calculation_id=calculation_id or f"risk_calc_{portfolio_id}_{symbol}",
        )

    def position(self, *, symbol="2330.TW"):
        return PortfolioPosition(
            symbol=symbol,
            shares=Decimal("10.00"),
            average_cost=Decimal("650.50"),
            holding_type=HoldingType.FRACTIONAL_SHARE,
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )

    def technical_artifact(
        self,
        *,
        artifact_id="technical_atomic_artifact_001",
        portfolio_id="portfolio_atomic_001",
        position_id="position_001",
        symbol="2330.TW",
        severity=RiskSeverity.MEDIUM,
        created_at=None,
    ):
        context = self.context(portfolio_id=portfolio_id, symbol=symbol, calculation_id=f"calc_{artifact_id}")
        signal = RiskSignal(
            risk_id="TECHNICAL_DOWNSIDE_RISK_V1",
            symbol=symbol,
            category=RiskCategory.TECHNICAL,
            severity=severity,
            trigger_reason="TREND_WEAKNESS",
            created_at=created_at or self.created_at(),
        )
        produced_signal = ProducedRiskSignal(
            signal=signal,
            policy_id="TECH_RISK_POLICY_V1",
            policy_version="v1",
            producer_version="TECHNICAL_RISK_SIGNAL_PRODUCER_V1",
            source_feature_ids=("TECH_AS_OF_CLOSE_V1", "TECH_SMA20_V1", "TECH_SMA60_V1", "TECH_RSI14_V1"),
            source_checksums=("close_checksum", "sma20_checksum", "sma60_checksum", "rsi14_checksum"),
            calculation_id=context.calculation_id,
            policy_checksum="policy_checksum_001",
            evaluation_id=f"technical_eval_{artifact_id}",
            evaluation_checksum=f"evaluation_checksum_{artifact_id}",
            portfolio_id=portfolio_id,
            position_id=position_id,
            as_of_date=context.analysis_date,
            valuation_date=date(2026, 8, 14),
        )
        result = TechnicalRiskProductionResult(
            produced_signal=produced_signal,
            risk_assessment=RiskAssessment.from_signals(
                portfolio_id=portfolio_id,
                symbol=symbol,
                signals=(signal,),
                assessment_date=context.analysis_date,
            ),
        )
        return TechnicalRiskArtifactAdapter().build(
            result=result,
            context=context,
            position=self.position(symbol=symbol),
            artifact_id=artifact_id,
            created_at=created_at or self.created_at(),
        )

    def generic_artifact(self, *, artifact_id="generic_atomic_artifact"):
        context = self.context(calculation_id=f"calc_{artifact_id}")
        signal = RiskSignal(
            risk_id="MARKET_RISK_V1",
            symbol=context.symbol,
            category=RiskCategory.MARKET,
            severity=RiskSeverity.MEDIUM,
            trigger_reason="market risk evidence",
            created_at=self.created_at(),
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id=context.portfolio_id,
            symbol=context.symbol,
            signals=(signal,),
            assessment_date=context.analysis_date,
        )
        artifact = RiskArtifactGenerator().generate(
            artifact_id=artifact_id,
            position=self.position(symbol=context.symbol),
            context=context,
            assessment=assessment,
            created_at=self.created_at(),
        )
        checksum = RiskChecksumGenerator().generate(artifact, context)
        return replace(artifact, checksum=checksum)

    def critical_artifact(self):
        artifact = self.technical_artifact(artifact_id="critical_artifact", severity=RiskSeverity.HIGH)
        signal = replace(artifact.signals[0], severity=RiskSeverity.CRITICAL)
        assessment = RiskAssessment.from_signals(
            portfolio_id=artifact.risk_assessment.portfolio_id,
            symbol=artifact.risk_assessment.symbol,
            signals=(signal,),
            assessment_date=artifact.risk_assessment.assessment_date,
        )
        invalid = replace(artifact, signals=(signal,), risk_assessment=assessment, checksum=None)
        context = self.context(calculation_id=artifact.calculation_metadata["calculation_id"])
        return replace(invalid, checksum=RiskChecksumGenerator().generate(invalid, context))

    def multiple_technical_signals_artifact(self):
        artifact = self.technical_artifact(artifact_id="multiple_technical_signals")
        second_signal = replace(
            artifact.signals[0],
            risk_id="TECHNICAL_DOWNSIDE_RISK_CONFIRMATION_V1",
            trigger_reason="MOMENTUM_WEAKNESS_CONFIRMATION",
        )
        signals = artifact.signals + (second_signal,)
        assessment = RiskAssessment.from_signals(
            portfolio_id=artifact.risk_assessment.portfolio_id,
            symbol=artifact.risk_assessment.symbol,
            signals=signals,
            assessment_date=artifact.risk_assessment.assessment_date,
        )
        invalid = replace(artifact, signals=signals, risk_assessment=assessment, checksum=None)
        context = self.context(calculation_id=artifact.calculation_metadata["calculation_id"])
        return replace(invalid, checksum=RiskChecksumGenerator().generate(invalid, context))

    def create_v1_db(self, artifacts):
        connection = self.connection()
        try:
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute(V1_CREATE_RISK_ARTIFACTS_TABLE_SQL)
            for artifact in artifacts:
                connection.execute(
                    """
                    INSERT INTO risk_artifacts (
                        artifact_id,
                        artifact_checksum,
                        payload_json
                    )
                    VALUES (?, ?, ?)
                    """,
                    (artifact.artifact_id, artifact.checksum, RiskArtifactCodec().encode(artifact)),
                )
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION_V1}")
            connection.commit()
        finally:
            connection.close()

    def insert_index_record(self, record):
        connection = self.connection()
        try:
            connection.execute(
                """
                INSERT INTO technical_risk_artifact_index (
                    artifact_id,
                    portfolio_id,
                    position_id,
                    symbol,
                    severity,
                    analysis_date,
                    valuation_date,
                    created_at,
                    calculation_id,
                    policy_id,
                    policy_version,
                    policy_checksum,
                    evaluation_id,
                    evaluation_checksum,
                    producer_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artifact_id,
                    record.portfolio_id,
                    record.position_id,
                    record.symbol,
                    record.severity.value,
                    record.analysis_date.isoformat(),
                    record.valuation_date.isoformat(),
                    record.created_at.isoformat(),
                    record.calculation_id,
                    record.policy_id,
                    record.policy_version,
                    record.policy_checksum,
                    record.evaluation_id,
                    record.evaluation_checksum,
                    record.producer_version,
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def update_index(self, artifact_id, field_name, value):
        connection = self.connection()
        try:
            connection.execute(
                f"UPDATE technical_risk_artifact_index SET {field_name} = ? WHERE artifact_id = ?",
                (value, artifact_id),
            )
            connection.commit()
        finally:
            connection.close()

    def update_core_payload(self, artifact_id, payload_json):
        connection = self.connection()
        try:
            connection.execute(
                "UPDATE risk_artifacts SET payload_json = ? WHERE artifact_id = ?",
                (payload_json, artifact_id),
            )
            connection.commit()
        finally:
            connection.close()

    def counts(self):
        connection = self.connection()
        try:
            return (
                connection.execute("SELECT COUNT(*) FROM risk_artifacts").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM technical_risk_artifact_index").fetchone()[0],
            )
        finally:
            connection.close()

    def index_record(self, artifact_id):
        connection = self.connection()
        try:
            return connection.execute(
                "SELECT artifact_id, portfolio_id, position_id, symbol, severity FROM technical_risk_artifact_index WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        finally:
            connection.close()

    def test_public_api_export_and_constructor_validation(self):
        import risk_persistence

        self.assertIs(
            risk_persistence.SQLiteTechnicalRiskArtifactPersistenceCoordinator,
            SQLiteTechnicalRiskArtifactPersistenceCoordinator,
        )
        with self.assertRaises(RiskArtifactPersistenceError):
            SQLiteTechnicalRiskArtifactPersistenceCoordinator(Path(self.temp_dir.name) / "missing" / "risk.db")
        with self.assertRaises(RiskArtifactPersistenceError):
            self.coordinator(busy_timeout_ms=0)

    def test_low_medium_high_atomic_save_insert_core_and_index(self):
        for severity in (RiskSeverity.LOW, RiskSeverity.MEDIUM, RiskSeverity.HIGH):
            with self.subTest(severity=severity):
                self.db_path = Path(self.temp_dir.name) / f"{severity.value.lower()}.db"
                artifact = self.technical_artifact(
                    artifact_id=f"technical_{severity.value.lower()}",
                    severity=severity,
                )

                result = self.coordinator().save(artifact)

                self.assertEqual(result.status, RiskArtifactSaveStatus.INSERTED)
                self.assertEqual(self.counts(), (1, 1))
                self.assertEqual(self.index_record(artifact.artifact_id)[4], severity.value)

    def test_critical_non_technical_and_multiple_signals_rejected_without_rows(self):
        invalid_artifacts = (
            self.critical_artifact(),
            self.generic_artifact(),
            self.multiple_technical_signals_artifact(),
        )
        for artifact in invalid_artifacts:
            with self.subTest(artifact_id=artifact.artifact_id):
                self.db_path = Path(self.temp_dir.name) / f"{artifact.artifact_id}.db"
                coordinator = self.coordinator()

                with self.assertRaises(RiskArtifactPersistenceError):
                    coordinator.save(artifact)

                self.assertEqual(self.counts(), (0, 0))

    def test_same_artifact_retry_is_idempotent_and_keeps_single_rows(self):
        artifact = self.technical_artifact()
        coordinator = self.coordinator()

        self.assertEqual(coordinator.save(artifact).status, RiskArtifactSaveStatus.INSERTED)
        self.assertEqual(coordinator.save(artifact).status, RiskArtifactSaveStatus.IDEMPOTENT)

        self.assertEqual(self.counts(), (1, 1))

    def test_migration_backfilled_artifact_retry_is_idempotent(self):
        artifact = self.technical_artifact()
        self.create_v1_db((artifact,))
        coordinator = self.coordinator()

        result = coordinator.save(artifact)

        self.assertEqual(result.status, RiskArtifactSaveStatus.IDEMPOTENT)
        self.assertEqual(self.counts(), (1, 1))

    def test_existing_core_missing_index_is_completed_and_query_visible(self):
        artifact = self.technical_artifact()
        self.core_repository().save(artifact)
        self.assertEqual(self.counts(), (1, 0))

        result = self.coordinator().save(artifact)

        self.assertEqual(result.status, RiskArtifactSaveStatus.IDEMPOTENT)
        self.assertEqual(self.counts(), (1, 1))
        self.assertEqual(
            self.query_repository().get_latest_by_position("portfolio_atomic_001", "position_001"),
            artifact,
        )

    def test_existing_core_mismatched_index_is_index_corruption_without_overwrite(self):
        artifact = self.technical_artifact()
        coordinator = self.coordinator()
        coordinator.save(artifact)
        self.update_index(artifact.artifact_id, "policy_checksum", "tampered_policy_checksum")

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            coordinator.save(artifact)

        self.assertEqual(self.index_record(artifact.artifact_id)[0], artifact.artifact_id)

    def test_orphan_index_is_index_corruption_and_not_repaired(self):
        artifact = self.technical_artifact()
        self.coordinator()
        record = TechnicalRiskArtifactIndexRecord.from_artifact(artifact)
        connection = self.connection()
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute(
                """
                INSERT INTO technical_risk_artifact_index (
                    artifact_id,
                    portfolio_id,
                    position_id,
                    symbol,
                    severity,
                    analysis_date,
                    valuation_date,
                    created_at,
                    calculation_id,
                    policy_id,
                    policy_version,
                    policy_checksum,
                    evaluation_id,
                    evaluation_checksum,
                    producer_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artifact_id,
                    record.portfolio_id,
                    record.position_id,
                    record.symbol,
                    record.severity.value,
                    record.analysis_date.isoformat(),
                    record.valuation_date.isoformat(),
                    record.created_at.isoformat(),
                    record.calculation_id,
                    record.policy_id,
                    record.policy_version,
                    record.policy_checksum,
                    record.evaluation_id,
                    record.evaluation_checksum,
                    record.producer_version,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            self.coordinator().save(artifact)

        self.assertEqual(self.counts(), (0, 1))

    def test_same_id_different_valid_core_conflicts_and_does_not_write_index(self):
        first = self.technical_artifact(artifact_id="shared_artifact", position_id="position_a")
        second = self.technical_artifact(artifact_id="shared_artifact", position_id="position_b")
        self.core_repository().save(first)

        with self.assertRaises(RiskArtifactConflictError):
            self.coordinator().save(second)

        self.assertEqual(self.counts(), (1, 0))

    def test_core_corruption_precedes_missing_index_completion(self):
        artifact = self.technical_artifact()
        self.core_repository().save(artifact)
        self.update_core_payload(artifact.artifact_id, "{not-json")

        with self.assertRaises(RiskArtifactCorruptionError):
            self.coordinator().save(artifact)

        self.assertEqual(self.counts(), (1, 0))

    def test_forced_index_failure_rolls_back_core_insert(self):
        artifact = self.technical_artifact()
        self.coordinator()
        connection = self.connection()
        try:
            connection.execute(
                """
                CREATE TRIGGER fail_technical_index_insert
                BEFORE INSERT ON technical_risk_artifact_index
                BEGIN
                    SELECT RAISE(ABORT, 'forced index failure');
                END
                """
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.coordinator().save(artifact)

        self.assertEqual(self.counts(), (0, 0))

    def test_same_symbol_multi_position_and_two_instances(self):
        first = self.technical_artifact(artifact_id="artifact_position_a", position_id="position_a", symbol="SAME")
        second = self.technical_artifact(artifact_id="artifact_position_b", position_id="position_b", symbol="SAME")
        first_coordinator = self.coordinator()
        second_coordinator = self.coordinator()

        self.assertEqual(first_coordinator.save(first).status, RiskArtifactSaveStatus.INSERTED)
        self.assertEqual(second_coordinator.save(first).status, RiskArtifactSaveStatus.IDEMPOTENT)
        self.assertEqual(second_coordinator.save(second).status, RiskArtifactSaveStatus.INSERTED)

        self.assertEqual(self.counts(), (2, 2))
        latest = self.query_repository().list_latest_by_portfolio("portfolio_atomic_001")
        self.assertEqual(tuple(artifact.artifact_id for artifact in latest), ("artifact_position_a", "artifact_position_b"))

    def test_fresh_db_and_v1_db_save_paths(self):
        fresh_artifact = self.technical_artifact(artifact_id="fresh_db_artifact")
        self.assertEqual(self.coordinator().save(fresh_artifact).status, RiskArtifactSaveStatus.INSERTED)

        self.db_path = Path(self.temp_dir.name) / "v1.db"
        v1_artifact = self.technical_artifact(artifact_id="v1_incoming_artifact")
        self.create_v1_db(())
        self.assertEqual(self.coordinator().save(v1_artifact).status, RiskArtifactSaveStatus.INSERTED)
        self.assertEqual(self.counts(), (1, 1))

    def test_core_repository_still_only_writes_core_and_query_repository_stays_read_only(self):
        artifact = self.technical_artifact()

        self.core_repository().save(artifact)

        self.assertEqual(self.counts(), (1, 0))
        query_source = (SRC_PATH / "risk_persistence" / "sqlite_technical_query_repository.py").read_text()
        self.assertIn("mode=ro", query_source)
        self.assertIn("PRAGMA query_only=ON", query_source)
        for forbidden in ("INSERT", "UPDATE", "DELETE", "CREATE TABLE", "ALTER TABLE", "repair", "rebuild"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, query_source)

    def test_source_boundary_and_no_production_paths(self):
        coordinator_source = (SRC_PATH / "risk_persistence" / "sqlite_technical_artifact_persistence.py").read_text()
        storage_source = (SRC_PATH / "risk_persistence" / "sqlite_storage.py").read_text()
        self.assertIn("BEGIN IMMEDIATE", coordinator_source)
        self.assertIn("persist_core_artifact_in_connection", coordinator_source)
        self.assertIn("TechnicalRiskArtifactIndexRecord.from_artifact", coordinator_source)
        self.assertNotIn("SQLiteRiskArtifactRepository(", coordinator_source)
        self.assertNotIn("TechnicalRiskArtifactIndexRecord", storage_source)
        forbidden = (
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "portfolio_generation",
            "risk_evaluation",
            "risk_oos",
            "risk_integration",
            "dashboard",
            "yfinance",
            "data/production",
            "data/stocks.db",
            "data/live",
            "data/research",
        )
        for text in forbidden:
            with self.subTest(text=text):
                self.assertNotIn(text, coordinator_source)
                self.assertNotIn(text, storage_source)


if __name__ == "__main__":
    unittest.main()
