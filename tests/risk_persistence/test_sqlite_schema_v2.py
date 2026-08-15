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
from risk_persistence import RiskArtifactIndexCorruptionError
from risk_persistence import RiskArtifactPersistenceError
from risk_persistence import SQLiteRiskArtifactRepository


APPLICATION_ID = 0x41494952
SCHEMA_VERSION = 2
SCHEMA_VERSION_V1 = 1

V1_CREATE_RISK_ARTIFACTS_TABLE_SQL = """
CREATE TABLE risk_artifacts (
    artifact_id TEXT PRIMARY KEY CHECK (artifact_id <> ''),
    artifact_checksum TEXT NOT NULL CHECK (artifact_checksum <> ''),
    payload_json TEXT NOT NULL CHECK (payload_json <> '')
)
"""


class SQLiteSchemaV2TestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "risk_artifacts.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def repository(self):
        return SQLiteRiskArtifactRepository(self.db_path)

    def connection(self):
        return sqlite3.connect(self.db_path)

    def created_at(self, hour=12):
        return datetime(2026, 8, 15, hour, 0, tzinfo=UTC)

    def analysis_date(self):
        return date(2026, 8, 15)

    def context(self, *, portfolio_id="portfolio_schema_v2", symbol="2330.TW", analysis_date=None, calculation_id=None):
        selected_date = analysis_date or self.analysis_date()
        return RiskContext(
            portfolio_id=portfolio_id,
            symbol=symbol,
            analysis_date=selected_date,
            feature_version="technical_risk_feature_set_v1",
            model_version=None,
            calculation_id=calculation_id or f"risk_calc_{portfolio_id}_{selected_date.isoformat()}",
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
        artifact_id="technical_artifact_schema_v2",
        severity=RiskSeverity.MEDIUM,
        position_id="position_001",
    ):
        context = self.context()
        signal = RiskSignal(
            risk_id="TECHNICAL_DOWNSIDE_RISK_V1",
            symbol=context.symbol,
            category=RiskCategory.TECHNICAL,
            severity=severity,
            trigger_reason="TREND_WEAKNESS",
            created_at=self.created_at(),
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
            portfolio_id=context.portfolio_id,
            position_id=position_id,
            as_of_date=context.analysis_date,
            valuation_date=date(2026, 8, 14),
        )
        result = TechnicalRiskProductionResult(
            produced_signal=produced_signal,
            risk_assessment=RiskAssessment.from_signals(
                portfolio_id=context.portfolio_id,
                symbol=context.symbol,
                signals=(signal,),
                assessment_date=context.analysis_date,
            ),
        )
        return TechnicalRiskArtifactAdapter().build(
            result=result,
            context=context,
            position=self.position(symbol=context.symbol),
            artifact_id=artifact_id,
            created_at=self.created_at(),
        )

    def generic_non_technical_artifact(self, *, artifact_id="generic_market_artifact"):
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

    def invalid_technical_artifact(self):
        artifact = self.technical_artifact(artifact_id="invalid_technical_artifact")
        metadata = dict(artifact.calculation_metadata)
        metadata.pop("technical_position_id")
        invalid = replace(artifact, calculation_metadata=metadata, checksum=None)
        context = self.context(calculation_id=metadata["calculation_id"])
        checksum = RiskChecksumGenerator().generate(invalid, context)
        return replace(invalid, checksum=checksum)

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
        checksum = RiskChecksumGenerator().generate(invalid, context)
        return replace(invalid, checksum=checksum)

    def create_v1_db(self, artifacts=()):
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

    def schema_identity(self):
        connection = self.connection()
        try:
            return (
                connection.execute("PRAGMA application_id").fetchone()[0],
                connection.execute("PRAGMA user_version").fetchone()[0],
            )
        finally:
            connection.close()

    def user_tables(self):
        connection = self.connection()
        try:
            return tuple(
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
        finally:
            connection.close()

    def index_rows(self):
        connection = self.connection()
        try:
            return connection.execute(
                """
                SELECT artifact_id, portfolio_id, position_id, symbol, severity,
                       analysis_date, valuation_date, created_at, calculation_id,
                       policy_id, policy_version, policy_checksum, evaluation_id,
                       evaluation_checksum, producer_version
                FROM technical_risk_artifact_index
                ORDER BY artifact_id
                """
            ).fetchall()
        finally:
            connection.close()

    def test_fresh_db_initializes_schema_v2(self):
        self.repository()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION))
        self.assertEqual(self.user_tables(), ("risk_artifacts", "technical_risk_artifact_index"))
        connection = self.connection()
        try:
            core_columns = tuple(row[1] for row in connection.execute("PRAGMA table_info(risk_artifacts)").fetchall())
            technical_columns = tuple(
                row[1] for row in connection.execute("PRAGMA table_info(technical_risk_artifact_index)").fetchall()
            )
            self.assertEqual(core_columns, ("artifact_id", "artifact_checksum", "payload_json"))
            self.assertEqual(
                technical_columns,
                (
                    "artifact_id",
                    "portfolio_id",
                    "position_id",
                    "symbol",
                    "severity",
                    "analysis_date",
                    "valuation_date",
                    "created_at",
                    "calculation_id",
                    "policy_id",
                    "policy_version",
                    "policy_checksum",
                    "evaluation_id",
                    "evaluation_checksum",
                    "producer_version",
                ),
            )
            indexes = tuple(
                row[1]
                for row in connection.execute("PRAGMA index_list(technical_risk_artifact_index)").fetchall()
            )
            self.assertIn("idx_technical_risk_artifact_position_latest", indexes)
            fk = connection.execute("PRAGMA foreign_key_list(technical_risk_artifact_index)").fetchall()
            self.assertEqual(fk[0][2:5], ("risk_artifacts", "artifact_id", "artifact_id"))
        finally:
            connection.close()

    def test_existing_empty_file_initializes_schema_v2(self):
        self.db_path.touch()

        self.repository()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION))

    def test_existing_valid_v1_empty_db_migrates_to_v2(self):
        self.create_v1_db()

        self.repository()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION))
        self.assertEqual(self.index_rows(), [])

    def test_v1_technical_low_medium_high_backfill(self):
        artifacts = (
            self.technical_artifact(artifact_id="artifact_low", severity=RiskSeverity.LOW, position_id="position_low"),
            self.technical_artifact(artifact_id="artifact_medium", severity=RiskSeverity.MEDIUM, position_id="position_medium"),
            self.technical_artifact(artifact_id="artifact_high", severity=RiskSeverity.HIGH, position_id="position_high"),
        )
        self.create_v1_db(artifacts)

        self.repository()

        rows = self.index_rows()
        self.assertEqual(tuple(row[0] for row in rows), ("artifact_high", "artifact_low", "artifact_medium"))
        self.assertEqual({row[4] for row in rows}, {"LOW", "MEDIUM", "HIGH"})
        self.assertEqual(rows[0][6], "2026-08-14")
        self.assertIn("+00:00", rows[0][7])

    def test_v1_generic_non_technical_artifact_is_preserved_without_projection(self):
        artifact = self.generic_non_technical_artifact()
        self.create_v1_db((artifact,))

        repository = self.repository()

        self.assertEqual(repository.get_by_artifact_id(artifact.artifact_id), artifact)
        self.assertEqual(self.index_rows(), [])

    def test_v1_corrupt_payload_migration_fails_and_rolls_back(self):
        artifact = self.technical_artifact()
        self.create_v1_db((artifact,))
        payload = json.loads(RiskArtifactCodec().encode(artifact))
        payload["artifact"]["checksum"] = "wrong_domain_checksum"
        payload["serialization_checksum"] = codec_module.serialization_checksum(payload)
        connection = self.connection()
        try:
            connection.execute(
                "UPDATE risk_artifacts SET payload_json = ? WHERE artifact_id = ?",
                (codec_module.canonical_json_dumps(payload), artifact.artifact_id),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.repository()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION_V1))
        self.assertEqual(self.user_tables(), ("risk_artifacts",))

    def test_v1_invalid_technical_artifact_migration_fails_and_rolls_back(self):
        self.create_v1_db((self.invalid_technical_artifact(),))

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            self.repository()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION_V1))
        self.assertEqual(self.user_tables(), ("risk_artifacts",))

    def test_v1_multiple_technical_signals_migration_fails_and_rolls_back(self):
        self.create_v1_db((self.multiple_technical_signals_artifact(),))

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            self.repository()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION_V1))
        self.assertEqual(self.user_tables(), ("risk_artifacts",))

    def test_failed_migration_can_retry_after_corruption_fixed(self):
        invalid = self.invalid_technical_artifact()
        valid = self.technical_artifact(artifact_id=invalid.artifact_id)
        self.create_v1_db((invalid,))

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            self.repository()

        connection = self.connection()
        try:
            connection.execute(
                "UPDATE risk_artifacts SET artifact_checksum = ?, payload_json = ? WHERE artifact_id = ?",
                (valid.checksum, RiskArtifactCodec().encode(valid), invalid.artifact_id),
            )
            connection.commit()
        finally:
            connection.close()

        self.repository()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION))
        self.assertEqual(len(self.index_rows()), 1)

    def test_v1_with_existing_index_table_fails_closed(self):
        self.create_v1_db()
        connection = self.connection()
        try:
            connection.execute("CREATE TABLE technical_risk_artifact_index (artifact_id TEXT PRIMARY KEY)")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.repository()

    def test_existing_valid_v2_opens(self):
        self.repository()

        self.repository()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION))

    def test_future_version_fails_closed(self):
        self.create_v1_db()
        connection = self.connection()
        try:
            connection.execute("PRAGMA user_version=3")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.repository()

    def test_wrong_application_id_fails_closed(self):
        self.create_v1_db()
        connection = self.connection()
        try:
            connection.execute("PRAGMA application_id=123")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.repository()

    def test_wrong_v2_technical_table_schema_fails_closed(self):
        self.repository()
        connection = self.connection()
        try:
            connection.execute("DROP TABLE technical_risk_artifact_index")
            connection.execute("CREATE TABLE technical_risk_artifact_index (artifact_id TEXT PRIMARY KEY)")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.repository()

    def test_missing_required_index_fails_closed(self):
        self.repository()
        connection = self.connection()
        try:
            connection.execute("DROP INDEX idx_technical_risk_artifact_position_latest")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.repository()

    def test_wrong_foreign_key_fails_closed(self):
        self.repository()
        connection = self.connection()
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("DROP TABLE technical_risk_artifact_index")
            connection.execute(
                """
                CREATE TABLE technical_risk_artifact_index (
                    artifact_id TEXT PRIMARY KEY CHECK (artifact_id <> ''),
                    portfolio_id TEXT NOT NULL CHECK (portfolio_id <> ''),
                    position_id TEXT NOT NULL CHECK (position_id <> ''),
                    symbol TEXT NOT NULL CHECK (symbol <> ''),
                    severity TEXT NOT NULL CHECK (severity <> ''),
                    analysis_date TEXT NOT NULL CHECK (analysis_date <> ''),
                    valuation_date TEXT NOT NULL CHECK (valuation_date <> ''),
                    created_at TEXT NOT NULL CHECK (created_at <> ''),
                    calculation_id TEXT NOT NULL CHECK (calculation_id <> ''),
                    policy_id TEXT NOT NULL CHECK (policy_id <> ''),
                    policy_version TEXT NOT NULL CHECK (policy_version <> ''),
                    policy_checksum TEXT NOT NULL CHECK (policy_checksum <> ''),
                    evaluation_id TEXT NOT NULL CHECK (evaluation_id <> ''),
                    evaluation_checksum TEXT NOT NULL CHECK (evaluation_checksum <> ''),
                    producer_version TEXT NOT NULL CHECK (producer_version <> '')
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX idx_technical_risk_artifact_position_latest
                ON technical_risk_artifact_index (
                    portfolio_id,
                    position_id,
                    analysis_date DESC,
                    created_at DESC,
                    artifact_id DESC
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.repository()

    def test_unknown_extra_table_fails_closed(self):
        self.repository()
        connection = self.connection()
        try:
            connection.execute("CREATE TABLE extra_table (id TEXT PRIMARY KEY)")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.repository()

    def test_repository_save_does_not_populate_technical_index(self):
        artifact = self.technical_artifact()
        repository = self.repository()

        repository.save(artifact)

        self.assertEqual(self.index_rows(), [])
        self.assertEqual(repository.get_by_artifact_id(artifact.artifact_id), artifact)

    def test_no_production_db_paths_are_referenced(self):
        source = (SRC_PATH / "risk_persistence" / "sqlite_schema.py").read_text()
        for forbidden_path in ("data/production", "data/stocks.db", "data/live", "data/research"):
            with self.subTest(forbidden_path=forbidden_path):
                self.assertNotIn(forbidden_path, source)


if __name__ == "__main__":
    unittest.main()
