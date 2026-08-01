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
