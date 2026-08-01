import sys
from pathlib import Path

import streamlit as st


SRC_PATH = Path(__file__).resolve().parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dashboard import build_comparison_rows
from dashboard import indicator_help
from dashboard import indicator_label
from dashboard import query_stock_batch
from dashboard import stock_display_data
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

    dashboard_tab, watchlist_tab, comparison_tab = st.tabs(
        ["Dashboard", "Watchlist", "Comparison"]
    )

    with dashboard_tab:
        render_stock_search()

    with watchlist_tab:
        render_watchlist()

    with comparison_tab:
        render_comparison()


if __name__ == "__main__":
    main()
