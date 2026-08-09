import math
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
from volume_threshold_sensitivity_service import DEFAULT_VOLUME_THRESHOLD_GRID
from volume_threshold_sensitivity_service import VolumeThresholdSensitivityAnalysisError
from volume_threshold_sensitivity_service import VolumeThresholdSensitivityConfig
from volume_threshold_sensitivity_service import VolumeThresholdSensitivityPoint
from volume_threshold_sensitivity_service import VolumeThresholdSensitivityResult
from volume_threshold_sensitivity_service import VolumeThresholdSensitivitySymbolSummary
from volume_threshold_sensitivity_service import analyze_volume_threshold_sensitivity


FETCHED_AT = datetime(2026, 8, 9, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 9, 2, 0, tzinfo=UTC)


class VolumeThresholdSensitivityServiceTestCase(unittest.TestCase):

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
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 1), volume_ratio_20=1.20),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 2), volume_ratio_20=1.50),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 1), volume_ratio_20=1.30),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 2), volume_ratio_20=1.25),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 3), volume_ratio_20=1.10),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 3), volume_ratio_20=1.00),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 4), volume_ratio_20=0.80),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 4), volume_ratio_20=0.79),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 5), analysis_close=80.0, volume_ratio_20=2.00),
        )
        statuses = iter((
            OutcomeEvaluationStatus.HIT,
            OutcomeEvaluationStatus.MISS,
            OutcomeEvaluationStatus.HIT,
            OutcomeEvaluationStatus.NOT_EVALUABLE,
            OutcomeEvaluationStatus.HIT,
            OutcomeEvaluationStatus.HIT,
            OutcomeEvaluationStatus.INCOMPLETE,
            OutcomeEvaluationStatus.MISS,
            OutcomeEvaluationStatus.HIT,
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

    def test_config_validation_requires_finite_positive_unique_baseline_grid(self):
        self.assertEqual(VolumeThresholdSensitivityConfig().thresholds, DEFAULT_VOLUME_THRESHOLD_GRID)
        self.assertEqual(VolumeThresholdSensitivityConfig(thresholds=(1.50, 0.80, 1.20)).thresholds, (0.80, 1.20, 1.50))

        invalid_thresholds = (tuple(), (0.80, 1.00), (1.20, 1.20), (1.20, 0), (1.20, math.inf), (1.20, math.nan))
        for thresholds in invalid_thresholds:
            with self.subTest(thresholds=thresholds):
                with self.assertRaises(VolumeThresholdSensitivityAnalysisError):
                    VolumeThresholdSensitivityConfig(thresholds=thresholds)

    def test_threshold_summary_counts_deltas_and_percentage_points(self):
        result = analyze_volume_threshold_sensitivity(self.comparison_result(), generated_at=GENERATED_AT)
        rows = {row.threshold: row for row in result.aggregate_points}

        self.assertEqual(tuple(rows), DEFAULT_VOLUME_THRESHOLD_GRID)
        self.assertEqual(rows[1.20].observation_count, 4)
        self.assertEqual(rows[1.20].hit_count, 2)
        self.assertEqual(rows[1.20].miss_count, 1)
        self.assertEqual(rows[1.20].incomplete_count, 1)
        self.assertEqual(rows[1.20].not_evaluable_count, 0)
        self.assertEqual(rows[1.20].resolved_count, 3)
        self.assertEqual(rows[1.20].historical_hit_rate, 2 / 3)
        self.assertTrue(rows[1.20].is_current_v1_baseline)
        self.assertEqual(rows[1.20].observation_count_delta_vs_v1, 0)
        self.assertEqual(rows[1.20].observation_count_change_rate_vs_v1, 0)
        self.assertEqual(rows[1.20].resolved_count_delta_vs_v1, 0)
        self.assertEqual(rows[1.20].hit_count_delta_vs_v1, 0)
        self.assertEqual(rows[1.20].miss_count_delta_vs_v1, 0)
        self.assertEqual(rows[1.20].historical_hit_rate_delta_percentage_points_vs_v1, 0)

        self.assertEqual(rows[1.00].observation_count, 6)
        self.assertEqual(rows[1.00].hit_count, 3)
        self.assertEqual(rows[1.00].miss_count, 2)
        self.assertEqual(rows[1.00].incomplete_count, 1)
        self.assertEqual(rows[1.00].resolved_count, 5)
        self.assertEqual(rows[1.00].historical_hit_rate, 3 / 5)
        self.assertEqual(rows[1.00].observation_count_delta_vs_v1, 2)
        self.assertEqual(rows[1.00].observation_count_change_rate_vs_v1, 2 / 4)
        self.assertEqual(rows[1.00].resolved_count_delta_vs_v1, 2)
        self.assertEqual(rows[1.00].hit_count_delta_vs_v1, 1)
        self.assertEqual(rows[1.00].miss_count_delta_vs_v1, 1)
        self.assertAlmostEqual(rows[1.00].historical_hit_rate_delta_percentage_points_vs_v1, (3 / 5 - 2 / 3) * 100)

    def test_other_four_conditions_must_pass_and_three_of_five_is_excluded(self):
        result = analyze_volume_threshold_sensitivity(self.comparison_result())
        rows = {row.threshold: row for row in result.aggregate_points}

        self.assertEqual(rows[0.80].observation_count, 7)
        self.assertEqual(rows[0.80].hit_count, 3)
        self.assertEqual(rows[0.80].miss_count, 2)
        self.assertEqual(rows[0.80].incomplete_count, 1)
        self.assertEqual(rows[0.80].not_evaluable_count, 1)
        self.assertEqual(rows[0.80].resolved_count, 5)

    def test_numeric_boundary_uses_greater_than_or_equal_without_fuzzy_compare(self):
        comparison = self.comparison_result()
        custom = VolumeThresholdSensitivityConfig(thresholds=(1.099999999, 1.10, 1.20), baseline_threshold=1.20)
        result = analyze_volume_threshold_sensitivity(comparison, config=custom)
        rows = {row.threshold: row for row in result.aggregate_points}

        self.assertEqual(rows[1.10].observation_count, 5)
        self.assertEqual(rows[1.099999999].observation_count, 5)

        adjusted = replace(
            comparison,
            outcome_observations=tuple(
                replace(
                    observation,
                    diagnostic_observation=replace(
                        observation.diagnostic_observation,
                        source_snapshot=replace(observation.diagnostic_observation.source_snapshot, volume_ratio_20=1.099999999),
                    ),
                )
                if observation.trading_date == date(2025, 1, 3) and observation.symbol == "AAA"
                else observation
                for observation in comparison.outcome_observations
            ),
        )
        adjusted_result = analyze_volume_threshold_sensitivity(adjusted, config=custom)
        adjusted_rows = {row.threshold: row for row in adjusted_result.aggregate_points}
        self.assertEqual(adjusted_rows[1.10].observation_count, 4)
        self.assertEqual(adjusted_rows[1.099999999].observation_count, 5)

    def test_missing_and_non_finite_volume_values_do_not_qualify(self):
        comparison = self.comparison_result()
        targets = {(date(2025, 1, 3), "AAA"): None, (date(2025, 1, 3), "BBB"): math.inf}
        adjusted = replace(
            comparison,
            outcome_observations=tuple(
                replace(
                    observation,
                    diagnostic_observation=replace(
                        observation.diagnostic_observation,
                        source_snapshot=replace(
                            observation.diagnostic_observation.source_snapshot,
                            volume_ratio_20=targets[(observation.trading_date, observation.symbol)],
                        ),
                    ),
                )
                if (observation.trading_date, observation.symbol) in targets
                else observation
                for observation in comparison.outcome_observations
            ),
        )

        rows = {
            row.threshold: row
            for row in analyze_volume_threshold_sensitivity(adjusted).aggregate_points
        }

        self.assertEqual(rows[1.00].observation_count, 4)
        self.assertEqual(rows[1.00].resolved_count, 3)

    def test_sample_count_monotonic_and_qualified_id_subset_invariant(self):
        result = analyze_volume_threshold_sensitivity(self.comparison_result())
        counts = [row.observation_count for row in result.aggregate_points]

        self.assertEqual(counts, sorted(counts, reverse=True))
        self.assertEqual(counts, [7, 6, 5, 4, 2, 1])

    def test_incomplete_not_evaluable_denominator_and_zero_resolved_are_safe(self):
        comparison = self.comparison_result()
        result = analyze_volume_threshold_sensitivity(
            comparison,
            config=VolumeThresholdSensitivityConfig(thresholds=(0.80, 1.50), baseline_threshold=1.50),
        )
        rows = {row.threshold: row for row in result.aggregate_points}

        self.assertEqual(rows[0.80].observation_count, 7)
        self.assertEqual(rows[0.80].resolved_count, 5)
        self.assertEqual(rows[0.80].historical_hit_rate, 3 / 5)

        only_unresolved = replace(
            comparison,
            outcome_observations=tuple(
                observation for observation in comparison.outcome_observations
                if observation.status is OutcomeEvaluationStatus.INCOMPLETE
            ),
        )
        unresolved_rows = {
            row.threshold: row
            for row in analyze_volume_threshold_sensitivity(
                only_unresolved,
                config=VolumeThresholdSensitivityConfig(thresholds=(1.20,), baseline_threshold=1.20),
            ).aggregate_points
        }
        self.assertIsNone(unresolved_rows[1.20].historical_hit_rate)
        self.assertIsNone(unresolved_rows[1.20].historical_hit_rate_delta_percentage_points_vs_v1)

    def test_per_symbol_support_and_aggregate_raw_count_semantics(self):
        result = analyze_volume_threshold_sensitivity(self.comparison_result())
        summaries = {summary.symbol: summary for summary in result.per_symbol_summaries}
        aggregate = {row.threshold: row for row in result.aggregate_points}
        aaa = {row.threshold: row for row in summaries["AAA"].points}
        bbb = {row.threshold: row for row in summaries["BBB"].points}

        self.assertEqual(set(summaries), {"AAA", "BBB"})
        self.assertEqual(aaa[1.00].hit_count, 2)
        self.assertEqual(aaa[1.00].miss_count, 1)
        self.assertEqual(aaa[1.00].historical_hit_rate, 2 / 3)
        self.assertEqual(bbb[1.00].hit_count, 1)
        self.assertEqual(bbb[1.00].miss_count, 1)
        self.assertEqual(bbb[1.00].historical_hit_rate, 1 / 2)
        self.assertEqual(aggregate[1.00].hit_count, 3)
        self.assertEqual(aggregate[1.00].miss_count, 2)
        self.assertEqual(aggregate[1.00].historical_hit_rate, 3 / 5)
        self.assertNotEqual(aggregate[1.00].historical_hit_rate, (2 / 3 + 1 / 2) / 2)

    def test_daily_metadata_source_identity_and_determinism_are_preserved(self):
        comparison = self.comparison_result()
        before = comparison.outcome_observations

        first = analyze_volume_threshold_sensitivity(comparison, generated_at=GENERATED_AT)
        second = analyze_volume_threshold_sensitivity(comparison, generated_at=GENERATED_AT)

        self.assertEqual(comparison.outcome_observations, before)
        self.assertEqual(first, second)
        self.assertEqual(first.config.analysis_name, "成交量門檻變化測試")
        self.assertEqual(first.config.advanced_method_name, "Volume Threshold Sensitivity Analysis")
        self.assertEqual(first.threshold_grid, DEFAULT_VOLUME_THRESHOLD_GRID)
        self.assertEqual(first.baseline_threshold, 1.20)
        self.assertEqual(first.observation_unit, "DAILY")
        self.assertTrue(first.overlap_possible)
        self.assertEqual(first.source_signal_definition_id, TECHNICAL_EXAMPLE_SIGNAL_V1.id)
        self.assertEqual(first.source_outcome_definition_id, RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id)
        self.assertEqual(first.source_warmup_trading_bars, 60)
        self.assertEqual(first.generated_at, GENERATED_AT)

    def test_duplicate_observation_identity_is_rejected(self):
        comparison = self.comparison_result()
        duplicate = comparison.outcome_observations[0]
        comparison = replace(
            comparison,
            outcome_observations=comparison.outcome_observations + (duplicate,),
        )

        with self.assertRaises(VolumeThresholdSensitivityAnalysisError):
            analyze_volume_threshold_sensitivity(comparison)

    def test_no_fetch_technical_rebuild_or_outcome_rerun_during_sensitivity_grouping(self):
        comparison = self.comparison_result()

        with patch("historical_price_service.get_historical_prices") as fetch:
            with patch("technical_indicator_service.build_technical_indicator_series") as builder:
                with patch("signal_outcome_service.evaluate_historical_outcome") as evaluator:
                    analyze_volume_threshold_sensitivity(comparison)

        fetch.assert_not_called()
        builder.assert_not_called()
        evaluator.assert_not_called()

    def test_no_probability_recommendation_ranking_or_score_fields(self):
        names = {
            field.name
            for model in (
                VolumeThresholdSensitivityConfig,
                VolumeThresholdSensitivityPoint,
                VolumeThresholdSensitivitySymbolSummary,
                VolumeThresholdSensitivityResult,
            )
            for field in fields(model)
        }

        forbidden = ("score", "probability", "recommendation", "rank", "best", "optimal")
        self.assertFalse(any(term in name for term in forbidden for name in names))


if __name__ == "__main__":
    unittest.main()
