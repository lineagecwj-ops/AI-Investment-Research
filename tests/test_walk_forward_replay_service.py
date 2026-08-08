import sys
import unittest
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from historical_replay_service import HistoricalReplayResult
from models import HistoricalOutcomeResult
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeDefinition
from models import OutcomeEvaluationStatus
from models import OutcomeType
from models import OverlappingSignalPolicy
from models import SignalConditionOperator
from models import SignalDefinition
from models import TechnicalSignalCondition
from walk_forward_replay_service import MAX_REPLAY_PERIODS
from walk_forward_replay_service import WalkForwardReplayConfig
from walk_forward_replay_service import WalkForwardReplayFrequency
from walk_forward_replay_service import WalkForwardReplayPeriod
from walk_forward_replay_service import WalkForwardReplayService
from walk_forward_replay_service import build_walk_forward_id
from walk_forward_replay_service import generate_replay_dates
from walk_forward_replay_service import summarize_walk_forward_periods


FETCHED_AT = datetime(2026, 8, 8, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 8, 2, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CandidateStub:

    symbol: str

    requested_replay_date: date

    post_replay_outcome: HistoricalOutcomeResult

    research_rank: int | None = None


class RecordingPriceLoader:

    def __init__(self):
        self.calls = []

    def __call__(self, symbol, *, force_refresh=False):
        self.calls.append((symbol, force_refresh))
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="USD",
            bars=(
                HistoricalPriceBar(
                    symbol=symbol,
                    trading_date=date(2024, 1, 2),
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    adjusted_close=100.0,
                    volume=1000,
                ),
            ),
            fetched_at=FETCHED_AT,
            is_stale=False,
        )


class FakeReplayService:

    def __init__(self, candidate_plan=None, fail_dates=()):
        self.calls = []
        self.candidate_plan = candidate_plan or {}
        self.fail_dates = set(fail_dates)

    def replay_scan(self, symbols, config, *, price_series_by_symbol=None):
        self.calls.append((tuple(symbols), config, price_series_by_symbol))
        if config.replay_date in self.fail_dates:
            raise RuntimeError(f"period failed for {config.replay_date}")
        candidates = tuple(self.candidate_plan.get(config.replay_date, ()))
        matched_symbols = {candidate.symbol for candidate in candidates}
        normalized_symbols = tuple(symbols)
        no_match_symbols = tuple(symbol for symbol in normalized_symbols if symbol not in matched_symbols)
        return HistoricalReplayResult(
            config=config,
            requested_symbols=tuple(symbols),
            normalized_symbols=normalized_symbols,
            match_candidates=candidates,
            no_match_symbols=no_match_symbols,
            no_match_details=tuple(),
            not_evaluable_symbols=tuple(),
            failed_symbols=tuple(),
            generated_at=GENERATED_AT,
        )


class WalkForwardReplayServiceTestCase(unittest.TestCase):

    def signal_definition(self):
        return SignalDefinition(
            id="technical_example_v1",
            name="Technical Example",
            conditions=(
                TechnicalSignalCondition(
                    metric="analysis_close",
                    operator=SignalConditionOperator.GREATER_THAN,
                    secondary_metric="sma_20",
                ),
            ),
            minimum_required_features=("analysis_close", "sma_20"),
            description="Test signal.",
        )

    def outcome_definition(self):
        return OutcomeDefinition(
            id="raw_high_breakout_60d_within_20d_v1",
            outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
            horizon_bars=20,
            reference_metric="prior_high_60d",
        )

    def config(self, **overrides):
        values = {
            "start_date": date(2024, 1, 1),
            "end_date": date(2024, 3, 31),
            "frequency": WalkForwardReplayFrequency.MONTHLY,
            "signal_definition": self.signal_definition(),
            "outcome_definition": self.outcome_definition(),
            "overlap_policy": OverlappingSignalPolicy.ALLOW_ALL,
            "cooldown_bars": None,
            "historical_start_date": date(2018, 1, 1),
            "preferred_resolved_samples": 20,
        }
        values.update(overrides)
        return WalkForwardReplayConfig(**values)

    def outcome(self, status):
        return HistoricalOutcomeResult(
            symbol="TEST",
            signal_id=self.signal_definition().id,
            signal_date=date(2024, 1, 31),
            outcome_definition_id=self.outcome_definition().id,
            status=status,
            horizon_bars=20,
            available_future_bars=20,
            reference_high=100.0,
            intraday_target_hit=status is OutcomeEvaluationStatus.HIT,
            intraday_target_hit_date=date(2024, 2, 1) if status is OutcomeEvaluationStatus.HIT else None,
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

    def candidate(self, symbol, replay_date, status=OutcomeEvaluationStatus.HIT, rank=None):
        return CandidateStub(
            symbol=symbol,
            requested_replay_date=replay_date,
            post_replay_outcome=self.outcome(status),
            research_rank=rank,
        )

    def test_monthly_dates_are_calendar_month_ends(self):
        self.assertEqual(
            generate_replay_dates(self.config()),
            (date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)),
        )

    def test_monthly_leap_year_includes_february_29(self):
        self.assertEqual(
            generate_replay_dates(self.config(start_date=date(2024, 2, 1), end_date=date(2024, 2, 29))),
            (date(2024, 2, 29),),
        )

    def test_monthly_year_boundary(self):
        self.assertEqual(
            generate_replay_dates(self.config(start_date=date(2023, 12, 1), end_date=date(2024, 1, 31))),
            (date(2023, 12, 31), date(2024, 1, 31)),
        )

    def test_partial_first_month_uses_month_end(self):
        self.assertEqual(
            generate_replay_dates(self.config(start_date=date(2024, 1, 20), end_date=date(2024, 2, 29))),
            (date(2024, 1, 31), date(2024, 2, 29)),
        )

    def test_partial_last_month_excludes_month_end_after_end_date(self):
        self.assertEqual(
            generate_replay_dates(self.config(start_date=date(2024, 1, 1), end_date=date(2024, 3, 15))),
            (date(2024, 1, 31), date(2024, 2, 29)),
        )

    def test_single_month_without_month_end_is_empty(self):
        self.assertEqual(
            generate_replay_dates(self.config(start_date=date(2024, 1, 1), end_date=date(2024, 1, 15))),
            tuple(),
        )

    def test_weekly_dates_are_fridays(self):
        config = self.config(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 20),
            frequency=WalkForwardReplayFrequency.WEEKLY,
        )
        self.assertEqual(
            generate_replay_dates(config),
            (date(2024, 1, 5), date(2024, 1, 12), date(2024, 1, 19)),
        )

    def test_invalid_range_is_rejected(self):
        with self.assertRaises(ValueError):
            self.config(start_date=date(2024, 2, 1), end_date=date(2024, 1, 31))

    def test_bad_cooldown_config_is_rejected(self):
        with self.assertRaises(ValueError):
            self.config(overlap_policy=OverlappingSignalPolicy.COOLDOWN)
        with self.assertRaises(ValueError):
            self.config(overlap_policy=OverlappingSignalPolicy.ALLOW_ALL, cooldown_bars=20)

    def test_period_safety_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            generate_replay_dates(
                self.config(
                    start_date=date(2020, 1, 1),
                    end_date=date(2031, 1, 31),
                    max_replay_periods=MAX_REPLAY_PERIODS,
                )
            )

    def test_run_preserves_period_order(self):
        replay_service = FakeReplayService()
        result = WalkForwardReplayService(
            price_loader=RecordingPriceLoader(),
            replay_service=replay_service,
        ).run_walk_forward_replay(("A",), self.config())

        self.assertEqual(result.replay_dates, (date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)))
        self.assertEqual([period.requested_replay_date for period in result.period_results], list(result.replay_dates))

    def test_loader_runs_once_per_symbol_not_period_symbol(self):
        loader = RecordingPriceLoader()
        replay_service = FakeReplayService()

        WalkForwardReplayService(
            price_loader=loader,
            replay_service=replay_service,
        ).run_walk_forward_replay(("AAPL", "aapl", "MSFT"), self.config())

        self.assertEqual([call[0] for call in loader.calls], ["AAPL", "MSFT"])
        self.assertEqual(len(replay_service.calls), 3)
        self.assertEqual(len(loader.calls), 2)

    def test_replay_service_receives_cached_full_series(self):
        loader = RecordingPriceLoader()
        replay_service = FakeReplayService()

        WalkForwardReplayService(
            price_loader=loader,
            replay_service=replay_service,
        ).run_walk_forward_replay(("AAPL",), self.config())

        for _, _, cache in replay_service.calls:
            self.assertIsNotNone(cache)
            self.assertEqual(tuple(cache), ("AAPL",))

    def test_force_refresh_is_used_only_on_initial_symbol_load(self):
        loader = RecordingPriceLoader()
        WalkForwardReplayService(
            price_loader=loader,
            replay_service=FakeReplayService(),
        ).run_walk_forward_replay(("AAPL", "MSFT"), self.config(force_refresh=True))

        self.assertEqual(loader.calls, [("AAPL", True), ("MSFT", True)])

    def test_single_vs_multi_period_result_is_same_object_from_replay_service(self):
        june = date(2024, 6, 30)
        candidate = self.candidate("AAPL", june)
        replay_service = FakeReplayService(candidate_plan={june: (candidate,)})
        config = self.config(start_date=june, end_date=june)

        direct = replay_service.replay_scan(("AAPL",), config.to_replay_config(june), price_series_by_symbol={})
        replay_service.calls.clear()
        result = WalkForwardReplayService(
            price_loader=RecordingPriceLoader(),
            replay_service=replay_service,
        ).run_walk_forward_replay(("AAPL",), config)

        self.assertEqual(result.period_results[0].replay_result.match_candidates, direct.match_candidates)

    def test_period_count_matches_generated_dates_even_for_zero_match(self):
        result = WalkForwardReplayService(
            price_loader=RecordingPriceLoader(),
            replay_service=FakeReplayService(),
        ).run_walk_forward_replay(("AAPL",), self.config())

        self.assertEqual(len(result.period_results), len(result.replay_dates))
        self.assertEqual(result.summary.period_count, 3)
        self.assertEqual(result.summary.periods_without_matches, 3)

    def test_zero_match_period_is_preserved(self):
        result = WalkForwardReplayService(
            price_loader=RecordingPriceLoader(),
            replay_service=FakeReplayService(),
        ).run_walk_forward_replay(("AAPL",), self.config())

        self.assertEqual(result.period_results[0].matched_count, 0)
        self.assertEqual(result.period_results[0].no_match_count, 1)

    def test_all_zero_match_walk_forward_is_successful(self):
        result = WalkForwardReplayService(
            price_loader=RecordingPriceLoader(),
            replay_service=FakeReplayService(),
        ).run_walk_forward_replay(("AAPL",), self.config())

        self.assertEqual(result.summary.total_candidate_occurrences, 0)
        self.assertEqual(result.summary.unique_candidate_symbols, 0)

    def test_candidate_occurrences_and_unique_symbols_are_separate(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        periods = (
            self.period(jan, (self.candidate("A", jan),)),
            self.period(feb, (self.candidate("A", feb), self.candidate("B", feb))),
        )

        summary = summarize_walk_forward_periods(periods)

        self.assertEqual(summary.total_candidate_occurrences, 3)
        self.assertEqual(summary.unique_candidate_symbols, 2)

    def test_symbol_summary_counts_repeated_candidates(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        mar = date(2024, 3, 31)
        summary = summarize_walk_forward_periods(
            (
                self.period(jan, (self.candidate("A", jan),)),
                self.period(feb, (self.candidate("A", feb), self.candidate("B", feb))),
                self.period(mar, (self.candidate("A", mar),)),
            )
        )

        a_summary = next(item for item in summary.symbol_summaries if item.symbol == "A")
        b_summary = next(item for item in summary.symbol_summaries if item.symbol == "B")
        self.assertEqual(a_summary.candidate_occurrence_count, 3)
        self.assertEqual(b_summary.candidate_occurrence_count, 1)
        self.assertEqual(a_summary.first_candidate_date, jan)
        self.assertEqual(a_summary.last_candidate_date, mar)

    def test_outcome_counts_are_counts_not_fraction(self):
        jan = date(2024, 1, 31)
        summary = summarize_walk_forward_periods(
            (
                self.period(
                    jan,
                    (
                        self.candidate("A", jan, OutcomeEvaluationStatus.HIT),
                        self.candidate("B", jan, OutcomeEvaluationStatus.HIT),
                        self.candidate("C", jan, OutcomeEvaluationStatus.MISS),
                        self.candidate("D", jan, OutcomeEvaluationStatus.INCOMPLETE),
                        self.candidate("E", jan, OutcomeEvaluationStatus.NOT_EVALUABLE),
                    ),
                ),
            )
        )

        self.assertEqual(summary.post_replay_hit_occurrences, 2)
        self.assertEqual(summary.post_replay_miss_occurrences, 1)
        self.assertEqual(summary.post_replay_incomplete_occurrences, 1)
        self.assertEqual(summary.post_replay_not_evaluable_occurrences, 1)
        self.assertFalse(hasattr(summary, "walk_forward_hit_rate"))

    def test_period_failure_isolated_and_later_period_runs(self):
        replay_service = FakeReplayService(fail_dates=(date(2024, 2, 29),))
        result = WalkForwardReplayService(
            price_loader=RecordingPriceLoader(),
            replay_service=replay_service,
        ).run_walk_forward_replay(("AAPL",), self.config())

        self.assertIsNone(result.period_results[1].replay_result)
        self.assertEqual(result.period_results[1].failure.error_type, "RuntimeError")
        self.assertEqual(len(replay_service.calls), 3)

    def test_period_level_failure_count_is_one(self):
        period = WalkForwardReplayPeriod(
            requested_replay_date=date(2024, 1, 31),
            failure=type("Failure", (), {"requested_replay_date": date(2024, 1, 31)})(),
        )

        self.assertEqual(period.failed_count, 1)

    def test_empty_symbols_returns_safe_empty_result_without_loading_prices(self):
        loader = RecordingPriceLoader()
        result = WalkForwardReplayService(
            price_loader=loader,
            replay_service=FakeReplayService(),
        ).run_walk_forward_replay(tuple(), self.config())

        self.assertEqual(result.normalized_symbols, tuple())
        self.assertEqual(result.period_results, tuple())
        self.assertEqual(loader.calls, [])

    def test_requested_symbols_snapshot_is_frozen_in_result(self):
        symbols = ["AAPL", "MSFT"]
        result = WalkForwardReplayService(
            price_loader=RecordingPriceLoader(),
            replay_service=FakeReplayService(),
        ).run_walk_forward_replay(symbols, self.config())
        symbols.append("NVDA")

        self.assertEqual(result.requested_symbols, ("AAPL", "MSFT"))
        self.assertEqual(result.normalized_symbols, ("AAPL", "MSFT"))

    def test_period_result_is_frozen_snapshot_tuple(self):
        result = WalkForwardReplayService(
            price_loader=RecordingPriceLoader(),
            replay_service=FakeReplayService(),
        ).run_walk_forward_replay(("AAPL",), self.config())

        self.assertIsInstance(result.period_results, tuple)
        with self.assertRaises(Exception):
            result.period_results = tuple()

    def test_generated_at_is_timezone_aware_utc(self):
        result = WalkForwardReplayService(
            price_loader=RecordingPriceLoader(),
            replay_service=FakeReplayService(),
        ).run_walk_forward_replay(("AAPL",), self.config())

        self.assertEqual(result.generated_at.tzinfo, UTC)

    def test_walk_forward_id_is_deterministic_and_excludes_generated_at(self):
        config = self.config()
        replay_dates = generate_replay_dates(config)

        first = build_walk_forward_id(("AAPL",), config, replay_dates)
        second = build_walk_forward_id(("AAPL",), config, replay_dates)

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("walk_forward_"))

    def test_walk_forward_id_changes_with_frequency(self):
        monthly = self.config()
        weekly = self.config(frequency=WalkForwardReplayFrequency.WEEKLY)

        self.assertNotEqual(
            build_walk_forward_id(("AAPL",), monthly, generate_replay_dates(monthly)),
            build_walk_forward_id(("AAPL",), weekly, generate_replay_dates(weekly)),
        )

    def test_to_replay_config_reuses_single_date_config_values(self):
        config = self.config(overlap_policy=OverlappingSignalPolicy.COOLDOWN, cooldown_bars=20)

        replay_config = config.to_replay_config(date(2024, 1, 31))

        self.assertEqual(replay_config.replay_date, date(2024, 1, 31))
        self.assertEqual(replay_config.signal_definition.id, config.signal_definition.id)
        self.assertEqual(replay_config.outcome_definition.id, config.outcome_definition.id)
        self.assertEqual(replay_config.overlap_policy, OverlappingSignalPolicy.COOLDOWN)
        self.assertEqual(replay_config.cooldown_bars, 20)
        self.assertEqual(replay_config.historical_start_date, date(2018, 1, 1))

    def test_missing_signal_definition_is_fatal_when_building_replay_config(self):
        with self.assertRaises(ValueError):
            self.config(signal_definition=None).to_replay_config(date(2024, 1, 31))

    def test_missing_outcome_definition_is_fatal_when_building_replay_config(self):
        with self.assertRaises(ValueError):
            self.config(outcome_definition=None).to_replay_config(date(2024, 1, 31))

    def test_periods_with_matches_and_without_matches(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        summary = summarize_walk_forward_periods(
            (
                self.period(jan, (self.candidate("A", jan),)),
                self.period(feb, tuple()),
            )
        )

        self.assertEqual(summary.periods_with_matches, 1)
        self.assertEqual(summary.periods_without_matches, 1)

    def test_rank_snapshot_order_is_preserved_inside_period(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        periods = (
            self.period(jan, (self.candidate("B", jan, rank=1), self.candidate("A", jan, rank=2))),
            self.period(feb, (self.candidate("A", feb, rank=1), self.candidate("B", feb, rank=2))),
        )

        self.assertEqual([candidate.symbol for candidate in periods[0].replay_result.match_candidates], ["B", "A"])
        self.assertEqual([candidate.symbol for candidate in periods[1].replay_result.match_candidates], ["A", "B"])

    def test_end_date_limits_replay_dates_not_post_replay_outcome_counts(self):
        final_date = date(2024, 12, 31)
        candidate = self.candidate("A", final_date, OutcomeEvaluationStatus.HIT)
        result = WalkForwardReplayService(
            price_loader=RecordingPriceLoader(),
            replay_service=FakeReplayService(candidate_plan={final_date: (candidate,)}),
        ).run_walk_forward_replay(("A",), self.config(start_date=final_date, end_date=final_date))

        self.assertEqual(result.replay_dates, (final_date,))
        self.assertEqual(result.summary.post_replay_hit_occurrences, 1)

    def test_summary_does_not_expose_probability_language(self):
        summary_fields = set(summarize_walk_forward_periods(tuple()).__dataclass_fields__)

        forbidden = {"probability", "prediction_accuracy", "win_rate", "hit_rate"}
        self.assertTrue(forbidden.isdisjoint(summary_fields))

    def period(self, replay_date, candidates):
        result = HistoricalReplayResult(
            config=self.config(start_date=replay_date, end_date=replay_date).to_replay_config(replay_date),
            requested_symbols=tuple(candidate.symbol for candidate in candidates),
            normalized_symbols=tuple(candidate.symbol for candidate in candidates),
            match_candidates=tuple(candidates),
            no_match_symbols=tuple(),
            no_match_details=tuple(),
            not_evaluable_symbols=tuple(),
            failed_symbols=tuple(),
            generated_at=GENERATED_AT,
        )
        return WalkForwardReplayPeriod(
            requested_replay_date=replay_date,
            replay_result=result,
        )


if __name__ == "__main__":
    unittest.main()
