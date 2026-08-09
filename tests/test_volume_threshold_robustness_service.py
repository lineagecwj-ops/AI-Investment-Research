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
from volume_threshold_robustness_service import DEFAULT_ROBUSTNESS_THRESHOLDS
from volume_threshold_robustness_service import OverlapReducedThresholdSummary
from volume_threshold_robustness_service import ThresholdDailyRobustnessSummary
from volume_threshold_robustness_service import ThresholdSymbolRobustnessSummary
from volume_threshold_robustness_service import ThresholdYearRobustnessSummary
from volume_threshold_robustness_service import VolumeThresholdRobustnessAnalysisError
from volume_threshold_robustness_service import VolumeThresholdRobustnessConfig
from volume_threshold_robustness_service import VolumeThresholdRobustnessResult
from volume_threshold_robustness_service import analyze_volume_threshold_robustness


FETCHED_AT = datetime(2026, 8, 9, 3, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 9, 4, 0, tzinfo=UTC)


class VolumeThresholdRobustnessServiceTestCase(unittest.TestCase):

    def config(self):
        return HistoricalConditionDiagnosticsConfig(
            start_date=date(2024, 12, 1),
            end_date=date(2025, 12, 31),
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

    def price_series(self, symbol, observations):
        dates = sorted({observation.trading_date for observation in observations if observation.symbol == symbol})
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="USD",
            bars=tuple(self.price_bar(symbol, trading_date) for trading_date in dates),
            fetched_at=FETCHED_AT,
            is_stale=False,
        )

    def outcome(self, signal_event, status):
        hit_date = date(2026, 1, 5) if signal_event.signal_date == date(2025, 12, 31) else None
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
            intraday_target_hit_date=hit_date,
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
        aaa_filler = tuple(
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, day), volume_ratio_20=0.50)
            for day in range(4, 25)
        )
        observations = (
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 1), volume_ratio_20=1.20),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 2), volume_ratio_20=1.10),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 3), volume_ratio_20=1.00),
            *aaa_filler,
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 1, 25), volume_ratio_20=1.30),
            self.diagnostic_observation(symbol="AAA", trading_date=date(2025, 12, 31), volume_ratio_20=1.10),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 1), volume_ratio_20=1.20),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 2), volume_ratio_20=1.10),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 3), volume_ratio_20=1.00),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2024, 12, 31), volume_ratio_20=1.10),
            self.diagnostic_observation(symbol="BBB", trading_date=date(2025, 1, 4), analysis_close=80.0, volume_ratio_20=2.00),
        )
        statuses = {
            ("AAA", date(2025, 1, 1)): OutcomeEvaluationStatus.HIT,
            ("AAA", date(2025, 1, 2)): OutcomeEvaluationStatus.HIT,
            ("AAA", date(2025, 1, 3)): OutcomeEvaluationStatus.MISS,
            ("AAA", date(2025, 1, 25)): OutcomeEvaluationStatus.MISS,
            ("AAA", date(2025, 12, 31)): OutcomeEvaluationStatus.HIT,
            ("BBB", date(2025, 1, 1)): OutcomeEvaluationStatus.MISS,
            ("BBB", date(2025, 1, 2)): OutcomeEvaluationStatus.HIT,
            ("BBB", date(2025, 1, 3)): OutcomeEvaluationStatus.INCOMPLETE,
            ("BBB", date(2024, 12, 31)): OutcomeEvaluationStatus.NOT_EVALUABLE,
            ("BBB", date(2025, 1, 4)): OutcomeEvaluationStatus.HIT,
        }
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
            price_series_by_symbol={
                "AAA": self.price_series("AAA", observations),
                "BBB": self.price_series("BBB", observations),
            },
            config=HistoricalConditionOutcomeComparisonConfig(
                outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
            ),
            outcome_evaluator=lambda signal_event, price_series, outcome_definition: self.outcome(
                signal_event,
                statuses.get((signal_event.symbol, signal_event.signal_date), OutcomeEvaluationStatus.MISS),
            ),
            generated_at=GENERATED_AT,
        )

    def test_config_requires_exact_batch_3_thresholds_and_baseline(self):
        self.assertEqual(VolumeThresholdRobustnessConfig().candidate_thresholds, DEFAULT_ROBUSTNESS_THRESHOLDS)
        self.assertEqual(VolumeThresholdRobustnessConfig().baseline_threshold, 1.20)

        invalid = (
            {"candidate_thresholds": (1.00, 1.20)},
            {"candidate_thresholds": (0.80, 1.00, 1.10, 1.20)},
            {"candidate_thresholds": (1.10, 1.00, 1.20)},
            {"baseline_threshold": 1.10},
            {"warmup_trading_bars": 59},
            {"outcome_horizon_bars": 21},
            {"overlap_reduction_spacing_bars": 19},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(VolumeThresholdRobustnessAnalysisError):
                    VolumeThresholdRobustnessConfig(**kwargs)

    def test_daily_aggregate_counts_reconcile_and_do_not_average_symbol_percentages(self):
        result = analyze_volume_threshold_robustness(self.comparison_result(), generated_at=GENERATED_AT)
        rows = {row.threshold: row for row in result.daily_summaries}

        self.assertEqual(rows[1.20].observation_count, 3)
        self.assertEqual(rows[1.20].hit_count, 1)
        self.assertEqual(rows[1.20].miss_count, 2)
        self.assertEqual(rows[1.20].resolved_count, 3)
        self.assertEqual(rows[1.20].historical_hit_rate, 1 / 3)
        self.assertEqual(rows[1.20].delta_hit_rate_vs_1_20_pp, 0)

        self.assertEqual(rows[1.10].observation_count, 7)
        self.assertEqual(rows[1.10].hit_count, 4)
        self.assertEqual(rows[1.10].miss_count, 2)
        self.assertEqual(rows[1.10].not_evaluable_count, 1)
        self.assertEqual(rows[1.10].resolved_count, 6)
        self.assertEqual(rows[1.10].historical_hit_rate, 4 / 6)
        self.assertAlmostEqual(rows[1.10].delta_hit_rate_vs_1_20_pp, (4 / 6 - 1 / 3) * 100)

        self.assertEqual(rows[1.00].observation_count, 9)
        self.assertEqual(rows[1.00].hit_count, 4)
        self.assertEqual(rows[1.00].miss_count, 3)
        self.assertEqual(rows[1.00].incomplete_count, 1)
        self.assertEqual(rows[1.00].not_evaluable_count, 1)
        self.assertEqual(rows[1.00].resolved_count, 7)
        self.assertEqual(rows[1.00].historical_hit_rate, 4 / 7)
        self.assertNotEqual(rows[1.00].historical_hit_rate, (3 / 4 + 1 / 3) / 2)

    def test_per_symbol_factual_deltas_and_cross_symbol_isolation(self):
        result = analyze_volume_threshold_robustness(self.comparison_result())
        rows = {(row.symbol, row.threshold): row for row in result.per_symbol_summaries}

        self.assertEqual(rows[("AAA", 1.20)].observation_count, 2)
        self.assertEqual(rows[("AAA", 1.20)].historical_hit_rate, 1 / 2)
        self.assertEqual(rows[("AAA", 1.10)].observation_count_delta_vs_1_20, 2)
        self.assertEqual(rows[("AAA", 1.10)].hit_count, 3)
        self.assertEqual(rows[("AAA", 1.10)].miss_count, 1)
        self.assertAlmostEqual(rows[("AAA", 1.10)].delta_hit_rate_vs_1_20_pp, 25.0)

        self.assertEqual(rows[("BBB", 1.20)].observation_count, 1)
        self.assertEqual(rows[("BBB", 1.20)].historical_hit_rate, 0.0)
        self.assertEqual(rows[("BBB", 1.10)].observation_count_delta_vs_1_20, 2)
        self.assertEqual(rows[("BBB", 1.10)].hit_count, 1)
        self.assertEqual(rows[("BBB", 1.10)].miss_count, 1)
        self.assertEqual(rows[("BBB", 1.10)].not_evaluable_count, 1)
        self.assertEqual(rows[("BBB", 1.10)].delta_hit_rate_vs_1_20_pp, 50.0)

    def test_per_year_uses_observation_year_and_zero_resolved_is_none(self):
        result = analyze_volume_threshold_robustness(self.comparison_result())
        rows = {(row.year, row.threshold): row for row in result.per_year_summaries}

        self.assertEqual(rows[(2025, 1.10)].observation_count, 6)
        self.assertEqual(rows[(2025, 1.10)].hit_count, 4)
        self.assertEqual(rows[(2025, 1.10)].miss_count, 2)
        self.assertEqual(rows[(2025, 1.10)].resolved_count, 6)
        self.assertEqual(rows[(2025, 1.10)].historical_hit_rate, 4 / 6)
        self.assertNotIn((2026, 1.10), {(row.year, row.threshold) for row in result.per_year_summaries})

        self.assertEqual(rows[(2024, 1.10)].observation_count, 1)
        self.assertEqual(rows[(2024, 1.10)].not_evaluable_count, 1)
        self.assertEqual(rows[(2024, 1.10)].resolved_count, 0)
        self.assertIsNone(rows[(2024, 1.10)].historical_hit_rate)
        self.assertIsNone(rows[(2024, 1.10)].delta_hit_rate_vs_1_20_pp)

    def test_future_outcome_crossing_year_boundary_still_belongs_to_observation_year(self):
        result = analyze_volume_threshold_robustness(self.comparison_result())
        rows = {(row.year, row.threshold): row for row in result.per_year_summaries}

        self.assertEqual(rows[(2025, 1.10)].hit_count, 4)
        self.assertNotIn((2026, 1.10), rows)

    def test_overlap_reduced_is_deterministic_trading_bar_spaced_and_keeps_daily_result(self):
        comparison = self.comparison_result()
        before = comparison.outcome_observations
        first = analyze_volume_threshold_robustness(comparison, generated_at=GENERATED_AT)
        second = analyze_volume_threshold_robustness(comparison, generated_at=GENERATED_AT)
        rows = {row.threshold: row for row in first.overlap_reduced_summaries}

        self.assertEqual(first, second)
        self.assertEqual(comparison.outcome_observations, before)
        self.assertEqual(rows[1.00].daily_observation_count, 9)
        self.assertEqual(rows[1.00].overlap_reduced_observation_count, 3)
        self.assertTrue(rows[1.00].selected_spacing_invariant_passed)
        self.assertEqual(
            tuple((item.symbol, item.trading_date) for item in rows[1.00].selected_observations),
            (
                ("AAA", date(2025, 1, 1)),
                ("AAA", date(2025, 1, 25)),
                ("BBB", date(2024, 12, 31)),
            ),
        )
        self.assertGreaterEqual(
            rows[1.00].selected_observations[1].trading_bar_index
            - rows[1.00].selected_observations[0].trading_bar_index,
            20,
        )

    def test_overlap_reduced_uses_trading_bar_distance_not_calendar_day_distance(self):
        rows = {
            row.threshold: row
            for row in analyze_volume_threshold_robustness(self.comparison_result()).overlap_reduced_summaries
        }
        selected_aaa_dates = [
            item.trading_date
            for item in rows[1.20].selected_observations
            if item.symbol == "AAA"
        ]

        self.assertEqual(selected_aaa_dates, [date(2025, 1, 1), date(2025, 1, 25)])

    def test_overlap_reduced_accepts_explicit_prepared_trading_bar_index(self):
        comparison = self.comparison_result()
        reduced_observations = tuple(
            observation for observation in comparison.outcome_observations
            if observation.symbol == "AAA"
            and observation.trading_date in (date(2025, 1, 1), date(2025, 1, 25))
        )
        comparison = replace(
            comparison,
            outcome_observations=reduced_observations,
        )
        price_series = HistoricalPriceSeries(
            symbol="AAA",
            currency="USD",
            bars=tuple(
                self.price_bar("AAA", date(2025, 1, day))
                for day in range(1, 26)
            ),
            fetched_at=FETCHED_AT,
            is_stale=False,
        )

        rows = {
            row.threshold: row
            for row in analyze_volume_threshold_robustness(
                comparison,
                price_series_by_symbol={"AAA": price_series},
            ).overlap_reduced_summaries
        }

        self.assertEqual(
            tuple(item.trading_date for item in rows[1.20].selected_observations),
            (date(2025, 1, 1), date(2025, 1, 25)),
        )
        self.assertEqual(
            tuple(item.trading_bar_index for item in rows[1.20].selected_observations),
            (0, 24),
        )
        self.assertTrue(rows[1.20].selected_spacing_invariant_passed)

    def test_incomplete_and_not_evaluable_semantics_are_preserved(self):
        rows = {
            row.threshold: row
            for row in analyze_volume_threshold_robustness(self.comparison_result()).daily_summaries
        }

        self.assertEqual(rows[1.00].incomplete_count, 1)
        self.assertEqual(rows[1.00].not_evaluable_count, 1)
        self.assertEqual(rows[1.00].historical_hit_rate, 4 / 7)

    def test_duplicate_identity_is_rejected(self):
        comparison = self.comparison_result()
        duplicate = comparison.outcome_observations[0]
        comparison = replace(
            comparison,
            outcome_observations=comparison.outcome_observations + (duplicate,),
        )

        with self.assertRaises(VolumeThresholdRobustnessAnalysisError):
            analyze_volume_threshold_robustness(comparison)

    def test_no_fetch_sqlite_reload_technical_rebuild_diagnostics_or_outcome_rerun(self):
        comparison = self.comparison_result()

        with patch("historical_price_service.get_historical_prices") as fetch:
            with patch("technical_indicator_service.build_technical_indicator_series") as builder:
                with patch("signal_condition_diagnostics_service.run_historical_condition_diagnostics") as diagnostics:
                    with patch("signal_outcome_service.evaluate_historical_outcome") as evaluator:
                        analyze_volume_threshold_robustness(comparison)

        fetch.assert_not_called()
        builder.assert_not_called()
        diagnostics.assert_not_called()
        evaluator.assert_not_called()

    def test_result_metadata_and_no_recommendation_probability_ranking_fields(self):
        result = analyze_volume_threshold_robustness(self.comparison_result(), generated_at=GENERATED_AT)

        self.assertEqual(result.signal_definition_id, TECHNICAL_EXAMPLE_SIGNAL_V1.id)
        self.assertEqual(result.candidate_thresholds, (1.00, 1.10, 1.20))
        self.assertEqual(result.baseline_threshold, 1.20)
        self.assertEqual(result.warmup_trading_bars, 60)
        self.assertEqual(result.outcome_horizon_bars, 20)
        self.assertEqual(result.observation_unit, "DAILY")
        self.assertTrue(result.overlap_possible)
        self.assertEqual(result.overlap_reduction_spacing_bars, 20)
        self.assertEqual(result.generated_at, GENERATED_AT)

        names = {
            field.name
            for model in (
                VolumeThresholdRobustnessConfig,
                ThresholdDailyRobustnessSummary,
                ThresholdSymbolRobustnessSummary,
                ThresholdYearRobustnessSummary,
                OverlapReducedThresholdSummary,
                VolumeThresholdRobustnessResult,
            )
            for field in fields(model)
        }
        forbidden = ("score", "probability", "recommendation", "rank", "best", "optimal")
        self.assertFalse(any(term in name for term in forbidden for name in names))


if __name__ == "__main__":
    unittest.main()
