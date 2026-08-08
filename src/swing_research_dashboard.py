from datetime import date
import hashlib
import re

from historical_case_service import HistoricalCaseDataError
from historical_case_service import HistoricalCaseWindowConfig
from historical_case_service import HistoricalCaseView
from historical_case_service import build_historical_case_views
from models import HistoricalPriceSeries
from models import OutcomeEvaluationStatus
from models import SignalEvaluationStatus
from models import SignalMatch
from models import TechnicalIndicatorSnapshot
from symbol_utils import normalize_stock_symbol
from swing_scanner_service import SampleSizeStatus
from swing_scanner_service import SwingOpportunityCandidate
from swing_scanner_service import SwingScannerConfig
from swing_scanner_service import SwingScannerResult


CASE_PREVIEW_FILTER_OPTIONS = ("Resolved", "HIT", "MISS")
CASE_PREVIEW_LIMIT = 5
RESEARCH_RANKING_EXPLANATION = (
    "Sample-size tier -> Historical Hit Rate -> Resolved n -> Median MAE -> "
    "Median MFE -> Median End Return -> Symbol"
)
HISTORICAL_HIT_RATE_CAPTION = "歷史命中率是歷史條件事件比例，不代表未來發生機率。"
CASE_SELECTION_BIAS_CAPTION = "請同時查看 HIT 與 MISS；只檢視命中案例可能造成選擇偏誤。"


def parse_swing_symbol_input(user_input: str) -> tuple[str, ...]:
    symbols = []
    seen_symbols = set()
    for raw_symbol in re.split(r"[\s,;，；]+", user_input):
        symbol = normalize_stock_symbol(raw_symbol)
        if not symbol or symbol in seen_symbols:
            continue
        symbols.append(symbol)
        seen_symbols.add(symbol)
    return tuple(symbols)


def build_swing_research_fingerprint(
    *,
    normalized_symbols: tuple[str, ...],
    signal_id: str,
    outcome_id: str,
    overlap_policy: str,
    cooldown_bars: int | None,
    start_date: date | None,
    end_date: date | None,
    preferred_sample_minimum: int,
) -> str:
    identity = "|".join(
        (
            ",".join(normalized_symbols),
            signal_id,
            outcome_id,
            overlap_policy,
            "" if cooldown_bars is None else str(cooldown_bars),
            "" if start_date is None else start_date.isoformat(),
            "" if end_date is None else end_date.isoformat(),
            str(preferred_sample_minimum),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"swing_research_{digest}"


def fingerprint_from_config(
    normalized_symbols: tuple[str, ...],
    config: SwingScannerConfig,
) -> str:
    return build_swing_research_fingerprint(
        normalized_symbols=normalized_symbols,
        signal_id=config.signal_definition.id,
        outcome_id=config.outcome_definition.id,
        overlap_policy=config.overlap_policy.value,
        cooldown_bars=config.cooldown_bars,
        start_date=config.backtest_start_date,
        end_date=config.backtest_end_date,
        preferred_sample_minimum=config.minimum_resolved_samples,
    )


def build_scan_summary_rows(result: SwingScannerResult) -> list[dict[str, object]]:
    return [
        {"Metric": "Scanned", "Value": result.scanned_count},
        {"Metric": "MATCH", "Value": result.matched_count},
        {"Metric": "NO_MATCH", "Value": result.no_match_count},
        {"Metric": "NOT_EVALUABLE", "Value": result.not_evaluable_count},
        {"Metric": "FAILED", "Value": result.failure_count},
    ]


def build_candidate_table_rows(
    candidates: tuple[SwingOpportunityCandidate, ...],
) -> list[dict[str, object]]:
    return [
        {
            "Research Priority": candidate.research_rank,
            "Symbol": candidate.symbol,
            "Latest Trading Date": format_date(candidate.latest_trading_date),
            "Historical Hit Rate": format_percentage(candidate.historical_hit_rate),
            "Resolved n": candidate.resolved_count,
            "HIT": candidate.hit_count,
            "MISS": candidate.miss_count,
            "Median MFE": format_percentage(candidate.median_max_close_return),
            "Median MAE": format_percentage(candidate.median_max_adverse_return),
            "Median End Return": format_percentage(candidate.median_end_return),
            "Median Hit Bars": format_optional_number(candidate.median_hit_bar_index),
            "Sample Status": sample_status_label(candidate.sample_size_status),
            "Overlap Policy": candidate.overlap_policy.value,
            "Stale?": "Yes" if candidate.source_price_is_stale else "No",
        }
        for candidate in candidates
    ]


def candidate_selector_label(candidate: SwingOpportunityCandidate) -> str:
    return (
        f"{candidate.symbol} | {format_percentage(candidate.historical_hit_rate)} | "
        f"n={candidate.resolved_count}"
    )


def build_condition_trace_rows(signal_match: SignalMatch) -> list[dict[str, str]]:
    return [
        {
            "Metric": condition.metric,
            "Actual": format_raw_value(condition.actual_value),
            "Operator": condition.operator.value,
            "Expected / Secondary": condition.secondary_metric or format_raw_value(condition.expected_value),
            "Secondary Actual": format_raw_value(condition.secondary_actual_value),
            "Status": condition.status.value,
        }
        for condition in signal_match.evaluated_conditions
    ]


def current_match_trace_is_consistent(signal_match: SignalMatch) -> bool:
    if signal_match.status is not SignalEvaluationStatus.MATCH:
        return False
    return all(
        condition.status is SignalEvaluationStatus.MATCH and condition.matched is True
        for condition in signal_match.evaluated_conditions
    )


def build_technical_snapshot_rows(
    snapshot: TechnicalIndicatorSnapshot,
) -> list[dict[str, str]]:
    metrics = (
        ("SMA20", "sma_20"),
        ("SMA60", "sma_60"),
        ("SMA120", "sma_120"),
        ("SMA200", "sma_200"),
        ("RSI14", "rsi_14"),
        ("MACD", "macd"),
        ("MACD Signal", "macd_signal"),
        ("ATR14 %", "atr_14_pct"),
        ("Volume Ratio20", "volume_ratio_20"),
        ("Return20D", "return_20d"),
        ("Return60D", "return_60d"),
        ("Distance to Prior60D High", "distance_to_prior_60d_high"),
    )
    return [
        {
            "Metric": label,
            "Value": format_metric_value(attribute, getattr(snapshot, attribute)),
        }
        for label, attribute in metrics
    ]


def build_no_match_rows(result: SwingScannerResult) -> list[dict[str, str]]:
    return [
        {
            "Symbol": detail.symbol,
            "Failed Conditions": ", ".join(detail.failed_conditions) or "N/A",
        }
        for detail in result.no_match_details
    ]


def build_not_evaluable_rows(result: SwingScannerResult) -> list[dict[str, str]]:
    return [
        {
            "Symbol": detail.symbol,
            "Missing Required Features": ", ".join(detail.missing_required_features) or "N/A",
        }
        for detail in result.not_evaluable_symbols
    ]


def build_failure_rows(result: SwingScannerResult) -> list[dict[str, str]]:
    return [
        {
            "Symbol": failure.symbol,
            "Safe Error Type": failure.error_type,
            "Safe Message": failure.message,
        }
        for failure in result.failed_symbols
    ]


def build_case_preview_views(
    *,
    candidate: SwingOpportunityCandidate,
    price_series_by_symbol: dict[str, HistoricalPriceSeries],
    window_config: HistoricalCaseWindowConfig | None = None,
) -> tuple[HistoricalCaseView, ...]:
    price_series = price_series_by_symbol.get(candidate.symbol)
    if price_series is None:
        raise HistoricalCaseDataError("case preview unavailable: scan-time price series cache is missing.")
    return build_historical_case_views(
        price_series,
        candidate.historical_backtest_report,
        window_config or HistoricalCaseWindowConfig(pre_signal_bars=60, post_signal_bars=20),
    )


def filter_case_preview_views(
    case_views: tuple[HistoricalCaseView, ...],
    status_filter: str,
) -> tuple[HistoricalCaseView, ...]:
    if status_filter == "Resolved":
        return tuple(
            case for case in case_views
            if case.outcome_status in (OutcomeEvaluationStatus.HIT, OutcomeEvaluationStatus.MISS)
        )
    status = OutcomeEvaluationStatus[status_filter]
    return tuple(case for case in case_views if case.outcome_status is status)


def latest_case_preview_rows(
    case_views: tuple[HistoricalCaseView, ...],
    *,
    limit: int = CASE_PREVIEW_LIMIT,
) -> tuple[HistoricalCaseView, ...]:
    return tuple(
        sorted(case_views, key=lambda case: (case.signal_date, case.case_id), reverse=True)[:limit]
    )


def build_case_preview_count_rows(case_views: tuple[HistoricalCaseView, ...]) -> list[dict[str, object]]:
    return [
        {"Metric": "HIT Cases", "Value": count_case_status(case_views, OutcomeEvaluationStatus.HIT)},
        {"Metric": "MISS Cases", "Value": count_case_status(case_views, OutcomeEvaluationStatus.MISS)},
        {"Metric": "INCOMPLETE Cases", "Value": count_case_status(case_views, OutcomeEvaluationStatus.INCOMPLETE)},
    ]


def count_case_status(
    case_views: tuple[HistoricalCaseView, ...],
    status: OutcomeEvaluationStatus,
) -> int:
    return sum(1 for case in case_views if case.outcome_status is status)


def sample_status_label(status: SampleSizeStatus) -> str:
    labels = {
        SampleSizeStatus.NO_RESOLVED_SAMPLES: "No Resolved Samples",
        SampleSizeStatus.BELOW_PREFERRED_MINIMUM: "Below Preferred Minimum",
        SampleSizeStatus.MEETS_PREFERRED_MINIMUM: "Meets Preferred Minimum",
    }
    return labels[status]


def format_percentage(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def format_optional_number(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def format_date(value: date | None) -> str:
    if value is None:
        return "N/A"
    return value.isoformat()


def format_raw_value(value) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, tuple):
        return " - ".join(format_raw_value(item) for item in value)
    if isinstance(value, float):
        return f"{value:,.4f}"
    return str(value)


def format_metric_value(metric: str, value) -> str:
    if metric in {
        "atr_14_pct",
        "return_20d",
        "return_60d",
        "distance_to_prior_60d_high",
    }:
        return format_percentage(value)
    return format_raw_value(value)
