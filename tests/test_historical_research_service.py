import re
import sys
import unittest
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from historical_research_service import build_historical_research_report
from historical_research_service import count_valid_periods
from historical_research_service import format_currency_amount
from historical_research_service import format_percentage_points
from historical_research_service import period_label
from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries


class HistoricalResearchServiceTestCase(unittest.TestCase):

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
        "undervalued",
        "overvalued",
        "買",
        "賣",
        "持有",
        "強勁",
        "疲弱",
        "健康",
        "惡化",
        "優秀",
        "低估",
        "高估",
        "一定",
        "必然",
        "造成",
        "導致",
        "證明",
    ]

    def period(
        self,
        year,
        revenue=None,
        net_income=None,
        eps=None,
        gross_margin=None,
        operating_margin=None,
        net_margin=None,
        operating_cash_flow=None,
        capital_expenditure=None,
        free_cash_flow=None,
        total_assets=None,
        total_debt=None,
        total_equity=None,
        cash=None,
        month=12,
        day=31,
    ):
        return HistoricalFinancialPeriod(
            symbol="TEST",
            period_end=date(year, month, day),
            period_year=year,
            currency="USD",
            revenue=revenue,
            net_income=net_income,
            eps=eps,
            gross_margin=gross_margin,
            operating_margin=operating_margin,
            net_margin=net_margin,
            operating_cash_flow=operating_cash_flow,
            capital_expenditure=capital_expenditure,
            free_cash_flow=free_cash_flow,
            total_assets=total_assets,
            total_debt=total_debt,
            total_equity=total_equity,
            cash_and_cash_equivalents=cash,
        )

    def series(self, periods):
        return HistoricalFinancialSeries(symbol="TEST", currency="USD", periods=periods)

    def test_revenue_consecutive_positive_yoy(self):
        report = build_historical_research_report(
            self.series([
                self.period(2023, revenue=100),
                self.period(2024, revenue=120),
                self.period(2025, revenue=150),
            ])
        )

        text = self.combined_text(report)
        self.assertIn("Revenue 連續兩期增加", text)
        self.assertIn("+20.00%", text)
        self.assertIn("+25.00%", text)

    def test_revenue_consecutive_negative_yoy(self):
        report = build_historical_research_report(
            self.series([
                self.period(2023, revenue=150),
                self.period(2024, revenue=120),
                self.period(2025, revenue=90),
            ])
        )

        self.assertIn("Revenue 連續兩期下降", self.combined_text(report))

    def test_revenue_decline_then_recovery(self):
        report = build_historical_research_report(
            self.series([
                self.period(2023, revenue=100),
                self.period(2024, revenue=80),
                self.period(2025, revenue=100),
            ])
        )

        text = self.combined_text(report)
        self.assertIn("Revenue 前期下降後回升", text)
        self.assertIn("FY2024 較前一年下降 20.00%", text)
        self.assertIn("FY2025 回升 +25.00%", text)

    def test_revenue_decline_then_two_year_recovery(self):
        report = build_historical_research_report(
            self.series([
                self.period(2022, revenue=100),
                self.period(2023, revenue=79),
                self.period(2024, revenue=96.704),
                self.period(2025, revenue=108.617),
            ])
        )

        text = self.combined_text(report)
        self.assertIn("Revenue 前期下降後連續回升", text)
        self.assertIn("FY2023 較前一年下降 21.00%", text)
        self.assertIn("FY2024 回升 +22.41%", text)
        self.assertIn("FY2025 再增加 +12.32%", text)

    def test_revenue_decline_then_two_year_recovery_requires_connected_chain(self):
        report = build_historical_research_report(
            self.series([
                self.period(2022, revenue=100),
                self.period(2023, revenue=80),
                self.period(2025, revenue=100),
                self.period(2026, revenue=120),
                self.period(2027, revenue=140),
            ])
        )

        text = self.combined_text(report)
        self.assertNotIn("Revenue 前期下降後連續回升", text)
        self.assertIn("Revenue 年度資料不連續", text)

    def test_revenue_decline_then_two_year_recovery_rejects_disconnected_changes(self):
        report = build_historical_research_report(
            self.series([
                self.period(2021, revenue=150),
                self.period(2022, revenue=100),
                self.period(2023, revenue=80),
                self.period(2025, revenue=100),
                self.period(2026, revenue=120),
                self.period(2027, revenue=140),
            ])
        )

        text = self.combined_text(report)
        self.assertIn("Revenue 連續兩期增加", text)
        self.assertNotIn("Revenue 前期下降後連續回升", text)

    def test_revenue_decline_then_two_year_recovery_requires_relative_changes(self):
        report = build_historical_research_report(
            self.series([
                self.period(2022, revenue=100),
                self.period(2023, revenue=0),
                self.period(2024, revenue=10),
                self.period(2025, revenue=20),
            ])
        )

        text = self.combined_text(report)
        self.assertNotIn("Revenue 前期下降後連續回升", text)
        self.assertNotIn("回升 N/A", text)

    def test_revenue_decline_then_two_year_recovery_rejects_zero_denominator(self):
        report = build_historical_research_report(
            self.series([
                self.period(2022, revenue=0),
                self.period(2023, revenue=10),
                self.period(2024, revenue=20),
                self.period(2025, revenue=30),
            ])
        )

        text = self.combined_text(report)
        self.assertNotIn("Revenue 前期下降後連續回升", text)
        self.assertNotIn("回升 N/A", text)

    def test_revenue_growth_then_decline(self):
        report = build_historical_research_report(
            self.series([
                self.period(2023, revenue=100),
                self.period(2024, revenue=130),
                self.period(2025, revenue=90),
            ])
        )

        self.assertIn("Revenue 前期增加後下降", self.combined_text(report))

    def test_revenue_missing_year_prevents_consecutive_trend(self):
        report = build_historical_research_report(
            self.series([
                self.period(2022, revenue=100),
                self.period(2024, revenue=130),
                self.period(2025, revenue=150),
            ])
        )

        text = self.combined_text(report)
        self.assertIn("Revenue 年度資料不連續", text)
        self.assertNotIn("2022 到 FY2025 連續", text)

    def test_revenue_insufficient_periods(self):
        report = build_historical_research_report(
            self.series([self.period(2025, revenue=100)])
        )

        text = self.combined_text(report)
        self.assertIn("Revenue 少於 2 個有效年度", text)
        self.assertEqual(count_valid_periods(report.series, "revenue"), 1)

    def test_revenue_up_net_income_down_and_reverse(self):
        up_down = build_historical_research_report(
            self.series([
                self.period(2024, revenue=100, net_income=20),
                self.period(2025, revenue=120, net_income=15),
            ])
        )
        self.assertIn("Revenue 增加但 Net Income 下降", self.combined_text(up_down))

        down_up = build_historical_research_report(
            self.series([
                self.period(2024, revenue=120, net_income=15),
                self.period(2025, revenue=100, net_income=20),
            ])
        )
        self.assertIn("Revenue 與 Net Income 最新年度方向不同", self.combined_text(down_up))

    def test_eps_decline_then_recovery_and_latest_missing(self):
        report = build_historical_research_report(
            self.series([
                self.period(2022, eps=10, net_income=100),
                self.period(2023, eps=8, net_income=80),
                self.period(2024, eps=9, net_income=90),
                self.period(2025, eps=None, net_income=95),
            ])
        )

        text = self.combined_text(report)
        self.assertIn("EPS 前期下降後回升", text)
        self.assertIn("Yahoo Finance 目前未提供 FY2025 EPS", text)
        self.assertIn("系統不自行計算 Yahoo 未提供的 EPS", text)

    def test_missing_eps_does_not_create_false_trend(self):
        report = build_historical_research_report(
            self.series([
                self.period(2023, eps=10),
                self.period(2024, eps=None),
                self.period(2025, eps=12),
            ])
        )

        text = self.combined_text(report)
        self.assertNotIn("EPS 連續兩期", text)
        self.assertNotIn("EPS 前期下降後回升", text)

    def test_margin_percentage_point_change_positive_and_negative(self):
        report = build_historical_research_report(
            self.series([
                self.period(2024, gross_margin=0.4964, operating_margin=0.30),
                self.period(2025, gross_margin=0.4750, operating_margin=0.35),
            ])
        )

        text = self.combined_text(report)
        self.assertIn("Gross Margin 最新年度下降", text)
        self.assertIn("2.14 percentage points", text)
        self.assertIn("Operating Margin 最新年度增加", text)
        self.assertNotIn("下降 4.31%", text)

    def test_missing_margin_does_not_crash(self):
        report = build_historical_research_report(
            self.series([
                self.period(2024, gross_margin=None),
                self.period(2025, gross_margin=None),
            ])
        )

        self.assertIsNotNone(report)
        self.assertIn("Gross Margin", self.combined_text(report))

    def test_cash_flow_positive_negative_fcf_turn_and_recovery(self):
        negative = build_historical_research_report(
            self.series([
                self.period(2023, operating_cash_flow=-10, free_cash_flow=10),
                self.period(2024, operating_cash_flow=-8, free_cash_flow=-5),
            ])
        )
        text = self.combined_text(negative)
        self.assertIn("Operating Cash Flow 為 USD -8，為負值", text)
        self.assertIn("Free Cash Flow 轉為負值", text)

        recovery = build_historical_research_report(
            self.series([
                self.period(2023, free_cash_flow=-5),
                self.period(2024, free_cash_flow=10),
            ])
        )
        self.assertIn("Free Cash Flow 回到正值", self.combined_text(recovery))

    def test_consecutive_positive_fcf(self):
        report = build_historical_research_report(
            self.series([
                self.period(2023, free_cash_flow=5),
                self.period(2024, free_cash_flow=10),
                self.period(2025, free_cash_flow=12),
            ])
        )

        self.assertIn("Free Cash Flow 連續年度為正", self.combined_text(report))

    def test_capex_absolute_spending_increase_and_decrease(self):
        increase = build_historical_research_report(
            self.series([
                self.period(2024, capital_expenditure=-18_910_000_000),
                self.period(2025, capital_expenditure=-25_420_000_000),
            ])
        )
        self.assertIn("由 USD 18.91B 增加至 USD 25.42B", self.combined_text(increase))
        self.assertNotIn("CapEx 下降", self.combined_text(increase))

        decrease = build_historical_research_report(
            self.series([
                self.period(2024, capital_expenditure=-25_420_000_000),
                self.period(2025, capital_expenditure=-18_910_000_000),
            ])
        )
        self.assertIn("由 USD 25.42B 下降至 USD 18.91B", self.combined_text(decrease))

    def test_financial_position_cash_and_debt_changes(self):
        report = build_historical_research_report(
            self.series([
                self.period(2023, cash=100, total_debt=15, total_assets=500, total_equity=300),
                self.period(2024, cash=120, total_debt=18, total_assets=550, total_equity=320),
                self.period(2025, cash=140, total_debt=13, total_assets=600, total_equity=360),
            ])
        )

        text = self.combined_text(report)
        self.assertIn("Cash 最新年度增加", text)
        self.assertIn("Total Debt 最新年度下降", text)
        self.assertIn("Cash 高於 Total Debt", text)

    def test_missing_balance_sheet_metric_becomes_data_quality(self):
        report = build_historical_research_report(
            self.series([
                self.period(2024, revenue=100),
                self.period(2025, revenue=120),
            ])
        )

        self.assertIn("部分歷史指標缺漏", self.combined_text(report))

    def test_cross_metric_revenue_up_margin_down_and_earnings_up_fcf_down(self):
        report = build_historical_research_report(
            self.series([
                self.period(
                    2024,
                    revenue=100,
                    net_income=20,
                    operating_margin=0.30,
                    free_cash_flow=20,
                ),
                self.period(
                    2025,
                    revenue=130,
                    net_income=25,
                    operating_margin=0.25,
                    free_cash_flow=10,
                ),
            ])
        )

        text = self.combined_text(report)
        self.assertIn("Revenue 增加但 Operating Margin 下降", text)
        self.assertIn("Net Income 增加但 Free Cash Flow 下降", text)

    def test_missing_cross_metric_prevents_observation(self):
        report = build_historical_research_report(
            self.series([
                self.period(2024, revenue=100, net_income=20),
                self.period(2025, revenue=130, net_income=None),
            ])
        )

        self.assertNotIn("Revenue 增加但 Net Income 下降", self.combined_text(report))

    def test_nvda_fy2026_period_label_does_not_claim_calendar_year(self):
        period = HistoricalFinancialPeriod(
            symbol="NVDA",
            period_end=date(2026, 1, 31),
            period_year=2026,
        )

        self.assertEqual(period_label(period), "FY2026")
        report = build_historical_research_report(
            HistoricalFinancialSeries(
                symbol="NVDA",
                currency="USD",
                periods=[
                    self.period(2025, revenue=100, month=1, day=31),
                    self.period(2026, revenue=120, month=1, day=31),
                ],
            )
        )
        self.assertIn("FY2026 Revenue", self.combined_text(report))
        self.assertNotIn("calendar year 2026", self.combined_text(report).lower())

    def test_next_steps_are_deterministic_grouped_and_not_duplicates(self):
        series = self.series([
            self.period(2024, revenue=100, free_cash_flow=10),
            self.period(2025, revenue=120, free_cash_flow=-5),
        ])

        first = build_historical_research_report(series)
        second = build_historical_research_report(series)

        self.assertEqual(first.next_steps, second.next_steps)
        self.assertTrue(first.next_steps)
        observation_messages = {
            observation.what_happened
            for observation in first.observations
        }
        next_step_items = {
            item
            for step in first.next_steps
            for item in step.items
        }
        self.assertTrue(observation_messages.isdisjoint(next_step_items))

    def test_language_safety(self):
        report = build_historical_research_report(
            self.series([
                self.period(
                    2024,
                    revenue=100,
                    net_income=20,
                    operating_margin=0.30,
                    free_cash_flow=20,
                    capital_expenditure=-10,
                    cash=10,
                    total_debt=20,
                ),
                self.period(
                    2025,
                    revenue=130,
                    net_income=15,
                    operating_margin=0.20,
                    free_cash_flow=-5,
                    capital_expenditure=-15,
                    cash=15,
                    total_debt=25,
                ),
            ])
        )

        text = self.combined_text(report).lower()
        for term in self.forbidden_terms:
            self.assert_not_forbidden(term, text)

    def test_beginner_friendly_formatting_helpers(self):
        self.assertEqual(format_currency_amount(595_970_000_000, "TWD"), "TWD 595.97B")
        self.assertEqual(format_percentage_points(-0.0214), "2.14 percentage points")

    def combined_text(self, report):
        observation_text = [
            text
            for observation in report.observations
            for text in [
                observation.category,
                observation.title,
                observation.metric,
                observation.what_happened,
                observation.why_it_matters,
                *observation.what_to_check,
            ]
        ]
        next_step_text = [
            text
            for step in report.next_steps
            for text in [step.category, step.title, step.metric, *step.items]
        ]
        return " ".join(observation_text + next_step_text)

    def assert_not_forbidden(self, term, text):
        if term.isascii():
            pattern = r"\b" + re.escape(term) + r"\b"
            self.assertIsNone(re.search(pattern, text))
        else:
            self.assertNotIn(term, text)


if __name__ == "__main__":
    unittest.main()
