import inspect
import sys
import unittest
from copy import deepcopy
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

from risk import RiskCategory
from risk import RiskSeverity
from risk_evaluation import PRODUCTION_TECHNICAL_RISK_POLICY_V1
from risk_evaluation import TECHNICAL_RISK_SIGNAL_PRODUCER_VERSION_V1
from risk_evaluation import TECHNICAL_RISK_SIGNAL_RISK_ID_V1
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
from risk_evaluation import MissingDataPolicy
from risk_evaluation import ProductionTechnicalRiskPolicy
from risk_evaluation import ProductionTechnicalRiskPredicateId
from risk_evaluation import ProductionTechnicalRiskReasonCode
from risk_evaluation import ProductionTechnicalRiskRule
from risk_evaluation import ProductionTechnicalRiskThresholdDimension
from risk_evaluation import ProductionTechnicalRiskThresholdDimensionId
from risk_evaluation import ProductionTechnicalRiskThresholdOperator
from risk_evaluation import RiskEvaluationPolicy
from risk_evaluation import RiskFeatureInput
from risk_evaluation import RiskSignalProducer
from risk_evaluation import RiskSignalProducerError
from risk_evaluation import RiskSignalProductionInput
from risk_evaluation import TechnicalRiskEvaluationInput
from risk_evaluation import TechnicalRiskEvaluator
from risk_evaluation import TechnicalRiskEvaluatorError
from risk_evaluation import TechnicalRiskSignalProducer


class CountingEvaluator:
    def __init__(self, *, fail=False):
        self.calls = 0
        self.inputs = []
        self.fail = fail
        self.delegate = TechnicalRiskEvaluator()

    def evaluate(self, evaluation_input):
        self.calls += 1
        self.inputs.append(evaluation_input)
        if self.fail:
            raise TechnicalRiskEvaluatorError("synthetic evaluator failure")
        return self.delegate.evaluate(evaluation_input)


class TechnicalRiskSignalProducerTestCase(unittest.TestCase):

    def created_at(self, day=14):
        return datetime(2026, 8, day, 12, 0, tzinfo=UTC)

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

    def policy(self, **overrides):
        values = {
            "policy_id": None,
            "policy_version": PRODUCTION_TECHNICAL_RISK_POLICY_V1,
            "policy_checksum": None,
            "technical_policy_version": "TECH_RISK_POLICY_V1_RESEARCH_FREEZE",
            "source_research_freeze_id": "freeze_001",
            "source_research_freeze_checksum": "freeze_checksum_001",
            "candidate_id": "TECH_POLICY_CANDIDATE_TEST",
            "candidate_version": "v1",
            "candidate_structural_checksum": "candidate_checksum_001",
            "rules": (
                self.rule(
                    "HIGH_MULTI_EVIDENCE",
                    10,
                    RiskSeverity.HIGH,
                    (
                        ProductionTechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                        ProductionTechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                    ),
                    optional=(ProductionTechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,),
                    reasons=(ProductionTechnicalRiskReasonCode.MULTI_EVIDENCE_TECHNICAL_DETERIORATION,),
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
            "threshold_set_id": "threshold_set_001",
            "threshold_set_version": "v1",
            "threshold_set_checksum": "threshold_checksum_001",
            "threshold_dimensions": self.dimensions(),
            "required_feature_ids": TECH_RISK_REQUIRED_FEATURE_IDS_V1,
            "derived_evidence_version": TECH_RISK_DERIVED_EVIDENCE_V1,
            "numeric_context_version": TECH_RISK_DECIMAL_CONTEXT_V1,
            "severity_mapping_version": TECH_RISK_SEVERITY_MAPPING_V1,
            "reason_mapping_version": TECH_RISK_REASON_MAPPING_V1,
        }
        values.update(overrides)
        return ProductionTechnicalRiskPolicy(**values)

    def generic_policy(self):
        return RiskEvaluationPolicy(
            policy_id="generic_policy",
            version="v1",
            enabled_categories=(RiskCategory.TECHNICAL,),
            required_feature_ids=TECH_RISK_REQUIRED_FEATURE_IDS_V1,
            category_producer_versions={RiskCategory.TECHNICAL: TECHNICAL_RISK_SIGNAL_PRODUCER_VERSION_V1},
            severity_rules={},
            missing_data_policy=MissingDataPolicy.FAIL_EVALUATION,
        )

    def feature(
        self,
        feature_id,
        value,
        *,
        version="v1",
        portfolio_id="portfolio_001",
        position_id="position_001",
        symbol="2330.TW",
        calculation_id="technical_eval_calc_001",
        source_artifact_id=None,
        source_checksum=None,
    ):
        return RiskFeatureInput(
            feature_id=feature_id,
            feature_version=version,
            portfolio_id=portfolio_id,
            position_id=position_id,
            symbol=symbol,
            as_of_date=date(2026, 8, 14),
            feature_date=date(2026, 8, 14),
            value=Decimal(value) if isinstance(value, str) else value,
            source_artifact_id=source_artifact_id or f"artifact_{feature_id}",
            source_checksum=source_checksum or f"checksum_{feature_id}",
            calculation_id=calculation_id,
        )

    def features(self, close="100", sma20="105", sma60="120", rsi14="35", **overrides):
        values = {
            TECH_AS_OF_CLOSE_FEATURE_ID: close,
            TECH_SMA20_FEATURE_ID: sma20,
            TECH_SMA60_FEATURE_ID: sma60,
            TECH_RSI14_FEATURE_ID: rsi14,
        }
        values.update(overrides)
        return (
            self.feature(TECH_RSI14_FEATURE_ID, values[TECH_RSI14_FEATURE_ID], version=TECH_RSI14_FEATURE_VERSION),
            self.feature(TECH_SMA60_FEATURE_ID, values[TECH_SMA60_FEATURE_ID], version=TECH_SMA60_FEATURE_VERSION),
            self.feature(TECH_AS_OF_CLOSE_FEATURE_ID, values[TECH_AS_OF_CLOSE_FEATURE_ID], version=TECH_AS_OF_CLOSE_FEATURE_VERSION),
            self.feature(TECH_SMA20_FEATURE_ID, values[TECH_SMA20_FEATURE_ID], version=TECH_SMA20_FEATURE_VERSION),
        )

    def production_input(self, features=None, **overrides):
        active_features = features if features is not None else self.features()
        values = {
            "portfolio_id": "portfolio_001",
            "position_id": "position_001",
            "symbol": "2330.TW",
            "as_of_date": date(2026, 8, 14),
            "valuation_date": date(2026, 8, 14),
            "feature_version": "technical_risk_feature_set_v1",
            "feature_values": active_features,
            "model_version": None,
            "model_metadata": None,
            "exposure_metadata": {"shares": Decimal("10")},
            "source_artifact_ids": tuple(feature.source_artifact_id for feature in active_features),
            "source_checksums": tuple(feature.source_checksum for feature in active_features),
            "calculation_id": "technical_eval_calc_001",
        }
        values.update(overrides)
        return RiskSignalProductionInput(**values)

    def evaluation_result(self, production_input=None, policy=None):
        active_input = production_input or self.production_input()
        active_policy = policy or self.policy()
        return TechnicalRiskEvaluator().evaluate(
            TechnicalRiskEvaluationInput(
                production_input=active_input,
                policy=active_policy,
            )
        )

    def producer(self, evaluator=None):
        return TechnicalRiskSignalProducer(evaluator=evaluator or CountingEvaluator())

    def produced_signal(self, production_input=None, policy=None, created_at=None, evaluator=None):
        return self.producer(evaluator).produce(
            production_input or self.production_input(),
            policy or self.policy(),
            created_at or self.created_at(),
        )[0]

    def tampered_result(self, result, field_name, value):
        copied = deepcopy(result)
        object.__setattr__(copied, field_name, value)
        return copied

    def test_protocol_compliance_and_basic_signal_fields(self):
        producer: RiskSignalProducer = self.producer()
        produced = producer.produce(self.production_input(), self.policy(), self.created_at())

        self.assertEqual(len(produced), 1)
        signal = produced[0].signal
        self.assertEqual(signal.risk_id, TECHNICAL_RISK_SIGNAL_RISK_ID_V1)
        self.assertEqual(signal.symbol, "2330.TW")
        self.assertEqual(signal.category, RiskCategory.TECHNICAL)
        self.assertEqual(signal.created_at, self.created_at())
        self.assertEqual(produced[0].producer_version, TECHNICAL_RISK_SIGNAL_PRODUCER_VERSION_V1)

    def test_low_medium_and_high_evaluation_produce_signals(self):
        low = self.produced_signal(self.production_input(self.features(close="110", sma20="100", sma60="100", rsi14="55")))
        medium = self.produced_signal(self.production_input(self.features(close="94", sma20="100", sma60="100", rsi14="55")))
        high = self.produced_signal(self.production_input(self.features(close="80", sma20="90", sma60="100", rsi14="55")))

        self.assertEqual(low.signal.severity, RiskSeverity.LOW)
        self.assertEqual(medium.signal.severity, RiskSeverity.MEDIUM)
        self.assertEqual(high.signal.severity, RiskSeverity.HIGH)
        self.assertIn(ProductionTechnicalRiskReasonCode.NO_ELEVATED_TECHNICAL_DOWNSIDE_EVIDENCE.value, low.signal.trigger_reason)
        self.assertNotEqual(low, ())

    def test_evaluator_called_exactly_once_and_failure_raises(self):
        evaluator = CountingEvaluator()
        produced = self.producer(evaluator).produce(self.production_input(), self.policy(), self.created_at())

        self.assertEqual(len(produced), 1)
        self.assertEqual(evaluator.calls, 1)
        self.assertIsInstance(evaluator.inputs[0], TechnicalRiskEvaluationInput)

        failing = CountingEvaluator(fail=True)
        with self.assertRaisesRegex(RiskSignalProducerError, "synthetic evaluator failure"):
            self.producer(failing).produce(self.production_input(), self.policy(), self.created_at())
        self.assertEqual(failing.calls, 1)

    def test_generic_policy_and_timezone_naive_created_at_rejected(self):
        with self.assertRaisesRegex(RiskSignalProducerError, "ProductionTechnicalRiskPolicy"):
            self.producer().produce(self.production_input(), self.generic_policy(), self.created_at())
        with self.assertRaisesRegex(RiskSignalProducerError, "timezone-aware"):
            self.producer().produce(self.production_input(), self.policy(), datetime(2026, 8, 14, 12, 0))

    def test_projection_helper_preserves_lineage(self):
        production_input = self.production_input()
        policy = self.policy()
        evaluation_result = self.evaluation_result(production_input, policy)
        produced = self.producer().produce_from_evaluation(
            production_input,
            policy,
            evaluation_result,
            self.created_at(),
        )

        self.assertEqual(produced.policy_id, policy.policy_id)
        self.assertEqual(produced.policy_version, policy.policy_version)
        self.assertEqual(produced.policy_checksum, policy.policy_checksum)
        self.assertEqual(produced.evaluation_id, evaluation_result.evaluation_id)
        self.assertEqual(produced.evaluation_checksum, evaluation_result.evaluation_checksum)
        self.assertEqual(produced.portfolio_id, production_input.portfolio_id)
        self.assertEqual(produced.position_id, production_input.position_id)
        self.assertEqual(produced.as_of_date, production_input.as_of_date)
        self.assertEqual(produced.valuation_date, production_input.valuation_date)
        self.assertEqual(produced.source_feature_ids, tuple(reference.feature_id for reference in evaluation_result.feature_references))
        self.assertEqual(produced.source_checksums, evaluation_result.source_checksums)
        self.assertEqual(produced.calculation_id, production_input.calculation_id)

    def test_projection_context_mismatches_fail_closed(self):
        production_input = self.production_input()
        policy = self.policy()
        evaluation_result = self.evaluation_result(production_input, policy)
        mismatches = (
            ("portfolio_id", "portfolio_002", "portfolio_id"),
            ("position_id", "position_002", "position_id"),
            ("symbol", "2454.TW", "symbol"),
            ("as_of_date", date(2026, 8, 15), "as_of_date"),
            ("valuation_date", date(2026, 8, 15), "valuation_date"),
            ("calculation_id", "calc_002", "calculation_id"),
            ("policy_id", "policy_002", "policy_id"),
            ("policy_version", "policy_v2", "policy_version"),
            ("policy_checksum", "policy_checksum_002", "policy_checksum"),
            ("source_artifact_ids", ("different_artifact",), "source_artifact_ids"),
            ("source_checksums", ("different_checksum",), "source_checksums"),
        )
        for field_name, value, message in mismatches:
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(RiskSignalProducerError, message):
                    self.producer().produce_from_evaluation(
                        production_input,
                        policy,
                        self.tampered_result(evaluation_result, field_name, value),
                        self.created_at(),
                    )

        tampered_reference = replace(
            evaluation_result.feature_references[0],
            source_checksum="changed_feature_checksum",
        )
        with self.assertRaisesRegex(RiskSignalProducerError, "source feature lineage"):
            self.producer().produce_from_evaluation(
                production_input,
                policy,
                self.tampered_result(
                    evaluation_result,
                    "feature_references",
                    (tampered_reference, *evaluation_result.feature_references[1:]),
                ),
                self.created_at(),
            )

    def test_projection_rejects_invalid_result_type_and_critical(self):
        production_input = self.production_input()
        policy = self.policy()
        evaluation_result = self.evaluation_result(production_input, policy)

        with self.assertRaisesRegex(RiskSignalProducerError, "TechnicalRiskEvaluationResult"):
            self.producer().produce_from_evaluation(production_input, policy, object(), self.created_at())
        with self.assertRaisesRegex(RiskSignalProducerError, "CRITICAL"):
            self.producer().produce_from_evaluation(
                production_input,
                policy,
                self.tampered_result(evaluation_result, "severity", RiskSeverity.CRITICAL),
                self.created_at(),
            )

    def test_missing_feature_not_converted_to_low_or_empty_tuple(self):
        incomplete = tuple(feature for feature in self.features() if feature.feature_id != TECH_RSI14_FEATURE_ID)

        with self.assertRaisesRegex(RiskSignalProducerError, "Missing required"):
            self.producer().produce(self.production_input(incomplete), self.policy(), self.created_at())

    def test_same_symbol_different_position_preserves_severity_but_lineage_differs(self):
        base_input = self.production_input()
        alternate_features = tuple(
            self.feature(
                feature.feature_id,
                feature.value,
                version=feature.feature_version,
                portfolio_id="portfolio_002",
                position_id="position_002",
            )
            for feature in self.features()
        )
        alternate_input = self.production_input(
            alternate_features,
            portfolio_id="portfolio_002",
            position_id="position_002",
        )

        base = self.produced_signal(base_input)
        alternate = self.produced_signal(alternate_input)

        self.assertEqual(base.signal.severity, alternate.signal.severity)
        self.assertNotEqual(base.position_id, alternate.position_id)
        self.assertNotEqual(base.evaluation_checksum, alternate.evaluation_checksum)

    def test_deterministic_output_and_timestamp_semantics(self):
        production_input = self.production_input()
        policy = self.policy()
        first = self.produced_signal(production_input, policy, self.created_at())
        second = self.produced_signal(production_input, policy, self.created_at())
        changed_time = self.produced_signal(production_input, policy, self.created_at(day=15))

        self.assertEqual(first, second)
        self.assertNotEqual(first.signal.created_at, changed_time.signal.created_at)
        self.assertEqual(first.evaluation_checksum, changed_time.evaluation_checksum)

    def test_trigger_reason_is_neutral_and_not_research_dump(self):
        trigger_reason = self.produced_signal().signal.trigger_reason

        self.assertIn("technical downside risk evidence", trigger_reason)
        forbidden = (
            "BUY",
            "SELL",
            "HOLD",
            "ENTRY",
            "EXIT",
            "TARGET PRICE",
            "STOP LOSS",
            "TRADING SCORE",
            "{",
            "}",
            "MAE",
            "Holdout",
        )
        for token in forbidden:
            self.assertNotIn(token, trigger_reason)

    def test_producer_does_not_mutate_input_policy_or_evaluation_result(self):
        production_input = self.production_input()
        policy = self.policy()
        evaluation_result = self.evaluation_result(production_input, policy)
        before = (production_input, policy, evaluation_result)

        self.producer().produce_from_evaluation(production_input, policy, evaluation_result, self.created_at())

        self.assertEqual(before, (production_input, policy, evaluation_result))
        with self.assertRaises(FrozenInstanceError):
            self.producer().producer_version = "other"

    def test_public_api_exports(self):
        import risk_evaluation

        for name in (
            "TECHNICAL_RISK_SIGNAL_PRODUCER_VERSION_V1",
            "TECHNICAL_RISK_SIGNAL_RISK_ID_V1",
            "TechnicalRiskSignalProducer",
        ):
            self.assertIn(name, risk_evaluation.__all__)

    def test_source_boundary_no_duplicate_evaluation_or_data_access(self):
        import risk_evaluation.technical_signal_producer as technical_signal_producer

        source = inspect.getsource(technical_signal_producer)
        forbidden = (
            "close_vs_sma20",
            "close_vs_sma60",
            "relative_sma_spread",
            "LESS_THAN_OR_EQUAL",
            "required_predicates",
            "rule_priority",
            "threshold_dimensions",
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "risk_oos",
            "risk_integration",
            "targets",
            "datasets",
            "features.calculators",
            "sqlite",
            "LiveDataStore",
            "ResearchDataStore",
            "yfinance",
            "open(",
            "latest",
            "default_policy",
            "search",
            "optimize",
            "app.py",
            "dashboard",
            "shares",
            "quantity",
        )
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
