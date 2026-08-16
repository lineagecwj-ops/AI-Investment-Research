import sys
import unittest
from dataclasses import dataclass
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

from portfolio_generation import ExactVersionPolicyResolver
from portfolio_generation import MonitoringEvaluationOutput
from portfolio_generation import PortfolioRiskGenerationService
from portfolio_generation import PortfolioRiskGenerationStatus
from portfolio_generation import RiskEvaluationOutput
from portfolio_generation import build_monitoring_artifact_id
from portfolio_generation import build_risk_artifact_id
from portfolio_generation import position_identity_digest
from portfolio_state import HoldingType
from portfolio_state import PortfolioPositionState
from portfolio_state import PortfolioSnapshot
from portfolio_state import RiskEvaluationInput
from risk import RiskArtifact
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskDefinition
from risk import RiskRegistry
from risk import RiskSeverity
from risk import RiskSignal


FEATURE_SET_CHECKSUM_A = "technical_feature_set_" + "a" * 64


@dataclass(frozen=True)
class FakeMonitoringArtifact:
    artifact_id: str
    source_risk_artifact_id: str
    portfolio_id: str
    symbol: str


class FakeRiskEvaluator:
    def __init__(
        self,
        *,
        symbol_to_position_id: dict[str, str],
        fail_position_id: str | None = None,
        warning: str | None = None,
    ):
        self.symbol_to_position_id = symbol_to_position_id
        self.fail_position_id = fail_position_id
        self.warning = warning
        self.calls: list[tuple[str, str, str]] = []

    def evaluate(self, position, context, risk_artifact_id):
        position_id = self.symbol_to_position_id[position.symbol]
        self.calls.append((position_id, position.symbol, risk_artifact_id))
        if position_id == self.fail_position_id:
            raise RuntimeError(f"risk failure for {position_id}")
        signal = RiskSignal(
            risk_id="TECH_TREND_WEAKENING_V1",
            symbol=position.symbol,
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.HIGH,
            trigger_reason="fake evaluator metadata",
            created_at=datetime(2026, 8, 13, 12, 0, tzinfo=UTC),
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id=context.portfolio_id,
            symbol=position.symbol,
            signals=(signal,),
            assessment_date=context.analysis_date,
        )
        artifact = RiskArtifact(
            artifact_id=risk_artifact_id,
            position_identity=position.identity,
            risk_assessment=assessment,
            signals=(signal,),
            feature_lineage={"feature_version": context.feature_version, "model_version": context.model_version},
            calculation_metadata={
                "portfolio_id": context.portfolio_id,
                "symbol": position.symbol,
                "analysis_date": context.analysis_date.isoformat(),
                "calculation_id": context.calculation_id,
            },
            created_at=datetime(2026, 8, 13, 12, 0, tzinfo=UTC),
            checksum=f"{risk_artifact_id}_checksum",
        )
        return RiskEvaluationOutput(
            position_id=position_id,
            symbol=position.symbol,
            risk_artifact=artifact,
            warnings=(self.warning,) if self.warning else (),
        )


class FakeMonitoringEvaluator:
    def __init__(
        self,
        *,
        symbol_to_position_id: dict[str, str],
        fail_position_id: str | None = None,
        warning: str | None = None,
    ):
        self.symbol_to_position_id = symbol_to_position_id
        self.fail_position_id = fail_position_id
        self.warning = warning
        self.calls: list[tuple[str, str, str, date]] = []

    def evaluate(self, risk_artifact, context, monitoring_artifact_id):
        position_id = self.symbol_to_position_id[context.symbol]
        self.calls.append((position_id, context.symbol, monitoring_artifact_id, context.monitoring_date))
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
            ),
            warnings=(self.warning,) if self.warning else (),
        )


class PortfolioRiskGenerationServiceFrameworkTestCase(unittest.TestCase):

    def position(
        self,
        position_id: str,
        symbol: str,
        *,
        status: str = "ACTIVE",
        portfolio_id: str = "portfolio_synthetic_001",
    ):
        return PortfolioPositionState(
            portfolio_id=portfolio_id,
            position_id=position_id,
            symbol=symbol,
            shares=Decimal("10"),
            average_cost=Decimal("650.00"),
            currency="TWD",
            position_status=status,
            holding_type=HoldingType.WHOLE_SHARE,
            acquisition_date=date(2026, 1, 5),
        )

    def snapshot(self, positions, *, portfolio_id: str = "portfolio_synthetic_001", snapshot_id: str = "snapshot_001"):
        return PortfolioSnapshot(
            snapshot_id=snapshot_id,
            portfolio_id=portfolio_id,
            as_of_date=date(2026, 8, 13),
            valuation_date=date(2026, 8, 12),
            positions=positions,
            created_at=datetime(2026, 8, 13, 12, 0, tzinfo=UTC),
            source_lineage={"source_type": "manual_contract_test", "source_version": "v1"},
        )

    def evaluation_input(self, snapshot, **overrides):
        params = {
            "feature_version": "feature_set_v1",
            "feature_set_checksum": FEATURE_SET_CHECKSUM_A,
            "model_version": "baseline_model_v1",
            "risk_definition_version": "risk_definition_v1",
            "risk_policy_version": "risk_policy_v1",
            "monitoring_policy_version": "monitoring_policy_v1",
        }
        params.update(overrides)
        return RiskEvaluationInput.from_snapshot(snapshot, **params)

    def resolver(self, *, risk_policy_versions=("risk_policy_v1",), monitoring_policy_versions=("monitoring_policy_v1",)):
        registry = RiskRegistry()
        registry.register(
            RiskDefinition(
                risk_id="TECH_TREND_WEAKENING_V1",
                risk_name="Trend Weakening",
                category=RiskCategory.TECHNICAL,
                version="risk_definition_v1",
                description="Synthetic risk definition.",
                severity_rule="metadata threshold",
            )
        )
        return ExactVersionPolicyResolver(
            risk_registry=registry,
            allowed_risk_policy_versions=risk_policy_versions,
            allowed_monitoring_policy_versions=monitoring_policy_versions,
        )

    def service(self, *, risk_evaluator=None, monitoring_evaluator=None, resolver=None):
        empty_symbol_map: dict[str, str] = {}
        return PortfolioRiskGenerationService(
            risk_evaluator=risk_evaluator or FakeRiskEvaluator(symbol_to_position_id=empty_symbol_map),
            monitoring_evaluator=monitoring_evaluator or FakeMonitoringEvaluator(symbol_to_position_id=empty_symbol_map),
            policy_resolver=resolver or self.resolver(),
            risk_definition_ids=("TECH_TREND_WEAKENING_V1",),
        )

    def generation_fixture(self, positions):
        symbol_to_position_id = {position.symbol: position.position_id for position in positions}
        snapshot = self.snapshot(positions)
        evaluation_input = self.evaluation_input(snapshot)
        risk_evaluator = FakeRiskEvaluator(symbol_to_position_id=symbol_to_position_id)
        monitoring_evaluator = FakeMonitoringEvaluator(symbol_to_position_id=symbol_to_position_id)
        service = self.service(risk_evaluator=risk_evaluator, monitoring_evaluator=monitoring_evaluator)
        return snapshot, evaluation_input, service, risk_evaluator, monitoring_evaluator

    def test_single_active_position_success(self):
        snapshot, evaluation_input, service, _risk_evaluator, _monitoring_evaluator = self.generation_fixture(
            (self.position("position_a", "2330.TW"),)
        )

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.SUCCESS)
        self.assertEqual(result.attempted_position_ids, ("position_a",))
        self.assertEqual(result.succeeded_position_ids, ("position_a",))
        self.assertEqual(result.failed_position_ids, ())
        self.assertEqual(result.position_results[0].status, PortfolioRiskGenerationStatus.SUCCESS)

    def test_multiple_active_position_success(self):
        snapshot, evaluation_input, service, _risk_evaluator, _monitoring_evaluator = self.generation_fixture(
            (
                self.position("position_b", "2454.TW"),
                self.position("position_a", "2330.TW"),
            )
        )

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.SUCCESS)
        self.assertEqual(result.succeeded_position_ids, ("position_a", "position_b"))
        self.assertEqual(tuple(row.position_id for row in result.position_results), ("position_a", "position_b"))

    def test_deterministic_processing_order_and_call_order(self):
        snapshot, evaluation_input, service, risk_evaluator, monitoring_evaluator = self.generation_fixture(
            (
                self.position("position_c", "3008.TW"),
                self.position("position_a", "2330.TW"),
                self.position("position_b", "2454.TW"),
            )
        )

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.attempted_position_ids, ("position_a", "position_b", "position_c"))
        self.assertEqual(tuple(call[0] for call in risk_evaluator.calls), ("position_a", "position_b", "position_c"))
        self.assertEqual(tuple(call[0] for call in monitoring_evaluator.calls), ("position_a", "position_b", "position_c"))

    def test_snapshot_tuple_order_does_not_affect_result_order(self):
        positions_a = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2454.TW"),
            self.position("position_c", "3008.TW"),
        )
        positions_b = (positions_a[2], positions_a[0], positions_a[1])
        first = self.generation_fixture(positions_a)
        second = self.generation_fixture(positions_b)

        first_result = first[2].generate(first[0], first[1])
        second_result = second[2].generate(second[0], second[1])

        self.assertEqual(first_result.attempted_position_ids, second_result.attempted_position_ids)
        self.assertEqual(
            tuple(row.risk_artifact_id for row in first_result.position_results),
            tuple(row.risk_artifact_id for row in second_result.position_results),
        )

    def test_deterministic_artifact_ids(self):
        calculation_id = "portfolio_risk_calc_001"

        self.assertEqual(
            build_risk_artifact_id(calculation_id, "position_a"),
            build_risk_artifact_id(calculation_id, "position_a"),
        )
        self.assertEqual(
            build_monitoring_artifact_id(calculation_id, "position_a"),
            build_monitoring_artifact_id(calculation_id, "position_a"),
        )
        self.assertNotEqual(
            build_risk_artifact_id(calculation_id, "position_a"),
            build_risk_artifact_id(calculation_id, "position_b"),
        )
        self.assertNotEqual(
            build_monitoring_artifact_id(calculation_id, "position_a"),
            build_monitoring_artifact_id("different_calc", "position_a"),
        )

    def test_raw_position_id_not_exposed_in_artifact_id(self):
        artifact_id = build_risk_artifact_id("portfolio_risk_calc_001", "unsafe position/id")

        self.assertNotIn("unsafe position/id", artifact_id)
        self.assertEqual(len(position_identity_digest("unsafe position/id")), 64)

    def test_same_generation_repeatability(self):
        snapshot, evaluation_input, service, _risk_evaluator, _monitoring_evaluator = self.generation_fixture(
            (
                self.position("position_a", "2330.TW"),
                self.position("position_b", "2454.TW"),
            )
        )
        second_service = self.generation_fixture(tuple(snapshot.positions))[2]

        first_result = service.generate(snapshot, evaluation_input)
        second_result = second_service.generate(snapshot, evaluation_input)

        self.assertEqual(first_result, second_result)

    def test_different_calculation_id_changes_artifact_ids(self):
        first_snapshot = self.snapshot((self.position("position_a", "2330.TW"),))
        second_snapshot = replace(first_snapshot, snapshot_id="snapshot_002", checksum=None)
        first_input = self.evaluation_input(first_snapshot)
        second_input = self.evaluation_input(second_snapshot)

        self.assertNotEqual(
            build_risk_artifact_id(first_input.calculation_id, "position_a"),
            build_risk_artifact_id(second_input.calculation_id, "position_a"),
        )

    def test_active_position_missing_validation_failed(self):
        snapshot, evaluation_input, service, _risk_evaluator, _monitoring_evaluator = self.generation_fixture(
            (self.position("position_a", "2330.TW"),)
        )
        evaluation_input = replace(evaluation_input, active_position_ids=("missing_position",))

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.VALIDATION_FAILED)
        self.assertEqual(result.attempted_position_ids, ("missing_position",))
        self.assertEqual(result.failed_position_ids, ("missing_position",))

    def test_inactive_position_validation_failed(self):
        position = self.position("position_a", "2330.TW", status="CLOSED")
        snapshot, evaluation_input, service, _risk_evaluator, _monitoring_evaluator = self.generation_fixture((position,))
        evaluation_input = replace(evaluation_input, active_position_ids=("position_a",))

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.VALIDATION_FAILED)
        self.assertEqual(result.failed_position_ids, ("position_a",))

    def test_portfolio_mismatch_validation_failed(self):
        original_snapshot = self.snapshot((self.position("position_a", "2330.TW"),))
        evaluation_input = self.evaluation_input(original_snapshot)
        mismatched_position = self.position(
            "position_a",
            "2330.TW",
            portfolio_id="other_portfolio",
        )
        mismatched_snapshot = self.snapshot(
            (mismatched_position,),
            portfolio_id="other_portfolio",
        )
        service = self.service(
            risk_evaluator=FakeRiskEvaluator(symbol_to_position_id={"2330.TW": "position_a"}),
            monitoring_evaluator=FakeMonitoringEvaluator(symbol_to_position_id={"2330.TW": "position_a"}),
        )

        result = service.generate(mismatched_snapshot, evaluation_input)

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.VALIDATION_FAILED)

    def test_policy_resolution_failure_before_evaluator(self):
        snapshot = self.snapshot((self.position("position_a", "2330.TW"),))
        evaluation_input = self.evaluation_input(snapshot, risk_policy_version="unknown_policy")
        symbol_to_position_id = {"2330.TW": "position_a"}
        risk_evaluator = FakeRiskEvaluator(symbol_to_position_id=symbol_to_position_id)
        monitoring_evaluator = FakeMonitoringEvaluator(symbol_to_position_id=symbol_to_position_id)
        service = self.service(risk_evaluator=risk_evaluator, monitoring_evaluator=monitoring_evaluator)

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.VALIDATION_FAILED)
        self.assertEqual(result.attempted_position_ids, ())
        self.assertEqual(risk_evaluator.calls, [])
        self.assertEqual(monitoring_evaluator.calls, [])

    def test_fake_risk_evaluator_failure(self):
        positions = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2454.TW"),
            self.position("position_c", "3008.TW"),
        )
        symbol_to_position_id = {position.symbol: position.position_id for position in positions}
        snapshot = self.snapshot(positions)
        evaluation_input = self.evaluation_input(snapshot)
        risk_evaluator = FakeRiskEvaluator(symbol_to_position_id=symbol_to_position_id, fail_position_id="position_b")
        monitoring_evaluator = FakeMonitoringEvaluator(symbol_to_position_id=symbol_to_position_id)
        service = self.service(risk_evaluator=risk_evaluator, monitoring_evaluator=monitoring_evaluator)

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.RISK_EVALUATION_FAILED)
        self.assertEqual(result.attempted_position_ids, ("position_a", "position_b"))
        self.assertEqual(result.succeeded_position_ids, ("position_a",))
        self.assertEqual(result.failed_position_ids, ("position_b",))
        self.assertEqual(tuple(call[0] for call in risk_evaluator.calls), ("position_a", "position_b"))
        self.assertEqual(tuple(call[0] for call in monitoring_evaluator.calls), ("position_a",))

    def test_fake_monitoring_evaluator_failure(self):
        positions = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2454.TW"),
        )
        symbol_to_position_id = {position.symbol: position.position_id for position in positions}
        snapshot = self.snapshot(positions)
        evaluation_input = self.evaluation_input(snapshot)
        risk_evaluator = FakeRiskEvaluator(symbol_to_position_id=symbol_to_position_id)
        monitoring_evaluator = FakeMonitoringEvaluator(
            symbol_to_position_id=symbol_to_position_id,
            fail_position_id="position_b",
        )
        service = self.service(risk_evaluator=risk_evaluator, monitoring_evaluator=monitoring_evaluator)

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.MONITORING_FAILED)
        self.assertEqual(result.attempted_position_ids, ("position_a", "position_b"))
        self.assertEqual(result.succeeded_position_ids, ("position_a",))
        self.assertEqual(result.failed_position_ids, ("position_b",))

    def test_fail_fast_stops_subsequent_positions_and_retains_diagnostics(self):
        positions = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2454.TW"),
            self.position("position_c", "3008.TW"),
        )
        symbol_to_position_id = {position.symbol: position.position_id for position in positions}
        snapshot = self.snapshot(positions)
        evaluation_input = self.evaluation_input(snapshot)
        risk_evaluator = FakeRiskEvaluator(symbol_to_position_id=symbol_to_position_id, fail_position_id="position_b")
        monitoring_evaluator = FakeMonitoringEvaluator(symbol_to_position_id=symbol_to_position_id)
        service = self.service(risk_evaluator=risk_evaluator, monitoring_evaluator=monitoring_evaluator)

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(tuple(row.position_id for row in result.position_results), ("position_a", "position_b"))
        self.assertIn("risk failure", result.errors[0])
        self.assertNotIn("position_c", result.attempted_position_ids)

    def test_no_partial_success_or_already_generated_without_writer(self):
        statuses = tuple(status.value for status in PortfolioRiskGenerationStatus)

        self.assertNotIn("PARTIAL_SUCCESS", statuses)
        snapshot, evaluation_input, service, _risk_evaluator, _monitoring_evaluator = self.generation_fixture(
            (self.position("position_a", "2330.TW"),)
        )
        result = service.generate(snapshot, evaluation_input)

        self.assertNotEqual(result.status, PortfolioRiskGenerationStatus.ALREADY_GENERATED)

    def test_result_envelope_deterministic_and_contains_identities(self):
        snapshot, evaluation_input, service, _risk_evaluator, _monitoring_evaluator = self.generation_fixture(
            (self.position("position_a", "2330.TW"),)
        )

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.generation_key, evaluation_input.generation_key)
        self.assertEqual(result.calculation_id, evaluation_input.calculation_id)
        self.assertEqual(result.portfolio_id, evaluation_input.portfolio_id)
        self.assertEqual(result.snapshot_id, evaluation_input.snapshot_id)
        self.assertIsInstance(result.position_results, tuple)

    def test_monitoring_date_is_as_of_date(self):
        snapshot, evaluation_input, service, _risk_evaluator, monitoring_evaluator = self.generation_fixture(
            (self.position("position_a", "2330.TW"),)
        )

        service.generate(snapshot, evaluation_input)

        self.assertEqual(monitoring_evaluator.calls[0][3], evaluation_input.as_of_date)

    def test_warnings_are_collected(self):
        position = self.position("position_a", "2330.TW")
        symbol_to_position_id = {position.symbol: position.position_id}
        snapshot = self.snapshot((position,))
        evaluation_input = self.evaluation_input(snapshot)
        risk_evaluator = FakeRiskEvaluator(symbol_to_position_id=symbol_to_position_id, warning="risk warning")
        monitoring_evaluator = FakeMonitoringEvaluator(
            symbol_to_position_id=symbol_to_position_id,
            warning="monitoring warning",
        )
        service = self.service(risk_evaluator=risk_evaluator, monitoring_evaluator=monitoring_evaluator)

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.warnings, ("risk warning", "monitoring warning"))
        self.assertEqual(result.position_results[0].warnings, ("risk warning", "monitoring warning"))

    def test_no_filesystem_side_effects_in_portfolio_generation_tree(self):
        generated = tuple(
            path
            for path in (SRC_PATH / "portfolio_generation").glob("**/*")
            if path.name == "__pycache__" or path.suffix == ".pyc"
        )

        self.assertEqual(generated, ())

    def test_architecture_boundary_scan(self):
        source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "portfolio_generation").glob("*.py"))
        )

        forbidden_terms = (
            "RiskMonitoringEngine(",
            "RiskArtifactGenerator(",
            "RiskMonitoringArtifactGenerator(",
            "sqlite3",
            "LiveDataStore",
            "live_data_store",
            "ResearchDataStore",
            "research_data_store",
            "swing_scanner",
            "scanner_service",
            "pdf_export",
            "yfinance",
            "portfolio_artifacts",
            "portfolio_dashboard",
            "open(",
            "Path(",
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
        )
        for forbidden in forbidden_terms:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
