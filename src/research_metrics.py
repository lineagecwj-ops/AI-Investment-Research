from models import Stock
from models import HistoricalFinancialSeries


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


def calculate_yoy_growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None

    return (current - previous) / abs(previous)


def calculate_eps_yoy_growth(current: float | None, previous: float | None) -> float | None:
    if previous is None or previous <= 0:
        return None

    return calculate_yoy_growth(current, previous)


def historical_yoy_growth_by_field(
    series: HistoricalFinancialSeries,
    field_name: str,
) -> list[tuple[int | None, float | None]]:
    growth_values = []
    previous_value = None

    for period in series.periods or []:
        current_value = getattr(period, field_name)
        if field_name == "eps":
            growth = calculate_eps_yoy_growth(current_value, previous_value)
        else:
            growth = calculate_yoy_growth(current_value, previous_value)
        growth_values.append((period.fiscal_year, growth))
        previous_value = current_value

    return growth_values
