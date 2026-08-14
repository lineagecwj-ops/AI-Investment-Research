from dataclasses import dataclass
from datetime import datetime

from risk import RiskCategory
from risk import RiskSeverity
from risk import RiskSignal
from risk_evaluation.evaluation_input import RiskSignalProductionInput
from risk_evaluation.policy import RiskEvaluationPolicy
from risk_evaluation.signal_producer import ProducedRiskSignal
from risk_evaluation.signal_producer import RiskSignalProducer
from risk_evaluation.signal_producer import validate_producer_created_at
from risk_evaluation.technical_evaluator import TECHNICAL_RISK_EVALUATOR_VERSION_V1
from risk_evaluation.technical_evaluator import TechnicalRiskEvaluationInput
from risk_evaluation.technical_evaluator import TechnicalRiskEvaluationResult
from risk_evaluation.technical_evaluator import TechnicalRiskEvaluator
from risk_evaluation.technical_evaluator import TechnicalRiskEvaluatorError
from risk_evaluation.technical_policy import ProductionTechnicalRiskPolicy
from risk_evaluation.technical_policy import ProductionTechnicalRiskReasonCode
from risk_evaluation.validation import RiskSignalProducerError


TECHNICAL_RISK_SIGNAL_PRODUCER_VERSION_V1 = "TECHNICAL_RISK_SIGNAL_PRODUCER_V1"
TECHNICAL_RISK_SIGNAL_RISK_ID_V1 = "TECHNICAL_DOWNSIDE_RISK_V1"


@dataclass(frozen=True)
class TechnicalRiskSignalProducer:
    """Project deterministic Technical Risk evaluations into production risk signals."""

    evaluator: TechnicalRiskEvaluator = TechnicalRiskEvaluator()

    category: RiskCategory = RiskCategory.TECHNICAL
    producer_version: str = TECHNICAL_RISK_SIGNAL_PRODUCER_VERSION_V1

    def produce(
        self,
        input: RiskSignalProductionInput,
        policy: RiskEvaluationPolicy,
        created_at: datetime,
    ) -> tuple[ProducedRiskSignal, ...]:
        validate_producer_created_at(created_at)
        technical_policy = _require_technical_policy(policy)
        try:
            evaluation_result = self.evaluator.evaluate(
                TechnicalRiskEvaluationInput(
                    production_input=input,
                    policy=technical_policy,
                    evaluator_version=TECHNICAL_RISK_EVALUATOR_VERSION_V1,
                    numeric_context_version=technical_policy.numeric_context_version,
                )
            )
        except TechnicalRiskEvaluatorError as exc:
            raise RiskSignalProducerError(str(exc)) from exc
        return (self.produce_from_evaluation(input, technical_policy, evaluation_result, created_at),)

    def produce_from_evaluation(
        self,
        input: RiskSignalProductionInput,
        policy: ProductionTechnicalRiskPolicy,
        evaluation_result: TechnicalRiskEvaluationResult,
        created_at: datetime,
    ) -> ProducedRiskSignal:
        validate_producer_created_at(created_at)
        technical_policy = _require_technical_policy(policy)
        _require_evaluation_result(evaluation_result)
        _validate_input_policy_evaluation(input, technical_policy, evaluation_result)
        severity = RiskSeverity(evaluation_result.severity)
        if severity == RiskSeverity.CRITICAL:
            raise RiskSignalProducerError("Technical Risk v1 signal producer cannot emit CRITICAL severity.")
        signal = RiskSignal(
            risk_id=TECHNICAL_RISK_SIGNAL_RISK_ID_V1,
            symbol=evaluation_result.symbol,
            category=self.category,
            severity=severity,
            trigger_reason=_trigger_reason(evaluation_result),
            created_at=created_at,
        )
        if signal.category != RiskCategory.TECHNICAL:
            raise RiskSignalProducerError("Technical Risk signal category must be TECHNICAL.")
        return ProducedRiskSignal(
            signal=signal,
            policy_id=technical_policy.policy_id,
            policy_version=technical_policy.policy_version,
            producer_version=self.producer_version,
            source_feature_ids=tuple(reference.feature_id for reference in evaluation_result.feature_references),
            source_checksums=evaluation_result.source_checksums,
            calculation_id=evaluation_result.calculation_id,
            policy_checksum=technical_policy.policy_checksum,
            evaluation_id=evaluation_result.evaluation_id,
            evaluation_checksum=evaluation_result.evaluation_checksum,
            portfolio_id=evaluation_result.portfolio_id,
            position_id=evaluation_result.position_id,
            as_of_date=evaluation_result.as_of_date,
            valuation_date=evaluation_result.valuation_date,
        )


def _require_technical_policy(policy: object) -> ProductionTechnicalRiskPolicy:
    if not isinstance(policy, ProductionTechnicalRiskPolicy):
        raise RiskSignalProducerError("TechnicalRiskSignalProducer requires ProductionTechnicalRiskPolicy.")
    return policy


def _require_evaluation_result(evaluation_result: object) -> TechnicalRiskEvaluationResult:
    if not isinstance(evaluation_result, TechnicalRiskEvaluationResult):
        raise RiskSignalProducerError("produce_from_evaluation requires TechnicalRiskEvaluationResult.")
    return evaluation_result


def _validate_input_policy_evaluation(
    input: RiskSignalProductionInput,
    policy: ProductionTechnicalRiskPolicy,
    evaluation_result: TechnicalRiskEvaluationResult,
) -> None:
    if not isinstance(input, RiskSignalProductionInput):
        raise RiskSignalProducerError("TechnicalRiskSignalProducer requires RiskSignalProductionInput.")
    expected_fields = (
        "portfolio_id",
        "position_id",
        "symbol",
        "as_of_date",
        "valuation_date",
        "calculation_id",
    )
    for field_name in expected_fields:
        if getattr(input, field_name) != getattr(evaluation_result, field_name):
            raise RiskSignalProducerError(f"Technical Risk evaluation {field_name} mismatch.")
    if policy.policy_id != evaluation_result.policy_id:
        raise RiskSignalProducerError("Technical Risk evaluation policy_id mismatch.")
    if policy.policy_version != evaluation_result.policy_version:
        raise RiskSignalProducerError("Technical Risk evaluation policy_version mismatch.")
    if policy.policy_checksum != evaluation_result.policy_checksum:
        raise RiskSignalProducerError("Technical Risk evaluation policy_checksum mismatch.")
    if input.source_artifact_ids != evaluation_result.source_artifact_ids:
        raise RiskSignalProducerError("Technical Risk evaluation source_artifact_ids mismatch.")
    if input.source_checksums != evaluation_result.source_checksums:
        raise RiskSignalProducerError("Technical Risk evaluation source_checksums mismatch.")
    input_feature_ids = tuple(
        feature.feature_id
        for feature in input.feature_values
        if feature.feature_id in policy.required_feature_ids
    )
    evaluation_feature_ids = tuple(reference.feature_id for reference in evaluation_result.feature_references)
    if input_feature_ids != evaluation_feature_ids:
        raise RiskSignalProducerError("Technical Risk evaluation source feature lineage mismatch.")
    input_features = {
        feature.feature_id: feature
        for feature in input.feature_values
        if feature.feature_id in policy.required_feature_ids
    }
    for reference in evaluation_result.feature_references:
        feature = input_features[reference.feature_id]
        if feature.feature_version != reference.feature_version:
            raise RiskSignalProducerError("Technical Risk evaluation source feature lineage mismatch.")
        if feature.source_artifact_id != reference.source_artifact_id:
            raise RiskSignalProducerError("Technical Risk evaluation source feature lineage mismatch.")
        if feature.source_checksum != reference.source_checksum:
            raise RiskSignalProducerError("Technical Risk evaluation source feature lineage mismatch.")
        if feature.calculation_id != reference.calculation_id:
            raise RiskSignalProducerError("Technical Risk evaluation source feature lineage mismatch.")


def _trigger_reason(evaluation_result: TechnicalRiskEvaluationResult) -> str:
    reasons = tuple(ProductionTechnicalRiskReasonCode(reason).value for reason in evaluation_result.reason_codes)
    if not reasons:
        raise RiskSignalProducerError("Technical Risk evaluation requires reason codes.")
    return "technical downside risk evidence: " + ", ".join(reasons)
