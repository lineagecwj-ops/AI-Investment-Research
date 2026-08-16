import inspect
import sys
import unittest
from dataclasses import dataclass
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
from portfolio_generation import TechnicalRiskArtifactAdapter
from portfolio_generation import TechnicalRiskPortfolioEvaluator
from portfolio_generation import build_risk_artifact_id
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskDefinition
from risk import RiskRegistry
from risk import RiskSeverity
from risk import RiskSignal
from risk_evaluation import PRODUCTION_TECHNICAL_RISK_POLICY_V1
from risk_evaluation import TECHNICAL_RISK_SIGNAL_PRODUCER_VERSION_V1
from risk_evaluation import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation import TECH_AS_OF_CLOSE_FEATURE_VERSION
from risk_evaluation import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_evaluation import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_evaluation import TECH_RISK_REASON_MAPPING_V1
from risk_evaluation import TECH_RISK_REQUIRED_FEATURE_IDS_V1
from risk_evaluation import TECH_RISK_SEVERITY_MAPPING_V1
from risk_evaluation import TECH_RSI14_FEATURE_ID
from risk_evaluation import TECH_RSI14_FEATURE_VERSION
from risk_evaluation import TECH_SMA20_FEATURE_ID
from risk_evaluation import TECH_SMA20_FEATURE_VERSION
from risk_evaluation import TECH_SMA60_FEATURE_ID
from risk_evaluation import TECH_SMA60_FEATURE_VERSION
from risk_evaluation import ProducedRiskSignal
from risk_evaluation import ProductionTechnicalRiskPolicy
from risk_evaluation import ProductionTechnicalRiskPredicateId
from risk_evaluation import ProductionTechnicalRiskReasonCode
from risk_evaluation import ProductionTechnicalRiskRule
from risk_evaluation import ProductionTechnicalRiskThresholdDimension
from risk_evaluation import ProductionTechnicalRiskThresholdDimensionId
from risk_evaluation import ProductionTechnicalRiskThresholdOperator
from risk_evaluation import RiskFeatureInput
from risk_evaluation import RiskSignalProductionInput
from risk_evaluation import TechnicalRiskProductionResult
from risk_evaluation import TechnicalRiskProductionService
from portfolio_state import HoldingType
from portfolio_state import PortfolioPositionState
from portfolio_state import PortfolioSnapshot
from portfolio_state import RiskEvaluationInput


FEATURE_SET_CHECKSUM_A = "technical_feature_set_" + "a" * 64


@dataclass(frozen=True)
class CapturedMonitoringArtifact:
    artifact_id: str
    source_risk_artifact_id: str
    portfolio_id: str
    symbol: str
    position_id: str


class ArtifactKeyedTechnicalInputProvider:
    def __init__(self, inputs_by_artifact_id):
        self.inputs_by_artifact_id = dict(inputs_by_artifact_id)
        self.calls = []

    def resolve(self, position, context, risk_artifact_id):
        self.calls.append((position, context, risk_artifact_id))
        try:
            return self.inputs_by_artifact_id[risk_artifact_id]
        except KeyError as exc:
            raise RuntimeError(f"missing technical production input for artifact {risk_artifact_id}") from exc


class CapturingMonitoringEvaluator:
    def __init__(self, *, fail_position_id=None):
        self.fail_position_id = fail_position_id
        self.calls = []

    def evaluate(self, risk_artifact, context, monitoring_artifact_id):
        position_id = risk_artifact.calculation_metadata["technical_position_id"]
        self.calls.append((position_id, risk_artifact, context, monitoring_artifact_id))
        if position_id == self.fail_position_id:
            raise RuntimeError(f"monitoring failure for {position_id}")
        return MonitoringEvaluationOutput(
            position_id=position_id,
            symbol=context.symbol,
            monitoring_artifact=CapturedMonitoringArtifact(
                artifact_id=monitoring_artifact_id,
                source_risk_artifact_id=risk_artifact.artifact_id,
                portfolio_id=context.portfolio_id,
                symbol=context.symbol,
                position_id=position_id,
            ),
        )


class CriticalProductionService:
    def run(self, *, input, policy, created_at):
        signal = RiskSignal(
            risk_id="TECHNICAL_DOWNSIDE_RISK_V1",
            symbol=input.symbol,
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.CRITICAL,
            trigger_reason="synthetic critical technical evidence",
            created_at=created_at,
        )
        produced = ProducedRiskSignal(
            signal=signal,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            producer_version=TECHNICAL_RISK_SIGNAL_PRODUCER_VERSION_V1,
            source_feature_ids=input.feature_ids,
            source_checksums=input.source_checksums,
            calculation_id=input.calculation_id,
            policy_checksum=policy.policy_checksum,
            evaluation_id="synthetic_critical_evaluation",
            evaluation_checksum="synthetic_critical_checksum",
            portfolio_id=input.portfolio_id,
            position_id=input.position_id,
            as_of_date=input.as_of_date,
            valuation_date=input.valuation_date,
        )
        return TechnicalRiskProductionResult(
            produced_signal=produced,
            risk_assessment=RiskAssessment.from_signals(
                portfolio_id=input.portfolio_id,
                symbol=input.symbol,
                signals=(signal,),
                assessment_date=input.as_of_date,
            ),
        )


class TechnicalRiskPortfolioGenerationIntegrationTestCase(unittest.TestCase):
    def created_at(self):
        return datetime(2026, 8, 15, 10, 30, tzinfo=UTC)

    def position(
        self,
        position_id,
        symbol,
        *,
        shares="10",
        holding_type=HoldingType.WHOLE_SHARE,
    ):
        return PortfolioPositionState(
            portfolio_id="portfolio_technical_001",
            position_id=position_id,
            symbol=symbol,
            shares=Decimal(shares),
            average_cost=Decimal("650.00"),
            currency="TWD",
            position_status="ACTIVE",
            holding_type=holding_type,
            acquisition_date=date(2026, 1, 5),
        )

    def snapshot(self, positions):
        return PortfolioSnapshot(
            snapshot_id="snapshot_technical_001",
            portfolio_id="portfolio_technical_001",
            as_of_date=date(2026, 8, 15),
            valuation_date=date(2026, 8, 14),
            positions=tuple(positions),
            created_at=self.created_at(),
            source_lineage={"source_type": "technical_integration_test", "source_version": "v1"},
        )

    def evaluation_input(self, snapshot):
        return RiskEvaluationInput.from_snapshot(
            snapshot,
            feature_version="technical_risk_feature_set_v1",
            feature_set_checksum=FEATURE_SET_CHECKSUM_A,
            model_version=None,
            risk_definition_version="risk_definition_v1",
            risk_policy_version="risk_policy_v1",
            monitoring_policy_version="monitoring_policy_v1",
        )

    def resolver(self):
        registry = RiskRegistry()
        registry.register(
            RiskDefinition(
                risk_id="TECHNICAL_DOWNSIDE_RISK_V1",
                risk_name="Technical Downside Risk",
                category=RiskCategory.TECHNICAL,
                version="risk_definition_v1",
                description="Technical downside risk integration definition.",
                severity_rule="production technical policy",
            )
        )
        return ExactVersionPolicyResolver(
            risk_registry=registry,
            allowed_risk_policy_versions=("risk_policy_v1",),
            allowed_monitoring_policy_versions=("monitoring_policy_v1",),
        )

    def dimension(self, dimension_id, value):
        return ProductionTechnicalRiskThresholdDimension(
            dimension_id=dimension_id,
            operator=ProductionTechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            canonical_value=Decimal(value),
        )

    def policy(self):
        return ProductionTechnicalRiskPolicy(
            policy_id=None,
            policy_version=PRODUCTION_TECHNICAL_RISK_POLICY_V1,
            policy_checksum=None,
            technical_policy_version="TECH_RISK_POLICY_V1_RESEARCH_FREEZE",
            source_research_freeze_id="freeze_technical_integration_001",
            source_research_freeze_checksum="freeze_checksum_technical_integration_001",
            candidate_id="TECH_POLICY_CANDIDATE_INTEGRATION",
            candidate_version="v1",
            candidate_structural_checksum="candidate_checksum_technical_integration_001",
            rules=(
                ProductionTechnicalRiskRule(
                    rule_id="HIGH_MULTI_EVIDENCE",
                    rule_priority=10,
                    severity=RiskSeverity.HIGH,
                    required_predicates=(
                        ProductionTechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                        ProductionTechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                    ),
                    optional_confirmation_predicates=(
                        ProductionTechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,
                    ),
                    reason_codes=(ProductionTechnicalRiskReasonCode.MULTI_EVIDENCE_TECHNICAL_DETERIORATION,),
                ),
                ProductionTechnicalRiskRule(
                    rule_id="MEDIUM_SHORT_WEAKNESS",
                    rule_priority=20,
                    severity=RiskSeverity.MEDIUM,
                    required_predicates=(ProductionTechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS,),
                    optional_confirmation_predicates=(
                        ProductionTechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,
                    ),
                    reason_codes=(ProductionTechnicalRiskReasonCode.PRICE_POSITION_SHORT_TERM_WEAKNESS,),
                ),
            ),
            threshold_set_id="threshold_set_technical_integration_001",
            threshold_set_version="v1",
            threshold_set_checksum="threshold_checksum_technical_integration_001",
            threshold_dimensions=(
                self.dimension(ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, "-0.05"),
                self.dimension(ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.10"),
                self.dimension(ProductionTechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, "-0.05"),
                self.dimension(ProductionTechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "40"),
            ),
            required_feature_ids=TECH_RISK_REQUIRED_FEATURE_IDS_V1,
            derived_evidence_version=TECH_RISK_DERIVED_EVIDENCE_V1,
            numeric_context_version=TECH_RISK_DECIMAL_CONTEXT_V1,
            severity_mapping_version=TECH_RISK_SEVERITY_MAPPING_V1,
            reason_mapping_version=TECH_RISK_REASON_MAPPING_V1,
        )

    def feature(
        self,
        feature_id,
        value,
        *,
        portfolio_id,
        position_id,
        symbol,
        as_of_date,
        calculation_id,
        version,
    ):
        return RiskFeatureInput(
            feature_id=feature_id,
            feature_version=version,
            portfolio_id=portfolio_id,
            position_id=position_id,
            symbol=symbol,
            as_of_date=as_of_date,
            feature_date=as_of_date,
            value=Decimal(value),
            source_artifact_id=f"artifact_{feature_id}_{position_id}",
            source_checksum=f"checksum_{feature_id}_{position_id}",
            calculation_id=calculation_id,
        )

    def features(
        self,
        evaluation_input,
        position_id,
        symbol,
        *,
        close,
        sma20,
        sma60,
        rsi14,
        portfolio_id=None,
        as_of_date=None,
        calculation_id=None,
    ):
        common = {
            "portfolio_id": portfolio_id or evaluation_input.portfolio_id,
            "position_id": position_id,
            "symbol": symbol,
            "as_of_date": as_of_date or evaluation_input.as_of_date,
            "calculation_id": calculation_id or evaluation_input.calculation_id,
        }
        return (
            self.feature(
                TECH_AS_OF_CLOSE_FEATURE_ID,
                close,
                version=TECH_AS_OF_CLOSE_FEATURE_VERSION,
                **common,
            ),
            self.feature(TECH_RSI14_FEATURE_ID, rsi14, version=TECH_RSI14_FEATURE_VERSION, **common),
            self.feature(TECH_SMA20_FEATURE_ID, sma20, version=TECH_SMA20_FEATURE_VERSION, **common),
            self.feature(TECH_SMA60_FEATURE_ID, sma60, version=TECH_SMA60_FEATURE_VERSION, **common),
        )

    def production_input(
        self,
        evaluation_input,
        base_position_id,
        base_symbol,
        *,
        close="100",
        sma20="105",
        sma60="120",
        rsi14="35",
        **overrides,
    ):
        values = {
            "portfolio_id": evaluation_input.portfolio_id,
            "position_id": base_position_id,
            "symbol": base_symbol,
            "as_of_date": evaluation_input.as_of_date,
            "valuation_date": evaluation_input.valuation_date,
            "feature_version": evaluation_input.feature_version,
            "feature_values": (),
            "model_version": evaluation_input.model_version,
            "model_metadata": None,
            "exposure_metadata": None,
            "source_artifact_ids": (),
            "source_checksums": (),
            "calculation_id": evaluation_input.calculation_id,
        }
        values.update(overrides)
        if "feature_values" not in overrides:
            feature_values = self.features(
                evaluation_input,
                values["position_id"],
                values["symbol"],
                close=close,
                sma20=sma20,
                sma60=sma60,
                rsi14=rsi14,
                portfolio_id=values["portfolio_id"],
                as_of_date=values["as_of_date"],
                calculation_id=values["calculation_id"],
            )
            values["feature_values"] = feature_values
            values["source_artifact_ids"] = tuple(feature.source_artifact_id for feature in feature_values)
            values["source_checksums"] = tuple(feature.source_checksum for feature in feature_values)
        elif "source_artifact_ids" not in overrides:
            values["source_artifact_ids"] = tuple(feature.source_artifact_id for feature in values["feature_values"])
            values["source_checksums"] = tuple(feature.source_checksum for feature in values["feature_values"])
        return RiskSignalProductionInput(**values)

    def artifact_id(self, evaluation_input, position_id):
        return build_risk_artifact_id(evaluation_input.calculation_id, position_id)

    def provider_for(self, evaluation_input, position_specs, *, overrides_by_position_id=None):
        overrides_by_position_id = overrides_by_position_id or {}
        mapping = {}
        for position_id, symbol, feature_values in position_specs:
            mapping[self.artifact_id(evaluation_input, position_id)] = self.production_input(
                evaluation_input,
                position_id,
                symbol,
                **feature_values,
                **overrides_by_position_id.get(position_id, {}),
            )
        return ArtifactKeyedTechnicalInputProvider(mapping)

    def service(self, provider, monitoring_evaluator, *, production_service=None, policy=None, created_at=None):
        evaluator = TechnicalRiskPortfolioEvaluator(
            input_provider=provider,
            policy=policy or self.policy(),
            created_at=created_at or self.created_at(),
            production_service=production_service or TechnicalRiskProductionService(),
            artifact_adapter=TechnicalRiskArtifactAdapter(),
        )
        return PortfolioRiskGenerationService(
            risk_evaluator=evaluator,
            monitoring_evaluator=monitoring_evaluator,
            policy_resolver=self.resolver(),
            risk_definition_ids=("TECHNICAL_DOWNSIDE_RISK_V1",),
        )

    def run_generation(self, positions, position_specs, *, provider=None, monitoring_evaluator=None, **service_kwargs):
        snapshot = self.snapshot(positions)
        evaluation_input = self.evaluation_input(snapshot)
        provider = provider or self.provider_for(evaluation_input, position_specs)
        monitoring_evaluator = monitoring_evaluator or CapturingMonitoringEvaluator()
        service = self.service(provider, monitoring_evaluator, **service_kwargs)
        return snapshot, evaluation_input, provider, monitoring_evaluator, service.generate(snapshot, evaluation_input)

    def artifact_by_position(self, monitoring_evaluator):
        return {position_id: risk_artifact for position_id, risk_artifact, _context, _artifact_id in monitoring_evaluator.calls}

    def expected_input_by_position(self, provider):
        return {
            production_input.position_id: production_input
            for production_input in provider.inputs_by_artifact_id.values()
        }

    def assert_technical_lineage_matches_input(self, artifact, production_input):
        metadata = artifact.calculation_metadata
        self.assertEqual(metadata["technical_policy_id"], self.policy().policy_id)
        self.assertEqual(metadata["technical_policy_version"], self.policy().policy_version)
        self.assertEqual(metadata["technical_policy_checksum"], self.policy().policy_checksum)
        self.assertEqual(metadata["technical_position_id"], production_input.position_id)
        self.assertEqual(metadata["technical_as_of_date"], production_input.as_of_date.isoformat())
        self.assertEqual(metadata["technical_valuation_date"], production_input.valuation_date.isoformat())
        self.assertEqual(metadata["technical_calculation_id"], production_input.calculation_id)
        self.assertEqual(metadata["technical_producer_version"], TECHNICAL_RISK_SIGNAL_PRODUCER_VERSION_V1)
        self.assertIsInstance(metadata["technical_evaluation_id"], str)
        self.assertTrue(metadata["technical_evaluation_id"])
        self.assertIsInstance(metadata["technical_evaluation_checksum"], str)
        self.assertTrue(metadata["technical_evaluation_checksum"])
        self.assertEqual(artifact.feature_lineage["technical_source_feature_ids"], production_input.feature_ids)
        self.assertEqual(artifact.feature_lineage["technical_source_checksums"], production_input.source_checksums)
        self.assertEqual(
            tuple(
                zip(
                    artifact.feature_lineage["technical_source_feature_ids"],
                    artifact.feature_lineage["technical_source_checksums"],
                )
            ),
            tuple(zip(production_input.feature_ids, production_input.source_checksums)),
        )

    def test_single_position_full_service_technical_integration_success(self):
        positions = (self.position("position_a", "2330.TW"),)
        specs = (("position_a", "2330.TW", {"close": "100", "sma20": "105", "sma60": "120", "rsi14": "35"}),)

        _snapshot, evaluation_input, provider, monitoring, result = self.run_generation(positions, specs)

        expected_artifact_id = self.artifact_id(evaluation_input, "position_a")
        self.assertEqual(result.status, PortfolioRiskGenerationStatus.SUCCESS)
        self.assertEqual(result.attempted_position_ids, ("position_a",))
        self.assertEqual(result.succeeded_position_ids, ("position_a",))
        self.assertEqual(result.failed_position_ids, ())
        self.assertEqual(result.position_results[0].risk_artifact_id, expected_artifact_id)
        self.assertEqual(provider.calls[0][2], expected_artifact_id)
        self.assertEqual(monitoring.calls[0][1].artifact_id, expected_artifact_id)
        self.assertTrue(monitoring.calls[0][1].checksum)

    def test_mixed_low_medium_high_positions_preserve_order_and_lineage(self):
        positions = (
            self.position("position_c", "3008.TW"),
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2454.TW", shares="10.5", holding_type=HoldingType.FRACTIONAL_SHARE),
        )
        specs = (
            ("position_a", "2330.TW", {"close": "130", "sma20": "105", "sma60": "100", "rsi14": "55"}),
            ("position_b", "2454.TW", {"close": "100", "sma20": "110", "sma60": "100", "rsi14": "55"}),
            ("position_c", "3008.TW", {"close": "100", "sma20": "105", "sma60": "120", "rsi14": "35"}),
        )

        _snapshot, evaluation_input, provider, monitoring, result = self.run_generation(positions, specs)

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.SUCCESS)
        self.assertEqual(result.attempted_position_ids, ("position_a", "position_b", "position_c"))
        self.assertEqual(result.succeeded_position_ids, ("position_a", "position_b", "position_c"))
        self.assertEqual(result.failed_position_ids, ())
        artifacts = self.artifact_by_position(monitoring)
        expected_inputs = self.expected_input_by_position(provider)
        self.assertEqual(artifacts["position_a"].signals[0].severity, RiskSeverity.LOW)
        self.assertEqual(artifacts["position_b"].signals[0].severity, RiskSeverity.MEDIUM)
        self.assertEqual(artifacts["position_c"].signals[0].severity, RiskSeverity.HIGH)
        self.assertEqual(
            tuple(row.risk_artifact_id for row in result.position_results),
            tuple(self.artifact_id(evaluation_input, position_id) for position_id in ("position_a", "position_b", "position_c")),
        )
        for position_id, artifact in artifacts.items():
            self.assert_technical_lineage_matches_input(artifact, expected_inputs[position_id])
            self.assertEqual(artifact.created_at, self.created_at())
        self.assertEqual(
            len(
                {
                    artifacts[position_id].calculation_metadata["technical_evaluation_id"]
                    for position_id in artifacts
                }
            ),
            3,
        )
        self.assertEqual(
            len(
                {
                    artifacts[position_id].calculation_metadata["technical_evaluation_checksum"]
                    for position_id in artifacts
                }
            ),
            3,
        )

    def test_same_symbol_positions_use_artifact_id_mapping_and_replay_deterministically(self):
        positions = (
            self.position("position_b", "2330.TW"),
            self.position("position_a", "2330.TW"),
        )
        specs = (
            ("position_a", "2330.TW", {"close": "130", "sma20": "105", "sma60": "100", "rsi14": "55"}),
            ("position_b", "2330.TW", {"close": "100", "sma20": "105", "sma60": "120", "rsi14": "35"}),
        )

        first = self.run_generation(positions, specs)
        second = self.run_generation(tuple(reversed(positions)), specs)

        first_result = first[4]
        second_result = second[4]
        self.assertEqual(first_result, second_result)
        self.assertEqual(first_result.status, PortfolioRiskGenerationStatus.SUCCESS)
        self.assertEqual(first_result.attempted_position_ids, ("position_a", "position_b"))
        first_artifacts = self.artifact_by_position(first[3])
        second_artifacts = self.artifact_by_position(second[3])
        first_inputs = self.expected_input_by_position(first[2])
        self.assertEqual(first_artifacts["position_a"].artifact_id, second_artifacts["position_a"].artifact_id)
        self.assertEqual(first_artifacts["position_b"].artifact_id, second_artifacts["position_b"].artifact_id)
        self.assertNotEqual(first_artifacts["position_a"].artifact_id, first_artifacts["position_b"].artifact_id)
        self.assertEqual(first_artifacts["position_a"].checksum, second_artifacts["position_a"].checksum)
        self.assertEqual(first_artifacts["position_b"].checksum, second_artifacts["position_b"].checksum)
        self.assertNotEqual(
            first_artifacts["position_a"].calculation_metadata["technical_position_id"],
            first_artifacts["position_b"].calculation_metadata["technical_position_id"],
        )
        self.assertNotEqual(
            first_artifacts["position_a"].calculation_metadata["technical_evaluation_id"],
            first_artifacts["position_b"].calculation_metadata["technical_evaluation_id"],
        )
        for position_id in ("position_a", "position_b"):
            self.assert_technical_lineage_matches_input(first_artifacts[position_id], first_inputs[position_id])
            for metadata_key in (
                "technical_evaluation_id",
                "technical_evaluation_checksum",
                "technical_as_of_date",
                "technical_valuation_date",
            ):
                self.assertEqual(
                    first_artifacts[position_id].calculation_metadata[metadata_key],
                    second_artifacts[position_id].calculation_metadata[metadata_key],
                )
            for lineage_key in ("technical_source_feature_ids", "technical_source_checksums"):
                self.assertEqual(
                    first_artifacts[position_id].feature_lineage[lineage_key],
                    second_artifacts[position_id].feature_lineage[lineage_key],
                )
        self.assertEqual(
            tuple(call[2] for call in first[2].calls),
            tuple(row.risk_artifact_id for row in first_result.position_results),
        )

    def test_provider_missing_artifact_id_uses_existing_risk_failure_semantics(self):
        positions = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2454.TW"),
            self.position("position_c", "3008.TW"),
        )
        snapshot = self.snapshot(positions)
        evaluation_input = self.evaluation_input(snapshot)
        provider = self.provider_for(
            evaluation_input,
            (("position_a", "2330.TW", {"close": "130", "sma20": "105", "sma60": "100", "rsi14": "55"}),),
        )
        monitoring = CapturingMonitoringEvaluator()
        service = self.service(provider, monitoring)

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.RISK_EVALUATION_FAILED)
        self.assertEqual(result.attempted_position_ids, ("position_a", "position_b"))
        self.assertEqual(result.succeeded_position_ids, ("position_a",))
        self.assertEqual(result.failed_position_ids, ("position_b",))
        self.assertNotIn("position_c", result.attempted_position_ids)
        self.assertEqual(tuple(call[0] for call in monitoring.calls), ("position_a",))

    def test_wrong_provider_position_id_same_symbol_fails_without_symbol_fallback(self):
        positions = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2330.TW"),
            self.position("position_c", "3008.TW"),
        )
        snapshot = self.snapshot(positions)
        evaluation_input = self.evaluation_input(snapshot)
        overrides = {"position_b": {"position_id": "position_wrong", "symbol": "2330.TW"}}
        provider = self.provider_for(
            evaluation_input,
            (
                ("position_a", "2330.TW", {"close": "130", "sma20": "105", "sma60": "100", "rsi14": "55"}),
                ("position_b", "2330.TW", {"close": "100", "sma20": "105", "sma60": "120", "rsi14": "35"}),
            ),
            overrides_by_position_id=overrides,
        )
        monitoring = CapturingMonitoringEvaluator()
        service = self.service(provider, monitoring)

        result = service.generate(snapshot, evaluation_input)

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.RISK_EVALUATION_FAILED)
        self.assertEqual(result.attempted_position_ids, ("position_a", "position_b"))
        self.assertEqual(result.succeeded_position_ids, ("position_a",))
        self.assertEqual(result.failed_position_ids, ("position_b",))
        self.assertIn("position_id artifact", result.errors[0])

    def test_wrong_provider_context_fields_fail_through_existing_risk_failure_semantics(self):
        cases = (
            ("portfolio_id", {"portfolio_id": "portfolio_other"}, "portfolio_id"),
            ("calculation_id", {"calculation_id": "technical_calc_other"}, "calculation_id"),
            ("as_of_date", {"as_of_date": date(2026, 8, 14)}, "as_of_date"),
        )
        for _case_name, override, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                position = self.position("position_a", "2330.TW")
                snapshot = self.snapshot((position,))
                evaluation_input = self.evaluation_input(snapshot)
                provider = self.provider_for(
                    evaluation_input,
                    (("position_a", "2330.TW", {"close": "100", "sma20": "105", "sma60": "120", "rsi14": "35"}),),
                    overrides_by_position_id={"position_a": override},
                )
                service = self.service(provider, CapturingMonitoringEvaluator())

                result = service.generate(snapshot, evaluation_input)

                self.assertEqual(result.status, PortfolioRiskGenerationStatus.RISK_EVALUATION_FAILED)
                self.assertEqual(result.attempted_position_ids, ("position_a",))
                self.assertEqual(result.succeeded_position_ids, ())
                self.assertEqual(result.failed_position_ids, ("position_a",))
                self.assertIn(expected_error, result.errors[0])

    def test_monitoring_failure_preserves_existing_fail_fast_semantics(self):
        positions = (
            self.position("position_a", "2330.TW"),
            self.position("position_b", "2454.TW"),
            self.position("position_c", "3008.TW"),
        )
        specs = (
            ("position_a", "2330.TW", {"close": "130", "sma20": "105", "sma60": "100", "rsi14": "55"}),
            ("position_b", "2454.TW", {"close": "100", "sma20": "110", "sma60": "100", "rsi14": "55"}),
            ("position_c", "3008.TW", {"close": "100", "sma20": "105", "sma60": "120", "rsi14": "35"}),
        )

        _snapshot, _input, _provider, monitoring, result = self.run_generation(
            positions,
            specs,
            monitoring_evaluator=CapturingMonitoringEvaluator(fail_position_id="position_b"),
        )

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.MONITORING_FAILED)
        self.assertEqual(result.attempted_position_ids, ("position_a", "position_b"))
        self.assertEqual(result.succeeded_position_ids, ("position_a",))
        self.assertEqual(result.failed_position_ids, ("position_b",))
        self.assertNotIn("position_c", result.attempted_position_ids)
        self.assertEqual(tuple(call[0] for call in monitoring.calls), ("position_a", "position_b"))

    def test_critical_upstream_failure_returns_existing_risk_failure_result(self):
        positions = (self.position("position_a", "2330.TW"),)
        specs = (("position_a", "2330.TW", {"close": "100", "sma20": "105", "sma60": "120", "rsi14": "35"}),)

        _snapshot, _input, _provider, monitoring, result = self.run_generation(
            positions,
            specs,
            production_service=CriticalProductionService(),
        )

        self.assertEqual(result.status, PortfolioRiskGenerationStatus.RISK_EVALUATION_FAILED)
        self.assertEqual(result.attempted_position_ids, ("position_a",))
        self.assertEqual(result.succeeded_position_ids, ())
        self.assertEqual(result.failed_position_ids, ("position_a",))
        self.assertEqual(monitoring.calls, [])
        self.assertIn("artifact adapter failed", result.errors[0])

    def test_no_portfolio_severity_aggregation_or_production_source_change_required(self):
        source = inspect.getsource(PortfolioRiskGenerationService)

        forbidden = (
            "TechnicalRiskPortfolioEvaluator",
            "TechnicalPortfolioGenerationService",
            "TechnicalPortfolioRiskScore",
            "portfolio_severity",
            "weighted",
            "activation",
            "scheduler",
            "dashboard",
            "alert",
            "sqlite",
            "yfinance",
        )
        for forbidden_text in forbidden:
            with self.subTest(forbidden_text=forbidden_text):
                self.assertNotIn(forbidden_text, source)


if __name__ == "__main__":
    unittest.main()
