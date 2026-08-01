import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from stock_service import stock_from_yahoo_info


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
        self.assertEqual(stock.price, 200.75)
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


if __name__ == "__main__":
    unittest.main()
