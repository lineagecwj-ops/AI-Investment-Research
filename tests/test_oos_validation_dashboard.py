import sys
import unittest
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from oos_validation_dashboard import CANDIDATE_SHARE_CAPTION
from oos_validation_dashboard import HISTORICAL_HIT_RATE_CAPTION
from oos_validation_dashboard import OOS_VALIDATION_MODE
from oos_validation_dashboard import OUTCOME_CAPTION
from oos_validation_dashboard import SMALL_SAMPLE_WARNING
from oos_validation_dashboard import STORED_RESULT_MISMATCH_MESSAGE
from oos_validation_dashboard import build_candidate_count_chart_rows
from oos_validation_dashboard import build_candidate_share_chart_rows
from oos_validation_dashboard import build_cross_period_comparison_rows
from oos_validation_dashboard import build_cross_period_symbol_presence_rows
from oos_validation_dashboard import build_factual_observations
from oos_validation_dashboard import build_failure_summary_rows
from oos_validation_dashboard import build_historical_hit_rate_chart_rows
from oos_validation_dashboard import build_oos_validation_request_fingerprint
from oos_validation_dashboard import build_outcome_count_rows
from oos_validation_dashboard import build_period_summary_rows
from oos_validation_dashboard import build_period_symbol_rows
from oos_validation_dashboard import build_period_timeline_rows
from oos_validation_dashboard import build_source_context_copy
from oos_validation_dashboard import contains_verdict_language
from oos_validation_dashboard import format_candidate_period_share
from oos_validation_dashboard import format_historical_hit_rate_with_n
from oos_validation_dashboard import format_percentage
from oos_validation_dashboard import format_percentage_point_delta
from oos_validation_dashboard import ordered_period_results
from oos_validation_dashboard import stored_result_is_stale
from out_of_sample_validation_service import ValidationPeriodRole
from replay_analytics_service import ReplayAnalyticsConfig
from replay_analytics_service import ReplayAnalyticsResult
from replay_analytics_service import ReplayOutcomeDistribution
from replay_analytics_service import ReplayPeriodSummary
from replay_analytics_service import ReplayStabilitySummary
from replay_analytics_service import ReplaySymbolSummary


@dataclass(frozen=True)
class PeriodResultStub:

    role: ValidationPeriodRole
    start_date: date
    end_date: date
    requested_replay_period_count: int
    completed_replay_period_count: int
    periods_with_candidates: int
    periods_without_candidates: int
    unique_candidate_symbols: int
    total_candidate_occurrences: int
    candidate_period_share: float
    post_replay_hit_count: int
    post_replay_miss_count: int
    post_replay_incomplete_count: int
    post_replay_not_evaluable_count: int
    resolved_count: int
    historical_hit_rate: float | None
    replay_analytics: ReplayAnalyticsResult
    walk_forward_result: object


class OosValidationDashboardTestCase(unittest.TestCase):

    def symbol_summary(self, symbol, occurrences, *, share=0.5, hit=1, miss=0):
        return ReplaySymbolSummary(
            symbol=symbol,
            candidate_occurrence_count=occurrences,
            first_candidate_date=date(2024, 1, 31),
            last_candidate_date=date(2024, 2, 29),
            candidate_dates=(date(2024, 1, 31),),
            total_period_count=2,
            candidate_period_share=share,
            longest_consecutive_candidate_periods=1,
            post_replay_hit_count=hit,
            post_replay_miss_count=miss,
            post_replay_incomplete_count=0,
            post_replay_not_evaluable_count=0,
            resolved_post_replay_count=hit + miss,
            best_research_priority_rank=1,
            worst_research_priority_rank=3,
            median_research_priority_rank=2.0,
        )

    def analytics(self, *, role="DEVELOPMENT", symbols=(), timeline_counts=(1, 0), failures=0):
        period_summaries = tuple(
            ReplayPeriodSummary(
                requested_replay_date=date(2024, index + 1, 28),
                candidate_count=count,
                match_count=count,
                no_match_count=2 - count,
                not_evaluable_count=0,
                failure_count=failures if index == 0 else 0,
                candidate_symbols=tuple(item.symbol for item in symbols[:count]),
                resolved_post_replay_count=count,
                post_replay_hit_count=count,
                post_replay_miss_count=0,
                post_replay_incomplete_count=0,
                post_replay_not_evaluable_count=0,
            )
            for index, count in enumerate(timeline_counts)
        )
        return ReplayAnalyticsResult(
            config=ReplayAnalyticsConfig(),
            stability_summary=ReplayStabilitySummary(
                total_period_count=len(timeline_counts),
                periods_with_candidates=sum(1 for count in timeline_counts if count > 0),
                periods_without_candidates=sum(1 for count in timeline_counts if count == 0),
                unique_candidate_symbols=len(symbols),
                total_candidate_occurrences=sum(item.candidate_occurrence_count for item in symbols),
                candidate_period_share=sum(1 for count in timeline_counts if count > 0) / len(timeline_counts) if timeline_counts else 0.0,
                candidate_set_transitions=tuple(),
            ),
            period_summaries=period_summaries,
            symbol_summaries=tuple(symbols),
            candidate_occurrences=tuple(),
            post_replay_outcome_distribution=ReplayOutcomeDistribution(0, 0, 0, 0),
        )

    def period(
        self,
        role,
        *,
        total=60,
        with_candidates=5,
        unique=2,
        occurrences=5,
        hit=5,
        miss=0,
        incomplete=0,
        not_evaluable=0,
        symbols=(),
        timeline_counts=(1, 0),
        failures=(),
    ):
        analytics = self.analytics(symbols=symbols, timeline_counts=timeline_counts, failures=len(failures))
        resolved = hit + miss
        failure_periods = tuple(
            SimpleNamespace(
                requested_replay_date=date(2024, 1, 28),
                failure=SimpleNamespace(error_type="RuntimeError", safe_message="provider failed"),
            )
            for _ in failures
        )
        return PeriodResultStub(
            role=role,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            requested_replay_period_count=total,
            completed_replay_period_count=total - len(failures),
            periods_with_candidates=with_candidates,
            periods_without_candidates=total - with_candidates,
            unique_candidate_symbols=unique,
            total_candidate_occurrences=occurrences,
            candidate_period_share=with_candidates / total if total else 0.0,
            post_replay_hit_count=hit,
            post_replay_miss_count=miss,
            post_replay_incomplete_count=incomplete,
            post_replay_not_evaluable_count=not_evaluable,
            resolved_count=resolved,
            historical_hit_rate=None if resolved == 0 else hit / resolved,
            replay_analytics=analytics,
            walk_forward_result=SimpleNamespace(period_results=failure_periods),
        )

    def result(self):
        development = self.period(
            ValidationPeriodRole.DEVELOPMENT,
            total=60,
            with_candidates=5,
            symbols=(self.symbol_summary("AAPL", 3), self.symbol_summary("MSFT", 2)),
        )
        validation = self.period(
            ValidationPeriodRole.VALIDATION,
            total=24,
            with_candidates=2,
            unique=1,
            occurrences=2,
            hit=2,
            symbols=(self.symbol_summary("AAPL", 2),),
            timeline_counts=(0, 1),
        )
        holdout = self.period(
            ValidationPeriodRole.HOLDOUT,
            total=19,
            with_candidates=8,
            unique=3,
            occurrences=9,
            hit=6,
            miss=2,
            incomplete=1,
            symbols=(self.symbol_summary("AAPL", 4), self.symbol_summary("NVDA", 3), self.symbol_summary("TSM", 2)),
        )
        return SimpleNamespace(
            config=SimpleNamespace(minimum_resolved_samples=20),
            development_result=development,
            validation_result=validation,
            holdout_result=holdout,
        )

    def test_percentage_formatter(self):
        self.assertEqual(format_percentage(0.75), "75.00%")
        self.assertEqual(format_percentage(-0.25), "-25.00%")

    def test_none_formatter(self):
        self.assertEqual(format_percentage(None), "N/A")

    def test_candidate_period_share_formatting(self):
        self.assertEqual(format_candidate_period_share(self.result().development_result), "5 / 60 = 8.33%")

    def test_percentage_point_delta(self):
        self.assertEqual(format_percentage_point_delta(0.3378), "+33.78 percentage points")
        self.assertEqual(format_percentage_point_delta(-0.25), "-25.00 percentage points")

    def test_zero_resolved_hit_rate_is_na(self):
        period = self.period(ValidationPeriodRole.DEVELOPMENT, hit=0, miss=0)
        self.assertEqual(format_historical_hit_rate_with_n(period), "N/A (n=0)")

    def test_resolved_n_is_always_present_with_hit_rate(self):
        self.assertIn("(n=5)", format_historical_hit_rate_with_n(self.result().development_result))

    def test_comparison_rows_include_required_metrics(self):
        metrics = [row["Metric"] for row in build_cross_period_comparison_rows(self.result())]
        self.assertIn("Candidate Period Share", metrics)
        self.assertIn("Historical Hit Rate", metrics)
        self.assertIn("Resolved n", metrics)

    def test_development_validation_holdout_order(self):
        roles = [period.role for period in ordered_period_results(self.result())]
        self.assertEqual(roles, [ValidationPeriodRole.DEVELOPMENT, ValidationPeriodRole.VALIDATION, ValidationPeriodRole.HOLDOUT])

    def test_outcome_count_rows_are_side_by_side(self):
        rows = build_outcome_count_rows(self.result())
        self.assertEqual(rows[0]["Outcome"], "HIT")
        self.assertIn("Development", rows[0])
        self.assertIn("Holdout / Out-of-Sample", rows[0])

    def test_symbol_cross_period_table(self):
        rows = build_cross_period_symbol_presence_rows(self.result())
        aapl = next(row for row in rows if row["Symbol"] == "AAPL")
        self.assertEqual(aapl["Development Occurrences"], 3)
        self.assertEqual(aapl["Holdout Occurrences"], 4)

    def test_missing_symbol_in_one_period_is_zero(self):
        rows = build_cross_period_symbol_presence_rows(self.result())
        nvda = next(row for row in rows if row["Symbol"] == "NVDA")
        self.assertEqual(nvda["Development Occurrences"], 0)
        self.assertIn("Holdout / Out-of-Sample", nvda["Appeared In Periods"])

    def test_zero_candidates_symbol_table_empty(self):
        period = self.period(ValidationPeriodRole.DEVELOPMENT, with_candidates=0, unique=0, occurrences=0, symbols=())
        self.assertEqual(build_period_symbol_rows(period), [])

    def test_factual_observations_are_neutral(self):
        observations = build_factual_observations(self.result())
        combined = " ".join(observations)
        self.assertIn("candidate period share", combined)
        self.assertFalse(contains_verdict_language(combined))

    def test_no_verdict_language_detector(self):
        self.assertTrue(contains_verdict_language("Validation Passed"))
        self.assertFalse(contains_verdict_language("Holdout candidate period share is higher than Development."))

    def test_fixed_captions_do_not_use_future_probability_label(self):
        combined = " ".join([HISTORICAL_HIT_RATE_CAPTION, OUTCOME_CAPTION, CANDIDATE_SHARE_CAPTION])
        self.assertNotIn("Future Probability", combined)
        self.assertNotIn("Prediction Accuracy", combined)

    def test_fixed_captions_do_not_use_recommendation_wording(self):
        combined = " ".join([HISTORICAL_HIT_RATE_CAPTION, OUTCOME_CAPTION, CANDIDATE_SHARE_CAPTION])
        self.assertNotIn("Buy", combined)
        self.assertNotIn("Sell", combined)

    def test_request_fingerprint_changes_when_source_changes(self):
        base = self.request_fingerprint(source_type="Manual Input")
        changed = self.request_fingerprint(source_type="Saved Universe")
        self.assertNotEqual(base, changed)

    def test_config_mismatch_helper(self):
        self.assertTrue(stored_result_is_stale("old", "new"))
        self.assertFalse(stored_result_is_stale("same", "same"))
        self.assertIn("上一組驗證設定", STORED_RESULT_MISMATCH_MESSAGE)

    def test_result_source_snapshot_preserves_symbols(self):
        snapshot = build_source_context_copy({"source_type": "Saved Universe", "source_universe_name": "TW", "symbol_count": 2, "symbols_copy": ("2330.TW", "2454.TW")})
        self.assertEqual(snapshot["symbols"], ("2330.TW", "2454.TW"))

    def test_period_local_stability_symbol_rows(self):
        rows = build_period_symbol_rows(self.result().development_result)
        self.assertEqual(rows[0]["Symbol"], "AAPL")
        self.assertIn("Best Research Priority", rows[0])

    def test_zero_replay_date_period_safe(self):
        period = self.period(ValidationPeriodRole.DEVELOPMENT, total=0, with_candidates=0, timeline_counts=())
        self.assertEqual(format_candidate_period_share(period), "0 / 0 = 0.00%")
        self.assertEqual(build_period_timeline_rows(period), [])

    def test_safe_failures_are_rows(self):
        result = SimpleNamespace(
            development_result=self.period(ValidationPeriodRole.DEVELOPMENT, failures=("x",)),
            validation_result=self.period(ValidationPeriodRole.VALIDATION),
            holdout_result=self.period(ValidationPeriodRole.HOLDOUT),
        )
        rows = build_failure_summary_rows(result)
        self.assertEqual(rows[0]["Safe Error Type"], "RuntimeError")
        self.assertEqual(rows[0]["Safe Message"], "provider failed")

    def test_chart_rows_use_theme_safe_plain_data(self):
        rows = build_candidate_share_chart_rows(self.result())
        self.assertIn("Candidate Period Share", rows[0])
        self.assertNotIn("color", rows[0])
        self.assertNotIn("background", rows[0])

    def test_candidate_count_chart_keeps_zero_candidate_periods(self):
        rows = build_candidate_count_chart_rows(self.result())
        self.assertIn(0, [row["Candidate Count"] for row in rows])

    def test_historical_hit_rate_chart_labels_include_n(self):
        rows = build_historical_hit_rate_chart_rows(self.result())
        self.assertIn("n=5", rows[0]["Label"])

    def test_period_summary_rows_include_small_sample_context_metric(self):
        rows = build_period_summary_rows(self.result().validation_result)
        self.assertIn({"Metric": "Resolved n", "Value": 2}, rows)
        self.assertEqual(SMALL_SAMPLE_WARNING, "此期間已解析歷史樣本低於偏好門檻。")

    def test_mode_label_is_explicit(self):
        self.assertEqual(OOS_VALIDATION_MODE, "Out-of-Sample Validation")

    def request_fingerprint(self, *, source_type):
        return build_oos_validation_request_fingerprint(
            normalized_symbols=("2330.TW", "NVDA"),
            source_type=source_type,
            development_start=date(2018, 1, 1),
            development_end=date(2022, 12, 31),
            validation_start=date(2023, 1, 1),
            validation_end=date(2024, 12, 31),
            holdout_start=date(2025, 1, 1),
            holdout_end=date(2026, 8, 8),
            replay_frequency="MONTHLY",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            historical_start_date=date(2018, 1, 1),
            minimum_resolved_samples=20,
        )


if __name__ == "__main__":
    unittest.main()
