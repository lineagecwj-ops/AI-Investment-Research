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

from risk import RiskAssessment
from risk import RiskCategory
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
from risk_evaluation import MissingDataPolicy
from risk_evaluation import ProducedRiskSignal
from risk_evaluation import ProductionTechnicalRiskPolicy
from risk_evaluation import ProductionTechnicalRiskPredicateId
from risk_evaluation import ProductionTechnicalRiskReasonCode
from risk_evaluation import ProductionTechnicalRiskRule
from risk_evaluation import ProductionTechnicalRiskThresholdDimension
from risk_evaluation import ProductionTechnicalRiskThresholdDimensionId
from risk_evaluation import ProductionTechnicalRiskThresholdOperator
from risk_evaluation import RiskEvaluationPolicy
from risk_evaluation import RiskFeatureInput
from risk_evaluation import RiskSignalProducerError
from risk_evaluation import RiskSignalProductionInput
from risk_evaluation import TechnicalRiskProductionResult
from risk_evaluation import TechnicalRiskProductionService
from risk_evaluation import TechnicalRiskProductionServiceError
from risk_evaluation import TechnicalRiskSignalProducer


class CountingProducer:
    def __init__(self, *, produced=None, fail=False):
        self.calls = 0
        self.inputs = []
        self.produced = produced
        self.fail = fail
        self.delegate = TechnicalRiskSignalProducer()

    def produce(self, input, policy, created_at):
        self.calls += 1
        self.inputs.append((input, policy, created_at))
        if self.fail:
            raise RiskSignalProducerError("synthetic producer failure")
        if self.produced is not None:
            return self.produced
        return self.delegate.produce(input, policy, created_at)


class TechnicalRiskProductionServiceTestCase(unittest.TestCase):

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
            source_artifact_id=source_artifact_id or f"artifact_{feature_id}_{position_id}",
            source_checksum=source_checksum or f"checksum_{feature_id}_{position_id}",
            calculation_id=calculation_id,
        )

    def features(
        self,
        close="100",
        sma20="105",
        sma60="120",
        rsi14="35",
        *,
        position_id="position_001",
    ):
        return (
            self.feature(TECH_RSI14_FEATURE_ID, rsi14, version=TECH_RSI14_FEATURE_VERSION, position_id=position_id),
            self.feature(TECH_SMA60_FEATURE_ID, sma60, version=TECH_SMA60_FEATURE_VERSION, position_id=position_id),
            self.feature(TECH_AS_OF_CLOSE_FEATURE_ID, close, version=TECH_AS_OF_CLOSE_FEATURE_VERSION, position_id=position_id),
            self.feature(TECH_SMA20_FEATURE_ID, sma20, version=TECH_SMA20_FEATURE_VERSION, position_id=position_id),
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
            "exposure_metadata": {"shares": Decimal("10"), "quantity": Decimal("10")},
            "source_artifact_ids": tuple(feature.source_artifact_id for feature in active_features),
            "source_checksums": tuple(feature.source_checksum for feature in active_features),
            "calculation_id": "technical_eval_calc_001",
        }
        values.update(overrides)
        return RiskSignalProductionInput(**values)

    def service(self, producer=None):
        return TechnicalRiskProductionService(producer=producer or CountingProducer())

    def execute(self, production_input=None, policy=None, created_at=None, producer=None):
        return self.service(producer).run(
            production_input or self.production_input(),
            policy or self.policy(),
            created_at or self.created_at(),
        )

    def test_valid_low_medium_high_end_to_end_and_assessment_view(self):
        low = self.execute(self.production_input(self.features(close="130", sma20="105", sma60="100", rsi14="55")))
        medium = self.execute(self.production_input(self.features(close="100", sma20="110", sma60="100", rsi14="55")))
        high = self.execute()

        self.assertEqual(low.produced_signal.signal.severity, RiskSeverity.LOW)
        self.assertEqual(medium.produced_signal.signal.severity, RiskSeverity.MEDIUM)
        self.assertEqual(high.produced_signal.signal.severity, RiskSeverity.HIGH)
        for result in (low, medium, high):
            self.assertIsInstance(result.risk_assessment, RiskAssessment)
            self.assertEqual(result.risk_assessment.signals, (result.produced_signal.signal,))
            self.assertEqual(result.risk_assessment.overall_risk_level, result.produced_signal.signal.severity)

    def test_low_is_retained_in_production_result_and_assessment(self):
        result = self.execute(self.production_input(self.features(close="130", sma20="105", sma60="100", rsi14="55")))

        self.assertEqual(result.produced_signal.signal.severity, RiskSeverity.LOW)
        self.assertEqual(result.risk_assessment.signals, (result.produced_signal.signal,))
        self.assertEqual(result.risk_assessment.overall_risk_level, RiskSeverity.LOW)

    def test_producer_called_exactly_once_and_service_does_not_depend_on_evaluator(self):
        producer = CountingProducer()

        result = self.execute(producer=producer)

        self.assertEqual(producer.calls, 1)
        self.assertEqual(len(producer.inputs), 1)
        self.assertIsInstance(result.produced_signal, ProducedRiskSignal)
        service_source = (SRC_PATH / "risk_evaluation" / "technical_production_service.py").read_text()
        self.assertNotIn("TechnicalRiskEvaluator", service_source)

    def test_producer_failure_and_invalid_counts_fail_closed(self):
        with self.assertRaisesRegex(TechnicalRiskProductionServiceError, "synthetic producer failure"):
            self.execute(producer=CountingProducer(fail=True))
        with self.assertRaisesRegex(TechnicalRiskProductionServiceError, "exactly one"):
            self.execute(producer=CountingProducer(produced=()))
        produced = self.execute().produced_signal
        with self.assertRaisesRegex(TechnicalRiskProductionServiceError, "exactly one"):
            self.execute(producer=CountingProducer(produced=(produced, produced)))

    def test_policy_boundary_requires_explicit_production_policy(self):
        producer = CountingProducer()

        with self.assertRaisesRegex(TechnicalRiskProductionServiceError, "ProductionTechnicalRiskPolicy"):
            self.service(producer).run(self.production_input(), self.generic_policy(), self.created_at())

        self.assertEqual(producer.calls, 0)
        source = (SRC_PATH / "risk_evaluation" / "technical_production_service.py").read_text()
        for forbidden in ("latest", "default", "current", "activation", "registry"):
            self.assertNotIn(forbidden, source)

    def test_created_at_preserved_and_deterministic_replay(self):
        production_input = self.production_input()
        policy = self.policy()
        created_at = self.created_at()

        first = self.execute(production_input, policy, created_at)
        second = self.execute(production_input, policy, created_at)
        changed_time = self.execute(production_input, policy, self.created_at(day=15))

        self.assertEqual(first, second)
        self.assertEqual(first.risk_assessment, second.risk_assessment)
        self.assertEqual(first.produced_signal.signal.created_at, created_at)
        self.assertNotEqual(first.produced_signal.signal.created_at, changed_time.produced_signal.signal.created_at)
        self.assertEqual(first.produced_signal.evaluation_checksum, changed_time.produced_signal.evaluation_checksum)

    def test_produced_signal_lineage_is_retained_exactly(self):
        result = self.execute()
        produced = result.produced_signal
        policy = self.policy()
        production_input = self.production_input()

        self.assertEqual(produced.policy_id, policy.policy_id)
        self.assertEqual(produced.policy_version, policy.policy_version)
        self.assertEqual(produced.policy_checksum, policy.policy_checksum)
        self.assertTrue(produced.evaluation_id)
        self.assertTrue(produced.evaluation_checksum)
        self.assertEqual(produced.portfolio_id, production_input.portfolio_id)
        self.assertEqual(produced.position_id, production_input.position_id)
        self.assertEqual(produced.as_of_date, production_input.as_of_date)
        self.assertEqual(produced.valuation_date, production_input.valuation_date)
        self.assertEqual(produced.source_checksums, production_input.source_checksums)
        self.assertEqual(produced.calculation_id, production_input.calculation_id)

    def test_same_symbol_different_position_keeps_severity_and_distinct_lineage(self):
        base = self.execute()
        alternate_features = self.features(position_id="position_002")
        alternate_input = self.production_input(
            alternate_features,
            position_id="position_002",
            source_artifact_ids=tuple(feature.source_artifact_id for feature in alternate_features),
            source_checksums=tuple(feature.source_checksum for feature in alternate_features),
        )
        alternate = self.execute(alternate_input)

        self.assertEqual(base.produced_signal.signal.severity, alternate.produced_signal.signal.severity)
        self.assertNotEqual(base.produced_signal.position_id, alternate.produced_signal.position_id)
        self.assertNotEqual(base.produced_signal.evaluation_checksum, alternate.produced_signal.evaluation_checksum)

    def test_service_defensive_validation_for_invalid_produced_signal(self):
        valid = self.execute().produced_signal
        invalid_signal = RiskSignal(
            risk_id=valid.signal.risk_id,
            symbol=valid.signal.symbol,
            category=RiskCategory.FUNDAMENTAL,
            severity=RiskSeverity.LOW,
            trigger_reason="synthetic invalid category",
            created_at=valid.signal.created_at,
        )
        invalid_category = replace(valid, signal=invalid_signal)
        critical_signal = replace(
            valid,
            signal=RiskSignal(
                risk_id=valid.signal.risk_id,
                symbol=valid.signal.symbol,
                category=RiskCategory.TECHNICAL,
                severity=RiskSeverity.CRITICAL,
                trigger_reason="synthetic invalid critical",
                created_at=valid.signal.created_at,
            ),
        )
        invalid_lineage = replace(valid, position_id="position_002")

        with self.assertRaisesRegex(TechnicalRiskProductionServiceError, "TECHNICAL"):
            self.execute(producer=CountingProducer(produced=(invalid_category,)))
        with self.assertRaisesRegex(TechnicalRiskProductionServiceError, "CRITICAL"):
            self.execute(producer=CountingProducer(produced=(critical_signal,)))
        with self.assertRaisesRegex(TechnicalRiskProductionServiceError, "position_id"):
            self.execute(producer=CountingProducer(produced=(invalid_lineage,)))
        with self.assertRaisesRegex(TechnicalRiskProductionServiceError, "ProducedRiskSignal"):
            self.execute(producer=CountingProducer(produced=(object(),)))

    def test_result_immutability_and_inputs_not_mutated(self):
        production_input = self.production_input()
        policy = self.policy()
        input_snapshot = (
            production_input.feature_values,
            production_input.source_artifact_ids,
            production_input.source_checksums,
            dict(production_input.exposure_metadata),
        )
        policy_snapshot = (
            policy.policy_id,
            policy.policy_checksum,
            policy.rules,
            policy.threshold_dimensions,
        )

        result = self.execute(production_input, policy)

        self.assertEqual(
            (
                production_input.feature_values,
                production_input.source_artifact_ids,
                production_input.source_checksums,
                dict(production_input.exposure_metadata),
            ),
            input_snapshot,
        )
        self.assertEqual(
            (
                policy.policy_id,
                policy.policy_checksum,
                policy.rules,
                policy.threshold_dimensions,
            ),
            policy_snapshot,
        )
        with self.assertRaises(FrozenInstanceError):
            result.produced_signal = result.produced_signal
        with self.assertRaises(FrozenInstanceError):
            result.risk_assessment = result.risk_assessment
        with self.assertRaises(FrozenInstanceError):
            self.service().producer = CountingProducer()

    def test_no_share_or_exposure_severity_adjustment(self):
        base = self.execute(self.production_input(exposure_metadata={"shares": Decimal("10"), "quantity": Decimal("10")}))
        large = self.execute(self.production_input(exposure_metadata={"shares": Decimal("100000"), "quantity": Decimal("100000")}))

        self.assertEqual(base.produced_signal.signal.severity, large.produced_signal.signal.severity)
        self.assertEqual(base.risk_assessment.overall_risk_level, large.risk_assessment.overall_risk_level)

    def test_no_risk_artifact_schema_or_boundary_dependencies(self):
        source = (SRC_PATH / "risk_evaluation" / "technical_production_service.py").read_text()
        forbidden_terms = (
            "RiskArtifact",
            "RiskContext",
            "RiskRegistry",
            "RiskDefinition",
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
            "requests",
            "urllib",
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "scheduler",
            "background",
            "email",
            "dashboard",
            "app.py",
            "BUY",
            "SELL",
            "HOLD",
            "ENTRY",
            "EXIT",
            "TARGET PRICE",
            "STOP LOSS",
            "TRADING SCORE",
            "production_result_id",
            "production_result_checksum",
        )
        for forbidden in forbidden_terms:
            self.assertNotIn(forbidden, source)

    def test_public_api_exports(self):
        from risk_evaluation import TechnicalRiskProductionResult as ExportedResult
        from risk_evaluation import TechnicalRiskProductionService as ExportedService
        from risk_evaluation import TechnicalRiskProductionServiceError as ExportedError

        self.assertIs(ExportedResult, TechnicalRiskProductionResult)
        self.assertIs(ExportedService, TechnicalRiskProductionService)
        self.assertIs(ExportedError, TechnicalRiskProductionServiceError)


if __name__ == "__main__":
    unittest.main()
