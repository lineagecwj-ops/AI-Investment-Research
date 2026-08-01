from models import Stock


def calculate_52_week_position(stock: Stock) -> float | None:
    if (
        stock.current_price is None
        or stock.fifty_two_week_low is None
        or stock.fifty_two_week_high is None
    ):
        return None

    range_width = stock.fifty_two_week_high - stock.fifty_two_week_low
    if range_width <= 0:
        return None

    return (stock.current_price - stock.fifty_two_week_low) / range_width
