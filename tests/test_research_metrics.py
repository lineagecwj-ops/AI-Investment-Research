import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import Stock
from research_metrics import calculate_52_week_position


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


if __name__ == "__main__":
    unittest.main()
