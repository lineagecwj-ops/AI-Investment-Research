from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
import math

from historical_condition_outcome_service import ConditionOutcomeObservation
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonResult
from models import HistoricalOutcomeResult
from models import SignalDefinition
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL


VOLUME_CONDITION_ID = "volume_ratio_20"
PRODUCTION_V1_VOLUME_THRESHOLD = 1.20
EXPERIMENTAL_V1_1_VOLUME_THRESHOLD = 1.10


class V11ShadowComparisonError(Exception):
    """Raised when V1/V1.1 shadow comparison inputs are invalid."""


@dataclass(frozen=True)
class V11ShadowComparisonObservation:

    symbol: str

    trading_date: object

    v1_qualified: bool

    v1_1_qualified: bool

    v1_outcome: HistoricalOutcomeResult | None

    v1_1_outcome: HistoricalOutcomeResult | None

    signal_definition_ids: tuple[str, str]

    source_observation: ConditionOutcomeObservation

    @property
    def is_shared_observation(self) -> bool:
        return self.v1_qualified and self.v1_1_qualified

    @property
    def is_v1_1_only_observation(self) -> bool:
        return self.v1_1_qualified and not self.v1_qualified


@dataclass(frozen=True)
class V11ShadowComparisonSummary:

    v1_observation_count: int

    v1_1_observation_count: int

    added_observation_count: int

    shared_observation_count: int


@dataclass(frozen=True)
class V11ShadowComparisonResult:

    production_signal_definition: SignalDefinition

    experimental_signal_definition: SignalDefinition

    observations: tuple[V11ShadowComparisonObservation, ...]

    summary: V11ShadowComparisonSummary

    generated_at: datetime


def compare_v1_v1_1_shadow_definitions(
    comparison_result: HistoricalConditionOutcomeComparisonResult,
    *,
    production_signal_definition: SignalDefinition = TECHNICAL_EXAMPLE_SIGNAL_V1,
    experimental_signal_definition: SignalDefinition = TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL,
    generated_at: datetime | None = None,
) -> V11ShadowComparisonResult:
    _validate_signal_definitions(production_signal_definition, experimental_signal_definition)
    observations = tuple(
        _shadow_observation(
            observation,
            production_signal_definition=production_signal_definition,
            experimental_signal_definition=experimental_signal_definition,
        )
        for observation in comparison_result.outcome_observations
    )
    _validate_v1_subset_v1_1(observations)
    _validate_shared_outcome_identity(observations)
    _validate_v1_1_only_interval(observations)
    return V11ShadowComparisonResult(
        production_signal_definition=production_signal_definition,
        experimental_signal_definition=experimental_signal_definition,
        observations=observations,
        summary=_summary(observations),
        generated_at=generated_at or datetime.now(UTC),
    )


def _shadow_observation(
    observation: ConditionOutcomeObservation,
    *,
    production_signal_definition: SignalDefinition,
    experimental_signal_definition: SignalDefinition,
) -> V11ShadowComparisonObservation:
    v1_qualified = _qualified_at_threshold(observation, PRODUCTION_V1_VOLUME_THRESHOLD)
    v1_1_qualified = _qualified_at_threshold(observation, EXPERIMENTAL_V1_1_VOLUME_THRESHOLD)
    return V11ShadowComparisonObservation(
        symbol=observation.symbol,
        trading_date=observation.trading_date,
        v1_qualified=v1_qualified,
        v1_1_qualified=v1_1_qualified,
        v1_outcome=observation.outcome if v1_qualified else None,
        v1_1_outcome=observation.outcome if v1_1_qualified else None,
        signal_definition_ids=(
            production_signal_definition.id,
            experimental_signal_definition.id,
        ),
        source_observation=observation,
    )


def _qualified_at_threshold(
    observation: ConditionOutcomeObservation,
    threshold: float,
) -> bool:
    return _other_v1_conditions_pass(observation) and _volume_ratio_qualifies(
        observation,
        threshold,
    )


def _other_v1_conditions_pass(observation: ConditionOutcomeObservation) -> bool:
    expected_other_conditions = observation.total_condition_count - 1
    if observation.matched_condition_count < expected_other_conditions:
        return False
    return all(
        condition_id == VOLUME_CONDITION_ID or condition_id in observation.passed_condition_ids
        for condition_id in _condition_ids_from_observation(observation)
    )


def _volume_ratio_qualifies(
    observation: ConditionOutcomeObservation,
    threshold: float,
) -> bool:
    value = getattr(observation.diagnostic_observation.source_snapshot, VOLUME_CONDITION_ID, None)
    return _is_finite_number(value) and value >= threshold


def _condition_ids_from_observation(observation: ConditionOutcomeObservation) -> tuple[str, ...]:
    return tuple(
        condition.secondary_metric and f"{condition.metric}_vs_{condition.secondary_metric}" or condition.metric
        for condition in observation.diagnostic_observation.evaluated_conditions
    )


def _validate_signal_definitions(
    production_signal_definition: SignalDefinition,
    experimental_signal_definition: SignalDefinition,
) -> None:
    if production_signal_definition.id == experimental_signal_definition.id:
        raise V11ShadowComparisonError("V1 and V1.1 must use different signal_definition_id values.")
    if production_signal_definition.name == experimental_signal_definition.name:
        raise V11ShadowComparisonError("V1 and V1.1 must use different display names.")
    if "EXPERIMENTAL" not in experimental_signal_definition.name.upper() and "EXPERIMENTAL" not in experimental_signal_definition.description.upper():
        raise V11ShadowComparisonError("V1.1 must be explicitly marked EXPERIMENTAL.")
    _validate_single_volume_threshold(
        production_signal_definition,
        expected_threshold=PRODUCTION_V1_VOLUME_THRESHOLD,
    )
    _validate_single_volume_threshold(
        experimental_signal_definition,
        expected_threshold=EXPERIMENTAL_V1_1_VOLUME_THRESHOLD,
    )
    production_without_volume = _conditions_except_volume(production_signal_definition)
    experimental_without_volume = _conditions_except_volume(experimental_signal_definition)
    if production_without_volume != experimental_without_volume:
        raise V11ShadowComparisonError("V1 and V1.1 must keep the other four conditions identical.")
    if production_signal_definition.minimum_required_features != experimental_signal_definition.minimum_required_features:
        raise V11ShadowComparisonError("V1 and V1.1 must keep required features identical.")


def _validate_single_volume_threshold(
    signal_definition: SignalDefinition,
    *,
    expected_threshold: float,
) -> None:
    volume_conditions = [
        condition for condition in signal_definition.conditions
        if condition.metric == VOLUME_CONDITION_ID and condition.secondary_metric is None
    ]
    if len(volume_conditions) != 1:
        raise V11ShadowComparisonError("Signal definition must contain one volume_ratio_20 condition.")
    condition = volume_conditions[0]
    if getattr(condition.operator, "value", None) != ">=" or condition.value != expected_threshold:
        raise V11ShadowComparisonError(
            f"{signal_definition.id} volume threshold must be volume_ratio_20 >= {expected_threshold:.2f}."
        )


def _conditions_except_volume(signal_definition: SignalDefinition):
    return tuple(
        condition for condition in signal_definition.conditions
        if condition.metric != VOLUME_CONDITION_ID or condition.secondary_metric is not None
    )


def _validate_v1_subset_v1_1(
    observations: tuple[V11ShadowComparisonObservation, ...],
) -> None:
    if any(observation.v1_qualified and not observation.v1_1_qualified for observation in observations):
        raise V11ShadowComparisonError("V1 qualified observations must be a subset of V1.1 qualified observations.")


def _validate_shared_outcome_identity(
    observations: tuple[V11ShadowComparisonObservation, ...],
) -> None:
    if any(
        observation.is_shared_observation
        and observation.v1_outcome is not observation.v1_1_outcome
        for observation in observations
    ):
        raise V11ShadowComparisonError("Shared V1/V1.1 observations must reuse the same attached outcome object.")


def _validate_v1_1_only_interval(
    observations: tuple[V11ShadowComparisonObservation, ...],
) -> None:
    invalid = [
        observation for observation in observations
        if observation.is_v1_1_only_observation
        and not _in_v1_1_only_volume_interval(observation.source_observation)
    ]
    if invalid:
        raise V11ShadowComparisonError("V1.1-only observations must have 1.10 <= volume_ratio_20 < 1.20.")


def _in_v1_1_only_volume_interval(observation: ConditionOutcomeObservation) -> bool:
    value = getattr(observation.diagnostic_observation.source_snapshot, VOLUME_CONDITION_ID, None)
    return (
        _is_finite_number(value)
        and EXPERIMENTAL_V1_1_VOLUME_THRESHOLD <= value < PRODUCTION_V1_VOLUME_THRESHOLD
    )


def _summary(
    observations: tuple[V11ShadowComparisonObservation, ...],
) -> V11ShadowComparisonSummary:
    v1_count = sum(observation.v1_qualified for observation in observations)
    v1_1_count = sum(observation.v1_1_qualified for observation in observations)
    added_count = sum(observation.is_v1_1_only_observation for observation in observations)
    shared_count = sum(observation.is_shared_observation for observation in observations)
    return V11ShadowComparisonSummary(
        v1_observation_count=v1_count,
        v1_1_observation_count=v1_1_count,
        added_observation_count=added_count,
        shared_observation_count=shared_count,
    )


def _is_finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
