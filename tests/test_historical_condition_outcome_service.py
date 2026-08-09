import sys
import unittest
from dataclasses import fields
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from historical_condition_outcome_service import DEFAULT_DIAGNOSTIC_WARMUP_TRADING_BARS
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonConfig
from historical_condition_outcome_service import build_diagnostic_technical_series
from historical_condition_outcome_service import compare_historical_condition_outcomes
from historical_condition_outcome_service import prepare_diagnostic_research_series
from models import HistoricalOutcomeResult
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeEvaluationStatus
from models import SignalEvaluationStatus
from models import TechnicalIndicatorSnapshot
from signal_condition_diagnostics_service import ConditionDiagnosticObservation
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsConfig
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsService
from signal_condition_diagnostics_service import build_condition_diagnostic_observation
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import evaluate_signal_conditions


FETCHED_AT = datetime(2026, 8, 9, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 9, 2, 0, tzinfo=UTC)


class HistoricalConditionOutcomeServiceTestCase(unittest.TestCase):

    def config(self):
        return HistoricalConditionDiagnosticsConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
            signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
        )

    def comparison_config(self):
        return HistoricalConditionOutcomeComparisonConfig(
            outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
        )

    def snapshot(self, symbol="TEST", trading_date=date(2025, 1, 1), **overrides):
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

    def observation(self, **overrides):
        match = evaluate_signal_conditions(
            self.snapshot(**overrides),
            TECHNICAL_EXAMPLE_SIGNAL_V1,
        )
        return build_condition_diagnostic_observation(match)

    def diagnostic_result(self, observations):
        return HistoricalConditionDiagnosticsService(
            price_loader=lambda *args, **kwargs: self.fail("price loader should not be called"),
        ).run_diagnostics(
            ("TEST",),
            self.config(),
            technical_series_by_symbol={
                "TEST": type(
                    "Series",
                    (),
                    {
                        "symbol": "TEST",
                        "snapshots": tuple(observation.source_snapshot for observation in observations),
                    },
                )()
            },
        )

    def price_bar(self, trading_date, *, high=100.0, close=100.0):
        return HistoricalPriceBar(
            symbol="TEST",
            trading_date=trading_date,
            open=close,
            high=high,
            low=close - 1.0,
            close=close,
            adjusted_close=None,
            volume=1000,
        )

    def price_series(self, bars):
        return HistoricalPriceSeries(
            symbol="TEST",
            currency="USD",
            bars=tuple(bars),
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

    def test_research_series_uses_exact_warmup_and_outcome_extension(self):
        start = date(2025, 1, 1)
        end = date(2025, 1, 5)
        bars = [
            self.price_bar(start - timedelta(days=80 - index))
            for index in range(80)
        ]
        bars.extend(self.price_bar(start + timedelta(days=index)) for index in range(5))
        bars.extend(self.price_bar(end + timedelta(days=index + 1)) for index in range(25))

        prepared = prepare_diagnostic_research_series(
            self.price_series(bars),
            observation_start=start,
            observation_end=end,
            outcome_horizon_bars=20,
        )

        self.assertEqual(len([bar for bar in prepared.bars if bar.trading_date < start]), DEFAULT_DIAGNOSTIC_WARMUP_TRADING_BARS)
        self.assertEqual(len([bar for bar in prepared.bars if start <= bar.trading_date <= end]), 5)
        self.assertEqual(len([bar for bar in prepared.bars if bar.trading_date > end]), 20)
        self.assertEqual(prepared.bars[60].trading_date, start)

    def test_extra_unrelated_earlier_history_does_not_change_observation_denominator(self):
        start = date(2025, 1, 1)
        end = date(2025, 1, 3)
        base_bars = [
            self.price_bar(start - timedelta(days=60 - index), high=100 + index, close=100 + index)
            for index in range(60)
        ]
        base_bars.extend(
            self.price_bar(start + timedelta(days=index), high=200 + index, close=200 + index)
            for index in range(3)
        )
        base_bars.extend(
            self.price_bar(end + timedelta(days=index + 1), high=210 + index, close=210 + index)
            for index in range(20)
        )
        extra_bars = [
            self.price_bar(start - timedelta(days=560 - index), high=50 + index, close=50 + index)
            for index in range(500)
        ]

        first = prepare_diagnostic_research_series(
            self.price_series(base_bars),
            observation_start=start,
            observation_end=end,
            outcome_horizon_bars=20,
        )
        second = prepare_diagnostic_research_series(
            self.price_series(extra_bars + base_bars),
            observation_start=start,
            observation_end=end,
            outcome_horizon_bars=20,
        )

        first_diagnostics = HistoricalConditionDiagnosticsService().run_diagnostics(
            ("TEST",),
            HistoricalConditionDiagnosticsConfig(start, end, TECHNICAL_EXAMPLE_SIGNAL_V1),
            technical_series_by_symbol={"TEST": build_diagnostic_technical_series(first)},
        )
        second_diagnostics = HistoricalConditionDiagnosticsService().run_diagnostics(
            ("TEST",),
            HistoricalConditionDiagnosticsConfig(start, end, TECHNICAL_EXAMPLE_SIGNAL_V1),
            technical_series_by_symbol={"TEST": build_diagnostic_technical_series(second)},
        )

        self.assertEqual(first_diagnostics.total_observation_count, 3)
        self.assertEqual(second_diagnostics.total_observation_count, 3)
        self.assertEqual(
            [row.observation_count for row in first_diagnostics.match_count_distribution],
            [row.observation_count for row in second_diagnostics.match_count_distribution],
        )

    def test_match_count_outcome_summary_uses_historical_hit_rate_denominator(self):
        observations = (
            self.observation(trading_date=date(2025, 1, 1), analysis_close=80, sma_20=100, sma_60=110, volume_ratio_20=0.5, rsi_14=40, distance_to_prior_60d_high=-0.20),
            self.observation(trading_date=date(2025, 1, 2)),
            self.observation(trading_date=date(2025, 1, 3)),
            self.observation(trading_date=date(2025, 1, 4)),
        )
        statuses = iter((
            OutcomeEvaluationStatus.INCOMPLETE,
            OutcomeEvaluationStatus.HIT,
            OutcomeEvaluationStatus.MISS,
            OutcomeEvaluationStatus.NOT_EVALUABLE,
        ))

        def evaluator(signal_event, price_series, outcome_definition):
            return self.outcome(signal_event, next(statuses))

        result = compare_historical_condition_outcomes(
            self.diagnostic_result(observations),
            price_series_by_symbol={"TEST": self.price_series([self.price_bar(date(2025, 1, day)) for day in range(1, 25)])},
            config=self.comparison_config(),
            outcome_evaluator=evaluator,
            generated_at=GENERATED_AT,
        )

        zero = result.match_count_outcome_summaries[0].outcome_summary
        five = result.match_count_outcome_summaries[5].outcome_summary
        self.assertEqual(zero.observation_count, 1)
        self.assertEqual(zero.incomplete_count, 1)
        self.assertIsNone(zero.historical_hit_rate)
        self.assertEqual(five.observation_count, 3)
        self.assertEqual(five.hit_count, 1)
        self.assertEqual(five.miss_count, 1)
        self.assertEqual(five.not_evaluable_count, 1)
        self.assertEqual(five.resolved_count, 2)
        self.assertEqual(five.historical_hit_rate, 0.5)

    def test_four_of_five_missing_condition_groups_each_observation_once(self):
        observations = (
            self.observation(trading_date=date(2025, 1, 1), volume_ratio_20=0.5),
            self.observation(trading_date=date(2025, 1, 2), rsi_14=80),
            self.observation(trading_date=date(2025, 1, 3), distance_to_prior_60d_high=-0.20),
        )
        statuses = iter((
            OutcomeEvaluationStatus.HIT,
            OutcomeEvaluationStatus.MISS,
            OutcomeEvaluationStatus.HIT,
        ))

        result = compare_historical_condition_outcomes(
            self.diagnostic_result(observations),
            price_series_by_symbol={"TEST": self.price_series([self.price_bar(date(2025, 1, day)) for day in range(1, 25)])},
            config=self.comparison_config(),
            outcome_evaluator=lambda signal_event, price_series, outcome_definition: self.outcome(signal_event, next(statuses)),
        )

        rows = {row.condition_id: row.outcome_summary for row in result.missing_condition_outcome_summaries}
        self.assertEqual(rows["volume_ratio_20"].observation_count, 1)
        self.assertEqual(rows["rsi_14"].observation_count, 1)
        self.assertEqual(rows["distance_to_prior_60d_high"].observation_count, 1)
        self.assertEqual(rows["analysis_close_vs_sma_20"].observation_count, 0)
        self.assertEqual(sum(row.observation_count for row in rows.values()), 3)

    def test_condition_side_identity_is_preserved_and_existing_outcome_evaluator_is_injected(self):
        observation = self.observation(trading_date=date(2025, 1, 1), volume_ratio_20=0.5)
        calls = []

        def evaluator(signal_event, price_series, outcome_definition):
            calls.append((signal_event, outcome_definition.id))
            return self.outcome(signal_event, OutcomeEvaluationStatus.HIT)

        result = compare_historical_condition_outcomes(
            self.diagnostic_result((observation,)),
            price_series_by_symbol={"TEST": self.price_series([self.price_bar(date(2025, 1, day)) for day in range(1, 25)])},
            config=self.comparison_config(),
            outcome_evaluator=evaluator,
        )

        self.assertEqual(len(calls), 1)
        outcome_observation = result.outcome_observations[0]
        self.assertEqual(outcome_observation.diagnostic_observation, observation)
        self.assertEqual(outcome_observation.matched_condition_count, 4)
        self.assertEqual(outcome_observation.missing_condition_ids, ("volume_ratio_20",))
        self.assertIn("volume_ratio_20", outcome_observation.source_observation_id)

    def test_real_outcome_uses_frozen_reference_high_and_horizon_only(self):
        observation = self.observation(
            trading_date=date(2025, 1, 1),
            prior_high_60d=100.0,
            distance_to_prior_60d_high=0.0,
        )
        bars = [self.price_bar(date(2025, 1, 1), high=100.0, close=100.0)]
        bars.extend(self.price_bar(date(2025, 1, day), high=99.0, close=99.0) for day in range(2, 22))
        bars.append(self.price_bar(date(2025, 1, 22), high=999.0, close=999.0))

        result = compare_historical_condition_outcomes(
            self.diagnostic_result((observation,)),
            price_series_by_symbol={"TEST": self.price_series(bars)},
            config=self.comparison_config(),
        )

        outcome = result.outcome_observations[0].outcome
        self.assertEqual(outcome.reference_high, 100.0)
        self.assertEqual(outcome.status, OutcomeEvaluationStatus.MISS)
        self.assertEqual(outcome.available_future_bars, 20)

    def test_per_symbol_aggregate_sums_observations_not_symbol_rates(self):
        first = self.observation(symbol="AAA", trading_date=date(2025, 1, 1))
        second = self.observation(symbol="AAA", trading_date=date(2025, 1, 2))
        third = self.observation(symbol="BBB", trading_date=date(2025, 1, 1))
        diagnostics = HistoricalConditionDiagnosticsService().run_diagnostics(
            ("AAA", "BBB"),
            self.config(),
            technical_series_by_symbol={
                "AAA": type("Series", (), {"symbol": "AAA", "snapshots": (first.source_snapshot, second.source_snapshot)})(),
                "BBB": type("Series", (), {"symbol": "BBB", "snapshots": (third.source_snapshot,)})(),
            },
        )
        statuses = iter((
            OutcomeEvaluationStatus.HIT,
            OutcomeEvaluationStatus.MISS,
            OutcomeEvaluationStatus.MISS,
        ))

        def evaluator(signal_event, price_series, outcome_definition):
            return self.outcome(signal_event, next(statuses))

        result = compare_historical_condition_outcomes(
            diagnostics,
            price_series_by_symbol={
                "AAA": HistoricalPriceSeries("AAA", "USD", tuple(self.price_bar(date(2025, 1, day)) for day in range(1, 25)), FETCHED_AT),
                "BBB": HistoricalPriceSeries("BBB", "USD", tuple(self.price_bar(date(2025, 1, day)) for day in range(1, 25)), FETCHED_AT),
            },
            config=self.comparison_config(),
            outcome_evaluator=evaluator,
        )

        five = result.match_count_outcome_summaries[5].outcome_summary
        self.assertEqual(five.observation_count, 3)
        self.assertEqual(five.resolved_count, 3)
        self.assertEqual(five.historical_hit_rate, 1 / 3)
        self.assertEqual({summary.symbol for summary in result.per_symbol_summaries}, {"AAA", "BBB"})

    def test_only_evaluable_batch_one_observations_enter_match_count_outcome_buckets(self):
        observations = (
            self.observation(trading_date=date(2025, 1, 1), rsi_14=None),
            self.observation(trading_date=date(2025, 1, 2)),
        )

        result = compare_historical_condition_outcomes(
            self.diagnostic_result(observations),
            price_series_by_symbol={"TEST": self.price_series([self.price_bar(date(2025, 1, day)) for day in range(1, 25)])},
            config=self.comparison_config(),
            outcome_evaluator=lambda signal_event, price_series, outcome_definition: self.outcome(signal_event, OutcomeEvaluationStatus.HIT),
        )

        self.assertEqual(result.diagnostics_result.total_observation_count, 2)
        self.assertEqual(result.observation_count, 1)
        self.assertEqual(sum(row.outcome_summary.observation_count for row in result.match_count_outcome_summaries), 1)
        self.assertEqual(result.match_count_outcome_summaries[5].outcome_summary.observation_count, 1)


if __name__ == "__main__":
    unittest.main()
