import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from main import parse_stock_symbols


class ParseStockSymbolsTestCase(unittest.TestCase):

    def test_parse_single_taiwan_stock_symbol(self):
        self.assertEqual(parse_stock_symbols("2330"), ["2330.TW"])

    def test_parse_single_us_stock_symbol(self):
        self.assertEqual(parse_stock_symbols("nvda"), ["NVDA"])

    def test_parse_multiple_stock_symbols(self):
        self.assertEqual(
            parse_stock_symbols("2330,NVDA,AAPL"),
            ["2330.TW", "NVDA", "AAPL"],
        )

    def test_parse_multiple_stock_symbols_with_spaces(self):
        self.assertEqual(
            parse_stock_symbols("2330, NVDA, AAPL"),
            ["2330.TW", "NVDA", "AAPL"],
        )

    def test_parse_duplicate_stock_symbols_once(self):
        self.assertEqual(
            parse_stock_symbols("2330, 2330.TW, nvda, NVDA"),
            ["2330.TW", "NVDA"],
        )


if __name__ == "__main__":
    unittest.main()
