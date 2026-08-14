import inspect
import sys
import unittest
from dataclasses import FrozenInstanceError
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

import portfolio_generation.technical_risk_portfolio_evaluator as evaluator_module
from portfolio_generation import TechnicalRiskArtifactAdapter
from portfolio_generation import TechnicalRiskPortfolioEvaluator
from portfolio_generation import TechnicalRiskPortfolioEvaluatorError
from portfolio_generation import TechnicalRiskProductionInputProvider
from portfolio_generation import build_risk_artifact_id
from portfolio_generation import RiskEvaluationOutput
from portfolio_generation import PortfolioRiskGenerationService
from risk import HoldingType
from risk import PortfolioPosition
from risk import RiskArtifact
from risk import RiskAssessment
from risk import RiskContext
from risk import RiskSeverity
from risk import RiskCategory
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
from risk_evaluation import ProductionTechnicalRiskPolicy
from risk_evaluation import ProductionTechnicalRiskPredicateId
from risk_evaluation import ProductionTechnicalRiskReasonCode
from risk_evaluation import ProductionTechnicalRiskRule
from risk_evaluation import ProductionTechnicalRiskThresholdDimension
from risk_evaluation import ProductionTechnicalRiskThresholdDimensionId
from risk_evaluation import ProductionTechnicalRiskThresholdOperator
from risk_evaluation import RiskEvaluationPolicy
from risk_evaluation import RiskFeatureInput
from risk_evaluation import RiskSignalProductionInput
from risk_evaluation import ProducedRiskSignal
from risk_evaluation import TechnicalRiskProductionResult
from risk_evaluation import TechnicalRiskProductionService
from risk_evaluation import MissingDataPolicy


class StaticTechnicalRiskInputProvider:
    def __init__(self, inputs_by_artifact_id, *, fail=False, invalid_output=False):
        self.inputs_by_artifact_id = inputs_by_artifact_id
        self.fail = fail
        self.invalid_output = invalid_output
        self.calls = []

    def resolve(self, position, context, risk_artifact_id):
        self.calls.append((position, context, risk_artifact_id))
        if self.fail:
            raise RuntimeError("synthetic provider failure")
        if self.invalid_output:
            return object()
        return self.inputs_by_artifact_id[risk_artifact_id]


class CountingProductionService:
    def __init__(self):
        self.calls = []
        self.delegate = TechnicalRiskProductionService()

    def run(self, *, input, policy, created_at):
        self.calls.append((input, policy, created_at))
        return self.delegate.run(input=input, policy=policy, created_at=created_at)


class CountingArtifactAdapter:
    def __init__(self):
        self.calls = []
        self.delegate = TechnicalRiskArtifactAdapter()

    def build(self, *, result, context, position, artifact_id, created_at):
        self.calls.append((result, context, position, artifact_id, created_at))
        return self.delegate.build(
            result=result,
            context=context,
            position=position,
            artifact_id=artifact_id,
            created_at=created_at,
        )


class TechnicalRiskPortfolioEvaluatorTestCase(unittest.TestCase):

    def created_at(self, day=14):
        return datetime(2026, 8, day, 12, 0, tzinfo=UTC)

    def position(self, *, symbol="2330.TW", shares=Decimal("10"), holding_type=HoldingType.WHOLE_SHARE):
        return PortfolioPosition(
            symbol=symbol,
            shares=shares,
            average_cost=Decimal("650.00"),
            holding_type=holding_type,
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )

    def context(self, *, symbol="2330.TW", calculation_id="technical_calc_001"):
        return RiskContext(
            portfolio_id="portfolio_001",
            symbol=symbol,
            analysis_date=date(2026, 8, 14),
            feature_version="technical_risk_feature_set_v1",
            calculation_id=calculation_id,
            model_version=None,
        )

    def dimension(self, dimension_id, value):
        return ProductionTechnicalRiskThresholdDimension(
            dimension_id=dimension_id,
            operator=ProductionTechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            canonical_value=Decimal(value),
        )

    def dimensions(
        self,
        close_vs_sma20="-0.05",
        close_vs_sma60="-0.10",
        relative_sma_spread="-0.05",
        rsi14="40",
    ):
        return (
            self.dimension(ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, close_vs_sma20),
            self.dimension(ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, close_vs_sma60),
            self.dimension(ProductionTechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, relative_sma_spread),
            self.dimension(ProductionTechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, rsi14),
        )

    def rule(self, rule_id, priority, severity, required, optional=(), reasons=None):
        return ProductionTechnicalRiskRule(
            rule_id=rule_id,
            rule_priority=priority,
            severity=severity,
            required_predicates=required,
            optional_confirmation_predicates=optional,
            reason_codes=reasons
            if reasons is not None
            else (ProductionTechnicalRiskReasonCode.MULTI_EVIDENCE_TECHNICAL_DETERIORATION,),
        )

    def policy(self):
        return ProductionTechnicalRiskPolicy(
            policy_id=None,
            policy_version=PRODUCTION_TECHNICAL_RISK_POLICY_V1,
            policy_checksum=None,
            technical_policy_version="TECH_RISK_POLICY_V1_RESEARCH_FREEZE",
            source_research_freeze_id="freeze_001",
            source_research_freeze_checksum="freeze_checksum_001",
            candidate_id="TECH_POLICY_CANDIDATE_TEST",
            candidate_version="v1",
            candidate_structural_checksum="candidate_checksum_001",
            rules=(
                self.rule(
                    "HIGH_MULTI_EVIDENCE",
                    10,
                    RiskSeverity.HIGH,
                    (
                        ProductionTechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                        ProductionTechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                    ),
                    optional=(ProductionTechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,),
                ),
                self.rule(
                    "MEDIUM_SHORT_WEAKNESS",
                    20,
                    RiskSeverity.MEDIUM,
                    (ProductionTechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS,),
                    optional=(ProductionTechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,),
                    reasons=(ProductionTechnicalRiskReasonCode.PRICE_POSITION_SHORT_TERM_WEAKNESS,),
                ),
            ),
            threshold_set_id="threshold_set_001",
            threshold_set_version="v1",
            threshold_set_checksum="threshold_checksum_001",
            threshold_dimensions=self.dimensions(),
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
        portfolio_id="portfolio_001",
        position_id="position_001",
        symbol="2330.TW",
        as_of_date=date(2026, 8, 14),
        calculation_id="technical_calc_001",
        version="v1",
    ):
        return RiskFeatureInput(
            feature_id=feature_id,
            feature_version=version,
            portfolio_id=portfolio_id,
            position_id=position_id,
            symbol=symbol,
            as_of_date=as_of_date,
            feature_date=as_of_date,
            value=Decimal(value) if isinstance(value, str) else value,
            source_artifact_id=f"artifact_{feature_id}_{position_id}",
            source_checksum=f"checksum_{feature_id}_{position_id}",
            calculation_id=calculation_id,
        )

    def features(
        self,
        *,
        close="100",
        sma20="105",
        sma60="120",
        rsi14="35",
        portfolio_id="portfolio_001",
        position_id="position_001",
        symbol="2330.TW",
        as_of_date=date(2026, 8, 14),
        calculation_id="technical_calc_001",
    ):
        return (
            self.feature(TECH_AS_OF_CLOSE_FEATURE_ID, close, version=TECH_AS_OF_CLOSE_FEATURE_VERSION, portfolio_id=portfolio_id, position_id=position_id, symbol=symbol, as_of_date=as_of_date, calculation_id=calculation_id),
            self.feature(TECH_RSI14_FEATURE_ID, rsi14, version=TECH_RSI14_FEATURE_VERSION, portfolio_id=portfolio_id, position_id=position_id, symbol=symbol, as_of_date=as_of_date, calculation_id=calculation_id),
            self.feature(TECH_SMA20_FEATURE_ID, sma20, version=TECH_SMA20_FEATURE_VERSION, portfolio_id=portfolio_id, position_id=position_id, symbol=symbol, as_of_date=as_of_date, calculation_id=calculation_id),
            self.feature(TECH_SMA60_FEATURE_ID, sma60, version=TECH_SMA60_FEATURE_VERSION, portfolio_id=portfolio_id, position_id=position_id, symbol=symbol, as_of_date=as_of_date, calculation_id=calculation_id),
        )

    def production_input(self, *, position_id="position_001", symbol="2330.TW", calculation_id="technical_calc_001", features=None, **overrides):
        values = {
            "portfolio_id": "portfolio_001",
            "position_id": position_id,
            "symbol": symbol,
            "as_of_date": date(2026, 8, 14),
            "valuation_date": date(2026, 8, 14),
            "feature_version": "technical_risk_feature_set_v1",
            "feature_values": (),
            "model_version": None,
            "model_metadata": None,
            "exposure_metadata": None,
            "source_artifact_ids": (),
            "source_checksums": (),
            "calculation_id": calculation_id,
        }
        values.update(overrides)
        active_features = features if features is not None else self.features(
            portfolio_id=values["portfolio_id"],
            position_id=values["position_id"],
            symbol=values["symbol"],
            as_of_date=values["as_of_date"],
            calculation_id=values["calculation_id"],
        )
        values["feature_values"] = active_features
        values["source_artifact_ids"] = tuple(feature.source_artifact_id for feature in active_features)
        values["source_checksums"] = tuple(feature.source_checksum for feature in active_features)
        return RiskSignalProductionInput(**values)

    def artifact_id(self, position_id="position_001", calculation_id="technical_calc_001"):
        return build_risk_artifact_id(calculation_id, position_id)

    def evaluator(self, input_provider, *, policy=None, created_at=None, production_service=None, artifact_adapter=None):
        return TechnicalRiskPortfolioEvaluator(
            input_provider=input_provider,
            policy=policy or self.policy(),
            created_at=created_at or self.created_at(),
            production_service=production_service or TechnicalRiskProductionService(),
            artifact_adapter=artifact_adapter or TechnicalRiskArtifactAdapter(),
        )

    def test_provider_protocol_accepted_and_receives_exact_inputs(self):
        production_input = self.production_input()
        provider = StaticTechnicalRiskInputProvider({self.artifact_id(): production_input})
        evaluator = self.evaluator(provider)
        position = self.position()
        context = self.context()

        evaluator.evaluate(position, context, self.artifact_id())

        self.assertIsInstance(provider, TechnicalRiskProductionInputProvider)
        self.assertEqual(provider.calls, [(position, context, self.artifact_id())])

    def test_low_medium_high_end_to_end_outputs(self):
        cases = (
            (RiskSeverity.LOW, {"close": "130", "sma20": "105", "sma60": "100", "rsi14": "55"}),
            (RiskSeverity.MEDIUM, {"close": "100", "sma20": "110", "sma60": "100", "rsi14": "55"}),
            (RiskSeverity.HIGH, {"close": "100", "sma20": "105", "sma60": "120", "rsi14": "35"}),
        )
        for expected_severity, feature_values in cases:
            with self.subTest(expected_severity=expected_severity):
                features = self.features(**feature_values)
                production_input = self.production_input(features=features)
                evaluator = self.evaluator(StaticTechnicalRiskInputProvider({self.artifact_id(): production_input}))

                output = evaluator.evaluate(self.position(), self.context(), self.artifact_id())

                self.assertIsInstance(output, RiskEvaluationOutput)
                self.assertIsInstance(output.risk_artifact, RiskArtifact)
                self.assertEqual(output.position_id, "position_001")
                self.assertEqual(output.symbol, "2330.TW")
                self.assertEqual(output.risk_artifact.signals[0].severity, expected_severity)
                self.assertEqual(output.risk_artifact.artifact_id, self.artifact_id())

    def test_reuses_production_service_and_artifact_adapter_once(self):
        provider = StaticTechnicalRiskInputProvider({self.artifact_id(): self.production_input()})
        production_service = CountingProductionService()
        artifact_adapter = CountingArtifactAdapter()
        evaluator = self.evaluator(
            provider,
            production_service=production_service,
            artifact_adapter=artifact_adapter,
        )

        output = evaluator.evaluate(self.position(), self.context(), self.artifact_id())

        self.assertEqual(len(production_service.calls), 1)
        self.assertEqual(len(artifact_adapter.calls), 1)
        self.assertEqual(production_service.calls[0][1], evaluator.policy)
        self.assertEqual(production_service.calls[0][2], evaluator.created_at)
        self.assertEqual(artifact_adapter.calls[0][3], self.artifact_id())
        self.assertEqual(output.risk_artifact.calculation_metadata["technical_position_id"], "position_001")

    def test_invalid_provider_output_and_provider_error_fail_closed(self):
        with self.assertRaisesRegex(TechnicalRiskPortfolioEvaluatorError, "provider returned invalid"):
            self.evaluator(StaticTechnicalRiskInputProvider({}, invalid_output=True)).evaluate(
                self.position(),
                self.context(),
                self.artifact_id(),
            )

        with self.assertRaisesRegex(TechnicalRiskPortfolioEvaluatorError, "provider failed"):
            self.evaluator(StaticTechnicalRiskInputProvider({}, fail=True)).evaluate(
                self.position(),
                self.context(),
                self.artifact_id(),
            )

    def test_wrong_position_id_fails_artifact_id_consistency_even_with_same_symbol(self):
        wrong_input = self.production_input(position_id="position_wrong")

        with self.assertRaisesRegex(TechnicalRiskPortfolioEvaluatorError, "position_id artifact"):
            self.evaluator(StaticTechnicalRiskInputProvider({self.artifact_id(): wrong_input})).evaluate(
                self.position(),
                self.context(),
                self.artifact_id(),
            )

    def test_same_symbol_multiple_positions_resolve_by_artifact_id_not_symbol(self):
        first_input = self.production_input(position_id="position_a")
        second_input = self.production_input(position_id="position_b")
        first_artifact_id = self.artifact_id("position_a")
        second_artifact_id = self.artifact_id("position_b")
        provider = StaticTechnicalRiskInputProvider(
            {
                first_artifact_id: first_input,
                second_artifact_id: second_input,
            }
        )
        evaluator = self.evaluator(provider)

        first = evaluator.evaluate(self.position(), self.context(), first_artifact_id)
        second = evaluator.evaluate(self.position(), self.context(), second_artifact_id)

        self.assertEqual(first.position_id, "position_a")
        self.assertEqual(second.position_id, "position_b")
        self.assertEqual(first.symbol, second.symbol)
        self.assertNotEqual(first.risk_artifact.artifact_id, second.risk_artifact.artifact_id)

    def test_context_mismatches_fail_closed(self):
        cases = (
            (self.production_input(portfolio_id="portfolio_other"), self.context(), "portfolio_id"),
            (self.production_input(symbol="2454.TW"), self.context(), "symbol"),
            (self.production_input(calculation_id="technical_calc_other"), self.context(), "calculation_id"),
            (self.production_input(as_of_date=date(2026, 8, 13)), self.context(), "as_of_date"),
            (self.production_input(feature_version="other_feature_set"), self.context(), "feature_version"),
            (self.production_input(model_version="model_v1"), self.context(), "model_version"),
        )
        for production_input, context, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(TechnicalRiskPortfolioEvaluatorError, expected):
                    self.evaluator(StaticTechnicalRiskInputProvider({self.artifact_id(): production_input})).evaluate(
                        self.position(),
                        context,
                        self.artifact_id(),
                    )

    def test_wrong_policy_type_and_naive_created_at_rejected(self):
        provider = StaticTechnicalRiskInputProvider({self.artifact_id(): self.production_input()})

        with self.assertRaisesRegex(TechnicalRiskPortfolioEvaluatorError, "ProductionTechnicalRiskPolicy"):
            TechnicalRiskPortfolioEvaluator(
                input_provider=provider,
                policy=RiskEvaluationPolicy(
                    policy_id="generic",
                    version="v1",
                    enabled_categories=(RiskCategory.TECHNICAL,),
                    required_feature_ids=("TECH_AS_OF_CLOSE_V1",),
                    category_producer_versions={RiskCategory.TECHNICAL: TECHNICAL_RISK_SIGNAL_PRODUCER_VERSION_V1},
                    severity_rules={},
                    missing_data_policy=MissingDataPolicy.FAIL_EVALUATION,
                ),
                created_at=self.created_at(),
            )

        with self.assertRaisesRegex(TechnicalRiskPortfolioEvaluatorError, "timezone-aware"):
            TechnicalRiskPortfolioEvaluator(
                input_provider=provider,
                policy=self.policy(),
                created_at=datetime(2026, 8, 14, 12, 0),
            )

    def test_production_service_and_artifact_adapter_errors_wrap_with_cause(self):
        class FailingProductionService:
            def run(self, *, input, policy, created_at):
                raise RuntimeError("service failure")

        class FailingArtifactAdapter:
            def build(self, *, result, context, position, artifact_id, created_at):
                raise RuntimeError("adapter failure")

        provider = StaticTechnicalRiskInputProvider({self.artifact_id(): self.production_input()})
        with self.assertRaisesRegex(TechnicalRiskPortfolioEvaluatorError, "production service") as service_context:
            self.evaluator(provider, production_service=FailingProductionService()).evaluate(
                self.position(),
                self.context(),
                self.artifact_id(),
            )
        self.assertIsInstance(service_context.exception.__cause__, RuntimeError)

        with self.assertRaisesRegex(TechnicalRiskPortfolioEvaluatorError, "artifact adapter") as adapter_context:
            self.evaluator(provider, artifact_adapter=FailingArtifactAdapter()).evaluate(
                self.position(),
                self.context(),
                self.artifact_id(),
            )
        self.assertIsInstance(adapter_context.exception.__cause__, RuntimeError)

    def test_critical_severity_fails_through_artifact_adapter_chain(self):
        class CriticalProductionService:
            def run(inner_self, *, input, policy, created_at):
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

        provider = StaticTechnicalRiskInputProvider({self.artifact_id(): self.production_input()})

        with self.assertRaisesRegex(TechnicalRiskPortfolioEvaluatorError, "artifact adapter") as context:
            self.evaluator(provider, production_service=CriticalProductionService()).evaluate(
                self.position(),
                self.context(),
                self.artifact_id(),
            )
        self.assertIn("CRITICAL", str(context.exception.__cause__))

    def test_same_semantic_run_is_deterministic(self):
        provider = StaticTechnicalRiskInputProvider({self.artifact_id(): self.production_input()})
        evaluator = self.evaluator(provider)

        first = evaluator.evaluate(self.position(), self.context(), self.artifact_id())
        second = evaluator.evaluate(self.position(), self.context(), self.artifact_id())

        self.assertEqual(first, second)
        self.assertEqual(first.risk_artifact.checksum, second.risk_artifact.checksum)

    def test_whole_and_fractional_shares_do_not_change_severity(self):
        production_input = self.production_input()
        evaluator = self.evaluator(StaticTechnicalRiskInputProvider({self.artifact_id(): production_input}))

        whole = evaluator.evaluate(self.position(shares=Decimal("10")), self.context(), self.artifact_id())
        fractional = evaluator.evaluate(
            self.position(shares=Decimal("10.5"), holding_type=HoldingType.FRACTIONAL_SHARE),
            self.context(),
            self.artifact_id(),
        )

        self.assertEqual(whole.risk_artifact.signals[0].severity, RiskSeverity.HIGH)
        self.assertEqual(fractional.risk_artifact.signals[0].severity, RiskSeverity.HIGH)
        self.assertNotEqual(whole.risk_artifact.position_identity, fractional.risk_artifact.position_identity)

    def test_evaluator_is_immutable_and_exports_public_api(self):
        provider = StaticTechnicalRiskInputProvider({self.artifact_id(): self.production_input()})
        evaluator = self.evaluator(provider)

        with self.assertRaises(FrozenInstanceError):
            evaluator.created_at = self.created_at(15)

        self.assertIs(TechnicalRiskPortfolioEvaluator, evaluator_module.TechnicalRiskPortfolioEvaluator)
        self.assertIs(TechnicalRiskPortfolioEvaluatorError, evaluator_module.TechnicalRiskPortfolioEvaluatorError)
        self.assertIs(TechnicalRiskProductionInputProvider, evaluator_module.TechnicalRiskProductionInputProvider)

    def test_source_boundary_no_forbidden_runtime_dependencies(self):
        source = inspect.getsource(evaluator_module)

        forbidden = (
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "latest",
            "default policy",
            "activation",
            "sqlite",
            "DB",
            "yfinance",
            "network",
            "LiveDataStore",
            "ResearchDataStore",
            "TechnicalRiskEvaluator",
            "TechnicalRiskSignalProducer",
            "RiskSignal(",
            "RiskAssessment.from_signals",
            "risk_oos",
            "risk_integration",
            "targets",
            "datasets",
            "dashboard",
            "app.py",
            "scheduler",
            "alert",
            "persistence",
            "BUY",
            "SELL",
            "HOLD recommendation",
            "ENTRY",
            "EXIT",
            "TARGET PRICE",
            "STOP LOSS",
            "TRADING SCORE",
        )
        for forbidden_text in forbidden:
            with self.subTest(forbidden_text=forbidden_text):
                self.assertNotIn(forbidden_text, source)

    def test_portfolio_generation_service_not_modified_for_technical(self):
        source = inspect.getsource(PortfolioRiskGenerationService)

        self.assertNotIn("TechnicalRiskPortfolioEvaluator", source)
        self.assertNotIn("TechnicalRiskProductionService", source)
        self.assertNotIn("TechnicalRiskArtifactAdapter", source)


if __name__ == "__main__":
    unittest.main()
