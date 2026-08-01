from stock_service import get_stock


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
    print("股票代號：", stock.symbol)
    print("股票名稱：", stock.company_name)
    print("目前價格：", stock.price)
    print("貨幣：", stock.currency)


def main():
    symbols = get_stock_symbols()

    for symbol in symbols:
        stock = get_stock(symbol)

        display_stock(stock)


if __name__ == "__main__":
    main()
