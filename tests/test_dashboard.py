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
from dashboard import format_market_cap
from dashboard import format_na
from dashboard import format_percentage
from dashboard import indicator_help
from dashboard import indicator_label
from dashboard import INDICATOR_HELP_TEXT
from dashboard import INDICATOR_LABELS
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
        self.assertEqual(format_market_cap(2_500_000_000, "USD"), "USD 2.50B")
        self.assertEqual(format_market_cap(5_674_171_891_712, "TWD"), "TWD 5.67T")
        self.assertEqual(format_market_cap(850_200_000, None), "850.20M")
        self.assertEqual(format_market_cap(None, "USD"), "N/A")

    def test_integer_formatting_remains_available(self):
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
        self.assertEqual(display_data["Market Cap"], "USD 4.88T")
        self.assertEqual(display_data["Trailing PE"], "57.68")
        self.assertEqual(display_data["EPS"], "3.48")
        self.assertEqual(display_data["ROE"], "28.50%")

    def test_bilingual_indicator_labels(self):
        self.assertEqual(indicator_label("current_price"), "Current Price（目前股價）")
        self.assertEqual(indicator_label("market_cap"), "Market Cap（市值）")
        self.assertEqual(indicator_label("return_on_equity"), "ROE（股東權益報酬率）")
        self.assertEqual(indicator_label("trailing_pe"), "Trailing P/E（歷史本益比）")
        self.assertEqual(indicator_label("forward_pe"), "Forward P/E（預估本益比）")

    def test_required_help_text_registry(self):
        required_indicators = [
            "current_price",
            "market_cap",
            "trailing_pe",
            "forward_pe",
            "trailing_eps",
            "return_on_equity",
            "sector",
            "industry",
        ]

        for indicator in required_indicators:
            self.assertIn(indicator, INDICATOR_LABELS)
            self.assertIn(indicator, INDICATOR_HELP_TEXT)
            self.assertTrue(indicator_help(indicator))

    def test_comparison_rows_use_display_ready_values(self):
        rows = build_comparison_rows([self.sample_stock()])

        self.assertEqual(
            rows,
            [
                {
                    "Symbol（股票代號）": "NVDA",
                    "Company Name（公司名稱）": "NVIDIA Corporation",
                    "Current Price（目前股價）": "200.76",
                    "Currency（交易幣別）": "USD",
                    "Market Cap（市值）": "USD 4.88T",
                    "Trailing P/E（歷史本益比）": "57.68",
                    "Forward P/E（預估本益比）": "44.30",
                    "EPS（每股盈餘）": "3.48",
                    "ROE（股東權益報酬率）": "28.50%",
                    "Sector（產業類別）": "Technology",
                    "Industry（細分產業）": "Semiconductors",
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
