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
from scanner_condition_coverage_outcome_research_service import CANONICAL_CONDITION_IDS
from scanner_condition_coverage_outcome_research_service import ConditionCoverageOutcomeStudyError
from scanner_condition_coverage_outcome_research_service import V1_DAILY_BASELINE_HHR
from scanner_condition_coverage_outcome_research_service import V1_DAILY_BASELINE_HIT
from scanner_condition_coverage_outcome_research_service import V1_DAILY_BASELINE_MISS
from scanner_condition_coverage_outcome_research_service import V1_DAILY_BASELINE_N
from scanner_condition_coverage_outcome_research_service import _control_reconciled
from scanner_condition_coverage_outcome_research_service import analyze_condition_coverage_outcomes
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1


GENERATED_AT = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)


@dataclass(frozen=True)
class FakeObservation:

    symbol: str

    trading_date: date

    matched_condition_count: int

    passed_condition_ids: tuple[str, ...]

    missing_condition_ids: tuple[str, ...]

    status: OutcomeEvaluationStatus

    volume_ratio_20: float

    source_observation_id: str = "fake"

    signal_definition_id: str = TECHNICAL_EXAMPLE_SIGNAL_V1.id

    outcome_definition_id: str = RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id

    total_condition_count: int = 5

    @property
    def diagnostic_observation(self):
        return SimpleNamespace(source_snapshot=SimpleNamespace(volume_ratio_20=self.volume_ratio_20))

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


def obs(symbol, trading_date, missing, status=OutcomeEvaluationStatus.HIT, volume_ratio_20=1.3):
    missing = tuple(missing)
    passed = tuple(condition_id for condition_id in CANONICAL_CONDITION_IDS if condition_id not in missing)
    return FakeObservation(
        source_observation_id=f"{symbol}-{trading_date.isoformat()}",
        symbol=symbol,
        trading_date=trading_date,
        matched_condition_count=len(passed),
        passed_condition_ids=passed,
        missing_condition_ids=missing,
        status=status,
        volume_ratio_20=volume_ratio_20,
    )


class ScannerConditionCoverageOutcomeResearchServiceTestCase(unittest.TestCase):

    def sample_observations(self):
        return (
            obs("AAA", date(2018, 1, 2), (), OutcomeEvaluationStatus.HIT),
            obs("AAA", date(2019, 1, 2), (), OutcomeEvaluationStatus.MISS),
            obs("BBB", date(2024, 1, 2), ("volume_ratio_20",), OutcomeEvaluationStatus.HIT, 1.05),
            obs("BBB", date(2025, 1, 2), ("volume_ratio_20",), OutcomeEvaluationStatus.MISS, 1.15),
            obs("CCC", date(2025, 1, 3), ("rsi_14",), OutcomeEvaluationStatus.HIT),
            obs("DDD", date(2025, 1, 4), ("volume_ratio_20", "rsi_14"), OutcomeEvaluationStatus.HIT, 1.0),
            obs(
                "EEE",
                date(2025, 1, 5),
                ("sma_20_vs_sma_60", "distance_to_prior_60d_high"),
                OutcomeEvaluationStatus.MISS,
            ),
        )

    def test_exact_coverage_buckets_do_not_overlap_and_reconcile_groups(self):
        result = analyze_condition_coverage_outcomes(self.sample_observations(), generated_at=GENERATED_AT)
        overall = {row.coverage_count: row for row in result.overall}

        self.assertEqual(overall[5].observation_count, 2)
        self.assertEqual(overall[4].observation_count, 3)
        self.assertEqual(overall[3].observation_count, 2)
        self.assertEqual(sum(row.observation_count for row in result.missing_condition_4_of_5), overall[4].observation_count)
        self.assertEqual(sum(row.observation_count for row in result.missing_pairs_3_of_5), overall[3].observation_count)

    def test_missing_signatures_and_volume_subgroups_are_deterministic(self):
        result = analyze_condition_coverage_outcomes(self.sample_observations(), generated_at=GENERATED_AT)

        self.assertEqual(
            [row.missing_signature for row in result.missing_condition_4_of_5],
            [
                "MISSING_analysis_close_vs_sma_20",
                "MISSING_sma_20_vs_sma_60",
                "MISSING_volume_ratio_20",
                "MISSING_rsi_14",
                "MISSING_distance_to_prior_60d_high",
            ],
        )
        volume_rows = {row.missing_signature: row for row in result.volume_subgroups_4_of_5}
        self.assertEqual(volume_rows["MISSING_volume_ratio_20__volume_lt_1_10"].observation_count, 1)
        self.assertEqual(volume_rows["MISSING_volume_ratio_20__volume_1_10_to_lt_1_20"].observation_count, 1)
        self.assertTrue(result.v1_1_incremental_consistency.identity_match)
        self.assertEqual(
            [row.missing_signature for row in result.missing_pairs_3_of_5],
            [
                "MISSING_sma_20_vs_sma_60+distance_to_prior_60d_high",
                "MISSING_volume_ratio_20+rsi_14",
            ],
        )

    def test_zero_year_hhr_is_none_and_periods_reconcile_overall(self):
        result = analyze_condition_coverage_outcomes(self.sample_observations(), generated_at=GENERATED_AT)
        year_rows = {
            (row.period, row.coverage_count): row
            for row in result.year_breakdown
        }

        self.assertEqual(year_rows[("2020", 5)].observation_count, 0)
        self.assertIsNone(year_rows[("2020", 5)].hhr)
        for coverage in (5, 4, 3):
            self.assertEqual(
                sum(row.observation_count for row in result.year_breakdown if row.coverage_count == coverage),
                next(row.observation_count for row in result.overall if row.coverage_count == coverage),
            )
            self.assertEqual(
                sum(row.observation_count for row in result.subperiod_breakdown if row.coverage_count == coverage),
                next(row.observation_count for row in result.overall if row.coverage_count == coverage),
            )

    def test_sample_flags_and_concentration_metrics(self):
        result = analyze_condition_coverage_outcomes(self.sample_observations(), generated_at=GENERATED_AT)
        self.assertTrue(all(row.sample_flag == "VERY_SMALL_SAMPLE" for row in result.overall))

        concentration_3 = next(row for row in result.concentration if row.coverage_count == 3)
        self.assertEqual(concentration_3.unique_symbols, 2)
        self.assertEqual(concentration_3.top_1_symbol_share, 0.5)
        self.assertEqual(concentration_3.year_2025_share, 1.0)

    def test_rejects_overlapping_daily_identity_and_volume_inconsistency(self):
        duplicate = (
            obs("AAA", date(2025, 1, 1), ()),
            obs("AAA", date(2025, 1, 1), ()),
        )
        with self.assertRaisesRegex(ConditionCoverageOutcomeStudyError, "unique"):
            analyze_condition_coverage_outcomes(duplicate, generated_at=GENERATED_AT)

        inconsistent = (
            obs("AAA", date(2025, 1, 1), ("volume_ratio_20",), volume_ratio_20=1.2),
        )
        with self.assertRaisesRegex(ConditionCoverageOutcomeStudyError, "volume_ratio_20 >= 1.20"):
            analyze_condition_coverage_outcomes(inconsistent, generated_at=GENERATED_AT)

    def test_result_is_deterministic_and_does_not_mutate_observations(self):
        observations = self.sample_observations()
        before = tuple((item.passed_condition_ids, item.missing_condition_ids, item.status) for item in observations)

        first = analyze_condition_coverage_outcomes(observations, generated_at=GENERATED_AT)
        second = analyze_condition_coverage_outcomes(observations, generated_at=GENERATED_AT)

        self.assertEqual(first.checksum, second.checksum)
        self.assertEqual(before, tuple((item.passed_condition_ids, item.missing_condition_ids, item.status) for item in observations))

    def test_control_reconciliation_uses_phase_7_daily_baseline(self):
        baseline_observations = tuple(
            obs(f"S{index:04d}", date(2025, 1, 1), (), OutcomeEvaluationStatus.HIT)
            for index in range(V1_DAILY_BASELINE_HIT)
        ) + tuple(
            obs(f"M{index:04d}", date(2025, 1, 2), (), OutcomeEvaluationStatus.MISS)
            for index in range(V1_DAILY_BASELINE_MISS)
        )
        result = analyze_condition_coverage_outcomes(baseline_observations, generated_at=GENERATED_AT)
        row = next(row for row in result.overall if row.coverage_count == 5)

        self.assertEqual(row.observation_count, V1_DAILY_BASELINE_N)
        self.assertAlmostEqual(row.hhr, V1_DAILY_BASELINE_HHR)
        self.assertTrue(_control_reconciled(result))


if __name__ == "__main__":
    unittest.main()
