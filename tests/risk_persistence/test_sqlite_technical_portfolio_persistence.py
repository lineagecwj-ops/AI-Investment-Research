import inspect
import sqlite3
import sys
import tempfile
import unittest
from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_persistence.sqlite_technical_portfolio_persistence as portfolio_persistence_module
import risk_persistence.sqlite_portfolio_run_repository as run_repository_module
from portfolio_generation import ExactVersionPolicyResolver
from portfolio_generation import MonitoringEvaluationOutput
from portfolio_generation import PortfolioRiskGenerationService
from portfolio_generation import PortfolioRiskGenerationStatus
from portfolio_generation import RiskEvaluationOutput
from portfolio_generation import build_risk_artifact_id
from risk import HoldingType as RiskHoldingType
from risk import PortfolioPosition
from risk import RiskArtifact
from risk import RiskArtifactCodec
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskChecksumGenerator
from risk import RiskContext
from risk import RiskDefinition
from risk import RiskRegistry
from risk import RiskSeverity
from risk import RiskSignal
from risk_persistence import PortfolioRiskGenerationRunRecord
from risk_persistence import PortfolioRiskGenerationRunRepository
from risk_persistence import PortfolioRiskGenerationRunPersistenceError
from risk_persistence import PortfolioRiskGenerationRunSaveStatus
from risk_persistence import RiskArtifactCorruptionError
from risk_persistence import RiskArtifactConflictError
from risk_persistence import RiskArtifactSaveStatus
from risk_persistence import SQLitePortfolioRiskGenerationRunRepository
from risk_persistence import SQLiteTechnicalPortfolioRiskPersistenceCoordinator
from risk_persistence import SQLiteTechnicalRiskArtifactPersistenceCoordinator
from risk_persistence import SQLiteTechnicalRiskArtifactQueryRepository
from risk_persistence import TechnicalPortfolioRiskPersistenceError
from risk_persistence import TechnicalPortfolioRiskPersistenceResult
from risk_persistence.sqlite_technical_index import insert_technical_index_record
from risk_persistence.technical_query_contracts import TechnicalRiskArtifactIndexRecord
from portfolio_state import HoldingType
from portfolio_state import PortfolioPositionState
from portfolio_state import PortfolioSnapshot
from portfolio_state import RiskEvaluationInput


@dataclass(frozen=True)
class FakeMonitoringArtifact:
    artifact_id: str
    source_risk_artifact_id: str
    portfolio_id: str
    symbol: str
    position_id: str


class FakeTechnicalRiskEvaluator:
    def __init__(self, *, fail_position_id=None, severity_by_position=None, warning_by_position=None):
        self.fail_position_id = fail_position_id
        self.severity_by_position = dict(severity_by_position or {})
        self.warning_by_position = dict(warning_by_position or {})
        self.calls = []

    def evaluate(self, position, context, risk_artifact_id):
        position_id = POSITION_ID_BY_ARTIFACT_ID[risk_artifact_id]
        self.calls.append(position_id)
        if position_id == self.fail_position_id:
            raise RuntimeError(f"risk failure for {position_id}")
        artifact = build_technical_artifact(
            position=position,
            context=context,
            position_id=position_id,
            artifact_id=risk_artifact_id,
            severity=self.severity_by_position.get(position_id, RiskSeverity.LOW),
        )
        return RiskEvaluationOutput(
            position_id=position_id,
            symbol=position.symbol,
            risk_artifact=artifact,
            warnings=tuple(self.warning_by_position.get(position_id, ())),
        )


class FakeMonitoringEvaluator:
    def __init__(self, *, fail_position_id=None, warning_by_position=None):
        self.fail_position_id = fail_position_id
        self.warning_by_position = dict(warning_by_position or {})
        self.calls = []

    def evaluate(self, risk_artifact, context, monitoring_artifact_id):
        position_id = risk_artifact.calculation_metadata["technical_position_id"]
        self.calls.append(position_id)
        if position_id == self.fail_position_id:
            raise RuntimeError(f"monitoring failure for {position_id}")
        return MonitoringEvaluationOutput(
            position_id=position_id,
            symbol=context.symbol,
            monitoring_artifact=FakeMonitoringArtifact(
                artifact_id=monitoring_artifact_id,
                source_risk_artifact_id=risk_artifact.artifact_id,
                portfolio_id=context.portfolio_id,
                symbol=context.symbol,
                position_id=position_id,
            ),
            warnings=tuple(self.warning_by_position.get(position_id, ())),
        )


class ExplodingService:
    def __init__(self, **_kwargs):
        pass

    def generate(self, _snapshot, _evaluation_input):
        raise RuntimeError("unexpected generation exception")


class BrokenRunHelper:
    def __call__(self, _connection, _prepared_record):
        raise RuntimeError("forced run helper failure")


class BrokenRunRecordCodec:
    def encode(self, _record):
        return "{not-json"

    def decode(self, _payload):
        raise run_repository_module.PortfolioRiskGenerationRunRecordCodecError("broken codec")


POSITION_ID_BY_ARTIFACT_ID = {}


def build_technical_artifact(*, position, context, position_id, artifact_id, severity):
    signal = RiskSignal(
        risk_id="TECHNICAL_DOWNSIDE_RISK_V1",
        symbol=position.symbol,
        category=RiskCategory.TECHNICAL,
        severity=severity,
        trigger_reason="technical persistence test",
        created_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
    )
    assessment = RiskAssessment.from_signals(
        portfolio_id=context.portfolio_id,
        symbol=position.symbol,
        signals=(signal,),
        assessment_date=context.analysis_date,
    )
    artifact = RiskArtifact(
        artifact_id=artifact_id,
        position_identity=position.identity,
        risk_assessment=assessment,
        signals=(signal,),
        feature_lineage={
            "feature_version": context.feature_version,
            "model_version": context.model_version,
            "technical_source_feature_ids": ("TECH_AS_OF_CLOSE_V1", "TECH_SMA20_V1", "TECH_SMA60_V1", "TECH_RSI14_V1"),
            "technical_source_checksums": ("close_checksum", "sma20_checksum", "sma60_checksum", "rsi14_checksum"),
        },
        calculation_metadata={
            "portfolio_id": context.portfolio_id,
            "symbol": context.symbol,
            "analysis_date": context.analysis_date.isoformat(),
            "calculation_id": context.calculation_id,
            "technical_policy_id": "technical_policy_v1",
            "technical_policy_version": "v1",
            "technical_policy_checksum": "technical_policy_checksum_v1",
            "technical_evaluation_id": f"technical_evaluation_{position_id}",
            "technical_evaluation_checksum": f"technical_evaluation_checksum_{position_id}",
            "technical_position_id": position_id,
            "technical_as_of_date": context.analysis_date.isoformat(),
            "technical_valuation_date": context.analysis_date.isoformat(),
            "technical_calculation_id": context.calculation_id,
            "technical_producer_version": "technical_producer_v1",
        },
        created_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
    )
    checksum = RiskChecksumGenerator().generate(artifact, context)
    return replace(artifact, checksum=checksum)


class SQLiteTechnicalPortfolioRiskPersistenceCoordinatorTestCase(unittest.TestCase):
    def setUp(self):
        POSITION_ID_BY_ARTIFACT_ID.clear()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "risk_artifacts.db"

    def tearDown(self):
        self.temp_dir.cleanup()
        POSITION_ID_BY_ARTIFACT_ID.clear()

    def created_at(self):
        return datetime(2026, 8, 15, 13, 0, tzinfo=UTC)

    def position(self, position_id, symbol, *, shares="10"):
        return PortfolioPositionState(
            portfolio_id="portfolio_technical_001",
            position_id=position_id,
            symbol=symbol,
            shares=Decimal(shares),
            average_cost=Decimal("650"),
            currency="TWD",
            position_status="ACTIVE",
            holding_type=HoldingType.WHOLE_SHARE,
            acquisition_date=date(2026, 1, 5),
        )

    def snapshot(self, positions):
        return PortfolioSnapshot(
            snapshot_id="snapshot_technical_001",
            portfolio_id="portfolio_technical_001",
            as_of_date=date(2026, 8, 15),
            valuation_date=date(2026, 8, 14),
            positions=tuple(positions),
            created_at=datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
            source_lineage={"source_type": "persistence_test", "source_version": "v1"},
        )

    def evaluation_input(self, snapshot, **overrides):
        values = {
            "feature_version": "technical_feature_set_v1",
            "model_version": None,
            "risk_definition_version": "risk_definition_v1",
            "risk_policy_version": "risk_policy_v1",
            "monitoring_policy_version": "monitoring_policy_v1",
        }
        values.update(overrides)
        evaluation_input = RiskEvaluationInput.from_snapshot(snapshot, **values)
        for position_id in evaluation_input.active_position_ids:
            POSITION_ID_BY_ARTIFACT_ID[build_risk_artifact_id(evaluation_input.calculation_id, position_id)] = position_id
        return evaluation_input

    def resolver(self):
        registry = RiskRegistry()
        registry.register(
            RiskDefinition(
                risk_id="TECHNICAL_DOWNSIDE_RISK_V1",
                risk_name="Technical Downside Risk",
                category=RiskCategory.TECHNICAL,
                version="risk_definition_v1",
                description="Technical persistence test definition.",
                severity_rule="technical policy",
            )
        )
        return ExactVersionPolicyResolver(
            risk_registry=registry,
            allowed_risk_policy_versions=("risk_policy_v1",),
            allowed_monitoring_policy_versions=("monitoring_policy_v1",),
        )

    def coordinator(self, risk_evaluator=None, monitoring_evaluator=None):
        return SQLiteTechnicalPortfolioRiskPersistenceCoordinator(
            db_path=self.db_path,
            risk_evaluator=risk_evaluator or FakeTechnicalRiskEvaluator(),
            monitoring_evaluator=monitoring_evaluator or FakeMonitoringEvaluator(),
            policy_resolver=self.resolver(),
            risk_definition_ids=("TECHNICAL_DOWNSIDE_RISK_V1",),
        )

    def run_generation(self, positions, *, risk_evaluator=None, monitoring_evaluator=None, created_at=None, risk_policy_version=None):
        snapshot = self.snapshot(positions)
        kwargs = {}
        if risk_policy_version is not None:
            kwargs["risk_policy_version"] = risk_policy_version
        evaluation_input = self.evaluation_input(snapshot, **kwargs)
        result = self.coordinator(risk_evaluator, monitoring_evaluator).generate_and_persist(
            snapshot,
            evaluation_input,
            created_at=created_at or self.created_at(),
        )
        return snapshot, evaluation_input, result

    def row_count(self, table_name):
        if not self.db_path.exists():
            return 0
        connection = sqlite3.connect(self.db_path)
        try:
            return connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        finally:
            connection.close()

    def test_public_api_and_constructor_boundary(self):
        coordinator = self.coordinator()

        import risk_persistence

        self.assertIs(
            risk_persistence.SQLiteTechnicalPortfolioRiskPersistenceCoordinator,
            SQLiteTechnicalPortfolioRiskPersistenceCoordinator,
        )
        self.assertIsInstance(
            TechnicalPortfolioRiskPersistenceResult(
                generation_result=self.run_generation((self.position("position_a", "2330.TW"),))[2].generation_result,
                run_record=self.run_generation((self.position("position_b", "2454.TW"),))[2].run_record,
                artifact_save_results=(),
                run_save_result=self.run_generation((self.position("position_c", "3008.TW"),))[2].run_save_result,
            ),
            TechnicalPortfolioRiskPersistenceResult,
        )
        self.assertNotIn("CapturingRiskEvaluatorError", risk_persistence.__all__)
        self.assertFalse(hasattr(risk_persistence, "CapturingRiskEvaluatorError"))
        new_public_names = {
            "CapturingRiskEvaluator",
            "SQLiteTechnicalPortfolioRiskPersistenceCoordinator",
            "TechnicalPortfolioRiskPersistenceResult",
            "TechnicalPortfolioRiskPersistenceError",
        }
        self.assertTrue(new_public_names.issubset(set(risk_persistence.__all__)))
        self.assertEqual(coordinator.busy_timeout_ms, 5000)
        with self.assertRaises(TechnicalPortfolioRiskPersistenceError):
            SQLiteTechnicalPortfolioRiskPersistenceCoordinator(
                db_path=self.db_path,
                risk_evaluator=object(),
                monitoring_evaluator=FakeMonitoringEvaluator(),
                policy_resolver=self.resolver(),
            )

    def test_multi_position_success_persists_artifacts_indexes_and_run(self):
        positions = (
            self.position("position_b", "2454.TW"),
            self.position("position_a", "2330.TW"),
        )
        _snapshot, evaluation_input, result = self.run_generation(positions)

        self.assertEqual(result.generation_result.status, PortfolioRiskGenerationStatus.SUCCESS)
        self.assertEqual(result.run_record.attempted_position_ids, ("position_a", "position_b"))
        self.assertEqual(result.run_record.risk_evaluated_position_ids, ("position_a", "position_b"))
        self.assertEqual(result.run_record.succeeded_position_ids, ("position_a", "position_b"))
        self.assertEqual(tuple(item.status for item in result.artifact_save_results), (RiskArtifactSaveStatus.INSERTED,) * 2)
        self.assertEqual(result.run_save_result.status, PortfolioRiskGenerationRunSaveStatus.INSERTED)
        self.assertEqual(self.row_count("risk_artifacts"), 2)
        self.assertEqual(self.row_count("technical_risk_artifact_index"), 2)
        self.assertEqual(self.row_count("portfolio_risk_generation_runs"), 1)
        self.assertEqual(
            SQLitePortfolioRiskGenerationRunRepository(self.db_path).get_by_calculation_id(evaluation_input.calculation_id),
            result.run_record,
        )
        self.assertEqual(
            tuple(artifact.artifact_id for artifact in SQLiteTechnicalRiskArtifactQueryRepository(self.db_path).list_latest_by_portfolio(evaluation_input.portfolio_id)),
            tuple(ref.artifact_id for ref in result.run_record.risk_artifact_refs),
        )

    def test_same_symbol_positions_and_low_medium_high_preserved(self):
        risk = FakeTechnicalRiskEvaluator(
            severity_by_position={
                "position_a": RiskSeverity.LOW,
                "position_b": RiskSeverity.MEDIUM,
                "position_c": RiskSeverity.HIGH,
            }
        )
        positions = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2330.TW"),
            self.position("position_c", "3008.TW"),
        )
        _snapshot, evaluation_input, result = self.run_generation(positions, risk_evaluator=risk)

        artifacts = SQLiteTechnicalRiskArtifactQueryRepository(self.db_path).list_latest_by_portfolio(evaluation_input.portfolio_id)
        self.assertEqual(result.run_record.risk_evaluated_position_ids, ("position_a", "position_b", "position_c"))
        self.assertEqual(
            tuple(artifact.risk_assessment.overall_risk_level for artifact in artifacts),
            (RiskSeverity.LOW, RiskSeverity.MEDIUM, RiskSeverity.HIGH),
        )

    def test_risk_failure_persists_prior_successful_artifact_and_failure_run(self):
        risk = FakeTechnicalRiskEvaluator(fail_position_id="position_b")
        positions = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2454.TW"),
            self.position("position_c", "3008.TW"),
        )
        _snapshot, _input, result = self.run_generation(positions, risk_evaluator=risk)

        self.assertEqual(result.generation_result.status, PortfolioRiskGenerationStatus.RISK_EVALUATION_FAILED)
        self.assertEqual(result.run_record.attempted_position_ids, ("position_a", "position_b"))
        self.assertEqual(result.run_record.risk_evaluated_position_ids, ("position_a",))
        self.assertEqual(result.run_record.succeeded_position_ids, ("position_a",))
        self.assertEqual(result.run_record.failed_position_ids, ("position_b",))
        self.assertEqual(tuple(ref.position_id for ref in result.run_record.risk_artifact_refs), ("position_a",))
        self.assertEqual(tuple(ref.position_id for ref in result.run_record.monitoring_artifact_refs), ("position_a",))
        self.assertEqual(result.run_record.issues[0].stage, "RISK_EVALUATION")
        self.assertEqual(self.row_count("risk_artifacts"), 1)
        self.assertEqual(self.row_count("portfolio_risk_generation_runs"), 1)

    def test_monitoring_failure_persists_failed_position_risk_artifact_without_monitoring_ref(self):
        monitoring = FakeMonitoringEvaluator(fail_position_id="position_b")
        positions = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2454.TW"),
            self.position("position_c", "3008.TW"),
        )
        _snapshot, _input, result = self.run_generation(positions, monitoring_evaluator=monitoring)

        self.assertEqual(result.generation_result.status, PortfolioRiskGenerationStatus.MONITORING_FAILED)
        self.assertEqual(result.run_record.attempted_position_ids, ("position_a", "position_b"))
        self.assertEqual(result.run_record.risk_evaluated_position_ids, ("position_a", "position_b"))
        self.assertEqual(result.run_record.succeeded_position_ids, ("position_a",))
        self.assertEqual(result.run_record.failed_position_ids, ("position_b",))
        self.assertEqual(tuple(ref.position_id for ref in result.run_record.risk_artifact_refs), ("position_a", "position_b"))
        self.assertEqual(tuple(ref.position_id for ref in result.run_record.monitoring_artifact_refs), ("position_a",))
        self.assertEqual(result.run_record.issues[0].stage, "MONITORING")
        self.assertEqual(self.row_count("risk_artifacts"), 2)

    def test_validation_failure_persists_run_record_only(self):
        positions = (self.position("position_a", "2330.TW"),)
        _snapshot, _input, result = self.run_generation(positions, risk_policy_version="missing_policy")

        self.assertEqual(result.generation_result.status, PortfolioRiskGenerationStatus.VALIDATION_FAILED)
        self.assertEqual(result.run_record.attempted_position_ids, ())
        self.assertEqual(result.run_record.risk_artifact_refs, ())
        self.assertEqual(result.run_record.monitoring_artifact_refs, ())
        self.assertEqual(tuple(result.artifact_save_results), ())
        self.assertEqual(result.run_save_result.status, PortfolioRiskGenerationRunSaveStatus.INSERTED)
        self.assertEqual(self.row_count("risk_artifacts"), 0)
        self.assertEqual(self.row_count("technical_risk_artifact_index"), 0)
        self.assertEqual(self.row_count("portfolio_risk_generation_runs"), 1)

    def test_unexpected_generation_exception_propagates_and_does_not_create_db(self):
        snapshot = self.snapshot((self.position("position_a", "2330.TW"),))
        evaluation_input = self.evaluation_input(snapshot)
        coordinator = self.coordinator()

        with patch.object(portfolio_persistence_module, "PortfolioRiskGenerationService", ExplodingService):
            with self.assertRaisesRegex(RuntimeError, "unexpected generation exception"):
                coordinator.generate_and_persist(snapshot, evaluation_input, created_at=self.created_at())

        self.assertFalse(self.db_path.exists())

    def test_run_record_codec_pre_validation_fails_before_sqlite_connection(self):
        snapshot = self.snapshot((self.position("position_a", "2330.TW"),))
        evaluation_input = self.evaluation_input(snapshot)
        coordinator = self.coordinator()

        with patch.object(run_repository_module, "PortfolioRiskGenerationRunRecordCodec", BrokenRunRecordCodec):
            with patch.object(portfolio_persistence_module.sqlite3, "connect") as connect:
                with self.assertRaises(TechnicalPortfolioRiskPersistenceError) as error:
                    coordinator.generate_and_persist(snapshot, evaluation_input, created_at=self.created_at())

        self.assertIsInstance(error.exception.__cause__, PortfolioRiskGenerationRunPersistenceError)
        connect.assert_not_called()
        self.assertFalse(self.db_path.exists())

    def test_replay_same_created_at_is_idempotent_and_different_created_at_conflicts(self):
        positions = (self.position("position_a", "2330.TW"),)
        created_at = self.created_at()
        _snapshot, _input, first = self.run_generation(positions, created_at=created_at)
        _snapshot, _input, second = self.run_generation(positions, created_at=created_at)

        self.assertEqual(tuple(item.status for item in second.artifact_save_results), (RiskArtifactSaveStatus.IDEMPOTENT,))
        self.assertEqual(second.run_save_result.status, PortfolioRiskGenerationRunSaveStatus.IDEMPOTENT)
        self.assertEqual(first.run_record.record_checksum, second.run_record.record_checksum)
        with self.assertRaises(TechnicalPortfolioRiskPersistenceError):
            self.run_generation(positions, created_at=datetime(2026, 8, 15, 13, 1, tzinfo=UTC))
        self.assertEqual(self.row_count("risk_artifacts"), 1)
        self.assertEqual(self.row_count("portfolio_risk_generation_runs"), 1)

    def test_existing_artifacts_missing_run_completes_run_insert(self):
        positions = (self.position("position_a", "2330.TW"),)
        snapshot = self.snapshot(positions)
        evaluation_input = self.evaluation_input(snapshot)
        risk_context = RiskContext(
            portfolio_id=evaluation_input.portfolio_id,
            symbol="2330.TW",
            analysis_date=evaluation_input.as_of_date,
            feature_version=evaluation_input.feature_version,
            calculation_id=evaluation_input.calculation_id,
            model_version=evaluation_input.model_version,
        )
        position = PortfolioPosition(
            symbol="2330.TW",
            shares=Decimal("10"),
            average_cost=Decimal("650"),
            holding_type=RiskHoldingType.WHOLE_SHARE,
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )
        artifact = build_technical_artifact(
            position=position,
            context=risk_context,
            position_id="position_a",
            artifact_id=build_risk_artifact_id(evaluation_input.calculation_id, "position_a"),
            severity=RiskSeverity.LOW,
        )
        SQLiteTechnicalRiskArtifactPersistenceCoordinator(self.db_path).save(artifact)

        result = self.coordinator().generate_and_persist(snapshot, evaluation_input, created_at=self.created_at())

        self.assertEqual(tuple(item.status for item in result.artifact_save_results), (RiskArtifactSaveStatus.IDEMPOTENT,))
        self.assertEqual(result.run_save_result.status, PortfolioRiskGenerationRunSaveStatus.INSERTED)

    def test_existing_core_artifact_missing_index_is_completed(self):
        positions = (self.position("position_a", "2330.TW"),)
        _snapshot, evaluation_input, first = self.run_generation(positions)
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("DELETE FROM technical_risk_artifact_index")
            connection.execute("DELETE FROM portfolio_risk_generation_runs")
            connection.commit()
        finally:
            connection.close()

        _snapshot, _input, result = self.run_generation(positions)

        self.assertEqual(tuple(item.status for item in result.artifact_save_results), (RiskArtifactSaveStatus.IDEMPOTENT,))
        self.assertEqual(result.run_save_result.status, PortfolioRiskGenerationRunSaveStatus.INSERTED)
        self.assertEqual(self.row_count("technical_risk_artifact_index"), 1)
        self.assertEqual(first.run_record.risk_artifact_refs, result.run_record.risk_artifact_refs)

    def test_artifact_conflict_rolls_back_prior_insert_and_run(self):
        positions = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2454.TW"),
        )
        snapshot = self.snapshot(positions)
        evaluation_input = self.evaluation_input(snapshot)
        context = RiskContext(
            portfolio_id=evaluation_input.portfolio_id,
            symbol="2454.TW",
            analysis_date=evaluation_input.as_of_date,
            feature_version=evaluation_input.feature_version,
            calculation_id=evaluation_input.calculation_id,
            model_version=evaluation_input.model_version,
        )
        conflicting_position = PortfolioPosition(
            symbol="2454.TW",
            shares=Decimal("10"),
            average_cost=Decimal("650"),
            holding_type=RiskHoldingType.WHOLE_SHARE,
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )
        conflicting = build_technical_artifact(
            position=conflicting_position,
            context=context,
            position_id="position_b",
            artifact_id=build_risk_artifact_id(evaluation_input.calculation_id, "position_b"),
            severity=RiskSeverity.HIGH,
        )
        SQLiteTechnicalRiskArtifactPersistenceCoordinator(self.db_path).save(conflicting)

        with self.assertRaises(TechnicalPortfolioRiskPersistenceError) as error:
            self.coordinator().generate_and_persist(snapshot, evaluation_input, created_at=self.created_at())

        self.assertIsInstance(error.exception.__cause__, RiskArtifactConflictError)
        self.assertEqual(self.row_count("risk_artifacts"), 1)
        self.assertEqual(self.row_count("portfolio_risk_generation_runs"), 0)
        self.assertIsNone(
            SQLiteTechnicalRiskArtifactQueryRepository(self.db_path).get_latest_by_position(
                evaluation_input.portfolio_id,
                "position_a",
            )
        )

    def test_run_conflict_and_forced_run_failure_roll_back_artifact_inserts(self):
        positions = (self.position("position_a", "2330.TW"),)
        snapshot = self.snapshot(positions)
        evaluation_input = self.evaluation_input(snapshot)
        conflicting_run = PortfolioRiskGenerationRunRecord(
            calculation_id=evaluation_input.calculation_id,
            generation_key="different_generation_key",
            portfolio_id=evaluation_input.portfolio_id,
            snapshot_id=evaluation_input.snapshot_id,
            snapshot_checksum=evaluation_input.snapshot_checksum,
            analysis_date=evaluation_input.as_of_date,
            valuation_date=evaluation_input.valuation_date,
            status=PortfolioRiskGenerationStatus.VALIDATION_FAILED,
            attempted_position_ids=(),
            risk_evaluated_position_ids=(),
            succeeded_position_ids=(),
            failed_position_ids=(),
            risk_artifact_refs=(),
            monitoring_artifact_refs=(),
            issues=(),
            warnings=(),
            created_at=self.created_at(),
        )
        SQLitePortfolioRiskGenerationRunRepository(self.db_path).save(conflicting_run)

        with self.assertRaises(TechnicalPortfolioRiskPersistenceError):
            self.coordinator().generate_and_persist(snapshot, evaluation_input, created_at=self.created_at())
        self.assertEqual(self.row_count("risk_artifacts"), 0)
        self.assertEqual(self.row_count("portfolio_risk_generation_runs"), 1)

        self.db_path.unlink()
        with patch.object(portfolio_persistence_module, "persist_portfolio_run_record_in_connection", BrokenRunHelper()):
            with self.assertRaises(TechnicalPortfolioRiskPersistenceError):
                self.coordinator().generate_and_persist(snapshot, evaluation_input, created_at=self.created_at())
        self.assertEqual(self.row_count("risk_artifacts"), 0)
        self.assertEqual(self.row_count("technical_risk_artifact_index"), 0)
        self.assertEqual(self.row_count("portfolio_risk_generation_runs"), 0)

    def test_existing_run_missing_core_fails_closed_without_repair(self):
        positions = (self.position("position_a", "2330.TW"),)
        _snapshot, _input, first = self.run_generation(positions)
        missing_artifact_id = first.run_record.risk_artifact_refs[0].artifact_id
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("DELETE FROM risk_artifacts WHERE artifact_id = ?", (missing_artifact_id,))
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(TechnicalPortfolioRiskPersistenceError, "missing RiskArtifact") as error:
            self.run_generation(positions)
        self.assertIsInstance(error.exception.__cause__, RiskArtifactCorruptionError)
        self.assertEqual(error.exception.__cause__.artifact_id, missing_artifact_id)
        self.assertEqual(self.row_count("portfolio_risk_generation_runs"), 1)
        self.assertEqual(self.row_count("risk_artifacts"), 0)

    def test_orphan_index_corruption_rolls_back_prior_insert(self):
        positions = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2454.TW"),
        )
        snapshot = self.snapshot(positions)
        evaluation_input = self.evaluation_input(snapshot)
        context = RiskContext(
            portfolio_id=evaluation_input.portfolio_id,
            symbol="2454.TW",
            analysis_date=evaluation_input.as_of_date,
            feature_version=evaluation_input.feature_version,
            calculation_id=evaluation_input.calculation_id,
            model_version=evaluation_input.model_version,
        )
        position = PortfolioPosition(
            symbol="2454.TW",
            shares=Decimal("10"),
            average_cost=Decimal("650"),
            holding_type=RiskHoldingType.WHOLE_SHARE,
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )
        artifact = build_technical_artifact(
            position=position,
            context=context,
            position_id="position_b",
            artifact_id=build_risk_artifact_id(evaluation_input.calculation_id, "position_b"),
            severity=RiskSeverity.LOW,
        )
        SQLitePortfolioRiskGenerationRunRepository(self.db_path)
        connection = sqlite3.connect(self.db_path)
        try:
            insert_technical_index_record(connection, TechnicalRiskArtifactIndexRecord.from_artifact(artifact))
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(TechnicalPortfolioRiskPersistenceError):
            self.coordinator().generate_and_persist(snapshot, evaluation_input, created_at=self.created_at())
        self.assertEqual(self.row_count("risk_artifacts"), 0)
        self.assertEqual(self.row_count("portfolio_risk_generation_runs"), 0)

    def test_warning_mapping_and_naive_created_at_fail_closed_before_db(self):
        risk = FakeTechnicalRiskEvaluator(warning_by_position={"position_a": ("risk warning",)})
        monitoring = FakeMonitoringEvaluator(warning_by_position={"position_a": ("monitoring warning",)})
        _snapshot, _input, result = self.run_generation(
            (self.position("position_a", "2330.TW"),),
            risk_evaluator=risk,
            monitoring_evaluator=monitoring,
        )

        self.assertEqual(
            tuple((warning.message, warning.position_id) for warning in result.run_record.warnings),
            (("risk warning", "position_a"), ("monitoring warning", "position_a")),
        )

        with self.assertRaises(TechnicalPortfolioRiskPersistenceError):
            self.run_generation((self.position("position_b", "2454.TW"),), created_at=datetime(2026, 8, 15, 13, 0))

    def test_boundaries(self):
        generation_source = (SRC_PATH / "portfolio_generation" / "generation_service.py").read_text()
        self.assertNotIn("risk_persistence", generation_source)
        self.assertNotIn("sqlite", generation_source.lower())

        schema_source = (SRC_PATH / "risk_persistence" / "sqlite_schema.py").read_text()
        self.assertIn("SCHEMA_VERSION = 3", schema_source)
        self.assertNotIn("SCHEMA_VERSION = 4", schema_source)

        source = inspect.getsource(portfolio_persistence_module)
        forbidden = (
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "data/production",
            "scheduler",
            "dashboard",
            "alert",
            "activation",
            "deployment",
            "TechnicalRiskEvidenceSnapshot",
            ".save(",
        )
        for text in forbidden:
            with self.subTest(text=text):
                self.assertNotIn(text, source)
        self.assertIsInstance(self.coordinator(), SQLiteTechnicalPortfolioRiskPersistenceCoordinator)


if __name__ == "__main__":
    unittest.main()
