import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dashboard import build_comparison_rows
from dashboard import format_decimal
from dashboard import format_integer
from dashboard import format_na
from dashboard import format_percentage
from dashboard import query_stock_batch
from dashboard import stock_display_data
from models import Stock
from stock_service import StockDataError


class DashboardFormattingTestCase(unittest.TestCase):

    def sample_stock(self):
        return Stock(
            symbol="NVDA",
            company_name="NVIDIA Corporation",
            current_price=200.756,
            currency="USD",
            market_cap=4879000000000,
            trailing_pe=57.681,
            forward_pe=44.3,
            trailing_eps=3.485,
            return_on_equity=0.285,
            sector="Technology",
            industry="Semiconductors",
        )

    def test_na_formatting(self):
        self.assertEqual(format_na(None), "N/A")
        self.assertEqual(format_na(""), "N/A")
        self.assertEqual(format_na("NVDA"), "NVDA")

    def test_market_cap_formatting(self):
        self.assertEqual(format_integer(2500000000), "2,500,000,000")
        self.assertEqual(format_integer(None), "N/A")

    def test_decimal_formatting(self):
        self.assertEqual(format_decimal(25.345), "25.34")
        self.assertEqual(format_decimal(None), "N/A")

    def test_roe_percentage_formatting(self):
        self.assertEqual(format_percentage(0.285), "28.50%")
        self.assertEqual(format_percentage(None), "N/A")

    def test_stock_display_data_formats_all_fields(self):
        display_data = stock_display_data(self.sample_stock())

        self.assertEqual(display_data["Company Name"], "NVIDIA Corporation")
        self.assertEqual(display_data["Symbol"], "NVDA")
        self.assertEqual(display_data["Current Price"], "200.76")
        self.assertEqual(display_data["Market Cap"], "4,879,000,000,000")
        self.assertEqual(display_data["Trailing PE"], "57.68")
        self.assertEqual(display_data["EPS"], "3.48")
        self.assertEqual(display_data["ROE"], "28.50%")

    def test_comparison_rows_use_display_ready_values(self):
        rows = build_comparison_rows([self.sample_stock()])

        self.assertEqual(
            rows,
            [
                {
                    "Symbol": "NVDA",
                    "Company": "NVIDIA Corporation",
                    "Current Price": "200.76",
                    "Currency": "USD",
                    "Market Cap": "4,879,000,000,000",
                    "Trailing PE": "57.68",
                    "Forward PE": "44.30",
                    "EPS": "3.48",
                    "ROE": "28.50%",
                    "Sector": "Technology",
                    "Industry": "Semiconductors",
                }
            ],
        )


class DashboardQueryTestCase(unittest.TestCase):

    def test_partial_query_failure_keeps_successful_stocks(self):
        nvda_stock = Stock(symbol="NVDA", company_name="NVIDIA Corporation")
        aapl_stock = Stock(symbol="AAPL", company_name="Apple Inc.")

        def fake_lookup(symbol):
            if symbol == "INVALID":
                raise StockDataError("Yahoo Finance 回傳資料缺少目前價格。")
            if symbol == "NVDA":
                return nvda_stock
            return aapl_stock

        stocks, failures = query_stock_batch(["NVDA", "INVALID", "AAPL"], fake_lookup)

        self.assertEqual(stocks, [nvda_stock, aapl_stock])
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].symbol, "INVALID")
        self.assertEqual(failures[0].message, "Yahoo Finance 回傳資料缺少目前價格。")


if __name__ == "__main__":
    unittest.main()
