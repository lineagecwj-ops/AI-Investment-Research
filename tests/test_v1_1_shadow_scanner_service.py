import sys
import unittest
from dataclasses import fields
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from backtest_service import HistoricalBacktestReport
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeEvaluationStatus
from models import OverlappingSignalPolicy
from models import SignalEvaluationStatus
from models import TechnicalIndicatorSeries
from models import TechnicalIndicatorSnapshot
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL
from signal_outcome_service import evaluate_signal_conditions
from swing_scanner_service import SwingScannerConfig
from swing_scanner_service import SwingScannerService
from v1_1_shadow_scanner_service import V1V11ShadowScannerComparisonStatus
from v1_1_shadow_scanner_service import V1V11ShadowScannerError
from v1_1_shadow_scanner_service import V1V11ShadowScannerResult
from v1_1_shadow_scanner_service import build_v1_v1_1_shadow_scanner_result
from v1_1_shadow_scanner_service import build_v1_v1_1_shadow_scanner_summary


FETCHED_AT = datetime(2026, 8, 10, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 10, 2, 0, tzinfo=UTC)


class V11ShadowScannerServiceTestCase(unittest.TestCase):

    def snapshot(self, symbol="2330.TW", trading_date=date(2026, 8, 10), **overrides):
        values = {field.name: None for field in fields(TechnicalIndicatorSnapshot)}
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
        snapshot = self.snapshot(**snapshot_overrides)
        return evaluate_signal_conditions(snapshot, TECHNICAL_EXAMPLE_SIGNAL_V1)

    def price_series(self, symbol):
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="TWD",
            bars=(
                HistoricalPriceBar(
                    symbol=symbol,
                    trading_date=date(2026, 8, 10),
                    open=100.0,
                    high=111.0,
                    low=99.0,
                    close=110.0,
                    adjusted_close=110.0,
                    volume=1000,
                ),
            ),
            fetched_at=FETCHED_AT,
            is_stale=False,
        )

    def technical_series(self, snapshot):
        return TechnicalIndicatorSeries(
            symbol=snapshot.symbol,
            snapshots=(snapshot,),
            generated_at=GENERATED_AT,
            source_price_fetched_at=FETCHED_AT,
            source_price_is_stale=False,
        )

    def report(self, symbol):
        return HistoricalBacktestReport(
            symbol=symbol,
            signal_definition_id=TECHNICAL_EXAMPLE_SIGNAL_V1.id,
            outcome_definition_id=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id,
            overlap_policy=OverlappingSignalPolicy.ALLOW_ALL,
            cooldown_bars=None,
            start_date=None,
            end_date=None,
            backtest_id=f"backtest_{symbol}",
            raw_signal_count=1,
            filtered_signal_count=1,
            hit_count=1,
            miss_count=0,
            incomplete_count=0,
            not_evaluable_count=0,
            resolved_count=1,
            historical_hit_rate=1.0,
            average_max_close_return=0.1,
            median_max_close_return=0.1,
            average_max_adverse_return=-0.01,
            median_max_adverse_return=-0.01,
            average_end_return=0.04,
            median_end_return=0.04,
            average_hit_bar_index=3,
            median_hit_bar_index=3,
            max_return_sample_count=1,
            max_adverse_sample_count=1,
            end_return_sample_count=1,
            hit_bar_sample_count=1,
            raw_events=tuple(),
            evaluated_events=tuple(),
            cases=tuple(),
            generated_at=GENERATED_AT,
        )

    def scanner_config(self):
        return SwingScannerConfig(
            signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
            outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
            overlap_policy=OverlappingSignalPolicy.ALLOW_ALL,
            minimum_resolved_samples=0,
        )

    def scan_result(self, snapshots):
        snapshots_by_symbol = {snapshot.symbol: snapshot for snapshot in snapshots}
        technical_call_count = {"count": 0}

        def price_loader(symbol, *, force_refresh=False):
            return self.price_series(symbol)

        def technical_builder(price_series):
            technical_call_count["count"] += 1
            return self.technical_series(snapshots_by_symbol[price_series.symbol])

        def backtest_runner(price_series, technical_series, config):
            return self.report(price_series.symbol)

        result = SwingScannerService(
            price_loader=price_loader,
            technical_builder=technical_builder,
            backtest_runner=backtest_runner,
        ).scan(tuple(snapshots_by_symbol), self.scanner_config())
        return result, technical_call_count

    def test_classifies_shared_pass_v1_1_only_and_neither(self):
        shared = self.signal_match(symbol="SHARED", volume_ratio_20=1.20)
        experimental_only = self.signal_match(symbol="V11", volume_ratio_20=1.10)
        neither = self.signal_match(symbol="NEITHER", analysis_close=90.0, volume_ratio_20=1.50)

        self.assertEqual(
            build_v1_v1_1_shadow_scanner_result(shared).comparison_status,
            V1V11ShadowScannerComparisonStatus.SHARED_PASS,
        )
        self.assertEqual(
            build_v1_v1_1_shadow_scanner_result(experimental_only).comparison_status,
            V1V11ShadowScannerComparisonStatus.V1_1_ONLY,
        )
        self.assertEqual(
            build_v1_v1_1_shadow_scanner_result(neither).comparison_status,
            V1V11ShadowScannerComparisonStatus.NEITHER,
        )

    def test_volume_boundaries_enforce_v1_1_only_interval(self):
        below = build_v1_v1_1_shadow_scanner_result(self.signal_match(symbol="LOW", volume_ratio_20=1.099999))
        lower = build_v1_v1_1_shadow_scanner_result(self.signal_match(symbol="LOWER", volume_ratio_20=1.10))
        upper = build_v1_v1_1_shadow_scanner_result(self.signal_match(symbol="UPPER", volume_ratio_20=1.199999))
        shared = build_v1_v1_1_shadow_scanner_result(self.signal_match(symbol="V1", volume_ratio_20=1.20))

        self.assertEqual(below.comparison_status, V1V11ShadowScannerComparisonStatus.NEITHER)
        self.assertEqual(lower.comparison_status, V1V11ShadowScannerComparisonStatus.V1_1_ONLY)
        self.assertEqual(upper.comparison_status, V1V11ShadowScannerComparisonStatus.V1_1_ONLY)
        self.assertEqual(shared.comparison_status, V1V11ShadowScannerComparisonStatus.SHARED_PASS)

    def test_other_condition_failure_prevents_v1_1_only(self):
        result = build_v1_v1_1_shadow_scanner_result(
            self.signal_match(symbol="FAIL_OTHER", analysis_close=90.0, volume_ratio_20=1.10)
        )

        self.assertEqual(result.comparison_status, V1V11ShadowScannerComparisonStatus.NEITHER)
        self.assertEqual(result.other_condition_statuses["analysis_close"], SignalEvaluationStatus.NO_MATCH.value)

    def test_batch_enforces_v1_subset_v1_1_identity_invariant(self):
        scan_result, _calls = self.scan_result(
            (
                self.snapshot(symbol="SHARED", volume_ratio_20=1.20),
                self.snapshot(symbol="V11", volume_ratio_20=1.10),
                self.snapshot(symbol="NEITHER", analysis_close=90.0, volume_ratio_20=1.50),
            )
        )

        summary = build_v1_v1_1_shadow_scanner_summary(scan_result)

        self.assertEqual(summary.evaluated_symbol_count, 3)
        self.assertEqual(summary.production_hit_symbols, ("SHARED",))
        self.assertEqual(summary.experimental_hit_symbols, ("SHARED", "V11"))
        self.assertEqual(summary.shared_symbols, ("SHARED",))
        self.assertEqual(summary.experimental_only_symbols, ("V11",))
        self.assertEqual(summary.neither_symbols, ("NEITHER",))
        self.assertEqual(summary.invariant_violation_count, 0)
        self.assertTrue(set(summary.production_hit_symbols).issubset(summary.experimental_hit_symbols))

    def test_same_scanner_snapshot_is_reused_without_second_technical_build(self):
        snapshots = (
            self.snapshot(symbol="SHARED", volume_ratio_20=1.20),
            self.snapshot(symbol="V11", volume_ratio_20=1.10),
        )
        scan_result, technical_call_count = self.scan_result(snapshots)
        production_ids_before = tuple(candidate.symbol for candidate in scan_result.matched_candidates)

        summary = build_v1_v1_1_shadow_scanner_summary(scan_result)

        self.assertEqual(technical_call_count["count"], 2)
        self.assertEqual(tuple(candidate.symbol for candidate in scan_result.matched_candidates), production_ids_before)
        self.assertIs(summary.results[0].production_condition_result.feature_snapshot, snapshots[0])
        self.assertIs(summary.results[0].experimental_condition_result.feature_snapshot, snapshots[0])
        self.assertEqual(technical_call_count["count"], 2)

    def test_production_output_contract_and_order_are_unchanged_by_shadow_summary(self):
        scan_result, _calls = self.scan_result(
            (
                self.snapshot(symbol="BBB", volume_ratio_20=1.20),
                self.snapshot(symbol="AAA", volume_ratio_20=1.20),
                self.snapshot(symbol="V11", volume_ratio_20=1.10),
            )
        )
        before_type = type(scan_result)
        before_hits = tuple(candidate.symbol for candidate in scan_result.matched_candidates)
        before_no_match = scan_result.no_match_symbols

        build_v1_v1_1_shadow_scanner_summary(scan_result)

        self.assertIs(type(scan_result), before_type)
        self.assertEqual(tuple(candidate.symbol for candidate in scan_result.matched_candidates), before_hits)
        self.assertEqual(scan_result.no_match_symbols, before_no_match)

    def test_default_definitions_and_result_model_do_not_add_recommendation_fields(self):
        self.assertEqual(TECHNICAL_EXAMPLE_SIGNAL_V1.id, "technical_example_v1")
        self.assertEqual(TECHNICAL_EXAMPLE_SIGNAL_V1.conditions[2].value, 1.2)
        self.assertEqual(TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL.id, "technical_example_v1_1_experimental")
        self.assertEqual(TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL.conditions[2].value, 1.1)
        forbidden = {"winner", "rank", "score", "probability", "confidence", "recommendation"}

        self.assertTrue(forbidden.isdisjoint({field.name for field in fields(V1V11ShadowScannerResult)}))

    def test_invariant_violation_is_blocking(self):
        shared = self.signal_match(symbol="BROKEN", volume_ratio_20=1.20)

        with patch(
            "v1_1_shadow_scanner_service.evaluate_signal_conditions",
            side_effect=(shared, self.signal_match(symbol="BROKEN", analysis_close=90.0, volume_ratio_20=1.20)),
        ):
            result = build_v1_v1_1_shadow_scanner_result(shared)

        self.assertEqual(result.comparison_status, V1V11ShadowScannerComparisonStatus.INVARIANT_VIOLATION)

    def test_batch_raises_on_invariant_violation(self):
        scan_result, _calls = self.scan_result((self.snapshot(symbol="BROKEN", volume_ratio_20=1.20),))
        broken = build_v1_v1_1_shadow_scanner_result(scan_result.current_signal_details[0])
        broken = type(broken)(
            symbol=broken.symbol,
            as_of_date=broken.as_of_date,
            production_definition_id=broken.production_definition_id,
            experimental_definition_id=broken.experimental_definition_id,
            production_qualified=True,
            experimental_qualified=False,
            comparison_status=V1V11ShadowScannerComparisonStatus.INVARIANT_VIOLATION,
            volume_ratio_20=broken.volume_ratio_20,
            production_condition_result=broken.production_condition_result,
            experimental_condition_result=broken.experimental_condition_result,
            other_condition_statuses=broken.other_condition_statuses,
        )

        with patch("v1_1_shadow_scanner_service.build_v1_v1_1_shadow_scanner_result", return_value=broken):
            with self.assertRaisesRegex(V1V11ShadowScannerError, "invariant violation"):
                build_v1_v1_1_shadow_scanner_summary(scan_result)

    def test_import_has_no_db_or_network_side_effects(self):
        import v1_1_shadow_scanner_service as module

        self.assertFalse(hasattr(module, "get_historical_prices"))
        self.assertFalse(hasattr(module, "build_technical_indicator_series"))
        self.assertFalse(hasattr(module, "scan_swing_opportunities"))


if __name__ == "__main__":
    unittest.main()
