import sys
import unittest
from dataclasses import fields
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from condition_contribution_service import ConditionContributionAnalysisError
from condition_contribution_service import ConditionContributionComparison
from condition_contribution_service import ConditionContributionConfig
from condition_contribution_service import ConditionContributionResult
from condition_contribution_service import ConditionContributionSymbolSummary
from condition_contribution_service import analyze_condition_contribution
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonConfig
from historical_condition_outcome_service import compare_historical_condition_outcomes
from models import HistoricalOutcomeResult
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeEvaluationStatus
from models import TechnicalIndicatorSnapshot
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsConfig
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsService
from signal_condition_diagnostics_service import build_condition_diagnostic_observation
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import evaluate_signal_conditions


FETCHED_AT = datetime(2026, 8, 9, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 9, 2, 0, tzinfo=UTC)
CONDITION_IDS = (
    "analysis_close_vs_sma_20",
    "sma_20_vs_sma_60",
    "volume_ratio_20",
    "rsi_14",
    "distance_to_prior_60d_high",
)


class ConditionContributionServiceTestCase(unittest.TestCase):

    def config(self):
        return HistoricalConditionDiagnosticsConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
        )

    def snapshot(self, symbol="AAA", trading_date=date(2025, 1, 1), **overrides):
        params = {
            field.name: None
            for field in fields(TechnicalIndicatorSnapshot)
        }
        params.update(
            symbol=symbol,
            trading_date=trading_date,
            analysis_close=105.0,
            sma_20=100.0,
            sma_60=90.0,
            volume_ratio_20=1.5,
            rsi_14=60.0,
            prior_high_60d=110.0,
            prior_low_60d=80.0,
            distance_to_prior_60d_high=-0.02,
        )
        params.update(overrides)
        return TechnicalIndicatorSnapshot(**params)

    def diagnostic_observation(self, **overrides):
        match = evaluate_signal_conditions(
            self.snapshot(**overrides),
            TECHNICAL_EXAMPLE_SIGNAL_V1,
        )
        return build_condition_diagnostic_observation(match)

    def price_bar(self, symbol, trading_date):
        return HistoricalPriceBar(
            symbol=symbol,
            trading_date=trading_date,
            open=100.0,
            high=100.0,
            low=99.0,
            close=100.0,
            adjusted_close=None,
            volume=1000,
        )

    def price_series(self, symbol):
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="USD",
            bars=tuple(self.price_bar(symbol, date(2025, 1, day)) for day in range(1, 32)),
            fetched_at=FETCHED_AT,
            is_stale=False,
        )

    def outcome(self, signal_event, status):
        return HistoricalOutcomeResult(
            symbol=signal_event.symbol,
            signal_id=signal_event.signal_id,
            signal_date=signal_event.signal_date,
            outcome_definition_id=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id,
            status=status,
            horizon_bars=20,
            available_future_bars=20,
            reference_high=signal_event.reference_high,
            intraday_target_hit=status is OutcomeEvaluationStatus.HIT,
            intraday_target_hit_date=None,
            intraday_target_hit_bar_index=1 if status is OutcomeEvaluationStatus.HIT else None,
            close_target_hit=False,
            close_target_hit_date=None,
            close_target_hit_bar_index=None,
            max_close_return=None,
            max_close_return_date=None,
            max_adverse_return=None,
            max_adverse_return_date=None,
            end_of_window_return=None,
        )

    def comparison_result(self):
        observations = (
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 1)),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 2)),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 1)),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 2)),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 3), analysis_close=90.0),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 3), sma_20=80.0, sma_60=90.0),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 4), volume_ratio_20=0.5),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 4), rsi_14=80.0),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 5), distance_to_prior_60d_high=-0.20),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 5), volume_ratio_20=0.5, rsi_14=80.0),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 6), rsi_14=None),
        )
        statuses = iter((
            OutcomeEvaluationStatus.HIT,
            OutcomeEvaluationStatus.MISS,
            OutcomeEvaluationStatus.MISS,
            OutcomeEvaluationStatus.HIT,
            OutcomeEvaluationStatus.HIT,
            OutcomeEvaluationStatus.HIT,
            OutcomeEvaluationStatus.INCOMPLETE,
            OutcomeEvaluationStatus.MISS,
            OutcomeEvaluationStatus.NOT_EVALUABLE,
            OutcomeEvaluationStatus.MISS,
        ))
        diagnostics = HistoricalConditionDiagnosticsService(
            price_loader=lambda *args, **kwargs: self.fail("price loader should not be called"),
            technical_builder=lambda *args, **kwargs: self.fail("technical builder should not be called"),
        ).run_diagnostics(
            ("AAA", "BBB"),
            self.config(),
            technical_series_by_symbol={
                "AAA": type("Series", (), {"symbol": "AAA", "snapshots": tuple(o.source_snapshot for o in observations if o.symbol == "AAA")})(),
                "BBB": type("Series", (), {"symbol": "BBB", "snapshots": tuple(o.source_snapshot for o in observations if o.symbol == "BBB")})(),
            },
        )

        return compare_historical_condition_outcomes(
            diagnostics,
            price_series_by_symbol={"AAA": self.price_series("AAA"), "BBB": self.price_series("BBB")},
            config=HistoricalConditionOutcomeComparisonConfig(
                outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
            ),
            outcome_evaluator=lambda signal_event, price_series, outcome_definition: self.outcome(signal_event, next(statuses)),
            generated_at=GENERATED_AT,
        )

    def test_leave_one_out_core_counts_and_percentage_point_delta(self):
        result = analyze_condition_contribution(self.comparison_result(), generated_at=GENERATED_AT)
        rows = {row.condition_id: row for row in result.condition_comparisons}

        self.assertEqual(result.baseline_summary.observation_count, 4)
        self.assertEqual(result.baseline_summary.hit_count, 2)
        self.assertEqual(result.baseline_summary.miss_count, 1)
        self.assertEqual(result.baseline_summary.incomplete_count, 1)
        self.assertEqual(result.baseline_summary.not_evaluable_count, 0)
        self.assertEqual(result.baseline_summary.resolved_count, 3)
        self.assertEqual(result.baseline_summary.historical_hit_rate, 2 / 3)

        volume = rows["volume_ratio_20"]
        self.assertEqual(volume.baseline_observation_count, 4)
        self.assertEqual(volume.baseline_hit_count, 2)
        self.assertEqual(volume.baseline_miss_count, 1)
        self.assertEqual(volume.baseline_incomplete_count, 1)
        self.assertEqual(volume.baseline_not_evaluable_count, 0)
        self.assertEqual(volume.baseline_resolved_count, 3)
        self.assertEqual(volume.baseline_historical_hit_rate, 2 / 3)
        self.assertEqual(volume.leave_one_out_observation_count, 5)
        self.assertEqual(volume.leave_one_out_hit_count, 3)
        self.assertEqual(volume.leave_one_out_miss_count, 1)
        self.assertEqual(volume.leave_one_out_incomplete_count, 1)
        self.assertEqual(volume.leave_one_out_not_evaluable_count, 0)
        self.assertEqual(volume.leave_one_out_resolved_count, 4)
        self.assertEqual(volume.leave_one_out_historical_hit_rate, 3 / 4)
        self.assertEqual(volume.added_observation_count, 1)
        self.assertEqual(volume.added_resolved_count, 1)
        self.assertEqual(volume.added_hit_count, 1)
        self.assertEqual(volume.added_miss_count, 0)
        self.assertEqual(volume.observation_increase_rate, 1 / 4)
        self.assertAlmostEqual(volume.historical_hit_rate_delta_percentage_points, (3 / 4 - 2 / 3) * 100)

    def test_each_canonical_condition_leave_one_out_equals_baseline_plus_only_missing_target(self):
        result = analyze_condition_contribution(self.comparison_result())
        counts = {
            row.condition_id: row.leave_one_out_observation_count
            for row in result.condition_comparisons
        }

        self.assertEqual([row.condition_id for row in result.condition_comparisons], list(CONDITION_IDS))
        self.assertEqual(counts["analysis_close_vs_sma_20"], 5)
        self.assertEqual(counts["sma_20_vs_sma_60"], 5)
        self.assertEqual(counts["volume_ratio_20"], 5)
        self.assertEqual(counts["rsi_14"], 5)
        self.assertEqual(counts["distance_to_prior_60d_high"], 5)
        for row in result.condition_comparisons:
            self.assertEqual(
                row.leave_one_out_observation_count,
                row.baseline_observation_count + row.added_observation_count,
            )

    def test_zero_added_and_zero_resolved_samples_are_safe(self):
        comparison = self.comparison_result()
        filtered = tuple(
            observation for observation in comparison.outcome_observations
            if observation.missing_condition_ids != ("analysis_close_vs_sma_20",)
        )
        comparison = replace(comparison, outcome_observations=filtered)

        result = analyze_condition_contribution(comparison)
        row = result.condition_comparisons[0]

        self.assertEqual(row.added_observation_count, 0)
        self.assertEqual(row.added_resolved_count, 0)
        self.assertEqual(row.added_hit_count, 0)
        self.assertEqual(row.added_miss_count, 0)
        self.assertEqual(row.leave_one_out_observation_count, row.baseline_observation_count)
        self.assertEqual(row.historical_hit_rate_delta_percentage_points, 0.0)

    def test_incomplete_and_not_evaluable_are_excluded_from_hit_rate_denominator(self):
        result = analyze_condition_contribution(self.comparison_result())
        rsi = {
            row.condition_id: row
            for row in result.condition_comparisons
        }["rsi_14"]

        self.assertEqual(rsi.leave_one_out_observation_count, 5)
        self.assertEqual(rsi.leave_one_out_not_evaluable_count, 1)
        self.assertEqual(rsi.leave_one_out_resolved_count, 3)
        self.assertEqual(rsi.leave_one_out_historical_hit_rate, 2 / 3)

    def test_per_symbol_isolation_and_aggregate_raw_count_semantics(self):
        result = analyze_condition_contribution(self.comparison_result())
        summaries = {summary.symbol: summary for summary in result.per_symbol_summaries}

        self.assertEqual(set(summaries), {"AAA", "BBB"})
        aaa_volume = {
            row.condition_id: row
            for row in summaries["AAA"].comparisons
        }["volume_ratio_20"]
        bbb_volume = {
            row.condition_id: row
            for row in summaries["BBB"].comparisons
        }["volume_ratio_20"]
        aggregate_volume = {
            row.condition_id: row
            for row in result.aggregate_summary
        }["volume_ratio_20"]

        self.assertEqual(aaa_volume.leave_one_out_hit_count, 2)
        self.assertEqual(aaa_volume.leave_one_out_miss_count, 1)
        self.assertEqual(aaa_volume.leave_one_out_historical_hit_rate, 2 / 3)
        self.assertEqual(bbb_volume.leave_one_out_hit_count, 1)
        self.assertEqual(bbb_volume.leave_one_out_miss_count, 0)
        self.assertEqual(bbb_volume.leave_one_out_historical_hit_rate, 1.0)
        self.assertEqual(aggregate_volume.leave_one_out_hit_count, 3)
        self.assertEqual(aggregate_volume.leave_one_out_miss_count, 1)
        self.assertEqual(aggregate_volume.leave_one_out_historical_hit_rate, 3 / 4)
        self.assertNotEqual(aggregate_volume.leave_one_out_historical_hit_rate, (2 / 3 + 1.0) / 2)

    def test_daily_metadata_and_source_metadata_are_preserved(self):
        result = analyze_condition_contribution(
            self.comparison_result(),
            config=ConditionContributionConfig(),
            generated_at=GENERATED_AT,
        )

        self.assertEqual(result.config.analysis_name, "單一條件影響分析")
        self.assertEqual(result.config.advanced_method_name, "Leave-One-Out Condition Analysis")
        self.assertEqual(result.observation_unit, "DAILY")
        self.assertTrue(result.overlap_possible)
        self.assertEqual(result.source_signal_definition_id, TECHNICAL_EXAMPLE_SIGNAL_V1.id)
        self.assertEqual(result.source_outcome_definition_id, RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id)
        self.assertEqual(result.source_warmup_trading_bars, 60)
        self.assertEqual(result.generated_at, GENERATED_AT)

    def test_duplicate_observation_identity_is_rejected(self):
        comparison = self.comparison_result()
        duplicate = comparison.outcome_observations[0]
        comparison = replace(
            comparison,
            outcome_observations=comparison.outcome_observations + (duplicate,),
        )

        with self.assertRaises(ConditionContributionAnalysisError):
            analyze_condition_contribution(comparison)

    def test_input_batch_two_result_is_not_mutated_and_execution_is_deterministic(self):
        comparison = self.comparison_result()
        before = comparison.outcome_observations

        first = analyze_condition_contribution(comparison, generated_at=GENERATED_AT)
        second = analyze_condition_contribution(comparison, generated_at=GENERATED_AT)

        self.assertEqual(comparison.outcome_observations, before)
        self.assertEqual(first, second)

    def test_no_fetch_technical_rebuild_or_outcome_rerun_during_contribution_grouping(self):
        comparison = self.comparison_result()

        with patch("historical_price_service.get_historical_prices") as fetch:
            with patch("technical_indicator_service.build_technical_indicator_series") as builder:
                with patch("signal_outcome_service.evaluate_historical_outcome") as evaluator:
                    analyze_condition_contribution(comparison)

        fetch.assert_not_called()
        builder.assert_not_called()
        evaluator.assert_not_called()

    def test_no_probability_recommendation_ranking_or_score_fields(self):
        names = {
            field.name
            for model in (
                ConditionContributionConfig,
                ConditionContributionComparison,
                ConditionContributionSymbolSummary,
                ConditionContributionResult,
            )
            for field in fields(model)
        }

        forbidden = ("score", "probability", "recommendation", "rank", "best", "optimal")
        self.assertFalse(any(term in name for term in forbidden for name in names))


if __name__ == "__main__":
    unittest.main()
