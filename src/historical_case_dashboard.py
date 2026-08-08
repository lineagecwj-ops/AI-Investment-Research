import hashlib

import altair as alt
import pandas as pd

from historical_case_service import HistoricalCaseView
from models import OutcomeEvaluationStatus


RESOLVED_STATUSES = (
    OutcomeEvaluationStatus.HIT,
    OutcomeEvaluationStatus.MISS,
)

STATUS_FILTER_OPTIONS = (
    "Resolved Cases",
    "All",
    "HIT",
    "MISS",
    "INCOMPLETE",
    "NOT_EVALUABLE",
)

SORT_OPTIONS = (
    "Newest",
    "Oldest",
)


def build_case_request_fingerprint(
    *,
    symbol: str,
    signal_id: str,
    outcome_definition_id: str,
    overlap_policy: str,
    cooldown_bars: int | None,
    start_date,
    end_date,
) -> str:
    identity = "|".join(
        (
            symbol,
            signal_id,
            outcome_definition_id,
            overlap_policy,
            "" if cooldown_bars is None else str(cooldown_bars),
            "" if start_date is None else start_date.isoformat(),
            "" if end_date is None else end_date.isoformat(),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"historical_case_request_{digest}"


def filter_case_views(
    case_views: tuple[HistoricalCaseView, ...],
    status_filter: str,
) -> tuple[HistoricalCaseView, ...]:
    if status_filter == "Resolved Cases":
        return tuple(case for case in case_views if case.outcome_status in RESOLVED_STATUSES)
    if status_filter == "All":
        return tuple(case_views)

    status = OutcomeEvaluationStatus[status_filter]
    return tuple(case for case in case_views if case.outcome_status is status)


def sort_case_views(
    case_views: tuple[HistoricalCaseView, ...],
    sort_option: str,
) -> tuple[HistoricalCaseView, ...]:
    reverse = sort_option == "Newest"
    return tuple(sorted(case_views, key=lambda case: (case.signal_date, case.case_id), reverse=reverse))


def case_selector_label(case: HistoricalCaseView) -> str:
    hit_text = ""
    if case.target_hit_bar_index is not None:
        hit_text = f" | hit bar {case.target_hit_bar_index}"
    return f"{case.signal_date.isoformat()} | {case.outcome_status.value}{hit_text}"


def build_case_summary_rows(case_views: tuple[HistoricalCaseView, ...]) -> list[dict[str, str]]:
    return [
        {
            "Signal Date": case.signal_date.isoformat(),
            "Status": case.outcome_status.value,
            "Reference High": format_price_value(case.reference_high, case.currency),
            "First Hit": format_date_value(case.target_hit_date),
            "Hit Bar": format_optional_int(case.target_hit_bar_index),
            "MFE": format_percentage_value(case.max_close_return),
            "MAE": format_percentage_value(case.max_adverse_return),
            "End Return": format_percentage_value(case.end_of_window_return),
        }
        for case in case_views
    ]


def build_condition_detail_rows(case: HistoricalCaseView) -> list[dict[str, str]]:
    return [
        {
            "Metric": detail.metric,
            "Actual": format_raw_value(detail.actual_value),
            "Operator": detail.operator,
            "Expected / Secondary Metric": detail.secondary_metric or format_raw_value(detail.expected_value),
            "Secondary Actual": format_raw_value(detail.secondary_actual_value),
            "Status": detail.evaluation_status,
            "Matched": format_bool_value(detail.matched),
        }
        for detail in case.condition_details
    ]


def build_technical_summary_rows(case: HistoricalCaseView) -> list[dict[str, str]]:
    return [
        {
            "Metric": metric,
            "Value": format_technical_metric_value(metric, value),
        }
        for metric, value in case.technical_snapshot_summary
    ]


def build_case_chart(case: HistoricalCaseView, *, x_mode: str = "Relative Bars") -> alt.Chart:
    rows = _chart_rows(case)
    data = pd.DataFrame(rows)
    x_field = "Relative Bar:Q" if x_mode == "Relative Bars" else "Trading Date:T"
    x_title = "Relative Trading Bars" if x_mode == "Relative Bars" else "Trading Date"

    base = alt.Chart(data).encode(
        x=alt.X(x_field, title=x_title),
        tooltip=[
            alt.Tooltip("Trading Date:T", title="Trading Date"),
            alt.Tooltip("Relative Bar:Q", title="Relative Bar"),
            alt.Tooltip("Analysis Close:Q", title="Analysis Close", format=",.2f"),
            alt.Tooltip("Raw High:Q", title="Raw High", format=",.2f"),
            alt.Tooltip("Raw Low:Q", title="Raw Low", format=",.2f"),
            alt.Tooltip("Volume:Q", title="Volume", format=","),
            alt.Tooltip("Is Signal:N", title="Signal?"),
            alt.Tooltip("Is First Hit:N", title="First Hit?"),
        ],
    )
    analysis_close_line = base.mark_line(point=True, color="#2563eb").encode(
        y=alt.Y("Analysis Close:Q", title=f"Price ({case.currency or 'currency'})"),
    )
    raw_high_line = base.mark_line(color="#94a3b8", opacity=0.65, strokeDash=[4, 3]).encode(
        y=alt.Y("Raw High:Q", title=f"Price ({case.currency or 'currency'})"),
    )
    signal_rule = alt.Chart(pd.DataFrame([_signal_rule_row(case, x_mode)])).mark_rule(
        color="#334155",
        strokeDash=[6, 4],
    ).encode(x=alt.X(x_field, title=x_title))
    reference_rule = alt.Chart(pd.DataFrame([_reference_rule_row(case)])).mark_rule(
        color="#dc2626",
        strokeDash=[6, 4],
    ).encode(y=alt.Y("Reference High:Q"))
    layers = [analysis_close_line, raw_high_line, reference_rule, signal_rule]

    hit_row = _hit_row(case, rows)
    if hit_row is not None:
        hit_point = alt.Chart(pd.DataFrame([hit_row])).mark_point(
            color="#16a34a",
            filled=True,
            size=90,
        ).encode(
            x=alt.X(x_field, title=x_title),
            y=alt.Y("Raw High:Q"),
            tooltip=[
                alt.Tooltip("Trading Date:T", title="First Hit"),
                alt.Tooltip("Relative Bar:Q", title="Hit Bar"),
                alt.Tooltip("Raw High:Q", title="Raw High", format=",.2f"),
            ],
        )
        layers.append(hit_point)

    return alt.layer(*layers).properties(
        title=f"{case.symbol} - {case.signal_date.isoformat()} - {case.outcome_status.value}",
    ).resolve_scale(y="shared")


def format_percentage_value(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def format_price_value(value: float | None, currency: str | None = None) -> str:
    if value is None:
        return "N/A"
    prefix = f"{currency} " if currency else ""
    return f"{prefix}{value:,.2f}"


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


def format_technical_metric_value(metric: str, value) -> str:
    if metric in {
        "atr_14_pct",
        "distance_to_prior_60d_high",
        "return_20d",
        "return_60d",
    }:
        return format_percentage_value(value)
    return format_raw_value(value)


def format_date_value(value) -> str:
    if value is None:
        return "N/A"
    return value.isoformat()


def format_optional_int(value: int | None) -> str:
    if value is None:
        return "N/A"
    return str(value)


def format_bool_value(value: bool | None) -> str:
    if value is None:
        return "N/A"
    return "Yes" if value else "No"


def _chart_rows(case: HistoricalCaseView) -> list[dict[str, object]]:
    return [
        {
            "Trading Date": point.trading_date,
            "Relative Bar": point.relative_bar_index,
            "Analysis Close": point.analysis_close,
            "Raw High": point.raw_high,
            "Raw Low": point.raw_low,
            "Volume": point.volume,
            "Is Signal": "Yes" if point.is_signal_date else "No",
            "Is First Hit": "Yes" if point.is_target_hit_date else "No",
        }
        for point in case.price_points
    ]


def _signal_rule_row(case: HistoricalCaseView, x_mode: str) -> dict[str, object]:
    if x_mode == "Relative Bars":
        return {"Relative Bar": 0, "Trading Date": case.signal_date}
    return {"Relative Bar": 0, "Trading Date": case.signal_date}


def _reference_rule_row(case: HistoricalCaseView) -> dict[str, object]:
    return {"Reference High": case.reference_high}


def _hit_row(
    case: HistoricalCaseView,
    rows: list[dict[str, object]],
) -> dict[str, object] | None:
    if case.outcome_status is not OutcomeEvaluationStatus.HIT or case.target_hit_date is None:
        return None
    for row in rows:
        if row["Trading Date"] == case.target_hit_date:
            return row
    return None
