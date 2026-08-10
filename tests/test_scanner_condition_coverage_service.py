import sys
import unittest
from dataclasses import fields
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import OverlappingSignalPolicy
from models import SignalEvaluationStatus
from models import TechnicalIndicatorSnapshot
from scanner_condition_coverage_service import ConditionCoverageClassification
from scanner_condition_coverage_service import ScannerConditionCoverageError
from scanner_condition_coverage_service import ScannerConditionCoverageResult
from scanner_condition_coverage_service import build_scanner_condition_coverage_result
from scanner_condition_coverage_service import build_scanner_condition_coverage_summary
from scanner_condition_coverage_service import missing_condition_signature
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import evaluate_signal_conditions
from swing_scanner_service import SwingScannerConfig


GENERATED_AT = datetime(2026, 8, 10, 2, 0, tzinfo=UTC)


class ScannerConditionCoverageServiceTestCase(unittest.TestCase):

    def snapshot(self, symbol="2330.TW", trading_date=date(2026, 8, 10), **overrides):
        values = {
            field.name: None
            for field in fields(TechnicalIndicatorSnapshot)
        }
        values.update(
            symbol=symbol,
            trading_date=trading_date,
            analysis_close=110.0,
            sma_20=100.0,
            sma_60=90.0,
            volume_ratio_20=1.20,
            rsi_14=60.0,
            distance_to_prior_60d_high=-0.02,
            prior_high_60d=115.0,
            prior_low_60d=80.0,
        )
        values.update(overrides)
        return TechnicalIndicatorSnapshot(**values)

    def signal_match(self, **snapshot_overrides):
        return evaluate_signal_conditions(
            self.snapshot(**snapshot_overrides),
            TECHNICAL_EXAMPLE_SIGNAL_V1,
        )

    def coverage(self, **snapshot_overrides):
        return build_scanner_condition_coverage_result(
            self.signal_match(**snapshot_overrides),
            production_signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
        )

    def config(self):
        return SwingScannerConfig(
            signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
            outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
            overlap_policy=OverlappingSignalPolicy.ALLOW_ALL,
            minimum_resolved_samples=0,
        )

    def scanner_result(self, signal_matches, matched_symbols):
        return SimpleNamespace(
            config=self.config(),
            current_signal_details=tuple(signal_matches),
            matched_candidates=tuple(SimpleNamespace(symbol=symbol) for symbol in matched_symbols),
            generated_at=GENERATED_AT,
        )

    def test_classifies_5_4_3_2_and_0_condition_coverage(self):
        cases = (
            (self.coverage(symbol="FIVE"), 5, ConditionCoverageClassification.FORMAL_V1_MATCH),
            (self.coverage(symbol="FOUR", volume_ratio_20=1.10), 4, ConditionCoverageClassification.NEAR_MATCH),
            (self.coverage(symbol="THREE", volume_ratio_20=1.10, rsi_14=72.0), 3, ConditionCoverageClassification.EXPLORATORY),
            (self.coverage(symbol="TWO", volume_ratio_20=1.10, rsi_14=72.0, analysis_close=90.0), 2, ConditionCoverageClassification.BELOW_DISPLAY_THRESHOLD),
            (
                self.coverage(
                    symbol="ZERO",
                    volume_ratio_20=1.10,
                    rsi_14=72.0,
                    analysis_close=70.0,
                    sma_20=80.0,
                    distance_to_prior_60d_high=-0.08,
                ),
                0,
                ConditionCoverageClassification.BELOW_DISPLAY_THRESHOLD,
            ),
        )
        for result, expected_count, expected_classification in cases:
            self.assertEqual(result.matched_condition_count, expected_count)
            self.assertEqual(result.total_condition_count, 5)
            self.assertEqual(result.coverage_label, f"{expected_count}/5")
            self.assertIs(result.classification, expected_classification)

    def test_missing_ids_and_signature_are_exact_and_deterministic(self):
        missing_volume = self.coverage(symbol="VOL", volume_ratio_20=1.10)
        missing_rsi = self.coverage(symbol="RSI", rsi_14=72.0)
        missing_two = self.coverage(symbol="TWO", volume_ratio_20=1.10, rsi_14=72.0)

        self.assertEqual(missing_volume.missing_condition_ids, ("volume_ratio_20",))
        self.assertEqual(missing_volume.missing_condition_signature, "MISSING_volume_ratio_20")
        self.assertEqual(missing_rsi.missing_condition_ids, ("rsi_14",))
        self.assertEqual(missing_two.missing_condition_ids, ("volume_ratio_20", "rsi_14"))
        self.assertEqual(
            missing_condition_signature(missing_two.missing_condition_ids),
            "MISSING_volume_ratio_20+rsi_14",
        )

    def test_formal_v1_identity_matches_scanner_hits(self):
        formal = self.signal_match(symbol="2330.TW")
        near = self.signal_match(symbol="2368.TW", volume_ratio_20=1.10)
        summary = build_scanner_condition_coverage_summary(
            self.scanner_result((formal, near), matched_symbols=("2330.TW",)),
            production_signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
        )

        self.assertEqual(summary.formal_v1_match_symbols, ("2330.TW",))
        self.assertEqual(summary.near_match_symbols, ("2368.TW",))
        self.assertEqual(summary.formal_v1_match_count, 1)
        self.assertEqual(summary.near_match_count, 1)
        self.assertEqual(summary.evaluated_symbol_count, 2)

    def test_formal_v1_identity_violation_is_blocking(self):
        formal = self.signal_match(symbol="2330.TW")

        with self.assertRaises(ScannerConditionCoverageError):
            build_scanner_condition_coverage_summary(
                self.scanner_result((formal,), matched_symbols=tuple()),
                production_signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
            )

    def test_v1_1_badge_uses_experimental_definition_without_changing_coverage(self):
        lower = self.coverage(symbol="LOWER", volume_ratio_20=1.10)
        upper = self.coverage(symbol="UPPER", volume_ratio_20=1.199999)
        production = self.coverage(symbol="V1", volume_ratio_20=1.20)
        below = self.coverage(symbol="BELOW", volume_ratio_20=1.099999)

        self.assertTrue(lower.v1_1_experimental_match)
        self.assertTrue(upper.v1_1_experimental_match)
        self.assertFalse(production.v1_1_experimental_match)
        self.assertEqual(production.coverage_label, "5/5")
        self.assertFalse(below.v1_1_experimental_match)

    def test_v1_1_badge_is_not_granted_when_another_condition_fails(self):
        result = self.coverage(symbol="OTHER", volume_ratio_20=1.10, rsi_14=72.0)

        self.assertEqual(result.coverage_label, "3/5")
        self.assertEqual(result.missing_condition_ids, ("volume_ratio_20", "rsi_14"))
        self.assertFalse(result.v1_1_experimental_match)

    def test_result_model_has_no_forbidden_fields(self):
        forbidden = {
            "score",
            "rank",
            "winner",
            "probability",
            "confidence",
            "recommendation",
        }

        self.assertTrue(
            forbidden.isdisjoint({field.name for field in fields(ScannerConditionCoverageResult)})
        )

    def test_summary_breakdown_counts_missing_condition_signatures(self):
        near_volume = self.signal_match(symbol="2368.TW", volume_ratio_20=1.10)
        near_rsi = self.signal_match(symbol="2884.TW", rsi_14=72.0)
        exploratory = self.signal_match(symbol="2002.TW", volume_ratio_20=1.10, rsi_14=72.0)
        summary = build_scanner_condition_coverage_summary(
            self.scanner_result((near_volume, near_rsi, exploratory), matched_symbols=tuple()),
            production_signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
        )

        near_breakdown = {
            row.missing_condition_signature: row.symbol_count
            for row in summary.near_match_missing_condition_breakdown
        }
        exploratory_breakdown = {
            row.missing_condition_signature: row.symbol_count
            for row in summary.exploratory_missing_condition_breakdown
        }
        self.assertEqual(near_breakdown["MISSING_volume_ratio_20"], 1)
        self.assertEqual(near_breakdown["MISSING_rsi_14"], 1)
        self.assertEqual(exploratory_breakdown["MISSING_volume_ratio_20+rsi_14"], 1)


if __name__ == "__main__":
    unittest.main()
