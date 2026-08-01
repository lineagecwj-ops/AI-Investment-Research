import yfinance as yf


def main():
    stock = yf.Ticker("2330.TW")

    info = stock.info

    print("股票代號：", info.get("symbol"))
    print("股票名稱：", info.get("longName"))
    print("目前價格：", info.get("currentPrice"))
    print("貨幣：", info.get("currency"))


main()