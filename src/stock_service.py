import yfinance as yf

from models import Stock


def get_stock(symbol: str) -> Stock:
    stock = yf.Ticker(symbol)
    info = stock.info

    return Stock(
        symbol=info.get("symbol"),
        company_name=info.get("longName"),
        price=info.get("currentPrice"),
        currency=info.get("currency"),
    )