import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dashboard import build_comparison_rows
from dashboard import format_currency_value
from dashboard import format_debt_to_equity
from dashboard import format_decimal
from dashboard import format_integer
from dashboard import format_industry
from dashboard import format_market_cap
from dashboard import format_na
from dashboard import format_percentage
from dashboard import format_price
from dashboard import format_ratio
from dashboard import format_sector
from dashboard import indicator_help
from dashboard import indicator_label
from dashboard import INDUSTRY_TRANSLATIONS
from dashboard import INDICATOR_HELP_TEXT
from dashboard import INDICATOR_LABELS
from dashboard import query_stock_batch
from dashboard import SECTOR_TRANSLATIONS
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

    def test_currency_value_formatting_keeps_currency_context(self):
        self.assertEqual(format_currency_value(1_250_000_000_000, "TWD"), "TWD 1.25T")
        self.assertEqual(format_currency_value(85_400_000_000, "USD"), "USD 85.40B")
        self.assertEqual(format_currency_value(None, "USD"), "N/A")

    def test_integer_formatting_remains_available(self):
        self.assertEqual(format_integer(2500000000), "2,500,000,000")
        self.assertEqual(format_integer(None), "N/A")

    def test_decimal_formatting(self):
        self.assertEqual(format_decimal(25.345), "25.34")
        self.assertEqual(format_decimal(None), "N/A")

    def test_price_and_ratio_formatting(self):
        self.assertEqual(format_price(123.456, "USD"), "USD 123.46")
        self.assertEqual(format_price(None, "USD"), "N/A")
        self.assertEqual(format_ratio(35.2), "35.20")
        self.assertEqual(format_ratio(None), "N/A")

    def test_debt_to_equity_display_uses_yahoo_percent_scale(self):
        self.assertEqual(format_debt_to_equity(15.174), "15.17%")
        self.assertEqual(format_debt_to_equity(3.952), "3.95%")
        self.assertEqual(format_debt_to_equity(None), "N/A")
        self.assertNotEqual(format_debt_to_equity(15.174), "1,517.40%")

    def test_research_page_uses_debt_to_equity_formatter(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("from dashboard import format_debt_to_equity", app_source)
        self.assertIn(
            '(indicator_label("debt_to_equity"), format_debt_to_equity(stock.debt_to_equity), indicator_help("debt_to_equity"))',
            app_source,
        )

    def test_roe_percentage_formatting(self):
        self.assertEqual(format_percentage(0.285), "28.50%")
        self.assertEqual(format_percentage(None), "N/A")

    def test_known_sector_translation(self):
        self.assertEqual(format_sector("Technology"), "Technology（科技）")
        self.assertEqual(format_sector("Financial Services"), "Financial Services（金融服務）")

    def test_known_industry_translation(self):
        self.assertEqual(format_industry("Semiconductors"), "Semiconductors（半導體）")

    def test_unknown_classification_falls_back_to_english(self):
        self.assertEqual(format_sector("Specialty Business Services"), "Specialty Business Services")
        self.assertEqual(format_industry("Unknown Industry"), "Unknown Industry")

    def test_missing_classification_formats_as_na(self):
        self.assertEqual(format_sector(None), "N/A")
        self.assertEqual(format_industry(None), "N/A")

    def test_translation_mappings_cover_required_values(self):
        required_sectors = [
            "Technology",
            "Healthcare",
            "Financial Services",
            "Consumer Cyclical",
            "Consumer Defensive",
            "Industrials",
            "Energy",
            "Basic Materials",
            "Communication Services",
            "Real Estate",
            "Utilities",
        ]

        for sector in required_sectors:
            self.assertIn(sector, SECTOR_TRANSLATIONS)

        self.assertIn("Semiconductors", INDUSTRY_TRANSLATIONS)

    def test_stock_display_data_formats_all_fields(self):
        with patch("dashboard.get_display_company_name", return_value="NVIDIA Corporation") as mock_name:
            display_data = stock_display_data(self.sample_stock())

        self.assertEqual(display_data["Company Name"], "NVIDIA Corporation")
        mock_name.assert_called_once()
        self.assertEqual(display_data["Symbol"], "NVDA")
        self.assertEqual(display_data["Current Price"], "200.76")
        self.assertEqual(display_data["Market Cap"], "USD 4.88T")
        self.assertEqual(display_data["Trailing PE"], "57.68")
        self.assertEqual(display_data["EPS"], "3.48")
        self.assertEqual(display_data["ROE"], "28.50%")
        self.assertEqual(display_data["Sector"], "Technology（科技）")
        self.assertEqual(display_data["Industry"], "Semiconductors（半導體）")

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
        with patch("dashboard.get_display_company_name", return_value="NVIDIA Corporation"):
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
                    "Sector（產業類別）": "Technology（科技）",
                    "Industry（細分產業）": "Semiconductors（半導體）",
                }
            ],
        )

    def test_dashboard_uses_localized_name_helper(self):
        stock = Stock(
            symbol="2330.TW",
            company_name="Taiwan Semiconductor Manufacturing Company Limited",
        )

        with patch("dashboard.get_display_company_name", return_value="台積電") as mock_name:
            display_data = stock_display_data(stock)

        mock_name.assert_called_once_with(stock)
        self.assertEqual(display_data["Company Name"], "台積電")

    def test_comparison_uses_localized_name_helper(self):
        stock = Stock(
            symbol="2330.TW",
            company_name="Taiwan Semiconductor Manufacturing Company Limited",
        )

        with patch("dashboard.get_display_company_name", return_value="台積電") as mock_name:
            rows = build_comparison_rows([stock])

        mock_name.assert_called_once_with(stock)
        self.assertEqual(rows[0]["Company Name（公司名稱）"], "台積電")


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
