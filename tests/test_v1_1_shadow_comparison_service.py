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

from historical_condition_outcome_service import ConditionOutcomeObservation
from models import HistoricalOutcomeResult
from models import OutcomeEvaluationStatus
from models import TechnicalIndicatorSnapshot
from signal_condition_diagnostics_service import build_condition_diagnostic_observation
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL
from signal_outcome_service import evaluate_signal_conditions
from v1_1_shadow_comparison_service import EXPERIMENTAL_V1_1_VOLUME_THRESHOLD
from v1_1_shadow_comparison_service import PRODUCTION_V1_VOLUME_THRESHOLD
from v1_1_shadow_comparison_service import VOLUME_CONDITION_ID
from v1_1_shadow_comparison_service import V11ShadowComparisonObservation
from v1_1_shadow_comparison_service import compare_v1_v1_1_shadow_definitions


GENERATED_AT = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


class V11ShadowComparisonServiceTestCase(unittest.TestCase):

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
            volume_ratio_20=1.50,
            rsi_14=60.0,
            prior_high_60d=110.0,
            prior_low_60d=80.0,
            distance_to_prior_60d_high=-0.02,
        )
        params.update(overrides)
        return TechnicalIndicatorSnapshot(**params)

    def outcome(self, symbol, trading_date, status=OutcomeEvaluationStatus.HIT):
        return HistoricalOutcomeResult(
            symbol=symbol,
            signal_id=TECHNICAL_EXAMPLE_SIGNAL_V1.id,
            signal_date=trading_date,
            outcome_definition_id=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id,
            status=status,
            horizon_bars=20,
            available_future_bars=20,
            reference_high=110.0,
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

    def observation(self, symbol="AAA", trading_date=date(2025, 1, 1), status=OutcomeEvaluationStatus.HIT, **snapshot_overrides):
        snapshot = self.snapshot(symbol=symbol, trading_date=trading_date, **snapshot_overrides)
        signal_match = evaluate_signal_conditions(snapshot, TECHNICAL_EXAMPLE_SIGNAL_V1)
        diagnostic = build_condition_diagnostic_observation(signal_match)
        return ConditionOutcomeObservation(
            source_observation_id=f"{symbol}|{trading_date.isoformat()}",
            symbol=symbol,
            trading_date=trading_date,
            signal_definition_id=TECHNICAL_EXAMPLE_SIGNAL_V1.id,
            outcome_definition_id=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id,
            matched_condition_count=diagnostic.matched_condition_count,
            total_condition_count=diagnostic.total_condition_count,
            passed_condition_ids=diagnostic.passed_condition_ids,
            missing_condition_ids=diagnostic.missing_condition_ids,
            diagnostic_observation=diagnostic,
            outcome=self.outcome(symbol, trading_date, status),
        )

    def comparison_input(self, observations):
        return type(
            "ComparisonInput",
            (),
            {"outcome_observations": tuple(observations)},
        )()

    def volume_condition(self, signal_definition):
        matches = [
            condition for condition in signal_definition.conditions
            if condition.metric == VOLUME_CONDITION_ID
        ]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_definitions_keep_v1_authoritative_and_v1_1_experimental(self):
        self.assertEqual(TECHNICAL_EXAMPLE_SIGNAL_V1.id, "technical_example_v1")
        self.assertEqual(
            self.volume_condition(TECHNICAL_EXAMPLE_SIGNAL_V1).value,
            PRODUCTION_V1_VOLUME_THRESHOLD,
        )
        self.assertEqual(
            TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL.id,
            "technical_example_v1_1_experimental",
        )
        self.assertEqual(
            self.volume_condition(TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL).value,
            EXPERIMENTAL_V1_1_VOLUME_THRESHOLD,
        )
        self.assertNotEqual(
            TECHNICAL_EXAMPLE_SIGNAL_V1.id,
            TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL.id,
        )
        self.assertNotEqual(
            TECHNICAL_EXAMPLE_SIGNAL_V1.name,
            TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL.name,
        )
        self.assertIn("EXPERIMENTAL", TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL.description)
        self.assertIn("V1.1 實驗版", TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL.description)

    def test_other_four_conditions_and_required_features_are_identical(self):
        v1_other = tuple(
            condition for condition in TECHNICAL_EXAMPLE_SIGNAL_V1.conditions
            if condition.metric != VOLUME_CONDITION_ID
        )
        v1_1_other = tuple(
            condition for condition in TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL.conditions
            if condition.metric != VOLUME_CONDITION_ID
        )

        self.assertEqual(v1_other, v1_1_other)
        self.assertEqual(
            TECHNICAL_EXAMPLE_SIGNAL_V1.minimum_required_features,
            TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL.minimum_required_features,
        )

    def test_v1_subset_v1_1_and_incremental_interval(self):
        observations = (
            self.observation("AAA", date(2025, 1, 1), volume_ratio_20=1.20),
            self.observation("AAA", date(2025, 1, 2), volume_ratio_20=1.50),
            self.observation("BBB", date(2025, 1, 1), volume_ratio_20=1.10),
            self.observation("BBB", date(2025, 1, 2), volume_ratio_20=1.19),
            self.observation("CCC", date(2025, 1, 1), volume_ratio_20=1.09),
            self.observation("DDD", date(2025, 1, 1), analysis_close=80.0, volume_ratio_20=1.50),
        )

        result = compare_v1_v1_1_shadow_definitions(
            self.comparison_input(observations),
            generated_at=GENERATED_AT,
        )

        self.assertEqual(result.generated_at, GENERATED_AT)
        self.assertEqual(result.summary.v1_observation_count, 2)
        self.assertEqual(result.summary.v1_1_observation_count, 4)
        self.assertEqual(result.summary.shared_observation_count, 2)
        self.assertEqual(result.summary.added_observation_count, 2)
        self.assertTrue(all(
            not observation.v1_qualified or observation.v1_1_qualified
            for observation in result.observations
        ))
        incremental = tuple(
            observation for observation in result.observations
            if observation.is_v1_1_only_observation
        )
        self.assertEqual(
            tuple(getattr(item.source_observation.diagnostic_observation.source_snapshot, VOLUME_CONDITION_ID) for item in incremental),
            (1.10, 1.19),
        )

    def test_shared_observations_reuse_the_same_attached_outcome(self):
        observation = self.observation("AAA", date(2025, 1, 1), volume_ratio_20=1.20)

        result = compare_v1_v1_1_shadow_definitions(
            self.comparison_input((observation,)),
            generated_at=GENERATED_AT,
        )

        shared = result.observations[0]
        self.assertTrue(shared.is_shared_observation)
        self.assertIs(shared.v1_outcome, observation.outcome)
        self.assertIs(shared.v1_1_outcome, observation.outcome)
        self.assertEqual(
            shared.signal_definition_ids,
            (
                TECHNICAL_EXAMPLE_SIGNAL_V1.id,
                TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL.id,
            ),
        )

    def test_no_recommendation_rank_score_or_probability_fields_are_added(self):
        forbidden = ("rank", "score", "winner", "recommendation", "probability", "confidence")
        field_names = tuple(V11ShadowComparisonObservation.__dataclass_fields__)

        for forbidden_fragment in forbidden:
            with self.subTest(forbidden_fragment=forbidden_fragment):
                self.assertFalse(any(forbidden_fragment in field_name for field_name in field_names))

    def test_app_defaults_still_reference_formal_v1_only(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1", app_source)
        self.assertNotIn("TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL", app_source)


if __name__ == "__main__":
    unittest.main()
