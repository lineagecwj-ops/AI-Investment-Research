import sys
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


SRC_PATH = Path(__file__).resolve().parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dashboard import build_comparison_rows
from dashboard import build_historical_chart_rows
from dashboard import build_historical_trend_display
from dashboard import format_currency_amount
from dashboard import format_currency_value
from dashboard import format_debt_to_equity
from dashboard import indicator_help
from dashboard import indicator_label
from dashboard import format_decimal
from dashboard import format_industry
from dashboard import format_percentage
from dashboard import format_price
from dashboard import format_ratio
from dashboard import format_sector
from dashboard import has_enough_historical_data
from dashboard import historical_metric_help
from dashboard import query_stock_batch
from dashboard import StockQueryFailure
from dashboard import stock_display_data
from backtest_service import BacktestConfig
from backtest_service import BacktestDataError
from backtest_service import HistoricalBacktestCase
from backtest_service import aggregate_backtest_cases
from backtest_service import build_case_id
from backtest_service import run_historical_backtest
from ai_config import MAX_RESEARCH_QUESTION_LENGTH
from ai_config import get_ai_research_config
from ai_dashboard import build_request_fingerprint
from ai_dashboard import evidence_lookup
from ai_dashboard import format_evidence_period
from ai_dashboard import format_evidence_value
from ai_dashboard import format_generated_at
from ai_dashboard import format_limitation_item
from ai_dashboard import format_missing_data_item
from ai_dashboard import is_openai_api_configured
from ai_dashboard import json_safe_selected_context_summary
from ai_dashboard import question_type_help
from ai_dashboard import question_type_label
from ai_dashboard import question_type_options
from ai_dashboard import question_type_placeholder
from ai_dashboard import safe_error_details
from ai_dashboard import safe_error_message
from ai_dashboard import source_type_label
from ai_followup import AIResearchSession
from ai_followup import MAX_RESEARCH_TURNS
from ai_followup import aggregate_session_usage
from ai_followup import append_verified_turn
from ai_followup import build_followup_suggestions
from ai_followup import create_research_turn
from ai_followup import infer_followup_question_type
from ai_research_service import generate_grounded_research_answer
from company_summary_service import build_company_summary_display
from historical_financial_service import get_historical_financials
from historical_financial_service import HistoricalFinancialServiceError
from historical_price_service import get_historical_prices
from historical_interpretation_presentation import ATTENTION_COLOR_EXPLANATION
from historical_interpretation_presentation import build_historical_highlights
from historical_interpretation_presentation import build_next_step_display_groups
from historical_interpretation_presentation import FY_PERIOD_CAPTION
from historical_interpretation_presentation import group_detailed_interpretation
from historical_research_service import build_historical_research_report
from historical_case_dashboard import STATUS_FILTER_OPTIONS
from historical_case_dashboard import SORT_OPTIONS
from historical_case_dashboard import build_case_chart
from historical_case_dashboard import build_case_request_fingerprint
from historical_case_dashboard import build_case_summary_rows
from historical_case_dashboard import build_condition_detail_rows
from historical_case_dashboard import build_technical_summary_rows
from historical_case_dashboard import case_selector_label
from historical_case_dashboard import filter_case_views
from historical_case_dashboard import format_date_value
from historical_case_dashboard import format_optional_int
from historical_case_dashboard import format_percentage_value
from historical_case_dashboard import format_price_value
from historical_case_dashboard import sort_case_views
from historical_case_service import HistoricalCaseDataError
from historical_case_service import HistoricalCaseWindowConfig
from historical_case_service import build_historical_case_views
from research_context import build_research_context
from research_context_selector import ResearchSelectionRequest
from research_context_selector import select_research_context
from research_glossary import get_research_glossary
from research_service import build_research_report
from symbol_utils import normalize_stock_symbol
from symbol_utils import parse_stock_symbols
from technical_indicator_service import build_technical_indicator_series
from watchlist_service import add_stock
from watchlist_service import list_watchlist
from watchlist_service import remove_stock
from watchlist_service import WatchlistDataError
from universe_service import create_universe
from universe_service import delete_universe
from universe_service import list_universes
from universe_service import update_universe
from universe_service import UniverseAlreadyExistsError
from universe_service import UniverseError
from universe_service import UniverseNotFoundError
from universe_service import UniverseValidationError
from models import OutcomeEvaluationStatus
from models import OverlappingSignalPolicy
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import build_signal_event
from historical_replay_service import HistoricalReplayConfig
from historical_replay_service import HistoricalReplayService
from out_of_sample_validation_service import OutOfSampleValidationConfig
from out_of_sample_validation_service import OutOfSampleValidationError
from out_of_sample_validation_service import OutOfSampleValidationService
from out_of_sample_validation_service import ValidationPeriod
from out_of_sample_validation_service import ValidationPeriodRole
from swing_scanner_service import SwingScannerConfig
from swing_scanner_service import SwingScannerService
from ui_terminology import format_condition_labels
from ui_terminology import get_frequency_label
from ui_terminology import get_outcome_definition_label
from ui_terminology import get_outcome_status_label
from ui_terminology import get_overlap_policy_label
from ui_terminology import get_scan_mode_label
from ui_terminology import get_signal_definition_label
from ui_terminology import get_signal_status_label
from ui_terminology import get_source_label
from ui_terminology import get_technical_metric_label
from walk_forward_replay_service import WalkForwardReplayConfig
from walk_forward_replay_service import WalkForwardReplayFrequency
from walk_forward_replay_service import WalkForwardReplayService
import oos_validation_dashboard as oos_dashboard
import swing_research_dashboard as swing_dashboard
import universe_dashboard as universe_ui


st.set_page_config(
    page_title="AI Investment Research",
    layout="wide",
)

HISTORICAL_CASE_STATUS_FILTER_LABELS = {
    "Resolved Cases": "已解析案例（HIT / MISS）",
    "All": "全部案例",
    "HIT": "達成研究目標（HIT）",
    "MISS": "未達研究目標（MISS）",
    "INCOMPLETE": "觀察期間尚未完整",
    "NOT_EVALUABLE": "資料不足",
}

HISTORICAL_CASE_SORT_LABELS = {
    "Newest": "最新在前",
    "Oldest": "最舊在前",
}

HISTORICAL_CASE_X_MODE_LABELS = {
    "Relative Bars": "相對交易日",
    "Actual Dates": "實際交易日期",
}


def historical_case_status_filter_label(option: str) -> str:
    return HISTORICAL_CASE_STATUS_FILTER_LABELS.get(option, option)


def historical_case_sort_label(option: str) -> str:
    return HISTORICAL_CASE_SORT_LABELS.get(option, option)


def historical_case_x_mode_label(option: str) -> str:
    return HISTORICAL_CASE_X_MODE_LABELS.get(option, option)


def initialize_session_state() -> None:
    st.session_state.setdefault("stock_search_stocks", [])
    st.session_state.setdefault("stock_search_failures", [])
    st.session_state.setdefault("research_stock", None)
    st.session_state.setdefault("research_failures", [])
    st.session_state.setdefault("historical_stock", None)
    st.session_state.setdefault("historical_series", None)
    st.session_state.setdefault("historical_failures", [])
    st.session_state.setdefault("watchlist_query_stocks", [])
    st.session_state.setdefault("watchlist_query_failures", [])
    st.session_state.setdefault("comparison_stocks", [])
    st.session_state.setdefault("comparison_failures", [])
    st.session_state.setdefault("ai_research_session", None)
    st.session_state.setdefault("ai_research_last_error", None)
    st.session_state.setdefault("ai_research_last_error_details", None)
    st.session_state.setdefault("ai_followup_question_draft", "")
    st.session_state.setdefault("ai_followup_question_type", None)
    st.session_state.setdefault("historical_case_result", None)
    st.session_state.setdefault("historical_case_last_error", None)
    st.session_state.setdefault("swing_research_result", None)
    st.session_state.setdefault("swing_research_config_fingerprint", None)
    st.session_state.setdefault("swing_research_last_error", None)
    st.session_state.setdefault("swing_research_price_series_by_symbol", {})
    st.session_state.setdefault("swing_research_source_context", None)
    st.session_state.setdefault("swing_research_result_mode", None)
    st.session_state.setdefault("swing_research_replay_date", None)
    st.session_state.setdefault("oos_validation_result", None)
    st.session_state.setdefault("oos_validation_fingerprint", None)
    st.session_state.setdefault("oos_validation_last_error", None)
    st.session_state.setdefault("oos_validation_source_context", None)


def render_query_failures(failures) -> None:
    for failure in failures:
        st.error(f"{failure.symbol} 查詢失敗：{failure.message}")


def run_stock_query(input_text: str):
    symbols = parse_stock_symbols(input_text)
    if not symbols:
        st.warning("請輸入至少一個股票代號。")
        return [], []

    return query_stock_batch(symbols)


def render_stock_cards(stocks) -> None:
    for stock in stocks:
        display_data = stock_display_data(stock)
        with st.container(border=True):
            st.subheader(f"{display_data['Symbol']} · {display_data['Company Name']}")

            price_col, market_cap_col, roe_col = st.columns(3)
            price_col.metric(
                indicator_label("current_price"),
                display_data["Current Price"],
                help=indicator_help("current_price"),
            )
            market_cap_col.metric(
                indicator_label("market_cap"),
                display_data["Market Cap"],
                help=indicator_help("market_cap"),
            )
            roe_col.metric(
                indicator_label("return_on_equity"),
                display_data["ROE"],
                help=indicator_help("return_on_equity"),
            )

            col1, col2, col3, col4 = st.columns(4)
            col1.metric(indicator_label("currency"), display_data["Currency"])
            col2.metric(
                indicator_label("trailing_pe"),
                display_data["Trailing PE"],
                help=indicator_help("trailing_pe"),
            )
            col3.metric(
                indicator_label("forward_pe"),
                display_data["Forward PE"],
                help=indicator_help("forward_pe"),
            )
            col4.metric(
                indicator_label("trailing_eps"),
                display_data["EPS"],
                help=indicator_help("trailing_eps"),
            )

            sector_col, industry_col = st.columns(2)
            sector_col.metric(
                indicator_label("sector"),
                display_data["Sector"],
                help=indicator_help("sector"),
            )
            industry_col.metric(
                indicator_label("industry"),
                display_data["Industry"],
                help=indicator_help("industry"),
            )


def render_stock_search() -> None:
    st.header("Dashboard")
    st.caption(
        "股票搜尋 · Company / Price（公司 / 股價） · Market Cap（市值） · "
        "P/E / EPS / ROE（估值 / 盈餘 / 股東權益報酬率） · Sector / Industry（產業）"
    )

    with st.form("stock_search_form"):
        input_text = st.text_input(
            "股票搜尋",
            placeholder="2330, NVDA, AAPL",
            key="stock_search_input",
        )
        submitted = st.form_submit_button("查詢")

    if submitted:
        stocks, failures = run_stock_query(input_text)
        st.session_state["stock_search_stocks"] = stocks
        st.session_state["stock_search_failures"] = failures

    render_query_failures(st.session_state["stock_search_failures"])
    render_stock_cards(st.session_state["stock_search_stocks"])


def render_research_metric_grid(metrics: list[tuple[str, str, str | None]], columns: int = 3) -> None:
    if not metrics:
        st.info("此區塊目前沒有可顯示的資料。")
        return

    for index in range(0, len(metrics), columns):
        cols = st.columns(columns)
        for col, metric in zip(cols, metrics[index:index + columns]):
            label, value, help_text = metric
            col.metric(label, value, help=help_text)


def render_observations(observations) -> None:
    if not observations:
        st.info("目前沒有觸發額外 observation。")
        return

    for observation in observations:
        body = (
            f"**{observation.title}**\n\n"
            "**Observation（觀察）**\n\n"
            f"{observation.what_happened}\n\n"
            "**Why it matters（為什麼值得注意）**\n\n"
            f"{observation.why_it_matters}\n\n"
            "**What to check（下一步查什麼）**\n\n"
            + "\n".join(f"- {item}" for item in observation.what_to_check)
        )
        if observation.observation_type == "info":
            st.info(body)
        else:
            st.warning(body)


def render_next_steps(next_steps) -> None:
    for step in next_steps:
        st.write(f"**{step.category} · {step.title}**")
        for item in step.items:
            st.write(f"□ {item}")


def render_historical_interpretation(series) -> None:
    report = build_historical_research_report(series)
    highlights = build_historical_highlights(report.observations)
    detail_groups = group_detailed_interpretation(report.observations)
    next_step_groups = build_next_step_display_groups(report.next_steps, per_category_limit=3)

    st.markdown("### Historical Interpretation（歷史趨勢解讀）")
    st.caption("固定規則整理 historical observations；這些是研究提示，不是評分、預測或投資建議。")
    st.caption(FY_PERIOD_CAPTION)

    st.markdown("#### Historical Highlights（歷史重點）")
    if highlights:
        for highlight in highlights:
            st.write(f"**{highlight.category} · {highlight.title}**")
            st.write(f"• {highlight.summary}")
    else:
        st.info("目前 historical observations 不足以形成重點摘要。")

    st.markdown("#### Detailed Interpretation（詳細趨勢解讀）")
    st.caption(ATTENTION_COLOR_EXPLANATION)
    for group in detail_groups:
        with st.expander(f"{group.category} · {len(group.observations)} observations", expanded=False):
            render_observations(group.observations)

    st.markdown("#### Research Next Steps（下一步研究）")
    for group in next_step_groups:
        st.write(f"**{group.category}**")
        for item in group.visible_items:
            st.write(f"□ {item}")
        if group.overflow_items:
            with st.expander("查看更多研究項目", expanded=False):
                for item in group.overflow_items:
                    st.write(f"□ {item}")


def render_historical_chart(
    series,
    fields: list[str],
    chart_type: str = "line",
    value_format: str = "number",
) -> None:
    rows = build_historical_chart_rows(series, fields)
    if not rows:
        return

    chart_data = pd.DataFrame(build_historical_chart_long_rows(rows, fields, value_format, series.currency))
    if chart_data.empty:
        return

    y_axis = alt.Axis(title=historical_chart_y_axis_title(value_format, series.currency))
    if value_format == "percentage":
        y_axis = alt.Axis(format=".0%", title="Percentage")
    elif value_format == "currency":
        y_axis = alt.Axis(format="~s", title=f"Amount ({series.currency or 'currency'})")

    base = alt.Chart(chart_data).encode(
        x=alt.X(
            "Period:N",
            sort=None,
            title="Fiscal period",
            axis=alt.Axis(labelAngle=0),
        ),
        y=alt.Y("Value:Q", axis=y_axis),
        color=alt.Color("Metric:N", title="Metric"),
        tooltip=[
            alt.Tooltip("Period:N", title="Period"),
            alt.Tooltip("Period End:N", title="Period End"),
            alt.Tooltip("Metric:N", title="Metric"),
            alt.Tooltip("Display Value:N", title="Value"),
        ],
    )

    if chart_type == "bar":
        chart = base.mark_bar()
    else:
        chart = base.mark_line(point=True)

    st.altair_chart(chart, use_container_width=True)


def build_historical_chart_long_rows(
    rows: list[dict[str, float | str | None]],
    fields: list[str],
    value_format: str,
    currency: str | None,
) -> list[dict[str, float | str]]:
    metric_labels = [key for key in rows[0] if key not in {"Period", "Period End"}] if rows else []
    selected_labels = metric_labels[:len(fields)]
    long_rows = []

    for row in rows:
        for metric in selected_labels:
            value = row.get(metric)
            if value is None:
                continue
            long_rows.append(
                {
                    "Period": row["Period"],
                    "Period End": row["Period End"],
                    "Metric": metric,
                    "Value": value,
                    "Display Value": historical_chart_display_value(value, value_format, currency),
                }
            )

    return long_rows


def historical_chart_display_value(
    value: float,
    value_format: str,
    currency: str | None,
) -> str:
    if value_format == "percentage":
        return f"{value * 100:.2f}%"
    if value_format == "currency":
        return format_currency_amount(value, currency)

    return f"{value:,.2f}"


def historical_chart_y_axis_title(value_format: str, currency: str | None) -> str:
    if value_format == "percentage":
        return "Percentage"
    if value_format == "currency":
        return f"Amount ({currency or 'currency'})"

    return "Value"


def render_research_glossary() -> None:
    with st.expander("研究名詞說明"):
        for entry in get_research_glossary().values():
            st.write(f"**{entry['title']}**")
            st.write(entry["description"])


def render_company_summary(stock) -> None:
    summary = build_company_summary_display(stock)

    st.markdown(f"#### {summary.section_title}")
    st.write(summary.short_summary)
    st.caption(summary.source_note)

    if summary.full_summary and summary.full_summary_title:
        with st.expander(summary.full_summary_title):
            st.write(summary.full_summary)

    if summary.original_yahoo_summary:
        with st.expander("查看 Yahoo Finance 詳細公司介紹"):
            st.write(summary.original_yahoo_summary)


def render_research() -> None:
    st.header("Research（研究）")
    st.caption("以固定研究流程整理目前可取得的基本面資料；本頁不使用 AI，也不產生 Buy / Sell / Hold recommendation。")

    with st.form("research_form"):
        input_text = st.text_input(
            "單一股票研究",
            placeholder="2330 或 NVDA",
            key="research_input",
        )
        submitted = st.form_submit_button("建立研究摘要")

    if submitted:
        symbols = parse_stock_symbols(input_text)
        if not symbols:
            st.warning("請輸入至少一個股票代號。")
            st.session_state["research_stock"] = None
            st.session_state["research_failures"] = []
        else:
            if len(symbols) > 1:
                st.info(f"Research 頁面目前顯示第一支股票：{symbols[0]}")
            stocks, failures = query_stock_batch([symbols[0]])
            st.session_state["research_stock"] = stocks[0] if stocks else None
            st.session_state["research_failures"] = failures

    render_query_failures(st.session_state["research_failures"])

    stock = st.session_state["research_stock"]
    if stock is None:
        st.info("輸入股票代號後，系統會依照 8 個固定研究問題建立研究摘要。")
        return

    report = build_research_report(stock)
    display_data = stock_display_data(stock)

    st.subheader(f"{display_data['Symbol']} · {display_data['Company Name']}")

    with st.expander("如何理解這些指標？"):
        st.write(
            "本頁使用 Yahoo Finance 提供的目前可取得基本面資料，協助建立研究問題與觀察方向。"
            "所有觀察都是固定規則產生的研究提示，不是投資建議，也不是整體評分。"
        )
    render_research_glossary()

    st.markdown("### Company Overview（公司概況）")
    render_research_metric_grid(
        [
            (indicator_label("symbol"), display_data["Symbol"], None),
            (indicator_label("company_name"), display_data["Company Name"], None),
            (indicator_label("sector"), format_sector(stock.sector), indicator_help("sector")),
            (indicator_label("industry"), format_industry(stock.industry), indicator_help("industry")),
            (indicator_label("market_cap"), format_currency_value(stock.market_cap, stock.currency), indicator_help("market_cap")),
        ],
        columns=3,
    )
    render_company_summary(stock)

    st.markdown("### Profitability（獲利能力）")
    render_research_metric_grid(
        [
            (indicator_label("return_on_equity"), format_percentage(stock.return_on_equity), indicator_help("return_on_equity")),
            (indicator_label("gross_margin"), format_percentage(stock.gross_margin), indicator_help("gross_margin")),
            (indicator_label("operating_margin"), format_percentage(stock.operating_margin), indicator_help("operating_margin")),
            (indicator_label("net_margin"), format_percentage(stock.net_margin), indicator_help("net_margin")),
            (indicator_label("trailing_eps"), format_decimal(stock.trailing_eps), indicator_help("trailing_eps")),
        ],
        columns=3,
    )

    st.markdown("### Growth（成長性）")
    st.info("資料說明：目前顯示的是 Yahoo Finance 提供的近期成長數據，僅反映目前可取得的資料，不代表多年長期趨勢。")
    growth_metrics = [
        (indicator_label("revenue_growth"), format_percentage(stock.revenue_growth), indicator_help("revenue_growth")),
        (indicator_label("earnings_growth"), format_percentage(stock.earnings_growth), indicator_help("earnings_growth")),
    ]
    render_research_metric_grid(growth_metrics, columns=2)

    st.markdown("### Financial Health（財務健康）")
    st.caption("Cash / Debt / Cash Flow 保留原始 currency context；不要跨幣別直接比較大小。")
    render_research_metric_grid(
        [
            (indicator_label("total_cash"), format_currency_value(stock.total_cash, stock.currency), indicator_help("total_cash")),
            (indicator_label("total_debt"), format_currency_value(stock.total_debt, stock.currency), indicator_help("total_debt")),
            (indicator_label("debt_to_equity"), format_debt_to_equity(stock.debt_to_equity), indicator_help("debt_to_equity")),
            (indicator_label("operating_cash_flow"), format_currency_value(stock.operating_cash_flow, stock.currency), indicator_help("operating_cash_flow")),
            (indicator_label("free_cash_flow"), format_currency_value(stock.free_cash_flow, stock.currency), indicator_help("free_cash_flow")),
        ],
        columns=3,
    )

    st.markdown("### Valuation（估值）")
    render_research_metric_grid(
        [
            (indicator_label("trailing_pe"), format_ratio(stock.trailing_pe), indicator_help("trailing_pe")),
            (indicator_label("forward_pe"), format_ratio(stock.forward_pe), indicator_help("forward_pe")),
            (indicator_label("price_to_book"), format_ratio(stock.price_to_book), indicator_help("price_to_book")),
        ],
        columns=3,
    )
    render_observations(report.valuation_observations)

    st.markdown("### Market Position（市場位置）")
    position_text = format_percentage(report.fifty_two_week_position)
    render_research_metric_grid(
        [
            (indicator_label("current_price"), format_price(stock.current_price, stock.currency), indicator_help("current_price")),
            (indicator_label("fifty_two_week_high"), format_price(stock.fifty_two_week_high, stock.currency), indicator_help("fifty_two_week_high")),
            (indicator_label("fifty_two_week_low"), format_price(stock.fifty_two_week_low, stock.currency), indicator_help("fifty_two_week_low")),
            (indicator_label("fifty_two_week_position"), position_text, indicator_help("fifty_two_week_position")),
            (indicator_label("fifty_day_average"), format_price(stock.fifty_day_average, stock.currency), indicator_help("fifty_day_average")),
            (indicator_label("two_hundred_day_average"), format_price(stock.two_hundred_day_average, stock.currency), indicator_help("two_hundred_day_average")),
        ],
        columns=3,
    )
    if report.fifty_two_week_position is not None:
        st.progress(max(0.0, min(1.0, report.fifty_two_week_position)))
    st.caption(report.market_position_note)

    st.markdown("### Risk Signals（風險提示）")
    st.caption("Risk Signals 是可解釋觀察，不是風險評分。")
    render_observations(report.risk_signals)

    st.markdown("### Research Next Steps（下一步研究）")
    render_next_steps(report.next_steps)


def render_historical_trends() -> None:
    st.header("Historical Trends（歷史趨勢）")
    st.caption(
        "使用 Yahoo Finance annual financial statements 呈現歷史基本面資料；"
        "本頁不使用 AI，也不產生 Buy / Sell / Hold recommendation。"
    )

    with st.form("historical_trends_form"):
        input_text = st.text_input(
            "單一股票歷史趨勢",
            placeholder="2330 或 NVDA",
            key="historical_trends_input",
        )
        submitted = st.form_submit_button("建立歷史趨勢")

    if submitted:
        symbols = parse_stock_symbols(input_text)
        if not symbols:
            st.warning("請輸入至少一個股票代號。")
            st.session_state["historical_stock"] = None
            st.session_state["historical_series"] = None
            st.session_state["historical_failures"] = []
        else:
            if len(symbols) > 1:
                st.info(f"Historical Trends 頁面目前顯示第一支股票：{symbols[0]}")
            stocks, failures = query_stock_batch([symbols[0]])
            stock = stocks[0] if stocks else None
            series = None
            historical_failures = failures.copy()
            if stock is not None:
                try:
                    series = get_historical_financials(stock.symbol or symbols[0])
                except HistoricalFinancialServiceError as error:
                    historical_failures.append(
                        StockQueryFailure(
                            symbol=stock.symbol or symbols[0],
                            message=str(error),
                        )
                    )
            st.session_state["historical_stock"] = stock
            st.session_state["historical_series"] = series
            st.session_state["historical_failures"] = historical_failures

    render_query_failures(st.session_state["historical_failures"])

    stock = st.session_state["historical_stock"]
    series = st.session_state["historical_series"]
    if stock is None or series is None:
        st.info("輸入股票代號後，系統會顯示年度營收、獲利、利潤率、現金流與財務結構趨勢。")
        return

    display = build_historical_trend_display(series, stock)
    overview = display.overview

    st.subheader(f"{overview.symbol} · {overview.company_name}")
    if overview.stale_warning:
        st.warning(overview.stale_warning)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Currency", overview.currency)
    metric_cols[1].metric("Annual periods", overview.annual_periods)
    metric_cols[2].metric("Available periods", overview.available_periods)
    metric_cols[3].metric("Historical data cache", overview.cache_status)
    st.caption(f"Period range: {overview.period_range}")

    with st.expander("資料來源與 Period End 說明"):
        st.write(
            "歷史財務資料來自 Yahoo Finance annual financial statements。"
            "Period End 是財務資料期間結束日；例如 NVDA 或 AAPL 的年度結束日可能不是 12/31。"
            "因此本頁優先顯示 FY ending YYYY-MM-DD，避免把期間結束日誤讀為完整曆年。"
        )
        st.write(
            "YoY 只在相鄰資料的 year component 連續時顯示；若中間缺年度，該期 YoY 會顯示 N/A。"
            "本頁只呈現歷史數值與可見變化，不自動判斷 improving、deteriorating、strong 或 weak。"
        )

    for note in display.missing_data_notes:
        st.info(note)

    st.markdown("### Revenue（營收）Trend")
    st.caption(historical_metric_help("revenue"))
    if has_enough_historical_data(series, ["revenue"]):
        render_historical_chart(series, ["revenue"], chart_type="bar", value_format="currency")
    else:
        st.info("目前可取得的歷史資料不足，暫不顯示趨勢。")
    st.dataframe(display.revenue_rows, width="stretch", hide_index=True)

    st.markdown("### Earnings（獲利）Trend")
    st.caption(historical_metric_help("net_income"))
    st.caption(historical_metric_help("eps"))
    st.markdown("#### Net Income Trend")
    if has_enough_historical_data(series, ["net_income"]):
        render_historical_chart(series, ["net_income"], value_format="currency")
    else:
        st.info("目前可取得的 Net Income 歷史資料不足，暫不顯示趨勢。")
    st.markdown("#### EPS Trend")
    if has_enough_historical_data(series, ["eps"]):
        render_historical_chart(series, ["eps"], value_format="eps")
    else:
        st.info("目前可取得的 EPS 歷史資料不足，暫不顯示趨勢。")
    st.dataframe(display.earnings_rows, width="stretch", hide_index=True)

    st.markdown("### Margins（利潤率趨勢）")
    with st.expander("利潤率怎麼看？"):
        st.write(historical_metric_help("gross_margin"))
        st.write(historical_metric_help("operating_margin"))
        st.write(historical_metric_help("net_margin"))
        st.write("Margin 上升或下降都需要搭配產品組合、費用結構、產業循環與一次性項目理解，不能單獨判斷好壞。")
    if has_enough_historical_data(series, ["gross_margin", "operating_margin", "net_margin"]):
        render_historical_chart(
            series,
            ["gross_margin", "operating_margin", "net_margin"],
            value_format="percentage",
        )
    else:
        st.info("目前可取得的歷史資料不足，暫不顯示趨勢。")
    st.dataframe(display.margin_rows, width="stretch", hide_index=True)

    st.markdown("### Cash Flow（現金流趨勢）")
    st.caption(historical_metric_help("operating_cash_flow"))
    st.caption(historical_metric_help("free_cash_flow"))
    st.info(historical_metric_help("capital_expenditure"))
    if has_enough_historical_data(
        series,
        ["operating_cash_flow", "capital_expenditure", "free_cash_flow"],
    ):
        render_historical_chart(
            series,
            ["operating_cash_flow", "capital_expenditure", "free_cash_flow"],
            value_format="currency",
        )
    else:
        st.info("目前可取得的歷史資料不足，暫不顯示趨勢。")
    st.dataframe(display.cash_flow_rows, width="stretch", hide_index=True)

    st.markdown("### Financial Position（財務結構）")
    st.caption("Financial Position 保留 currency context；不同股票或不同幣別不要直接排名。")
    st.caption(historical_metric_help("total_debt"))
    st.caption(historical_metric_help("total_equity"))
    if has_enough_historical_data(
        series,
        ["total_assets", "total_debt", "total_equity", "cash_and_cash_equivalents"],
    ):
        render_historical_chart(
            series,
            ["total_assets", "total_debt", "total_equity", "cash_and_cash_equivalents"],
            value_format="currency",
        )
    else:
        st.info("目前可取得的歷史資料不足，暫不顯示趨勢。")
    st.dataframe(display.financial_position_rows, width="stretch", hide_index=True)

    render_historical_interpretation(series)

    st.markdown("### Historical Table（完整年度資料）")
    st.dataframe(display.historical_table_rows, width="stretch", hide_index=True)


def openai_api_configured() -> bool:
    return is_openai_api_configured()


def build_ai_research_turn(
    input_text: str,
    question_type,
    question: str,
    *,
    parent_turn_id: str | None = None,
    on_provider_call=None,
) -> dict:
    symbols = parse_stock_symbols(input_text)
    if not symbols:
        raise ValueError("請輸入至少一個股票代號。")
    if len(symbols) > 1:
        raise ValueError("AI Research 目前只支援單一股票。")
    if not question.strip():
        raise ValueError("你想研究什麼？不可空白。")
    if len(question.strip()) > MAX_RESEARCH_QUESTION_LENGTH:
        raise ValueError("研究問題長度超過限制。")

    symbol = symbols[0]
    stocks, failures = query_stock_batch([symbol])
    if failures:
        raise ValueError(f"{failures[0].symbol} 查詢失敗：{failures[0].message}")
    stock = stocks[0]
    display_data = stock_display_data(stock)

    research_report = build_research_report(stock)
    historical_series = get_historical_financials(stock.symbol or symbol)
    historical_research_report = build_historical_research_report(historical_series)
    context = build_research_context(
        stock=stock,
        research_report=research_report,
        historical_series=historical_series,
        historical_research_report=historical_research_report,
        display_name=display_data["Company Name"],
    )
    selected_context = select_research_context(
        context,
        ResearchSelectionRequest(question_type=question_type),
    )
    fingerprint = build_request_fingerprint(
        symbol=stock.symbol or symbol,
        question_type=question_type,
        question=question,
        selected_context=selected_context,
    )
    if on_provider_call is not None:
        on_provider_call()
    answer = generate_grounded_research_answer(
        question=question,
        selected_context=selected_context,
    )
    turn = create_research_turn(
        parent_turn_id=parent_turn_id,
        symbol=stock.symbol or symbol,
        question_type=question_type,
        question=question,
        fingerprint=fingerprint,
        answer=answer,
        selected_context=selected_context,
    )

    return {
        "turn": turn,
        "display_name": display_data["Company Name"],
        "historical_stale": bool(historical_series.is_stale),
    }


def build_ai_research_result(input_text: str, question_type, question: str) -> dict:
    turn_result = build_ai_research_turn(input_text, question_type, question)
    turn = turn_result["turn"]
    selected_context = turn.selected_context
    answer = turn.answer
    return {
        "last_symbol": turn.symbol,
        "last_display_name": turn_result["display_name"],
        "last_question_type": turn.question_type,
        "last_question": turn.question,
        "selected_context": selected_context,
        "selected_context_summary": json_safe_selected_context_summary(selected_context),
        "answer": answer,
        "metadata": answer.metadata,
        "error": None,
        "error_details": None,
        "request_fingerprint": turn.fingerprint,
        "historical_stale": turn_result["historical_stale"],
    }


def build_ai_research_error_result(
    input_text: str,
    question_type,
    question: str,
    error: Exception,
) -> dict:
    return {
        "last_symbol": normalize_stock_symbol(input_text),
        "last_display_name": None,
        "last_question_type": question_type,
        "last_question": question.strip(),
        "selected_context": None,
        "selected_context_summary": None,
        "answer": None,
        "metadata": None,
        "error": safe_error_message(error),
        "error_details": safe_error_details(error),
        "request_fingerprint": None,
        "historical_stale": False,
    }


def render_ai_research() -> None:
    st.header("AI Research（AI 研究）")
    st.caption("AI 依系統目前可取得的資料與快取狀態回答；回答不是即時分析，也不是投資建議。")

    if openai_api_configured():
        st.success("OpenAI API：Configured")
    else:
        st.warning("OpenAI API：Not configured。請先以環境變數設定 OpenAI API Key。")

    config = get_ai_research_config()
    question_options = question_type_options()

    session = st.session_state["ai_research_session"]
    if session is not None:
        render_ai_research_session_header(session)

    st.markdown("### Initial Grounded Research（初始研究）")
    with st.form("ai_research_form"):
        input_text = st.text_input(
            "股票",
            placeholder="2454 或 NVDA",
            key="ai_research_symbol_input",
        )
        question_type = st.selectbox(
            "Research Question Type",
            question_options,
            format_func=question_type_label,
            help="請選擇本次 AI Research 使用的 deterministic context selection 類型。",
            key="ai_research_question_type",
        )
        st.caption(question_type_help(question_type))
        question = st.text_area(
            "你想研究什麼？",
            placeholder=question_type_placeholder(question_type),
            max_chars=MAX_RESEARCH_QUESTION_LENGTH,
            key="ai_research_question",
        )
        st.caption(
            f"最多 {MAX_RESEARCH_QUESTION_LENGTH} 字。AI 只會依選擇的研究類型與可用證據回答。"
        )
        st.caption("此操作會呼叫 OpenAI API，可能產生 API 使用費用。")
        submitted = st.form_submit_button(
            "產生 AI 研究",
            disabled=not openai_api_configured(),
        )

    if submitted:
        request_attempts = {"count": 0}

        def count_provider_call() -> None:
            request_attempts["count"] += 1

        with st.spinner("正在產生 Grounded AI Research…"):
            try:
                turn_result = build_ai_research_turn(
                    input_text,
                    question_type,
                    question,
                    on_provider_call=count_provider_call,
                )
                turn = turn_result["turn"]
                new_session = AIResearchSession(
                    symbol=turn.symbol,
                    display_name=turn_result["display_name"],
                    turns=[],
                    api_request_count=request_attempts["count"],
                )
                append_verified_turn(new_session, turn)
                st.session_state["ai_research_session"] = new_session
                st.session_state["ai_research_last_error"] = None
                st.session_state["ai_research_last_error_details"] = None
                st.session_state["ai_followup_question_draft"] = ""
                st.session_state["ai_followup_question_type"] = None
            except Exception as error:
                if request_attempts["count"] and st.session_state["ai_research_session"] is not None:
                    st.session_state["ai_research_session"].api_request_count += request_attempts["count"]
                st.session_state["ai_research_last_error"] = safe_error_message(error)
                st.session_state["ai_research_last_error_details"] = safe_error_details(error)

    if st.button(
        "清除 AI 研究工作階段",
        disabled=st.session_state["ai_research_session"] is None
        and st.session_state["ai_research_last_error"] is None,
    ):
        st.session_state["ai_research_session"] = None
        st.session_state["ai_research_last_error"] = None
        st.session_state["ai_research_last_error_details"] = None
        st.session_state["ai_followup_question_draft"] = ""
        st.session_state["ai_followup_question_type"] = None
        st.rerun()

    if st.session_state["ai_research_last_error"]:
        render_ai_research_error(
            {
                "error": st.session_state["ai_research_last_error"],
                "error_details": st.session_state["ai_research_last_error_details"],
            }
        )
        st.info("延伸研究未完成，先前研究結果仍保留。")

    session = st.session_state["ai_research_session"]
    if session is None or not session.turns:
        st.info("輸入單一股票與研究問題後，按下「產生 AI 研究」才會呼叫 OpenAI API。")
        return

    render_research_history(session, config.model)
    current_turn = session.turns[-1]
    st.markdown("### 目前研究結果")
    render_ai_research_turn_answer(current_turn, config.model)
    render_followup_research(session, current_turn, config.model)


def render_ai_research_session_header(session: AIResearchSession) -> None:
    usage = aggregate_session_usage(session.turns or [])
    st.subheader(f"{session.symbol} · {session.display_name or 'N/A'}")
    cols = st.columns(4)
    cols[0].metric("Research Session", f"{session.turn_count} / {MAX_RESEARCH_TURNS}")
    cols[1].metric("AI Requests in this session", f"{session.api_request_count} / {MAX_RESEARCH_TURNS}")
    cols[2].metric("Input tokens", f"{usage['input_tokens']:,}")
    cols[3].metric("Total tokens", f"{usage['total_tokens']:,}")


def render_research_history(session: AIResearchSession, fallback_model: str) -> None:
    st.markdown("### Research History（本次研究歷程）")
    for index, turn in enumerate(session.turns or [], start=1):
        label = (
            f"Turn {index} — {question_type_label(turn.question_type)} — "
            f"{format_generated_at(turn.generated_at)}"
        )
        if turn is session.turns[-1]:
            st.write(f"**{label}**")
            st.caption(turn.question)
            continue
        with st.expander(label, expanded=False):
            st.caption("先前研究結果")
            render_ai_research_turn_answer(turn, fallback_model)


def render_ai_research_error(result: dict) -> None:
    st.error(result["error"])
    with st.expander("技術資訊", expanded=False):
        details = result.get("error_details") or {}
        if details:
            st.dataframe([details], width="stretch", hide_index=True)
        else:
            st.write("N/A")


def render_ai_research_answer(result: dict, fallback_model: str) -> None:
    turn = create_research_turn(
        parent_turn_id=None,
        symbol=result["last_symbol"],
        question_type=result["last_question_type"],
        question=result["last_question"],
        fingerprint=result["request_fingerprint"],
        answer=result["answer"],
        selected_context=result["selected_context"],
    )
    render_ai_research_turn_answer(turn, fallback_model)


def render_ai_research_turn_answer(turn, fallback_model: str) -> None:
    answer = turn.answer
    selected_context = turn.selected_context
    metadata = turn.metadata
    question_type = turn.question_type

    display_name = selected_context.display_name or "N/A"
    st.subheader(f"{turn.symbol} · {display_name}")
    header_cols = st.columns(4)
    header_cols[0].metric("Question Type", question_type_label(question_type))
    header_cols[1].metric("Generated", format_generated_at(metadata.generated_at))
    header_cols[2].metric("Model", metadata.model or fallback_model)
    header_cols[3].metric("Fingerprint", turn.fingerprint[:12])
    st.write(f"**User Question：** {turn.question}")

    render_grounded_answer_sections(answer, selected_context, metadata)


def render_grounded_answer_sections(answer, selected_context, metadata) -> None:
    st.markdown("#### AI Summary（AI 摘要）")
    st.write(answer.summary)
    st.caption("此回答僅依本回合重新選取的研究資料產生。")

    st.markdown("#### Grounded Findings（有證據支持的研究觀察）")
    selected_evidence = evidence_lookup(selected_context)
    for index, finding in enumerate(answer.findings, start=1):
        st.write(f"**Finding {index}**")
        st.write(finding.statement)
        with st.expander("查看 Evidence", expanded=False):
            for evidence_id in finding.evidence_ids:
                evidence = selected_evidence.get(evidence_id)
                if evidence is None:
                    st.warning(f"{evidence_id}：Evidence unavailable")
                    continue
                render_evidence_detail(evidence, selected_evidence)

    st.markdown("#### Limitations（資料限制）")
    if answer.limitations:
        st.write("**AI 提到的限制**")
        for item in answer.limitations:
            st.write(f"- {item}")
    if selected_context.selected_limitations:
        st.write("**Underlying Context Limitations**")
        for item in selected_context.selected_limitations:
            st.write(f"- {format_limitation_item(item)}")
    if not answer.limitations and not selected_context.selected_limitations:
        st.info("目前沒有額外 limitations。")

    st.markdown("#### Missing Information（缺漏資料）")
    if answer.missing_information:
        st.write("**AI 提到的缺漏資料**")
        for item in answer.missing_information:
            st.write(f"- {item}")
    if selected_context.selected_missing_data:
        st.write("**Deterministic Missing Data Detail**")
        st.dataframe(
            [format_missing_data_item(item) for item in selected_context.selected_missing_data],
            width="stretch",
            hide_index=True,
        )
    if not answer.missing_information and not selected_context.selected_missing_data:
        st.info("目前沒有 selected missing-data detail。")

    st.markdown("#### Research Next Steps（下一步研究）")
    for item in answer.next_steps:
        st.write(f"□ {item}")
    st.caption("這些是研究方向，不是投資建議。")

    st.markdown("#### Validation")
    st.success("Structured Output ✓　Evidence Grounding ✓　Numeric Guard ✓　Advice Guard ✓")
    st.caption("回答已通過系統的結構與引用驗證。")

    render_selected_context_preview(selected_context)
    render_ai_request_details(metadata)


def render_followup_research(session: AIResearchSession, current_turn, fallback_model: str) -> None:
    st.markdown("### Follow-up Research（延伸研究）")
    st.caption("你可以從以下方向繼續研究。這些是下一步研究問題，不是 AI 結論。")
    st.caption("每次延伸研究都是新的 OpenAI API request，可能產生額外 API 使用費用。")
    st.caption("系統只會根據目前研究資料提供研究整理，不提供買賣建議。")

    suggestions = build_followup_suggestions(
        current_question_type=current_turn.question_type,
        answer_next_steps=current_turn.answer.next_steps,
        selected_context=current_turn.selected_context,
    )
    if suggestions:
        for suggestion in suggestions:
            with st.container(border=True):
                st.write(f"**{suggestion.title}**")
                st.write(f"問題：{suggestion.question}")
                st.caption(f"Research Type：{question_type_label(suggestion.question_type)}")
                if st.button(
                    "使用這個問題",
                    key=f"use_followup_{current_turn.turn_id}_{suggestion.id}",
                    disabled=not session.can_add_turn,
                ):
                    st.session_state["ai_followup_question_draft"] = suggestion.question
                    st.session_state["ai_followup_question_type"] = suggestion.question_type
                    st.rerun()
    else:
        st.info("目前沒有可顯示的延伸研究問題。")

    if not session.can_add_turn:
        st.warning(f"此研究工作階段已達 {MAX_RESEARCH_TURNS} 回合上限。可清除後重新開始。")
        return

    inferred_type = infer_followup_question_type(
        st.session_state.get("ai_followup_question_draft", ""),
        st.session_state.get("ai_followup_question_type"),
    )
    selected_type = st.session_state.get("ai_followup_question_type") or inferred_type
    type_index = question_type_options().index(selected_type) if selected_type in question_type_options() else 0
    st.caption(f"建議研究類型：{question_type_label(inferred_type)}")
    st.caption("Routing: deterministic")

    with st.form("ai_followup_form"):
        followup_type = st.selectbox(
            "Question Type",
            question_type_options(),
            index=type_index,
            format_func=question_type_label,
            help="可覆寫建議研究類型；AI 不會自動偷偷改 question type。",
            key=f"ai_followup_question_type_widget_{current_turn.turn_id}",
        )
        followup_question = st.text_area(
            "Question",
            value=st.session_state.get("ai_followup_question_draft", ""),
            max_chars=MAX_RESEARCH_QUESTION_LENGTH,
            key=f"ai_followup_question_widget_{current_turn.turn_id}",
        )
        st.caption(f"最多 {MAX_RESEARCH_QUESTION_LENGTH} 字。延伸研究只針對目前股票：{session.symbol}。")
        followup_submitted = st.form_submit_button(
            "產生延伸研究",
            disabled=not openai_api_configured() or not session.can_add_turn,
        )

    if followup_submitted:
        if not followup_question.strip():
            st.session_state["ai_research_last_error"] = "延伸研究問題不可空白。"
            st.session_state["ai_research_last_error_details"] = {"error_type": "ValueError"}
            st.rerun()

        with st.spinner("正在產生 Follow-up Grounded AI Research…"):
            try:
                request_attempts = {"count": 0}

                def count_provider_call() -> None:
                    request_attempts["count"] += 1
                    session.api_request_count += 1

                turn_result = build_ai_research_turn(
                    session.symbol,
                    followup_type,
                    followup_question,
                    parent_turn_id=current_turn.turn_id,
                    on_provider_call=count_provider_call,
                )
                append_verified_turn(session, turn_result["turn"])
                st.session_state["ai_research_last_error"] = None
                st.session_state["ai_research_last_error_details"] = None
                st.session_state["ai_followup_question_draft"] = ""
                st.session_state["ai_followup_question_type"] = None
                st.rerun()
            except Exception as error:
                st.session_state["ai_research_last_error"] = safe_error_message(error)
                st.session_state["ai_research_last_error_details"] = safe_error_details(error)
                st.rerun()


def render_evidence_detail(
    evidence,
    selected_evidence: dict,
    *,
    visited: set[str] | None = None,
) -> None:
    visited = visited or set()
    if evidence.id in visited:
        st.warning(f"{evidence.id}：lineage already shown")
        return
    visited.add(evidence.id)

    st.write(f"**Evidence ID：** {evidence.id}")
    st.write(f"**Metric：** {evidence.metric}")
    st.write(f"**Value：** {format_evidence_value(evidence)}")
    st.write(f"**Period：** {format_evidence_period(evidence.period_end)}")
    st.write(f"**Source：** {evidence.source}")
    st.write(f"**Source Type：** {source_type_label(evidence.source_type)}")
    if evidence.source_type == "derived":
        st.write("**Derived Evidence（衍生資料）**")
    if evidence.note:
        st.caption(evidence.note)
    if evidence.derived_from:
        with st.expander("Derived from", expanded=False):
            for source_id in evidence.derived_from:
                source_evidence = selected_evidence.get(source_id)
                if source_evidence is None:
                    st.warning(f"{source_id}：Evidence unavailable")
                else:
                    render_evidence_detail(source_evidence, selected_evidence, visited=visited)


def render_selected_context_preview(selected_context) -> None:
    with st.expander("Research Context Used（本次使用資料）", expanded=False):
        summary = json_safe_selected_context_summary(selected_context)
        metric_cols = st.columns(4)
        metric_cols[0].metric("Evidence count", summary["evidence_count"])
        metric_cols[1].metric("Observation count", len(selected_context.selected_observations))
        metric_cols[2].metric("Missing-data count", summary["missing_data_count"])
        metric_cols[3].metric("Limitation count", summary["limitation_count"])
        grouped = {}
        for item in selected_context.selected_evidence:
            grouped.setdefault(item.category, []).append(item.id)
        for category, ids in grouped.items():
            st.write(f"**{category}**")
            for evidence_id in ids:
                st.write(f"- {evidence_id}")


def render_ai_request_details(metadata) -> None:
    usage = metadata.usage if isinstance(metadata.usage, dict) else {}
    with st.expander("AI Request Details", expanded=False):
        st.dataframe(
            [
                {
                    "model": metadata.model,
                    "response_id": metadata.response_id or "N/A",
                    "generated_at": format_generated_at(metadata.generated_at),
                    "input_tokens": usage.get("input_tokens", "N/A"),
                    "output_tokens": usage.get("output_tokens", "N/A"),
                    "reasoning_tokens": metadata.reasoning_tokens
                    if metadata.reasoning_tokens is not None
                    else "N/A",
                    "cached_input_tokens": metadata.cached_input_tokens
                    if metadata.cached_input_tokens is not None
                    else "N/A",
                    "total_tokens": usage.get("total_tokens", "N/A"),
                }
            ],
            width="stretch",
            hide_index=True,
        )


def build_swing_research_scan_result(
    *,
    symbols: tuple[str, ...],
    config: SwingScannerConfig,
    source_type: str,
) -> dict:
    price_series_by_symbol = {}

    def recording_price_loader(symbol: str, *, force_refresh: bool = False):
        price_series = get_historical_prices(symbol, force_refresh=force_refresh)
        price_series_by_symbol[price_series.symbol] = price_series
        return price_series

    scanner = SwingScannerService(price_loader=recording_price_loader)
    result = scanner.scan(symbols, config)
    fingerprint = swing_dashboard.fingerprint_from_config(
        result.normalized_symbols,
        config,
        source_type=source_type,
    )
    return {
        "result": result,
        "fingerprint": fingerprint,
        "price_series_by_symbol": price_series_by_symbol,
    }


def build_swing_research_replay_result(
    *,
    symbols: tuple[str, ...],
    config: HistoricalReplayConfig,
    source_type: str,
) -> dict:
    price_series_by_symbol = {}

    def recording_price_loader(symbol: str, *, force_refresh: bool = False):
        price_series = get_historical_prices(symbol, force_refresh=force_refresh)
        price_series_by_symbol[price_series.symbol] = price_series
        return price_series

    replay_service = HistoricalReplayService(price_loader=recording_price_loader)
    result = replay_service.replay_scan(symbols, config)
    fingerprint = swing_dashboard.replay_fingerprint_from_config(
        result.normalized_symbols,
        config,
        source_type=source_type,
    )
    return {
        "result": result,
        "fingerprint": fingerprint,
        "price_series_by_symbol": price_series_by_symbol,
    }


def build_swing_research_walk_forward_result(
    *,
    symbols: tuple[str, ...],
    config: WalkForwardReplayConfig,
    source_type: str,
) -> dict:
    price_series_by_symbol = {}

    def recording_price_loader(symbol: str, *, force_refresh: bool = False):
        price_series = get_historical_prices(symbol, force_refresh=force_refresh)
        price_series_by_symbol[price_series.symbol] = price_series
        return price_series

    walk_forward_service = WalkForwardReplayService(price_loader=recording_price_loader)
    result = walk_forward_service.run_walk_forward_replay(symbols, config)
    fingerprint = swing_dashboard.walk_forward_fingerprint_from_config(
        result.normalized_symbols,
        config,
        source_type=source_type,
    )
    return {
        "result": result,
        "fingerprint": fingerprint,
        "price_series_by_symbol": price_series_by_symbol,
    }


def build_oos_validation_result(
    *,
    symbols: tuple[str, ...],
    config: OutOfSampleValidationConfig,
    source_type: str,
) -> dict:
    service = OutOfSampleValidationService()
    result = service.run_out_of_sample_validation(symbols, config)
    fingerprint = oos_dashboard.build_oos_validation_request_fingerprint(
        normalized_symbols=result.normalized_symbols,
        source_type=source_type,
        development_start=config.development_period.start_date,
        development_end=config.development_period.end_date,
        validation_start=config.validation_period.start_date,
        validation_end=config.validation_period.end_date,
        holdout_start=config.holdout_period.start_date,
        holdout_end=config.holdout_period.end_date,
        replay_frequency=config.replay_frequency.value,
        overlap_policy=config.overlap_policy.value,
        cooldown_bars=config.cooldown_bars,
        historical_start_date=config.historical_start_date,
        minimum_resolved_samples=config.minimum_resolved_samples,
    )
    return {
        "result": result,
        "fingerprint": fingerprint,
    }


def render_swing_research() -> None:
    st.header("Swing Research（波段研究）")
    st.caption(
        "整合波段掃描、歷史驗證與歷史案例的日常研究流程。"
        "符合條件的股票只是研究候選，不是交易清單；研究優先順序只是檢視順序。"
    )

    universes = read_universes_for_ui()
    watchlist_symbols = read_watchlist_for_ui(show_error=False)
    st.markdown("### 掃描設定")
    scan_mode = st.radio(
        "掃描模式",
        [
            swing_dashboard.CURRENT_SCAN_MODE,
            swing_dashboard.HISTORICAL_REPLAY_MODE,
            swing_dashboard.WALK_FORWARD_REPLAY_MODE,
            oos_dashboard.OOS_VALIDATION_MODE,
        ],
        format_func=get_scan_mode_label,
        horizontal=True,
        key="swing_research_scan_mode",
    )
    source_options = [
        universe_ui.MANUAL_SOURCE,
        universe_ui.WATCHLIST_SOURCE,
        universe_ui.SAVED_UNIVERSE_SOURCE,
    ]
    source_type = st.selectbox(
        "股票來源",
        source_options,
        format_func=get_source_label,
        key="swing_research_symbol_source",
    )
    selected_universe = None
    input_symbols = ""

    with st.form("swing_research_scan_form"):
        if source_type == universe_ui.MANUAL_SOURCE:
            input_symbols = st.text_area(
                "股票池",
                placeholder="2330\n2454\nNVDA\nAAPL\n6488.TWO",
                help="每行輸入一個股票代號。例如：2330、2454、NVDA、6488.TWO",
                key="swing_research_symbol_input",
                height=140,
            )
        elif source_type == universe_ui.WATCHLIST_SOURCE:
            st.caption(f"觀察清單股票數：{len(watchlist_symbols)}")
            if not watchlist_symbols:
                st.info("觀察清單目前沒有股票。")
        else:
            if universes:
                universe_labels = [
                    universe_ui.universe_selector_label(universe)
                    for universe in universes
                ]
                selected_label = st.selectbox(
                    "研究股票池",
                    universe_labels,
                    key="swing_research_universe_selector",
                )
                selected_universe = universes[universe_labels.index(selected_label)]
                st.caption(
                    f"{selected_universe.name} · "
                    f"{selected_universe.symbol_count} 檔股票 · "
                    f"更新時間：{universe_ui.format_universe_updated_at(selected_universe)}"
                )
                with st.expander("股票", expanded=False):
                    st.write(universe_ui.symbols_to_text(selected_universe.symbols) or "N/A")
            else:
                st.info("尚未建立自訂股票池。仍可使用手動輸入。")
        st.text_input("篩選規則", value=get_signal_definition_label(TECHNICAL_EXAMPLE_SIGNAL_V1.id), disabled=True, key="swing_signal_definition_label")
        st.caption("依均線、動能、成交量與接近前高等技術條件，判斷目前是否符合研究條件。")
        st.text_input("歷史研究目標", value=get_outcome_definition_label(RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id), disabled=True, key="swing_outcome_definition_label")
        st.caption("用來判斷歷史案例是否達成研究目標。這是歷史研究目標，不代表實際交易獲利。")
        overlap_label = st.selectbox("歷史訊號樣本處理方式", ["ALLOW_ALL", "COOLDOWN"], format_func=get_overlap_policy_label)
        st.caption("保留全部訊號可能包含同一段行情中彼此相近的歷史事件。")
        cooldown_bars = None
        if overlap_label == "COOLDOWN":
            cooldown_bars = st.number_input("訊號間隔交易日數", min_value=1, value=20, step=1)
        date_cols = st.columns(2)
        frequency_label = None
        walk_forward_start_date = None
        walk_forward_end_date = None
        development_start_date = None
        development_end_date = None
        validation_start_date = None
        validation_end_date = None
        holdout_start_date = None
        holdout_end_date = None
        historical_start_date = None
        if scan_mode == swing_dashboard.HISTORICAL_REPLAY_MODE:
            start_date = date_cols[0].date_input("歷史研究開始日期", value=pd.to_datetime("2018-01-01").date(), key="swing_replay_historical_start_date")
            replay_date = date_cols[1].date_input("指定回放日期", value=pd.to_datetime("2024-06-30").date(), key="swing_replay_date")
            end_date = None
        elif scan_mode == oos_dashboard.OOS_VALIDATION_MODE:
            st.caption("樣本外驗證會比較開發期間、驗證期間與保留樣本期間三段固定規則結果；只有按下執行才會讀取完整歷史價格資料。")
            development_cols = st.columns(2)
            development_start_date = development_cols[0].date_input("開發期間開始日期", value=pd.to_datetime("2018-01-01").date(), key="oos_development_start_date")
            development_end_date = development_cols[1].date_input("開發期間結束日期", value=pd.to_datetime("2022-12-31").date(), key="oos_development_end_date")
            validation_cols = st.columns(2)
            validation_start_date = validation_cols[0].date_input("驗證期間開始日期", value=pd.to_datetime("2023-01-01").date(), key="oos_validation_start_date")
            validation_end_date = validation_cols[1].date_input("驗證期間結束日期", value=pd.to_datetime("2024-12-31").date(), key="oos_validation_end_date")
            holdout_cols = st.columns(2)
            holdout_start_date = holdout_cols[0].date_input("保留樣本期間開始日期", value=pd.to_datetime("2025-01-01").date(), key="oos_holdout_start_date")
            holdout_end_date = holdout_cols[1].date_input("保留樣本期間結束日期", value=date.today(), key="oos_holdout_end_date")
            frequency_label = st.selectbox("回放頻率", ["MONTHLY", "WEEKLY"], index=0, format_func=get_frequency_label)
            historical_start_date = st.date_input("歷史研究開始日期", value=pd.to_datetime("2018-01-01").date(), key="oos_historical_start_date")
            start_date = development_start_date
            replay_date = None
            end_date = holdout_end_date
        elif scan_mode == swing_dashboard.WALK_FORWARD_REPLAY_MODE:
            walk_forward_start_date = date_cols[0].date_input("歷史研究開始日期", value=pd.to_datetime("2024-01-01").date(), key="walk_forward_start_date")
            walk_forward_end_date = date_cols[1].date_input("歷史研究結束日期", value=pd.to_datetime("2024-06-30").date(), key="walk_forward_end_date")
            frequency_label = st.selectbox("回放頻率", ["MONTHLY", "WEEKLY"], index=0, format_func=get_frequency_label)
            historical_start_date = st.date_input("歷史研究開始日期（統計資料）", value=pd.to_datetime("2018-01-01").date(), key="walk_forward_historical_start_date")
            start_date = walk_forward_start_date
            replay_date = None
            end_date = walk_forward_end_date
        else:
            start_date = date_cols[0].date_input("歷史研究開始日期", value=pd.to_datetime("2018-01-01").date(), key="current_historical_start_date")
            replay_date = None
            end_date = date_cols[1].date_input("歷史研究結束日期", value=pd.to_datetime("2025-12-31").date(), key="current_historical_end_date")
        preferred_sample_minimum = st.number_input(
            "偏好最低有效歷史樣本數",
            min_value=0,
            value=20,
            step=1,
            help="歷史樣本數較多時，統計結果通常較容易判讀；此設定只是研究提示，不是買賣門檻。",
        )
        submitted = st.form_submit_button(
            "執行樣本外驗證"
            if scan_mode == oos_dashboard.OOS_VALIDATION_MODE
            else
            "執行多日期歷史回放"
            if scan_mode == swing_dashboard.WALK_FORWARD_REPLAY_MODE
            else "執行歷史回放"
            if scan_mode == swing_dashboard.HISTORICAL_REPLAY_MODE
            else "執行波段掃描"
        )

    normalized_symbols, current_source_context = resolve_swing_research_source(
        source_type=source_type,
        input_symbols=input_symbols,
        watchlist_symbols=watchlist_symbols,
        selected_universe=selected_universe,
    )
    if scan_mode == oos_dashboard.OOS_VALIDATION_MODE:
        current_fingerprint = oos_dashboard.build_oos_validation_request_fingerprint(
            normalized_symbols=normalized_symbols,
            source_type=source_type,
            development_start=development_start_date,
            development_end=development_end_date,
            validation_start=validation_start_date,
            validation_end=validation_end_date,
            holdout_start=holdout_start_date,
            holdout_end=holdout_end_date,
            replay_frequency=frequency_label,
            overlap_policy=overlap_label,
            cooldown_bars=int(cooldown_bars) if cooldown_bars is not None else None,
            historical_start_date=historical_start_date,
            minimum_resolved_samples=int(preferred_sample_minimum),
        )
    else:
        current_fingerprint = swing_dashboard.build_swing_research_fingerprint(
            normalized_symbols=normalized_symbols,
            source_type=source_type,
            scan_mode=scan_mode,
            replay_date=replay_date,
            frequency=frequency_label,
            signal_id=TECHNICAL_EXAMPLE_SIGNAL_V1.id,
            outcome_id=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id,
            overlap_policy=overlap_label,
            cooldown_bars=int(cooldown_bars) if cooldown_bars is not None else None,
            start_date=start_date,
            end_date=end_date,
            historical_start_date=historical_start_date,
            preferred_sample_minimum=int(preferred_sample_minimum),
        )

    with st.expander("查看篩選條件", expanded=False):
        st.write(f"篩選規則：{get_signal_definition_label(TECHNICAL_EXAMPLE_SIGNAL_V1.id)}")
        signal_rows = [
            {
                "條件": get_technical_metric_label(condition.metric),
                "Operator": condition.operator.value,
                "Expected / Secondary": get_technical_metric_label(condition.secondary_metric) if condition.secondary_metric else swing_dashboard.format_raw_value(condition.value),
            }
            for condition in TECHNICAL_EXAMPLE_SIGNAL_V1.conditions
        ]
        st.dataframe(signal_rows, width="stretch", hide_index=True)
        st.write(f"歷史研究目標：{get_outcome_definition_label(RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id)}")
        st.caption("20 個交易日內突破前 60 日高點。")
        st.caption("本掃描目前只包含技術條件；基本面條件尚未納入這個掃描器。")
        st.caption("歷史命中率必須和已解析歷史樣本數一起閱讀；它不是未來上漲機率。")
        if scan_mode == swing_dashboard.HISTORICAL_REPLAY_MODE:
            st.caption("歷史回放只使用回放日期當下可取得的價格歷史與已知歷史結果統計產生研究排序。回放日期之後資料只用於事後驗證。")
        if scan_mode == swing_dashboard.WALK_FORWARD_REPLAY_MODE:
            st.caption("多日期歷史回放會依頻率重複執行單日期歷史回放。候選出現次數是重複觀察，不是獨立樣本，也不是績效評分。")
        if scan_mode == oos_dashboard.OOS_VALIDATION_MODE:
            st.caption("三段期間使用相同固定研究規格；保留樣本期間不參與規則建立與調整。")
            st.caption(oos_dashboard.HISTORICAL_HIT_RATE_CAPTION)
            st.caption(oos_dashboard.OUTCOME_CAPTION)
            st.caption(oos_dashboard.CANDIDATE_SHARE_CAPTION)
        with st.expander("開發者資訊", expanded=False):
            st.write(f"Signal Definition ID：{TECHNICAL_EXAMPLE_SIGNAL_V1.id}")
            st.write(f"Outcome Definition ID：{RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id}")
            st.write(f"Overlap Policy ID：{overlap_label}")

    if overlap_label == "ALLOW_ALL":
        st.info("保留全部訊號：可能包含同一段行情中的重複事件。")
    else:
        st.info("訊號間隔限制：會減少彼此相近的重複事件，但不代表事件完全獨立。")

    if submitted:
        if not normalized_symbols:
            if scan_mode == oos_dashboard.OOS_VALIDATION_MODE:
                st.session_state["oos_validation_result"] = None
                st.session_state["oos_validation_fingerprint"] = None
                st.session_state["oos_validation_source_context"] = None
            else:
                st.session_state["swing_research_result"] = None
                st.session_state["swing_research_config_fingerprint"] = None
            if source_type == universe_ui.SAVED_UNIVERSE_SOURCE:
                error_message = "股票池目前沒有股票。"
            elif source_type == universe_ui.WATCHLIST_SOURCE:
                error_message = "觀察清單目前沒有股票。"
            else:
                error_message = "請輸入至少一個股票代號。"
            if scan_mode == oos_dashboard.OOS_VALIDATION_MODE:
                st.session_state["oos_validation_last_error"] = error_message
            else:
                st.session_state["swing_research_last_error"] = error_message
                st.session_state["swing_research_price_series_by_symbol"] = {}
                st.session_state["swing_research_source_context"] = None
        else:
            try:
                if scan_mode == oos_dashboard.OOS_VALIDATION_MODE:
                    config = OutOfSampleValidationConfig(
                        signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
                        outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
                        development_period=ValidationPeriod(
                            role=ValidationPeriodRole.DEVELOPMENT,
                            start_date=development_start_date,
                            end_date=development_end_date,
                        ),
                        validation_period=ValidationPeriod(
                            role=ValidationPeriodRole.VALIDATION,
                            start_date=validation_start_date,
                            end_date=validation_end_date,
                        ),
                        holdout_period=ValidationPeriod(
                            role=ValidationPeriodRole.HOLDOUT,
                            start_date=holdout_start_date,
                            end_date=holdout_end_date,
                        ),
                        replay_frequency=WalkForwardReplayFrequency(frequency_label),
                        overlap_policy=OverlappingSignalPolicy(overlap_label),
                        cooldown_bars=int(cooldown_bars) if cooldown_bars is not None else None,
                        historical_start_date=historical_start_date,
                        minimum_resolved_samples=int(preferred_sample_minimum),
                    )
                    with st.spinner("正在執行樣本外驗證..."):
                        scan_payload = build_oos_validation_result(
                            symbols=normalized_symbols,
                            config=config,
                            source_type=source_type,
                        )
                    st.session_state["oos_validation_result"] = scan_payload["result"]
                    st.session_state["oos_validation_fingerprint"] = scan_payload["fingerprint"]
                    st.session_state["oos_validation_source_context"] = oos_dashboard.build_source_context_copy(current_source_context)
                    st.session_state["oos_validation_last_error"] = None
                elif scan_mode == swing_dashboard.HISTORICAL_REPLAY_MODE:
                    config = HistoricalReplayConfig(
                        replay_date=replay_date,
                        signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
                        outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
                        overlap_policy=OverlappingSignalPolicy(overlap_label),
                        cooldown_bars=int(cooldown_bars) if cooldown_bars is not None else None,
                        historical_start_date=start_date,
                        preferred_resolved_samples=int(preferred_sample_minimum),
                    )
                    with st.spinner("正在執行歷史回放..."):
                        scan_payload = build_swing_research_replay_result(
                            symbols=normalized_symbols,
                            config=config,
                            source_type=source_type,
                        )
                elif scan_mode == swing_dashboard.WALK_FORWARD_REPLAY_MODE:
                    config = WalkForwardReplayConfig(
                        start_date=walk_forward_start_date,
                        end_date=walk_forward_end_date,
                        frequency=WalkForwardReplayFrequency(frequency_label),
                        signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
                        outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
                        overlap_policy=OverlappingSignalPolicy(overlap_label),
                        cooldown_bars=int(cooldown_bars) if cooldown_bars is not None else None,
                        historical_start_date=historical_start_date,
                        preferred_resolved_samples=int(preferred_sample_minimum),
                    )
                    with st.spinner("正在執行多日期歷史回放..."):
                        scan_payload = build_swing_research_walk_forward_result(
                            symbols=normalized_symbols,
                            config=config,
                            source_type=source_type,
                        )
                else:
                    config = SwingScannerConfig(
                        signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
                        outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
                        overlap_policy=OverlappingSignalPolicy(overlap_label),
                        cooldown_bars=int(cooldown_bars) if cooldown_bars is not None else None,
                        backtest_start_date=start_date,
                        backtest_end_date=end_date,
                        minimum_resolved_samples=int(preferred_sample_minimum),
                    )
                    with st.spinner("正在執行 Swing Scanner..."):
                        scan_payload = build_swing_research_scan_result(
                            symbols=normalized_symbols,
                            config=config,
                            source_type=source_type,
                        )
                    st.session_state["swing_research_result"] = scan_payload["result"]
                    st.session_state["swing_research_config_fingerprint"] = scan_payload["fingerprint"]
                    st.session_state["swing_research_price_series_by_symbol"] = scan_payload["price_series_by_symbol"]
                    st.session_state["swing_research_source_context"] = current_source_context
                    st.session_state["swing_research_result_mode"] = scan_mode
                    st.session_state["swing_research_replay_date"] = replay_date
                    st.session_state["swing_research_last_error"] = None
            except (OutOfSampleValidationError, Exception) as error:
                if scan_mode == oos_dashboard.OOS_VALIDATION_MODE:
                    st.session_state["oos_validation_result"] = None
                    st.session_state["oos_validation_fingerprint"] = None
                    st.session_state["oos_validation_source_context"] = None
                    st.session_state["oos_validation_last_error"] = safe_error_message(error)
                else:
                    st.session_state["swing_research_result"] = None
                    st.session_state["swing_research_config_fingerprint"] = None
                    st.session_state["swing_research_price_series_by_symbol"] = {}
                    st.session_state["swing_research_source_context"] = None
                    st.session_state["swing_research_last_error"] = safe_error_message(error)

    if st.button("清除掃描結果"):
        for key in list(st.session_state.keys()):
            if key.startswith("swing_research_"):
                st.session_state[key] = {} if key == "swing_research_price_series_by_symbol" else None
    if st.button("清除樣本外驗證結果"):
        for key in list(st.session_state.keys()):
            if key.startswith("oos_validation_"):
                st.session_state[key] = None

    if st.session_state["swing_research_last_error"]:
        st.error(f"Swing Research 掃描失敗：{st.session_state['swing_research_last_error']}")

    if st.session_state["oos_validation_last_error"]:
        st.error(f"樣本外驗證失敗：{st.session_state['oos_validation_last_error']}")

    if scan_mode == oos_dashboard.OOS_VALIDATION_MODE:
        result = st.session_state["oos_validation_result"]
        if result is None:
            st.info("設定三段 period 並按下「執行樣本外驗證」後，系統才會讀取完整 historical price series 並執行 OOS validation。")
            return
        if oos_dashboard.stored_result_is_stale(st.session_state["oos_validation_fingerprint"], current_fingerprint):
            st.warning(oos_dashboard.STORED_RESULT_MISMATCH_MESSAGE)
        render_oos_validation_result(
            result,
            st.session_state.get("oos_validation_source_context"),
        )
        return

    result = st.session_state["swing_research_result"]
    if result is None:
        st.info("輸入股票池並按下「執行波段掃描」後，系統才會讀取 historical price、建立 technical indicators、評估 current signal 並執行 matched backtests。")
        return

    if st.session_state["swing_research_config_fingerprint"] != current_fingerprint:
        stored_mode = st.session_state.get("swing_research_result_mode")
        if stored_mode and stored_mode != scan_mode:
            st.warning(f"stored result came from {stored_mode} mode；若要更新，請重新執行目前模式。")
        else:
            st.warning("目前結果來自上一組設定；若要更新，請重新按「執行波段掃描」。")

    if st.session_state.get("swing_research_result_mode") == swing_dashboard.WALK_FORWARD_REPLAY_MODE:
        render_swing_research_walk_forward_result(
            result,
            st.session_state.get("swing_research_source_context"),
        )
    elif st.session_state.get("swing_research_result_mode") == swing_dashboard.HISTORICAL_REPLAY_MODE:
        render_swing_research_replay_result(
            result,
            st.session_state.get("swing_research_source_context"),
        )
    else:
        render_swing_research_result(
            result,
            st.session_state.get("swing_research_source_context"),
        )


def resolve_swing_research_source(
    *,
    source_type: str,
    input_symbols: str,
    watchlist_symbols: list[str],
    selected_universe,
) -> tuple[tuple[str, ...], dict[str, object]]:
    if source_type == universe_ui.WATCHLIST_SOURCE:
        symbols = tuple(watchlist_symbols)
        return symbols, universe_ui.build_source_context(
            source_type=source_type,
            symbols=symbols,
        )
    if source_type == universe_ui.SAVED_UNIVERSE_SOURCE and selected_universe is not None:
        symbols = selected_universe.symbols
        return symbols, universe_ui.build_source_context(
            source_type=source_type,
            symbols=symbols,
            universe_id=selected_universe.id,
            universe_name=selected_universe.name,
        )

    symbols = swing_dashboard.parse_swing_symbol_input(input_symbols)
    return symbols, universe_ui.build_source_context(
        source_type=universe_ui.MANUAL_SOURCE,
        symbols=symbols,
    )


def render_oos_validation_result(result, source_context=None) -> None:
    st.markdown("### 樣本外驗證")
    st.caption(oos_dashboard.HISTORICAL_HIT_RATE_CAPTION)
    st.caption(oos_dashboard.OUTCOME_CAPTION)
    st.caption(oos_dashboard.CANDIDATE_SHARE_CAPTION)

    if source_context:
        st.caption(
            "股票來源："
            f"{universe_ui.source_display_name(source_type=source_context['source_type'], universe_name=source_context.get('source_universe_name'))} · "
            f"股票數：{source_context['symbol_count']}"
        )
        with st.expander("來源股票清單", expanded=False):
            st.write("\n".join(source_context.get("symbols", tuple())) or "N/A")

    spec_cols = st.columns(2)
    spec_cols[0].metric("研究規格識別碼", result.research_fingerprint)
    spec_cols[1].metric(
        "三個期間是否使用相同研究規則",
        "是" if result.all_periods_same_fingerprint else "否",
    )
    st.caption("畫面請求識別碼只用於判斷目前設定是否和畫面結果相同；研究規格識別碼來自固定研究規格。")

    with st.expander("開發者資訊：固定研究規格", expanded=False):
        spec = result.frozen_specification
        st.dataframe(
            pd.DataFrame([
                {"Metric": "Signal ID", "Value": spec.signal_definition.id},
                {"Metric": "Outcome ID", "Value": spec.outcome_definition.id},
                {"Metric": "Replay Frequency", "Value": spec.replay_frequency.value},
                {"Metric": "Overlap Policy", "Value": spec.overlap_policy.value},
                {"Metric": "Cooldown Bars", "Value": swing_dashboard.format_optional_number(spec.cooldown_bars)},
                {"Metric": "Historical Start", "Value": swing_dashboard.format_date(spec.historical_start_date)},
                {"Metric": "Preferred Resolved Samples", "Value": spec.minimum_resolved_samples},
            ]).astype(str),
            width="stretch",
            hide_index=True,
        )

    st.markdown("#### 期間摘要")
    for period_result in oos_dashboard.ordered_period_results(result):
        with st.container(border=True):
            st.subheader(oos_dashboard.period_label(period_result))
            if period_result.role is ValidationPeriodRole.HOLDOUT:
                st.caption(oos_dashboard.HOLDOUT_CAPTION)
            metric_cols = st.columns(3)
            metric_cols[0].metric("日期範圍", f"{oos_dashboard.format_date(period_result.start_date)} -> {oos_dashboard.format_date(period_result.end_date)}")
            metric_cols[1].metric("回放期數", period_result.requested_replay_period_count)
            metric_cols[2].metric("候選出現期間比例", oos_dashboard.format_candidate_period_share(period_result))
            hit_cols = st.columns(3)
            hit_cols[0].metric("歷史命中率", oos_dashboard.format_percentage(period_result.historical_hit_rate))
            hit_cols[1].metric("已解析樣本", period_result.resolved_count)
            hit_cols[2].metric("候選出現次數", period_result.total_candidate_occurrences)
            if period_result.resolved_count < result.config.minimum_resolved_samples:
                st.warning(oos_dashboard.SMALL_SAMPLE_WARNING)
            st.dataframe(
                pd.DataFrame(oos_dashboard.build_period_summary_rows(period_result)).astype(str),
                width="stretch",
                hide_index=True,
            )

    st.markdown("#### 跨期間比較")
    st.dataframe(
        pd.DataFrame(oos_dashboard.build_cross_period_comparison_rows(result)).astype(str),
        width="stretch",
        hide_index=True,
    )
    st.caption("差異欄位是原始差值；百分比指標使用百分點，不是相對變化。")

    observations = oos_dashboard.build_factual_observations(result)
    if observations:
        st.markdown("#### 事實觀察")
        for observation in observations:
            st.write(f"- {observation}")

    chart_rows = oos_dashboard.build_candidate_count_chart_rows(result)
    if chart_rows:
        st.markdown("#### 各回放期間候選數")
        chart_df = pd.DataFrame(chart_rows)
        chart = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                x=alt.X("Replay Date:N", title="回放日期"),
                y=alt.Y("Candidate Count:Q", title="候選數"),
                color=alt.Color("Validation Role:N", title="驗證期間"),
                tooltip=["Validation Role", "Replay Date", "Candidate Count", "HIT", "MISS", "INCOMPLETE", "NOT_EVALUABLE", "FAILED"],
            )
        )
        st.altair_chart(chart, width="stretch")
    else:
        st.info("此驗證結果沒有可顯示的回放日期。")

    share_df = pd.DataFrame(oos_dashboard.build_candidate_share_chart_rows(result))
    if not share_df.empty:
        st.markdown("#### 各驗證期間候選出現期間比例")
        share_chart = (
            alt.Chart(share_df)
            .mark_bar()
            .encode(
                x=alt.X("Validation Role:N", title="驗證期間"),
                y=alt.Y("Candidate Period Share:Q", title="候選出現期間比例", axis=alt.Axis(format="%")),
                tooltip=["Validation Role", "Candidate Period Share Label"],
            )
        )
        st.altair_chart(share_chart, width="stretch")

    hit_rate_df = pd.DataFrame(oos_dashboard.build_historical_hit_rate_chart_rows(result))
    hit_rate_df = hit_rate_df.dropna(subset=["Historical Hit Rate"])
    if not hit_rate_df.empty:
        st.markdown("#### 歷史命中率與已解析樣本")
        hit_rate_chart = (
            alt.Chart(hit_rate_df)
            .mark_bar()
            .encode(
                x=alt.X("Validation Role:N", title="驗證期間"),
                y=alt.Y("Historical Hit Rate:Q", title="歷史命中率", axis=alt.Axis(format="%")),
                tooltip=["Label", "Resolved n"],
            )
        )
        st.altair_chart(hit_rate_chart, width="stretch")

    st.markdown("#### 歷史結果統計")
    st.dataframe(
        pd.DataFrame(oos_dashboard.build_outcome_count_rows(result)).astype(str),
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### 跨期間股票出現情形")
    symbol_presence_rows = oos_dashboard.build_cross_period_symbol_presence_rows(result)
    if symbol_presence_rows:
        st.dataframe(pd.DataFrame(symbol_presence_rows).astype(str), width="stretch", hide_index=True)
    else:
        st.info("三段期間都沒有候選股票。")

    for period_result in oos_dashboard.ordered_period_results(result):
        with st.expander(f"{oos_dashboard.period_label(period_result)} 候選穩定性", expanded=False):
            symbol_rows = oos_dashboard.build_period_symbol_rows(period_result)
            if symbol_rows:
                st.dataframe(pd.DataFrame(symbol_rows).astype(str), width="stretch", hide_index=True)
            else:
                st.info("此期間沒有候選股票。")
            timeline_rows = oos_dashboard.build_period_timeline_rows(period_result)
            if timeline_rows:
                st.dataframe(pd.DataFrame(timeline_rows).astype(str), width="stretch", hide_index=True)
            else:
                st.info("此期間沒有回放日期。")

    failure_rows = oos_dashboard.build_failure_summary_rows(result)
    if failure_rows:
        with st.expander("安全錯誤摘要", expanded=False):
            st.dataframe(pd.DataFrame(failure_rows).astype(str), width="stretch", hide_index=True)


def render_swing_research_result(result, source_context=None) -> None:
    st.markdown("### 掃描結果摘要")
    if source_context:
        st.caption(
            "股票來源："
            f"{universe_ui.source_display_name(source_type=source_context['source_type'], universe_name=source_context.get('source_universe_name'))} · "
            f"掃描股票數：{source_context['symbol_count']}"
        )
    st.caption(
        f"輸入股票數：{len(result.requested_symbols)} · "
        f"有效股票數：{len(result.normalized_symbols)}"
    )
    st.caption("符合條件：目前符合「波段技術篩選 V1」。不符合條件：目前至少有一項篩選條件未達標，不代表看跌。資料不足：目前無法取得足夠資料完成判斷。掃描失敗：取得資料或計算過程發生錯誤。")
    summary_cols = st.columns(5)
    for col, row in zip(summary_cols, swing_dashboard.build_scan_summary_rows(result)):
        col.metric(row["Metric"], row["Value"])

    if result.failed_symbols:
        with st.expander("掃描失敗的股票", expanded=False):
            st.dataframe(swing_dashboard.build_failure_rows(result), width="stretch", hide_index=True)

    if result.no_match_count:
        with st.expander("不符合條件的股票", expanded=False):
            rows = swing_dashboard.build_no_match_rows(result)
            if rows:
                st.dataframe(rows, width="stretch", hide_index=True)
            else:
                st.dataframe({"股票": list(result.no_match_symbols)}, width="stretch", hide_index=True)

    if result.not_evaluable_count:
        with st.expander("資料不足", expanded=False):
            st.dataframe(swing_dashboard.build_not_evaluable_rows(result), width="stretch", hide_index=True)

    st.markdown("### 符合條件的研究候選")
    with st.expander("研究優先順序如何排列", expanded=False):
        st.caption("Research Ranking Policy: swing_research_rank_v1")
        st.write(swing_dashboard.RESEARCH_RANKING_EXPLANATION)
        st.caption("研究優先順序是研究檢視順序，不是推薦、預測或交易排序。")

    candidate_rows = swing_dashboard.build_candidate_table_rows(result.matched_candidates)
    st.dataframe(candidate_rows, width="stretch", hide_index=True)

    if result.matched_count == 0:
        st.info("目前沒有股票符合這組篩選條件。")
        st.caption("這不代表股票看跌，只代表目前未符合波段技術篩選 V1。")
        return

    candidate_labels = [
        swing_dashboard.candidate_selector_label(candidate)
        for candidate in result.matched_candidates
    ]
    selected_label = st.selectbox("選擇研究候選", candidate_labels)
    selected_candidate = result.matched_candidates[candidate_labels.index(selected_label)]
    render_swing_candidate_detail(selected_candidate)


def render_swing_candidate_detail(candidate) -> None:
    st.markdown("### 研究候選明細")
    if candidate.source_price_is_stale:
        st.warning("歷史價格資料來自過期快取。")
    if candidate.is_provisional_possible:
        st.caption("若交易日尚未結束，最新日線資料可能仍是暫定值。")

    st.markdown("#### 目前篩選結果")
    signal_cols = st.columns(3)
    signal_cols[0].metric("最新交易日", swing_dashboard.format_date(candidate.latest_trading_date))
    current_features = getattr(candidate, "current_" + "snap" + "shot")
    signal_cols[1].metric("分析價格", f"{current_features.analysis_close:,.2f}")
    signal_cols[2].metric("篩選狀態", get_signal_status_label(candidate.signal_match.status.value))

    if not swing_dashboard.current_match_trace_is_consistent(candidate.signal_match):
        st.error("目前篩選條件明細與符合狀態不一致。")
    st.dataframe(
        swing_dashboard.build_condition_trace_rows(candidate.signal_match),
        width="stretch",
        hide_index=True,
    )

    with st.expander("目前技術指標", expanded=False):
        st.dataframe(
            getattr(swing_dashboard, "build_technical_" + "snap" + "shot_rows")(current_features),
            width="stretch",
            hide_index=True,
        )

    st.markdown("#### 歷史驗證資料")
    context_cols = st.columns(4)
    context_cols[0].metric("歷史命中率", swing_dashboard.format_percentage(candidate.historical_hit_rate), help="過去符合相同條件且已解析的歷史事件中，達成指定研究目標的比例。不是未來上漲機率。")
    context_cols[1].metric("已解析歷史樣本數", f"n = {candidate.resolved_count}", help="已能判定 HIT 或 MISS 的歷史案例數。")
    context_cols[2].metric("HIT", candidate.hit_count)
    context_cols[3].metric("MISS", candidate.miss_count)
    st.caption(swing_dashboard.HISTORICAL_HIT_RATE_CAPTION)

    detail_cols = st.columns(4)
    detail_cols[0].metric("觀察期間尚未完整", candidate.incomplete_count)
    detail_cols[1].metric("無法判定", candidate.not_evaluable_count)
    detail_cols[2].metric("原始訊號數", candidate.raw_signal_count)
    detail_cols[3].metric("已評估訊號數", candidate.filtered_signal_count)
    st.caption(
        f"歷史驗證範圍：{swing_dashboard.format_date(candidate.backtest_start_date)} -> "
        f"{swing_dashboard.format_date(candidate.backtest_end_date)} · "
        f"歷史訊號樣本處理方式：{get_overlap_policy_label(candidate.overlap_policy.value)} · "
        f"訊號間隔交易日數：{format_optional_int(candidate.cooldown_bars)}"
    )

    return_cols = st.columns(4)
    return_cols[0].metric("最大有利變動（MFE）中位數", swing_dashboard.format_percentage(candidate.median_max_close_return), help="訊號後指定觀察期間內，分析價格曾出現的最大有利變動。")
    return_cols[1].metric("最大不利變動（MAE）中位數", swing_dashboard.format_percentage(candidate.median_max_adverse_return), help="訊號後指定觀察期間內，分析價格曾出現的最大不利變動。")
    return_cols[2].metric("觀察期末變動中位數", swing_dashboard.format_percentage(candidate.median_end_return), help="指定觀察期間結束時，相對訊號日分析價格的變動。")
    return_cols[3].metric("中位達標交易日數", swing_dashboard.format_optional_number(candidate.median_hit_bar_index))
    average_cols = st.columns(4)
    average_cols[0].metric("最大有利變動平均", swing_dashboard.format_percentage(candidate.average_max_close_return))
    average_cols[1].metric("最大不利變動平均", swing_dashboard.format_percentage(candidate.average_max_adverse_return))
    average_cols[2].metric("觀察期末變動平均", swing_dashboard.format_percentage(candidate.average_end_return))
    average_cols[3].metric("平均達標交易日數", swing_dashboard.format_optional_number(candidate.average_hit_bar_index))

    if (
        candidate.historical_hit_rate is not None
        and candidate.historical_hit_rate >= 0.7
        and candidate.median_end_return is not None
        and candidate.median_end_return < 0
    ):
        st.info(
            "目標事件可能在觀察期間結束前發生；HIT 不代表觀察期末變動一定為正。"
        )

    render_swing_case_preview(candidate)


def render_swing_research_replay_result(result, source_context=None) -> None:
    st.markdown("### 歷史回放")
    st.caption(
        f"指定回放日期：{swing_dashboard.format_date(result.config.replay_date)}"
    )
    st.caption(
        "歷史回放只使用回放日期當下可取得的價格歷史與已知歷史結果統計產生研究排序。"
        "回放日期之後的資料只用於事後驗證，沒有用於產生當時的篩選結果。"
    )
    if source_context:
        st.caption(
            "股票來源："
            f"{universe_ui.source_display_name(source_type=source_context['source_type'], universe_name=source_context.get('source_universe_name'))} · "
            f"掃描股票數：{source_context['symbol_count']}"
        )
    st.caption(
        f"輸入股票數：{len(result.requested_symbols)} · "
        f"有效股票數：{len(result.normalized_symbols)}"
    )
    summary_cols = st.columns(5)
    for col, row in zip(summary_cols, swing_dashboard.build_replay_summary_rows(result)):
        col.metric(row["Metric"], row["Value"])

    if result.failed_symbols:
        with st.expander("掃描失敗的股票", expanded=False):
            rows = [
                {
                    "股票": failure.symbol,
                    "Safe Error Type": failure.error_type,
                    "Safe Message": failure.message,
                }
                for failure in result.failed_symbols
            ]
            st.dataframe(rows, width="stretch", hide_index=True)

    if result.no_match_count:
        with st.expander("不符合條件的股票", expanded=False):
            rows = [
                {
                    "股票": detail.symbol,
                    "實際使用交易日": swing_dashboard.format_date(detail.actual_signal_date),
                    "未符合的條件": format_condition_labels(detail.failed_conditions),
                }
                for detail in result.no_match_details
            ]
            st.dataframe(rows, width="stretch", hide_index=True)

    if result.not_evaluable_count:
        with st.expander("資料不足", expanded=False):
            rows = [
                {
                    "股票": detail.symbol,
                    "指定回放日期": swing_dashboard.format_date(detail.requested_replay_date),
                    "實際使用交易日": swing_dashboard.format_date(detail.actual_signal_date),
                    "原因": detail.reason or format_condition_labels(detail.missing_required_features),
                }
                for detail in result.not_evaluable_symbols
            ]
            st.dataframe(rows, width="stretch", hide_index=True)

    st.markdown("### 回放研究候選")
    with st.expander("研究優先順序如何排列", expanded=False):
        st.caption("Research Ranking Policy: swing_research_rank_v1")
        st.write(swing_dashboard.RESEARCH_RANKING_EXPLANATION)
        st.caption("回放排序只使用當時可知的歷史統計；回放日期後的實際歷史結果不參與排序。")
    st.dataframe(
        swing_dashboard.build_replay_candidate_table_rows(result.match_candidates),
        width="stretch",
        hide_index=True,
    )

    if result.matched_count == 0:
        st.info("此回放日期下沒有股票符合這組篩選條件。")
        return

    candidate_labels = [
        swing_dashboard.replay_candidate_selector_label(candidate)
        for candidate in result.match_candidates
    ]
    selected_label = st.selectbox("選擇回放研究候選", candidate_labels)
    selected_candidate = result.match_candidates[candidate_labels.index(selected_label)]
    render_swing_replay_candidate_detail(selected_candidate, result.config)


def render_swing_research_walk_forward_result(result, source_context=None) -> None:
    st.markdown("### 多日期歷史回放")
    st.caption(
        f"回放範圍：{swing_dashboard.format_date(result.config.start_date)} -> "
        f"{swing_dashboard.format_date(result.config.end_date)} · "
        f"回放頻率：{get_frequency_label(result.config.frequency.value)}"
    )
    st.caption(
        "同一股票可能在相鄰回放期間重複出現，因此候選出現次數並非獨立統計樣本。"
        "本頁只顯示出現次數，不顯示整體命中率或機率。"
    )
    if source_context:
        st.caption(
            "股票來源："
            f"{universe_ui.source_display_name(source_type=source_context['source_type'], universe_name=source_context.get('source_universe_name'))} · "
            f"掃描股票數：{source_context['symbol_count']}"
        )

    st.markdown("### 回放穩定性分析")
    summary_rows = swing_dashboard.build_walk_forward_summary_rows(result)
    summary_cols = st.columns(3)
    for col, row in zip(summary_cols, summary_rows):
        col.metric(row["Metric"], row["Value"])
    for col, row in zip(summary_cols, summary_rows[3:]):
        col.metric(row["Metric"], row["Value"])
    st.caption("候選出現期間比例代表有出現至少一個研究候選的回放期間比例，不是未來發生機率。")

    with st.expander("回放後歷史結果統計", expanded=False):
        st.caption("回放後歷史結果是事後驗證資訊，不參與回放當時的研究優先順序，也不代表策略報酬或未來機率。")
        st.dataframe(
            swing_dashboard.build_walk_forward_outcome_count_rows(result),
            width="stretch",
            hide_index=True,
        )

    st.markdown("#### 候選出現次數")
    st.dataframe(
        swing_dashboard.build_walk_forward_symbol_summary_rows(result),
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### 回放期間時間線")
    st.dataframe(
        swing_dashboard.build_walk_forward_timeline_rows(result),
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### 候選名單穩定性")
    st.dataframe(
        swing_dashboard.build_replay_analytics_candidate_set_rows(result),
        width="stretch",
        hide_index=True,
    )

    if not result.period_results:
        st.info("此多日期歷史回放沒有可顯示的回放期間。")
        return

    labels = [
        swing_dashboard.walk_forward_period_selector_label(period)
        for period in result.period_results
    ]
    selected_label = st.selectbox("選擇回放期間", labels)
    selected_period = result.period_results[labels.index(selected_label)]
    if selected_period.failure is not None:
        st.warning(
            "此回放期間執行失敗："
            f"{selected_period.failure.error_type} - {selected_period.failure.safe_message}"
        )
        return
    if selected_period.replay_result is None:
        st.info("此回放期間沒有結果。")
        return
    if selected_period.matched_count == 0:
        st.info("此回放期間沒有符合條件的股票。")
    render_swing_research_replay_result(selected_period.replay_result, source_context)


def render_swing_replay_candidate_detail(candidate, config: HistoricalReplayConfig) -> None:
    st.markdown("### 回放候選明細")
    if candidate.source_price_is_stale:
        st.warning("歷史價格資料來自過期快取。")

    st.markdown("#### 回放當時篩選結果")
    replay_features = getattr(candidate, "technical_" + "snap" + "shot")
    signal_cols = st.columns(4)
    signal_cols[0].metric("指定回放日期", swing_dashboard.format_date(candidate.requested_replay_date))
    signal_cols[1].metric("實際使用交易日", swing_dashboard.format_date(candidate.actual_signal_date))
    signal_cols[2].metric("分析價格", f"{replay_features.analysis_close:,.2f}")
    signal_cols[3].metric("篩選狀態", get_signal_status_label(candidate.signal_match.status.value))
    st.dataframe(
        swing_dashboard.build_condition_trace_rows(candidate.signal_match),
        width="stretch",
        hide_index=True,
    )

    with st.expander("回放當時技術指標", expanded=False):
        st.dataframe(
            getattr(swing_dashboard, "build_technical_" + "snap" + "shot_rows")(replay_features),
            width="stretch",
            hide_index=True,
        )

    st.markdown("#### 回放當時可知歷史資料")
    summary = candidate.point_in_time_backtest_summary
    context_cols = st.columns(4)
    context_cols[0].metric("回放當時可知歷史命中率", swing_dashboard.format_percentage(summary.historical_hit_rate_as_of))
    context_cols[1].metric("回放當時可知已解析樣本數", f"n = {summary.resolved_as_of_count}")
    context_cols[2].metric("HIT As Of", summary.hit_as_of_count)
    context_cols[3].metric("MISS As Of", summary.miss_as_of_count)
    st.caption("回放當時可知歷史命中率不是未來機率。")

    return_cols = st.columns(4)
    return_cols[0].metric("回放當時可知中位最大有利變動", swing_dashboard.format_percentage(summary.median_max_close_return_as_of))
    return_cols[1].metric("回放當時可知中位最大不利變動", swing_dashboard.format_percentage(summary.median_max_adverse_return_as_of))
    return_cols[2].metric("回放當時可知期末中位變動", swing_dashboard.format_percentage(summary.median_end_return_as_of))
    return_cols[3].metric("回放當時可知中位達標交易日數", swing_dashboard.format_optional_number(summary.median_hit_bar_index_as_of))

    st.markdown("#### 回放日期之後的實際歷史結果")
    st.caption("以下資料只用於歷史事後驗證，沒有用於產生當時訊號或排序。")
    st.dataframe(
        swing_dashboard.post_replay_outcome_rows(candidate),
        width="stretch",
        hide_index=True,
    )
    render_swing_replay_outcome_chart(candidate, config)


def render_swing_replay_outcome_chart(candidate, config: HistoricalReplayConfig) -> None:
    price_series_by_symbol = st.session_state.get("swing_research_price_series_by_symbol", {})
    price_series = price_series_by_symbol.get(candidate.symbol)
    if price_series is None:
        st.warning("Replay outcome chart unavailable: scan-time price series cache is missing.")
        return

    signal_raw_close = None
    for bar in price_series.bars:
        if bar.trading_date == candidate.actual_signal_date:
            signal_raw_close = bar.close
            break
    signal_event = build_signal_event(
        candidate.signal_match,
        signal_raw_close=signal_raw_close,
    )
    case = HistoricalBacktestCase(
        symbol=candidate.symbol,
        signal_event=signal_event,
        outcome=candidate.post_replay_outcome,
        case_id=build_case_id(candidate.symbol, signal_event, candidate.post_replay_outcome),
    )
    report = aggregate_backtest_cases(
        (case,),
        symbol=candidate.symbol,
        config=config.to_backtest_config(actual_signal_date=candidate.actual_signal_date),
        raw_events=(signal_event,),
        evaluated_events=(signal_event,),
    )
    try:
        case_view = build_historical_case_views(
            price_series,
            report,
            HistoricalCaseWindowConfig(pre_signal_bars=60, post_signal_bars=config.outcome_definition.horizon_bars),
        )[0]
    except HistoricalCaseDataError as error:
        st.warning(str(error))
        return

    st.markdown("#### 回放結果案例圖")
    chart_cols = st.columns(4)
    chart_cols[0].metric("訊號日期", case_view.signal_date.isoformat())
    chart_cols[1].metric("結果狀態", get_outcome_status_label(case_view.outcome_status.value))
    chart_cols[2].metric("首次達標日期", format_date_value(case_view.target_hit_date))
    chart_cols[3].metric("第幾個交易日達標", format_optional_int(case_view.target_hit_bar_index))
    st.altair_chart(build_case_chart(case_view, x_mode="Relative Bars"), use_container_width=True)
    st.caption("圖中 signal date 之後資料只用於歷史事後驗證，沒有用於產生當時訊號。")


def render_swing_case_preview(candidate) -> None:
    st.markdown("#### 歷史案例預覽")
    st.caption(swing_dashboard.CASE_SELECTION_BIAS_CAPTION)
    price_series_by_symbol = st.session_state.get("swing_research_price_series_by_symbol", {})
    try:
        case_views = swing_dashboard.build_case_preview_views(
            candidate=candidate,
            price_series_by_symbol=price_series_by_symbol,
            window_config=HistoricalCaseWindowConfig(pre_signal_bars=60, post_signal_bars=20),
        )
    except HistoricalCaseDataError as error:
        st.warning(str(error))
        st.caption("案例預覽不會在選擇候選時重新抓取資料；請重新執行掃描以重建掃描時的價格快取。")
        return

    count_cols = st.columns(3)
    for col, row in zip(count_cols, swing_dashboard.build_case_preview_count_rows(case_views)):
        col.metric(row["Metric"], row["Value"])

    status_filter = st.selectbox("案例篩選", swing_dashboard.CASE_PREVIEW_FILTER_OPTIONS)
    filtered_cases = swing_dashboard.filter_case_preview_views(case_views, status_filter)
    preview_cases = swing_dashboard.latest_case_preview_rows(filtered_cases)
    st.dataframe(build_case_summary_rows(preview_cases), width="stretch", hide_index=True)

    if not preview_cases:
        st.info("目前篩選條件下沒有歷史案例。")
        return

    selected_labels = [case_selector_label(case) for case in preview_cases]
    selected_case_label = st.selectbox("選擇歷史案例圖", selected_labels)
    selected_case = preview_cases[selected_labels.index(selected_case_label)]

    chart_cols = st.columns(4)
    chart_cols[0].metric("訊號日期", selected_case.signal_date.isoformat())
    chart_cols[1].metric("結果狀態", get_outcome_status_label(selected_case.outcome_status.value))
    chart_cols[2].metric("參考高點", format_price_value(selected_case.reference_high, selected_case.currency))
    chart_cols[3].metric("首次達標日期", format_date_value(selected_case.target_hit_date))
    return_cols = st.columns(4)
    return_cols[0].metric("第幾個交易日達標", format_optional_int(selected_case.target_hit_bar_index))
    return_cols[1].metric("最大有利變動", format_percentage_value(selected_case.max_close_return))
    return_cols[2].metric("最大不利變動", format_percentage_value(selected_case.max_adverse_return))
    return_cols[3].metric("觀察期末變動", format_percentage_value(selected_case.end_of_window_return))
    st.altair_chart(build_case_chart(selected_case, x_mode="Relative Bars"), use_container_width=True)
    st.caption("可至「歷史案例」頁面查看更多完整案例線圖。")


def build_historical_case_result(
    *,
    symbol: str,
    overlap_policy: OverlappingSignalPolicy,
    cooldown_bars: int | None,
    start_date,
    end_date,
    pre_signal_bars: int,
    post_signal_bars: int,
    force_refresh: bool = False,
) -> dict:
    price_series = get_historical_prices(symbol, force_refresh=force_refresh)
    technical_series = build_technical_indicator_series(price_series)
    config = BacktestConfig(
        signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
        outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
        overlap_policy=overlap_policy,
        cooldown_bars=cooldown_bars,
        start_date=start_date,
        end_date=end_date,
    )
    report = run_historical_backtest(price_series, technical_series, config)
    window_config = HistoricalCaseWindowConfig(
        pre_signal_bars=pre_signal_bars,
        post_signal_bars=post_signal_bars,
    )
    case_views = build_historical_case_views(price_series, report, window_config)
    fingerprint = build_case_request_fingerprint(
        symbol=price_series.symbol,
        signal_id=report.signal_definition_id,
        outcome_definition_id=report.outcome_definition_id,
        overlap_policy=report.overlap_policy.value,
        cooldown_bars=report.cooldown_bars,
        start_date=report.start_date,
        end_date=report.end_date,
    )
    return {
        "symbol": price_series.symbol,
        "currency": price_series.currency,
        "price_is_stale": price_series.is_stale,
        "report": report,
        "case_views": case_views,
        "fingerprint": fingerprint,
    }


def render_historical_cases() -> None:
    st.header("歷史案例")
    st.caption(
        "歷史案例用來檢視過去符合研究條件後的實際走勢。HIT 代表指定歷史研究目標曾在觀察期間內觸發；"
        "MISS 代表完整觀察期間內沒有觸發。這不是交易損益分類，也不是未來預測。"
    )

    with st.form("historical_case_form"):
        input_symbol = st.text_input(
            "股票",
            placeholder="2454 或 2330",
            key="historical_case_symbol_input",
        )
        st.text_input("篩選規則", value=get_signal_definition_label(TECHNICAL_EXAMPLE_SIGNAL_V1.id), disabled=True, key="historical_case_signal_definition_label")
        st.text_input("歷史研究目標", value=get_outcome_definition_label(RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id), disabled=True, key="historical_case_outcome_definition_label")
        overlap_label = st.selectbox("歷史訊號樣本處理方式", ["ALLOW_ALL", "COOLDOWN"], format_func=get_overlap_policy_label)
        cooldown_bars = None
        if overlap_label == "COOLDOWN":
            cooldown_bars = st.number_input("訊號間隔交易日數", min_value=1, value=20, step=1, key="historical_case_cooldown_bars")
        date_cols = st.columns(2)
        start_date = date_cols[0].date_input("歷史研究開始日期", value=pd.to_datetime("2018-01-01").date(), key="historical_case_start_date")
        end_date = date_cols[1].date_input("歷史研究結束日期", value=pd.to_datetime("2025-12-31").date(), key="historical_case_end_date")
        window_cols = st.columns(2)
        pre_signal_bars = window_cols[0].number_input("訊號前顯示交易日數", min_value=0, value=60, step=5)
        post_signal_bars = window_cols[1].number_input("訊號後顯示交易日數", min_value=0, value=20, step=5)
        force_refresh = st.checkbox("強制重新抓取 Yahoo 資料", value=False)
        with st.expander("開發者資訊", expanded=False):
            st.write(f"Signal Definition ID：{TECHNICAL_EXAMPLE_SIGNAL_V1.id}")
            st.write(f"Outcome Definition ID：{RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id}")
        submitted = st.form_submit_button("建立歷史案例")

    parsed_symbols = parse_stock_symbols(input_symbol)
    current_symbol = parsed_symbols[0] if parsed_symbols else ""
    current_fingerprint = build_case_request_fingerprint(
        symbol=current_symbol,
        signal_id=TECHNICAL_EXAMPLE_SIGNAL_V1.id,
        outcome_definition_id=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id,
        overlap_policy=overlap_label,
        cooldown_bars=int(cooldown_bars) if cooldown_bars is not None else None,
        start_date=start_date,
        end_date=end_date,
    )

    if submitted:
        if not parsed_symbols:
            st.session_state["historical_case_result"] = None
            st.session_state["historical_case_last_error"] = "請輸入至少一個股票代號。"
        else:
            if len(parsed_symbols) > 1:
                st.info(f"歷史案例頁面目前顯示第一支股票：{parsed_symbols[0]}")
            try:
                result = build_historical_case_result(
                    symbol=parsed_symbols[0],
                    overlap_policy=OverlappingSignalPolicy(overlap_label),
                    cooldown_bars=int(cooldown_bars) if cooldown_bars is not None else None,
                    start_date=start_date,
                    end_date=end_date,
                    pre_signal_bars=int(pre_signal_bars),
                    post_signal_bars=int(post_signal_bars),
                    force_refresh=force_refresh,
                )
                st.session_state["historical_case_result"] = result
                st.session_state["historical_case_last_error"] = None
            except (ValueError, BacktestDataError, HistoricalCaseDataError) as error:
                st.session_state["historical_case_result"] = None
                st.session_state["historical_case_last_error"] = str(error)
            except Exception as error:
                st.session_state["historical_case_result"] = None
                st.session_state["historical_case_last_error"] = safe_error_message(error)

    if st.button("清除案例結果"):
        st.session_state["historical_case_result"] = None
        st.session_state["historical_case_last_error"] = None

    if st.session_state["historical_case_last_error"]:
        st.error(f"歷史案例建立失敗：{st.session_state['historical_case_last_error']}")

    result = st.session_state["historical_case_result"]
    if result is None:
        st.info("輸入單一股票並按下「建立歷史案例」後，系統才會讀取價格、建立技術指標、執行歷史驗證，並產生案例檢視。")
        return

    report = result["report"]
    case_views = result["case_views"]
    if result["fingerprint"] != current_fingerprint:
        st.warning("目前顯示的是上一組設定建立的案例結果；若要更新，請重新按「建立歷史案例」。")
    if result["price_is_stale"]:
        st.warning("目前使用過期歷史價格快取；請留意資料新鮮度。")

    st.subheader(f"{result['symbol']} · 歷史案例檢視")
    st.caption("主價格線使用分析價格；參考高點與首次達標使用原始高價基準。")
    st.caption("歷史命中率是歷史條件事件比例，不代表未來上漲機率。MFE、MAE 與觀察期末變動是以收盤價計算的歷史變動指標，不是實際交易報酬。")

    metric_cols = st.columns(5)
    metric_cols[0].metric("歷史命中率", format_percentage_value(report.historical_hit_rate))
    metric_cols[1].metric("已解析案例", report.resolved_count)
    metric_cols[2].metric("HIT", report.hit_count)
    metric_cols[3].metric("MISS", report.miss_count)
    metric_cols[4].metric("觀察期間尚未完整", report.incomplete_count)
    st.caption(
        f"歷史訊號樣本處理方式：{get_overlap_policy_label(report.overlap_policy.value)} · 訊號間隔交易日數：{format_optional_int(report.cooldown_bars)} · "
        f"歷史訊號範圍：{format_date_value(report.start_date)} -> {format_date_value(report.end_date)}"
    )

    if not case_views:
        st.info("此設定在指定期間沒有找到歷史訊號事件。")
        return

    controls = st.columns(3)
    status_filter = controls[0].selectbox(
        "結果狀態",
        STATUS_FILTER_OPTIONS,
        format_func=historical_case_status_filter_label,
    )
    sort_option = controls[1].selectbox("案例排序", SORT_OPTIONS, format_func=historical_case_sort_label)
    x_mode = controls[2].selectbox(
        "圖表 X 軸",
        ["Relative Bars", "Actual Dates"],
        format_func=historical_case_x_mode_label,
    )
    filtered_cases = sort_case_views(filter_case_views(case_views, status_filter), sort_option)
    st.dataframe(build_case_summary_rows(filtered_cases), width="stretch", hide_index=True)

    if not filtered_cases:
        st.info("目前篩選條件下沒有案例。")
        return

    selected_labels = [case_selector_label(case) for case in filtered_cases]
    selected_case_label = st.selectbox("選擇歷史案例", selected_labels)
    selected_case = filtered_cases[selected_labels.index(selected_case_label)]

    top_metrics = st.columns(4)
    top_metrics[0].metric("結果狀態", get_outcome_status_label(selected_case.outcome_status.value))
    top_metrics[1].metric("訊號日期", selected_case.signal_date.isoformat())
    top_metrics[2].metric("參考高點", format_price_value(selected_case.reference_high, selected_case.currency))
    top_metrics[3].metric("首次達標日期", format_date_value(selected_case.target_hit_date))

    return_metrics = st.columns(4)
    return_metrics[0].metric("第幾個交易日達標", format_optional_int(selected_case.target_hit_bar_index))
    return_metrics[1].metric("最大有利變動（MFE）", format_percentage_value(selected_case.max_close_return))
    return_metrics[2].metric("最大不利變動（MAE）", format_percentage_value(selected_case.max_adverse_return))
    return_metrics[3].metric("觀察期末變動", format_percentage_value(selected_case.end_of_window_return))

    if selected_case.outcome_status is OutcomeEvaluationStatus.INCOMPLETE:
        st.warning("觀察期間尚未完整：此案例尚未完整走完研究目標觀察期，不可視為 MISS。")

    st.altair_chart(build_case_chart(selected_case, x_mode=x_mode), use_container_width=True)

    with st.expander("訊號日技術指標", expanded=False):
        st.dataframe(build_technical_summary_rows(selected_case), width="stretch", hide_index=True)

    with st.expander("篩選條件明細", expanded=False):
        st.dataframe(build_condition_detail_rows(selected_case), width="stretch", hide_index=True)


def read_watchlist_for_ui(*, show_error: bool = True) -> list[str]:
    try:
        return list_watchlist()
    except WatchlistDataError as error:
        if show_error:
            st.error(f"觀察清單讀取失敗：{error}")
        return []


def read_universes_for_ui() -> list:
    try:
        return list_universes()
    except UniverseError as error:
        st.error(f"股票池讀取失敗：{error}")
        return []


def render_universe_management() -> None:
    st.header("研究股票池")
    st.caption(universe_ui.UNIVERSE_SEMANTICS_CAPTION)

    universes = read_universes_for_ui()

    create_col, edit_col = st.columns(2)
    with create_col:
        st.markdown("### 建立股票池")
        with st.form("universe_create_form"):
            name = st.text_input("股票池名稱", key="universe_create_name")
            description = st.text_area(
                "說明",
                key="universe_create_description",
                height=80,
            )
            symbol_text = st.text_area(
                "股票",
                placeholder="2330\n2454\nNVDA\nAAPL\n6488.TWO",
                key="universe_create_symbols",
                height=160,
            )
            submitted = st.form_submit_button("建立股票池")
        if submitted:
            symbols = universe_ui.parse_universe_symbol_text(symbol_text)
            if universe_ui.should_warn_large_universe(symbols):
                st.warning("股票池較大時，掃描時間可能較長。")
            try:
                created = create_universe(
                    name=name,
                    description=description,
                    symbols=symbols,
                )
                st.success(f"已建立股票池「{created.name}」，共 {created.symbol_count} 檔股票。")
            except (UniverseValidationError, UniverseAlreadyExistsError) as error:
                st.error(str(error))
            except UniverseError as error:
                st.error(f"股票池建立失敗：{error}")

    with edit_col:
        st.markdown("### 編輯股票池")
        if not universes:
            st.info("尚未建立自訂股票池。")
            return

        labels = [universe_ui.universe_selector_label(universe) for universe in universes]
        selected_label = st.selectbox(
            "已儲存股票池",
            labels,
            key="universe_edit_selector",
        )
        selected_universe = universes[labels.index(selected_label)]
        st.caption(
            f"更新時間：{universe_ui.format_universe_updated_at(selected_universe)}"
        )
        defaults = universe_ui.build_universe_form_defaults(selected_universe)
        with st.form(f"universe_edit_form_{selected_universe.id}"):
            next_name = st.text_input(
                "股票池名稱",
                value=defaults["name"],
                key=f"universe_edit_name_{selected_universe.id}",
            )
            next_description = st.text_area(
                "說明",
                value=defaults["description"],
                key=f"universe_edit_description_{selected_universe.id}",
                height=80,
            )
            next_symbols_text = st.text_area(
                "股票",
                value=defaults["symbols"],
                key=f"universe_edit_symbols_{selected_universe.id}",
                height=160,
            )
            saved = st.form_submit_button("儲存變更")
        if saved:
            symbols = universe_ui.parse_universe_symbol_text(next_symbols_text)
            if universe_ui.should_warn_large_universe(symbols):
                st.warning("股票池較大時，掃描時間可能較長。")
            try:
                updated = update_universe(
                    selected_universe.id,
                    name=next_name,
                    description=next_description,
                    symbols=symbols,
                )
                st.success(f"已更新股票池「{updated.name}」，共 {updated.symbol_count} 檔股票。")
            except (UniverseValidationError, UniverseAlreadyExistsError) as error:
                st.error(str(error))
            except UniverseNotFoundError as error:
                st.error(str(error))
            except UniverseError as error:
                st.error(f"股票池更新失敗：{error}")

        with st.form(f"universe_delete_form_{selected_universe.id}"):
            confirm_delete = st.checkbox(
                "我確認要刪除此股票池",
                key=f"universe_delete_confirm_{selected_universe.id}",
            )
            deleted = st.form_submit_button("刪除股票池")
        if deleted:
            if not confirm_delete:
                st.warning("請先勾選確認刪除。")
            else:
                try:
                    delete_universe(selected_universe.id)
                    st.success(f"已刪除股票池「{selected_universe.name}」。")
                except UniverseNotFoundError as error:
                    st.error(str(error))
                except UniverseError as error:
                    st.error(f"股票池刪除失敗：{error}")


def render_watchlist() -> None:
    st.header("觀察清單（Watchlist）")
    symbols = read_watchlist_for_ui()

    if symbols:
        st.write("目前觀察清單：")
        st.dataframe({"Symbol": symbols}, width="stretch", hide_index=True)
    else:
        st.info("觀察清單目前沒有股票。")

    add_col, remove_col = st.columns(2)

    with add_col:
        with st.form("watchlist_add_form"):
            symbol_to_add = st.text_input("新增股票", placeholder="2330 或 NVDA")
            add_submitted = st.form_submit_button("新增")

        if add_submitted:
            symbol = normalize_stock_symbol(symbol_to_add)
            if not symbol:
                st.warning("請輸入有效的股票代號。")
            else:
                try:
                    added = add_stock(symbol)
                except WatchlistDataError as error:
                    st.error(f"觀察清單寫入失敗：{error}")
                else:
                    if added:
                        st.success(f"已新增：{symbol}")
                        st.rerun()
                    else:
                        st.info(f"觀察清單已存在：{symbol}")

    with remove_col:
        if symbols:
            with st.form("watchlist_remove_form"):
                symbol_to_remove = st.selectbox("移除股票", symbols)
                remove_submitted = st.form_submit_button("移除")

            if remove_submitted:
                try:
                    removed = remove_stock(symbol_to_remove)
                except WatchlistDataError as error:
                    st.error(f"觀察清單寫入失敗：{error}")
                else:
                    if removed:
                        st.success(f"已移除：{symbol_to_remove}")
                        st.rerun()
                    else:
                        st.info(f"觀察清單找不到：{symbol_to_remove}")
        else:
            st.write("移除股票")
            st.info("目前沒有可移除的股票。")

    if st.button("查詢觀察清單股票", disabled=not symbols):
        stocks, failures = query_stock_batch(symbols)
        st.session_state["watchlist_query_stocks"] = stocks
        st.session_state["watchlist_query_failures"] = failures

    render_query_failures(st.session_state["watchlist_query_failures"])
    render_stock_cards(st.session_state["watchlist_query_stocks"])


def render_comparison() -> None:
    st.header("多股票比較")
    symbols = read_watchlist_for_ui()

    with st.form("comparison_form"):
        input_text = st.text_input(
            "多股票比較",
            placeholder="2330,NVDA,AAPL",
            key="comparison_input",
        )
        selected_watchlist_symbols = st.multiselect(
            "或從觀察清單選擇",
            symbols,
        )
        submitted = st.form_submit_button("比較")

    if submitted:
        input_symbols = parse_stock_symbols(input_text)
        merged_symbols = input_symbols.copy()
        for symbol in selected_watchlist_symbols:
            if symbol not in merged_symbols:
                merged_symbols.append(symbol)

        if not merged_symbols:
            st.warning("請輸入或選擇至少一個股票代號。")
            st.session_state["comparison_stocks"] = []
            st.session_state["comparison_failures"] = []
        else:
            stocks, failures = query_stock_batch(merged_symbols)
            st.session_state["comparison_stocks"] = stocks
            st.session_state["comparison_failures"] = failures

    render_query_failures(st.session_state["comparison_failures"])
    comparison_rows = build_comparison_rows(st.session_state["comparison_stocks"])
    if comparison_rows:
        st.info("Current Price 保留各股票原始貨幣，不直接作為跨幣別排名。")
        st.dataframe(comparison_rows, width="stretch", hide_index=True)


def main() -> None:
    initialize_session_state()

    st.title("AI Investment Research")
    st.info("資料可能使用 24 小時內的本地快取；若快取不存在或過期，系統會查詢 Yahoo Finance 並更新 SQLite cache。")

    dashboard_tab, research_tab, historical_tab, ai_research_tab, swing_research_tab, universe_tab, historical_cases_tab, watchlist_tab, comparison_tab = st.tabs(
        [
            "Dashboard",
            "Research",
            "Historical Trends",
            "AI Research",
            "Swing Research（波段研究）",
            "研究股票池",
            "歷史案例",
            "觀察清單",
            "Comparison（多股票比較）",
        ]
    )

    with dashboard_tab:
        render_stock_search()

    with research_tab:
        render_research()

    with historical_tab:
        render_historical_trends()

    with ai_research_tab:
        render_ai_research()

    with swing_research_tab:
        render_swing_research()

    with universe_tab:
        render_universe_management()

    with historical_cases_tab:
        render_historical_cases()

    with watchlist_tab:
        render_watchlist()

    with comparison_tab:
        render_comparison()


if __name__ == "__main__":
    main()
