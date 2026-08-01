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


def calculate_yoy_growth(
    current: float | None,
    previous: float | None,
    current_year: int | None = None,
    previous_year: int | None = None,
) -> float | None:
    if not are_consecutive_years(current_year, previous_year):
        return None
    if current is None or previous is None or previous == 0:
        return None

    return (current - previous) / abs(previous)


def calculate_eps_yoy_growth(
    current: float | None,
    previous: float | None,
    current_year: int | None = None,
    previous_year: int | None = None,
) -> float | None:
    if not are_consecutive_years(current_year, previous_year):
        return None
    if previous is None or previous <= 0:
        return None

    return calculate_yoy_growth(current, previous, current_year, previous_year)


def are_consecutive_years(
    current_year: int | None,
    previous_year: int | None,
) -> bool:
    if current_year is None or previous_year is None:
        return False

    return current_year == previous_year + 1


def historical_yoy_growth_by_field(
    series: HistoricalFinancialSeries,
    field_name: str,
) -> list[tuple[int | None, float | None]]:
    growth_values = []
    previous_value = None
    previous_year = None

    for period in series.periods or []:
        current_value = getattr(period, field_name)
        current_year = period.period_year
        if field_name == "eps":
            growth = calculate_eps_yoy_growth(
                current_value,
                previous_value,
                current_year,
                previous_year,
            )
        else:
            growth = calculate_yoy_growth(
                current_value,
                previous_value,
                current_year,
                previous_year,
            )
        growth_values.append((period.period_year, growth))
        previous_value = current_value
        previous_year = current_year

    return growth_values
