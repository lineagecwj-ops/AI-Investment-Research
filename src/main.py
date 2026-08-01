from stock_service import StockServiceError, get_stock
from symbol_utils import normalize_stock_symbol
from symbol_utils import parse_stock_symbols
from watchlist_service import add_stock
from watchlist_service import list_watchlist
from watchlist_service import remove_stock


def get_stock_symbols() -> list[str]:
    user_input = input("請輸入股票代號：")

    return parse_stock_symbols(user_input)


def display_stock(stock):
    print()
    print("股票代號：", format_value(stock.symbol))
    print("股票名稱：", format_value(stock.company_name))
    print("目前價格：", format_value(stock.current_price))
    print("貨幣：", format_value(stock.currency))
    print("市值：", format_value(stock.market_cap))
    print("Trailing PE：", format_value(stock.trailing_pe))
    print("Forward PE：", format_value(stock.forward_pe))
    print("EPS：", format_value(stock.trailing_eps))
    print("ROE：", format_percentage(stock.return_on_equity))
    print("Sector：", format_value(stock.sector))
    print("Industry：", format_value(stock.industry))


def display_stock_error(symbol: str, error: StockServiceError) -> None:
    print()
    print("股票代號：", symbol)
    print("查詢失敗：", error)


def format_value(value) -> str:
    if value is None or value == "":
        return "N/A"

    return str(value)


def format_percentage(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{value * 100:.2f}%"


def query_stocks(symbols: list[str]) -> None:
    if not symbols:
        print("請輸入至少一個股票代號。")
        return

    for symbol in symbols:
        try:
            stock = get_stock(symbol)
        except StockServiceError as error:
            display_stock_error(symbol, error)
            continue

        display_stock(stock)


def query_stocks_from_input() -> None:
    symbols = get_stock_symbols()
    query_stocks(symbols)


def display_main_menu() -> None:
    print()
    print("====================================")
    print("AI Investment Research")
    print("====================================")
    print("1. 查詢股票")
    print("2. Watchlist")
    print("3. 離開")


def display_watchlist_menu() -> None:
    print()
    print("========== Watchlist ==========")
    print("1. 顯示 Watchlist")
    print("2. 新增股票")
    print("3. 移除股票")
    print("4. 查詢 Watchlist 股票")
    print("5. 返回")


def show_watchlist() -> list[str]:
    symbols = list_watchlist()

    if not symbols:
        print("Watchlist 目前沒有股票。")
        return []

    print("Watchlist：")
    for symbol in symbols:
        print("-", symbol)

    return symbols


def add_watchlist_stock() -> None:
    symbol = normalize_stock_symbol(input("請輸入要新增的股票代號："))

    if not symbol:
        print("請輸入有效的股票代號。")
        return

    if add_stock(symbol):
        print(f"已新增：{symbol}")
    else:
        print(f"Watchlist 已存在：{symbol}")


def remove_watchlist_stock() -> None:
    symbol = normalize_stock_symbol(input("請輸入要移除的股票代號："))

    if not symbol:
        print("請輸入有效的股票代號。")
        return

    if remove_stock(symbol):
        print(f"已移除：{symbol}")
    else:
        print(f"Watchlist 找不到：{symbol}")


def query_watchlist_stocks() -> None:
    symbols = show_watchlist()
    if not symbols:
        return

    query_stocks(symbols)


def run_watchlist_menu() -> None:
    while True:
        display_watchlist_menu()
        choice = input("請選擇功能：").strip()

        if choice == "1":
            show_watchlist()
        elif choice == "2":
            add_watchlist_stock()
        elif choice == "3":
            remove_watchlist_stock()
        elif choice == "4":
            query_watchlist_stocks()
        elif choice == "5":
            return
        else:
            print("請輸入 1 到 5。")


def main():
    while True:
        display_main_menu()
        choice = input("請選擇功能：").strip()

        if choice == "1":
            query_stocks_from_input()
        elif choice == "2":
            run_watchlist_menu()
        elif choice == "3":
            print("再見。")
            return
        else:
            print("請輸入 1 到 3。")


if __name__ == "__main__":
    main()
