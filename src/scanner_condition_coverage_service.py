from dataclasses import dataclass
from enum import Enum

from models import EvaluatedSignalCondition
from models import SignalDefinition
from models import SignalEvaluationStatus
from models import SignalMatch
from signal_condition_diagnostics_service import condition_diagnostic_id
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL
from signal_outcome_service import evaluate_signal_conditions
from swing_scanner_service import SwingScannerResult


class ConditionCoverageClassification(Enum):

    FORMAL_V1_MATCH = "FORMAL_V1_MATCH"
    NEAR_MATCH = "NEAR_MATCH"
    EXPLORATORY = "EXPLORATORY"
    BELOW_DISPLAY_THRESHOLD = "BELOW_DISPLAY_THRESHOLD"


@dataclass(frozen=True)
class ScannerConditionCoverageResult:

    symbol: str

    as_of_date: object

    production_definition_id: str

    matched_condition_count: int

    total_condition_count: int

    missing_condition_count: int

    coverage_label: str

    classification: ConditionCoverageClassification

    formal_v1_qualified: bool

    matched_condition_ids: tuple[str, ...]

    missing_condition_ids: tuple[str, ...]

    missing_condition_signature: str

    condition_details: tuple[EvaluatedSignalCondition, ...]

    volume_ratio_20: float | None

    v1_1_experimental_match: bool


@dataclass(frozen=True)
class MissingConditionBreakdownRow:

    missing_condition_ids: tuple[str, ...]

    missing_condition_signature: str

    symbol_count: int

    symbols: tuple[str, ...]


@dataclass(frozen=True)
class ScannerConditionCoverageSummary:

    evaluated_symbol_count: int

    formal_v1_match_count: int

    near_match_count: int

    exploratory_count: int

    below_display_threshold_count: int

    formal_v1_match_symbols: tuple[str, ...]

    near_match_symbols: tuple[str, ...]

    exploratory_symbols: tuple[str, ...]

    below_display_threshold_symbols: tuple[str, ...]

    results: tuple[ScannerConditionCoverageResult, ...]

    near_match_missing_condition_breakdown: tuple[MissingConditionBreakdownRow, ...]

    exploratory_missing_condition_breakdown: tuple[MissingConditionBreakdownRow, ...]


class ScannerConditionCoverageError(Exception):
    """Raised when scanner condition coverage inputs violate V1 invariants."""


def build_scanner_condition_coverage_summary(
    scanner_result: SwingScannerResult,
    *,
    production_signal_definition: SignalDefinition,
) -> ScannerConditionCoverageSummary:
    results = tuple(
        sorted(
            (
                build_scanner_condition_coverage_result(
                    signal_match,
                    production_signal_definition=production_signal_definition,
                )
                for signal_match in getattr(scanner_result, "current_signal_details", tuple())
                if signal_match.status in {SignalEvaluationStatus.MATCH, SignalEvaluationStatus.NO_MATCH}
            ),
            key=lambda item: _symbol_sort_key(item.symbol),
        )
    )
    formal_symbols = _symbols_for_classification(results, ConditionCoverageClassification.FORMAL_V1_MATCH)
    near_symbols = _symbols_for_classification(results, ConditionCoverageClassification.NEAR_MATCH)
    exploratory_symbols = _symbols_for_classification(results, ConditionCoverageClassification.EXPLORATORY)
    below_symbols = _symbols_for_classification(results, ConditionCoverageClassification.BELOW_DISPLAY_THRESHOLD)
    _validate_formal_v1_identity(scanner_result, formal_symbols)
    summary = ScannerConditionCoverageSummary(
        evaluated_symbol_count=len(results),
        formal_v1_match_count=len(formal_symbols),
        near_match_count=len(near_symbols),
        exploratory_count=len(exploratory_symbols),
        below_display_threshold_count=len(below_symbols),
        formal_v1_match_symbols=formal_symbols,
        near_match_symbols=near_symbols,
        exploratory_symbols=exploratory_symbols,
        below_display_threshold_symbols=below_symbols,
        results=results,
        near_match_missing_condition_breakdown=_missing_condition_breakdown(
            results,
            classification=ConditionCoverageClassification.NEAR_MATCH,
        ),
        exploratory_missing_condition_breakdown=_missing_condition_breakdown(
            results,
            classification=ConditionCoverageClassification.EXPLORATORY,
        ),
    )
    _validate_count_invariant(summary)
    return summary


def build_scanner_condition_coverage_result(
    signal_match: SignalMatch,
    *,
    production_signal_definition: SignalDefinition,
) -> ScannerConditionCoverageResult:
    condition_ids = _condition_ids_from_definition(production_signal_definition)
    if signal_match.signal_id != production_signal_definition.id:
        raise ScannerConditionCoverageError(
            "Coverage view only supports the active production V1 signal definition."
        )
    if len(signal_match.evaluated_conditions) != len(condition_ids):
        raise ScannerConditionCoverageError(
            "Coverage condition count does not match the production V1 definition."
        )

    matched_ids = []
    missing_ids = []
    for condition in signal_match.evaluated_conditions:
        condition_id = condition_diagnostic_id(condition)
        if condition.matched is True:
            matched_ids.append(condition_id)
        else:
            missing_ids.append(condition_id)
    matched_condition_ids = tuple(matched_ids)
    missing_condition_ids = tuple(missing_ids)
    total_condition_count = len(condition_ids)
    matched_condition_count = len(matched_condition_ids)
    classification = _classification_for_count(matched_condition_count)
    formal_v1_qualified = matched_condition_count == total_condition_count
    if formal_v1_qualified != (signal_match.status is SignalEvaluationStatus.MATCH):
        raise ScannerConditionCoverageError(
            "Production V1 PASS must be equivalent to coverage 5/5."
        )
    volume_ratio_20 = _as_float(signal_match.feature_snapshot.volume_ratio_20)
    return ScannerConditionCoverageResult(
        symbol=signal_match.symbol,
        as_of_date=signal_match.trading_date,
        production_definition_id=production_signal_definition.id,
        matched_condition_count=matched_condition_count,
        total_condition_count=total_condition_count,
        missing_condition_count=len(missing_condition_ids),
        coverage_label=f"{matched_condition_count}/{total_condition_count}",
        classification=classification,
        formal_v1_qualified=formal_v1_qualified,
        matched_condition_ids=matched_condition_ids,
        missing_condition_ids=missing_condition_ids,
        missing_condition_signature=missing_condition_signature(missing_condition_ids),
        condition_details=signal_match.evaluated_conditions,
        volume_ratio_20=volume_ratio_20,
        v1_1_experimental_match=_v1_1_experimental_match(signal_match, missing_condition_ids),
    )


def missing_condition_signature(missing_condition_ids: tuple[str, ...]) -> str:
    if not missing_condition_ids:
        return "NONE"
    return "MISSING_" + "+".join(missing_condition_ids)


def _condition_ids_from_definition(signal_definition: SignalDefinition) -> tuple[str, ...]:
    return tuple(
        f"{condition.metric}_vs_{condition.secondary_metric}"
        if condition.secondary_metric is not None else condition.metric
        for condition in signal_definition.conditions
    )


def _classification_for_count(matched_condition_count: int) -> ConditionCoverageClassification:
    if matched_condition_count == 5:
        return ConditionCoverageClassification.FORMAL_V1_MATCH
    if matched_condition_count == 4:
        return ConditionCoverageClassification.NEAR_MATCH
    if matched_condition_count == 3:
        return ConditionCoverageClassification.EXPLORATORY
    return ConditionCoverageClassification.BELOW_DISPLAY_THRESHOLD


def _v1_1_experimental_match(
    signal_match: SignalMatch,
    missing_condition_ids: tuple[str, ...],
) -> bool:
    if missing_condition_ids != ("volume_ratio_20",):
        return False
    experimental_match = evaluate_signal_conditions(
        signal_match.feature_snapshot,
        TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL,
    )
    return experimental_match.status is SignalEvaluationStatus.MATCH


def _symbols_for_classification(
    results: tuple[ScannerConditionCoverageResult, ...],
    classification: ConditionCoverageClassification,
) -> tuple[str, ...]:
    return tuple(item.symbol for item in results if item.classification is classification)


def _missing_condition_breakdown(
    results: tuple[ScannerConditionCoverageResult, ...],
    *,
    classification: ConditionCoverageClassification,
) -> tuple[MissingConditionBreakdownRow, ...]:
    by_signature = {}
    for result in results:
        if result.classification is not classification:
            continue
        by_signature.setdefault(result.missing_condition_ids, []).append(result.symbol)
    return tuple(
        MissingConditionBreakdownRow(
            missing_condition_ids=missing_ids,
            missing_condition_signature=missing_condition_signature(missing_ids),
            symbol_count=len(symbols),
            symbols=tuple(sorted(symbols, key=_symbol_sort_key)),
        )
        for missing_ids, symbols in sorted(
            by_signature.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
    )


def _validate_formal_v1_identity(
    scanner_result: SwingScannerResult,
    formal_symbols: tuple[str, ...],
) -> None:
    scanner_hit_symbols = tuple(
        sorted((candidate.symbol for candidate in scanner_result.matched_candidates), key=_symbol_sort_key)
    )
    if formal_symbols != scanner_hit_symbols:
        raise ScannerConditionCoverageError(
            "Condition Coverage 5/5 identity set must equal Production Scanner V1 hits."
        )


def _validate_count_invariant(summary: ScannerConditionCoverageSummary) -> None:
    total = (
        summary.formal_v1_match_count
        + summary.near_match_count
        + summary.exploratory_count
        + summary.below_display_threshold_count
    )
    if total != summary.evaluated_symbol_count:
        raise ScannerConditionCoverageError("Coverage classification counts must sum to evaluated symbols.")


def _as_float(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _symbol_sort_key(symbol: str) -> tuple[int, int | str, str]:
    code = symbol.split(".", 1)[0]
    if code.isdigit():
        return (0, int(code), symbol)
    return (1, code, symbol)
