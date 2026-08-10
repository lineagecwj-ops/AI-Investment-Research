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

from candidate_display_research_service import CandidateDisplayClassification
from candidate_display_research_service import CandidateDisplayResearchResult
from candidate_display_research_service import EvidenceClassification
from candidate_display_research_service import assert_no_forbidden_result_fields
from candidate_display_research_service import build_candidate_display_research_summary
from candidate_display_research_service import build_candidate_display_phase3_payload
from candidate_display_research_service import live_symbol_lists
from models import OverlappingSignalPolicy
from models import TechnicalIndicatorSnapshot
from scanner_condition_coverage_outcome_research_service import database_safety_audit
from scanner_condition_coverage_service import build_scanner_condition_coverage_summary
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import evaluate_signal_conditions
from swing_scanner_service import SwingScannerConfig


GENERATED_AT = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)


class CandidateDisplayResearchServiceTestCase(unittest.TestCase):

    def snapshot(self, symbol="2330.TW", trading_date=date(2026, 8, 10), **overrides):
        values = {
            "symbol": symbol,
            "trading_date": trading_date,
            "analysis_close": 110.0,
            "sma_5": None,
            "sma_10": None,
            "sma_20": 100.0,
            "sma_60": 90.0,
            "sma_120": None,
            "sma_200": None,
            "ema_12": None,
            "ema_26": None,
            "rsi_14": 60.0,
            "macd": None,
            "macd_signal": None,
            "macd_histogram": None,
            "atr_14": None,
            "atr_14_pct": None,
            "volume_sma_20": None,
            "volume_ratio_20": 1.20,
            "return_5d": None,
            "return_20d": None,
            "return_60d": None,
            "return_volatility_20d": None,
            "high_20d": None,
            "high_60d": None,
            "high_252d": None,
            "low_20d": None,
            "low_60d": None,
            "prior_high_20d": None,
            "prior_high_60d": 115.0,
            "prior_high_252d": None,
            "prior_low_20d": None,
            "prior_low_60d": 80.0,
            "distance_to_prior_20d_high": None,
            "distance_to_prior_60d_high": -0.02,
            "distance_to_prior_52_week_high": None,
            "is_above_prior_20d_high": None,
            "is_above_prior_60d_high": None,
            "is_above_prior_52_week_high": None,
            "close_above_sma20": None,
            "close_above_sma60": None,
            "sma20_above_sma60": None,
            "sma60_above_sma120": None,
            "sma20_change_5d": None,
            "sma60_change_5d": None,
            "position_in_prior_60d_range": None,
        }
        values.update(overrides)
        return TechnicalIndicatorSnapshot(**values)

    def signal_match(self, **snapshot_overrides):
        return evaluate_signal_conditions(
            self.snapshot(**snapshot_overrides),
            TECHNICAL_EXAMPLE_SIGNAL_V1,
        )

    def scanner_result(self, signal_matches, matched_symbols):
        return SimpleNamespace(
            config=SwingScannerConfig(
                signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
                outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
                overlap_policy=OverlappingSignalPolicy.ALLOW_ALL,
                minimum_resolved_samples=0,
            ),
            current_signal_details=tuple(signal_matches),
            matched_candidates=tuple(SimpleNamespace(symbol=symbol) for symbol in matched_symbols),
            generated_at=GENERATED_AT,
        )

    def summary(self, signal_matches, matched_symbols):
        coverage = build_scanner_condition_coverage_summary(
            self.scanner_result(signal_matches, matched_symbols),
            production_signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
        )
        return build_candidate_display_research_summary(
            coverage,
            generated_at=GENERATED_AT,
        )

    def test_classifies_required_phase3_display_buckets(self):
        summary = self.summary(
            (
                self.signal_match(symbol="1001.TW"),
                self.signal_match(symbol="1002.TW", rsi_14=72.0),
                self.signal_match(symbol="1003.TW", volume_ratio_20=1.10),
                self.signal_match(symbol="1004.TW", distance_to_prior_60d_high=-0.08),
                self.signal_match(symbol="1005.TW", sma_20=80.0, sma_60=90.0),
                self.signal_match(symbol="1006.TW", analysis_close=90.0),
                self.signal_match(symbol="1007.TW", volume_ratio_20=1.10, rsi_14=72.0),
                self.signal_match(symbol="1008.TW", volume_ratio_20=1.10, rsi_14=72.0, analysis_close=90.0),
            ),
            matched_symbols=("1001.TW",),
        )
        by_symbol = {result.symbol: result for result in summary.results}

        self.assertIs(by_symbol["1001.TW"].display_classification, CandidateDisplayClassification.FORMAL_V1)
        self.assertEqual(by_symbol["1001.TW"].display_reason_code, "FORMAL_V1_5_OF_5")
        self.assertIs(by_symbol["1002.TW"].display_classification, CandidateDisplayClassification.RESEARCH_PRIORITY_A)
        self.assertEqual(by_symbol["1002.TW"].display_reason_code, "FOUR_OF_FIVE_MISSING_RSI")
        self.assertIs(by_symbol["1003.TW"].display_classification, CandidateDisplayClassification.RESEARCH_PRIORITY_B)
        self.assertEqual(by_symbol["1003.TW"].display_reason_code, "FOUR_OF_FIVE_MISSING_VOLUME")
        self.assertIs(by_symbol["1004.TW"].display_classification, CandidateDisplayClassification.RESEARCH_WATCH)
        self.assertEqual(by_symbol["1004.TW"].display_reason_code, "FOUR_OF_FIVE_MISSING_DISTANCE")
        self.assertIs(by_symbol["1005.TW"].display_classification, CandidateDisplayClassification.EXPLORATORY)
        self.assertEqual(by_symbol["1005.TW"].display_reason_code, "FOUR_OF_FIVE_OTHER")
        self.assertIs(by_symbol["1006.TW"].display_classification, CandidateDisplayClassification.EXPLORATORY)
        self.assertEqual(by_symbol["1006.TW"].display_reason_code, "FOUR_OF_FIVE_OTHER")
        self.assertIs(by_symbol["1007.TW"].display_classification, CandidateDisplayClassification.EXPLORATORY)
        self.assertEqual(by_symbol["1007.TW"].display_reason_code, "THREE_OF_FIVE_EXPLORATORY")
        self.assertIs(by_symbol["1008.TW"].display_classification, CandidateDisplayClassification.BELOW_DISPLAY_SCOPE)
        self.assertEqual(by_symbol["1008.TW"].display_reason_code, "BELOW_THREE_OF_FIVE")

    def test_count_reconciliation_and_formal_identity(self):
        summary = self.summary(
            (
                self.signal_match(symbol="1001.TW"),
                self.signal_match(symbol="1002.TW", rsi_14=72.0),
                self.signal_match(symbol="1003.TW", volume_ratio_20=1.10),
                self.signal_match(symbol="1004.TW", distance_to_prior_60d_high=-0.08),
                self.signal_match(symbol="1005.TW", sma_20=80.0, sma_60=90.0),
                self.signal_match(symbol="1006.TW", volume_ratio_20=1.10, rsi_14=72.0),
                self.signal_match(symbol="1007.TW", volume_ratio_20=1.10, rsi_14=72.0, analysis_close=90.0),
            ),
            matched_symbols=("1001.TW",),
        )

        self.assertTrue(summary.count_reconciliation.reconciled)
        self.assertEqual(summary.count_reconciliation.evaluated_symbol_count, 7)
        self.assertEqual(summary.count_reconciliation.formal_v1_count, 1)
        self.assertEqual(summary.count_reconciliation.research_priority_a_count, 1)
        self.assertEqual(summary.count_reconciliation.research_priority_b_count, 1)
        self.assertEqual(summary.count_reconciliation.research_watch_count, 1)
        self.assertEqual(summary.count_reconciliation.other_4of5_exploratory_count, 1)
        self.assertEqual(summary.count_reconciliation.three_of_five_exploratory_count, 1)
        self.assertEqual(summary.count_reconciliation.below_display_scope_count, 1)
        self.assertEqual(live_symbol_lists(summary)["FORMAL_V1"], ("1001.TW",))

    def test_v1_1_badge_stays_factual_and_does_not_promote_priority_b(self):
        summary = self.summary(
            (
                self.signal_match(symbol="2368.TW", volume_ratio_20=1.10),
                self.signal_match(symbol="2884.TW", volume_ratio_20=1.099999),
            ),
            matched_symbols=tuple(),
        )
        by_symbol = {result.symbol: result for result in summary.results}

        self.assertIs(by_symbol["2368.TW"].display_classification, CandidateDisplayClassification.RESEARCH_PRIORITY_B)
        self.assertTrue(by_symbol["2368.TW"].v1_1_experimental_match)
        self.assertFalse(by_symbol["2368.TW"].formal_v1_qualified)
        self.assertIs(by_symbol["2884.TW"].display_classification, CandidateDisplayClassification.RESEARCH_PRIORITY_B)
        self.assertFalse(by_symbol["2884.TW"].v1_1_experimental_match)

    def test_non_formal_groups_do_not_promote_to_formal_v1(self):
        summary = self.summary(
            (
                self.signal_match(symbol="1002.TW", rsi_14=72.0),
                self.signal_match(symbol="1003.TW", volume_ratio_20=1.10),
                self.signal_match(symbol="1004.TW", distance_to_prior_60d_high=-0.08),
            ),
            matched_symbols=tuple(),
        )

        self.assertTrue(all(not result.formal_v1_qualified for result in summary.results))

    def test_evidence_metadata_is_group_hhr_not_individual_output_fields(self):
        summary = self.summary((self.signal_match(symbol="1002.TW", rsi_14=72.0),), matched_symbols=tuple())
        result = summary.results[0]

        self.assertEqual(result.evidence_reference.group_id, "MISSING_rsi_14")
        self.assertEqual(result.evidence_reference.daily_hhr, 0.9713)
        self.assertIs(result.evidence_classification, EvidenceClassification.DISPLAY_DESIGN_SUPPORTED)
        forbidden = {
            "score",
            "rank",
            "probability",
            "confidence",
            "recommendation",
            "expected_return",
            "buy",
            "sell",
            "individual_success_probability",
            "predicted_hhr",
            "stock_win_rate",
        }
        self.assertTrue(forbidden.isdisjoint({field.name for field in fields(CandidateDisplayResearchResult)}))
        assert_no_forbidden_result_fields()

    def test_same_inputs_produce_same_semantic_checksum(self):
        signal_matches = (
            self.signal_match(symbol="1001.TW"),
            self.signal_match(symbol="1002.TW", rsi_14=72.0),
        )

        first = self.summary(signal_matches, matched_symbols=("1001.TW",))
        second = self.summary(signal_matches, matched_symbols=("1001.TW",))

        self.assertEqual(first.semantic_checksum, second.semantic_checksum)

    def test_phase3_projection_does_not_mutate_scanner_or_coverage_results(self):
        scan_result = self.scanner_result(
            (
                self.signal_match(symbol="1001.TW"),
                self.signal_match(symbol="1002.TW", rsi_14=72.0),
            ),
            matched_symbols=("1001.TW",),
        )
        coverage = build_scanner_condition_coverage_summary(
            scan_result,
            production_signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
        )
        scanner_hits_before = tuple(candidate.symbol for candidate in scan_result.matched_candidates)
        coverage_missing_before = tuple(result.missing_condition_ids for result in coverage.results)
        current_signal_ids = tuple(id(match) for match in scan_result.current_signal_details)

        build_candidate_display_research_summary(coverage, generated_at=GENERATED_AT)

        self.assertEqual(tuple(candidate.symbol for candidate in scan_result.matched_candidates), scanner_hits_before)
        self.assertEqual(tuple(result.missing_condition_ids for result in coverage.results), coverage_missing_before)
        self.assertEqual(tuple(id(match) for match in scan_result.current_signal_details), current_signal_ids)

    def test_payload_records_safety_boundaries(self):
        summary = self.summary((self.signal_match(symbol="1001.TW"),), matched_symbols=("1001.TW",))
        db_audit = database_safety_audit(PROJECT_ROOT / "data" / "stocks.db")

        payload = build_candidate_display_phase3_payload(
            summary,
            db_audit_before=db_audit,
            db_audit_after=db_audit,
            scanner_result=None,
        )

        self.assertFalse(payload["metadata"]["dashboard_changed"])
        self.assertFalse(payload["metadata"]["scanner_changed"])
        self.assertFalse(payload["metadata"]["ranking_created"])
        self.assertFalse(payload["metadata"]["score_created"])
        self.assertFalse(payload["metadata"]["recommendation_created"])
        self.assertIn("post-hoc", payload["metadata"]["post_hoc_warning"])
        self.assertIn("survivorship bias", payload["metadata"]["survivorship_warning"])


if __name__ == "__main__":
    unittest.main()
