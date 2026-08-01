import yfinance as yf

from models import Stock


def stock_from_yahoo_info(info: dict, requested_symbol: str) -> Stock:
    current_price = info.get("currentPrice")

    return Stock(
        symbol=info.get("symbol") or requested_symbol,
        company_name=info.get("longName") or info.get("shortName"),
        price=current_price,
        current_price=current_price,
        currency=info.get("currency"),
        market_cap=info.get("marketCap"),
        trailing_pe=info.get("trailingPE"),
        forward_pe=info.get("forwardPE"),
        trailing_eps=info.get("trailingEps"),
        return_on_equity=info.get("returnOnEquity"),
        sector=info.get("sector"),
        industry=info.get("industry"),
    )


def get_stock(symbol: str) -> Stock:
    stock = yf.Ticker(symbol)
    info = stock.info

    return stock_from_yahoo_info(info, symbol)
