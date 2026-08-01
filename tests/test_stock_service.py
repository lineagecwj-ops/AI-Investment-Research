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
        self.assertEqual(stock.sector, "Technology")
        self.assertEqual(stock.industry, "Semiconductors")

    def test_missing_yahoo_info_uses_none_without_crashing(self):
        stock = stock_from_yahoo_info({}, "MISSING")

        self.assertEqual(stock.symbol, "MISSING")
        self.assertIsNone(stock.company_name)
        self.assertIsNone(stock.current_price)
        self.assertIsNone(stock.currency)

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

    def test_cache_read_failure_falls_back_to_yahoo(self):
        yahoo_stock = self.sample_stock(price=220.0)

        with patch("stock_service.get_cached_stock", side_effect=OSError("cache read failed")):
            with patch("stock_service.fetch_stock_from_yahoo", return_value=yahoo_stock):
                with self.assertLogs(level="WARNING"):
                    stock = get_stock("NVDA", db_path=self.db_path)

        self.assertEqual(stock.current_price, 220.0)

    def test_cache_write_failure_still_returns_yahoo_stock(self):
        yahoo_stock = self.sample_stock(price=225.0)

        with patch("stock_service.fetch_stock_from_yahoo", return_value=yahoo_stock):
            with patch("stock_service.save_stock", side_effect=OSError("cache write failed")):
                with self.assertLogs(level="WARNING"):
                    stock = get_stock("NVDA", db_path=self.db_path)

        self.assertEqual(stock.current_price, 225.0)


if __name__ == "__main__":
    unittest.main()
