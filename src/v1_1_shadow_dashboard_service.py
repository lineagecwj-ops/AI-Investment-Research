from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from database import DEFAULT_DB_PATH
from expanded_volume_threshold_validation_service import _materialized_twse_common_stock_symbols
from expanded_volume_threshold_validation_service import _prepare_research_inputs
from expanded_volume_threshold_validation_service import load_twse_listing_date_snapshot
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonConfig
from historical_condition_outcome_service import compare_historical_condition_outcomes
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsConfig
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsService
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL
from ui_terminology import get_diagnostic_condition_label
from ui_terminology import get_outcome_status_label
from v1_1_shadow_comparison_service import EXPERIMENTAL_V1_1_VOLUME_THRESHOLD
from v1_1_shadow_comparison_service import PRODUCTION_V1_VOLUME_THRESHOLD
from v1_1_shadow_comparison_service import VOLUME_CONDITION_ID
from v1_1_shadow_comparison_service import compare_v1_v1_1_shadow_definitions
from volume_threshold_robustness_service import DEFAULT_OBSERVATION_END
from volume_threshold_robustness_service import DEFAULT_OBSERVATION_START
from volume_threshold_robustness_service import DEFAULT_OVERLAP_REDUCTION_SPACING_BARS
from volume_threshold_robustness_service import VolumeThresholdRobustnessConfig
from volume_threshold_robustness_service import analyze_volume_threshold_robustness
from volume_threshold_time_robustness_service import analyze_volume_threshold_time_robustness


OFFICIAL_LISTING_DATE_SNAPSHOT_PATH = Path("docs/research_inputs/twse_listing_dates_2026_08_09.json")
PRIMARY_STATUS_LABEL = "正式 V1 / Production"
EXPERIMENTAL_STATUS_LABEL = "V1.1 實驗版 / Experimental Shadow"
LIMITATION_ROWS = (
    "survivorship bias",
    "constituent look-back bias",
    "current constituent universe limitation",
    "daily observation overlap",
    "2025 time concentration",
    "V1.1 實驗版不是 production recommendation",
)


@dataclass(frozen=True)
class V11ShadowDashboardView:

    title: str

    subtitle: str

    production_card: dict[str, object]

    experimental_card: dict[str, object]

    delta_rows: list[dict[str, object]]

    definition_rows: list[dict[str, object]]

    evidence_rows: list[dict[str, object]]

    time_robustness_rows: list[dict[str, object]]

    incremental_rows: list[dict[str, object]]

    limitation_rows: list[dict[str, object]]

    safety_notes: list[str]


def build_official_v1_1_shadow_dashboard_view(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    listing_date_snapshot_path: Path | str = OFFICIAL_LISTING_DATE_SNAPSHOT_PATH,
) -> V11ShadowDashboardView:
    comparison_result, price_series_by_symbol, symbols = _build_official_comparison_result(
        db_path=db_path,
        listing_date_snapshot_path=listing_date_snapshot_path,
    )
    shadow_result = compare_v1_v1_1_shadow_definitions(comparison_result)
    robustness_result = analyze_volume_threshold_robustness(
        comparison_result,
        config=VolumeThresholdRobustnessConfig(
            symbols=symbols,
            start_date=DEFAULT_OBSERVATION_START,
            end_date=DEFAULT_OBSERVATION_END,
            overlap_reduction_spacing_bars=DEFAULT_OVERLAP_REDUCTION_SPACING_BARS,
        ),
        price_series_by_symbol=price_series_by_symbol,
    )
    time_robustness_result = analyze_volume_threshold_time_robustness(comparison_result)
    return build_v1_1_shadow_dashboard_view(
        shadow_result,
        robustness_result=robustness_result,
        time_robustness_result=time_robustness_result,
    )


def build_v1_1_shadow_dashboard_view(
    shadow_result,
    *,
    robustness_result=None,
    time_robustness_result=None,
) -> V11ShadowDashboardView:
    production = _definition_summary(shadow_result, is_experimental=False)
    experimental = _definition_summary(shadow_result, is_experimental=True)
    return V11ShadowDashboardView(
        title="V1 與 V1.1 實驗版比較",
        subtitle="V1 vs V1.1 Experimental Comparison",
        production_card=production,
        experimental_card=experimental,
        delta_rows=_delta_rows(production, experimental, shadow_result.summary),
        definition_rows=_definition_rows(shadow_result),
        evidence_rows=_evidence_rows(production, experimental, robustness_result, time_robustness_result),
        time_robustness_rows=_time_robustness_rows(time_robustness_result),
        incremental_rows=_incremental_rows(shadow_result),
        limitation_rows=[{"限制": item} for item in LIMITATION_ROWS],
        safety_notes=[
            "Production V1 remains default. V1.1 is experimental / shadow only.",
            "V1.1 增加樣本 / event，但目前沒有證據顯示 Historical Hit Rate 高於正式 V1。",
            "此區塊只供查看，不會切換 scanner、alerts、Replay、Walk-Forward、OOS 或任何 production default。",
        ],
    )


def _build_official_comparison_result(
    *,
    db_path: Path | str,
    listing_date_snapshot_path: Path | str,
):
    symbols = _materialized_twse_common_stock_symbols(db_path)
    snapshot = load_twse_listing_date_snapshot(
        listing_date_snapshot_path,
        required_symbols=symbols,
    )
    price_series_by_symbol, technical_series_by_symbol = _prepare_research_inputs(
        symbols,
        db_path=db_path,
        official_listing_dates_by_symbol=snapshot.listing_dates_by_symbol,
    )
    diagnostics = HistoricalConditionDiagnosticsService(
        price_loader=lambda *args, **kwargs: _unexpected_price_load(),
        technical_builder=lambda *args, **kwargs: _unexpected_technical_build(),
    ).run_diagnostics(
        symbols,
        HistoricalConditionDiagnosticsConfig(
            start_date=DEFAULT_OBSERVATION_START,
            end_date=DEFAULT_OBSERVATION_END,
            signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
        ),
        technical_series_by_symbol=technical_series_by_symbol,
    )
    comparison = compare_historical_condition_outcomes(
        diagnostics,
        price_series_by_symbol=price_series_by_symbol,
        config=HistoricalConditionOutcomeComparisonConfig(
            outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
            warmup_trading_bars=60,
            observation_unit="DAILY",
            overlap_possible=True,
        ),
    )
    return comparison, price_series_by_symbol, symbols


def _definition_summary(shadow_result, *, is_experimental: bool) -> dict[str, object]:
    definition = (
        shadow_result.experimental_signal_definition
        if is_experimental
        else shadow_result.production_signal_definition
    )
    qualified = tuple(
        observation for observation in shadow_result.observations
        if _is_qualified_for_card(observation, is_experimental=is_experimental)
    )
    hit_count = sum(_outcome_status(observation, is_experimental=is_experimental) == "HIT" for observation in qualified)
    miss_count = sum(_outcome_status(observation, is_experimental=is_experimental) == "MISS" for observation in qualified)
    incomplete_count = sum(_outcome_status(observation, is_experimental=is_experimental) == "INCOMPLETE" for observation in qualified)
    not_evaluable_count = sum(_outcome_status(observation, is_experimental=is_experimental) == "NOT_EVALUABLE" for observation in qualified)
    resolved_count = hit_count + miss_count
    hit_rate = None if resolved_count == 0 else hit_count / resolved_count
    return {
        "Definition": "Production V1" if not is_experimental else "V1.1 Experimental",
        "Definition ID": definition.id,
        "Status": PRIMARY_STATUS_LABEL if not is_experimental else EXPERIMENTAL_STATUS_LABEL,
        "Volume Threshold": _volume_threshold_display(definition),
        "Observation Count": len(qualified),
        "Resolved Count": resolved_count,
        "HIT": hit_count,
        "MISS": miss_count,
        "INCOMPLETE": incomplete_count,
        "NOT_EVALUABLE": not_evaluable_count,
        "Historical Hit Rate": hit_rate,
        "Historical Hit Rate Display": _format_percentage(hit_rate),
    }


def _outcome_status(observation, *, is_experimental: bool) -> str | None:
    outcome = observation.v1_1_outcome if is_experimental else observation.v1_outcome
    return None if outcome is None else outcome.status.value


def _is_qualified_for_card(observation, *, is_experimental: bool) -> bool:
    return observation.v1_1_qualified if is_experimental else observation.v1_qualified


def _delta_rows(production: dict[str, object], experimental: dict[str, object], summary) -> list[dict[str, object]]:
    observation_delta = int(experimental["Observation Count"]) - int(production["Observation Count"])
    baseline_count = int(production["Observation Count"])
    increase = None if baseline_count == 0 else observation_delta / baseline_count
    hhr_delta = _percentage_point_delta(
        production["Historical Hit Rate"],
        experimental["Historical Hit Rate"],
    )
    return [
        {"Metric": "共同樣本", "Value": summary.shared_observation_count, "Display": str(summary.shared_observation_count)},
        {"Metric": "V1.1 新增樣本", "Value": summary.added_observation_count, "Display": f"+{summary.added_observation_count}"},
        {"Metric": "Observation increase", "Value": increase, "Display": _format_percentage(increase)},
        {"Metric": "HHR difference", "Value": hhr_delta, "Display": _format_pp(hhr_delta)},
    ]


def _definition_rows(shadow_result) -> list[dict[str, object]]:
    rows = []
    for production, experimental in zip(
        shadow_result.production_signal_definition.conditions,
        shadow_result.experimental_signal_definition.conditions,
    ):
        condition_id = production.secondary_metric and f"{production.metric}_vs_{production.secondary_metric}" or production.metric
        rows.append(
            {
                "Condition": _plain_condition_label(condition_id),
                "Production V1": _condition_display(production),
                "V1.1 Experimental": _condition_display(experimental),
                "Status": "唯一差異" if production != experimental else "相同",
            }
        )
    return rows


def _evidence_rows(production, experimental, robustness_result, time_robustness_result) -> list[dict[str, object]]:
    rows = [
        _evidence_row("Daily", production, experimental),
    ]
    if robustness_result is not None:
        rows.append(_evidence_row_from_threshold_rows("20-bar reduced", robustness_result.overlap_reduced_summaries))
    if time_robustness_result is not None:
        rows.append(_event_evidence_row("First-event", time_robustness_result.event_summaries))
    return rows


def _evidence_row(label: str, production: dict[str, object], experimental: dict[str, object]) -> dict[str, object]:
    return {
        "Evidence": label,
        "V1 n": production["Observation Count"],
        "V1 HHR": production["Historical Hit Rate Display"],
        "V1.1 n": experimental["Observation Count"],
        "V1.1 HHR": experimental["Historical Hit Rate Display"],
        "Delta pp": _format_pp(_percentage_point_delta(production["Historical Hit Rate"], experimental["Historical Hit Rate"])),
    }


def _evidence_row_from_threshold_rows(label: str, rows) -> dict[str, object]:
    by_threshold = {row.threshold: row for row in rows}
    v1 = by_threshold[PRODUCTION_V1_VOLUME_THRESHOLD]
    v11 = by_threshold[EXPERIMENTAL_V1_1_VOLUME_THRESHOLD]
    return {
        "Evidence": label,
        "V1 n": v1.overlap_reduced_observation_count,
        "V1 HHR": _format_percentage(v1.overlap_reduced_hit_rate),
        "V1.1 n": v11.overlap_reduced_observation_count,
        "V1.1 HHR": _format_percentage(v11.overlap_reduced_hit_rate),
        "Delta pp": _format_pp(_percentage_point_delta(v1.overlap_reduced_hit_rate, v11.overlap_reduced_hit_rate)),
    }


def _event_evidence_row(label: str, rows) -> dict[str, object]:
    by_threshold = {row.threshold: row for row in rows}
    v1 = by_threshold[PRODUCTION_V1_VOLUME_THRESHOLD]
    v11 = by_threshold[EXPERIMENTAL_V1_1_VOLUME_THRESHOLD]
    return {
        "Evidence": label,
        "V1 n": v1.first_qualification_event_count,
        "V1 HHR": _format_percentage(v1.event_hit_rate),
        "V1.1 n": v11.first_qualification_event_count,
        "V1.1 HHR": _format_percentage(v11.event_hit_rate),
        "Delta pp": _format_pp(_percentage_point_delta(v1.event_hit_rate, v11.event_hit_rate)),
    }


def _time_robustness_rows(time_robustness_result) -> list[dict[str, object]]:
    if time_robustness_result is None:
        return []
    labels = {
        "PERIOD_A": "2018–2020",
        "PERIOD_B": "2021–2023",
        "PERIOD_C": "2024",
        "PERIOD_D": "2025",
    }
    by_period = {}
    for row in time_robustness_result.period_summaries:
        by_period.setdefault(row.period_name, {})[row.threshold_summary.threshold] = row.threshold_summary
    result = []
    for period in time_robustness_result.periods:
        threshold_rows = by_period[period.name]
        v1 = threshold_rows[PRODUCTION_V1_VOLUME_THRESHOLD]
        v11 = threshold_rows[EXPERIMENTAL_V1_1_VOLUME_THRESHOLD]
        result.append(
            {
                "Period": labels.get(period.name, period.name),
                "V1 HHR": _format_percentage(v1.historical_hit_rate),
                "V1.1 HHR": _format_percentage(v11.historical_hit_rate),
                "Delta pp": _format_pp(_percentage_point_delta(v1.historical_hit_rate, v11.historical_hit_rate)),
            }
        )
    return result


def _incremental_rows(shadow_result) -> list[dict[str, object]]:
    rows = []
    for observation in shadow_result.observations:
        if not observation.is_v1_1_only_observation:
            continue
        source = observation.source_observation
        volume = getattr(source.diagnostic_observation.source_snapshot, VOLUME_CONDITION_ID, None)
        rows.append(
            {
                "symbol": observation.symbol,
                "trading_date": observation.trading_date.isoformat(),
                "volume_ratio_20": None if volume is None else round(float(volume), 6),
                "outcome status": get_outcome_status_label(source.status.value),
                "signal_definition_id": shadow_result.experimental_signal_definition.id,
            }
        )
    return rows


def _condition_display(condition) -> str:
    if condition.secondary_metric:
        return f"{condition.metric} {condition.operator.value} {condition.secondary_metric}"
    if condition.operator.value == "between":
        return f"{condition.metric} between {condition.value[0]:.0f} and {condition.value[1]:.0f}"
    return f"{condition.metric} {condition.operator.value} {condition.value:.2f}"


def _plain_condition_label(condition_id: str) -> str:
    labels = {
        "analysis_close_vs_sma_20": "Price > SMA20",
        "sma_20_vs_sma_60": "SMA20 > SMA60",
        "volume_ratio_20": "Volume ratio",
        "rsi_14": "RSI",
        "distance_to_prior_60d_high": "Distance to prior high",
    }
    return labels.get(condition_id, get_diagnostic_condition_label(condition_id))


def _volume_threshold_display(definition) -> str:
    condition = next(condition for condition in definition.conditions if condition.metric == VOLUME_CONDITION_ID)
    return f"{condition.metric} {condition.operator.value} {condition.value:.2f}"


def _format_percentage(value) -> str:
    if value is None:
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def _format_pp(value) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):+.2f} pp"


def _percentage_point_delta(baseline, candidate) -> float | None:
    if baseline is None or candidate is None:
        return None
    return (float(candidate) - float(baseline)) * 100


def _unexpected_price_load():
    raise RuntimeError("V1.1 shadow dashboard must use preloaded read-only price series.")


def _unexpected_technical_build():
    raise RuntimeError("V1.1 shadow dashboard must use prebuilt technical series.")
