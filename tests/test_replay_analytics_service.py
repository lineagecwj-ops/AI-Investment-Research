import sys
import unittest
from dataclasses import dataclass
from dataclasses import fields
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from historical_replay_service import HistoricalReplayConfig
from historical_replay_service import HistoricalReplayResult
from models import HistoricalOutcomeResult
from models import OutcomeDefinition
from models import OutcomeEvaluationStatus
from models import OutcomeType
from models import OverlappingSignalPolicy
from models import SignalConditionOperator
from models import SignalDefinition
from models import TechnicalSignalCondition
from replay_analytics_service import ReplayAnalyticsResult
from replay_analytics_service import ReplayAnalyticsService
from replay_analytics_service import ReplayCandidateOccurrence
from replay_analytics_service import ReplayPeriodSummary
from replay_analytics_service import ReplayStabilitySummary
from replay_analytics_service import ReplaySymbolSummary
from replay_analytics_service import build_replay_analytics
from walk_forward_replay_service import WalkForwardReplayConfig
from walk_forward_replay_service import WalkForwardReplayFrequency
from walk_forward_replay_service import WalkForwardReplayPeriod
from walk_forward_replay_service import WalkForwardReplayResult
from walk_forward_replay_service import summarize_walk_forward_periods


GENERATED_AT = datetime(2026, 8, 8, 2, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CandidateStub:

    symbol: str

    requested_replay_date: date

    actual_signal_date: date

    post_replay_outcome: HistoricalOutcomeResult

    research_rank: int | None = None


class ReplayAnalyticsServiceTestCase(unittest.TestCase):

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

    def replay_config(self, replay_date):
        return HistoricalReplayConfig(
            replay_date=replay_date,
            signal_definition=self.signal_definition(),
            outcome_definition=self.outcome_definition(),
            overlap_policy=OverlappingSignalPolicy.ALLOW_ALL,
            historical_start_date=date(2018, 1, 1),
        )

    def walk_forward_config(self, *, start_date=date(2024, 1, 1), end_date=date(2024, 3, 31), frequency=WalkForwardReplayFrequency.MONTHLY):
        return WalkForwardReplayConfig(
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            signal_definition=self.signal_definition(),
            outcome_definition=self.outcome_definition(),
            overlap_policy=OverlappingSignalPolicy.ALLOW_ALL,
            historical_start_date=date(2018, 1, 1),
        )

    def outcome(self, status, symbol="TEST", signal_date=date(2024, 1, 31)):
        is_hit = status is OutcomeEvaluationStatus.HIT
        return HistoricalOutcomeResult(
            symbol=symbol,
            signal_id=self.signal_definition().id,
            signal_date=signal_date,
            outcome_definition_id=self.outcome_definition().id,
            status=status,
            horizon_bars=20,
            available_future_bars=20,
            reference_high=100.0,
            intraday_target_hit=is_hit,
            intraday_target_hit_date=date(2024, 2, 1) if is_hit else None,
            intraday_target_hit_bar_index=1 if is_hit else None,
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
            actual_signal_date=replay_date,
            post_replay_outcome=self.outcome(status, symbol=symbol, signal_date=replay_date),
            research_rank=rank,
        )

    def period(self, replay_date, candidates=tuple(), *, no_match_count=0, not_evaluable_count=0, failed_count=0):
        if failed_count:
            return WalkForwardReplayPeriod(
                requested_replay_date=replay_date,
                failure=RuntimeError("test failure"),
            )
        matched = {candidate.symbol for candidate in candidates}
        symbols = tuple(sorted(matched | {f"NO{i}" for i in range(no_match_count)}))
        return WalkForwardReplayPeriod(
            requested_replay_date=replay_date,
            replay_result=HistoricalReplayResult(
                config=self.replay_config(replay_date),
                requested_symbols=symbols,
                normalized_symbols=symbols,
                match_candidates=tuple(candidates),
                no_match_symbols=tuple(f"NO{i}" for i in range(no_match_count)),
                no_match_details=tuple(),
                not_evaluable_symbols=tuple(object() for _ in range(not_evaluable_count)),
                failed_symbols=tuple(object() for _ in range(failed_count)),
                generated_at=GENERATED_AT,
            ),
        )

    def result(self, periods, *, frequency=WalkForwardReplayFrequency.MONTHLY):
        replay_dates = tuple(period.requested_replay_date for period in periods)
        ordered_replay_dates = tuple(sorted(replay_dates))
        config = self.walk_forward_config(
            start_date=ordered_replay_dates[0] if ordered_replay_dates else date(2024, 1, 1),
            end_date=ordered_replay_dates[-1] if ordered_replay_dates else date(2024, 1, 1),
            frequency=frequency,
        )
        return WalkForwardReplayResult(
            config=config,
            requested_symbols=("AAPL", "MSFT"),
            normalized_symbols=("AAPL", "MSFT"),
            replay_dates=replay_dates,
            period_results=tuple(periods),
            summary=summarize_walk_forward_periods(tuple(periods)),
            generated_at=GENERATED_AT,
            walk_forward_id="walk_forward_test",
        )

    def analytics(self, periods, *, frequency=WalkForwardReplayFrequency.MONTHLY):
        return build_replay_analytics(self.result(periods, frequency=frequency))

    def test_empty_result(self):
        result = self.result(tuple())
        analytics = build_replay_analytics(result)

        self.assertEqual(analytics.stability_summary.total_period_count, 0)
        self.assertEqual(analytics.stability_summary.candidate_period_share, 0.0)
        self.assertEqual(analytics.period_summaries, tuple())
        self.assertEqual(analytics.symbol_summaries, tuple())

    def test_all_zero_match_periods_are_retained(self):
        analytics = self.analytics((
            self.period(date(2024, 1, 31), no_match_count=2),
            self.period(date(2024, 2, 29), no_match_count=2),
        ))

        self.assertEqual(analytics.stability_summary.total_period_count, 2)
        self.assertEqual(analytics.stability_summary.periods_with_candidates, 0)
        self.assertEqual(analytics.stability_summary.periods_without_candidates, 2)
        self.assertEqual([item.requested_replay_date for item in analytics.period_summaries], [date(2024, 1, 31), date(2024, 2, 29)])

    def test_single_candidate_occurrence_and_share(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        analytics = self.analytics((
            self.period(jan, no_match_count=2),
            self.period(feb, (self.candidate("AAPL", feb),), no_match_count=1),
        ))

        self.assertEqual(analytics.stability_summary.periods_with_candidates, 1)
        self.assertEqual(analytics.stability_summary.unique_candidate_symbols, 1)
        self.assertEqual(analytics.stability_summary.total_candidate_occurrences, 1)
        self.assertAlmostEqual(analytics.stability_summary.candidate_period_share, 0.5)
        self.assertEqual(analytics.symbol_summaries[0].candidate_period_share, 0.5)

    def test_repeated_consecutive_candidate_occurrence(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        mar = date(2024, 3, 31)
        analytics = self.analytics((
            self.period(jan, (self.candidate("AAPL", jan),)),
            self.period(feb, (self.candidate("AAPL", feb),)),
            self.period(mar, (self.candidate("AAPL", mar),)),
        ))

        summary = analytics.symbol_summaries[0]
        self.assertEqual(summary.candidate_occurrence_count, 3)
        self.assertEqual(summary.first_candidate_date, jan)
        self.assertEqual(summary.last_candidate_date, mar)
        self.assertEqual(summary.longest_consecutive_candidate_periods, 3)

    def test_non_consecutive_candidate_has_longest_one(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        mar = date(2024, 3, 31)
        analytics = self.analytics((
            self.period(jan, (self.candidate("AAPL", jan),)),
            self.period(feb),
            self.period(mar, (self.candidate("AAPL", mar),)),
        ))

        self.assertEqual(analytics.symbol_summaries[0].candidate_dates, (jan, mar))
        self.assertEqual(analytics.symbol_summaries[0].longest_consecutive_candidate_periods, 1)

    def test_weekly_sequence_uses_period_order_for_consecutive_behavior(self):
        jan_5 = date(2024, 1, 5)
        jan_12 = date(2024, 1, 12)
        jan_19 = date(2024, 1, 19)
        analytics = self.analytics((
            self.period(jan_5, (self.candidate("AAPL", jan_5),)),
            self.period(jan_12, (self.candidate("AAPL", jan_12),)),
            self.period(jan_19),
        ), frequency=WalkForwardReplayFrequency.WEEKLY)

        self.assertEqual(analytics.symbol_summaries[0].longest_consecutive_candidate_periods, 2)

    def test_monthly_sequence_uses_period_order_for_consecutive_behavior(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        analytics = self.analytics((
            self.period(jan, (self.candidate("AAPL", jan),)),
            self.period(feb, (self.candidate("AAPL", feb),)),
        ))

        self.assertEqual(analytics.symbol_summaries[0].longest_consecutive_candidate_periods, 2)

    def test_post_replay_outcome_distribution_counts_all_statuses(self):
        jan = date(2024, 1, 31)
        analytics = self.analytics((
            self.period(jan, (
                self.candidate("A", jan, OutcomeEvaluationStatus.HIT),
                self.candidate("B", jan, OutcomeEvaluationStatus.MISS),
                self.candidate("C", jan, OutcomeEvaluationStatus.INCOMPLETE),
                self.candidate("D", jan, OutcomeEvaluationStatus.NOT_EVALUABLE),
            )),
        ))

        distribution = analytics.post_replay_outcome_distribution
        self.assertEqual(distribution.post_replay_hit_count, 1)
        self.assertEqual(distribution.post_replay_miss_count, 1)
        self.assertEqual(distribution.post_replay_incomplete_count, 1)
        self.assertEqual(distribution.post_replay_not_evaluable_count, 1)
        self.assertEqual(distribution.resolved_post_replay_count, 2)

    def test_period_summary_keeps_zero_candidate_and_post_replay_counts(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        analytics = self.analytics((
            self.period(jan, no_match_count=2),
            self.period(feb, (self.candidate("AAPL", feb, OutcomeEvaluationStatus.MISS),), no_match_count=1),
        ))

        self.assertEqual(analytics.period_summaries[0].candidate_count, 0)
        self.assertEqual(analytics.period_summaries[0].candidate_symbols, tuple())
        self.assertEqual(analytics.period_summaries[1].post_replay_miss_count, 1)

    def test_jaccard_same_sets_disjoint_both_empty_and_empty_transitions(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        mar = date(2024, 3, 31)
        apr = date(2024, 4, 30)
        may = date(2024, 5, 31)
        analytics = self.analytics((
            self.period(jan, (self.candidate("A", jan),)),
            self.period(feb, (self.candidate("A", feb),)),
            self.period(mar, (self.candidate("B", mar),)),
            self.period(apr),
            self.period(may),
        ))

        transitions = analytics.stability_summary.candidate_set_transitions
        self.assertEqual((transitions[0].candidate_jaccard_similarity, transitions[0].candidate_turnover), (1.0, 0.0))
        self.assertEqual((transitions[1].candidate_jaccard_similarity, transitions[1].candidate_turnover), (0.0, 1.0))
        self.assertEqual((transitions[2].candidate_jaccard_similarity, transitions[2].candidate_turnover), (0.0, 1.0))
        self.assertEqual((transitions[3].candidate_jaccard_similarity, transitions[3].candidate_turnover), (1.0, 0.0))

    def test_non_empty_to_empty_transition(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        analytics = self.analytics((
            self.period(jan, (self.candidate("A", jan),)),
            self.period(feb),
        ))

        transition = analytics.stability_summary.candidate_set_transitions[0]
        self.assertEqual(transition.previous_candidate_count, 1)
        self.assertEqual(transition.current_candidate_count, 0)
        self.assertEqual(transition.candidate_turnover, 1.0)

    def test_deterministic_ordering(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        mar = date(2024, 3, 31)
        analytics = self.analytics((
            self.period(mar, (self.candidate("B", mar, rank=2),)),
            self.period(jan, (self.candidate("A", jan, rank=2), self.candidate("B", jan, rank=1))),
            self.period(feb, (self.candidate("A", feb, rank=1), self.candidate("B", feb, rank=2))),
        ))

        self.assertEqual([item.symbol for item in analytics.symbol_summaries], ["B", "A"])
        self.assertEqual(
            [(item.requested_replay_date, item.research_priority_rank, item.symbol) for item in analytics.candidate_occurrences],
            [(jan, 1, "B"), (jan, 2, "A"), (feb, 1, "A"), (feb, 2, "B"), (mar, 2, "B")],
        )

    def test_research_priority_history(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        mar = date(2024, 3, 31)
        analytics = self.analytics((
            self.period(jan, (self.candidate("AAPL", jan, rank=3),)),
            self.period(feb, (self.candidate("AAPL", feb, rank=1),)),
            self.period(mar, (self.candidate("AAPL", mar, rank=2),)),
        ))

        summary = analytics.symbol_summaries[0]
        self.assertEqual(summary.best_research_priority_rank, 1)
        self.assertEqual(summary.median_research_priority_rank, 2)
        self.assertEqual(summary.worst_research_priority_rank, 3)

    def test_occurrence_and_ranking_not_affected_by_outcome_mutation(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        base_candidate = self.candidate("AAPL", jan, OutcomeEvaluationStatus.HIT, rank=1)
        mutated_candidate = replace(
            base_candidate,
            post_replay_outcome=self.outcome(OutcomeEvaluationStatus.MISS, symbol="AAPL", signal_date=jan),
        )
        base = self.analytics((self.period(jan, (base_candidate,)), self.period(feb)))
        mutated = self.analytics((self.period(jan, (mutated_candidate,)), self.period(feb)))

        self.assertEqual(base.symbol_summaries[0].candidate_occurrence_count, mutated.symbol_summaries[0].candidate_occurrence_count)
        self.assertEqual(base.symbol_summaries[0].candidate_dates, mutated.symbol_summaries[0].candidate_dates)
        self.assertEqual(base.symbol_summaries[0].candidate_period_share, mutated.symbol_summaries[0].candidate_period_share)
        self.assertEqual(base.symbol_summaries[0].longest_consecutive_candidate_periods, mutated.symbol_summaries[0].longest_consecutive_candidate_periods)
        self.assertEqual(base.candidate_occurrences[0].research_priority_rank, mutated.candidate_occurrences[0].research_priority_rank)
        self.assertNotEqual(
            base.post_replay_outcome_distribution.post_replay_hit_count,
            mutated.post_replay_outcome_distribution.post_replay_hit_count,
        )

    def test_service_has_no_provider_replay_or_backtest_hooks(self):
        service = ReplayAnalyticsService()

        self.assertFalse(hasattr(service, "price_loader"))
        self.assertFalse(hasattr(service, "replay_service"))
        self.assertFalse(hasattr(service, "backtest_runner"))

    def test_no_probability_or_recommendation_fields(self):
        field_names = {
            field.name
            for model in (
                ReplayAnalyticsResult,
                ReplayStabilitySummary,
                ReplayPeriodSummary,
                ReplayCandidateOccurrence,
                ReplaySymbolSummary,
            )
            for field in fields(model)
        }
        banned_terms = ("probability", "recommendation", "prediction", "confidence", "win_rate", "success_rate")

        self.assertFalse(any(term in field_name for term in banned_terms for field_name in field_names))


if __name__ == "__main__":
    unittest.main()
