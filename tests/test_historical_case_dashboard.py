import sys
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from historical_case_dashboard import build_case_chart
from historical_case_dashboard import build_case_request_fingerprint
from historical_case_dashboard import build_case_summary_rows
from historical_case_dashboard import build_condition_detail_rows
from historical_case_dashboard import build_technical_summary_rows
from historical_case_dashboard import case_selector_label
from historical_case_dashboard import filter_case_views
from historical_case_dashboard import format_percentage_value
from historical_case_dashboard import format_price_value
from historical_case_dashboard import format_technical_metric_value
from historical_case_dashboard import sort_case_views
from historical_case_service import HistoricalCaseConditionDetail
from historical_case_service import HistoricalCasePricePoint
from historical_case_service import HistoricalCaseView
from models import OutcomeEvaluationStatus


class HistoricalCaseDashboardTestCase(unittest.TestCase):

    def point(self, trading_date, relative_index, *, hit=False):
        return HistoricalCasePricePoint(
            trading_date=trading_date,
            relative_bar_index=relative_index,
            raw_open=99.0,
            raw_high=105.0 + relative_index,
            raw_low=95.0,
            raw_close=100.0 + relative_index,
            adjusted_close=100.0 + relative_index,
            analysis_close=100.0 + relative_index,
            volume=1000,
            is_signal_date=relative_index == 0,
            is_target_hit_date=hit,
            before_or_after_signal="SIGNAL_DATE" if relative_index == 0 else "AFTER_SIGNAL",
        )

    def condition(self):
        return HistoricalCaseConditionDetail(
            metric="analysis_close",
            actual_value=100.0,
            operator=">",
            expected_value=95.0,
            secondary_metric="sma_20",
            secondary_actual_value=95.0,
            evaluation_status="MATCH",
            matched=True,
        )

    def case(self, status=OutcomeEvaluationStatus.HIT, *, signal_date=date(2025, 1, 2)):
        points = (
            self.point(date(2025, 1, 1), -1),
            self.point(signal_date, 0),
            self.point(date(2025, 1, 3), 1, hit=status is OutcomeEvaluationStatus.HIT),
        )
        return HistoricalCaseView(
            case_id=f"TEST|signal|{signal_date.isoformat()}|outcome",
            symbol="TEST",
            currency="USD",
            signal_id="signal",
            outcome_definition_id="outcome",
            signal_date=signal_date,
            signal_analysis_close=100.0,
            signal_raw_close=100.0,
            reference_high=110.0,
            reference_low=80.0,
            outcome_status=status,
            target_hit_date=date(2025, 1, 3) if status is OutcomeEvaluationStatus.HIT else None,
            target_hit_bar_index=1 if status is OutcomeEvaluationStatus.HIT else None,
            max_close_return=0.12,
            max_close_return_date=date(2025, 1, 3),
            max_adverse_return=-0.04,
            max_adverse_return_date=date(2025, 1, 1),
            end_of_window_return=0.05,
            horizon_bars=20,
            available_future_bars=20,
            pre_signal_bars=1,
            post_signal_bars=1,
            price_points=points,
            condition_details=(self.condition(),),
            technical_snapshot_summary=(("sma_20", 95.0), ("return_20d", 0.04)),
            is_window_complete_before=True,
            is_window_complete_after=True,
        )

    def test_percentage_and_price_formatters(self):
        self.assertEqual(format_percentage_value(0.0512), "5.12%")
        self.assertEqual(format_percentage_value(-0.064), "-6.40%")
        self.assertEqual(format_percentage_value(None), "N/A")
        self.assertEqual(format_price_value(123.456, "USD"), "USD 123.46")
        self.assertEqual(format_price_value(None, "USD"), "N/A")

    def test_technical_percentage_fields_are_formatted_as_percentages(self):
        self.assertEqual(format_technical_metric_value("return_20d", 0.04), "4.00%")
        self.assertEqual(format_technical_metric_value("sma_20", 95.0), "95.0000")

    def test_filter_resolved_cases_uses_hit_and_miss_only(self):
        cases = (
            self.case(OutcomeEvaluationStatus.HIT),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 4)),
            self.case(OutcomeEvaluationStatus.INCOMPLETE, signal_date=date(2025, 1, 5)),
            self.case(OutcomeEvaluationStatus.NOT_EVALUABLE, signal_date=date(2025, 1, 6)),
        )

        filtered = filter_case_views(cases, "Resolved Cases")

        self.assertEqual([case.outcome_status for case in filtered], [OutcomeEvaluationStatus.HIT, OutcomeEvaluationStatus.MISS])

    def test_filter_specific_status(self):
        cases = (
            self.case(OutcomeEvaluationStatus.HIT),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 4)),
        )

        self.assertEqual(filter_case_views(cases, "MISS")[0].outcome_status, OutcomeEvaluationStatus.MISS)

    def test_sort_newest_and_oldest(self):
        older = self.case(signal_date=date(2025, 1, 2))
        newer = self.case(signal_date=date(2025, 1, 5))

        self.assertEqual(sort_case_views((older, newer), "Newest")[0].signal_date, date(2025, 1, 5))
        self.assertEqual(sort_case_views((newer, older), "Oldest")[0].signal_date, date(2025, 1, 2))

    def test_selector_label_uses_neutral_case_language(self):
        self.assertEqual(case_selector_label(self.case()), "2025-01-02 | 達成研究目標（HIT） | 第 1 個交易日達標")
        self.assertEqual(case_selector_label(self.case(OutcomeEvaluationStatus.MISS)), "2025-01-02 | 未達研究目標（MISS）")

    def test_summary_rows_use_display_formatting(self):
        rows = build_case_summary_rows((self.case(),))

        self.assertEqual(rows[0]["結果狀態"], "達成研究目標（HIT）")
        self.assertEqual(rows[0]["參考高點"], "USD 110.00")
        self.assertEqual(rows[0]["最大有利變動"], "12.00%")
        self.assertEqual(rows[0]["最大不利變動"], "-4.00%")

    def test_condition_rows_preserve_trace_fields(self):
        rows = build_condition_detail_rows(self.case())

        self.assertEqual(rows[0]["指標"], "分析價格")
        self.assertEqual(rows[0]["運算子"], ">")
        self.assertEqual(rows[0]["預期值／比較指標"], "20 日均線")
        self.assertEqual(rows[0]["是否符合"], "是")

    def test_technical_summary_rows_are_display_ready(self):
        rows = build_technical_summary_rows(self.case())

        self.assertEqual(rows[0], {"指標": "20 日均線", "數值": "95.0000"})
        self.assertEqual(rows[1], {"指標": "20 日價格變化", "數值": "4.00%"})

    def test_request_fingerprint_changes_when_config_changes(self):
        base = build_case_request_fingerprint(
            symbol="2330.TW",
            signal_id="signal",
            outcome_definition_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
        )
        changed = build_case_request_fingerprint(
            symbol="2330.TW",
            signal_id="signal",
            outcome_definition_id="outcome",
            overlap_policy="COOLDOWN",
            cooldown_bars=20,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
        )

        self.assertNotEqual(base, changed)
        self.assertTrue(base.startswith("historical_case_request_"))

    def test_hit_chart_includes_hit_point_layer(self):
        chart_spec = build_case_chart(self.case()).to_dict()

        self.assertEqual(len(chart_spec["layer"]), 5)
        self.assertIn("TEST - 2025-01-02 - 達成研究目標（HIT）", chart_spec["title"])

    def test_miss_chart_does_not_include_hit_point_layer(self):
        chart_spec = build_case_chart(self.case(OutcomeEvaluationStatus.MISS)).to_dict()

        self.assertEqual(len(chart_spec["layer"]), 4)
        self.assertIn("TEST - 2025-01-02 - 未達研究目標（MISS）", chart_spec["title"])

    def test_chart_uses_relative_bar_axis_by_default(self):
        chart_spec = build_case_chart(self.case()).to_dict()

        self.assertEqual(chart_spec["layer"][0]["encoding"]["x"]["field"], "Relative Bar")

    def test_chart_can_use_actual_date_axis(self):
        chart_spec = build_case_chart(self.case(), x_mode="Actual Dates").to_dict()

        self.assertEqual(chart_spec["layer"][0]["encoding"]["x"]["field"], "Trading Date")


if __name__ == "__main__":
    unittest.main()
