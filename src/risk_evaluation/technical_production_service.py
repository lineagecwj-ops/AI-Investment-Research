from dataclasses import dataclass
from datetime import datetime

from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskSeverity
from risk_evaluation.evaluation_input import RiskSignalProductionInput
from risk_evaluation.signal_producer import ProducedRiskSignal
from risk_evaluation.signal_producer import RiskSignalProducer
from risk_evaluation.technical_policy import ProductionTechnicalRiskPolicy
from risk_evaluation.technical_signal_producer import TechnicalRiskSignalProducer
from risk_evaluation.validation import RiskSignalProducerError


class TechnicalRiskProductionServiceError(ValueError):
    """Raised when Technical Risk production orchestration fails closed."""


@dataclass(frozen=True)
class TechnicalRiskProductionResult:
    """Technical Risk production output retaining lineage plus assessment view."""

    produced_signal: ProducedRiskSignal
    risk_assessment: RiskAssessment

    def __post_init__(self):
        if not isinstance(self.produced_signal, ProducedRiskSignal):
            raise TechnicalRiskProductionServiceError("TechnicalRiskProductionResult requires ProducedRiskSignal.")
        if not isinstance(self.risk_assessment, RiskAssessment):
            raise TechnicalRiskProductionServiceError("TechnicalRiskProductionResult requires RiskAssessment.")
        if self.risk_assessment.signals != (self.produced_signal.signal,):
            raise TechnicalRiskProductionServiceError("RiskAssessment must contain the produced RiskSignal exactly once.")


@dataclass(frozen=True)
class TechnicalRiskProductionService:
    """Orchestrate one Technical Risk v1 production input into a retained result."""

    producer: RiskSignalProducer = TechnicalRiskSignalProducer()

    def run(
        self,
        input: RiskSignalProductionInput,
        policy: ProductionTechnicalRiskPolicy,
        created_at: datetime,
    ) -> TechnicalRiskProductionResult:
        if not isinstance(input, RiskSignalProductionInput):
            raise TechnicalRiskProductionServiceError("TechnicalRiskProductionService requires RiskSignalProductionInput.")
        if not isinstance(policy, ProductionTechnicalRiskPolicy):
            raise TechnicalRiskProductionServiceError("TechnicalRiskProductionService requires ProductionTechnicalRiskPolicy.")
        try:
            produced_signals = self.producer.produce(input, policy, created_at)
        except RiskSignalProducerError as exc:
            raise TechnicalRiskProductionServiceError(str(exc)) from exc
        if not isinstance(produced_signals, tuple):
            raise TechnicalRiskProductionServiceError("Technical Risk producer must return a tuple.")
        if len(produced_signals) != 1:
            raise TechnicalRiskProductionServiceError("Technical Risk production requires exactly one ProducedRiskSignal.")

        produced_signal = produced_signals[0]
        self._validate_produced_signal(input, policy, produced_signal)
        try:
            assessment = RiskAssessment.from_signals(
                portfolio_id=input.portfolio_id,
                symbol=input.symbol,
                signals=(produced_signal.signal,),
                assessment_date=input.as_of_date,
            )
        except Exception as exc:
            raise TechnicalRiskProductionServiceError(str(exc)) from exc
        return TechnicalRiskProductionResult(
            produced_signal=produced_signal,
            risk_assessment=assessment,
        )

    def _validate_produced_signal(
        self,
        input: RiskSignalProductionInput,
        policy: ProductionTechnicalRiskPolicy,
        produced_signal: object,
    ) -> None:
        if not isinstance(produced_signal, ProducedRiskSignal):
            raise TechnicalRiskProductionServiceError("Technical Risk producer must return ProducedRiskSignal.")
        if produced_signal.signal.category != RiskCategory.TECHNICAL:
            raise TechnicalRiskProductionServiceError("Technical Risk production requires TECHNICAL signal category.")
        if produced_signal.signal.severity == RiskSeverity.CRITICAL:
            raise TechnicalRiskProductionServiceError("Technical Risk v1 production cannot produce CRITICAL severity.")
        if produced_signal.signal.symbol != input.symbol:
            raise TechnicalRiskProductionServiceError("Technical Risk produced signal symbol mismatch.")
        expected_lineage = {
            "portfolio_id": input.portfolio_id,
            "position_id": input.position_id,
            "as_of_date": input.as_of_date,
            "valuation_date": input.valuation_date,
            "calculation_id": input.calculation_id,
        }
        for field_name, expected in expected_lineage.items():
            if getattr(produced_signal, field_name) != expected:
                raise TechnicalRiskProductionServiceError(f"Technical Risk produced signal {field_name} mismatch.")
        if produced_signal.policy_id != policy.policy_id:
            raise TechnicalRiskProductionServiceError("Technical Risk produced signal policy_id mismatch.")
        if produced_signal.policy_version != policy.policy_version:
            raise TechnicalRiskProductionServiceError("Technical Risk produced signal policy_version mismatch.")
        if produced_signal.policy_checksum != policy.policy_checksum:
            raise TechnicalRiskProductionServiceError("Technical Risk produced signal policy_checksum mismatch.")
