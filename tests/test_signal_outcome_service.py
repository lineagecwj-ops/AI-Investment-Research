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

from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeDefinition
from models import OutcomeEvaluationStatus
from models import OutcomeType
from models import SignalConditionOperator
from models import SignalDefinition
from models import SignalEvaluationStatus
from models import SignalEvent
from models import TechnicalIndicatorSeries
from models import TechnicalIndicatorSnapshot
from models import TechnicalSignalCondition
from signal_outcome_service import CLOSE_RETURN_5PCT_WITHIN_20D_V1
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import SignalOutcomeError
from signal_outcome_service import apply_signal_cooldown
from signal_outcome_service import audit_signal_evaluation
from signal_outcome_service import build_signal_event
from signal_outcome_service import evaluate_historical_outcome
from signal_outcome_service import evaluate_signal_conditions
from signal_outcome_service import evaluate_signal_events
from signal_outcome_service import find_signal_events
from signal_outcome_service import get_future_bars_after
from signal_outcome_service import is_outcome_complete


FETCHED_AT = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


class SignalOutcomeServiceTestCase(unittest.TestCase):

    def snapshot(self, trading_date=date(2025, 1, 10), **overrides):
        params = {
            field.name: None
            for field in fields(TechnicalIndicatorSnapshot)
        }
        params.update(
            symbol="TEST",
            trading_date=trading_date,
            analysis_close=105.0,
            sma_20=100.0,
            sma_60=90.0,
            volume_ratio_20=1.5,
            rsi_14=60.0,
            distance_to_prior_60d_high=-0.02,
            prior_high_60d=110.0,
            prior_low_60d=80.0,
            close_above_sma20=True,
            sma20_above_sma60=True,
        )
        params.update(overrides)
        return TechnicalIndicatorSnapshot(**params)

    def signal(self, *conditions, required=None, signal_id="test_signal_v1"):
        if required is None:
            required = tuple(condition.metric for condition in conditions)
        return SignalDefinition(
            id=signal_id,
            name="Test Signal",
            conditions=tuple(conditions),
            minimum_required_features=tuple(required),
            description="Test-only deterministic condition.",
        )

    def condition(self, metric, operator, value=None, secondary_metric=None):
        return TechnicalSignalCondition(
            metric=metric,
            operator=operator,
            value=value,
            secondary_metric=secondary_metric,
        )

    def bar(
        self,
        trading_date,
        close,
        *,
        high=None,
        low=None,
        raw_close=None,
        adjusted_close=None,
    ):
        raw_close = close if raw_close is None else raw_close
        return HistoricalPriceBar(
            symbol="TEST",
            trading_date=trading_date,
            open=raw_close,
            high=raw_close + 1 if high is None else high,
            low=raw_close - 1 if low is None else low,
            close=raw_close,
            adjusted_close=close if adjusted_close is None else adjusted_close,
            volume=1000,
        )

    def price_series(self, bars):
        return HistoricalPriceSeries(
            symbol="TEST",
            currency="USD",
            bars=tuple(bars),
            fetched_at=FETCHED_AT,
        )

    def event(self, signal_date=date(2025, 1, 10), reference_high=100.0, analysis_close=100.0):
        snapshot = self.snapshot(
            trading_date=signal_date,
            analysis_close=analysis_close,
            prior_high_60d=reference_high,
        )
        signal_definition = self.signal(
            self.condition("analysis_close", SignalConditionOperator.GREATER_THAN, 90.0)
        )
        match = evaluate_signal_conditions(snapshot, signal_definition)
        return build_signal_event(match, signal_raw_close=101.0)

    def test_all_conditions_match(self):
        signal_definition = self.signal(
            self.condition("analysis_close", SignalConditionOperator.GREATER_THAN, 100.0),
            self.condition("volume_ratio_20", SignalConditionOperator.GREATER_THAN_OR_EQUAL, 1.2),
        )

        match = evaluate_signal_conditions(self.snapshot(), signal_definition)

        self.assertEqual(match.status, SignalEvaluationStatus.MATCH)
        self.assertTrue(match.matched)
        self.assertTrue(all(condition.matched for condition in match.evaluated_conditions))

    def test_one_condition_failure_is_no_match(self):
        signal_definition = self.signal(
            self.condition("analysis_close", SignalConditionOperator.GREATER_THAN, 120.0)
        )

        match = evaluate_signal_conditions(self.snapshot(), signal_definition)

        self.assertEqual(match.status, SignalEvaluationStatus.NO_MATCH)
        self.assertFalse(match.matched)

    def test_missing_required_feature_is_not_evaluable(self):
        signal_definition = self.signal(
            self.condition("sma_200", SignalConditionOperator.GREATER_THAN, 100.0),
            required=("sma_200",),
        )

        match = evaluate_signal_conditions(self.snapshot(sma_200=None), signal_definition)

        self.assertEqual(match.status, SignalEvaluationStatus.NOT_EVALUABLE)
        self.assertFalse(match.matched)

    def test_unknown_metric_is_not_evaluable(self):
        signal_definition = self.signal(
            self.condition("not_a_metric", SignalConditionOperator.GREATER_THAN, 1.0)
        )

        match = evaluate_signal_conditions(self.snapshot(), signal_definition)

        self.assertEqual(match.status, SignalEvaluationStatus.NOT_EVALUABLE)

    def test_metric_vs_metric_comparison(self):
        signal_definition = self.signal(
            self.condition(
                "sma_20",
                SignalConditionOperator.GREATER_THAN,
                secondary_metric="sma_60",
            ),
            required=("sma_20", "sma_60"),
        )

        match = evaluate_signal_conditions(self.snapshot(), signal_definition)

        self.assertEqual(match.status, SignalEvaluationStatus.MATCH)
        self.assertEqual(match.evaluated_conditions[0].secondary_actual_value, 90.0)

    def test_between_is_inclusive(self):
        signal_definition = self.signal(
            self.condition("rsi_14", SignalConditionOperator.BETWEEN, (50.0, 70.0))
        )

        lower = evaluate_signal_conditions(self.snapshot(rsi_14=50.0), signal_definition)
        upper = evaluate_signal_conditions(self.snapshot(rsi_14=70.0), signal_definition)

        self.assertEqual(lower.status, SignalEvaluationStatus.MATCH)
        self.assertEqual(upper.status, SignalEvaluationStatus.MATCH)

    def test_boolean_equality_condition(self):
        signal_definition = self.signal(
            self.condition("close_above_sma20", SignalConditionOperator.EQUAL, True)
        )

        match = evaluate_signal_conditions(self.snapshot(), signal_definition)

        self.assertEqual(match.status, SignalEvaluationStatus.MATCH)

    def test_bool_cannot_be_ordered_as_number(self):
        signal_definition = self.signal(
            self.condition("close_above_sma20", SignalConditionOperator.GREATER_THAN, 0.0)
        )

        with self.assertRaises(SignalOutcomeError):
            evaluate_signal_conditions(self.snapshot(), signal_definition)

    def test_non_finite_value_is_not_evaluable(self):
        signal_definition = self.signal(
            self.condition("rsi_14", SignalConditionOperator.LESS_THAN, 70.0)
        )

        match = evaluate_signal_conditions(self.snapshot(rsi_14=float("nan")), signal_definition)

        self.assertEqual(match.status, SignalEvaluationStatus.NOT_EVALUABLE)

    def test_unsupported_between_shape_raises(self):
        signal_definition = self.signal(
            self.condition("rsi_14", SignalConditionOperator.BETWEEN, 60.0)
        )

        with self.assertRaises(SignalOutcomeError):
            evaluate_signal_conditions(self.snapshot(), signal_definition)

    def test_evaluated_condition_trace_contains_actual_expected_and_result(self):
        signal_definition = self.signal(
            self.condition("volume_ratio_20", SignalConditionOperator.GREATER_THAN_OR_EQUAL, 1.2)
        )

        evaluated = evaluate_signal_conditions(self.snapshot(), signal_definition).evaluated_conditions[0]

        self.assertEqual(evaluated.metric, "volume_ratio_20")
        self.assertEqual(evaluated.actual_value, 1.5)
        self.assertEqual(evaluated.expected_value, 1.2)
        self.assertTrue(evaluated.matched)

    def test_signal_event_freezes_reference_and_snapshot(self):
        match = evaluate_signal_conditions(
            self.snapshot(prior_high_60d=123.0),
            self.signal(self.condition("analysis_close", SignalConditionOperator.GREATER_THAN, 100.0)),
        )

        event = build_signal_event(match, signal_raw_close=106.0)

        self.assertEqual(event.reference_high, 123.0)
        self.assertEqual(event.signal_analysis_close, 105.0)
        self.assertEqual(event.signal_raw_close, 106.0)
        self.assertIs(event.feature_snapshot, match.feature_snapshot)

    def test_non_match_cannot_become_signal_event(self):
        match = evaluate_signal_conditions(
            self.snapshot(),
            self.signal(self.condition("analysis_close", SignalConditionOperator.GREATER_THAN, 999.0)),
        )

        with self.assertRaises(SignalOutcomeError):
            build_signal_event(match)

    def test_find_signal_events_returns_only_matches_and_deduplicates_same_day(self):
        snapshots = (
            self.snapshot(date(2025, 1, 10)),
            self.snapshot(date(2025, 1, 10)),
            self.snapshot(date(2025, 1, 11), analysis_close=50.0),
        )
        technical_series = TechnicalIndicatorSeries(
            symbol="TEST",
            snapshots=snapshots,
            generated_at=FETCHED_AT,
            source_price_fetched_at=FETCHED_AT,
        )
        signal_definition = self.signal(
            self.condition("analysis_close", SignalConditionOperator.GREATER_THAN, 100.0)
        )

        events = find_signal_events(technical_series, signal_definition)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].signal_date, date(2025, 1, 10))

    def test_audit_counts_match_no_match_and_not_evaluable(self):
        technical_series = TechnicalIndicatorSeries(
            symbol="TEST",
            snapshots=(
                self.snapshot(date(2025, 1, 10)),
                self.snapshot(date(2025, 1, 11), analysis_close=50.0),
                self.snapshot(date(2025, 1, 12), sma_20=None),
            ),
            generated_at=FETCHED_AT,
            source_price_fetched_at=FETCHED_AT,
        )
        signal_definition = self.signal(
            self.condition(
                "analysis_close",
                SignalConditionOperator.GREATER_THAN,
                secondary_metric="sma_20",
            ),
            required=("analysis_close", "sma_20"),
        )

        audit = audit_signal_evaluation(technical_series, signal_definition)

        self.assertEqual(audit.evaluated_snapshots, 3)
        self.assertEqual(audit.matched, 1)
        self.assertEqual(audit.not_matched, 1)
        self.assertEqual(audit.not_evaluable, 1)

    def test_get_future_bars_after_excludes_signal_date_and_weekend(self):
        series = self.price_series(
            (
                self.bar(date(2025, 1, 3), 100.0),
                self.bar(date(2025, 1, 6), 101.0),
                self.bar(date(2025, 1, 7), 102.0),
            )
        )

        future = get_future_bars_after(series, date(2025, 1, 3), 2)

        self.assertEqual([bar.trading_date for bar in future], [date(2025, 1, 6), date(2025, 1, 7)])

    def test_get_future_bars_after_limits_to_count(self):
        series = self.price_series(
            tuple(self.bar(date(2025, 1, 10) + timedelta(days=index), 100.0 + index) for index in range(5))
        )

        future = get_future_bars_after(series, date(2025, 1, 10), 2)

        self.assertEqual(len(future), 2)

    def test_raw_high_breakout_uses_strict_greater_than_and_first_hit(self):
        series = self.price_series(
            (
                self.bar(date(2025, 1, 10), 100.0, high=100.0),
                self.bar(date(2025, 1, 13), 99.0, high=99.0),
                self.bar(date(2025, 1, 14), 100.0, high=100.0),
                self.bar(date(2025, 1, 15), 100.01, high=100.01),
            )
        )
        outcome = OutcomeDefinition(
            id="raw_high_breakout_60d_within_5d_v1",
            outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
            horizon_bars=5,
            reference_metric="prior_high_60d",
        )

        result = evaluate_historical_outcome(self.event(reference_high=100.0), series, outcome)

        self.assertEqual(result.status, OutcomeEvaluationStatus.HIT)
        self.assertTrue(result.intraday_target_hit)
        self.assertEqual(result.intraday_target_hit_bar_index, 3)
        self.assertEqual(result.intraday_target_hit_date, date(2025, 1, 15))

    def test_equal_high_is_not_breakout(self):
        series = self.price_series(
            (
                self.bar(date(2025, 1, 10), 100.0, high=100.0),
                self.bar(date(2025, 1, 13), 100.0, high=100.0),
                self.bar(date(2025, 1, 14), 100.0, high=100.0),
                self.bar(date(2025, 1, 15), 100.0, high=100.0),
                self.bar(date(2025, 1, 16), 100.0, high=100.0),
                self.bar(date(2025, 1, 17), 100.0, high=100.0),
            )
        )
        outcome = OutcomeDefinition(
            id="raw_high_breakout_60d_within_5d_v1",
            outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
            horizon_bars=5,
            reference_metric="prior_high_60d",
        )

        result = evaluate_historical_outcome(self.event(reference_high=100.0), series, outcome)

        self.assertEqual(result.status, OutcomeEvaluationStatus.MISS)
        self.assertFalse(result.intraday_target_hit)

    def test_horizon_does_not_peek_at_bar_after_window(self):
        bars = [self.bar(date(2025, 1, 10), 100.0, high=100.0)]
        bars.extend(
            self.bar(date(2025, 1, 10) + timedelta(days=index), 99.0, high=99.0)
            for index in range(1, 21)
        )
        bars.append(self.bar(date(2025, 1, 31), 101.0, high=101.0))
        outcome = OutcomeDefinition(
            id="raw_high_breakout_60d_within_20d_v1",
            outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
            horizon_bars=20,
            reference_metric="prior_high_60d",
        )

        result = evaluate_historical_outcome(self.event(reference_high=100.0), self.price_series(bars), outcome)

        self.assertEqual(result.status, OutcomeEvaluationStatus.MISS)
        self.assertFalse(result.intraday_target_hit)

    def test_no_future_bars_is_incomplete(self):
        series = self.price_series((self.bar(date(2025, 1, 10), 100.0),))

        result = evaluate_historical_outcome(self.event(), series, RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1)

        self.assertEqual(result.status, OutcomeEvaluationStatus.INCOMPLETE)
        self.assertEqual(result.available_future_bars, 0)

    def test_early_hit_is_resolved_even_when_horizon_is_incomplete(self):
        series = self.price_series(
            (
                self.bar(date(2025, 1, 10), 100.0, high=100.0),
                self.bar(date(2025, 1, 13), 101.0, high=101.0),
            )
        )

        result = evaluate_historical_outcome(self.event(reference_high=100.0), series, RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1)

        self.assertEqual(result.status, OutcomeEvaluationStatus.HIT)
        self.assertEqual(result.available_future_bars, 1)
        self.assertIsNone(result.max_close_return)
        self.assertIsNone(result.end_of_window_return)

    def test_incomplete_without_hit_keeps_window_metrics_empty(self):
        series = self.price_series(
            (
                self.bar(date(2025, 1, 10), 100.0, high=100.0),
                self.bar(date(2025, 1, 13), 99.0, high=99.0),
            )
        )

        result = evaluate_historical_outcome(self.event(reference_high=100.0), series, RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1)

        self.assertEqual(result.status, OutcomeEvaluationStatus.INCOMPLETE)
        self.assertIsNone(result.max_close_return)
        self.assertIsNone(result.max_adverse_return)
        self.assertIsNone(result.end_of_window_return)

    def test_complete_window_calculates_mfe_mae_and_end_return(self):
        bars = [self.bar(date(2025, 1, 10), 100.0, high=100.0)]
        closes = [101.0, 98.0, 103.0, 103.0, 99.0]
        bars.extend(
            self.bar(date(2025, 1, 13) + timedelta(days=index), close, high=99.0)
            for index, close in enumerate(closes)
        )
        outcome = OutcomeDefinition(
            id="raw_high_breakout_60d_within_5d_v1",
            outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
            horizon_bars=5,
            reference_metric="prior_high_60d",
        )

        result = evaluate_historical_outcome(self.event(reference_high=100.0), self.price_series(bars), outcome)

        self.assertEqual(result.status, OutcomeEvaluationStatus.MISS)
        self.assertAlmostEqual(result.max_close_return, 0.03)
        self.assertEqual(result.max_close_return_date, date(2025, 1, 15))
        self.assertAlmostEqual(result.max_adverse_return, -0.02)
        self.assertEqual(result.max_adverse_return_date, date(2025, 1, 14))
        self.assertAlmostEqual(result.end_of_window_return, -0.01)

    def test_close_return_target_uses_analysis_close_basis_and_greater_equal(self):
        series = self.price_series(
            (
                self.bar(date(2025, 1, 10), 100.0, high=1000.0, raw_close=1000.0, adjusted_close=100.0),
                self.bar(date(2025, 1, 13), 104.0, high=2000.0, raw_close=2000.0, adjusted_close=104.0),
                self.bar(date(2025, 1, 14), 105.0, high=3000.0, raw_close=3000.0, adjusted_close=105.0),
            )
        )
        event = self.event(reference_high=5000.0, analysis_close=100.0)

        result = evaluate_historical_outcome(event, series, CLOSE_RETURN_5PCT_WITHIN_20D_V1)

        self.assertEqual(result.status, OutcomeEvaluationStatus.HIT)
        self.assertTrue(result.close_target_hit)
        self.assertEqual(result.close_target_hit_bar_index, 2)
        self.assertFalse(result.intraday_target_hit)

    def test_missing_reference_high_is_not_evaluable_for_raw_breakout(self):
        event = self.event(reference_high=None)
        series = self.price_series((self.bar(date(2025, 1, 13), 101.0, high=101.0),))

        result = evaluate_historical_outcome(event, series, RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1)

        self.assertEqual(result.status, OutcomeEvaluationStatus.NOT_EVALUABLE)

    def test_outcome_complete_helper_excludes_incomplete_and_not_evaluable(self):
        complete = self.outcome_stub(OutcomeEvaluationStatus.HIT)
        miss = self.outcome_stub(OutcomeEvaluationStatus.MISS)
        incomplete = self.outcome_stub(OutcomeEvaluationStatus.INCOMPLETE)
        not_evaluable = self.outcome_stub(OutcomeEvaluationStatus.NOT_EVALUABLE)

        self.assertTrue(is_outcome_complete(complete))
        self.assertTrue(is_outcome_complete(miss))
        self.assertFalse(is_outcome_complete(incomplete))
        self.assertFalse(is_outcome_complete(not_evaluable))

    def outcome_stub(self, status):
        result = evaluate_historical_outcome(
            self.event(reference_high=100.0),
            self.price_series(
                (
                    self.bar(date(2025, 1, 10), 100.0, high=100.0),
                    self.bar(date(2025, 1, 13), 101.0, high=101.0),
                )
            ),
            RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
        )
        return result.__class__(
            **{
                field.name: (status if field.name == "status" else getattr(result, field.name))
                for field in fields(result)
            }
        )

    def test_batch_evaluator_returns_one_result_per_event_without_aggregation(self):
        events = (
            self.event(signal_date=date(2025, 1, 10), reference_high=100.0),
            self.event(signal_date=date(2025, 1, 13), reference_high=105.0),
        )
        series = self.price_series(
            (
                self.bar(date(2025, 1, 10), 100.0, high=100.0),
                self.bar(date(2025, 1, 13), 101.0, high=101.0),
                self.bar(date(2025, 1, 14), 106.0, high=106.0),
            )
        )

        results = evaluate_signal_events(events, series, RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1)

        self.assertEqual(len(results), 2)
        self.assertFalse(hasattr(results, "hit_rate"))

    def test_signal_cooldown_uses_trading_bar_distance(self):
        events = (
            self.event(signal_date=date(2025, 1, 1)),
            self.event(signal_date=date(2025, 1, 2)),
            self.event(signal_date=date(2025, 1, 5)),
            self.event(signal_date=date(2025, 1, 10)),
        )
        calendar = (
            date(2025, 1, 1),
            date(2025, 1, 2),
            date(2025, 1, 3),
            date(2025, 1, 5),
            date(2025, 1, 6),
            date(2025, 1, 7),
            date(2025, 1, 8),
            date(2025, 1, 9),
            date(2025, 1, 10),
        )

        kept = apply_signal_cooldown(events, calendar, cooldown_bars=3)

        self.assertEqual([event.signal_date for event in kept], [date(2025, 1, 1), date(2025, 1, 10)])

    def test_signal_cooldown_does_not_mutate_raw_events(self):
        events = (
            self.event(signal_date=date(2025, 1, 1)),
            self.event(signal_date=date(2025, 1, 2)),
        )
        kept = apply_signal_cooldown(events, (date(2025, 1, 1), date(2025, 1, 2)), cooldown_bars=3)

        self.assertEqual(len(events), 2)
        self.assertEqual(len(kept), 1)

    def test_signal_cooldown_keeps_separate_signal_ids_independent(self):
        event_a = self.event(signal_date=date(2025, 1, 1))
        event_b = SignalEvent(
            **{
                field.name: ("other_signal_v1" if field.name == "signal_id" else getattr(event_a, field.name))
                for field in fields(SignalEvent)
            }
        )

        kept = apply_signal_cooldown(
            (event_a, event_b),
            (date(2025, 1, 1),),
            cooldown_bars=3,
        )

        self.assertEqual(len(kept), 2)

    def test_sample_signal_definition_has_stable_neutral_id(self):
        self.assertEqual(TECHNICAL_EXAMPLE_SIGNAL_V1.id, "technical_example_v1")
        self.assertNotIn("buy", TECHNICAL_EXAMPLE_SIGNAL_V1.name.lower())
        self.assertNotIn("probability", TECHNICAL_EXAMPLE_SIGNAL_V1.description.lower())

    def test_sample_outcome_definitions_have_stable_ids(self):
        self.assertEqual(RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id, "raw_high_breakout_60d_within_20d_v1")
        self.assertEqual(CLOSE_RETURN_5PCT_WITHIN_20D_V1.id, "close_return_5pct_within_20d_v1")

    def test_signal_evaluation_does_not_change_when_future_price_data_is_appended(self):
        signal_definition = self.signal(
            self.condition("analysis_close", SignalConditionOperator.GREATER_THAN, 100.0)
        )
        before = evaluate_signal_conditions(self.snapshot(), signal_definition)
        series_with_future_extreme = self.price_series(
            (
                self.bar(date(2025, 1, 10), 105.0, high=106.0),
                self.bar(date(2025, 1, 13), 9999.0, high=9999.0),
            )
        )

        after = evaluate_signal_conditions(self.snapshot(), signal_definition)

        self.assertEqual(before, after)
        self.assertEqual(series_with_future_extreme.bars[-1].high, 9999.0)

    def test_same_signal_event_can_have_different_future_outcome(self):
        event = self.event(reference_high=100.0)
        miss_series = self.price_series(
            (
                self.bar(date(2025, 1, 10), 100.0, high=100.0),
                self.bar(date(2025, 1, 13), 99.0, high=99.0),
                self.bar(date(2025, 1, 14), 99.0, high=99.0),
                self.bar(date(2025, 1, 15), 99.0, high=99.0),
                self.bar(date(2025, 1, 16), 99.0, high=99.0),
                self.bar(date(2025, 1, 17), 99.0, high=99.0),
            )
        )
        hit_series = self.price_series(
            (
                self.bar(date(2025, 1, 10), 100.0, high=100.0),
                self.bar(date(2025, 1, 13), 101.0, high=101.0),
            )
        )
        outcome = OutcomeDefinition(
            id="raw_high_breakout_60d_within_5d_v1",
            outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
            horizon_bars=5,
            reference_metric="prior_high_60d",
        )

        miss = evaluate_historical_outcome(event, miss_series, outcome)
        hit = evaluate_historical_outcome(event, hit_series, outcome)

        self.assertEqual(miss.status, OutcomeEvaluationStatus.MISS)
        self.assertEqual(hit.status, OutcomeEvaluationStatus.HIT)
        self.assertEqual(event.reference_high, 100.0)

    def test_invalid_horizon_raises(self):
        outcome = OutcomeDefinition(
            id="bad_horizon_v1",
            outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
            horizon_bars=7,
            reference_metric="prior_high_60d",
        )

        with self.assertRaises(SignalOutcomeError):
            evaluate_historical_outcome(self.event(), self.price_series(tuple()), outcome)

    def test_domain_models_are_frozen(self):
        event = self.event()

        with self.assertRaises(Exception):
            event.signal_analysis_close = 200.0


if __name__ == "__main__":
    unittest.main()
