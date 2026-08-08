import sys
import unittest
from dataclasses import dataclass
from dataclasses import fields
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
from out_of_sample_validation_service import OutOfSampleValidationConfig
from out_of_sample_validation_service import OutOfSampleValidationError
from out_of_sample_validation_service import OutOfSampleValidationResult
from out_of_sample_validation_service import OutOfSampleValidationService
from out_of_sample_validation_service import ValidationPeriod
from out_of_sample_validation_service import ValidationPeriodRole
from out_of_sample_validation_service import build_research_fingerprint
from walk_forward_replay_service import WalkForwardReplayFrequency


FETCHED_AT = datetime(2026, 8, 8, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 8, 2, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CandidateStub:

    symbol: str

    requested_replay_date: date

    actual_signal_date: date

    post_replay_outcome: HistoricalOutcomeResult

    research_rank: int | None = None


class RecordingPriceLoader:

    def __init__(self, fail_symbols=()):
        self.calls = []
        self.fail_symbols = set(fail_symbols)

    def __call__(self, symbol, *, force_refresh=False):
        self.calls.append((symbol, force_refresh))
        if symbol in self.fail_symbols:
            raise RuntimeError(f"provider failed for {symbol}")
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

    def __init__(self, candidate_plan=None):
        self.calls = []
        self.candidate_plan = candidate_plan or {}

    def replay_scan(self, symbols, config, *, price_series_by_symbol=None):
        self.calls.append((tuple(symbols), config, price_series_by_symbol))
        candidates = tuple(self.candidate_plan.get(config.replay_date, tuple()))
        matched_symbols = {candidate.symbol for candidate in candidates}
        no_match_symbols = tuple(symbol for symbol in symbols if symbol not in matched_symbols)
        return HistoricalReplayResult(
            config=config,
            requested_symbols=tuple(symbols),
            normalized_symbols=tuple(symbols),
            match_candidates=candidates,
            no_match_symbols=no_match_symbols,
            no_match_details=tuple(),
            not_evaluable_symbols=tuple(),
            failed_symbols=tuple(),
            generated_at=GENERATED_AT,
        )


class OutOfSampleValidationServiceTestCase(unittest.TestCase):

    def signal_definition(self, *, condition_value=100.0):
        return SignalDefinition(
            id="technical_example_v1",
            name="Technical Example",
            conditions=(
                TechnicalSignalCondition(
                    metric="analysis_close",
                    operator=SignalConditionOperator.GREATER_THAN,
                    value=condition_value,
                ),
            ),
            minimum_required_features=("analysis_close",),
            description="Test signal.",
        )

    def outcome_definition(self, *, horizon=20):
        return OutcomeDefinition(
            id="raw_high_breakout_60d_within_20d_v1",
            outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
            horizon_bars=horizon,
            reference_metric="prior_high_60d",
        )

    def period(self, role, start_date, end_date):
        return ValidationPeriod(role=role, start_date=start_date, end_date=end_date)

    def config(self, **overrides):
        values = {
            "signal_definition": self.signal_definition(),
            "outcome_definition": self.outcome_definition(),
            "development_period": self.period(ValidationPeriodRole.DEVELOPMENT, date(2024, 1, 1), date(2024, 1, 31)),
            "validation_period": self.period(ValidationPeriodRole.VALIDATION, date(2024, 2, 1), date(2024, 2, 29)),
            "holdout_period": self.period(ValidationPeriodRole.HOLDOUT, date(2024, 3, 1), date(2024, 3, 31)),
            "replay_frequency": WalkForwardReplayFrequency.MONTHLY,
            "overlap_policy": OverlappingSignalPolicy.ALLOW_ALL,
            "cooldown_bars": None,
            "historical_start_date": date(2018, 1, 1),
            "minimum_resolved_samples": 20,
        }
        values.update(overrides)
        return OutOfSampleValidationConfig(**values)

    def outcome(self, status, *, symbol="AAPL", signal_date=date(2024, 1, 31)):
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
            intraday_target_hit_date=signal_date if is_hit else None,
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

    def candidate(self, symbol, replay_date, status=OutcomeEvaluationStatus.HIT, rank=1):
        return CandidateStub(
            symbol=symbol,
            requested_replay_date=replay_date,
            actual_signal_date=replay_date,
            post_replay_outcome=self.outcome(status, symbol=symbol, signal_date=replay_date),
            research_rank=rank,
        )

    def run_validation(self, plan=None, *, loader=None, config=None, symbols=("AAPL", "MSFT")):
        replay_service = FakeReplayService(plan)
        price_loader = loader or RecordingPriceLoader()
        result = OutOfSampleValidationService(
            price_loader=price_loader,
            replay_service=replay_service,
        ).run_out_of_sample_validation(symbols, config or self.config())
        return result, price_loader, replay_service

    def test_valid_periods_accept_inclusive_non_overlapping_boundaries(self):
        config = self.config()

        self.assertEqual(config.development_period.end_date, date(2024, 1, 31))
        self.assertEqual(config.validation_period.start_date, date(2024, 2, 1))
        self.assertEqual(config.holdout_period.start_date, date(2024, 3, 1))

    def test_reversed_period_dates_are_rejected(self):
        with self.assertRaises(OutOfSampleValidationError):
            self.period(ValidationPeriodRole.DEVELOPMENT, date(2024, 2, 1), date(2024, 1, 1))

    def test_one_day_overlap_is_rejected_for_inclusive_boundaries(self):
        with self.assertRaises(OutOfSampleValidationError):
            self.config(
                development_period=self.period(ValidationPeriodRole.DEVELOPMENT, date(2024, 1, 1), date(2024, 2, 1)),
                validation_period=self.period(ValidationPeriodRole.VALIDATION, date(2024, 2, 1), date(2024, 2, 29)),
            )

    def test_missing_or_wrong_period_role_is_rejected(self):
        with self.assertRaises(OutOfSampleValidationError):
            self.config(
                development_period=self.period(ValidationPeriodRole.VALIDATION, date(2024, 1, 1), date(2024, 1, 31))
            )

    def test_development_after_validation_is_rejected(self):
        with self.assertRaises(OutOfSampleValidationError):
            self.config(
                development_period=self.period(ValidationPeriodRole.DEVELOPMENT, date(2024, 3, 1), date(2024, 3, 31)),
                validation_period=self.period(ValidationPeriodRole.VALIDATION, date(2024, 2, 1), date(2024, 2, 29)),
            )

    def test_validation_after_holdout_is_rejected(self):
        with self.assertRaises(OutOfSampleValidationError):
            self.config(
                validation_period=self.period(ValidationPeriodRole.VALIDATION, date(2024, 3, 1), date(2024, 3, 31)),
                holdout_period=self.period(ValidationPeriodRole.HOLDOUT, date(2024, 2, 1), date(2024, 2, 29)),
            )

    def test_deterministic_fingerprint_for_same_research_specification(self):
        spec_a = self.config().frozen_specification(generated_at=datetime(2024, 1, 1, tzinfo=UTC))
        spec_b = self.config().frozen_specification(generated_at=datetime(2025, 1, 1, tzinfo=UTC))

        self.assertEqual(build_research_fingerprint(spec_a), build_research_fingerprint(spec_b))

    def test_fingerprint_changes_when_relevant_setting_changes(self):
        base = self.config().frozen_specification()
        changed = self.config(minimum_resolved_samples=30).frozen_specification()

        self.assertNotEqual(base.fingerprint, changed.fingerprint)

    def test_fingerprint_changes_when_signal_threshold_changes_even_with_same_id(self):
        base = self.config().frozen_specification()
        changed = self.config(signal_definition=self.signal_definition(condition_value=101.0)).frozen_specification()

        self.assertNotEqual(base.fingerprint, changed.fingerprint)

    def test_development_validation_holdout_result_separation(self):
        plan = {
            date(2024, 1, 31): (self.candidate("AAPL", date(2024, 1, 31)),),
            date(2024, 2, 29): (self.candidate("MSFT", date(2024, 2, 29)),),
            date(2024, 3, 31): (self.candidate("NVDA", date(2024, 3, 31)),),
        }

        result, _, _ = self.run_validation(plan, symbols=("AAPL", "MSFT", "NVDA"))

        self.assertEqual(result.development_result.replay_dates, (date(2024, 1, 31),))
        self.assertEqual(result.validation_result.replay_dates, (date(2024, 2, 29),))
        self.assertEqual(result.holdout_result.replay_dates, (date(2024, 3, 31),))
        self.assertEqual(result.development_result.unique_candidate_symbols, 1)
        self.assertEqual(result.validation_result.unique_candidate_symbols, 1)
        self.assertEqual(result.holdout_result.unique_candidate_symbols, 1)

    def test_replay_dates_do_not_cross_period_boundaries(self):
        result, _, replay_service = self.run_validation()

        replay_dates = tuple(call[1].replay_date for call in replay_service.calls)
        self.assertEqual(replay_dates, (date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)))
        self.assertEqual(result.development_result.requested_replay_period_count, 1)

    def test_full_price_series_reused_across_all_periods(self):
        result, loader, replay_service = self.run_validation(symbols=("AAPL", "aapl", "MSFT"))

        self.assertEqual([call[0] for call in loader.calls], ["AAPL", "MSFT"])
        self.assertEqual(result.price_loader_call_count, 2)
        for _, _, cache in replay_service.calls:
            self.assertEqual(tuple(cache), ("AAPL", "MSFT"))

    def test_zero_candidate_period_is_safe(self):
        result, _, _ = self.run_validation()

        self.assertEqual(result.development_result.periods_with_candidates, 0)
        self.assertEqual(result.development_result.periods_without_candidates, 1)
        self.assertEqual(result.development_result.total_candidate_occurrences, 0)

    def test_zero_resolved_samples_have_no_fake_zero_hit_rate(self):
        plan = {
            date(2024, 1, 31): (
                self.candidate("AAPL", date(2024, 1, 31), OutcomeEvaluationStatus.INCOMPLETE),
            ),
        }

        result, _, _ = self.run_validation(plan)

        self.assertEqual(result.development_result.resolved_count, 0)
        self.assertIsNone(result.development_result.historical_hit_rate)

    def test_incomplete_and_not_evaluable_are_excluded_from_hit_rate_denominator(self):
        plan = {
            date(2024, 1, 31): (
                self.candidate("A", date(2024, 1, 31), OutcomeEvaluationStatus.HIT),
                self.candidate("B", date(2024, 1, 31), OutcomeEvaluationStatus.MISS),
                self.candidate("C", date(2024, 1, 31), OutcomeEvaluationStatus.INCOMPLETE),
                self.candidate("D", date(2024, 1, 31), OutcomeEvaluationStatus.NOT_EVALUABLE),
            ),
        }

        result, _, _ = self.run_validation(plan, symbols=("A", "B", "C", "D"))

        self.assertEqual(result.development_result.resolved_count, 2)
        self.assertEqual(result.development_result.post_replay_incomplete_count, 1)
        self.assertEqual(result.development_result.post_replay_not_evaluable_count, 1)
        self.assertEqual(result.development_result.historical_hit_rate, 0.5)

    def test_candidate_period_share_uses_period_count(self):
        config = self.config(
            development_period=self.period(ValidationPeriodRole.DEVELOPMENT, date(2024, 1, 1), date(2024, 2, 29)),
            validation_period=self.period(ValidationPeriodRole.VALIDATION, date(2024, 3, 1), date(2024, 3, 31)),
            holdout_period=self.period(ValidationPeriodRole.HOLDOUT, date(2024, 4, 1), date(2024, 4, 30)),
        )
        plan = {date(2024, 1, 31): (self.candidate("AAPL", date(2024, 1, 31)),)}

        result, _, _ = self.run_validation(plan, config=config)

        self.assertEqual(result.development_result.requested_replay_period_count, 2)
        self.assertEqual(result.development_result.candidate_period_share, 0.5)

    def test_period_local_replay_analytics_do_not_mix_candidate_history(self):
        plan = {
            date(2024, 1, 31): (self.candidate("AAPL", date(2024, 1, 31)),),
            date(2024, 3, 31): (self.candidate("NVDA", date(2024, 3, 31)),),
        }

        result, _, _ = self.run_validation(plan, symbols=("AAPL", "NVDA"))

        self.assertEqual(result.development_result.replay_analytics.symbol_summaries[0].symbol, "AAPL")
        self.assertEqual(result.holdout_result.replay_analytics.symbol_summaries[0].symbol, "NVDA")

    def test_holdout_outcome_mutation_does_not_alter_development_result(self):
        base_plan = {
            date(2024, 1, 31): (self.candidate("AAPL", date(2024, 1, 31), OutcomeEvaluationStatus.HIT),),
            date(2024, 3, 31): (self.candidate("NVDA", date(2024, 3, 31), OutcomeEvaluationStatus.HIT),),
        }
        mutated_plan = {
            date(2024, 1, 31): base_plan[date(2024, 1, 31)],
            date(2024, 3, 31): (self.candidate("NVDA", date(2024, 3, 31), OutcomeEvaluationStatus.MISS),),
        }

        base, _, _ = self.run_validation(base_plan, symbols=("AAPL", "NVDA"))
        mutated, _, _ = self.run_validation(mutated_plan, symbols=("AAPL", "NVDA"))

        self.assertEqual(base.development_result.replay_dates, mutated.development_result.replay_dates)
        self.assertEqual(base.development_result.total_candidate_occurrences, mutated.development_result.total_candidate_occurrences)
        self.assertEqual(base.development_result.post_replay_hit_count, mutated.development_result.post_replay_hit_count)
        self.assertEqual(base.development_result.research_fingerprint, mutated.development_result.research_fingerprint)
        self.assertNotEqual(base.holdout_result.post_replay_hit_count, mutated.holdout_result.post_replay_hit_count)

    def test_holdout_outcome_mutation_does_not_alter_validation_result(self):
        base_plan = {
            date(2024, 2, 29): (self.candidate("MSFT", date(2024, 2, 29), OutcomeEvaluationStatus.HIT),),
            date(2024, 3, 31): (self.candidate("NVDA", date(2024, 3, 31), OutcomeEvaluationStatus.HIT),),
        }
        mutated_plan = {
            date(2024, 2, 29): base_plan[date(2024, 2, 29)],
            date(2024, 3, 31): (self.candidate("NVDA", date(2024, 3, 31), OutcomeEvaluationStatus.MISS),),
        }

        base, _, _ = self.run_validation(base_plan, symbols=("MSFT", "NVDA"))
        mutated, _, _ = self.run_validation(mutated_plan, symbols=("MSFT", "NVDA"))

        self.assertEqual(base.validation_result.replay_dates, mutated.validation_result.replay_dates)
        self.assertEqual(base.validation_result.total_candidate_occurrences, mutated.validation_result.total_candidate_occurrences)
        self.assertEqual(base.validation_result.post_replay_hit_count, mutated.validation_result.post_replay_hit_count)
        self.assertEqual(base.validation_result.research_fingerprint, mutated.validation_result.research_fingerprint)
        self.assertNotEqual(base.holdout_result.post_replay_hit_count, mutated.holdout_result.post_replay_hit_count)

    def test_later_development_outcome_mutation_does_not_alter_earlier_replay_date_signal(self):
        config = self.config(
            development_period=self.period(ValidationPeriodRole.DEVELOPMENT, date(2024, 1, 1), date(2024, 2, 29)),
            validation_period=self.period(ValidationPeriodRole.VALIDATION, date(2024, 3, 1), date(2024, 3, 31)),
            holdout_period=self.period(ValidationPeriodRole.HOLDOUT, date(2024, 4, 1), date(2024, 4, 30)),
        )
        base_plan = {
            date(2024, 1, 31): (self.candidate("AAPL", date(2024, 1, 31), OutcomeEvaluationStatus.HIT),),
            date(2024, 2, 29): (self.candidate("MSFT", date(2024, 2, 29), OutcomeEvaluationStatus.HIT),),
        }
        mutated_plan = {
            date(2024, 1, 31): base_plan[date(2024, 1, 31)],
            date(2024, 2, 29): (self.candidate("MSFT", date(2024, 2, 29), OutcomeEvaluationStatus.MISS),),
        }

        base, _, _ = self.run_validation(base_plan, config=config, symbols=("AAPL", "MSFT"))
        mutated, _, _ = self.run_validation(mutated_plan, config=config, symbols=("AAPL", "MSFT"))

        base_first_period = base.development_result.replay_analytics.period_summaries[0]
        mutated_first_period = mutated.development_result.replay_analytics.period_summaries[0]
        self.assertEqual(base_first_period.candidate_symbols, ("AAPL",))
        self.assertEqual(base_first_period.candidate_symbols, mutated_first_period.candidate_symbols)
        self.assertEqual(base_first_period.post_replay_hit_count, mutated_first_period.post_replay_hit_count)

    def test_same_fixed_specification_across_all_periods(self):
        result, _, _ = self.run_validation()

        self.assertTrue(result.all_periods_same_fingerprint)
        self.assertEqual(result.development_result.research_fingerprint, result.research_fingerprint)
        self.assertEqual(result.validation_result.research_fingerprint, result.research_fingerprint)
        self.assertEqual(result.holdout_result.research_fingerprint, result.research_fingerprint)

    def test_no_optimization_or_recommendation_fields_exist(self):
        banned = ("optimization", "best_", "probability", "recommendation", "score", "position", "pnl", "p_l")
        names = {field.name.lower() for field in fields(OutOfSampleValidationConfig)}
        names |= {field.name.lower() for field in fields(OutOfSampleValidationResult)}

        self.assertFalse(any(any(term in name for term in banned) for name in names))

    def test_mixed_market_symbols_are_normalized_and_preserved(self):
        result, loader, _ = self.run_validation(symbols=("2330", "2454.TW", "NVDA", "6488.two"))

        self.assertEqual(result.normalized_symbols, ("2330.TW", "2454.TW", "NVDA", "6488.TWO"))
        self.assertEqual([call[0] for call in loader.calls], list(result.normalized_symbols))

    def test_provider_failure_is_isolated_without_repeated_refetch(self):
        loader = RecordingPriceLoader(fail_symbols=("MSFT",))

        result, loader, replay_service = self.run_validation(loader=loader, symbols=("AAPL", "MSFT"))

        self.assertEqual([call[0] for call in loader.calls], ["AAPL", "MSFT"])
        for _, _, cache in replay_service.calls:
            self.assertEqual(cache["MSFT"].bars, tuple())
            self.assertEqual(cache["MSFT"].source, "Provider failure")
        self.assertEqual(result.price_loader_call_count, 2)

    def test_deterministic_result_ordering(self):
        result, _, _ = self.run_validation()

        self.assertEqual(
            (
                result.development_result.role,
                result.validation_result.role,
                result.holdout_result.role,
            ),
            (
                ValidationPeriodRole.DEVELOPMENT,
                ValidationPeriodRole.VALIDATION,
                ValidationPeriodRole.HOLDOUT,
            ),
        )
        self.assertEqual(
            [item[0:2] for item in result.comparison.candidate_period_share_differences],
            [
                ("DEVELOPMENT", "VALIDATION"),
                ("VALIDATION", "HOLDOUT"),
                ("DEVELOPMENT", "HOLDOUT"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
