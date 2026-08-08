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

from backtest_service import HistoricalBacktestCase
from backtest_service import build_case_id
from historical_replay_service import HistoricalReplayConfig
from historical_replay_service import HistoricalReplayService
from historical_replay_service import are_return_metrics_known_as_of
from historical_replay_service import build_historical_replay_candidate
from historical_replay_service import build_point_in_time_backtest_summary
from historical_replay_service import full_horizon_end_date
from historical_replay_service import is_outcome_known_as_of
from historical_replay_service import rank_historical_replay_candidates
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
from models import TechnicalIndicatorSeries
from models import TechnicalIndicatorSnapshot
from models import TechnicalSignalCondition
from signal_outcome_service import evaluate_signal_conditions


FETCHED_AT = datetime(2026, 8, 8, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 8, 2, 0, tzinfo=UTC)


class RecordingBacktestRunner:

    def __init__(self, reports):
        self.reports = reports
        self.calls = []

    def __call__(self, price_series, technical_series, config):
        self.calls.append((price_series, technical_series, config))
        return self.reports[price_series.symbol]


class ReportStub:

    def __init__(self, symbol, cases, raw_events=tuple(), evaluated_events=tuple()):
        self.symbol = symbol
        self.cases = tuple(cases)
        self.raw_events = tuple(raw_events)
        self.evaluated_events = tuple(evaluated_events)


class HistoricalReplayServiceTestCase(unittest.TestCase):

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
                TechnicalSignalCondition(
                    metric="volume_ratio_20",
                    operator=SignalConditionOperator.GREATER_THAN_OR_EQUAL,
                    value=1.2,
                ),
            ),
            minimum_required_features=("analysis_close", "sma_20", "volume_ratio_20"),
            description="Test replay signal.",
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
            "replay_date": date(2024, 6, 30),
            "signal_definition": self.signal_definition(),
            "outcome_definition": self.outcome_definition(),
            "overlap_policy": OverlappingSignalPolicy.ALLOW_ALL,
            "cooldown_bars": None,
            "historical_start_date": date(2018, 1, 1),
            "preferred_resolved_samples": 5,
        }
        values.update(overrides)
        return HistoricalReplayConfig(**values)

    def snapshot(self, trading_date, symbol="TEST", *, match=True, insufficient=False):
        params = {field.name: None for field in fields(TechnicalIndicatorSnapshot)}
        params.update(
            symbol=symbol,
            trading_date=trading_date,
            analysis_close=110.0 if match else 90.0,
            sma_20=100.0,
            sma_60=90.0,
            volume_ratio_20=1.5,
            rsi_14=60.0,
            distance_to_prior_60d_high=-0.02,
            prior_high_60d=115.0,
            prior_low_60d=80.0,
        )
        if insufficient:
            params["sma_20"] = None
        return TechnicalIndicatorSnapshot(**params)

    def price_series(self, symbol="TEST", *, start=date(2024, 1, 1), days=40, stale=False):
        bars = []
        current = start
        while len(bars) < days:
            if current.weekday() < 5:
                index = len(bars)
                bars.append(
                    HistoricalPriceBar(
                        symbol=symbol,
                        trading_date=current,
                        open=100.0 + index,
                        high=116.0 if index % 7 == 0 else 104.0 + index,
                        low=98.0 + index,
                        close=101.0 + index,
                        adjusted_close=101.0 + index,
                        volume=1000 + index,
                    )
                )
            current += timedelta(days=1)
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="USD",
            bars=tuple(bars),
            fetched_at=FETCHED_AT,
            is_stale=stale,
        )

    def technical_series_from_prices(self, price_series, *, match=True, insufficient=False):
        return TechnicalIndicatorSeries(
            symbol=price_series.symbol,
            snapshots=tuple(
                self.snapshot(
                    bar.trading_date,
                    symbol=price_series.symbol,
                    match=match,
                    insufficient=insufficient,
                )
                for bar in price_series.bars
            ),
            generated_at=GENERATED_AT,
            source_price_fetched_at=price_series.fetched_at,
            source_price_is_stale=price_series.is_stale,
        )

    def condition(self):
        return EvaluatedSignalCondition(
            metric="analysis_close",
            actual_value=110.0,
            operator=SignalConditionOperator.GREATER_THAN,
            expected_value=None,
            secondary_metric="sma_20",
            secondary_actual_value=100.0,
            status=SignalEvaluationStatus.MATCH,
            matched=True,
        )

    def event(self, signal_date, symbol="TEST"):
        snapshot = self.snapshot(signal_date, symbol=symbol)
        return SignalEvent(
            symbol=symbol,
            signal_id=self.signal_definition().id,
            signal_date=signal_date,
            signal_analysis_close=110.0,
            signal_raw_close=110.0,
            reference_high=115.0,
            reference_low=80.0,
            evaluation_status=SignalEvaluationStatus.MATCH,
            feature_snapshot=snapshot,
            evaluated_conditions=(self.condition(),),
        )

    def outcome(
        self,
        status,
        *,
        signal_date,
        symbol="TEST",
        horizon=5,
        hit_date=None,
        hit_index=None,
        mfe=0.10,
        mae=-0.04,
        end_return=0.02,
        available=5,
    ):
        is_hit = status is OutcomeEvaluationStatus.HIT
        return HistoricalOutcomeResult(
            symbol=symbol,
            signal_id=self.signal_definition().id,
            signal_date=signal_date,
            outcome_definition_id=self.outcome_definition(horizon=horizon).id,
            status=status,
            horizon_bars=horizon,
            available_future_bars=available,
            reference_high=115.0,
            intraday_target_hit=is_hit,
            intraday_target_hit_date=hit_date if is_hit else None,
            intraday_target_hit_bar_index=hit_index if is_hit else None,
            close_target_hit=False,
            close_target_hit_date=None,
            close_target_hit_bar_index=None,
            max_close_return=mfe,
            max_close_return_date=None,
            max_adverse_return=mae,
            max_adverse_return_date=None,
            end_of_window_return=end_return,
        )

    def case(self, status, *, signal_date, symbol="TEST", **kwargs):
        event = self.event(signal_date, symbol=symbol)
        outcome = self.outcome(status, signal_date=signal_date, symbol=symbol, **kwargs)
        return HistoricalBacktestCase(
            symbol=symbol,
            signal_event=event,
            outcome=outcome,
            case_id=build_case_id(symbol, event, outcome),
        )

    def test_config_rejects_bad_cooldown(self):
        with self.assertRaises(ValueError):
            self.config(overlap_policy=OverlappingSignalPolicy.COOLDOWN)
        with self.assertRaises(ValueError):
            self.config(overlap_policy=OverlappingSignalPolicy.ALLOW_ALL, cooldown_bars=5)

    def test_full_horizon_end_date_uses_trading_bars_not_calendar_days(self):
        prices = self.price_series(days=10)
        case = self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[0].trading_date)

        self.assertEqual(full_horizon_end_date(case, prices), prices.bars[5].trading_date)

    def test_hit_known_when_first_hit_date_is_before_replay(self):
        prices = self.price_series(days=20)
        case = self.case(
            OutcomeEvaluationStatus.HIT,
            signal_date=prices.bars[1].trading_date,
            hit_date=prices.bars[3].trading_date,
            hit_index=2,
        )

        self.assertTrue(is_outcome_known_as_of(case, prices, prices.bars[3].trading_date))

    def test_future_hit_is_not_known_as_of_replay(self):
        prices = self.price_series(days=20)
        case = self.case(
            OutcomeEvaluationStatus.HIT,
            signal_date=prices.bars[1].trading_date,
            hit_date=prices.bars[7].trading_date,
            hit_index=6,
        )

        self.assertFalse(is_outcome_known_as_of(case, prices, prices.bars[5].trading_date))

    def test_miss_known_only_after_full_horizon_completed(self):
        prices = self.price_series(days=20)
        case = self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[1].trading_date)

        self.assertFalse(is_outcome_known_as_of(case, prices, prices.bars[5].trading_date))
        self.assertTrue(is_outcome_known_as_of(case, prices, prices.bars[6].trading_date))

    def test_return_metrics_known_only_after_full_horizon_completed(self):
        prices = self.price_series(days=20)
        case = self.case(
            OutcomeEvaluationStatus.HIT,
            signal_date=prices.bars[1].trading_date,
            hit_date=prices.bars[3].trading_date,
            hit_index=2,
        )

        self.assertTrue(is_outcome_known_as_of(case, prices, prices.bars[3].trading_date))
        self.assertFalse(are_return_metrics_known_as_of(case, prices, prices.bars[3].trading_date))
        self.assertTrue(are_return_metrics_known_as_of(case, prices, prices.bars[6].trading_date))

    def test_point_in_time_denominator_excludes_future_known_today_outcomes(self):
        prices = self.price_series(days=40)
        replay_date = prices.bars[18].trading_date
        cases = (
            self.case(OutcomeEvaluationStatus.HIT, signal_date=prices.bars[1].trading_date, hit_date=prices.bars[2].trading_date, hit_index=1),
            self.case(OutcomeEvaluationStatus.HIT, signal_date=prices.bars[3].trading_date, hit_date=prices.bars[4].trading_date, hit_index=1),
            self.case(OutcomeEvaluationStatus.HIT, signal_date=prices.bars[5].trading_date, hit_date=prices.bars[6].trading_date, hit_index=1),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[7].trading_date),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[9].trading_date),
            self.case(OutcomeEvaluationStatus.HIT, signal_date=prices.bars[16].trading_date, hit_date=prices.bars[20].trading_date, hit_index=4),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[17].trading_date),
        )

        summary = build_point_in_time_backtest_summary(
            cases,
            price_series=prices,
            config=self.config(replay_date=replay_date),
            actual_signal_date=replay_date,
        )

        self.assertEqual(summary.resolved_as_of_count, 5)
        self.assertEqual(summary.hit_as_of_count, 3)
        self.assertEqual(summary.miss_as_of_count, 2)
        self.assertEqual(summary.incomplete_as_of_count, 2)
        self.assertEqual(summary.historical_hit_rate_as_of, 0.6)

    def test_early_hit_enters_denominator_but_not_return_aggregates(self):
        prices = self.price_series(days=20)
        replay_date = prices.bars[6].trading_date
        early_hit = self.case(
            OutcomeEvaluationStatus.HIT,
            signal_date=prices.bars[4].trading_date,
            hit_date=prices.bars[5].trading_date,
            hit_index=1,
            mfe=0.5,
            mae=-0.5,
            end_return=0.4,
        )
        old_miss = self.case(
            OutcomeEvaluationStatus.MISS,
            signal_date=prices.bars[0].trading_date,
            mfe=0.1,
            mae=-0.1,
            end_return=-0.01,
        )

        summary = build_point_in_time_backtest_summary(
            (early_hit, old_miss),
            price_series=prices,
            config=self.config(replay_date=replay_date),
            actual_signal_date=replay_date,
        )

        self.assertEqual(summary.resolved_as_of_count, 2)
        self.assertEqual(summary.hit_as_of_count, 1)
        self.assertEqual(summary.max_return_sample_count_as_of, 1)
        self.assertEqual(summary.median_max_close_return_as_of, 0.1)

    def test_future_signal_after_actual_date_excluded_from_context(self):
        prices = self.price_series(days=20)
        actual_date = prices.bars[8].trading_date
        future_case = self.case(
            OutcomeEvaluationStatus.HIT,
            signal_date=prices.bars[10].trading_date,
            hit_date=prices.bars[11].trading_date,
            hit_index=1,
        )

        summary = build_point_in_time_backtest_summary(
            (future_case,),
            price_series=prices,
            config=self.config(replay_date=actual_date),
            actual_signal_date=actual_date,
        )

        self.assertEqual(summary.raw_signal_count, 0)
        self.assertEqual(summary.resolved_as_of_count, 0)

    def test_raw_and_evaluated_counts_are_as_of(self):
        prices = self.price_series(days=20)
        actual_date = prices.bars[8].trading_date
        raw_events = (self.event(prices.bars[1].trading_date), self.event(prices.bars[10].trading_date))
        evaluated_events = (self.event(prices.bars[1].trading_date),)

        summary = build_point_in_time_backtest_summary(
            tuple(),
            price_series=prices,
            config=self.config(replay_date=actual_date),
            actual_signal_date=actual_date,
            raw_events=raw_events,
            evaluated_events=evaluated_events,
        )

        self.assertEqual(summary.raw_signal_count, 1)
        self.assertEqual(summary.evaluated_signal_count, 1)

    def test_replay_signal_uses_sliced_series_for_weekend_actual_date(self):
        prices = self.price_series(days=20)
        replay_date = date(2024, 1, 14)
        built_lengths = []

        def technical_builder(series):
            built_lengths.append(len(series.bars))
            return self.technical_series_from_prices(series)

        actual_date = max(bar.trading_date for bar in prices.bars if bar.trading_date <= replay_date)
        report = ReportStub("TEST", tuple())
        service = HistoricalReplayService(
            price_loader=lambda symbol, *, force_refresh=False: prices,
            technical_builder=technical_builder,
            backtest_runner=RecordingBacktestRunner({"TEST": report}),
        )

        result = service.replay_scan(("TEST",), self.config(replay_date=replay_date))

        self.assertEqual(result.match_candidates[0].requested_replay_date, replay_date)
        self.assertEqual(result.match_candidates[0].actual_signal_date, actual_date)
        self.assertEqual(built_lengths[0], len([bar for bar in prices.bars if bar.trading_date <= replay_date]))

    def test_replay_before_earliest_price_is_not_evaluable(self):
        prices = self.price_series(start=date(2024, 1, 10), days=5)
        service = HistoricalReplayService(price_loader=lambda symbol, *, force_refresh=False: prices)

        result = service.replay_scan(("TEST",), self.config(replay_date=date(2024, 1, 1)))

        self.assertEqual(result.matched_count, 0)
        self.assertEqual(result.not_evaluable_count, 1)
        self.assertEqual(result.not_evaluable_symbols[0].reason, "no market data available on or before replay date")

    def test_insufficient_technical_history_is_not_evaluable(self):
        prices = self.price_series(days=3)
        service = HistoricalReplayService(
            price_loader=lambda symbol, *, force_refresh=False: prices,
            technical_builder=lambda series: self.technical_series_from_prices(series, insufficient=True),
        )

        result = service.replay_scan(("TEST",), self.config(replay_date=prices.bars[-1].trading_date))

        self.assertEqual(result.not_evaluable_count, 1)
        self.assertEqual(result.not_evaluable_symbols[0].actual_signal_date, prices.bars[-1].trading_date)

    def test_no_match_is_preserved_without_backtest(self):
        prices = self.price_series(days=10)
        runner = RecordingBacktestRunner({})
        service = HistoricalReplayService(
            price_loader=lambda symbol, *, force_refresh=False: prices,
            technical_builder=lambda series: self.technical_series_from_prices(series, match=False),
            backtest_runner=runner,
        )

        result = service.replay_scan(("TEST",), self.config(replay_date=prices.bars[-1].trading_date))

        self.assertEqual(result.no_match_count, 1)
        self.assertEqual(runner.calls, [])

    def test_symbol_failure_isolated(self):
        prices = self.price_series(symbol="OK", days=10)
        service = HistoricalReplayService(
            price_loader=lambda symbol, *, force_refresh=False: (_ for _ in ()).throw(RuntimeError("boom")) if symbol == "FAIL" else prices,
            technical_builder=lambda series: self.technical_series_from_prices(series),
            backtest_runner=RecordingBacktestRunner({"OK": ReportStub("OK", tuple())}),
        )

        result = service.replay_scan(("OK", "FAIL"), self.config(replay_date=prices.bars[-1].trading_date))

        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.failure_count, 1)

    def test_result_count_invariant_uses_unique_normalized_symbols(self):
        prices = self.price_series(symbol="2330.TW", days=10)
        service = HistoricalReplayService(
            price_loader=lambda symbol, *, force_refresh=False: prices,
            technical_builder=lambda series: self.technical_series_from_prices(series),
            backtest_runner=RecordingBacktestRunner({"2330.TW": ReportStub("2330.TW", tuple())}),
        )

        result = service.replay_scan(("2330", "2330.TW"), self.config(replay_date=prices.bars[-1].trading_date))

        total = result.matched_count + result.no_match_count + result.not_evaluable_count + result.failure_count
        self.assertEqual(result.normalized_symbols, ("2330.TW",))
        self.assertEqual(total, len(result.normalized_symbols))

    def test_mixed_market_actual_dates_are_per_symbol(self):
        prices_a = self.price_series(symbol="AAA", start=date(2024, 1, 1), days=10)
        prices_b = HistoricalPriceSeries(
            symbol="BBB",
            currency="USD",
            bars=prices_a.bars[:-1],
            fetched_at=FETCHED_AT,
        )
        prices_by_symbol = {"AAA": prices_a, "BBB": prices_b}
        reports = {"AAA": ReportStub("AAA", tuple()), "BBB": ReportStub("BBB", tuple())}
        service = HistoricalReplayService(
            price_loader=lambda symbol, *, force_refresh=False: prices_by_symbol[symbol],
            technical_builder=lambda series: self.technical_series_from_prices(series),
            backtest_runner=RecordingBacktestRunner(reports),
        )

        result = service.replay_scan(("AAA", "BBB"), self.config(replay_date=prices_a.bars[-1].trading_date))
        actual_dates = {candidate.symbol: candidate.actual_signal_date for candidate in result.match_candidates}

        self.assertEqual(actual_dates["AAA"], prices_a.bars[-1].trading_date)
        self.assertEqual(actual_dates["BBB"], prices_b.bars[-1].trading_date)

    def test_ranking_uses_as_of_summary_not_post_replay_outcome(self):
        prices = self.price_series(days=20)
        config = self.config(replay_date=prices.bars[10].trading_date, preferred_resolved_samples=1)
        match_a = evaluate_signal_conditions(self.snapshot(prices.bars[10].trading_date, symbol="AAA"), config.signal_definition)
        match_b = evaluate_signal_conditions(self.snapshot(prices.bars[10].trading_date, symbol="BBB"), config.signal_definition)
        summary_a = build_point_in_time_backtest_summary(
            (self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[1].trading_date, symbol="AAA"),),
            price_series=prices,
            config=config,
            actual_signal_date=prices.bars[10].trading_date,
        )
        summary_b = build_point_in_time_backtest_summary(
            (self.case(OutcomeEvaluationStatus.HIT, signal_date=prices.bars[1].trading_date, symbol="BBB", hit_date=prices.bars[2].trading_date, hit_index=1),),
            price_series=prices,
            config=config,
            actual_signal_date=prices.bars[10].trading_date,
        )
        great_future_for_a = self.outcome(OutcomeEvaluationStatus.HIT, signal_date=prices.bars[10].trading_date, hit_date=prices.bars[11].trading_date, hit_index=1)
        bad_future_for_b = self.outcome(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[10].trading_date)

        ranked = rank_historical_replay_candidates((
            build_historical_replay_candidate(
                signal_match=match_a,
                summary=summary_a,
                post_replay_outcome=great_future_for_a,
                price_series=prices,
                config=config,
            ),
            build_historical_replay_candidate(
                signal_match=match_b,
                summary=summary_b,
                post_replay_outcome=bad_future_for_b,
                price_series=prices,
                config=config,
            ),
        ))

        self.assertEqual([candidate.symbol for candidate in ranked], ["BBB", "AAA"])
        self.assertEqual(ranked[0].rank_components[1].source_metric, "historical_hit_rate_as_of")

    def test_future_append_does_not_change_replay_signal_or_as_of_summary(self):
        base_prices = self.price_series(days=10)
        future_bars = tuple(
            HistoricalPriceBar(
                symbol="TEST",
                trading_date=base_prices.bars[-1].trading_date + timedelta(days=index + 1),
                open=999.0,
                high=1200.0,
                low=1.0,
                close=1000.0,
                adjusted_close=1000.0,
                volume=999999,
            )
            for index in range(3)
        )
        extended_prices = HistoricalPriceSeries(
            symbol="TEST",
            currency="USD",
            bars=base_prices.bars + future_bars,
            fetched_at=FETCHED_AT,
        )

        def run(prices):
            service = HistoricalReplayService(
                price_loader=lambda symbol, *, force_refresh=False: prices,
                technical_builder=lambda series: self.technical_series_from_prices(series),
                backtest_runner=RecordingBacktestRunner({"TEST": ReportStub("TEST", tuple())}),
            )
            return service.replay_scan(("TEST",), self.config(replay_date=base_prices.bars[-1].trading_date))

        first = run(base_prices).match_candidates[0]
        second = run(extended_prices).match_candidates[0]

        self.assertEqual(first.actual_signal_date, second.actual_signal_date)
        self.assertEqual(first.signal_match.status, second.signal_match.status)
        self.assertEqual(first.point_in_time_backtest_summary.resolved_as_of_count, second.point_in_time_backtest_summary.resolved_as_of_count)

    def test_replay_candidate_uses_as_of_sample_status(self):
        prices = self.price_series(days=20)
        config = self.config(replay_date=prices.bars[10].trading_date, preferred_resolved_samples=20)
        match = evaluate_signal_conditions(self.snapshot(prices.bars[10].trading_date), config.signal_definition)
        summary = build_point_in_time_backtest_summary(tuple(), price_series=prices, config=config, actual_signal_date=prices.bars[10].trading_date)
        outcome = self.outcome(OutcomeEvaluationStatus.INCOMPLETE, signal_date=prices.bars[10].trading_date, available=0)

        candidate = build_historical_replay_candidate(
            signal_match=match,
            summary=summary,
            post_replay_outcome=outcome,
            price_series=prices,
            config=config,
        )

        self.assertEqual(candidate.sample_size_status.value, "NO_RESOLVED_SAMPLES")

    def test_sample_status_below_preferred_uses_as_of_resolved_count(self):
        prices = self.price_series(days=20)
        config = self.config(replay_date=prices.bars[10].trading_date, preferred_resolved_samples=3)
        case = self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[1].trading_date)
        summary = build_point_in_time_backtest_summary((case,), price_series=prices, config=config, actual_signal_date=prices.bars[10].trading_date)
        match = evaluate_signal_conditions(self.snapshot(prices.bars[10].trading_date), config.signal_definition)
        outcome = self.outcome(OutcomeEvaluationStatus.INCOMPLETE, signal_date=prices.bars[10].trading_date, available=0)

        candidate = build_historical_replay_candidate(
            signal_match=match,
            summary=summary,
            post_replay_outcome=outcome,
            price_series=prices,
            config=config,
        )

        self.assertEqual(candidate.sample_size_status.value, "BELOW_PREFERRED_MINIMUM")

    def test_sample_status_meets_preferred_uses_as_of_resolved_count(self):
        prices = self.price_series(days=20)
        config = self.config(replay_date=prices.bars[10].trading_date, preferred_resolved_samples=1)
        case = self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[1].trading_date)
        summary = build_point_in_time_backtest_summary((case,), price_series=prices, config=config, actual_signal_date=prices.bars[10].trading_date)
        match = evaluate_signal_conditions(self.snapshot(prices.bars[10].trading_date), config.signal_definition)
        outcome = self.outcome(OutcomeEvaluationStatus.INCOMPLETE, signal_date=prices.bars[10].trading_date, available=0)

        candidate = build_historical_replay_candidate(
            signal_match=match,
            summary=summary,
            post_replay_outcome=outcome,
            price_series=prices,
            config=config,
        )

        self.assertEqual(candidate.sample_size_status.value, "MEETS_PREFERRED_MINIMUM")

    def test_backtest_config_end_date_is_actual_signal_date(self):
        config = self.config(replay_date=date(2024, 6, 30))
        actual_signal_date = date(2024, 6, 28)

        backtest_config = config.to_backtest_config(actual_signal_date=actual_signal_date)

        self.assertEqual(backtest_config.start_date, config.historical_start_date)
        self.assertEqual(backtest_config.end_date, actual_signal_date)

    def test_historical_start_date_filters_old_cases(self):
        prices = self.price_series(days=20)
        replay_date = prices.bars[10].trading_date
        old_case = self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[1].trading_date)
        kept_case = self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[3].trading_date)

        summary = build_point_in_time_backtest_summary(
            (old_case, kept_case),
            price_series=prices,
            config=self.config(replay_date=replay_date, historical_start_date=prices.bars[3].trading_date),
            actual_signal_date=replay_date,
        )

        self.assertEqual(summary.resolved_as_of_count, 1)

    def test_not_evaluable_case_is_counted_but_excluded_from_denominator(self):
        prices = self.price_series(days=20)
        replay_date = prices.bars[10].trading_date
        case = self.case(OutcomeEvaluationStatus.NOT_EVALUABLE, signal_date=prices.bars[1].trading_date)

        summary = build_point_in_time_backtest_summary(
            (case,),
            price_series=prices,
            config=self.config(replay_date=replay_date),
            actual_signal_date=replay_date,
        )

        self.assertEqual(summary.not_evaluable_as_of_count, 1)
        self.assertEqual(summary.resolved_as_of_count, 0)
        self.assertIsNone(summary.historical_hit_rate_as_of)

    def test_incomplete_case_is_not_known_as_of(self):
        prices = self.price_series(days=20)
        case = self.case(OutcomeEvaluationStatus.INCOMPLETE, signal_date=prices.bars[1].trading_date, available=2)

        self.assertFalse(is_outcome_known_as_of(case, prices, prices.bars[10].trading_date))

    def test_metric_known_cases_preserve_only_completed_horizon_cases(self):
        prices = self.price_series(days=20)
        replay_date = prices.bars[6].trading_date
        old_case = self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[0].trading_date)
        early_hit = self.case(
            OutcomeEvaluationStatus.HIT,
            signal_date=prices.bars[4].trading_date,
            hit_date=prices.bars[5].trading_date,
            hit_index=1,
        )

        summary = build_point_in_time_backtest_summary(
            (old_case, early_hit),
            price_series=prices,
            config=self.config(replay_date=replay_date),
            actual_signal_date=replay_date,
        )

        self.assertEqual(summary.known_cases, (old_case, early_hit))
        self.assertEqual(summary.metric_known_cases, (old_case,))

    def test_hit_bar_aggregate_can_include_early_hit_before_full_horizon(self):
        prices = self.price_series(days=20)
        replay_date = prices.bars[6].trading_date
        early_hit = self.case(
            OutcomeEvaluationStatus.HIT,
            signal_date=prices.bars[4].trading_date,
            hit_date=prices.bars[5].trading_date,
            hit_index=1,
        )

        summary = build_point_in_time_backtest_summary(
            (early_hit,),
            price_series=prices,
            config=self.config(replay_date=replay_date),
            actual_signal_date=replay_date,
        )

        self.assertEqual(summary.hit_bar_sample_count_as_of, 1)
        self.assertEqual(summary.median_hit_bar_index_as_of, 1)

    def test_no_resolved_cases_hit_rate_is_none_not_zero(self):
        prices = self.price_series(days=20)
        replay_date = prices.bars[3].trading_date
        future_hit = self.case(
            OutcomeEvaluationStatus.HIT,
            signal_date=prices.bars[1].trading_date,
            hit_date=prices.bars[5].trading_date,
            hit_index=4,
        )

        summary = build_point_in_time_backtest_summary(
            (future_hit,),
            price_series=prices,
            config=self.config(replay_date=replay_date),
            actual_signal_date=replay_date,
        )

        self.assertEqual(summary.resolved_as_of_count, 0)
        self.assertIsNone(summary.historical_hit_rate_as_of)

    def test_all_miss_as_of_hit_rate_is_zero(self):
        prices = self.price_series(days=20)
        replay_date = prices.bars[10].trading_date
        cases = (
            self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[1].trading_date),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[2].trading_date),
        )

        summary = build_point_in_time_backtest_summary(
            cases,
            price_series=prices,
            config=self.config(replay_date=replay_date),
            actual_signal_date=replay_date,
        )

        self.assertEqual(summary.historical_hit_rate_as_of, 0.0)

    def test_all_hit_as_of_hit_rate_is_one(self):
        prices = self.price_series(days=20)
        replay_date = prices.bars[10].trading_date
        cases = (
            self.case(OutcomeEvaluationStatus.HIT, signal_date=prices.bars[1].trading_date, hit_date=prices.bars[2].trading_date, hit_index=1),
            self.case(OutcomeEvaluationStatus.HIT, signal_date=prices.bars[2].trading_date, hit_date=prices.bars[3].trading_date, hit_index=1),
        )

        summary = build_point_in_time_backtest_summary(
            cases,
            price_series=prices,
            config=self.config(replay_date=replay_date),
            actual_signal_date=replay_date,
        )

        self.assertEqual(summary.historical_hit_rate_as_of, 1.0)

    def test_return_aggregates_use_known_metric_cases_only(self):
        prices = self.price_series(days=20)
        replay_date = prices.bars[10].trading_date
        cases = (
            self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[1].trading_date, mfe=0.10, mae=-0.05, end_return=0.03),
            self.case(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[2].trading_date, mfe=0.20, mae=-0.07, end_return=0.05),
        )

        summary = build_point_in_time_backtest_summary(
            cases,
            price_series=prices,
            config=self.config(replay_date=replay_date),
            actual_signal_date=replay_date,
        )

        self.assertEqual(summary.max_return_sample_count_as_of, 2)
        self.assertAlmostEqual(summary.average_max_close_return_as_of, 0.15)
        self.assertAlmostEqual(summary.median_max_adverse_return_as_of, -0.06)
        self.assertAlmostEqual(summary.median_end_return_as_of, 0.04)

    def test_post_replay_outcome_can_differ_without_changing_rank_components(self):
        prices = self.price_series(days=20)
        config = self.config(replay_date=prices.bars[10].trading_date, preferred_resolved_samples=1)
        match = evaluate_signal_conditions(self.snapshot(prices.bars[10].trading_date), config.signal_definition)
        summary = build_point_in_time_backtest_summary(tuple(), price_series=prices, config=config, actual_signal_date=prices.bars[10].trading_date)
        hit_outcome = self.outcome(OutcomeEvaluationStatus.HIT, signal_date=prices.bars[10].trading_date, hit_date=prices.bars[11].trading_date, hit_index=1)
        miss_outcome = self.outcome(OutcomeEvaluationStatus.MISS, signal_date=prices.bars[10].trading_date)

        first = build_historical_replay_candidate(signal_match=match, summary=summary, post_replay_outcome=hit_outcome, price_series=prices, config=config)
        second = build_historical_replay_candidate(signal_match=match, summary=summary, post_replay_outcome=miss_outcome, price_series=prices, config=config)

        self.assertEqual(first.rank_components, second.rank_components)

    def test_source_stale_flag_is_preserved_on_replay_candidate(self):
        prices = self.price_series(days=20, stale=True)
        config = self.config(replay_date=prices.bars[10].trading_date)
        match = evaluate_signal_conditions(self.snapshot(prices.bars[10].trading_date), config.signal_definition)
        summary = build_point_in_time_backtest_summary(tuple(), price_series=prices, config=config, actual_signal_date=prices.bars[10].trading_date)
        outcome = self.outcome(OutcomeEvaluationStatus.INCOMPLETE, signal_date=prices.bars[10].trading_date, available=0)

        candidate = build_historical_replay_candidate(signal_match=match, summary=summary, post_replay_outcome=outcome, price_series=prices, config=config)

        self.assertTrue(candidate.source_price_is_stale)
        self.assertEqual(candidate.source_price_fetched_at, FETCHED_AT)

    def test_force_refresh_is_passed_to_price_loader(self):
        prices = self.price_series(days=10)
        force_refresh_values = []

        def price_loader(symbol, *, force_refresh=False):
            force_refresh_values.append(force_refresh)
            return prices

        service = HistoricalReplayService(
            price_loader=price_loader,
            technical_builder=lambda series: self.technical_series_from_prices(series),
            backtest_runner=RecordingBacktestRunner({"TEST": ReportStub("TEST", tuple())}),
        )

        service.replay_scan(("TEST",), self.config(replay_date=prices.bars[-1].trading_date, force_refresh=True))

        self.assertEqual(force_refresh_values, [True])

    def test_replay_scan_accepts_empty_symbols(self):
        service = HistoricalReplayService()

        result = service.replay_scan(tuple(), self.config())

        self.assertEqual(result.normalized_symbols, tuple())
        self.assertEqual(result.scanned_count, 0)


if __name__ == "__main__":
    unittest.main()
