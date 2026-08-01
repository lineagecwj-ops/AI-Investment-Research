import sys
from pathlib import Path

import streamlit as st


SRC_PATH = Path(__file__).resolve().parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dashboard import build_comparison_rows
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
from dashboard import query_stock_batch
from dashboard import stock_display_data
from research_glossary import get_research_glossary
from research_service import build_research_report
from symbol_utils import normalize_stock_symbol
from symbol_utils import parse_stock_symbols
from watchlist_service import add_stock
from watchlist_service import list_watchlist
from watchlist_service import remove_stock
from watchlist_service import WatchlistDataError


st.set_page_config(
    page_title="AI Investment Research",
    layout="wide",
)


def initialize_session_state() -> None:
    st.session_state.setdefault("stock_search_stocks", [])
    st.session_state.setdefault("stock_search_failures", [])
    st.session_state.setdefault("research_stock", None)
    st.session_state.setdefault("research_failures", [])
    st.session_state.setdefault("watchlist_query_stocks", [])
    st.session_state.setdefault("watchlist_query_failures", [])
    st.session_state.setdefault("comparison_stocks", [])
    st.session_state.setdefault("comparison_failures", [])


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


def render_research_glossary() -> None:
    with st.expander("研究名詞說明"):
        for entry in get_research_glossary().values():
            st.write(f"**{entry['title']}**")
            st.write(entry["description"])


def render_research() -> None:
    st.header("Research（研究）")
    st.caption("以固定研究流程整理 fundamental snapshot；本頁不使用 AI，也不產生 Buy / Sell / Hold recommendation。")

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
        st.info("輸入股票代號後，系統會依照 8 個研究問題建立 deterministic research summary。")
        return

    report = build_research_report(stock)
    display_data = stock_display_data(stock)

    st.subheader(f"{display_data['Symbol']} · {display_data['Company Name']}")

    with st.expander("如何理解這些指標？"):
        st.write(
            "本頁使用 Yahoo Finance 提供的單一 fundamental snapshot，協助建立研究問題與觀察方向。"
            "所有 observations 都是 deterministic research prompts，不是投資建議，也不是整體評分。"
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
    if stock.company_summary:
        st.write(stock.company_summary)
    else:
        st.info("Company Summary（公司業務摘要）目前為 N/A。")

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
    st.info("目前為 Yahoo Finance 提供的當期/近期 growth snapshot，不是本系統自行計算的多年 CAGR。")
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


def read_watchlist_for_ui() -> list[str]:
    try:
        return list_watchlist()
    except WatchlistDataError as error:
        st.error(f"Watchlist 讀取失敗：{error}")
        return []


def render_watchlist() -> None:
    st.header("Watchlist")
    symbols = read_watchlist_for_ui()

    if symbols:
        st.write("目前 Watchlist：")
        st.dataframe({"Symbol": symbols}, width="stretch", hide_index=True)
    else:
        st.info("Watchlist 目前沒有股票。")

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
                    st.error(f"Watchlist 寫入失敗：{error}")
                else:
                    if added:
                        st.success(f"已新增：{symbol}")
                        st.rerun()
                    else:
                        st.info(f"Watchlist 已存在：{symbol}")

    with remove_col:
        if symbols:
            with st.form("watchlist_remove_form"):
                symbol_to_remove = st.selectbox("移除股票", symbols)
                remove_submitted = st.form_submit_button("移除")

            if remove_submitted:
                try:
                    removed = remove_stock(symbol_to_remove)
                except WatchlistDataError as error:
                    st.error(f"Watchlist 寫入失敗：{error}")
                else:
                    if removed:
                        st.success(f"已移除：{symbol_to_remove}")
                        st.rerun()
                    else:
                        st.info(f"Watchlist 找不到：{symbol_to_remove}")
        else:
            st.write("移除股票")
            st.info("目前沒有可移除的股票。")

    if st.button("查詢 Watchlist 股票", disabled=not symbols):
        stocks, failures = query_stock_batch(symbols)
        st.session_state["watchlist_query_stocks"] = stocks
        st.session_state["watchlist_query_failures"] = failures

    render_query_failures(st.session_state["watchlist_query_failures"])
    render_stock_cards(st.session_state["watchlist_query_stocks"])


def render_comparison() -> None:
    st.header("Comparison")
    symbols = read_watchlist_for_ui()

    with st.form("comparison_form"):
        input_text = st.text_input(
            "多股票比較",
            placeholder="2330,NVDA,AAPL",
            key="comparison_input",
        )
        selected_watchlist_symbols = st.multiselect(
            "或從 Watchlist 選擇",
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

    dashboard_tab, research_tab, watchlist_tab, comparison_tab = st.tabs(
        ["Dashboard", "Research", "Watchlist", "Comparison"]
    )

    with dashboard_tab:
        render_stock_search()

    with research_tab:
        render_research()

    with watchlist_tab:
        render_watchlist()

    with comparison_tab:
        render_comparison()


if __name__ == "__main__":
    main()
