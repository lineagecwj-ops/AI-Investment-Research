import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from company_name_service import TPEX_OTC_COMPANIES_URL
from company_name_service import TWSE_LISTED_COMPANIES_URL
from company_summary_service import build_company_summary_display
from company_summary_service import build_official_summary
from company_summary_service import clear_company_summary_memory_cache
from company_summary_service import parse_business_items
from company_summary_service import shorten_summary
from models import Stock


class CompanySummaryServiceTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.temp_dir.name) / "taiwan_company_summaries.json"
        clear_company_summary_memory_cache()

    def tearDown(self):
        clear_company_summary_memory_cache()
        self.temp_dir.cleanup()

    def fake_official_response(self, url):
        if url == TWSE_LISTED_COMPANIES_URL:
            return [
                {
                    "公司代號": "2330",
                    "公司名稱": "台灣積體電路製造股份有限公司",
                    "產業別": "半導體業",
                    "營利事業統一編號": "22099131",
                },
                {
                    "公司代號": "2454",
                    "公司名稱": "聯發科技股份有限公司",
                    "產業別": "半導體業",
                    "營利事業統一編號": "84149961",
                },
            ]
        if url == TPEX_OTC_COMPANIES_URL:
            return []
        if "22099131" in url:
            return [
                {
                    "Business_Accounting_NO": "22099131",
                    "Company_Name": "台灣積體電路製造股份有限公司",
                    "Cmp_Business": [
                        {"Business_Seq_NO": "0001", "Business_Item": "CC01080", "Business_Item_Desc": "電子零組件製造業"},
                        {"Business_Seq_NO": "0002", "Business_Item": "CC01090", "Business_Item_Desc": "電池製造業"},
                        {"Business_Seq_NO": "0003", "Business_Item": "       ", "Business_Item_Desc": "依客戶之訂單與其提供之產品設計說明，以從事製造與銷售積體電路。"},
                    ],
                }
            ]
        if "84149961" in url:
            return [
                {
                    "Business_Accounting_NO": "84149961",
                    "Company_Name": "聯發科技股份有限公司",
                    "Cmp_Business": [
                        {"Business_Seq_NO": "0001", "Business_Item": "CC01080", "Business_Item_Desc": "電子零組件製造業"},
                        {"Business_Seq_NO": "0002", "Business_Item": "F401010", "Business_Item_Desc": "國際貿易業"},
                        {"Business_Seq_NO": "0003", "Business_Item": "I301010", "Business_Item_Desc": "資訊軟體服務業"},
                        {"Business_Seq_NO": "0004", "Business_Item": "I501010", "Business_Item_Desc": "產品設計業"},
                    ],
                }
            ]

        return []

    def test_2330_uses_official_localized_summary(self):
        original_summary = "Yahoo English summary must remain raw."
        summary = build_company_summary_display(
            Stock(
                symbol="2330.TW",
                company_name="Taiwan Semiconductor Manufacturing Company Limited",
                company_summary=original_summary,
            ),
            cache_path=self.cache_path,
            fetch_json=self.fake_official_response,
        )

        self.assertTrue(summary.is_localized)
        self.assertEqual(summary.section_title, "公司登記業務概覽")
        self.assertIn("台灣積體電路製造股份有限公司", summary.short_summary)
        self.assertIn("電子零組件製造業", summary.short_summary)
        self.assertIn("官方登記營業項目", summary.full_summary)
        self.assertEqual(summary.original_yahoo_summary, original_summary)

    def test_2454_uses_official_localized_summary(self):
        summary = build_company_summary_display(
            Stock(
                symbol="2454.TW",
                company_name="MediaTek Inc.",
                company_summary="Yahoo English summary must remain raw.",
            ),
            cache_path=self.cache_path,
            fetch_json=self.fake_official_response,
        )

        self.assertTrue(summary.is_localized)
        self.assertIn("聯發科技股份有限公司", summary.short_summary)
        self.assertIn("電子零組件製造業", summary.short_summary)
        self.assertIn("資訊軟體服務業", summary.short_summary)

    def test_parse_business_items_supports_real_nested_moea_schema(self):
        records = [
            {
                "Business_Accounting_NO": "84149961",
                "Cmp_Business": [
                    {"Business_Item_Desc": "電子零組件製造業"},
                    {"Business_Item_Desc": "  國際貿易業  "},
                    {"Business_Item_Desc": ""},
                    {"Business_Item_Desc": "電子零組件製造業"},
                    {"Business_Item_Desc": "資訊軟體服務業"},
                ],
            }
        ]

        self.assertEqual(
            parse_business_items(records),
            ["電子零組件製造業", "國際貿易業", "資訊軟體服務業"],
        )

    def test_parse_business_items_handles_empty_missing_and_malformed_nested_schema(self):
        records = [
            {"Cmp_Business": []},
            {"Company_Name": "Missing business field"},
            {"Cmp_Business": [None, "bad", {"Business_Item_Desc": "   "}]},
        ]

        self.assertEqual(parse_business_items(records), [])

    def test_parse_business_items_keeps_flat_field_backward_compatibility(self):
        records = [
            {"Business_Item_Desc": "電子零組件製造業"},
            {"Business_Item_Desc": "電子零組件製造業"},
            {"營業項目": "資訊軟體服務業"},
        ]

        self.assertEqual(parse_business_items(records), ["電子零組件製造業", "資訊軟體服務業"])

    def test_numeric_twse_industry_code_is_not_displayed_as_industry_name(self):
        summary = build_official_summary(
            {
                "symbol": "2454.TW",
                "code": "2454",
                "name": "聯發科技股份有限公司",
                "industry": "24",
            },
            ["電子零組件製造業"],
        )

        self.assertNotIn("屬於 24 產業", summary.short_summary)

    def test_localized_summary_disclaimer_clarifies_registration_scope(self):
        summary = build_company_summary_display(
            Stock(
                symbol="2454.TW",
                company_name="MediaTek Inc.",
                company_summary="MediaTek Inc. designs chips.",
            ),
            cache_path=self.cache_path,
            fetch_json=self.fake_official_response,
        )
        combined_text = " ".join(
            [
                summary.section_title,
                summary.short_summary,
                summary.full_summary or "",
                summary.source_note,
            ]
        )

        self.assertIn("登記業務範圍", summary.source_note)
        self.assertIn("不代表各項業務的實際營收占比", summary.source_note)
        self.assertIn("主要產品", summary.source_note)
        self.assertIn("核心業務", summary.source_note)
        self.assertNotIn("主要從事", combined_text)
        self.assertNotIn("主要產品", summary.short_summary + (summary.full_summary or ""))
        self.assertNotIn("核心業務", summary.short_summary + (summary.full_summary or ""))

    def test_cached_localized_summary_uses_current_safe_disclaimer(self):
        self.cache_path.write_text(
            json.dumps(
                {
                    "fetched_at": "2999-01-01T00:00:00+00:00",
                    "summaries": {
                        "2454.TW": {
                            "short_summary": "聯發科技股份有限公司（2454）登記營業項目包含：資訊軟體服務業。",
                            "full_summary": "官方登記營業項目：\n- 資訊軟體服務業",
                            "source_note": "舊版公司簡介使用台灣官方公開資料整理。",
                            "is_localized": True,
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        summary = build_company_summary_display(
            Stock(
                symbol="2454.TW",
                company_name="MediaTek Inc.",
                company_summary="MediaTek Inc. designs chips.",
            ),
            cache_path=self.cache_path,
            fetch_json=self.fake_official_response,
        )

        self.assertEqual(summary.section_title, "公司登記業務概覽")
        self.assertIn("登記業務範圍", summary.source_note)
        self.assertIn("不代表各項業務的實際營收占比", summary.source_note)
        self.assertEqual(summary.original_yahoo_summary, "MediaTek Inc. designs chips.")

    def test_no_localized_summary_falls_back_to_english_without_overwriting_stock(self):
        original_summary = (
            "NVIDIA builds accelerated computing platforms. "
            "It serves several markets. The original text remains unchanged."
        )
        stock = Stock(
            symbol="NVDA",
            company_name="NVIDIA Corporation",
            company_summary=original_summary,
        )

        summary = build_company_summary_display(stock, cache_path=self.cache_path)

        self.assertFalse(summary.is_localized)
        self.assertEqual(summary.section_title, "公司簡介")
        self.assertIn("NVIDIA builds accelerated computing platforms.", summary.short_summary)
        self.assertEqual(summary.full_summary, original_summary)
        self.assertEqual(summary.full_summary_title, "查看 Yahoo Finance 詳細公司介紹")
        self.assertIsNone(summary.original_yahoo_summary)
        self.assertEqual(stock.company_summary, original_summary)

    def test_empty_summary_returns_friendly_na_message(self):
        summary = build_company_summary_display(
            Stock(symbol="EMPTY", company_name="Empty Inc.", company_summary=""),
            cache_path=self.cache_path,
        )

        self.assertEqual(summary.short_summary, "公司簡介目前為 N/A。")
        self.assertIsNone(summary.full_summary)

    def test_short_summary_renderer_supports_primary_and_full_content(self):
        long_summary = "First sentence. Second sentence. Third sentence. Fourth sentence."

        self.assertEqual(
            shorten_summary(long_summary, max_sentences=2),
            "First sentence. Second sentence.",
        )

    def test_renderer_can_show_official_and_yahoo_summaries(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("summary.section_title", app_source)
        self.assertIn("summary.full_summary_title", app_source)
        self.assertIn("summary.original_yahoo_summary", app_source)
        self.assertIn("查看 Yahoo Finance 詳細公司介紹", app_source)

    def test_partial_data_does_not_crash(self):
        summary = build_company_summary_display(Stock(symbol=None), cache_path=self.cache_path)

        self.assertEqual(summary.short_summary, "公司簡介目前為 N/A。")


if __name__ == "__main__":
    unittest.main()
