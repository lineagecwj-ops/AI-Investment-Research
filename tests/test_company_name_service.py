import sys
import tempfile
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from company_name_service import TPEX_OTC_COMPANIES_URL
from company_name_service import TWSE_LISTED_COMPANIES_URL
from company_name_service import clear_company_name_memory_cache
from company_name_service import get_display_company_name
from company_name_service import get_localized_company_name
from company_name_service import load_taiwan_company_names
from company_name_service import parse_company_name_records
from models import Stock


class TaiwanCompanyNameServiceTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.temp_dir.name) / "taiwan_company_names.json"
        self.now = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
        clear_company_name_memory_cache()

    def tearDown(self):
        clear_company_name_memory_cache()
        self.temp_dir.cleanup()

    def fake_official_response(self, url):
        if url == TWSE_LISTED_COMPANIES_URL:
            return [
                {"公司代號": "2330", "公司簡稱": "台積電"},
                {"公司代號": "2454", "公司簡稱": "聯發科"},
            ]
        if url == TPEX_OTC_COMPANIES_URL:
            return [
                {"公司代號": "6488", "公司簡稱": "環球晶"},
            ]

        return []

    def test_known_twse_stock_uses_localized_name(self):
        names = load_taiwan_company_names(
            cache_path=self.cache_path,
            fetch_json=self.fake_official_response,
            now=self.now,
        )

        self.assertEqual(names["2330.TW"], "台積電")
        self.assertEqual(get_localized_company_name("2330.TW", self.cache_path), "台積電")

    def test_known_tpex_stock_uses_localized_name(self):
        names = load_taiwan_company_names(
            cache_path=self.cache_path,
            fetch_json=self.fake_official_response,
            now=self.now,
        )

        self.assertEqual(names["6488.TWO"], "環球晶")
        self.assertEqual(get_localized_company_name("6488.TWO", self.cache_path), "環球晶")

    def test_unknown_taiwan_symbol_falls_back_to_yahoo_english(self):
        load_taiwan_company_names(
            cache_path=self.cache_path,
            fetch_json=self.fake_official_response,
            now=self.now,
        )
        stock = Stock(
            symbol="9999.TW",
            company_name="Unknown Taiwan Company Limited",
        )

        self.assertEqual(
            get_display_company_name(stock, cache_path=self.cache_path),
            "Unknown Taiwan Company Limited",
        )

    def test_us_stock_remains_yahoo_english(self):
        stock = Stock(symbol="NVDA", company_name="NVIDIA Corporation")

        self.assertEqual(
            get_display_company_name(stock, cache_path=self.cache_path),
            "NVIDIA Corporation",
        )

    def test_api_source_failure_falls_back_to_yahoo_english(self):
        stock = Stock(
            symbol="2330.TW",
            company_name="Taiwan Semiconductor Manufacturing Company Limited",
        )

        with patch("company_name_service.request_json", side_effect=OSError("offline")):
            self.assertEqual(
                get_display_company_name(stock, cache_path=self.cache_path),
                "Taiwan Semiconductor Manufacturing Company Limited",
            )

    def test_parse_records_accepts_official_chinese_fields(self):
        names = parse_company_name_records(
            [{"公司代號": "2330", "公司簡稱": "台積電"}],
            ".TW",
        )

        self.assertEqual(names, {"2330.TW": "台積電"})

    def test_fresh_cache_avoids_refetching_official_sources(self):
        load_taiwan_company_names(
            cache_path=self.cache_path,
            fetch_json=self.fake_official_response,
            now=self.now,
        )
        clear_company_name_memory_cache()

        with patch("company_name_service.request_json") as mock_request:
            self.assertEqual(
                get_localized_company_name("2454.TW", self.cache_path),
                "聯發科",
            )

        mock_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
