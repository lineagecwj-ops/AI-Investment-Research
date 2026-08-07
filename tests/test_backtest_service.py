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

from backtest_service import BacktestConfig
from backtest_service import BacktestConfigurationError
from backtest_service import BacktestDataError
from backtest_service import HistoricalBacktestCase
from backtest_service import aggregate_backtest_cases
from backtest_service import build_backtest_id
from backtest_service import build_case_id
from backtest_service import get_backtest_case_price_window
from backtest_service import run_historical_backtest
from models import HistoricalOutcomeResult
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeDefinition
from models import OutcomeEvaluationStatus
from models import OutcomeType
from models import OverlappingSignalPolicy
from models import SignalConditionOperator
from models import SignalDefinition
from models import SignalEvent
from models import TechnicalIndicatorSeries
from models import TechnicalIndicatorSnapshot
from models import TechnicalSignalCondition


FETCHED_AT = datetime(2026, 8, 8, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 8, 2, 0, tzinfo=UTC)


class BacktestServiceTestCase(unittest.TestCase):

    def snapshot(self, trading_date, symbol="TEST", analysis_close=100.0):
        params = {
            field.name: None
            for field in fields(TechnicalIndicatorSnapshot)
        }
        params.update(
            symbol=symbol,
            trading_date=trading_date,
            analysis_close=analysis_close,
            sma_20=95.0,
            sma_60=90.0,
            volume_ratio_20=1.5,
            rsi_14=60.0,
            distance_to_prior_60d_high=-0.02,
            prior_high_60d=105.0,
            prior_low_60d=80.0,
        )
        return TechnicalIndicatorSnapshot(**params)

    def signal_definition(self):
        return SignalDefinition(
            id="test_signal_v1",
            name="Test Signal",
            conditions=(
                TechnicalSignalCondition(
                    metric="analysis_close",
                    operator=SignalConditionOperator.GREATER_THAN,
                    secondary_metric="sma_20",
                ),
            ),
            minimum_required_features=("analysis_close", "sma_20"),
            description="Test-only signal.",
        )

    def outcome_definition(self, horizon=5):
        return OutcomeDefinition(
            id=f"raw_high_breakout_60d_within_{horizon}d_v1",
            outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
            horizon_bars=horizon,
            reference_metric="prior_high_60d",
        )

    def config(self, **overrides):
        values = {
            "signal_definition": self.signal_definition(),
            "outcome_definition": self.outcome_definition(),
            "overlap_policy": OverlappingSignalPolicy.ALLOW_ALL,
            "cooldown_bars": None,
            "start_date": None,
            "end_date": None,
        }
        values.update(overrides)
        return BacktestConfig(**values)

    def bar(self, trading_date, close=100.0, *, high=None, symbol="TEST"):
        return HistoricalPriceBar(
            symbol=symbol,
            trading_date=trading_date,
            open=close,
            high=close + 1 if high is None else high,
            low=close - 1,
            close=close,
            adjusted_close=close,
            volume=1000,
        )

    def price_series(self, bars, symbol="TEST"):
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="USD",
            bars=tuple(bars),
            fetched_at=FETCHED_AT,
        )

    def technical_series(self, dates, symbol="TEST", closes=None):
        closes = closes or {}
        return TechnicalIndicatorSeries(
            symbol=symbol,
            snapshots=tuple(
                self.snapshot(trading_date, symbol=symbol, analysis_close=closes.get(trading_date, 100.0))
                for trading_date in dates
            ),
            generated_at=GENERATED_AT,
            source_price_fetched_at=FETCHED_AT,
        )

    def event(self, signal_date=date(2025, 1, 1), symbol="TEST", signal_id="test_signal_v1"):
        snapshot = self.snapshot(signal_date, symbol=symbol)
        return SignalEvent(
            symbol=symbol,
            signal_id=signal_id,
            signal_date=signal_date,
            signal_analysis_close=100.0,
            signal_raw_close=100.0,
            reference_high=105.0,
            reference_low=80.0,
            evaluation_status=None,
            feature_snapshot=snapshot,
            evaluated_conditions=tuple(),
        )

    def outcome(
        self,
        status,
        *,
        signal_date=date(2025, 1, 1),
        symbol="TEST",
        signal_id="test_signal_v1",
        outcome_id="test_outcome_v1",
        mfe=None,
        mae=None,
        end_return=None,
        hit_index=None,
    ):
        return HistoricalOutcomeResult(
            symbol=symbol,
            signal_id=signal_id,
            signal_date=signal_date,
            outcome_definition_id=outcome_id,
            status=status,
            horizon_bars=20,
            available_future_bars=20,
            reference_high=105.0,
            intraday_target_hit=status is OutcomeEvaluationStatus.HIT,
            intraday_target_hit_date=date(2025, 1, 1) + timedelta(days=hit_index or 1)
            if status is OutcomeEvaluationStatus.HIT else None,
            intraday_target_hit_bar_index=hit_index,
            close_target_hit=False,
            close_target_hit_date=None,
            close_target_hit_bar_index=None,
            max_close_return=mfe,
            max_close_return_date=None,
            max_adverse_return=mae,
            max_adverse_return_date=None,
            end_of_window_return=end_return,
        )

    def case(self, status, *, signal_date, mfe=None, mae=None, end_return=None, hit_index=None):
        event = self.event(signal_date=signal_date)
        outcome = self.outcome(
            status,
            signal_date=signal_date,
            mfe=mfe,
            mae=mae,
            end_return=end_return,
            hit_index=hit_index,
        )
        return HistoricalBacktestCase(
            symbol=event.symbol,
            signal_event=event,
            outcome=outcome,
            case_id=build_case_id(event.symbol, event, outcome),
        )

    def aggregate(self, cases):
        return aggregate_backtest_cases(
            tuple(cases),
            symbol="TEST",
            config=self.config(),
            generated_at=GENERATED_AT,
        )

    def test_empty_cases_report_has_zero_counts_and_none_aggregates(self):
        report = self.aggregate(tuple())

        self.assertEqual(report.raw_signal_count, 0)
        self.assertEqual(report.filtered_signal_count, 0)
        self.assertEqual(report.resolved_count, 0)
        self.assertIsNone(report.historical_hit_rate)
        self.assertIsNone(report.average_max_close_return)
        self.assertEqual(report.cases, tuple())

    def test_all_hit_and_all_miss_hit_rate_edges(self):
        all_hit = self.aggregate((
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 1), hit_index=1),
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 2), hit_index=2),
        ))
        all_miss = self.aggregate((
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 1)),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 2)),
        ))

        self.assertEqual(all_hit.historical_hit_rate, 1.0)
        self.assertEqual(all_miss.historical_hit_rate, 0.0)

    def test_mixed_denominator_excludes_incomplete(self):
        report = self.aggregate((
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 1), hit_index=1),
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 2), hit_index=1),
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 3), hit_index=1),
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 4), hit_index=1),
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 5), hit_index=1),
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 6), hit_index=1),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 7)),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 8)),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 9)),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 10)),
            self.case(OutcomeEvaluationStatus.INCOMPLETE, signal_date=date(2025, 1, 11)),
            self.case(OutcomeEvaluationStatus.INCOMPLETE, signal_date=date(2025, 1, 12)),
            self.case(OutcomeEvaluationStatus.INCOMPLETE, signal_date=date(2025, 1, 13)),
        ))

        self.assertEqual(report.resolved_count, 10)
        self.assertEqual(report.incomplete_count, 3)
        self.assertEqual(report.historical_hit_rate, 0.6)

    def test_not_evaluable_is_counted_but_excluded_from_denominator(self):
        report = self.aggregate((
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 1), hit_index=1),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 2)),
            self.case(OutcomeEvaluationStatus.NOT_EVALUABLE, signal_date=date(2025, 1, 3)),
        ))

        self.assertEqual(report.not_evaluable_count, 1)
        self.assertEqual(report.resolved_count, 2)
        self.assertEqual(report.historical_hit_rate, 0.5)

    def test_only_incomplete_hit_rate_is_none_not_zero(self):
        report = self.aggregate((
            self.case(OutcomeEvaluationStatus.INCOMPLETE, signal_date=date(2025, 1, 1)),
            self.case(OutcomeEvaluationStatus.INCOMPLETE, signal_date=date(2025, 1, 2)),
        ))

        self.assertEqual(report.resolved_count, 0)
        self.assertIsNone(report.historical_hit_rate)

    def test_reference_aggregate_keeps_mean_median_and_sample_counts(self):
        report = self.aggregate((
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 1), mfe=0.10, mae=-0.03, end_return=0.08, hit_index=5),
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 2), mfe=0.06, mae=-0.04, end_return=0.02, hit_index=10),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 3), mfe=0.02, mae=-0.08, end_return=-0.05),
            self.case(OutcomeEvaluationStatus.INCOMPLETE, signal_date=date(2025, 1, 4)),
        ))

        self.assertEqual(report.resolved_count, 3)
        self.assertAlmostEqual(report.historical_hit_rate, 2 / 3)
        self.assertAlmostEqual(report.average_max_close_return, 0.06)
        self.assertAlmostEqual(report.median_max_close_return, 0.06)
        self.assertAlmostEqual(report.average_max_adverse_return, -0.05)
        self.assertAlmostEqual(report.median_max_adverse_return, -0.04)
        self.assertAlmostEqual(report.average_end_return, 0.016666666666666666)
        self.assertAlmostEqual(report.median_end_return, 0.02)
        self.assertEqual(report.max_return_sample_count, 3)
        self.assertEqual(report.end_return_sample_count, 3)
        self.assertEqual(report.average_hit_bar_index, 7.5)
        self.assertEqual(report.median_hit_bar_index, 7.5)

    def test_early_hit_enters_denominator_without_return_metrics(self):
        report = self.aggregate((
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 1), hit_index=5),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 2), mfe=0.02, mae=-0.05, end_return=-0.01),
        ))

        self.assertEqual(report.resolved_count, 2)
        self.assertEqual(report.historical_hit_rate, 0.5)
        self.assertEqual(report.max_return_sample_count, 1)

    def test_report_case_properties_split_statuses_without_duplicate_storage(self):
        report = self.aggregate((
            self.case(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, 1), hit_index=1),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 2)),
            self.case(OutcomeEvaluationStatus.INCOMPLETE, signal_date=date(2025, 1, 3)),
            self.case(OutcomeEvaluationStatus.NOT_EVALUABLE, signal_date=date(2025, 1, 4)),
        ))

        self.assertEqual(len(report.hit_cases), 1)
        self.assertEqual(len(report.miss_cases), 1)
        self.assertEqual(len(report.incomplete_cases), 1)
        self.assertEqual(len(report.not_evaluable_cases), 1)

    def test_cases_are_sorted_oldest_to_newest(self):
        report = self.aggregate((
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 3)),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 1)),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 2)),
        ))

        self.assertEqual(
            [case.signal_event.signal_date for case in report.cases],
            [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)],
        )

    def test_stable_backtest_and_case_ids_do_not_include_generated_at(self):
        config = self.config(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
        event = self.event(signal_date=date(2024, 5, 1))
        outcome = self.outcome(OutcomeEvaluationStatus.MISS, signal_date=date(2024, 5, 1), outcome_id=config.outcome_definition.id)

        self.assertEqual(build_backtest_id("TEST", config), build_backtest_id("TEST", config))
        self.assertEqual(
            build_case_id("TEST", event, outcome),
            "TEST|test_signal_v1|2024-05-01|raw_high_breakout_60d_within_5d_v1",
        )

    def test_config_validation_rejects_ambiguous_cooldown(self):
        with self.assertRaises(BacktestConfigurationError):
            self.config(overlap_policy=OverlappingSignalPolicy.COOLDOWN)
        with self.assertRaises(BacktestConfigurationError):
            self.config(overlap_policy=OverlappingSignalPolicy.ALLOW_ALL, cooldown_bars=20)
        with self.assertRaises(BacktestConfigurationError):
            self.config(start_date=date(2025, 2, 1), end_date=date(2025, 1, 1))

    def test_symbol_mismatch_raises_data_error(self):
        prices = self.price_series((self.bar(date(2025, 1, 1)),), symbol="AAA")
        technical = self.technical_series((date(2025, 1, 1),), symbol="BBB")

        with self.assertRaises(BacktestDataError):
            run_historical_backtest(prices, technical, self.config())

    def test_missing_technical_snapshot_date_raises_data_error(self):
        prices = self.price_series((self.bar(date(2025, 1, 1)),))
        technical = self.technical_series((date(2025, 1, 2),))

        with self.assertRaises(BacktestDataError):
            run_historical_backtest(prices, technical, self.config())

    def test_run_allow_all_preserves_all_raw_signals(self):
        dates = tuple(date(2025, 1, 1) + timedelta(days=index) for index in range(8))
        prices = self.price_series(
            tuple(self.bar(trading_date, close=100.0, high=106.0) for trading_date in dates)
        )
        technical = self.technical_series(dates[:3])

        report = run_historical_backtest(prices, technical, self.config())

        self.assertEqual(report.raw_signal_count, 3)
        self.assertEqual(report.filtered_signal_count, 3)
        self.assertEqual(len(report.cases), 3)

    def test_run_cooldown_uses_existing_trading_bar_policy(self):
        dates = (
            date(2025, 1, 6),
            date(2025, 1, 7),
            date(2025, 1, 8),
            date(2025, 1, 13),
            date(2025, 1, 14),
            date(2025, 1, 15),
            date(2025, 1, 16),
            date(2025, 1, 17),
        )
        prices = self.price_series(tuple(self.bar(trading_date, high=106.0) for trading_date in dates))
        technical = self.technical_series(dates[:4])
        config = self.config(
            overlap_policy=OverlappingSignalPolicy.COOLDOWN,
            cooldown_bars=2,
        )

        report = run_historical_backtest(prices, technical, config)

        self.assertEqual(report.raw_signal_count, 4)
        self.assertEqual(report.filtered_signal_count, 2)
        self.assertEqual([event.signal_date for event in report.evaluated_events], [date(2025, 1, 6), date(2025, 1, 13)])

    def test_date_range_filters_signal_dates_only(self):
        dates = tuple(date(2023, 12, 29) + timedelta(days=index) for index in range(370))
        signal_dates = (date(2023, 12, 29), date(2024, 1, 2), date(2025, 1, 1))
        prices = self.price_series(tuple(self.bar(trading_date, high=99.0) for trading_date in dates))
        technical = self.technical_series(signal_dates)
        config = self.config(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))

        report = run_historical_backtest(prices, technical, config)

        self.assertEqual(report.raw_signal_count, 3)
        self.assertEqual(report.filtered_signal_count, 1)
        self.assertEqual(report.cases[0].signal_event.signal_date, date(2024, 1, 2))

    def test_backtest_end_date_does_not_truncate_future_outcome_window(self):
        signal_date = date(2024, 12, 20)
        future_dates = tuple(signal_date + timedelta(days=index) for index in range(1, 6))
        prices = self.price_series(
            (self.bar(signal_date, high=99.0),)
            + tuple(self.bar(trading_date, close=100.0, high=99.0) for trading_date in future_dates)
        )
        technical = self.technical_series((signal_date,))
        config = self.config(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))

        report = run_historical_backtest(prices, technical, config)

        self.assertEqual(report.cases[0].outcome.status, OutcomeEvaluationStatus.MISS)
        self.assertEqual(report.cases[0].outcome.available_future_bars, 5)

    def test_no_signal_live_shape_returns_empty_report(self):
        trading_date = date(2025, 1, 1)
        prices = self.price_series((self.bar(trading_date),))
        technical = self.technical_series((trading_date,), closes={trading_date: 80.0})

        report = run_historical_backtest(prices, technical, self.config())

        self.assertEqual(report.raw_signal_count, 0)
        self.assertEqual(report.filtered_signal_count, 0)
        self.assertEqual(report.cases, tuple())

    def test_case_window_helper_returns_pre_signal_and_future_bars_for_review(self):
        dates = tuple(date(2025, 1, 1) + timedelta(days=index) for index in range(10))
        prices = self.price_series(tuple(self.bar(trading_date) for trading_date in dates))

        window = get_backtest_case_price_window(
            prices,
            signal_date=date(2025, 1, 5),
            pre_bars=2,
            post_bars=3,
        )

        self.assertEqual(
            [bar.trading_date for bar in window],
            [date(2025, 1, 3), date(2025, 1, 4), date(2025, 1, 5), date(2025, 1, 6), date(2025, 1, 7), date(2025, 1, 8)],
        )

    def test_case_window_helper_allows_zero_pre_bars(self):
        dates = tuple(date(2025, 1, 1) + timedelta(days=index) for index in range(5))
        prices = self.price_series(tuple(self.bar(trading_date) for trading_date in dates))

        window = get_backtest_case_price_window(
            prices,
            signal_date=date(2025, 1, 3),
            pre_bars=0,
            post_bars=1,
        )

        self.assertEqual(
            [bar.trading_date for bar in window],
            [date(2025, 1, 3), date(2025, 1, 4)],
        )


if __name__ == "__main__":
    unittest.main()
