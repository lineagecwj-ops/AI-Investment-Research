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
from risk_persistence import RiskArtifactCorruptionError
from risk_persistence import RiskArtifactIndexCorruptionError
from risk_persistence import RiskArtifactPersistenceError
from risk_persistence import SQLiteRiskArtifactRepository
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


class SQLiteTechnicalRiskArtifactQueryRepositoryTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "risk_artifacts.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def core_repository(self, db_path=None):
        return SQLiteRiskArtifactRepository(db_path or self.db_path)

    def query_repository(self, db_path=None, **kwargs):
        return SQLiteTechnicalRiskArtifactQueryRepository(db_path or self.db_path, **kwargs)

    def connection(self):
        return sqlite3.connect(self.db_path)

    def created_at(self, day=15, hour=12, minute=0):
        return datetime(2026, 8, day, hour, minute, tzinfo=UTC)

    def context(self, *, portfolio_id="portfolio_query_001", symbol="2330.TW", analysis_date=date(2026, 8, 15)):
        return RiskContext(
            portfolio_id=portfolio_id,
            symbol=symbol,
            analysis_date=analysis_date,
            feature_version="technical_risk_feature_set_v1",
            model_version=None,
            calculation_id=f"risk_calc_{portfolio_id}_{symbol}_{analysis_date.isoformat()}",
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

    def artifact(
        self,
        *,
        artifact_id="technical_query_artifact_001",
        portfolio_id="portfolio_query_001",
        position_id="position_001",
        symbol="2330.TW",
        severity=RiskSeverity.MEDIUM,
        analysis_date=date(2026, 8, 15),
        valuation_date=date(2026, 8, 14),
        created_at=None,
    ):
        context = self.context(portfolio_id=portfolio_id, symbol=symbol, analysis_date=analysis_date)
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
            as_of_date=analysis_date,
            valuation_date=valuation_date,
        )
        result = TechnicalRiskProductionResult(
            produced_signal=produced_signal,
            risk_assessment=RiskAssessment.from_signals(
                portfolio_id=portfolio_id,
                symbol=symbol,
                signals=(signal,),
                assessment_date=analysis_date,
            ),
        )
        return TechnicalRiskArtifactAdapter().build(
            result=result,
            context=context,
            position=self.position(symbol=symbol),
            artifact_id=artifact_id,
            created_at=created_at or self.created_at(),
        )

    def generic_artifact(self, *, artifact_id="generic_artifact"):
        context = self.context()
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

    def save_and_index(self, *artifacts):
        repository = self.core_repository()
        for artifact in artifacts:
            repository.save(artifact)
            self.insert_index_record(TechnicalRiskArtifactIndexRecord.from_artifact(artifact))

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

    def update_core(self, artifact_id, *, payload_json=None, artifact_checksum=None):
        assignments = []
        parameters = []
        if payload_json is not None:
            assignments.append("payload_json = ?")
            parameters.append(payload_json)
        if artifact_checksum is not None:
            assignments.append("artifact_checksum = ?")
            parameters.append(artifact_checksum)
        parameters.append(artifact_id)
        connection = self.connection()
        try:
            connection.execute(
                f"UPDATE risk_artifacts SET {', '.join(assignments)} WHERE artifact_id = ?",
                tuple(parameters),
            )
            connection.commit()
        finally:
            connection.close()

    def create_v1_db(self):
        connection = self.connection()
        try:
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute(V1_CREATE_RISK_ARTIFACTS_TABLE_SQL)
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION_V1}")
            connection.commit()
        finally:
            connection.close()

    def user_version(self):
        connection = self.connection()
        try:
            return connection.execute("PRAGMA user_version").fetchone()[0]
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

    def test_public_api_export_and_protocol_compatibility(self):
        self.core_repository()
        repository = self.query_repository()

        import risk_persistence

        self.assertIs(
            risk_persistence.SQLiteTechnicalRiskArtifactQueryRepository,
            SQLiteTechnicalRiskArtifactQueryRepository,
        )
        self.assertFalse(hasattr(repository, "save"))
        self.assertFalse(hasattr(repository, "index_artifact"))

    def test_constructor_rejects_missing_empty_directory_and_invalid_busy_timeout(self):
        missing = Path(self.temp_dir.name) / "missing.db"
        with self.assertRaises(RiskArtifactPersistenceError):
            SQLiteTechnicalRiskArtifactQueryRepository(missing)
        self.db_path.touch()
        with self.assertRaises(RiskArtifactPersistenceError):
            SQLiteTechnicalRiskArtifactQueryRepository(self.db_path)
        with self.assertRaises(RiskArtifactPersistenceError):
            SQLiteTechnicalRiskArtifactQueryRepository(self.temp_dir.name)
        self.core_repository()
        with self.assertRaises(RiskArtifactPersistenceError):
            self.query_repository(busy_timeout_ms=0)

    def test_query_repository_rejects_v1_without_migration(self):
        self.create_v1_db()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.query_repository()

        self.assertEqual(self.user_version(), SCHEMA_VERSION_V1)
        self.assertEqual(self.user_tables(), ("risk_artifacts",))

    def test_query_repository_rejects_wrong_and_future_schema(self):
        self.core_repository()
        connection = self.connection()
        try:
            connection.execute("PRAGMA user_version=3")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(RiskArtifactPersistenceError):
            self.query_repository()

        other_db = Path(self.temp_dir.name) / "wrong_app.db"
        connection = sqlite3.connect(other_db)
        try:
            connection.execute("PRAGMA application_id=123")
            connection.execute("CREATE TABLE foo (id TEXT PRIMARY KEY)")
            connection.execute("PRAGMA user_version=2")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(RiskArtifactPersistenceError):
            SQLiteTechnicalRiskArtifactQueryRepository(other_db)

    def test_query_repository_rejects_wrong_v2_shape(self):
        self.core_repository()
        connection = self.connection()
        try:
            connection.execute("DROP INDEX idx_technical_risk_artifact_position_latest")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactPersistenceError):
            self.query_repository()

    def test_empty_results_are_not_errors(self):
        self.core_repository()
        repository = self.query_repository()

        self.assertIsNone(repository.get_latest_by_position("portfolio_query_001", "missing_position"))
        self.assertEqual(repository.list_history_by_position("portfolio_query_001", "missing_position"), ())
        self.assertEqual(repository.list_latest_by_portfolio("portfolio_query_001"), ())

    def test_latest_by_position_uses_analysis_created_at_and_artifact_id_tiebreaks(self):
        old = self.artifact(artifact_id="artifact_old", analysis_date=date(2026, 8, 14))
        newest_date = self.artifact(artifact_id="artifact_newest_date", analysis_date=date(2026, 8, 15))
        newer_created_at = self.artifact(
            artifact_id="artifact_newer_created_at",
            analysis_date=date(2026, 8, 15),
            created_at=self.created_at(hour=13),
        )
        tie_by_id = self.artifact(
            artifact_id="artifact_z",
            analysis_date=date(2026, 8, 15),
            created_at=self.created_at(hour=13),
        )
        self.save_and_index(old, newest_date, newer_created_at, tie_by_id)

        latest = self.query_repository().get_latest_by_position("portfolio_query_001", "position_001")

        self.assertEqual(latest.artifact_id, "artifact_z")

    def test_history_by_position_newest_first_and_limit(self):
        artifacts = (
            self.artifact(artifact_id="artifact_old", analysis_date=date(2026, 8, 13)),
            self.artifact(artifact_id="artifact_mid", analysis_date=date(2026, 8, 14)),
            self.artifact(artifact_id="artifact_new", analysis_date=date(2026, 8, 15)),
        )
        self.save_and_index(*artifacts)
        repository = self.query_repository()

        self.assertEqual(
            tuple(item.artifact_id for item in repository.list_history_by_position("portfolio_query_001", "position_001")),
            ("artifact_new", "artifact_mid", "artifact_old"),
        )
        self.assertEqual(
            tuple(item.artifact_id for item in repository.list_history_by_position("portfolio_query_001", "position_001", limit=1)),
            ("artifact_new",),
        )
        self.assertEqual(
            tuple(item.artifact_id for item in repository.list_history_by_position("portfolio_query_001", "position_001", limit=2)),
            ("artifact_new", "artifact_mid"),
        )

    def test_query_input_validation(self):
        self.core_repository()
        repository = self.query_repository()

        invalid_pairs = (("", "position_001"), ("portfolio_query_001", ""), (None, "position_001"))
        for portfolio_id, position_id in invalid_pairs:
            with self.subTest(portfolio_id=portfolio_id, position_id=position_id):
                with self.assertRaises(RiskArtifactPersistenceError):
                    repository.get_latest_by_position(portfolio_id, position_id)
        for limit in (0, -1, True, "2"):
            with self.subTest(limit=limit):
                with self.assertRaises(RiskArtifactPersistenceError):
                    repository.list_history_by_position("portfolio_query_001", "position_001", limit=limit)
        with self.assertRaises(RiskArtifactPersistenceError):
            repository.list_latest_by_portfolio("portfolio_query_001", severity="HIGH")

    def test_latest_by_portfolio_returns_one_per_position_with_final_order(self):
        position_b = self.artifact(
            artifact_id="artifact_b",
            position_id="position_b",
            symbol="SAME",
            analysis_date=date(2026, 8, 15),
        )
        position_a_old = self.artifact(
            artifact_id="artifact_a_old",
            position_id="position_a",
            symbol="SAME",
            analysis_date=date(2026, 8, 14),
        )
        position_a_new = self.artifact(
            artifact_id="artifact_a_new",
            position_id="position_a",
            symbol="SAME",
            analysis_date=date(2026, 8, 15),
        )
        self.save_and_index(position_b, position_a_old, position_a_new)

        result = self.query_repository().list_latest_by_portfolio("portfolio_query_001")

        self.assertEqual(tuple(item.artifact_id for item in result), ("artifact_a_new", "artifact_b"))

    def test_cross_portfolio_isolation(self):
        first = self.artifact(
            artifact_id="artifact_portfolio_a",
            portfolio_id="portfolio_a",
            position_id="position_shared",
        )
        second = self.artifact(
            artifact_id="artifact_portfolio_b",
            portfolio_id="portfolio_b",
            position_id="position_shared",
        )
        self.save_and_index(first, second)

        result = self.query_repository().list_latest_by_portfolio("portfolio_a")

        self.assertEqual(tuple(item.artifact_id for item in result), ("artifact_portfolio_a",))

    def test_severity_filter_applies_after_latest_selection_and_preserves_low(self):
        old_high = self.artifact(
            artifact_id="artifact_position_a_old_high",
            position_id="position_a",
            severity=RiskSeverity.HIGH,
            analysis_date=date(2026, 8, 14),
        )
        latest_low = self.artifact(
            artifact_id="artifact_position_a_latest_low",
            position_id="position_a",
            severity=RiskSeverity.LOW,
            analysis_date=date(2026, 8, 15),
        )
        latest_high = self.artifact(
            artifact_id="artifact_position_b_latest_high",
            position_id="position_b",
            severity=RiskSeverity.HIGH,
            analysis_date=date(2026, 8, 15),
        )
        self.save_and_index(old_high, latest_low, latest_high)
        repository = self.query_repository()

        self.assertEqual(
            tuple(item.artifact_id for item in repository.list_latest_by_portfolio("portfolio_query_001", severity=RiskSeverity.HIGH)),
            ("artifact_position_b_latest_high",),
        )
        self.assertEqual(
            tuple(item.artifact_id for item in repository.list_latest_by_portfolio("portfolio_query_001", severity=RiskSeverity.LOW)),
            ("artifact_position_a_latest_low",),
        )

    def test_missing_core_row_is_index_corruption(self):
        artifact = self.artifact()
        self.save_and_index(artifact)
        connection = self.connection()
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("DELETE FROM risk_artifacts WHERE artifact_id = ?", (artifact.artifact_id,))
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            self.query_repository().get_latest_by_position("portfolio_query_001", "position_001")

    def test_invalid_index_values_are_index_corruption(self):
        artifact = self.artifact()
        invalid_cases = (
            ("severity", "UNKNOWN"),
            ("analysis_date", "not-a-date"),
            ("created_at", "2026-08-15T12:00:00"),
        )
        for field_name, value in invalid_cases:
            with self.subTest(field_name=field_name):
                db_path = Path(self.temp_dir.name) / f"{field_name}.db"
                self.db_path = db_path
                self.save_and_index(artifact)
                self.update_index(artifact.artifact_id, field_name, value)
                with self.assertRaises(RiskArtifactIndexCorruptionError):
                    self.query_repository().get_latest_by_position("portfolio_query_001", "position_001")

    def test_index_projection_tamper_is_index_corruption(self):
        tamper_cases = (
            ("policy_checksum", "tampered_policy_checksum"),
            ("evaluation_checksum", "tampered_evaluation_checksum"),
            ("producer_version", "tampered_producer_version"),
        )
        for field_name, value in tamper_cases:
            with self.subTest(field_name=field_name):
                self.db_path = Path(self.temp_dir.name) / f"{field_name}.db"
                artifact = self.artifact(artifact_id=f"artifact_{field_name}")
                self.save_and_index(artifact)
                self.update_index(artifact.artifact_id, field_name, value)
                with self.assertRaises(RiskArtifactIndexCorruptionError):
                    self.query_repository().get_latest_by_position("portfolio_query_001", "position_001")

    def test_index_row_pointing_to_non_technical_artifact_is_index_corruption(self):
        artifact = self.artifact()
        self.save_and_index(artifact)
        generic = self.generic_artifact(artifact_id=artifact.artifact_id)
        self.update_core(
            artifact.artifact_id,
            artifact_checksum=generic.checksum,
            payload_json=RiskArtifactCodec().encode(generic),
        )

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            self.query_repository().get_latest_by_position("portfolio_query_001", "position_001")

    def test_core_payload_corruption_is_core_corruption(self):
        artifact = self.artifact()
        self.save_and_index(artifact)
        self.update_core(artifact.artifact_id, payload_json="{not-json")

        with self.assertRaises(RiskArtifactCorruptionError):
            self.query_repository().get_latest_by_position("portfolio_query_001", "position_001")

    def test_core_checksum_column_mismatch_is_core_corruption(self):
        artifact = self.artifact()
        self.save_and_index(artifact)
        self.update_core(artifact.artifact_id, artifact_checksum="wrong_checksum")

        with self.assertRaises(RiskArtifactCorruptionError):
            self.query_repository().get_latest_by_position("portfolio_query_001", "position_001")

    def test_list_query_fails_whole_call_on_any_corruption(self):
        valid = self.artifact(artifact_id="artifact_valid", analysis_date=date(2026, 8, 15))
        corrupt = self.artifact(artifact_id="artifact_corrupt", analysis_date=date(2026, 8, 14))
        self.save_and_index(valid, corrupt)
        self.update_index(corrupt.artifact_id, "policy_checksum", "tampered")

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            self.query_repository().list_history_by_position("portfolio_query_001", "position_001")

    def test_source_boundary_read_only_no_repair_or_runtime_clock(self):
        source = (SRC_PATH / "risk_persistence" / "sqlite_technical_query_repository.py").read_text()
        required = (
            "mode=ro",
            "PRAGMA query_only=ON",
            "LEFT JOIN risk_artifacts",
            "ROW_NUMBER() OVER",
            "TechnicalRiskArtifactIndexRecord.from_artifact",
        )
        for text in required:
            with self.subTest(required=text):
                self.assertIn(text, source)
        forbidden = (
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE TABLE",
            "ALTER TABLE",
            "PRAGMA user_version",
            "PRAGMA journal_mode",
            "repair",
            "rebuild",
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "portfolio_generation",
            "risk_evaluation",
            "risk_oos",
            "risk_integration",
            "dashboard",
            "yfinance",
        )
        for text in forbidden:
            with self.subTest(forbidden=text):
                self.assertNotIn(text, source)

    def test_no_production_db_paths_are_referenced(self):
        source = (SRC_PATH / "risk_persistence" / "sqlite_technical_query_repository.py").read_text()
        for forbidden_path in ("data/production", "data/stocks.db", "data/live", "data/research"):
            with self.subTest(forbidden_path=forbidden_path):
                self.assertNotIn(forbidden_path, source)


if __name__ == "__main__":
    unittest.main()
