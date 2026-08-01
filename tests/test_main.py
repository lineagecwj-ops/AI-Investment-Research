import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from main import parse_stock_symbols
from main import main
from main import query_stocks
from stock_service import StockDataError


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

    def test_parse_blank_input_returns_empty_list(self):
        self.assertEqual(parse_stock_symbols("   "), [])


class MainFlowTestCase(unittest.TestCase):

    @patch("builtins.input", side_effect=["1", "   ", "3"])
    def test_blank_input_prints_friendly_message(self, _mock_input):
        with patch("builtins.print") as mock_print:
            main()

        mock_print.assert_any_call("請輸入至少一個股票代號。")

    @patch("main.display_stock")
    @patch("main.get_stock")
    def test_single_stock_error_does_not_stop_other_queries(
        self,
        mock_get_stock,
        mock_display_stock,
    ):
        first_stock = object()
        third_stock = object()
        mock_get_stock.side_effect = [
            first_stock,
            StockDataError("Yahoo Finance 回傳資料缺少目前價格。"),
            third_stock,
        ]

        with patch("main.display_stock_error") as mock_display_error:
            query_stocks(["2330.TW", "INVALID", "NVDA"])

        self.assertEqual(mock_get_stock.call_count, 3)
        mock_display_stock.assert_any_call(first_stock)
        mock_display_stock.assert_any_call(third_stock)
        mock_display_error.assert_called_once()

    @patch("builtins.input", side_effect=["3"])
    def test_menu_exit_prints_goodbye(self, _mock_input):
        with patch("builtins.print") as mock_print:
            main()

        mock_print.assert_any_call("再見。")


if __name__ == "__main__":
    unittest.main()
