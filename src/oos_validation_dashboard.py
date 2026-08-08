from datetime import date
import hashlib


OOS_VALIDATION_MODE = "Out-of-Sample Validation"
PERIOD_ORDER = ("DEVELOPMENT", "VALIDATION", "HOLDOUT")
PERIOD_LABELS = {
    "DEVELOPMENT": "Development",
    "VALIDATION": "Validation",
    "HOLDOUT": "Holdout / Out-of-Sample",
}
HOLDOUT_CAPTION = "此期間未參與 research specification 的建立與調整。"
HISTORICAL_HIT_RATE_CAPTION = "Out-of-Sample Historical Hit Rate 仍是描述性的歷史事件比例，不是未來上漲機率。"
OUTCOME_CAPTION = "HIT / MISS 是 OutcomeDefinition 的事件結果，不是實際交易損益。"
CANDIDATE_SHARE_CAPTION = "Candidate Period Share 描述訊號出現頻率，不直接代表訊號品質。"
SMALL_SAMPLE_WARNING = "此期間已解析歷史樣本低於偏好門檻。"
STORED_RESULT_MISMATCH_MESSAGE = "目前結果來自上一組驗證設定。"

_VERDICT_TERMS = (
    "passed",
    "failed",
    "robust",
    "reliable",
    "unreliable",
    "production ready",
    "good",
    "bad",
)


def format_percentage(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def format_date(value: date | None) -> str:
    if value is None:
        return "N/A"
    return value.isoformat()


def format_optional_number(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def format_candidate_period_share(period_result) -> str:
    return (
        f"{period_result.periods_with_candidates} / "
        f"{period_result.requested_replay_period_count} = "
        f"{format_percentage(period_result.candidate_period_share)}"
    )


def format_historical_hit_rate_with_n(period_result) -> str:
    return f"{format_percentage(period_result.historical_hit_rate)} (n={period_result.resolved_count})"


def format_percentage_point_delta(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value * 100:.2f} percentage points"


def format_count_delta(value: int) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value}"


def period_label(period_result) -> str:
    return PERIOD_LABELS[period_result.role.value]


def ordered_period_results(result) -> tuple:
    return (
        result.development_result,
        result.validation_result,
        result.holdout_result,
    )


def build_period_summary_rows(period_result) -> list[dict[str, object]]:
    return [
        {"Metric": "Date Range", "Value": f"{format_date(period_result.start_date)} -> {format_date(period_result.end_date)}"},
        {"Metric": "Replay Periods", "Value": period_result.requested_replay_period_count},
        {"Metric": "Completed Replay Periods", "Value": period_result.completed_replay_period_count},
        {"Metric": "Periods With Candidates", "Value": period_result.periods_with_candidates},
        {"Metric": "Periods Without Candidates", "Value": period_result.periods_without_candidates},
        {"Metric": "Candidate Period Share", "Value": format_candidate_period_share(period_result)},
        {"Metric": "Unique Candidate Symbols", "Value": period_result.unique_candidate_symbols},
        {"Metric": "Candidate Occurrences", "Value": period_result.total_candidate_occurrences},
        {"Metric": "Historical Hit Rate", "Value": format_historical_hit_rate_with_n(period_result)},
        {"Metric": "Resolved n", "Value": period_result.resolved_count},
        {"Metric": "HIT", "Value": period_result.post_replay_hit_count},
        {"Metric": "MISS", "Value": period_result.post_replay_miss_count},
        {"Metric": "INCOMPLETE", "Value": period_result.post_replay_incomplete_count},
        {"Metric": "NOT_EVALUABLE", "Value": period_result.post_replay_not_evaluable_count},
    ]


def build_cross_period_comparison_rows(result) -> list[dict[str, object]]:
    development, validation, holdout = ordered_period_results(result)
    return [
        _comparison_row("Replay Periods", development.requested_replay_period_count, validation.requested_replay_period_count, holdout.requested_replay_period_count),
        _comparison_row("Periods With Candidates", development.periods_with_candidates, validation.periods_with_candidates, holdout.periods_with_candidates),
        _comparison_row("Candidate Period Share", format_candidate_period_share(development), format_candidate_period_share(validation), format_candidate_period_share(holdout), _delta_share(development, validation), _delta_share(validation, holdout)),
        _comparison_row("Unique Candidates", development.unique_candidate_symbols, validation.unique_candidate_symbols, holdout.unique_candidate_symbols, format_count_delta(validation.unique_candidate_symbols - development.unique_candidate_symbols), format_count_delta(holdout.unique_candidate_symbols - validation.unique_candidate_symbols)),
        _comparison_row("Candidate Occurrences", development.total_candidate_occurrences, validation.total_candidate_occurrences, holdout.total_candidate_occurrences, format_count_delta(validation.total_candidate_occurrences - development.total_candidate_occurrences), format_count_delta(holdout.total_candidate_occurrences - validation.total_candidate_occurrences)),
        _comparison_row("Resolved n", development.resolved_count, validation.resolved_count, holdout.resolved_count, format_count_delta(validation.resolved_count - development.resolved_count), format_count_delta(holdout.resolved_count - validation.resolved_count)),
        _comparison_row("Historical Hit Rate", format_historical_hit_rate_with_n(development), format_historical_hit_rate_with_n(validation), format_historical_hit_rate_with_n(holdout), _delta_hit_rate(development, validation), _delta_hit_rate(validation, holdout)),
        _comparison_row("HIT", development.post_replay_hit_count, validation.post_replay_hit_count, holdout.post_replay_hit_count, format_count_delta(validation.post_replay_hit_count - development.post_replay_hit_count), format_count_delta(holdout.post_replay_hit_count - validation.post_replay_hit_count)),
        _comparison_row("MISS", development.post_replay_miss_count, validation.post_replay_miss_count, holdout.post_replay_miss_count, format_count_delta(validation.post_replay_miss_count - development.post_replay_miss_count), format_count_delta(holdout.post_replay_miss_count - validation.post_replay_miss_count)),
        _comparison_row("INCOMPLETE", development.post_replay_incomplete_count, validation.post_replay_incomplete_count, holdout.post_replay_incomplete_count, format_count_delta(validation.post_replay_incomplete_count - development.post_replay_incomplete_count), format_count_delta(holdout.post_replay_incomplete_count - validation.post_replay_incomplete_count)),
        _comparison_row("NOT_EVALUABLE", development.post_replay_not_evaluable_count, validation.post_replay_not_evaluable_count, holdout.post_replay_not_evaluable_count, format_count_delta(validation.post_replay_not_evaluable_count - development.post_replay_not_evaluable_count), format_count_delta(holdout.post_replay_not_evaluable_count - validation.post_replay_not_evaluable_count)),
    ]


def build_outcome_count_rows(result) -> list[dict[str, object]]:
    rows = []
    for status_name in ("HIT", "MISS", "INCOMPLETE", "NOT_EVALUABLE"):
        row = {"Outcome": status_name}
        for period_result in ordered_period_results(result):
            row[PERIOD_LABELS[period_result.role.value]] = getattr(period_result, f"post_replay_{status_name.lower()}_count")
        rows.append(row)
    return rows


def build_period_symbol_rows(period_result) -> list[dict[str, object]]:
    return [
        {
            "Symbol": item.symbol,
            "Candidate Occurrences": item.candidate_occurrence_count,
            "Candidate Period Share": format_percentage(item.candidate_period_share),
            "First Appearance": format_date(item.first_candidate_date),
            "Last Appearance": format_date(item.last_candidate_date),
            "Longest Consecutive Periods": item.longest_consecutive_candidate_periods,
            "Post-Replay HIT": item.post_replay_hit_count,
            "Post-Replay MISS": item.post_replay_miss_count,
            "Post-Replay INCOMPLETE": item.post_replay_incomplete_count,
            "Post-Replay NOT_EVALUABLE": item.post_replay_not_evaluable_count,
            "Best Research Priority": format_optional_number(item.best_research_priority_rank),
            "Median Research Priority": format_optional_number(item.median_research_priority_rank),
            "Worst Research Priority": format_optional_number(item.worst_research_priority_rank),
        }
        for item in period_result.replay_analytics.symbol_summaries
    ]


def build_cross_period_symbol_presence_rows(result) -> list[dict[str, object]]:
    period_maps = []
    for period_result in ordered_period_results(result):
        period_maps.append({
            item.symbol: item.candidate_occurrence_count
            for item in period_result.replay_analytics.symbol_summaries
        })
    symbols = sorted(set().union(*(set(period_map) for period_map in period_maps)))
    rows = []
    for symbol in symbols:
        appearances = [
            PERIOD_LABELS[period_result.role.value]
            for period_result, period_map in zip(ordered_period_results(result), period_maps)
            if period_map.get(symbol, 0) > 0
        ]
        rows.append(
            {
                "Symbol": symbol,
                "Development Occurrences": period_maps[0].get(symbol, 0),
                "Validation Occurrences": period_maps[1].get(symbol, 0),
                "Holdout Occurrences": period_maps[2].get(symbol, 0),
                "Appeared In Periods": ", ".join(appearances) or "N/A",
            }
        )
    return rows


def build_period_timeline_rows(period_result) -> list[dict[str, object]]:
    return [
        {
            "Validation Role": PERIOD_LABELS[period_result.role.value],
            "Replay Date": format_date(item.requested_replay_date),
            "Candidate Count": item.candidate_count,
            "HIT": item.post_replay_hit_count,
            "MISS": item.post_replay_miss_count,
            "INCOMPLETE": item.post_replay_incomplete_count,
            "NOT_EVALUABLE": item.post_replay_not_evaluable_count,
            "FAILED": item.failure_count,
        }
        for item in period_result.replay_analytics.period_summaries
    ]


def build_candidate_count_chart_rows(result) -> list[dict[str, object]]:
    rows = []
    for period_result in ordered_period_results(result):
        rows.extend(build_period_timeline_rows(period_result))
    return rows


def build_candidate_share_chart_rows(result) -> list[dict[str, object]]:
    return [
        {
            "Validation Role": PERIOD_LABELS[period_result.role.value],
            "Candidate Period Share": period_result.candidate_period_share,
            "Candidate Period Share Label": format_candidate_period_share(period_result),
        }
        for period_result in ordered_period_results(result)
    ]


def build_historical_hit_rate_chart_rows(result) -> list[dict[str, object]]:
    return [
        {
            "Validation Role": PERIOD_LABELS[period_result.role.value],
            "Historical Hit Rate": period_result.historical_hit_rate,
            "Resolved n": period_result.resolved_count,
            "Label": f"{PERIOD_LABELS[period_result.role.value]} {format_historical_hit_rate_with_n(period_result)}",
        }
        for period_result in ordered_period_results(result)
    ]


def build_failure_summary_rows(result) -> list[dict[str, object]]:
    rows = []
    for period_result in ordered_period_results(result):
        for replay_period in period_result.walk_forward_result.period_results:
            if replay_period.failure is None:
                continue
            rows.append(
                {
                    "Validation Role": PERIOD_LABELS[period_result.role.value],
                    "Replay Date": format_date(replay_period.requested_replay_date),
                    "Safe Error Type": replay_period.failure.error_type,
                    "Safe Message": replay_period.failure.safe_message,
                }
            )
    return rows


def build_factual_observations(result) -> list[str]:
    development, validation, holdout = ordered_period_results(result)
    observations = [
        _share_observation("Validation", validation, "Development", development),
        _share_observation("Holdout", holdout, "Development", development),
        _hit_rate_observation("Validation", validation, "Development", development),
        _hit_rate_observation("Holdout", holdout, "Development", development),
    ]
    for period_name, period_result in (
        ("Development", development),
        ("Validation", validation),
        ("Holdout", holdout),
    ):
        if period_result.resolved_count < result.config.minimum_resolved_samples:
            observations.append(
                f"{period_name} resolved sample size is below preferred minimum "
                f"(n={period_result.resolved_count}, preferred={result.config.minimum_resolved_samples})."
            )
    return [item for item in observations if item]


def build_source_context_copy(source_context: dict[str, object] | None) -> dict[str, object] | None:
    if source_context is None:
        return None
    symbols = source_context.get("symbols_copy", source_context.get("symbols", tuple()))
    return {
        "source_type": source_context.get("source_type"),
        "source_universe_id": source_context.get("source_universe_id"),
        "source_universe_name": source_context.get("source_universe_name"),
        "symbol_count": source_context.get("symbol_count"),
        "symbols": tuple(symbols),
    }


def build_oos_validation_request_fingerprint(
    *,
    normalized_symbols: tuple[str, ...],
    source_type: str,
    development_start: date,
    development_end: date,
    validation_start: date,
    validation_end: date,
    holdout_start: date,
    holdout_end: date,
    replay_frequency: str,
    overlap_policy: str,
    cooldown_bars: int | None,
    historical_start_date: date | None,
    minimum_resolved_samples: int,
) -> str:
    parts = (
        source_type,
        ",".join(normalized_symbols),
        development_start.isoformat(),
        development_end.isoformat(),
        validation_start.isoformat(),
        validation_end.isoformat(),
        holdout_start.isoformat(),
        holdout_end.isoformat(),
        replay_frequency,
        overlap_policy,
        "" if cooldown_bars is None else str(cooldown_bars),
        "" if historical_start_date is None else historical_start_date.isoformat(),
        str(minimum_resolved_samples),
    )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"oos_validation_request_{digest}"


def stored_result_is_stale(stored_fingerprint: str | None, current_fingerprint: str) -> bool:
    return stored_fingerprint is not None and stored_fingerprint != current_fingerprint


def contains_verdict_language(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in _VERDICT_TERMS)


def _comparison_row(
    metric: str,
    development,
    validation,
    holdout,
    validation_delta="N/A",
    holdout_delta="N/A",
) -> dict[str, object]:
    return {
        "Metric": metric,
        "Development": development,
        "Validation": validation,
        "Holdout": holdout,
        "Validation - Development": validation_delta,
        "Holdout - Validation": holdout_delta,
    }


def _delta_share(left, right) -> str:
    return format_percentage_point_delta(right.candidate_period_share - left.candidate_period_share)


def _delta_hit_rate(left, right) -> str:
    if left.historical_hit_rate is None or right.historical_hit_rate is None:
        return "N/A"
    return (
        f"{format_percentage_point_delta(right.historical_hit_rate - left.historical_hit_rate)} "
        f"(n={left.resolved_count} -> n={right.resolved_count})"
    )


def _share_observation(left_name: str, left, right_name: str, right) -> str:
    if left.candidate_period_share == right.candidate_period_share:
        return ""
    direction = "higher" if left.candidate_period_share > right.candidate_period_share else "lower"
    return (
        f"{left_name} candidate period share is {direction} than {right_name} "
        f"({format_percentage(left.candidate_period_share)} vs {format_percentage(right.candidate_period_share)})."
    )


def _hit_rate_observation(left_name: str, left, right_name: str, right) -> str:
    if left.historical_hit_rate is None or right.historical_hit_rate is None:
        return ""
    if left.historical_hit_rate == right.historical_hit_rate:
        return ""
    direction = "higher" if left.historical_hit_rate > right.historical_hit_rate else "lower"
    return (
        f"{left_name} Historical Hit Rate is {direction} than {right_name} "
        f"({format_percentage(left.historical_hit_rate)} n={left.resolved_count} vs "
        f"{format_percentage(right.historical_hit_rate)} n={right.resolved_count})."
    )
