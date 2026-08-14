import inspect
import sys
import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError
from dataclasses import replace
from datetime import date
from decimal import Decimal
from decimal import ROUND_DOWN
from decimal import ROUND_UP
from decimal import getcontext
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk import RiskSeverity
from risk_evaluation import PRODUCTION_TECHNICAL_RISK_POLICY_V1
from risk_evaluation import TECHNICAL_RISK_EVALUATOR_VERSION_V1
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
from risk_evaluation import RiskFeatureInput
from risk_evaluation import RiskSignalProductionInput
from risk_evaluation import TechnicalRiskEvaluationInput
from risk_evaluation import TechnicalRiskEvaluationResult
from risk_evaluation import TechnicalRiskEvaluator
from risk_evaluation import TechnicalRiskEvaluatorError
from risk_evaluation import TechnicalRiskPredicateState


class TechnicalRiskEvaluatorTestCase(unittest.TestCase):

    def setUp(self):
        self.evaluator = TechnicalRiskEvaluator()

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
        feature_value = Decimal(value) if isinstance(value, str) else value
        return RiskFeatureInput(
            feature_id=feature_id,
            feature_version=version,
            portfolio_id=portfolio_id,
            position_id=position_id,
            symbol=symbol,
            as_of_date=date(2026, 8, 14),
            feature_date=date(2026, 8, 14),
            value=feature_value,
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

    def evaluation_input(self, production_input=None, policy=None, **overrides):
        values = {
            "production_input": production_input or self.production_input(),
            "policy": policy or self.policy(),
            "evaluator_version": TECHNICAL_RISK_EVALUATOR_VERSION_V1,
            "numeric_context_version": TECH_RISK_DECIMAL_CONTEXT_V1,
        }
        values.update(overrides)
        return TechnicalRiskEvaluationInput(**values)

    def evaluate(self, production_input=None, policy=None, **overrides):
        return self.evaluator.evaluate(self.evaluation_input(production_input, policy, **overrides))

    def states_by_predicate(self, result):
        return {state.predicate_id: state for state in result.predicate_states}

    def test_valid_low_medium_and_high_results(self):
        low = self.evaluate(self.production_input(self.features(close="110", sma20="100", sma60="100", rsi14="55")))
        medium = self.evaluate(self.production_input(self.features(close="94", sma20="100", sma60="100", rsi14="55")))
        high = self.evaluate(self.production_input(self.features(close="80", sma20="90", sma60="100", rsi14="55")))

        self.assertEqual(low.severity, RiskSeverity.LOW)
        self.assertIsNone(low.matched_rule_id)
        self.assertEqual(low.reason_codes, (ProductionTechnicalRiskReasonCode.NO_ELEVATED_TECHNICAL_DOWNSIDE_EVIDENCE,))
        self.assertEqual(medium.severity, RiskSeverity.MEDIUM)
        self.assertEqual(medium.matched_rule_id, "MEDIUM_SHORT_WEAKNESS")
        self.assertEqual(high.severity, RiskSeverity.HIGH)
        self.assertEqual(high.matched_rule_id, "HIGH_MULTI_EVIDENCE")

    def test_derived_evidence_formulas_exact(self):
        result = self.evaluate(self.production_input(self.features(close="90", sma20="100", sma60="120", rsi14="35")))

        self.assertEqual(result.derived_evidence.close_vs_sma20, Decimal("-0.1"))
        self.assertEqual(result.derived_evidence.close_vs_sma60, Decimal("-0.25"))
        self.assertEqual(result.derived_evidence.relative_sma_spread, Decimal("-0.1666666666666666666666666666666667"))

    def test_predicate_mapping_and_boundary_equality(self):
        result = self.evaluate(self.production_input(self.features(close="95", sma20="100", sma60="105.55555555555555555555555555555556", rsi14="40")))
        states = self.states_by_predicate(result)

        self.assertTrue(states[ProductionTechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS].is_triggered)
        self.assertTrue(states[ProductionTechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS].is_triggered)
        self.assertTrue(states[ProductionTechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS].is_triggered)
        self.assertTrue(states[ProductionTechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION].is_triggered)
        self.assertEqual(
            states[ProductionTechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS].threshold_dimension_id,
            ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF,
        )
        self.assertEqual(states[ProductionTechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS].operator, ProductionTechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL)

    def test_optional_confirmation_does_not_gate_or_upgrade(self):
        policy = self.policy(
            rules=(
                self.rule(
                    "MEDIUM_WITH_OPTIONAL_FALSE",
                    10,
                    RiskSeverity.MEDIUM,
                    (ProductionTechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS,),
                    optional=(ProductionTechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,),
                    reasons=(ProductionTechnicalRiskReasonCode.PRICE_POSITION_SHORT_TERM_WEAKNESS,),
                ),
            )
        )
        false_optional = self.evaluate(self.production_input(self.features(close="94", sma20="100", sma60="100", rsi14="55")), policy)
        true_optional = self.evaluate(self.production_input(self.features(close="94", sma20="100", sma60="100", rsi14="35")), policy)

        self.assertEqual(false_optional.severity, RiskSeverity.MEDIUM)
        self.assertEqual(true_optional.severity, RiskSeverity.MEDIUM)
        self.assertEqual(false_optional.matched_rule_id, true_optional.matched_rule_id)

    def test_missing_required_features_fail_closed(self):
        for missing_feature in (
            TECH_AS_OF_CLOSE_FEATURE_ID,
            TECH_SMA20_FEATURE_ID,
            TECH_SMA60_FEATURE_ID,
            TECH_RSI14_FEATURE_ID,
        ):
            features = tuple(feature for feature in self.features() if feature.feature_id != missing_feature)
            with self.assertRaisesRegex(TechnicalRiskEvaluatorError, "Missing required"):
                self.evaluate(self.production_input(features))

    def test_invalid_numeric_inputs_fail_closed(self):
        for feature_id in (TECH_SMA20_FEATURE_ID, TECH_SMA60_FEATURE_ID):
            with self.assertRaisesRegex(TechnicalRiskEvaluatorError, "positive"):
                self.evaluate(self.production_input(self.features(**{feature_id: "0"})))
            with self.assertRaisesRegex(TechnicalRiskEvaluatorError, "positive"):
                self.evaluate(self.production_input(self.features(**{feature_id: "-1"})))

        with self.assertRaisesRegex(TechnicalRiskEvaluatorError, "finite"):
            self.evaluate(self.production_input(self.features(**{TECH_RSI14_FEATURE_ID: float("nan")})))
        with self.assertRaisesRegex(Exception, "numeric"):
            self.production_input(self.features(**{TECH_RSI14_FEATURE_ID: True}))

    def test_as_of_close_positive_contract_preserved(self):
        with self.assertRaisesRegex(Exception, "positive"):
            self.production_input(self.features(**{TECH_AS_OF_CLOSE_FEATURE_ID: "0"}))

    def test_feature_version_mismatch_rejected(self):
        bad_feature = self.feature(TECH_SMA20_FEATURE_ID, "100", version="v2")
        features = tuple(bad_feature if feature.feature_id == TECH_SMA20_FEATURE_ID else feature for feature in self.features())
        with self.assertRaisesRegex(TechnicalRiskEvaluatorError, "version"):
            self.evaluate(self.production_input(features))

    def test_input_wrapper_version_and_policy_context_validation(self):
        with self.assertRaisesRegex(TechnicalRiskEvaluatorError, "evaluator version"):
            self.evaluation_input(evaluator_version="TECHNICAL_RISK_EVALUATOR_V2")
        with self.assertRaisesRegex(TechnicalRiskEvaluatorError, "numeric_context_version"):
            self.evaluation_input(numeric_context_version="OTHER_CONTEXT")
        bad_policy = self.policy(derived_evidence_version="TECH_RISK_DERIVED_EVIDENCE_V2")
        with self.assertRaisesRegex(TechnicalRiskEvaluatorError, "derived evidence"):
            self.evaluation_input(policy=bad_policy)

    def test_same_input_policy_deterministic_and_feature_reorder_invariant(self):
        production_input = self.production_input()
        policy = self.policy()
        first = self.evaluate(production_input, policy)
        second = self.evaluate(production_input, policy)
        reordered = self.production_input(tuple(reversed(production_input.feature_values)))
        third = self.evaluate(reordered, policy)

        self.assertEqual(first.evaluation_id, second.evaluation_id)
        self.assertEqual(first.evaluation_checksum, second.evaluation_checksum)
        self.assertEqual(first.evaluation_checksum, third.evaluation_checksum)

    def test_source_lineage_reorder_invariant(self):
        production_input = self.production_input()
        reordered = self.production_input(
            production_input.feature_values,
            source_artifact_ids=tuple(reversed(production_input.source_artifact_ids)),
            source_checksums=tuple(reversed(production_input.source_checksums)),
        )

        self.assertEqual(self.evaluate(production_input).evaluation_checksum, self.evaluate(reordered).evaluation_checksum)

    def test_external_decimal_context_invariant_and_preserved(self):
        production_input = self.production_input(self.features(close="90", sma20="100", sma60="120", rsi14="35"))
        policy = self.policy()
        baseline = self.evaluate(production_input, policy)
        original_context = getcontext().copy()
        try:
            getcontext().prec = 12
            getcontext().rounding = ROUND_DOWN
            down = self.evaluate(production_input, policy)
            self.assertEqual(getcontext().prec, 12)
            self.assertEqual(getcontext().rounding, ROUND_DOWN)
            getcontext().prec = 50
            getcontext().rounding = ROUND_UP
            up = self.evaluate(production_input, policy)
            self.assertEqual(getcontext().prec, 50)
            self.assertEqual(getcontext().rounding, ROUND_UP)
        finally:
            getcontext().prec = original_context.prec
            getcontext().rounding = original_context.rounding

        for result in (down, up):
            self.assertEqual(baseline.derived_evidence, result.derived_evidence)
            self.assertEqual(baseline.predicate_states, result.predicate_states)
            self.assertEqual(baseline.severity, result.severity)
            self.assertEqual(baseline.matched_rule_id, result.matched_rule_id)
            self.assertEqual(baseline.reason_codes, result.reason_codes)
            self.assertEqual(baseline.evaluation_id, result.evaluation_id)
            self.assertEqual(baseline.evaluation_checksum, result.evaluation_checksum)

    def test_checksum_changes_for_semantic_changes(self):
        base_input = self.production_input()
        base_policy = self.policy()
        base = self.evaluate(base_input, base_policy)
        changed_feature = self.evaluate(self.production_input(self.features(close="99")), base_policy)
        changed_lineage_feature = self.feature(
            TECH_AS_OF_CLOSE_FEATURE_ID,
            "100",
            version=TECH_AS_OF_CLOSE_FEATURE_VERSION,
            source_checksum="changed_close_checksum",
        )
        changed_lineage_features = tuple(
            changed_lineage_feature if feature.feature_id == TECH_AS_OF_CLOSE_FEATURE_ID else feature
            for feature in self.features()
        )
        changed_lineage = self.evaluate(self.production_input(changed_lineage_features), base_policy)
        changed_threshold = self.evaluate(base_input, self.policy(threshold_dimensions=self.dimensions(close_vs_sma20="-0.04")))
        changed_rule = self.evaluate(base_input, self.policy(rules=(replace(base_policy.rules[0], rule_priority=11), base_policy.rules[1])))
        changed_calc_features = tuple(
            self.feature(feature.feature_id, feature.value, version=feature.feature_version, calculation_id="calc_002")
            for feature in self.features()
        )
        changed_calc = self.evaluate(
            self.production_input(changed_calc_features, calculation_id="calc_002"),
            base_policy,
        )
        tampered_policy = deepcopy(base_policy)
        object.__setattr__(tampered_policy, "policy_checksum", "different_policy_checksum")
        changed_policy_checksum = self.evaluate(base_input, tampered_policy)

        for changed in (
            changed_feature,
            changed_lineage,
            changed_threshold,
            changed_rule,
            changed_calc,
            changed_policy_checksum,
        ):
            self.assertNotEqual(base.evaluation_checksum, changed.evaluation_checksum)

    def test_reason_codes_are_production_native_and_critical_rejected(self):
        result = self.evaluate()

        self.assertTrue(all(isinstance(reason, ProductionTechnicalRiskReasonCode) for reason in result.reason_codes))
        with self.assertRaisesRegex(TechnicalRiskEvaluatorError, "CRITICAL"):
            TechnicalRiskEvaluationResult(
                evaluation_id=None,
                evaluation_checksum=None,
                evaluation_status="EVALUATED",
                evaluator_version=TECHNICAL_RISK_EVALUATOR_VERSION_V1,
                numeric_context_version=TECH_RISK_DECIMAL_CONTEXT_V1,
                policy_id=result.policy_id,
                policy_version=result.policy_version,
                policy_checksum=result.policy_checksum,
                portfolio_id=result.portfolio_id,
                position_id=result.position_id,
                symbol=result.symbol,
                as_of_date=result.as_of_date,
                valuation_date=result.valuation_date,
                calculation_id=result.calculation_id,
                source_artifact_ids=result.source_artifact_ids,
                source_checksums=result.source_checksums,
                feature_references=result.feature_references,
                derived_evidence=result.derived_evidence,
                predicate_states=result.predicate_states,
                matched_rule_id=None,
                matched_rule_priority=None,
                severity=RiskSeverity.CRITICAL,
                reason_codes=result.reason_codes,
            )

    def test_portfolio_and_position_do_not_alter_severity_but_change_identity(self):
        base_features = self.features()
        alternate_features = tuple(
            self.feature(
                feature.feature_id,
                feature.value,
                version=feature.feature_version,
                portfolio_id="portfolio_002",
                position_id="position_002",
            )
            for feature in base_features
        )
        base = self.evaluate(self.production_input(base_features))
        alternate = self.evaluate(
            self.production_input(
                alternate_features,
                portfolio_id="portfolio_002",
                position_id="position_002",
            )
        )

        self.assertEqual(base.severity, alternate.severity)
        self.assertNotEqual(base.evaluation_checksum, alternate.evaluation_checksum)

    def test_evaluator_does_not_mutate_inputs_or_policy(self):
        production_input = self.production_input()
        policy = self.policy()
        before_input = (
            production_input.feature_values,
            dict(production_input.model_metadata),
            dict(production_input.exposure_metadata),
            production_input.source_artifact_ids,
            production_input.source_checksums,
        )
        before_policy = (
            policy.policy_checksum,
            policy.rules,
            policy.threshold_dimensions,
            policy.required_feature_ids,
        )

        self.evaluate(production_input, policy)

        self.assertEqual(
            before_input,
            (
                production_input.feature_values,
                dict(production_input.model_metadata),
                dict(production_input.exposure_metadata),
                production_input.source_artifact_ids,
                production_input.source_checksums,
            ),
        )
        self.assertEqual(
            before_policy,
            (
                policy.policy_checksum,
                policy.rules,
                policy.threshold_dimensions,
                policy.required_feature_ids,
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            self.evaluate().severity = RiskSeverity.LOW

    def test_public_api_and_result_contract_validation(self):
        import risk_evaluation

        for name in (
            "TechnicalRiskEvaluationInput",
            "TechnicalRiskDerivedEvidence",
            "TechnicalRiskPredicateState",
            "TechnicalRiskEvaluationResult",
            "TechnicalRiskEvaluator",
            "TechnicalRiskEvaluatorError",
        ):
            self.assertIn(name, risk_evaluation.__all__)
        state = self.evaluate().predicate_states[0]
        with self.assertRaises(FrozenInstanceError):
            state.is_triggered = False
        with self.assertRaisesRegex(TechnicalRiskEvaluatorError, "evaluation_id"):
            TechnicalRiskEvaluationResult(**{**self.evaluate().__dict__, "evaluation_id": "wrong"})

    def test_no_research_data_signal_or_fetch_boundary(self):
        import risk_evaluation.technical_evaluator as technical_evaluator

        source = inspect.getsource(technical_evaluator)
        forbidden = (
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
            "RiskSignal(",
            "ProducedRiskSignal(",
            "TechnicalRiskSignalProducer",
            "MAE",
            "Holdout",
            "latest",
            "default_policy",
        )
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
