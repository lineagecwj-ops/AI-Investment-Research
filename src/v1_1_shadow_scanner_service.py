from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from models import SignalEvaluationStatus
from models import SignalMatch
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL
from signal_outcome_service import evaluate_signal_conditions
from swing_scanner_service import SwingScannerResult
from v1_1_shadow_comparison_service import EXPERIMENTAL_V1_1_VOLUME_THRESHOLD
from v1_1_shadow_comparison_service import PRODUCTION_V1_VOLUME_THRESHOLD
from v1_1_shadow_comparison_service import VOLUME_CONDITION_ID


class V1V11ShadowScannerError(Exception):
    """Raised when V1/V1.1 scanner shadow semantics are violated."""


class V1V11ShadowScannerComparisonStatus(Enum):

    SHARED_PASS = "SHARED_PASS"
    V1_1_ONLY = "V1_1_ONLY"
    NEITHER = "NEITHER"
    INVARIANT_VIOLATION = "INVARIANT_VIOLATION"


@dataclass(frozen=True)
class V1V11ShadowScannerResult:

    symbol: str

    as_of_date: object

    production_definition_id: str

    experimental_definition_id: str

    production_qualified: bool

    experimental_qualified: bool

    comparison_status: V1V11ShadowScannerComparisonStatus

    volume_ratio_20: float | None

    production_condition_result: SignalMatch

    experimental_condition_result: SignalMatch

    other_condition_statuses: MappingProxyType


@dataclass(frozen=True)
class V1V11ShadowScannerBatchSummary:

    evaluated_symbol_count: int

    production_hit_count: int

    experimental_hit_count: int

    shared_hit_count: int

    experimental_only_count: int

    neither_count: int

    invariant_violation_count: int

    results: tuple[V1V11ShadowScannerResult, ...]

    production_hit_symbols: tuple[str, ...]

    experimental_hit_symbols: tuple[str, ...]

    shared_symbols: tuple[str, ...]

    experimental_only_symbols: tuple[str, ...]

    neither_symbols: tuple[str, ...]

    invariant_violation_symbols: tuple[str, ...]


def build_v1_v1_1_shadow_scanner_summary(
    scanner_result: SwingScannerResult,
) -> V1V11ShadowScannerBatchSummary:
    results = tuple(
        build_v1_v1_1_shadow_scanner_result(signal_match)
        for signal_match in scanner_result.current_signal_details
    )
    production_hit_symbols = _symbols_where(results, lambda result: result.production_qualified)
    experimental_hit_symbols = _symbols_where(results, lambda result: result.experimental_qualified)
    shared_symbols = _symbols_with_status(results, V1V11ShadowScannerComparisonStatus.SHARED_PASS)
    experimental_only_symbols = _symbols_with_status(results, V1V11ShadowScannerComparisonStatus.V1_1_ONLY)
    neither_symbols = _symbols_with_status(results, V1V11ShadowScannerComparisonStatus.NEITHER)
    invariant_symbols = _symbols_with_status(results, V1V11ShadowScannerComparisonStatus.INVARIANT_VIOLATION)
    if invariant_symbols:
        raise V1V11ShadowScannerError(
            "V1/V1.1 scanner shadow invariant violation: "
            + ", ".join(invariant_symbols)
        )
    if not set(production_hit_symbols).issubset(experimental_hit_symbols):
        raise V1V11ShadowScannerError("Production V1 scanner hits must be a subset of V1.1 shadow hits.")
    return V1V11ShadowScannerBatchSummary(
        evaluated_symbol_count=len(results),
        production_hit_count=len(production_hit_symbols),
        experimental_hit_count=len(experimental_hit_symbols),
        shared_hit_count=len(shared_symbols),
        experimental_only_count=len(experimental_only_symbols),
        neither_count=len(neither_symbols),
        invariant_violation_count=len(invariant_symbols),
        results=results,
        production_hit_symbols=production_hit_symbols,
        experimental_hit_symbols=experimental_hit_symbols,
        shared_symbols=shared_symbols,
        experimental_only_symbols=experimental_only_symbols,
        neither_symbols=neither_symbols,
        invariant_violation_symbols=invariant_symbols,
    )


def build_v1_v1_1_shadow_scanner_result(signal_match: SignalMatch) -> V1V11ShadowScannerResult:
    snapshot = signal_match.feature_snapshot
    production = evaluate_signal_conditions(snapshot, TECHNICAL_EXAMPLE_SIGNAL_V1)
    experimental = evaluate_signal_conditions(snapshot, TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL)
    status = _comparison_status(production, experimental)
    volume = getattr(snapshot, VOLUME_CONDITION_ID, None)
    if status is V1V11ShadowScannerComparisonStatus.V1_1_ONLY:
        _validate_experimental_only_range(volume)
    return V1V11ShadowScannerResult(
        symbol=signal_match.symbol,
        as_of_date=signal_match.trading_date,
        production_definition_id=TECHNICAL_EXAMPLE_SIGNAL_V1.id,
        experimental_definition_id=TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL.id,
        production_qualified=production.status is SignalEvaluationStatus.MATCH,
        experimental_qualified=experimental.status is SignalEvaluationStatus.MATCH,
        comparison_status=status,
        volume_ratio_20=None if volume is None else float(volume),
        production_condition_result=production,
        experimental_condition_result=experimental,
        other_condition_statuses=MappingProxyType(_other_condition_statuses(experimental)),
    )


def _comparison_status(
    production: SignalMatch,
    experimental: SignalMatch,
) -> V1V11ShadowScannerComparisonStatus:
    production_qualified = production.status is SignalEvaluationStatus.MATCH
    experimental_qualified = experimental.status is SignalEvaluationStatus.MATCH
    if production_qualified and experimental_qualified:
        return V1V11ShadowScannerComparisonStatus.SHARED_PASS
    if not production_qualified and experimental_qualified:
        return V1V11ShadowScannerComparisonStatus.V1_1_ONLY
    if not production_qualified and not experimental_qualified:
        return V1V11ShadowScannerComparisonStatus.NEITHER
    return V1V11ShadowScannerComparisonStatus.INVARIANT_VIOLATION


def _validate_experimental_only_range(volume) -> None:
    if volume is None:
        raise V1V11ShadowScannerError("V1.1-only scanner result must have a volume_ratio_20 value.")
    numeric_volume = float(volume)
    if not (
        EXPERIMENTAL_V1_1_VOLUME_THRESHOLD
        <= numeric_volume
        < PRODUCTION_V1_VOLUME_THRESHOLD
    ):
        raise V1V11ShadowScannerError("V1.1-only scanner result must satisfy 1.10 <= volume_ratio_20 < 1.20.")


def _other_condition_statuses(signal_match: SignalMatch) -> dict[str, str]:
    return {
        condition.metric: condition.status.value
        for condition in signal_match.evaluated_conditions
        if condition.metric != VOLUME_CONDITION_ID
    }


def _symbols_where(results, predicate) -> tuple[str, ...]:
    return tuple(result.symbol for result in results if predicate(result))


def _symbols_with_status(
    results,
    status: V1V11ShadowScannerComparisonStatus,
) -> tuple[str, ...]:
    return tuple(result.symbol for result in results if result.comparison_status is status)
