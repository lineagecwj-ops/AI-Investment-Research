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

from backtest_service import BacktestConfig
from backtest_service import HistoricalBacktestReport
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeDefinition
from models import OutcomeType
from models import OverlappingSignalPolicy
from models import SignalConditionOperator
from models import SignalDefinition
from models import SignalEvaluationStatus
from models import TechnicalIndicatorSeries
from models import TechnicalIndicatorSnapshot
from models import TechnicalSignalCondition
from signal_outcome_service import evaluate_signal_conditions
from database_config import DEFAULT_DATABASE_PATH_CONFIG
from live_data_store import LiveDataStore
from swing_scanner_service import LATEST_BAR_PROVISIONAL_LIMITATION
from swing_scanner_service import SWING_RESEARCH_RANK_POLICY_V1
from swing_scanner_service import SampleSizeStatus
from swing_scanner_service import SwingOpportunityCandidate
from swing_scanner_service import SwingScannerConfig
from swing_scanner_service import SwingScannerService
from swing_scanner_service import build_swing_candidate
from swing_scanner_service import get_candidate_rank_components
from swing_scanner_service import get_sample_size_status
from swing_scanner_service import live_data_store_price_loader
from swing_scanner_service import rank_swing_candidates


FETCHED_AT = datetime(2026, 8, 8, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 8, 2, 0, tzinfo=UTC)


class RecordingBacktestRunner:

    def __init__(self, reports):
        self.reports = dict(reports)
        self.calls = []

    def __call__(self, price_series, technical_series, config):
        self.calls.append((price_series.symbol, price_series, technical_series, config))
        return self.reports[price_series.symbol]


class SwingScannerServiceTestCase(unittest.TestCase):

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
                    metric="sma_20",
                    operator=SignalConditionOperator.GREATER_THAN,
                    secondary_metric="sma_60",
                ),
                TechnicalSignalCondition(
                    metric="volume_ratio_20",
                    operator=SignalConditionOperator.GREATER_THAN_OR_EQUAL,
                    value=1.2,
                ),
            ),
            minimum_required_features=("analysis_close", "sma_20", "sma_60", "volume_ratio_20"),
            description="Test-only current scanner signal.",
        )

    def outcome_definition(self):
        return OutcomeDefinition(
            id="test_outcome_v1",
            outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
            horizon_bars=20,
            reference_metric="prior_high_60d",
        )

    def config(self, **overrides):
        values = {
            "signal_definition": self.signal_definition(),
            "outcome_definition": self.outcome_definition(),
            "overlap_policy": OverlappingSignalPolicy.ALLOW_ALL,
            "cooldown_bars": None,
            "backtest_start_date": date(2018, 1, 1),
            "backtest_end_date": date(2025, 12, 31),
            "minimum_resolved_samples": 20,
        }
        values.update(overrides)
        return SwingScannerConfig(**values)

    def snapshot(self, symbol="TEST", trading_date=date(2026, 8, 7), **overrides):
        params = {
            field.name: None
            for field in fields(TechnicalIndicatorSnapshot)
        }
        params.update(
            symbol=symbol,
            trading_date=trading_date,
            analysis_close=110.0,
            sma_20=100.0,
            sma_60=90.0,
            volume_ratio_20=1.5,
            rsi_14=60.0,
            distance_to_prior_60d_high=-0.02,
            prior_high_60d=115.0,
            prior_low_60d=80.0,
        )
        params.update(overrides)
        return TechnicalIndicatorSnapshot(**params)

    def price_series(self, symbol="TEST", stale=False):
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="USD",
            bars=(
                HistoricalPriceBar(
                    symbol=symbol,
                    trading_date=date(2026, 8, 7),
                    open=100.0,
                    high=111.0,
                    low=99.0,
                    close=110.0,
                    adjusted_close=110.0,
                    volume=1000,
                ),
            ),
            fetched_at=FETCHED_AT,
            is_stale=stale,
        )

    def technical_series(self, symbol="TEST", *, snapshot=None, stale=False, snapshots=None):
        if snapshots is None:
            snapshots = (snapshot or self.snapshot(symbol=symbol),)
        return TechnicalIndicatorSeries(
            symbol=symbol,
            snapshots=tuple(snapshots),
            generated_at=GENERATED_AT,
            source_price_fetched_at=FETCHED_AT,
            source_price_is_stale=stale,
        )

    def report(
        self,
        symbol="TEST",
        *,
        hit_rate=0.7,
        resolved=100,
        hit=70,
        miss=30,
        incomplete=2,
        not_evaluable=1,
        raw=120,
        filtered=103,
        mfe=0.12,
        mae=-0.04,
        end_return=0.03,
        hit_bars=8.0,
        config=None,
    ):
        config = config or self.config().to_backtest_config()
        return HistoricalBacktestReport(
            symbol=symbol,
            signal_definition_id=config.signal_definition.id,
            outcome_definition_id=config.outcome_definition.id,
            overlap_policy=config.overlap_policy,
            cooldown_bars=config.cooldown_bars,
            start_date=config.start_date,
            end_date=config.end_date,
            backtest_id=f"backtest_{symbol}",
            raw_signal_count=raw,
            filtered_signal_count=filtered,
            hit_count=hit,
            miss_count=miss,
            incomplete_count=incomplete,
            not_evaluable_count=not_evaluable,
            resolved_count=resolved,
            historical_hit_rate=hit_rate,
            average_max_close_return=mfe,
            median_max_close_return=mfe,
            average_max_adverse_return=mae,
            median_max_adverse_return=mae,
            average_end_return=end_return,
            median_end_return=end_return,
            average_hit_bar_index=hit_bars,
            median_hit_bar_index=hit_bars,
            max_return_sample_count=resolved,
            max_adverse_sample_count=resolved,
            end_return_sample_count=resolved,
            hit_bar_sample_count=hit,
            raw_events=tuple(),
            evaluated_events=tuple(),
            cases=tuple(),
            generated_at=GENERATED_AT,
        )

    def service(self, price_by_symbol, technical_by_symbol, reports):
        def price_loader(symbol, *, force_refresh=False):
            if symbol == "FAIL":
                raise RuntimeError("provider unavailable\ntrace omitted")
            return price_by_symbol[symbol]

        def technical_builder(price_series):
            return technical_by_symbol[price_series.symbol]

        runner = RecordingBacktestRunner(reports)
        return SwingScannerService(
            price_loader=price_loader,
            technical_builder=technical_builder,
            backtest_runner=runner,
        ), runner

    def candidate(self, symbol, *, hit_rate=0.7, resolved=100, mae=-0.04, mfe=0.12, end_return=0.03):
        config = self.config()
        snapshot = self.snapshot(symbol=symbol)
        match = evaluate_signal_conditions(snapshot, config.signal_definition)
        report = self.report(
            symbol=symbol,
            hit_rate=hit_rate,
            resolved=resolved,
            hit=0 if hit_rate is None else int(hit_rate * resolved),
            miss=resolved if hit_rate is None else resolved - int(hit_rate * resolved),
            mae=mae,
            mfe=mfe,
            end_return=end_return,
        )
        return build_swing_candidate(
            signal_match=match,
            technical_series=self.technical_series(symbol=symbol, snapshot=snapshot),
            report=report,
            config=config,
        )

    def test_empty_universe_returns_empty_result(self):
        service, runner = self.service({}, {}, {})

        result = service.scan([], self.config())

        self.assertEqual(result.requested_symbols, tuple())
        self.assertEqual(result.normalized_symbols, tuple())
        self.assertEqual(result.matched_candidates, tuple())
        self.assertEqual(runner.calls, [])

    def test_default_scanner_receives_live_data_store(self):
        live_store = LiveDataStore()

        service = SwingScannerService(live_data_store=live_store)

        self.assertIs(service.live_data_store, live_store)

    def test_default_price_loader_uses_live_data_store_boundary(self):
        live_store = LiveDataStore()
        series = self.price_series("NVDA")

        with patch("swing_scanner_service.get_historical_prices", return_value=series) as loader:
            price_loader = live_data_store_price_loader(live_store)
            loaded = price_loader("NVDA", force_refresh=True)

        self.assertIs(loaded, series)
        loader.assert_called_once_with("NVDA", force_refresh=True, live_store=live_store)

    def test_default_scanner_uses_formal_live_store_after_cutover(self):
        service = SwingScannerService()

        self.assertEqual(
            service.live_data_store.resolved_db_path,
            DEFAULT_DATABASE_PATH_CONFIG.live_db_path.resolve(),
        )
        self.assertNotEqual(
            service.live_data_store.resolved_db_path,
            DEFAULT_DATABASE_PATH_CONFIG.legacy_db_path.resolve(),
        )

    def test_scanner_module_does_not_import_research_data_store(self):
        import swing_scanner_service as module

        self.assertFalse(hasattr(module, "ResearchDataStore"))

    def test_duplicate_symbols_are_normalized_and_scanned_once(self):
        price = {"2330.TW": self.price_series("2330.TW")}
        technical = {"2330.TW": self.technical_series("2330.TW")}
        reports = {"2330.TW": self.report("2330.TW")}
        service, runner = self.service(price, technical, reports)

        result = service.scan(["2330", "2330.TW", "2330"], self.config())

        self.assertEqual(result.requested_count, 3)
        self.assertEqual(result.normalized_symbols, ("2330.TW",))
        self.assertEqual(len(runner.calls), 1)

    def test_match_calls_backtest_once(self):
        price = {"NVDA": self.price_series("NVDA")}
        technical = {"NVDA": self.technical_series("NVDA")}
        reports = {"NVDA": self.report("NVDA")}
        service, runner = self.service(price, technical, reports)

        result = service.scan(["NVDA"], self.config())

        self.assertEqual(result.matched_count, 1)
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0][0], "NVDA")
        self.assertEqual(result.current_signal_details[0].status, SignalEvaluationStatus.MATCH)

    def test_no_match_never_calls_backtest(self):
        no_match_snapshot = self.snapshot(symbol="AAPL", analysis_close=90.0)
        price = {"AAPL": self.price_series("AAPL")}
        technical = {"AAPL": self.technical_series("AAPL", snapshot=no_match_snapshot)}
        service, runner = self.service(price, technical, {})

        result = service.scan(["AAPL"], self.config())

        self.assertEqual(result.no_match_symbols, ("AAPL",))
        self.assertEqual(runner.calls, [])

    def test_no_match_details_keep_failed_condition_summary(self):
        no_match_snapshot = self.snapshot(symbol="AAPL", analysis_close=90.0)
        price = {"AAPL": self.price_series("AAPL")}
        technical = {"AAPL": self.technical_series("AAPL", snapshot=no_match_snapshot)}
        service, _runner = self.service(price, technical, {})

        result = service.scan(["AAPL"], self.config())

        self.assertEqual(result.no_match_details[0].symbol, "AAPL")
        self.assertEqual(result.no_match_details[0].status, SignalEvaluationStatus.NO_MATCH)
        self.assertEqual(result.no_match_details[0].failed_conditions, ("analysis_close",))

    def test_no_match_preserves_scan_time_current_signal_detail(self):
        no_match_snapshot = self.snapshot(symbol="AAPL", analysis_close=90.0)
        price = {"AAPL": self.price_series("AAPL")}
        technical = {"AAPL": self.technical_series("AAPL", snapshot=no_match_snapshot)}
        service, runner = self.service(price, technical, {})

        result = service.scan(["AAPL"], self.config())

        self.assertEqual(runner.calls, [])
        self.assertEqual(len(result.current_signal_details), 1)
        self.assertEqual(result.current_signal_details[0].symbol, "AAPL")
        self.assertEqual(result.current_signal_details[0].status, SignalEvaluationStatus.NO_MATCH)
        self.assertIs(result.current_signal_details[0].feature_snapshot, no_match_snapshot)
        self.assertEqual(result.current_signal_details[0].evaluated_conditions[0].actual_value, 90.0)

    def test_not_evaluable_never_calls_backtest(self):
        not_evaluable_snapshot = self.snapshot(symbol="AAPL", volume_ratio_20=None)
        price = {"AAPL": self.price_series("AAPL")}
        technical = {"AAPL": self.technical_series("AAPL", snapshot=not_evaluable_snapshot)}
        service, runner = self.service(price, technical, {})

        result = service.scan(["AAPL"], self.config())

        self.assertEqual(result.not_evaluable_count, 1)
        self.assertEqual(result.current_signal_details, tuple())
        self.assertEqual(result.not_evaluable_symbols[0].missing_required_features, ("volume_ratio_20",))
        self.assertEqual(runner.calls, [])

    def test_empty_technical_series_is_not_evaluable(self):
        price = {"AAPL": self.price_series("AAPL")}
        technical = {"AAPL": self.technical_series("AAPL", snapshots=tuple())}
        service, runner = self.service(price, technical, {})

        result = service.scan(["AAPL"], self.config())

        self.assertEqual(result.not_evaluable_count, 1)
        self.assertEqual(runner.calls, [])

    def test_one_symbol_failure_does_not_block_other_symbols(self):
        price = {"NVDA": self.price_series("NVDA")}
        technical = {"NVDA": self.technical_series("NVDA")}
        reports = {"NVDA": self.report("NVDA")}
        service, runner = self.service(price, technical, reports)

        result = service.scan(["NVDA", "FAIL"], self.config())

        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.failure_count, 1)
        self.assertEqual(result.failed_symbols[0].symbol, "FAIL")
        self.assertEqual(len(runner.calls), 1)

    def test_failure_message_does_not_store_traceback_lines(self):
        service, _runner = self.service({}, {}, {})

        result = service.scan(["FAIL"], self.config())

        self.assertEqual(result.failed_symbols[0].message, "provider unavailable")

    def test_blank_symbol_is_failed_not_crash(self):
        service, _runner = self.service({}, {}, {})

        result = service.scan([" "], self.config())

        self.assertEqual(result.failure_count, 1)
        self.assertEqual(result.failed_symbols[0].symbol, "")

    def test_all_no_match_is_valid_empty_candidates(self):
        no_match_snapshot = self.snapshot(symbol="AAPL", analysis_close=90.0)
        price = {"AAPL": self.price_series("AAPL")}
        technical = {"AAPL": self.technical_series("AAPL", snapshot=no_match_snapshot)}
        service, _runner = self.service(price, technical, {})

        result = service.scan(["AAPL"], self.config())

        self.assertEqual(result.matched_candidates, tuple())
        self.assertEqual(result.no_match_count, 1)

    def test_all_fail_still_returns_result(self):
        service, _runner = self.service({}, {}, {})

        result = service.scan(["FAIL"], self.config())

        self.assertEqual(result.scanned_count, 1)
        self.assertEqual(result.failure_count, 1)

    def test_count_invariant_uses_unique_normalized_symbols(self):
        no_match_snapshot = self.snapshot(symbol="AAPL", analysis_close=90.0)
        not_evaluable_snapshot = self.snapshot(symbol="MSFT", volume_ratio_20=None)
        price = {
            "NVDA": self.price_series("NVDA"),
            "AAPL": self.price_series("AAPL"),
            "MSFT": self.price_series("MSFT"),
        }
        technical = {
            "NVDA": self.technical_series("NVDA"),
            "AAPL": self.technical_series("AAPL", snapshot=no_match_snapshot),
            "MSFT": self.technical_series("MSFT", snapshot=not_evaluable_snapshot),
        }
        reports = {"NVDA": self.report("NVDA")}
        service, _runner = self.service(price, technical, reports)

        result = service.scan(["NVDA", "AAPL", "MSFT", "FAIL", "NVDA"], self.config())

        total = result.matched_count + result.no_match_count + result.not_evaluable_count + result.failure_count
        self.assertEqual(total, result.scanned_count)
        self.assertEqual(result.scanned_count, 4)

    def test_candidate_copies_backtest_metrics(self):
        price = {"NVDA": self.price_series("NVDA")}
        technical = {"NVDA": self.technical_series("NVDA")}
        reports = {"NVDA": self.report("NVDA", hit_rate=0.75, resolved=40, hit=30, miss=10)}
        service, _runner = self.service(price, technical, reports)

        candidate = service.scan(["NVDA"], self.config()).matched_candidates[0]

        self.assertEqual(candidate.historical_hit_rate, 0.75)
        self.assertEqual(candidate.resolved_count, 40)
        self.assertEqual(candidate.raw_signal_count, 120)
        self.assertEqual(candidate.filtered_signal_count, 103)
        self.assertEqual(candidate.median_max_close_return, 0.12)
        self.assertEqual(candidate.median_max_adverse_return, -0.04)
        self.assertEqual(candidate.median_end_return, 0.03)
        self.assertEqual(candidate.median_hit_bar_index, 8.0)

    def test_candidate_preserves_current_match_trace(self):
        price = {"NVDA": self.price_series("NVDA")}
        technical = {"NVDA": self.technical_series("NVDA")}
        reports = {"NVDA": self.report("NVDA")}
        service, _runner = self.service(price, technical, reports)

        candidate = service.scan(["NVDA"], self.config()).matched_candidates[0]

        self.assertEqual(candidate.signal_match.status, SignalEvaluationStatus.MATCH)
        self.assertGreater(len(candidate.signal_match.evaluated_conditions), 0)
        self.assertEqual(candidate.current_snapshot.trading_date, date(2026, 8, 7))

    def test_source_freshness_is_propagated(self):
        price = {"NVDA": self.price_series("NVDA", stale=True)}
        technical = {"NVDA": self.technical_series("NVDA", stale=True)}
        reports = {"NVDA": self.report("NVDA")}
        service, _runner = self.service(price, technical, reports)

        candidate = service.scan(["NVDA"], self.config()).matched_candidates[0]

        self.assertTrue(candidate.source_price_is_stale)
        self.assertIn("stale cached historical price data", " ".join(candidate.limitations))

    def test_candidate_and_result_keep_provisional_warning(self):
        price = {"NVDA": self.price_series("NVDA")}
        technical = {"NVDA": self.technical_series("NVDA")}
        reports = {"NVDA": self.report("NVDA")}
        service, _runner = self.service(price, technical, reports)

        result = service.scan(["NVDA"], self.config())

        self.assertIn(LATEST_BAR_PROVISIONAL_LIMITATION, result.limitations)
        self.assertTrue(result.matched_candidates[0].is_provisional_possible)
        self.assertIn(LATEST_BAR_PROVISIONAL_LIMITATION, result.matched_candidates[0].limitations)

    def test_backtest_config_is_shared_with_scanner_config(self):
        config = self.config(
            overlap_policy=OverlappingSignalPolicy.COOLDOWN,
            cooldown_bars=20,
            backtest_start_date=date(2019, 1, 1),
            backtest_end_date=date(2024, 12, 31),
        )
        price = {"NVDA": self.price_series("NVDA")}
        technical = {"NVDA": self.technical_series("NVDA")}
        reports = {"NVDA": self.report("NVDA", config=config.to_backtest_config())}
        service, runner = self.service(price, technical, reports)

        candidate = service.scan(["NVDA"], config).matched_candidates[0]

        self.assertEqual(runner.calls[0][3], config.to_backtest_config())
        self.assertEqual(candidate.overlap_policy, OverlappingSignalPolicy.COOLDOWN)
        self.assertEqual(candidate.cooldown_bars, 20)
        self.assertEqual(candidate.backtest_start_date, date(2019, 1, 1))

    def test_sample_size_status_zero(self):
        self.assertEqual(get_sample_size_status(0, 20), SampleSizeStatus.NO_RESOLVED_SAMPLES)

    def test_sample_size_status_below_preferred_minimum(self):
        self.assertEqual(get_sample_size_status(3, 20), SampleSizeStatus.BELOW_PREFERRED_MINIMUM)

    def test_sample_size_status_meets_preferred_minimum(self):
        self.assertEqual(get_sample_size_status(20, 20), SampleSizeStatus.MEETS_PREFERRED_MINIMUM)

    def test_zero_resolved_history_keeps_candidate_with_none_hit_rate(self):
        price = {"NVDA": self.price_series("NVDA")}
        technical = {"NVDA": self.technical_series("NVDA")}
        reports = {"NVDA": self.report("NVDA", hit_rate=None, resolved=0, hit=0, miss=0)}
        service, _runner = self.service(price, technical, reports)

        candidate = service.scan(["NVDA"], self.config()).matched_candidates[0]

        self.assertIsNone(candidate.historical_hit_rate)
        self.assertEqual(candidate.sample_size_status, SampleSizeStatus.NO_RESOLVED_SAMPLES)

    def test_small_sample_candidate_is_not_filtered_out(self):
        price = {"NVDA": self.price_series("NVDA")}
        technical = {"NVDA": self.technical_series("NVDA")}
        reports = {"NVDA": self.report("NVDA", hit_rate=1.0, resolved=3, hit=3, miss=0)}
        service, _runner = self.service(price, technical, reports)

        result = service.scan(["NVDA"], self.config())

        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.matched_candidates[0].sample_size_status, SampleSizeStatus.BELOW_PREFERRED_MINIMUM)

    def test_ranking_prefers_established_sample_over_small_perfect_sample(self):
        small = self.candidate("AAA", hit_rate=1.0, resolved=3)
        established = self.candidate("BBB", hit_rate=0.7, resolved=100)

        ranked = rank_swing_candidates((small, established))

        self.assertEqual([candidate.symbol for candidate in ranked], ["BBB", "AAA"])

    def test_same_tier_higher_hit_rate_first(self):
        lower = self.candidate("AAA", hit_rate=0.7, resolved=100)
        higher = self.candidate("BBB", hit_rate=0.8, resolved=100)

        ranked = rank_swing_candidates((lower, higher))

        self.assertEqual(ranked[0].symbol, "BBB")

    def test_hit_rate_tie_resolved_count_first(self):
        fewer = self.candidate("AAA", hit_rate=0.8, resolved=30)
        more = self.candidate("BBB", hit_rate=0.8, resolved=80)

        ranked = rank_swing_candidates((fewer, more))

        self.assertEqual(ranked[0].symbol, "BBB")

    def test_mae_tie_break_descending_without_abs(self):
        shallow_mae = self.candidate("AAA", hit_rate=0.8, resolved=80, mae=-0.02)
        deep_mae = self.candidate("BBB", hit_rate=0.8, resolved=80, mae=-0.08)

        ranked = rank_swing_candidates((deep_mae, shallow_mae))

        self.assertEqual(ranked[0].symbol, "AAA")

    def test_mfe_tie_break_descending(self):
        low_mfe = self.candidate("AAA", hit_rate=0.8, resolved=80, mae=-0.02, mfe=0.05)
        high_mfe = self.candidate("BBB", hit_rate=0.8, resolved=80, mae=-0.02, mfe=0.12)

        ranked = rank_swing_candidates((low_mfe, high_mfe))

        self.assertEqual(ranked[0].symbol, "BBB")

    def test_end_return_tie_break_descending(self):
        low_end = self.candidate("AAA", hit_rate=0.8, resolved=80, mae=-0.02, mfe=0.12, end_return=0.01)
        high_end = self.candidate("BBB", hit_rate=0.8, resolved=80, mae=-0.02, mfe=0.12, end_return=0.04)

        ranked = rank_swing_candidates((low_end, high_end))

        self.assertEqual(ranked[0].symbol, "BBB")

    def test_symbol_final_tie_is_ascending(self):
        b = self.candidate("BBB", hit_rate=0.8, resolved=80, mae=-0.02, mfe=0.12, end_return=0.04)
        a = self.candidate("AAA", hit_rate=0.8, resolved=80, mae=-0.02, mfe=0.12, end_return=0.04)

        ranked = rank_swing_candidates((b, a))

        self.assertEqual([candidate.symbol for candidate in ranked], ["AAA", "BBB"])

    def test_none_hit_rate_sorts_after_zero_hit_rate_in_same_no_resolved_tier(self):
        none_hit_rate = self.candidate("AAA", hit_rate=None, resolved=0)
        zero_hit_rate = self.candidate("BBB", hit_rate=0.0, resolved=0)

        ranked = rank_swing_candidates((none_hit_rate, zero_hit_rate))

        self.assertEqual(ranked[0].symbol, "BBB")

    def test_input_order_does_not_change_candidate_ranking(self):
        price = {
            "AAA": self.price_series("AAA"),
            "BBB": self.price_series("BBB"),
        }
        technical = {
            "AAA": self.technical_series("AAA"),
            "BBB": self.technical_series("BBB"),
        }
        reports = {
            "AAA": self.report("AAA", hit_rate=1.0, resolved=3, hit=3, miss=0),
            "BBB": self.report("BBB", hit_rate=0.7, resolved=100, hit=70, miss=30),
        }
        service, _runner = self.service(price, technical, reports)

        first = service.scan(["AAA", "BBB"], self.config())
        second = service.scan(["BBB", "AAA"], self.config())

        self.assertEqual(
            [candidate.symbol for candidate in first.matched_candidates],
            [candidate.symbol for candidate in second.matched_candidates],
        )

    def test_ranking_assigns_one_based_research_rank(self):
        ranked = rank_swing_candidates((self.candidate("BBB"), self.candidate("AAA")))

        self.assertEqual([candidate.research_rank for candidate in ranked], [1, 2])

    def test_rank_policy_version_is_stable(self):
        candidate = self.candidate("AAA")

        self.assertEqual(candidate.research_rank_policy, SWING_RESEARCH_RANK_POLICY_V1)

    def test_rank_components_expose_raw_metrics(self):
        candidate = self.candidate("AAA")

        components = get_candidate_rank_components(candidate)

        self.assertEqual([component.name for component in components], [
            "sample_size_status",
            "historical_hit_rate",
            "resolved_count",
            "median_max_adverse_return",
            "median_max_close_return",
            "median_end_return",
            "symbol",
        ])

    def test_config_id_is_deterministic_and_omits_generated_at(self):
        first = self.config()
        second = self.config()

        self.assertEqual(first.scanner_config_id, second.scanner_config_id)
        self.assertTrue(first.scanner_config_id.startswith("swing_scanner_"))

    def test_config_id_changes_with_overlap_policy(self):
        allow_all = self.config()
        cooldown = self.config(
            overlap_policy=OverlappingSignalPolicy.COOLDOWN,
            cooldown_bars=20,
        )

        self.assertNotEqual(allow_all.scanner_config_id, cooldown.scanner_config_id)

    def test_allow_all_limitation_mentions_overlap(self):
        candidate = self.candidate("AAA")

        self.assertIn("may overlap", " ".join(candidate.limitations))

    def test_cooldown_limitation_mentions_not_independent(self):
        config = self.config(
            overlap_policy=OverlappingSignalPolicy.COOLDOWN,
            cooldown_bars=20,
        )
        snapshot = self.snapshot(symbol="AAA")
        match = evaluate_signal_conditions(snapshot, config.signal_definition)
        candidate = build_swing_candidate(
            signal_match=match,
            technical_series=self.technical_series(symbol="AAA", snapshot=snapshot),
            report=self.report("AAA", config=config.to_backtest_config()),
            config=config,
        )

        self.assertIn("does not guarantee statistical independence", " ".join(candidate.limitations))

    def test_config_rejects_invalid_cooldown(self):
        with self.assertRaises(ValueError):
            self.config(overlap_policy=OverlappingSignalPolicy.COOLDOWN, cooldown_bars=0)

    def test_candidate_model_is_frozen(self):
        candidate = self.candidate("AAA")

        with self.assertRaises(Exception):
            candidate.symbol = "BBB"

    def test_result_timestamp_is_timezone_aware_utc(self):
        service, _runner = self.service({}, {}, {})

        result = service.scan([], self.config())

        self.assertEqual(result.generated_at.tzinfo, UTC)

    def test_no_probability_or_confidence_score_fields(self):
        field_names = {field.name for field in fields(SwingOpportunityCandidate)}

        self.assertNotIn("probability", field_names)
        self.assertNotIn("prediction_score", field_names)
        self.assertNotIn("confidence_score", field_names)


if __name__ == "__main__":
    unittest.main()
