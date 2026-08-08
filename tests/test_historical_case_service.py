import sys
import unittest
from dataclasses import fields
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from backtest_service import BacktestConfig
from backtest_service import HistoricalBacktestCase
from backtest_service import aggregate_backtest_cases
from backtest_service import build_case_id
from historical_case_service import HistoricalCaseDataError
from historical_case_service import HistoricalCaseWindowConfig
from historical_case_service import build_case_price_window
from historical_case_service import build_historical_case_views
from models import EvaluatedSignalCondition
from models import HistoricalOutcomeResult
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeDefinition
from models import OutcomeEvaluationStatus
from models import OutcomeType
from models import OverlappingSignalPolicy
from models import SignalConditionOperator
from models import SignalDefinition
from models import SignalEvaluationStatus
from models import SignalEvent
from models import TechnicalIndicatorSnapshot
from models import TechnicalSignalCondition


FETCHED_AT = datetime(2026, 8, 8, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 8, 2, 0, tzinfo=UTC)


class HistoricalCaseServiceTestCase(unittest.TestCase):

    def bar(self, trading_date, close=100.0, *, high=None, adjusted_close=None, symbol="TEST"):
        return HistoricalPriceBar(
            symbol=symbol,
            trading_date=trading_date,
            open=close - 0.5,
            high=close + 1 if high is None else high,
            low=close - 1,
            close=close,
            adjusted_close=close if adjusted_close is None else adjusted_close,
            volume=1000,
        )

    def price_series(self, bars, symbol="TEST", currency="USD"):
        return HistoricalPriceSeries(
            symbol=symbol,
            currency=currency,
            bars=tuple(bars),
            fetched_at=FETCHED_AT,
        )

    def snapshot(self, trading_date, symbol="TEST", analysis_close=100.0):
        params = {field.name: None for field in fields(TechnicalIndicatorSnapshot)}
        params.update(
            symbol=symbol,
            trading_date=trading_date,
            analysis_close=analysis_close,
            sma_20=95.0,
            sma_60=90.0,
            sma_120=85.0,
            sma_200=80.0,
            rsi_14=60.0,
            macd=1.2,
            macd_signal=1.0,
            atr_14_pct=0.03,
            volume_ratio_20=1.5,
            distance_to_prior_60d_high=-0.02,
            return_20d=0.04,
            return_60d=0.12,
            prior_high_60d=110.0,
            prior_low_60d=80.0,
        )
        return TechnicalIndicatorSnapshot(**params)

    def signal_definition(self, signal_id="test_signal_v1"):
        return SignalDefinition(
            id=signal_id,
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

    def outcome_definition(self, outcome_id="test_outcome_v1"):
        return OutcomeDefinition(
            id=outcome_id,
            outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
            horizon_bars=20,
            reference_metric="prior_high_60d",
        )

    def config(self):
        return BacktestConfig(
            signal_definition=self.signal_definition(),
            outcome_definition=self.outcome_definition(),
            overlap_policy=OverlappingSignalPolicy.ALLOW_ALL,
        )

    def condition_detail(self):
        return EvaluatedSignalCondition(
            metric="analysis_close",
            actual_value=100.0,
            operator=SignalConditionOperator.GREATER_THAN,
            expected_value=95.0,
            secondary_metric="sma_20",
            secondary_actual_value=95.0,
            status=SignalEvaluationStatus.MATCH,
            matched=True,
        )

    def event(self, signal_date, *, symbol="TEST", signal_id="test_signal_v1", reference_high=110.0):
        return SignalEvent(
            symbol=symbol,
            signal_id=signal_id,
            signal_date=signal_date,
            signal_analysis_close=100.0,
            signal_raw_close=101.0,
            reference_high=reference_high,
            reference_low=80.0,
            evaluation_status=SignalEvaluationStatus.MATCH,
            feature_snapshot=self.snapshot(signal_date, symbol=symbol),
            evaluated_conditions=(self.condition_detail(),),
        )

    def outcome(
        self,
        status,
        *,
        signal_date,
        symbol="TEST",
        signal_id="test_signal_v1",
        outcome_id="test_outcome_v1",
        hit_date=None,
        hit_index=None,
        reference_high=110.0,
    ):
        return HistoricalOutcomeResult(
            symbol=symbol,
            signal_id=signal_id,
            signal_date=signal_date,
            outcome_definition_id=outcome_id,
            status=status,
            horizon_bars=20,
            available_future_bars=20 if status is not OutcomeEvaluationStatus.INCOMPLETE else 2,
            reference_high=reference_high,
            intraday_target_hit=status is OutcomeEvaluationStatus.HIT,
            intraday_target_hit_date=hit_date,
            intraday_target_hit_bar_index=hit_index,
            close_target_hit=False,
            close_target_hit_date=None,
            close_target_hit_bar_index=None,
            max_close_return=0.12 if status in {OutcomeEvaluationStatus.HIT, OutcomeEvaluationStatus.MISS} else None,
            max_close_return_date=date(2025, 1, 8) if status in {OutcomeEvaluationStatus.HIT, OutcomeEvaluationStatus.MISS} else None,
            max_adverse_return=-0.04 if status in {OutcomeEvaluationStatus.HIT, OutcomeEvaluationStatus.MISS} else None,
            max_adverse_return_date=date(2025, 1, 6) if status in {OutcomeEvaluationStatus.HIT, OutcomeEvaluationStatus.MISS} else None,
            end_of_window_return=0.05 if status in {OutcomeEvaluationStatus.HIT, OutcomeEvaluationStatus.MISS} else None,
        )

    def case(self, status, signal_date, **overrides):
        event = self.event(signal_date, reference_high=overrides.get("reference_high", 110.0))
        outcome = self.outcome(status, signal_date=signal_date, **overrides)
        return HistoricalBacktestCase(
            symbol=event.symbol,
            signal_event=event,
            outcome=outcome,
            case_id=build_case_id(event.symbol, event, outcome),
        )

    def report(self, cases):
        return aggregate_backtest_cases(
            tuple(cases),
            symbol="TEST",
            config=self.config(),
            generated_at=GENERATED_AT,
        )

    def test_window_config_rejects_negative_values(self):
        with self.assertRaises(HistoricalCaseDataError):
            HistoricalCaseWindowConfig(pre_signal_bars=-1)
        with self.assertRaises(HistoricalCaseDataError):
            HistoricalCaseWindowConfig(post_signal_bars=-1)

    def test_price_window_keeps_actual_bars_only(self):
        bars = [
            self.bar(date(2025, 1, 1)),
            self.bar(date(2025, 1, 3)),
            self.bar(date(2025, 1, 6)),
        ]
        window = build_case_price_window(self.price_series(bars), date(2025, 1, 3), 2, 2)

        self.assertEqual([bar.trading_date for bar in window], [date(2025, 1, 1), date(2025, 1, 3), date(2025, 1, 6)])

    def test_price_window_requires_signal_bar(self):
        series = self.price_series([self.bar(date(2025, 1, 1))])

        with self.assertRaises(HistoricalCaseDataError):
            build_case_price_window(series, date(2025, 1, 2), 1, 1)

    def test_relative_index_uses_trading_bars_not_calendar_days(self):
        bars = [
            self.bar(date(2025, 1, 2)),
            self.bar(date(2025, 1, 3)),
            self.bar(date(2025, 1, 6)),
            self.bar(date(2025, 1, 7)),
        ]
        report = self.report((self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 3)),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 2))[0]

        self.assertEqual(
            [(point.trading_date, point.relative_bar_index) for point in view.price_points],
            [(date(2025, 1, 2), -1), (date(2025, 1, 3), 0), (date(2025, 1, 6), 1), (date(2025, 1, 7), 2)],
        )

    def test_signal_point_and_after_before_labels_are_marked(self):
        bars = [self.bar(date(2025, 1, day)) for day in (1, 2, 3)]
        report = self.report((self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 2)),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 1))[0]

        self.assertEqual([point.before_or_after_signal for point in view.price_points], ["BEFORE_SIGNAL", "SIGNAL_DATE", "AFTER_SIGNAL"])
        self.assertTrue(view.price_points[1].is_signal_date)

    def test_analysis_close_uses_foundation_helper_contract(self):
        bars = [
            self.bar(date(2025, 1, 1), close=100.0, adjusted_close=90.0),
            self.bar(date(2025, 1, 2), close=110.0, adjusted_close=99.0),
        ]
        report = self.report((self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 2)),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 0))[0]

        self.assertEqual(view.price_points[-1].analysis_close, 99.0)

    def test_before_window_completeness_false_when_history_is_short(self):
        bars = [self.bar(date(2025, 1, day)) for day in (1, 2)]
        report = self.report((self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 2)),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(3, 0))[0]

        self.assertFalse(view.is_window_complete_before)

    def test_after_window_completeness_false_when_future_is_short(self):
        bars = [self.bar(date(2025, 1, day)) for day in (1, 2)]
        report = self.report((self.case(OutcomeEvaluationStatus.INCOMPLETE, date(2025, 1, 2)),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 3))[0]

        self.assertFalse(view.is_window_complete_after)

    def test_complete_window_flags_true_when_enough_bars_exist(self):
        bars = [self.bar(date(2025, 1, day)) for day in (1, 2, 3, 4, 5)]
        report = self.report((self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 3)),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(2, 2))[0]

        self.assertTrue(view.is_window_complete_before)
        self.assertTrue(view.is_window_complete_after)

    def test_hit_marker_uses_first_target_hit_date(self):
        bars = [self.bar(date(2025, 1, day), high=120.0 if day == 4 else 105.0) for day in (1, 2, 3, 4, 5)]
        report = self.report((self.case(OutcomeEvaluationStatus.HIT, date(2025, 1, 2), hit_date=date(2025, 1, 4), hit_index=2),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 3))[0]

        self.assertEqual(view.target_hit_date, date(2025, 1, 4))
        self.assertEqual(view.target_hit_bar_index, 2)
        self.assertTrue([point for point in view.price_points if point.trading_date == date(2025, 1, 4)][0].is_target_hit_date)

    def test_miss_case_has_no_target_hit_marker(self):
        bars = [self.bar(date(2025, 1, day)) for day in (1, 2, 3)]
        report = self.report((self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 2)),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 1))[0]

        self.assertIsNone(view.target_hit_date)
        self.assertFalse(any(point.is_target_hit_date for point in view.price_points))

    def test_reference_high_is_frozen_from_signal_event_not_future_bars(self):
        bars = [
            self.bar(date(2025, 1, 1), high=100.0),
            self.bar(date(2025, 1, 2), high=101.0),
            self.bar(date(2025, 1, 3), high=999.0),
        ]
        report = self.report((self.case(OutcomeEvaluationStatus.HIT, date(2025, 1, 2), reference_high=110.0, hit_date=date(2025, 1, 3), hit_index=1),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 1))[0]

        self.assertEqual(view.reference_high, 110.0)

    def test_condition_details_are_copied_without_reevaluation(self):
        bars = [self.bar(date(2025, 1, day)) for day in (1, 2)]
        report = self.report((self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 2)),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 0))[0]

        self.assertEqual(view.condition_details[0].metric, "analysis_close")
        self.assertEqual(view.condition_details[0].operator, ">")
        self.assertTrue(view.condition_details[0].matched)

    def test_snapshot_metrics_include_required_summary_fields(self):
        bars = [self.bar(date(2025, 1, day)) for day in (1, 2)]
        report = self.report((self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 2)),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 0))[0]
        summary = dict(view.technical_snapshot_summary)

        self.assertEqual(summary["sma_20"], 95.0)
        self.assertEqual(summary["rsi_14"], 60.0)
        self.assertEqual(summary["return_60d"], 0.12)

    def test_view_preserves_raw_outcome_metrics(self):
        bars = [self.bar(date(2025, 1, day)) for day in (1, 2)]
        report = self.report((self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 2)),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 0))[0]

        self.assertEqual(view.max_close_return, 0.12)
        self.assertEqual(view.max_adverse_return, -0.04)
        self.assertEqual(view.end_of_window_return, 0.05)

    def test_views_are_ordered_oldest_to_newest(self):
        bars = [self.bar(date(2025, 1, day)) for day in (1, 2, 3, 4)]
        report = self.report((
            self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 3)),
            self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 2)),
        ))
        views = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 1))

        self.assertEqual([view.signal_date for view in views], [date(2025, 1, 2), date(2025, 1, 3)])

    def test_symbol_mismatch_raises(self):
        bars = [self.bar(date(2025, 1, 1), symbol="OTHER")]
        report = self.report(tuple())

        with self.assertRaises(HistoricalCaseDataError):
            build_historical_case_views(self.price_series(bars, symbol="OTHER"), report)

    def test_case_signal_id_mismatch_raises(self):
        bars = [self.bar(date(2025, 1, 1))]
        bad_case = self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 1))
        bad_case = HistoricalBacktestCase(
            symbol=bad_case.symbol,
            signal_event=self.event(date(2025, 1, 1), signal_id="other_signal"),
            outcome=bad_case.outcome,
            case_id=bad_case.case_id,
        )

        with self.assertRaises(HistoricalCaseDataError):
            build_historical_case_views(self.price_series(bars), self.report((bad_case,)))

    def test_case_outcome_id_mismatch_raises(self):
        bars = [self.bar(date(2025, 1, 1))]
        bad_case = self.case(OutcomeEvaluationStatus.MISS, date(2025, 1, 1), outcome_id="other_outcome")

        with self.assertRaises(HistoricalCaseDataError):
            build_historical_case_views(self.price_series(bars), self.report((bad_case,)))

    def test_event_outcome_identity_mismatch_raises(self):
        bars = [self.bar(date(2025, 1, 1)), self.bar(date(2025, 1, 2))]
        event = self.event(date(2025, 1, 1))
        outcome = self.outcome(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 2))
        bad_case = HistoricalBacktestCase(
            symbol=event.symbol,
            signal_event=event,
            outcome=outcome,
            case_id=build_case_id(event.symbol, event, outcome),
        )

        with self.assertRaises(HistoricalCaseDataError):
            build_historical_case_views(self.price_series(bars), self.report((bad_case,)))

    def test_not_evaluable_case_still_builds_window(self):
        bars = [self.bar(date(2025, 1, day)) for day in (1, 2, 3)]
        report = self.report((self.case(OutcomeEvaluationStatus.NOT_EVALUABLE, date(2025, 1, 2)),))
        view = build_historical_case_views(self.price_series(bars), report, HistoricalCaseWindowConfig(1, 1))[0]

        self.assertEqual(view.outcome_status, OutcomeEvaluationStatus.NOT_EVALUABLE)
        self.assertEqual(len(view.price_points), 3)

    def test_zero_window_returns_only_signal_bar(self):
        bars = [self.bar(date(2025, 1, day)) for day in (1, 2, 3)]
        window = build_case_price_window(self.price_series(bars), date(2025, 1, 2), 0, 0)

        self.assertEqual([bar.trading_date for bar in window], [date(2025, 1, 2)])


if __name__ == "__main__":
    unittest.main()
