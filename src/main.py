from stock_service import StockServiceError, get_stock


def normalize_stock_symbol(symbol: str) -> str:
    normalized_symbol = symbol.strip().upper()

    if normalized_symbol.isdigit():
        return normalized_symbol + ".TW"

    return normalized_symbol


def parse_stock_symbols(user_input: str) -> list[str]:
    symbols = []
    seen_symbols = set()

    for raw_symbol in user_input.split(","):
        symbol = normalize_stock_symbol(raw_symbol)

        if not symbol or symbol in seen_symbols:
            continue

        symbols.append(symbol)
        seen_symbols.add(symbol)

    return symbols


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


def main():
    symbols = get_stock_symbols()

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


if __name__ == "__main__":
    main()
