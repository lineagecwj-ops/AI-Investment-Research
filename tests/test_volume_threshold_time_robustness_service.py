import math
import sys
import unittest
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import HistoricalOutcomeResult
from models import OutcomeEvaluationStatus
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from volume_threshold_time_robustness_service import ACTIVE_V1_1_RESEARCH_THRESHOLDS
from volume_threshold_time_robustness_service import FORMAL_V1_BASELINE_THRESHOLD
from volume_threshold_time_robustness_service import TimeRobustnessPeriod
from volume_threshold_time_robustness_service import VolumeThresholdTimeRobustnessAnalysisError
from volume_threshold_time_robustness_service import analyze_volume_threshold_time_robustness
from volume_threshold_time_robustness_service import _event_concentration
from volume_threshold_time_robustness_service import _first_qualification_events
from volume_threshold_time_robustness_service import _outcome_summary


GENERATED_AT = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
OTHER_CONDITIONS = ("analysis_close_vs_sma_20", "sma_20_vs_sma_60", "rsi_14", "distance_to_prior_60d_high")


@dataclass(frozen=True)
class FakeCondition:

    metric: str

    secondary_metric: str | None = None


class VolumeThresholdTimeRobustnessServiceTestCase(unittest.TestCase):

    def observation(
        self,
        symbol,
        trading_date,
        *,
        volume_ratio_20,
        status=OutcomeEvaluationStatus.HIT,
        other_conditions_pass=True,
    ):
        passed = OTHER_CONDITIONS if other_conditions_pass else OTHER_CONDITIONS[:3]
        matched = len(passed) + (1 if isinstance(volume_ratio_20, (int, float)) and math.isfinite(volume_ratio_20) and volume_ratio_20 >= 1.20 else 0)
        diagnostic = SimpleNamespace(
            evaluated_conditions=(
                FakeCondition("analysis_close", "sma_20"),
                FakeCondition("sma_20", "sma_60"),
                FakeCondition("rsi_14"),
                FakeCondition("distance_to_prior_60d_high"),
                FakeCondition("volume_ratio_20"),
            ),
            source_snapshot=SimpleNamespace(volume_ratio_20=volume_ratio_20),
        )
        outcome = HistoricalOutcomeResult(
            symbol=symbol,
            signal_id=f"{symbol}-{trading_date.isoformat()}",
            signal_date=trading_date,
            outcome_definition_id=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id,
            status=status,
            horizon_bars=20,
            available_future_bars=20,
            reference_high=100.0,
            intraday_target_hit=status is OutcomeEvaluationStatus.HIT,
            intraday_target_hit_date=trading_date if status is OutcomeEvaluationStatus.HIT else None,
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
        return SimpleNamespace(
            source_observation_id=f"{symbol}-{trading_date.isoformat()}",
            symbol=symbol,
            trading_date=trading_date,
            signal_definition_id=TECHNICAL_EXAMPLE_SIGNAL_V1.id,
            outcome_definition_id=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id,
            matched_condition_count=matched,
            total_condition_count=5,
            passed_condition_ids=passed,
            missing_condition_ids=tuple(),
            diagnostic_observation=diagnostic,
            outcome=outcome,
            status=status,
        )

    def comparison(self, observations, symbols=("AAA", "BBB", "ZERO")):
        return SimpleNamespace(
            outcome_observations=tuple(observations),
            observation_unit="DAILY",
            overlap_possible=True,
            diagnostics_result=SimpleNamespace(
                normalized_symbols=tuple(symbols),
                config=SimpleNamespace(signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1),
            ),
        )

    def test_active_thresholds_exclude_1_00_and_new_tuned_thresholds(self):
        self.assertEqual(ACTIVE_V1_1_RESEARCH_THRESHOLDS, (1.10, 1.20))
        self.assertEqual(FORMAL_V1_BASELINE_THRESHOLD, 1.20)
        with self.assertRaises(VolumeThresholdTimeRobustnessAnalysisError):
            analyze_volume_threshold_time_robustness(
                self.comparison(()),
                thresholds=(1.00, 1.10, 1.20),
            )
        with self.assertRaises(VolumeThresholdTimeRobustnessAnalysisError):
            analyze_volume_threshold_time_robustness(
                self.comparison(()),
                thresholds=(1.10, 1.15, 1.20),
            )

    def test_sub_period_boundaries_group_by_observation_date_and_reconcile(self):
        observations = (
            self.observation("AAA", date(2018, 1, 1), volume_ratio_20=1.20, status=OutcomeEvaluationStatus.HIT),
            self.observation("AAA", date(2020, 12, 31), volume_ratio_20=1.10, status=OutcomeEvaluationStatus.MISS),
            self.observation("AAA", date(2021, 1, 1), volume_ratio_20=1.20, status=OutcomeEvaluationStatus.HIT),
            self.observation("AAA", date(2023, 12, 31), volume_ratio_20=1.10, status=OutcomeEvaluationStatus.HIT),
            self.observation("BBB", date(2024, 12, 31), volume_ratio_20=1.20, status=OutcomeEvaluationStatus.MISS),
            self.observation("BBB", date(2025, 1, 1), volume_ratio_20=1.10, status=OutcomeEvaluationStatus.HIT),
        )

        result = analyze_volume_threshold_time_robustness(
            self.comparison(observations),
            generated_at=GENERATED_AT,
        )

        period_rows = {
            (row.period_name, row.threshold_summary.threshold): row.threshold_summary
            for row in result.period_summaries
        }
        self.assertEqual(period_rows[("PERIOD_A", 1.10)].observation_count, 2)
        self.assertEqual(period_rows[("PERIOD_A", 1.20)].observation_count, 1)
        self.assertEqual(period_rows[("PERIOD_B", 1.10)].observation_count, 2)
        self.assertEqual(period_rows[("PERIOD_C", 1.20)].miss_count, 1)
        self.assertEqual(period_rows[("PERIOD_D", 1.10)].hit_count, 1)

        daily = {row.threshold: row for row in result.daily_summaries}
        for threshold in ACTIVE_V1_1_RESEARCH_THRESHOLDS:
            self.assertEqual(
                sum(row.threshold_summary.observation_count for row in result.period_summaries if row.threshold_summary.threshold == threshold),
                daily[threshold].observation_count,
            )
            self.assertEqual(
                sum(row.threshold_summary.hit_count for row in result.period_summaries if row.threshold_summary.threshold == threshold),
                daily[threshold].hit_count,
            )
            self.assertEqual(
                sum(row.threshold_summary.miss_count for row in result.period_summaries if row.threshold_summary.threshold == threshold),
                daily[threshold].miss_count,
            )

    def test_zero_sample_period_and_hhr_denominator(self):
        periods = (
            TimeRobustnessPeriod("EMPTY", date(2018, 1, 1), date(2018, 12, 31)),
            TimeRobustnessPeriod("FILLED", date(2019, 1, 1), date(2019, 12, 31)),
        )
        observations = (
            self.observation("AAA", date(2019, 1, 2), volume_ratio_20=1.20, status=OutcomeEvaluationStatus.HIT),
            self.observation("AAA", date(2019, 1, 3), volume_ratio_20=1.20, status=OutcomeEvaluationStatus.INCOMPLETE),
            self.observation("AAA", date(2019, 1, 4), volume_ratio_20=1.20, status=OutcomeEvaluationStatus.NOT_EVALUABLE),
        )

        result = analyze_volume_threshold_time_robustness(
            self.comparison(observations),
            periods=periods,
            generated_at=GENERATED_AT,
        )

        rows = {(row.period_name, row.threshold_summary.threshold): row.threshold_summary for row in result.period_summaries}
        self.assertIsNone(rows[("EMPTY", 1.10)].historical_hit_rate)
        self.assertEqual(rows[("FILLED", 1.20)].observation_count, 3)
        self.assertEqual(rows[("FILLED", 1.20)].resolved_count, 1)
        self.assertEqual(rows[("FILLED", 1.20)].historical_hit_rate, 1.0)

    def test_first_qualification_event_episode_extraction(self):
        observations = (
            self.observation("AAA", date(2025, 1, 1), volume_ratio_20=1.00),
            self.observation("AAA", date(2025, 1, 2), volume_ratio_20=1.10),
            self.observation("AAA", date(2025, 1, 3), volume_ratio_20=1.30),
            self.observation("AAA", date(2025, 1, 4), volume_ratio_20=1.30),
            self.observation("AAA", date(2025, 1, 5), volume_ratio_20=1.00),
            self.observation("AAA", date(2025, 1, 6), volume_ratio_20=1.20),
            self.observation("BBB", date(2025, 1, 1), volume_ratio_20=1.30),
            self.observation("ZERO", date(2025, 1, 1), volume_ratio_20=0.50),
            self.observation("ZERO", date(2025, 1, 2), volume_ratio_20=None),
        )

        events_1_10 = _first_qualification_events(observations, 1.10)
        events_1_20 = _first_qualification_events(observations, 1.20)

        self.assertEqual(
            [(event.symbol, event.event_start_trading_date) for event in events_1_10],
            [("AAA", date(2025, 1, 2)), ("AAA", date(2025, 1, 6)), ("BBB", date(2025, 1, 1))],
        )
        self.assertEqual(
            [(event.symbol, event.event_start_trading_date) for event in events_1_20],
            [("AAA", date(2025, 1, 3)), ("AAA", date(2025, 1, 6)), ("BBB", date(2025, 1, 1))],
        )

    def test_first_event_reuses_attached_outcome_without_recompute(self):
        observations = (
            self.observation("AAA", date(2025, 1, 1), volume_ratio_20=1.20, status=OutcomeEvaluationStatus.MISS),
            self.observation("AAA", date(2025, 1, 2), volume_ratio_20=1.20, status=OutcomeEvaluationStatus.HIT),
        )

        events = _first_qualification_events(observations, 1.20)
        summary = _outcome_summary(tuple(event.source_observation for event in events))

        self.assertEqual(len(events), 1)
        self.assertIs(events[0].source_observation, observations[0])
        self.assertEqual(summary.miss_count, 1)
        self.assertEqual(summary.hit_count, 0)
        self.assertEqual(summary.historical_hit_rate, 0.0)

    def test_event_concentration_arithmetic_zero_and_tie_handling(self):
        self.assertIsNone(_event_concentration(1.10, ()).year_2025_share)

        observations = (
            self.observation("BBB", date(2024, 1, 1), volume_ratio_20=1.20),
            self.observation("AAA", date(2025, 1, 1), volume_ratio_20=1.20),
            self.observation("AAA", date(2025, 1, 3), volume_ratio_20=0.90),
            self.observation("AAA", date(2025, 1, 4), volume_ratio_20=1.20),
            self.observation("CCC", date(2025, 1, 1), volume_ratio_20=1.20),
        )
        events = _first_qualification_events(observations, 1.20)
        concentration = _event_concentration(1.20, events)

        self.assertEqual(concentration.event_count, 4)
        self.assertEqual(concentration.year_2025_share, 3 / 4)
        self.assertEqual(concentration.largest_year, 2025)
        self.assertEqual(concentration.top_1_symbol_share, 2 / 4)
        self.assertEqual(concentration.top_2_symbol_share, 3 / 4)
        self.assertEqual(concentration.top_5_symbol_share, 1.0)
        self.assertEqual(concentration.top_10_symbol_share, 1.0)


if __name__ == "__main__":
    unittest.main()
