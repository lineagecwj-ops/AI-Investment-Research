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
from scanner_condition_coverage_phase2_robustness_service import SELECTED_MISSING_CONDITION_IDS
from scanner_condition_coverage_phase2_robustness_service import analyze_phase2_robustness
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1


GENERATED_AT = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
ALL_CONDITIONS = (
    "analysis_close_vs_sma_20",
    "sma_20_vs_sma_60",
    "volume_ratio_20",
    "rsi_14",
    "distance_to_prior_60d_high",
)


@dataclass(frozen=True)
class FakeObservation:

    symbol: str

    trading_date: date

    missing_condition_ids: tuple[str, ...]

    status: OutcomeEvaluationStatus

    rsi_14: float = 80.0

    volume_ratio_20: float = 1.0

    distance_to_prior_60d_high: float = -0.10

    signal_definition_id: str = TECHNICAL_EXAMPLE_SIGNAL_V1.id

    outcome_definition_id: str = RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id

    total_condition_count: int = 5

    @property
    def matched_condition_count(self):
        return self.total_condition_count - len(self.missing_condition_ids)

    @property
    def passed_condition_ids(self):
        return tuple(condition_id for condition_id in ALL_CONDITIONS if condition_id not in self.missing_condition_ids)

    @property
    def diagnostic_observation(self):
        return SimpleNamespace(
            source_snapshot=SimpleNamespace(
                rsi_14=self.rsi_14,
                volume_ratio_20=self.volume_ratio_20,
                distance_to_prior_60d_high=self.distance_to_prior_60d_high,
            )
        )

    @property
    def outcome(self):
        return HistoricalOutcomeResult(
            symbol=self.symbol,
            signal_id=self.signal_definition_id,
            signal_date=self.trading_date,
            outcome_definition_id=self.outcome_definition_id,
            status=self.status,
            horizon_bars=20,
            available_future_bars=20,
            reference_high=100.0,
            intraday_target_hit=self.status is OutcomeEvaluationStatus.HIT,
            intraday_target_hit_date=None,
            intraday_target_hit_bar_index=1 if self.status is OutcomeEvaluationStatus.HIT else None,
            close_target_hit=False,
            close_target_hit_date=None,
            close_target_hit_bar_index=None,
            max_close_return=None,
            max_close_return_date=None,
            max_adverse_return=None,
            max_adverse_return_date=None,
            end_of_window_return=None,
        )


def obs(symbol, trading_date, missing, status=OutcomeEvaluationStatus.HIT, **metrics):
    return FakeObservation(
        symbol=symbol,
        trading_date=trading_date,
        missing_condition_ids=tuple(missing),
        status=status,
        **metrics,
    )


class ScannerConditionCoveragePhase2RobustnessServiceTestCase(unittest.TestCase):

    def observations(self):
        return (
            obs("AAA", date(2018, 1, 2), ("rsi_14",), OutcomeEvaluationStatus.HIT, rsi_14=75.0),
            obs("AAA", date(2018, 1, 3), ("rsi_14",), OutcomeEvaluationStatus.MISS, rsi_14=45.0),
            obs("AAA", date(2018, 2, 1), (), OutcomeEvaluationStatus.HIT, rsi_14=60.0, volume_ratio_20=1.3, distance_to_prior_60d_high=-0.01),
            obs("AAA", date(2018, 3, 1), ("rsi_14",), OutcomeEvaluationStatus.HIT, rsi_14=80.0),
            obs("BBB", date(2024, 1, 2), ("volume_ratio_20",), OutcomeEvaluationStatus.HIT, volume_ratio_20=1.05),
            obs("BBB", date(2024, 1, 3), ("volume_ratio_20",), OutcomeEvaluationStatus.MISS, volume_ratio_20=1.15),
            obs("CCC", date(2025, 1, 2), ("distance_to_prior_60d_high",), OutcomeEvaluationStatus.HIT, distance_to_prior_60d_high=-0.08),
            obs("CCC", date(2025, 1, 3), ("distance_to_prior_60d_high",), OutcomeEvaluationStatus.MISS, distance_to_prior_60d_high=-0.20),
        )

    def readiness(self):
        return {"AAA": "FULL_WINDOW_ELIGIBLE", "BBB": "PARTIAL_WINDOW_VALID", "CCC": "FULL_WINDOW_ELIGIBLE"}

    def result(self):
        return analyze_phase2_robustness(
            self.observations(),
            generated_at=GENERATED_AT,
            readiness_by_symbol=self.readiness(),
            readiness_counts={"FULL_WINDOW_ELIGIBLE": 2, "PARTIAL_WINDOW_VALID": 1, "DATA_QUALITY_BLOCKED": 0},
        )

    def test_selected_groups_are_exactly_phase2_scope_and_daily_counts_reconcile(self):
        payload = self.result().payload

        self.assertEqual(tuple(payload["groups"]), SELECTED_MISSING_CONDITION_IDS)
        self.assertEqual(payload["groups"]["rsi_14"]["daily"]["observation_count"], 3)
        self.assertEqual(payload["groups"]["volume_ratio_20"]["daily"]["observation_count"], 2)
        self.assertEqual(payload["groups"]["distance_to_prior_60d_high"]["daily"]["observation_count"], 2)

    def test_de_overlap_reuses_symbol_spacing_and_is_deterministic(self):
        first = self.result()
        second = self.result()
        rsi = first.payload["groups"]["rsi_14"]

        self.assertEqual(rsi["reduced"]["observation_count"], 1)
        self.assertEqual(rsi["reduced"]["retained_observation_ratio"], 1 / 3)
        self.assertEqual(first.checksum, second.checksum)

    def test_full_partial_year_and_subperiod_reconcile(self):
        payload = self.result().payload
        volume = payload["groups"]["volume_ratio_20"]
        distance = payload["groups"]["distance_to_prior_60d_high"]

        self.assertEqual(volume["full_partial"]["daily"]["PARTIAL_WINDOW_VALID"]["observation_count"], 2)
        self.assertEqual(distance["full_partial"]["daily"]["FULL_WINDOW_ELIGIBLE"]["observation_count"], 2)
        for condition_id, group in payload["groups"].items():
            daily_n = group["daily"]["observation_count"]
            self.assertEqual(sum(row["observation_count"] for row in group["year_breakdown"]), daily_n, condition_id)
            self.assertEqual(sum(row["observation_count"] for row in group["subperiod_breakdown"]), daily_n, condition_id)

    def test_symbol_concentration_denominators_and_monotonic_top_shares(self):
        rsi = self.result().payload["groups"]["rsi_14"]
        concentration = rsi["symbol_concentration"]

        self.assertEqual(concentration["top_1_symbol_share"], 1.0)
        self.assertLessEqual(concentration["top_1_symbol_share"], concentration["top_5_symbol_share"])
        self.assertLessEqual(concentration["top_5_symbol_share"], concentration["top_10_symbol_share"])
        self.assertLessEqual(concentration["top_10_symbol_share"], 1.0)

    def test_first_events_use_not_in_group_to_in_group_transitions_and_reuse_outcome(self):
        rsi = self.result().payload["groups"]["rsi_14"]

        self.assertEqual(rsi["first_event"]["observation_count"], 2)
        self.assertEqual(rsi["first_event"]["hit_count"], 2)
        self.assertEqual(rsi["first_event"]["miss_count"], 0)
        self.assertEqual(rsi["event_subperiod_breakdown"][0]["observation_count"], 2)

    def test_rsi_volume_and_distance_deep_audits(self):
        payload = self.result().payload
        rsi = payload["groups"]["rsi_14"]["deep_audit"]
        volume = payload["groups"]["volume_ratio_20"]["volume_subgroups"]
        distance = payload["groups"]["distance_to_prior_60d_high"]["deep_audit"]

        self.assertEqual(rsi["fail_below"]["observation_count"], 1)
        self.assertEqual(rsi["fail_above"]["observation_count"], 2)
        self.assertEqual(rsi["failed_value_distribution"]["count"], 3)
        self.assertEqual(volume["volume_lt_1_10"]["daily"]["observation_count"], 1)
        self.assertEqual(volume["volume_1_10_to_lt_1_20"]["daily"]["observation_count"], 1)
        self.assertTrue(payload["groups"]["volume_ratio_20"]["v1_1_identity"]["identity_match"])
        self.assertEqual(distance["failed_value_distribution"]["count"], 2)

    def test_input_observations_are_not_mutated(self):
        observations = self.observations()
        before = tuple((item.symbol, item.trading_date, item.missing_condition_ids, item.status) for item in observations)

        analyze_phase2_robustness(
            observations,
            generated_at=GENERATED_AT,
            readiness_by_symbol=self.readiness(),
        )

        self.assertEqual(before, tuple((item.symbol, item.trading_date, item.missing_condition_ids, item.status) for item in observations))


if __name__ == "__main__":
    unittest.main()
