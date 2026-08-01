import re
import sys
import unittest
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from historical_interpretation_presentation import ATTENTION_COLOR_EXPLANATION
from historical_interpretation_presentation import build_historical_highlights
from historical_interpretation_presentation import build_next_step_display_groups
from historical_interpretation_presentation import DETAILED_INTERPRETATION_CATEGORY_ORDER
from historical_interpretation_presentation import FY_PERIOD_CAPTION
from historical_interpretation_presentation import group_detailed_interpretation
from historical_research_service import build_historical_research_report
from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries
from research_service import ResearchNextStep
from research_service import ResearchObservation


class HistoricalInterpretationPresentationTestCase(unittest.TestCase):

    forbidden_terms = [
        "buy",
        "sell",
        "hold",
        "score",
        "rating",
        "target price",
        "strong",
        "weak",
        "healthy",
        "unhealthy",
        "強勁",
        "疲弱",
        "健康",
        "惡化",
        "優秀",
        "低估",
        "高估",
        "值得買",
        "應該賣",
    ]

    def observation(self, category, title, summary):
        return ResearchObservation(
            category=category,
            title=title,
            metric="test_metric",
            what_happened=summary,
            why_it_matters="研究脈絡。",
            what_to_check=["下一步"],
            observation_type="info",
        )

    def test_highlights_are_deterministic_limited_ordered_and_unique(self):
        observations = [
            self.observation("Cash Flow（現金流）", "最新年度 Free Cash Flow 狀態", "FY2025 FCF 維持正值。"),
            self.observation("Revenue（營收）", "Revenue 連續兩期增加", "FY2024 與 FY2025 Revenue 連續增加。"),
            self.observation("Revenue（營收）", "最新年度 Revenue 增加", "FY2025 Revenue 增加。"),
            self.observation("Margins（利潤率）", "Gross Margin 最新年度下降", "FY2025 Gross Margin 下降 2.00 percentage points。"),
            self.observation("Data Quality（資料完整性）", "最新年度 EPS unavailable", "Yahoo Finance 目前未提供 FY2025 EPS。"),
            self.observation("Financial Position（財務結構）", "Cash 最新年度增加", "FY2025 Cash 增加。"),
            self.observation("Earnings（獲利）", "Revenue 與 Net Income 最新年度方向不同", "FY2025 Revenue 增加，但 Net Income 下降。"),
            self.observation("Revenue（營收）", "Revenue 連續兩期增加", "FY2024 與 FY2025 Revenue 連續增加。"),
        ]

        first = build_historical_highlights(observations, max_count=4)
        second = build_historical_highlights(observations, max_count=4)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 4)
        self.assertEqual(
            [highlight.category for highlight in first],
            [
                "Revenue（營收）",
                "Earnings（獲利）",
                "Margins（利潤率）",
                "Cash Flow（現金流）",
            ],
        )
        self.assertEqual(first[0].title, "Revenue 連續兩期增加")
        self.assertEqual(
            len({highlight.summary for highlight in first}),
            len(first),
        )

    def test_2454_like_highlight_prefers_decline_then_recovery(self):
        series = HistoricalFinancialSeries(
            symbol="2454.TW",
            currency="TWD",
            periods=[
                HistoricalFinancialPeriod(
                    symbol="2454.TW",
                    period_end=date(2022, 12, 31),
                    period_year=2022,
                    currency="TWD",
                    revenue=548_796_030_000,
                    net_income=118_000_000_000,
                    eps=74.23,
                    gross_margin=0.49,
                    operating_margin=0.22,
                    net_margin=0.21,
                    free_cash_flow=80_000_000_000,
                    capital_expenditure=-18_000_000_000,
                    cash_and_cash_equivalents=140_000_000_000,
                    total_debt=16_000_000_000,
                ),
                HistoricalFinancialPeriod(
                    symbol="2454.TW",
                    period_end=date(2023, 12, 31),
                    period_year=2023,
                    currency="TWD",
                    revenue=433_446_330_000,
                    net_income=76_000_000_000,
                    eps=48.34,
                    gross_margin=0.47,
                    operating_margin=0.17,
                    net_margin=0.17,
                    free_cash_flow=70_000_000_000,
                    capital_expenditure=-20_000_000_000,
                    cash_and_cash_equivalents=160_000_000_000,
                    total_debt=18_000_000_000,
                ),
                HistoricalFinancialPeriod(
                    symbol="2454.TW",
                    period_end=date(2024, 12, 31),
                    period_year=2024,
                    currency="TWD",
                    revenue=530_585_886_000,
                    net_income=105_000_000_000,
                    eps=66.78,
                    gross_margin=0.4964,
                    operating_margin=0.1929,
                    net_margin=0.1978,
                    free_cash_flow=90_000_000_000,
                    capital_expenditure=-18_910_000_000,
                    cash_and_cash_equivalents=200_000_000_000,
                    total_debt=18_290_000_000,
                ),
                HistoricalFinancialPeriod(
                    symbol="2454.TW",
                    period_end=date(2025, 12, 31),
                    period_year=2025,
                    currency="TWD",
                    revenue=595_965_682_000,
                    net_income=100_000_000_000,
                    eps=None,
                    gross_margin=0.475,
                    operating_margin=0.1736,
                    net_margin=0.168,
                    free_cash_flow=95_000_000_000,
                    capital_expenditure=-25_420_000_000,
                    cash_and_cash_equivalents=235_000_000_000,
                    total_debt=13_730_000_000,
                ),
            ],
        )

        report = build_historical_research_report(series)
        highlights = build_historical_highlights(report.observations)
        text = " ".join(highlight.summary for highlight in highlights)

        self.assertLessEqual(len(highlights), 6)
        self.assertIn("FY2023 較前一年下降", text)
        self.assertIn("FY2024 回升", text)
        self.assertIn("FY2025 再增加", text)
        self.assertIn("Yahoo Finance 目前未提供 FY2025 EPS", text)
        self.assertIn("percentage points", text)
        self.assertIn("Capital Expenditure 現金支出規模", text)

    def test_nvda_fy2026_highlight_uses_fiscal_period_wording(self):
        observations = [
            self.observation("Revenue（營收）", "最新年度 Revenue 增加", "FY2026 Revenue 較 FY2025 增加 +65.47%。"),
        ]

        highlights = build_historical_highlights(observations)
        text = " ".join(highlight.summary for highlight in highlights)

        self.assertIn("FY2026", text)
        self.assertNotIn("calendar year", text.lower())
        self.assertNotIn("未來年度", text)
        self.assertIn("FY 代表財務期間", FY_PERIOD_CAPTION)

    def test_detailed_interpretation_groups_by_category_order(self):
        observations = [
            self.observation("Data Quality（資料完整性）", "部分歷史指標缺漏", "缺漏。"),
            self.observation("Margins（利潤率）", "Gross Margin 最新年度下降", "Margin 下降。"),
            self.observation("Revenue（營收）", "最新年度 Revenue 增加", "Revenue 增加。"),
            self.observation("Margins（利潤率）", "Operating Margin 最新年度下降", "Operating Margin 下降。"),
        ]

        groups = group_detailed_interpretation(observations)

        self.assertEqual(
            [group.category for group in groups],
            ["Revenue（營收）", "Margins（利潤率）", "Data Quality（資料完整性）"],
        )
        self.assertEqual(len(groups[1].observations), 2)
        self.assertIn("Cross Metric（跨指標）", DETAILED_INTERPRETATION_CATEGORY_ORDER)

    def test_attention_explanation_says_not_negative_or_recommendation(self):
        self.assertIn("黃色代表值得進一步確認的研究項目", ATTENTION_COLOR_EXPLANATION)
        self.assertIn("不代表負面訊號或投資建議", ATTENTION_COLOR_EXPLANATION)
        self.assertNotIn("green", ATTENTION_COLOR_EXPLANATION.lower())
        self.assertNotIn("red", ATTENTION_COLOR_EXPLANATION.lower())

    def test_next_steps_deduplicate_limit_and_keep_overflow(self):
        steps = [
            ResearchNextStep(
                category="Revenue（營收）",
                title="A",
                metric="revenue",
                items=[
                    "比較主要產品或地區營收變化",
                    " 比較主要產品或地區營收變化 ",
                    "Compare peer Revenue trends",
                    "compare peer revenue trends",
                    "查看管理層需求說明",
                    "保留 overflow item",
                ],
            ),
            ResearchNextStep(
                category="Cash Flow（現金流）",
                title="B",
                metric="free_cash_flow",
                items=["確認 Capital Expenditure 的主要用途"],
            ),
        ]

        groups = build_next_step_display_groups(steps, per_category_limit=3)
        revenue_group = groups[0]

        self.assertEqual(revenue_group.category, "Revenue（營收）")
        self.assertEqual(
            revenue_group.visible_items,
            [
                "比較主要產品或地區營收變化",
                "Compare peer Revenue trends",
                "查看管理層需求說明",
            ],
        )
        self.assertEqual(revenue_group.overflow_items, ["保留 overflow item"])
        self.assertEqual(groups[1].category, "Cash Flow（現金流）")

    def test_next_steps_have_page_level_visible_limit(self):
        steps = [
            ResearchNextStep(
                category="Revenue（營收）",
                title="A",
                metric="revenue",
                items=["R1", "R2", "R3"],
            ),
            ResearchNextStep(
                category="Earnings（獲利）",
                title="B",
                metric="earnings",
                items=["E1", "E2", "E3"],
            ),
            ResearchNextStep(
                category="Margins（利潤率）",
                title="C",
                metric="margins",
                items=["M1", "M2", "M3"],
            ),
        ]

        groups = build_next_step_display_groups(
            steps,
            per_category_limit=3,
            max_visible_total=5,
        )

        visible_total = sum(len(group.visible_items) for group in groups)
        overflow_total = sum(len(group.overflow_items) for group in groups)

        self.assertEqual(visible_total, 5)
        self.assertEqual(overflow_total, 4)
        self.assertEqual(groups[1].visible_items, ["E1", "E2"])
        self.assertEqual(groups[1].overflow_items, ["E3"])
        self.assertEqual(groups[2].visible_items, [])
        self.assertEqual(groups[2].overflow_items, ["M1", "M2", "M3"])

    def test_highlight_language_safety(self):
        observations = [
            self.observation("Revenue（營收）", "Revenue 連續兩期增加", "FY2024 與 FY2025 Revenue 連續增加。"),
            self.observation("Earnings（獲利）", "最新年度 EPS unavailable", "Yahoo Finance 目前未提供 FY2025 EPS。"),
        ]
        text = " ".join(
            value
            for highlight in build_historical_highlights(observations)
            for value in [highlight.category, highlight.title, highlight.summary]
        ).lower()

        for term in self.forbidden_terms:
            if term.isascii():
                self.assertIsNone(re.search(r"\b" + re.escape(term) + r"\b", text))
            else:
                self.assertNotIn(term, text)

    def test_app_uses_collapsed_expanders_for_detailed_interpretation(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("Historical Highlights（歷史重點）", app_source)
        self.assertIn("Detailed Interpretation（詳細趨勢解讀）", app_source)
        self.assertIn("expanded=False", app_source)
        self.assertIn("ATTENTION_COLOR_EXPLANATION", app_source)


if __name__ == "__main__":
    unittest.main()
