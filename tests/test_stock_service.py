import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from stock_service import StockDataError
from stock_service import StockServiceError
from stock_service import fetch_stock_from_yahoo
from stock_service import get_stock
from stock_service import stock_from_yahoo_info
from stock_service import validate_stock
from database import save_stock
from models import Stock


class StockFromYahooInfoTestCase(unittest.TestCase):

    def test_maps_yahoo_info_to_stock_model(self):
        stock = stock_from_yahoo_info(
            {
                "symbol": "NVDA",
                "longName": "NVIDIA Corporation",
                "currentPrice": 200.75,
                "currency": "USD",
                "marketCap": 4879000000000,
                "trailingPE": 57.68,
                "forwardPE": 44.3,
                "trailingEps": 3.48,
                "returnOnEquity": 0.25,
                "longBusinessSummary": "NVIDIA builds accelerated computing platforms.",
                "grossMargins": 0.741,
                "operatingMargins": 0.656,
                "profitMargins": 0.63,
                "revenueGrowth": 0.852,
                "earningsGrowth": 2.145,
                "totalCash": 53171998720,
                "totalDebt": 12814000128,
                "debtToEquity": 6.555,
                "operatingCashflow": 125648003072,
                "freeCashflow": 46335873024,
                "priceToBook": 24.876,
                "fiftyTwoWeekHigh": 236.54,
                "fiftyTwoWeekLow": 164.07,
                "fiftyDayAverage": 206.17,
                "twoHundredDayAverage": 193.11,
                "sector": "Technology",
                "industry": "Semiconductors",
            },
            "NVDA",
        )

        self.assertEqual(stock.symbol, "NVDA")
        self.assertEqual(stock.company_name, "NVIDIA Corporation")
        self.assertEqual(stock.current_price, 200.75)
        self.assertEqual(stock.currency, "USD")
        self.assertEqual(stock.market_cap, 4879000000000)
        self.assertEqual(stock.trailing_pe, 57.68)
        self.assertEqual(stock.forward_pe, 44.3)
        self.assertEqual(stock.trailing_eps, 3.48)
        self.assertEqual(stock.return_on_equity, 0.25)
        self.assertEqual(stock.company_summary, "NVIDIA builds accelerated computing platforms.")
        self.assertEqual(stock.gross_margin, 0.741)
        self.assertEqual(stock.operating_margin, 0.656)
        self.assertEqual(stock.net_margin, 0.63)
        self.assertEqual(stock.revenue_growth, 0.852)
        self.assertEqual(stock.earnings_growth, 2.145)
        self.assertEqual(stock.total_cash, 53171998720)
        self.assertEqual(stock.total_debt, 12814000128)
        self.assertEqual(stock.debt_to_equity, 6.555)
        self.assertEqual(stock.operating_cash_flow, 125648003072)
        self.assertEqual(stock.free_cash_flow, 46335873024)
        self.assertEqual(stock.price_to_book, 24.876)
        self.assertEqual(stock.fifty_two_week_high, 236.54)
        self.assertEqual(stock.fifty_two_week_low, 164.07)
        self.assertEqual(stock.fifty_day_average, 206.17)
        self.assertEqual(stock.two_hundred_day_average, 193.11)
        self.assertEqual(stock.sector, "Technology")
        self.assertEqual(stock.industry, "Semiconductors")

    def test_missing_yahoo_info_uses_none_without_crashing(self):
        stock = stock_from_yahoo_info({}, "MISSING")

        self.assertEqual(stock.symbol, "MISSING")
        self.assertIsNone(stock.company_name)
        self.assertIsNone(stock.current_price)
        self.assertIsNone(stock.currency)

    def test_malformed_optional_yahoo_values_use_none_without_crashing(self):
        stock = stock_from_yahoo_info(
            {
                "symbol": "NVDA",
                "currentPrice": 200.75,
                "marketCap": "too large",
                "returnOnEquity": "unknown",
                "grossMargins": object(),
                "totalCash": 1.5,
                "priceToBook": float("nan"),
                "longBusinessSummary": 123,
                "sector": ["Technology"],
            },
            "NVDA",
        )

        self.assertEqual(stock.current_price, 200.75)
        self.assertIsNone(stock.market_cap)
        self.assertIsNone(stock.return_on_equity)
        self.assertIsNone(stock.gross_margin)
        self.assertIsNone(stock.total_cash)
        self.assertIsNone(stock.price_to_book)
        self.assertIsNone(stock.company_summary)
        self.assertIsNone(stock.sector)

    def test_validate_stock_rejects_missing_current_price(self):
        stock = stock_from_yahoo_info({"symbol": "MISSING"}, "MISSING")

        with self.assertRaises(StockDataError):
            validate_stock(stock)

    @patch("stock_service.yf.Ticker")
    def test_fetch_stock_from_yahoo_wraps_network_error(self, mock_ticker):
        mock_yahoo_stock = Mock()
        type(mock_yahoo_stock).info = property(Mock(side_effect=OSError("network error")))
        mock_ticker.return_value = mock_yahoo_stock

        with self.assertRaises(StockServiceError):
            fetch_stock_from_yahoo("NVDA")


class StockServiceCacheTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        self.now = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

    def tearDown(self):
        self.temp_dir.cleanup()

    def sample_stock(self, symbol="NVDA", price=200.75):
        return Stock(
            symbol=symbol,
            company_name="NVIDIA Corporation",
            current_price=price,
            currency="USD",
        )

    def test_cache_hit_does_not_query_yahoo(self):
        save_stock(self.sample_stock(), self.db_path, fetched_at=self.now)

        with patch("database.utc_now", return_value=self.now + timedelta(hours=1)):
            with patch("stock_service.fetch_stock_from_yahoo") as mock_fetch:
                stock = get_stock("NVDA", db_path=self.db_path)

        mock_fetch.assert_not_called()
        self.assertEqual(stock.symbol, "NVDA")
        self.assertEqual(stock.current_price, 200.75)

    def test_explicit_refresh_bypasses_a_valid_cache(self):
        save_stock(self.sample_stock(price=200.75), self.db_path, fetched_at=self.now)
        yahoo_stock = self.sample_stock(price=210.5)

        with patch("database.utc_now", return_value=self.now + timedelta(hours=1)):
            with patch("stock_service.fetch_stock_from_yahoo", return_value=yahoo_stock) as mock_fetch:
                stock = get_stock("NVDA", db_path=self.db_path, force_refresh=True)

        mock_fetch.assert_called_once_with("NVDA")
        self.assertEqual(stock.current_price, 210.5)

    def test_cache_miss_queries_yahoo_and_writes_cache(self):
        yahoo_stock = self.sample_stock(price=210.5)

        with patch("stock_service.fetch_stock_from_yahoo", return_value=yahoo_stock) as mock_fetch:
            stock = get_stock("NVDA", db_path=self.db_path)

        mock_fetch.assert_called_once_with("NVDA")
        self.assertEqual(stock.current_price, 210.5)

        cached_stock = get_stock("NVDA", db_path=self.db_path)
        self.assertEqual(cached_stock.current_price, 210.5)

    def test_expired_cache_queries_yahoo_again(self):
        save_stock(
            self.sample_stock(price=200.75),
            self.db_path,
            fetched_at=self.now - timedelta(hours=25),
        )
        yahoo_stock = self.sample_stock(price=215.0)

        with patch("database.utc_now", return_value=self.now):
            with patch("stock_service.fetch_stock_from_yahoo", return_value=yahoo_stock) as mock_fetch:
                stock = get_stock("NVDA", db_path=self.db_path)

        mock_fetch.assert_called_once_with("NVDA")
        self.assertEqual(stock.current_price, 215.0)

    def test_schema_migration_expires_cache_and_queries_yahoo(self):
        self.create_old_stocks_table()
        self.insert_old_cache_row(fetched_at=self.now.isoformat())
        yahoo_stock = self.sample_stock(price=215.0)

        with patch("database.utc_now", return_value=self.now):
            with patch("stock_service.fetch_stock_from_yahoo", return_value=yahoo_stock) as mock_fetch:
                stock = get_stock("NVDA", db_path=self.db_path)

        mock_fetch.assert_called_once_with("NVDA")
        self.assertEqual(stock.current_price, 215.0)

    def test_cache_read_failure_falls_back_to_yahoo(self):
        yahoo_stock = self.sample_stock(price=220.0)

        with patch("live_data_store.LiveDataStore.get_cached_stock", side_effect=OSError("cache read failed")):
            with patch("stock_service.fetch_stock_from_yahoo", return_value=yahoo_stock):
                with self.assertLogs(level="WARNING"):
                    stock = get_stock("NVDA", db_path=self.db_path)

        self.assertEqual(stock.current_price, 220.0)

    def test_cache_write_failure_still_returns_yahoo_stock(self):
        yahoo_stock = self.sample_stock(price=225.0)

        with patch("stock_service.fetch_stock_from_yahoo", return_value=yahoo_stock):
            with patch("live_data_store.LiveDataStore.save_stock", side_effect=OSError("cache write failed")):
                with self.assertLogs(level="WARNING"):
                    stock = get_stock("NVDA", db_path=self.db_path)

        self.assertEqual(stock.current_price, 225.0)

    def create_old_stocks_table(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE stocks (
                    symbol TEXT PRIMARY KEY,
                    company_name TEXT,
                    current_price REAL,
                    currency TEXT,
                    market_cap INTEGER,
                    trailing_pe REAL,
                    forward_pe REAL,
                    trailing_eps REAL,
                    return_on_equity REAL,
                    sector TEXT,
                    industry TEXT,
                    fetched_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

    def insert_old_cache_row(self, fetched_at: str) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                """
                INSERT INTO stocks (
                    symbol,
                    company_name,
                    current_price,
                    currency,
                    market_cap,
                    trailing_pe,
                    forward_pe,
                    trailing_eps,
                    return_on_equity,
                    sector,
                    industry,
                    fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "NVDA",
                    "NVIDIA Corporation",
                    200.75,
                    "USD",
                    4879000000000,
                    57.68,
                    44.3,
                    3.48,
                    0.25,
                    "Technology",
                    "Semiconductors",
                    fetched_at,
                ),
            )
            connection.commit()
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
