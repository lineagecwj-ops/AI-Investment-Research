from stock_service import get_stock


def get_stock_symbol():
    symbol = input("請輸入股票代號：").strip().upper()

    if symbol.isdigit():
        return symbol + ".TW"

    return symbol


def display_stock(stock):
    print()
    print("股票代號：", stock.symbol)
    print("股票名稱：", stock.company_name)
    print("目前價格：", stock.price)
    print("貨幣：", stock.currency)


def main():
    symbol = get_stock_symbol()

    stock = get_stock(symbol)

    display_stock(stock)


main()