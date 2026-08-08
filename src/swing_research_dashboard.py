from datetime import date
import hashlib

from historical_case_service import HistoricalCaseDataError
from historical_case_service import HistoricalCaseWindowConfig
from historical_case_service import HistoricalCaseView
from historical_case_service import build_historical_case_views
from models import HistoricalPriceSeries
from models import OutcomeEvaluationStatus
from models import SignalEvaluationStatus
from models import SignalMatch
from models import TechnicalIndicatorSnapshot
from replay_analytics_service import build_replay_analytics
from swing_scanner_service import SampleSizeStatus
from swing_scanner_service import SwingOpportunityCandidate
from swing_scanner_service import SwingScannerConfig
from swing_scanner_service import SwingScannerResult
from ui_terminology import format_condition_labels
from ui_terminology import get_frequency_label
from ui_terminology import get_outcome_status_label
from ui_terminology import get_overlap_policy_label
from ui_terminology import get_sample_status_label
from ui_terminology import get_scan_status_label
from ui_terminology import get_signal_status_label
from ui_terminology import get_technical_metric_label
from universe_dashboard import MANUAL_SOURCE
from universe_dashboard import parse_universe_symbol_text


CURRENT_SCAN_MODE = "Current"
HISTORICAL_REPLAY_MODE = "Historical Replay"
WALK_FORWARD_REPLAY_MODE = "Walk-Forward Replay"
CASE_PREVIEW_FILTER_OPTIONS = ("Resolved", "HIT", "MISS")
CASE_PREVIEW_LIMIT = 5
RESEARCH_RANKING_EXPLANATION = (
    "樣本數狀態 -> 歷史命中率 -> 已解析歷史樣本數 -> 歷史中位最大不利變動 -> "
    "歷史中位最大有利變動 -> 歷史期末中位變動 -> 股票"
)
HISTORICAL_HIT_RATE_CAPTION = "歷史命中率（Historical Hit Rate）是歷史條件事件比例，不代表未來上漲機率。"
CASE_SELECTION_BIAS_CAPTION = "請同時查看 HIT 與 MISS；只檢視命中案例可能造成選擇偏誤。"


def parse_swing_symbol_input(user_input: str) -> tuple[str, ...]:
    return parse_universe_symbol_text(user_input)


def build_swing_research_fingerprint(
    *,
    normalized_symbols: tuple[str, ...],
    source_type: str = MANUAL_SOURCE,
    scan_mode: str = CURRENT_SCAN_MODE,
    replay_date: date | None = None,
    frequency: str | None = None,
    signal_id: str,
    outcome_id: str,
    overlap_policy: str,
    cooldown_bars: int | None,
    start_date: date | None,
    end_date: date | None,
    historical_start_date: date | None = None,
    preferred_sample_minimum: int,
) -> str:
    identity = "|".join(
        (
            scan_mode,
            "" if replay_date is None else replay_date.isoformat(),
            "" if frequency is None else frequency,
            source_type,
            ",".join(normalized_symbols),
            signal_id,
            outcome_id,
            overlap_policy,
            "" if cooldown_bars is None else str(cooldown_bars),
            "" if start_date is None else start_date.isoformat(),
            "" if end_date is None else end_date.isoformat(),
            "" if historical_start_date is None else historical_start_date.isoformat(),
            str(preferred_sample_minimum),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"swing_research_{digest}"


def fingerprint_from_config(
    normalized_symbols: tuple[str, ...],
    config: SwingScannerConfig,
    *,
    source_type: str = MANUAL_SOURCE,
) -> str:
    return build_swing_research_fingerprint(
        normalized_symbols=normalized_symbols,
        source_type=source_type,
        scan_mode=CURRENT_SCAN_MODE,
        signal_id=config.signal_definition.id,
        outcome_id=config.outcome_definition.id,
        overlap_policy=config.overlap_policy.value,
        cooldown_bars=config.cooldown_bars,
        start_date=config.backtest_start_date,
        end_date=config.backtest_end_date,
        preferred_sample_minimum=config.minimum_resolved_samples,
    )


def replay_fingerprint_from_config(
    normalized_symbols: tuple[str, ...],
    config,
    *,
    source_type: str = MANUAL_SOURCE,
) -> str:
    return build_swing_research_fingerprint(
        normalized_symbols=normalized_symbols,
        source_type=source_type,
        scan_mode=HISTORICAL_REPLAY_MODE,
        replay_date=config.replay_date,
        signal_id=config.signal_definition.id,
        outcome_id=config.outcome_definition.id,
        overlap_policy=config.overlap_policy.value,
        cooldown_bars=config.cooldown_bars,
        start_date=config.historical_start_date,
        end_date=None,
        preferred_sample_minimum=config.preferred_resolved_samples,
    )


def walk_forward_fingerprint_from_config(
    normalized_symbols: tuple[str, ...],
    config,
    *,
    source_type: str = MANUAL_SOURCE,
) -> str:
    return build_swing_research_fingerprint(
        normalized_symbols=normalized_symbols,
        source_type=source_type,
        scan_mode=WALK_FORWARD_REPLAY_MODE,
        frequency=config.frequency.value,
        signal_id=config.signal_definition.id,
        outcome_id=config.outcome_definition.id,
        overlap_policy=config.overlap_policy.value,
        cooldown_bars=config.cooldown_bars,
        start_date=config.start_date,
        end_date=config.end_date,
        historical_start_date=config.historical_start_date,
        preferred_sample_minimum=config.preferred_resolved_samples,
    )


def build_scan_summary_rows(result: SwingScannerResult) -> list[dict[str, object]]:
    return [
        {"Metric": get_scan_status_label("Scanned"), "Value": result.scanned_count},
        {"Metric": get_scan_status_label("MATCH"), "Value": result.matched_count},
        {"Metric": get_scan_status_label("NO_MATCH"), "Value": result.no_match_count},
        {"Metric": get_scan_status_label("NOT_EVALUABLE"), "Value": result.not_evaluable_count},
        {"Metric": get_scan_status_label("FAILED"), "Value": result.failure_count},
    ]


def build_replay_summary_rows(result) -> list[dict[str, object]]:
    return [
        {"Metric": get_scan_status_label("Scanned"), "Value": result.scanned_count},
        {"Metric": get_scan_status_label("MATCH"), "Value": result.matched_count},
        {"Metric": get_scan_status_label("NO_MATCH"), "Value": result.no_match_count},
        {"Metric": get_scan_status_label("NOT_EVALUABLE"), "Value": result.not_evaluable_count},
        {"Metric": get_scan_status_label("FAILED"), "Value": result.failure_count},
    ]


def build_walk_forward_summary_rows(result) -> list[dict[str, object]]:
    summary = build_replay_analytics(result).stability_summary
    return [
        {"Metric": "回放期數", "Value": summary.total_period_count},
        {"Metric": "有研究候選的期間", "Value": summary.periods_with_candidates},
        {"Metric": "沒有研究候選的期間", "Value": summary.periods_without_candidates},
        {"Metric": "不重複候選股票數", "Value": summary.unique_candidate_symbols},
        {"Metric": "候選出現次數", "Value": summary.total_candidate_occurrences},
        {"Metric": "候選出現期間比例", "Value": format_percentage(summary.candidate_period_share)},
    ]


def build_walk_forward_outcome_count_rows(result) -> list[dict[str, object]]:
    distribution = build_replay_analytics(result).post_replay_outcome_distribution
    return [
        {"Metric": "回放後達成研究目標", "Value": distribution.post_replay_hit_count},
        {"Metric": "回放後未達研究目標", "Value": distribution.post_replay_miss_count},
        {"Metric": "回放後觀察期間尚未完整", "Value": distribution.post_replay_incomplete_count},
        {"Metric": "回放後無法判定", "Value": distribution.post_replay_not_evaluable_count},
    ]


def build_walk_forward_timeline_rows(result) -> list[dict[str, object]]:
    return build_replay_analytics_period_rows(result)


def walk_forward_period_selector_label(period) -> str:
    return (
        f"{format_date(period.requested_replay_date)} | "
        f"符合條件 {period.matched_count}"
    )


def build_walk_forward_symbol_summary_rows(result) -> list[dict[str, object]]:
    return [
        {
            "股票": item.symbol,
            "候選出現次數": item.candidate_occurrence_count,
            "候選出現期間比例": format_percentage(item.candidate_period_share),
            "首次出現日期": format_date(item.first_candidate_date),
            "最後出現日期": format_date(item.last_candidate_date),
            "最長連續出現期數": item.longest_consecutive_candidate_periods,
            "最佳研究優先順序": format_optional_number(item.best_research_priority_rank),
            "中位研究優先順序": format_optional_number(item.median_research_priority_rank),
            "最低研究優先順序": format_optional_number(item.worst_research_priority_rank),
            "回放後達成研究目標": item.post_replay_hit_count,
            "回放後未達研究目標": item.post_replay_miss_count,
            "回放後觀察期間尚未完整": item.post_replay_incomplete_count,
            "回放後無法判定": item.post_replay_not_evaluable_count,
        }
        for item in build_replay_analytics(result).symbol_summaries
    ]


def build_replay_analytics_period_rows(result) -> list[dict[str, object]]:
    analytics = build_replay_analytics(result)
    return [
        {
            "回放日期": format_date(item.requested_replay_date),
            "候選數": item.candidate_count,
            "候選股票": ", ".join(item.candidate_symbols) or "N/A",
            get_scan_status_label("NO_MATCH"): item.no_match_count,
            get_scan_status_label("NOT_EVALUABLE"): item.not_evaluable_count,
            get_scan_status_label("FAILED"): item.failure_count,
            "回放後達成研究目標": item.post_replay_hit_count,
            "回放後未達研究目標": item.post_replay_miss_count,
            "回放後觀察期間尚未完整": item.post_replay_incomplete_count,
            "回放後無法判定": item.post_replay_not_evaluable_count,
        }
        for item in analytics.period_summaries
    ]


def build_replay_analytics_candidate_set_rows(result) -> list[dict[str, object]]:
    analytics = build_replay_analytics(result)
    return [
        {
            "前一回放日期": format_date(item.previous_requested_date),
            "目前回放日期": format_date(item.current_requested_date),
            "前一候選數": item.previous_candidate_count,
            "目前候選數": item.current_candidate_count,
            "共同候選數": item.shared_candidate_count,
            "候選名單相似度": format_percentage(item.candidate_jaccard_similarity),
            "候選名單變動率": format_percentage(item.candidate_turnover),
        }
        for item in analytics.stability_summary.candidate_set_transitions
    ]


def build_candidate_table_rows(
    candidates: tuple[SwingOpportunityCandidate, ...],
) -> list[dict[str, object]]:
    return [
        {
            "研究優先順序": candidate.research_rank,
            "股票": candidate.symbol,
            "最新交易日": format_date(candidate.latest_trading_date),
            "歷史命中率": format_percentage(candidate.historical_hit_rate),
            "已解析歷史樣本數": candidate.resolved_count,
            "HIT": candidate.hit_count,
            "MISS": candidate.miss_count,
            "歷史中位最大有利變動": format_percentage(candidate.median_max_close_return),
            "歷史中位最大不利變動": format_percentage(candidate.median_max_adverse_return),
            "歷史期末中位變動": format_percentage(candidate.median_end_return),
            "中位達標交易日數": format_optional_number(candidate.median_hit_bar_index),
            "樣本狀態": sample_status_label(candidate.sample_size_status),
            "歷史訊號樣本處理方式": get_overlap_policy_label(candidate.overlap_policy.value),
            "資料是否過期": "是" if candidate.source_price_is_stale else "否",
        }
        for candidate in candidates
    ]


def build_replay_candidate_table_rows(candidates) -> list[dict[str, object]]:
    rows = []
    for candidate in candidates:
        summary = candidate.point_in_time_backtest_summary
        rows.append(
            {
                "研究優先順序": candidate.research_rank,
                "股票": candidate.symbol,
                "指定回放日期": format_date(candidate.requested_replay_date),
                "實際使用交易日": format_date(candidate.actual_signal_date),
                "回放當時可知歷史命中率": format_percentage(summary.historical_hit_rate_as_of),
                "回放當時可知已解析樣本數": summary.resolved_as_of_count,
                "HIT As Of": summary.hit_as_of_count,
                "MISS As Of": summary.miss_as_of_count,
                "回放當時可知中位最大有利變動": format_percentage(summary.median_max_close_return_as_of),
                "回放當時可知中位最大不利變動": format_percentage(summary.median_max_adverse_return_as_of),
                "回放當時可知期末中位變動": format_percentage(summary.median_end_return_as_of),
                "樣本狀態": sample_status_label(candidate.sample_size_status),
                "回放日期後的實際歷史結果": get_outcome_status_label(candidate.post_replay_outcome.status.value),
                "資料是否過期": "是" if candidate.source_price_is_stale else "否",
            }
        )
    return rows


def replay_candidate_selector_label(candidate) -> str:
    summary = candidate.point_in_time_backtest_summary
    return (
        f"{candidate.symbol} | "
        f"{format_percentage(summary.historical_hit_rate_as_of)} | "
        f"n={summary.resolved_as_of_count} | "
        f"Actual={format_date(candidate.actual_signal_date)}"
    )


def post_replay_outcome_rows(candidate) -> list[dict[str, str]]:
    outcome = candidate.post_replay_outcome
    return [
        {"Metric": "回放日期後的實際歷史結果", "Value": get_outcome_status_label(outcome.status.value)},
        {"Metric": "首次達標日期", "Value": format_date(outcome.intraday_target_hit_date or outcome.close_target_hit_date)},
        {"Metric": "第幾個交易日達標", "Value": format_optional_number(outcome.intraday_target_hit_bar_index or outcome.close_target_hit_bar_index)},
        {"Metric": "最大有利變動", "Value": format_percentage(outcome.max_close_return)},
        {"Metric": "最大不利變動", "Value": format_percentage(outcome.max_adverse_return)},
        {"Metric": "觀察期末變動", "Value": format_percentage(outcome.end_of_window_return)},
    ]


def candidate_selector_label(candidate: SwingOpportunityCandidate) -> str:
    return (
        f"{candidate.symbol} | {format_percentage(candidate.historical_hit_rate)} | "
        f"n={candidate.resolved_count}"
    )


def build_condition_trace_rows(signal_match: SignalMatch) -> list[dict[str, str]]:
    return [
        {
            "條件": get_technical_metric_label(condition.metric),
            "Actual": format_raw_value(condition.actual_value),
            "Operator": condition.operator.value,
            "Expected / Secondary": get_technical_metric_label(condition.secondary_metric) if condition.secondary_metric else format_raw_value(condition.expected_value),
            "Secondary Actual": format_raw_value(condition.secondary_actual_value),
            "Status": get_signal_status_label(condition.status.value),
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
        ("sma_20", "sma_20"),
        ("sma_60", "sma_60"),
        ("sma_120", "sma_120"),
        ("sma_200", "sma_200"),
        ("rsi_14", "rsi_14"),
        ("macd", "macd"),
        ("macd_signal", "macd_signal"),
        ("atr_14_pct", "atr_14_pct"),
        ("volume_ratio_20", "volume_ratio_20"),
        ("return_20d", "return_20d"),
        ("return_60d", "return_60d"),
        ("distance_to_prior_60d_high", "distance_to_prior_60d_high"),
    )
    return [
        {
            "指標": get_technical_metric_label(label),
            "Value": format_metric_value(attribute, getattr(snapshot, attribute)),
        }
        for label, attribute in metrics
    ]


def build_no_match_rows(result: SwingScannerResult) -> list[dict[str, str]]:
    return [
        {
            "股票": detail.symbol,
            "未符合的條件": format_condition_labels(detail.failed_conditions),
        }
        for detail in result.no_match_details
    ]


def build_not_evaluable_rows(result: SwingScannerResult) -> list[dict[str, str]]:
    return [
        {
            "股票": detail.symbol,
            "缺少必要指標": format_condition_labels(detail.missing_required_features),
        }
        for detail in result.not_evaluable_symbols
    ]


def build_failure_rows(result: SwingScannerResult) -> list[dict[str, str]]:
    return [
        {
            "股票": failure.symbol,
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
        {"Metric": "達成研究目標案例", "Value": count_case_status(case_views, OutcomeEvaluationStatus.HIT)},
        {"Metric": "未達研究目標案例", "Value": count_case_status(case_views, OutcomeEvaluationStatus.MISS)},
        {"Metric": "觀察期間尚未完整案例", "Value": count_case_status(case_views, OutcomeEvaluationStatus.INCOMPLETE)},
    ]


def count_case_status(
    case_views: tuple[HistoricalCaseView, ...],
    status: OutcomeEvaluationStatus,
) -> int:
    return sum(1 for case in case_views if case.outcome_status is status)


def sample_status_label(status: SampleSizeStatus) -> str:
    labels = {
        SampleSizeStatus.NO_RESOLVED_SAMPLES: get_sample_status_label("NO_RESOLVED_SAMPLES"),
        SampleSizeStatus.BELOW_PREFERRED_MINIMUM: get_sample_status_label("BELOW_PREFERRED_MINIMUM"),
        SampleSizeStatus.MEETS_PREFERRED_MINIMUM: get_sample_status_label("MEETS_PREFERRED_MINIMUM"),
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
