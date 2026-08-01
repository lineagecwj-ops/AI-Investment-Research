import sys
import unittest
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import Stock
from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries
from research_metrics import calculate_52_week_position
from research_metrics import calculate_eps_yoy_growth
from research_metrics import calculate_yoy_growth
from research_metrics import historical_yoy_growth_by_field


class ResearchMetricsTestCase(unittest.TestCase):

    def test_52_week_position_normal_case(self):
        stock = Stock(
            current_price=150.0,
            fifty_two_week_low=100.0,
            fifty_two_week_high=200.0,
        )

        self.assertEqual(calculate_52_week_position(stock), 0.5)

    def test_52_week_position_missing_values(self):
        self.assertIsNone(calculate_52_week_position(Stock()))
        self.assertIsNone(
            calculate_52_week_position(
                Stock(current_price=150.0, fifty_two_week_low=100.0)
            )
        )

    def test_52_week_position_high_equals_low(self):
        stock = Stock(
            current_price=150.0,
            fifty_two_week_low=100.0,
            fifty_two_week_high=100.0,
        )

        self.assertIsNone(calculate_52_week_position(stock))

    def test_52_week_position_invalid_range(self):
        stock = Stock(
            current_price=150.0,
            fifty_two_week_low=200.0,
            fifty_two_week_high=100.0,
        )

        self.assertIsNone(calculate_52_week_position(stock))

    def test_yoy_growth_uses_absolute_previous_denominator(self):
        self.assertEqual(calculate_yoy_growth(120.0, 100.0), 0.2)
        self.assertEqual(calculate_yoy_growth(-80.0, -100.0), 0.2)

    def test_yoy_growth_handles_missing_and_zero_previous(self):
        self.assertIsNone(calculate_yoy_growth(None, 100.0))
        self.assertIsNone(calculate_yoy_growth(120.0, None))
        self.assertIsNone(calculate_yoy_growth(120.0, 0.0))

    def test_eps_yoy_growth_requires_positive_previous_eps(self):
        self.assertAlmostEqual(calculate_eps_yoy_growth(2.4, 1.8), 1 / 3)
        self.assertIsNone(calculate_eps_yoy_growth(2.4, 0.0))
        self.assertIsNone(calculate_eps_yoy_growth(2.4, -1.0))

    def test_historical_yoy_growth_by_field_keeps_first_period_none(self):
        series = HistoricalFinancialSeries(
            symbol="TEST",
            periods=[
                HistoricalFinancialPeriod(
                    symbol="TEST",
                    period_end=date(2024, 12, 31),
                    fiscal_year=2024,
                    revenue=100.0,
                    eps=-1.0,
                    net_income=50.0,
                ),
                HistoricalFinancialPeriod(
                    symbol="TEST",
                    period_end=date(2025, 12, 31),
                    fiscal_year=2025,
                    revenue=120.0,
                    eps=2.0,
                    net_income=75.0,
                ),
            ],
        )

        self.assertEqual(
            historical_yoy_growth_by_field(series, "revenue"),
            [(2024, None), (2025, 0.2)],
        )
        self.assertEqual(
            historical_yoy_growth_by_field(series, "net_income"),
            [(2024, None), (2025, 0.5)],
        )
        self.assertEqual(
            historical_yoy_growth_by_field(series, "eps"),
            [(2024, None), (2025, None)],
        )


if __name__ == "__main__":
    unittest.main()
