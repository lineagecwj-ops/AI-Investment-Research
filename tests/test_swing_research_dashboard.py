import sys
import unittest
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

from backtest_service import HistoricalBacktestCase
from backtest_service import HistoricalBacktestReport
from historical_case_service import HistoricalCaseDataError
from models import EvaluatedSignalCondition
from models import HistoricalOutcomeResult
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeEvaluationStatus
from models import OutcomeDefinition
from models import OutcomeType
from models import OverlappingSignalPolicy
from models import SignalConditionOperator
from models import SignalDefinition
from models import SignalEvaluationStatus
from models import SignalEvent
from models import TechnicalIndicatorSeries
from models import TechnicalIndicatorSnapshot
from models import TechnicalSignalCondition
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import evaluate_signal_conditions
from swing_research_dashboard import CASE_PREVIEW_LIMIT
from swing_research_dashboard import CURRENT_SCAN_MODE
from swing_research_dashboard import HISTORICAL_REPLAY_MODE
from swing_research_dashboard import WALK_FORWARD_REPLAY_MODE
from swing_research_dashboard import build_candidate_table_rows
from swing_research_dashboard import build_case_preview_count_rows
from swing_research_dashboard import build_case_preview_views
from swing_research_dashboard import build_condition_trace_rows
from swing_research_dashboard import build_failure_rows
from swing_research_dashboard import build_no_match_rows
from swing_research_dashboard import build_not_evaluable_rows
from swing_research_dashboard import build_replay_candidate_table_rows
from swing_research_dashboard import build_replay_summary_rows
from swing_research_dashboard import build_scan_summary_rows
from swing_research_dashboard import build_swing_research_fingerprint
from swing_research_dashboard import build_beginner_indicator_explanations
from swing_research_dashboard import build_technical_condition_detail_rows
from swing_research_dashboard import build_technical_condition_detail_view
from swing_research_dashboard import build_technical_condition_visualization_rows
from swing_research_dashboard import build_technical_condition_developer_rows
from swing_research_dashboard import build_technical_snapshot_rows
from swing_research_dashboard import build_walk_forward_outcome_count_rows
from swing_research_dashboard import build_replay_analytics_candidate_set_rows
from swing_research_dashboard import build_walk_forward_summary_rows
from swing_research_dashboard import build_walk_forward_symbol_summary_rows
from swing_research_dashboard import build_walk_forward_timeline_rows
from swing_research_dashboard import candidate_selector_label
from swing_research_dashboard import current_match_trace_is_consistent
from swing_research_dashboard import filter_case_preview_views
from swing_research_dashboard import fingerprint_from_config
from swing_research_dashboard import format_percentage
from swing_research_dashboard import latest_case_preview_rows
from swing_research_dashboard import post_replay_outcome_rows
from swing_research_dashboard import parse_swing_symbol_input
from swing_research_dashboard import replay_candidate_selector_label
from swing_research_dashboard import replay_fingerprint_from_config
from swing_research_dashboard import sample_status_label
from swing_research_dashboard import technical_detail_selector_matches
from swing_research_dashboard import technical_detail_result_is_stale
from swing_research_dashboard import walk_forward_fingerprint_from_config
from swing_research_dashboard import walk_forward_period_selector_label
from historical_replay_service import HistoricalReplayConfig
from historical_replay_service import HistoricalReplayResult
from historical_replay_service import build_historical_replay_candidate
from historical_replay_service import build_point_in_time_backtest_summary
from swing_scanner_service import SampleSizeStatus
from swing_scanner_service import SwingScannerConfig
from swing_scanner_service import SwingScannerResult
from swing_scanner_service import build_swing_candidate
from swing_scanner_service import rank_swing_candidates
from walk_forward_replay_service import WalkForwardReplayConfig
from walk_forward_replay_service import WalkForwardReplayFrequency
from walk_forward_replay_service import WalkForwardReplayPeriod
from walk_forward_replay_service import WalkForwardReplayResult
from walk_forward_replay_service import summarize_walk_forward_periods


FETCHED_AT = datetime(2026, 8, 8, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 8, 2, 0, tzinfo=UTC)


class SwingResearchDashboardTestCase(unittest.TestCase):

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
            ),
            minimum_required_features=("analysis_close", "sma_20", "sma_60"),
            description="Test-only signal.",
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

    def snapshot(self, symbol="TEST", trading_date=date(2025, 1, 3), **overrides):
        params = {field.name: None for field in fields(TechnicalIndicatorSnapshot)}
        params.update(
            symbol=symbol,
            trading_date=trading_date,
            analysis_close=110.0,
            sma_20=100.0,
            sma_60=90.0,
            sma_120=80.0,
            sma_200=70.0,
            rsi_14=61.0,
            macd=1.2,
            macd_signal=0.8,
            atr_14_pct=0.03,
            volume_ratio_20=1.4,
            return_20d=0.05,
            return_60d=0.12,
            prior_high_60d=115.0,
            distance_to_prior_60d_high=-0.04,
        )
        params.update(overrides)
        return TechnicalIndicatorSnapshot(**params)

    def technical_series(self, symbol="TEST", snapshot=None):
        return TechnicalIndicatorSeries(
            symbol=symbol,
            snapshots=(snapshot or self.snapshot(symbol=symbol),),
            generated_at=GENERATED_AT,
            source_price_fetched_at=FETCHED_AT,
            source_price_is_stale=False,
        )

    def price_series(self, symbol="TEST"):
        bars = tuple(
            HistoricalPriceBar(
                symbol=symbol,
                trading_date=date(2025, 1, day),
                open=100.0 + day,
                high=104.0 + day,
                low=98.0 + day,
                close=101.0 + day,
                adjusted_close=101.0 + day,
                volume=1000 + day,
            )
            for day in range(1, 7)
        )
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="USD",
            bars=bars,
            fetched_at=FETCHED_AT,
            is_stale=False,
        )

    def condition(self):
        return EvaluatedSignalCondition(
            metric="analysis_close",
            actual_value=110.0,
            operator=SignalConditionOperator.GREATER_THAN,
            expected_value=None,
            secondary_metric="sma_20",
            secondary_actual_value=100.0,
            status=SignalEvaluationStatus.MATCH,
            matched=True,
        )

    def signal_event(self, symbol="TEST", signal_date=date(2025, 1, 3)):
        return SignalEvent(
            symbol=symbol,
            signal_id=self.signal_definition().id,
            signal_date=signal_date,
            signal_analysis_close=103.0,
            signal_raw_close=103.0,
            reference_high=110.0,
            reference_low=80.0,
            evaluation_status=SignalEvaluationStatus.MATCH,
            feature_snapshot=self.snapshot(symbol=symbol, trading_date=signal_date),
            evaluated_conditions=(self.condition(),),
        )

    def outcome(self, status, symbol="TEST", signal_date=date(2025, 1, 3)):
        is_hit = status is OutcomeEvaluationStatus.HIT
        return HistoricalOutcomeResult(
            symbol=symbol,
            signal_id=self.signal_definition().id,
            signal_date=signal_date,
            outcome_definition_id=self.outcome_definition().id,
            status=status,
            horizon_bars=20,
            available_future_bars=20,
            reference_high=110.0,
            intraday_target_hit=is_hit,
            intraday_target_hit_date=date(2025, 1, 4) if is_hit else None,
            intraday_target_hit_bar_index=1 if is_hit else None,
            close_target_hit=False,
            close_target_hit_date=None,
            close_target_hit_bar_index=None,
            max_close_return=0.10,
            max_close_return_date=date(2025, 1, 5),
            max_adverse_return=-0.04,
            max_adverse_return_date=date(2025, 1, 4),
            end_of_window_return=-0.02,
        )

    def replay_config(self, **overrides):
        values = {
            "replay_date": date(2024, 6, 30),
            "signal_definition": self.signal_definition(),
            "outcome_definition": self.outcome_definition(),
            "overlap_policy": OverlappingSignalPolicy.ALLOW_ALL,
            "cooldown_bars": None,
            "historical_start_date": date(2018, 1, 1),
            "preferred_resolved_samples": 20,
        }
        values.update(overrides)
        return HistoricalReplayConfig(**values)

    def replay_candidate(self, symbol="TEST"):
        config = self.replay_config()
        snapshot = self.snapshot(symbol=symbol, trading_date=date(2024, 6, 28))
        signal_match = evaluate_signal_conditions(snapshot, config.signal_definition)
        price_series = HistoricalPriceSeries(
            symbol=symbol,
            currency="USD",
            bars=(
                HistoricalPriceBar(symbol=symbol, trading_date=date(2024, 6, 28), open=100, high=120, low=90, close=110, adjusted_close=110, volume=1000),
                HistoricalPriceBar(symbol=symbol, trading_date=date(2024, 7, 1), open=111, high=130, low=100, close=120, adjusted_close=120, volume=1000),
            ),
            fetched_at=FETCHED_AT,
        )
        summary = build_point_in_time_backtest_summary(
            tuple(),
            price_series=price_series,
            config=config,
            actual_signal_date=date(2024, 6, 28),
        )
        return build_historical_replay_candidate(
            signal_match=signal_match,
            summary=summary,
            post_replay_outcome=self.outcome(OutcomeEvaluationStatus.HIT, symbol=symbol, signal_date=date(2024, 6, 28)),
            price_series=price_series,
            config=config,
        )

    def walk_forward_config(self, **overrides):
        values = {
            "start_date": date(2024, 1, 1),
            "end_date": date(2024, 2, 29),
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

    def walk_forward_result(self):
        jan = date(2024, 1, 31)
        feb = date(2024, 2, 29)
        jan_candidate = replace(self.replay_candidate("AAPL"), requested_replay_date=jan)
        feb_candidate_a = replace(self.replay_candidate("AAPL"), requested_replay_date=feb)
        feb_candidate_b = replace(
            self.replay_candidate("MSFT"),
            requested_replay_date=feb,
            post_replay_outcome=self.outcome(OutcomeEvaluationStatus.MISS, symbol="MSFT", signal_date=feb),
        )
        periods = (
            WalkForwardReplayPeriod(
                requested_replay_date=jan,
                replay_result=HistoricalReplayResult(
                    config=self.replay_config(replay_date=jan),
                    requested_symbols=("AAPL", "MSFT"),
                    normalized_symbols=("AAPL", "MSFT"),
                    match_candidates=(jan_candidate,),
                    no_match_symbols=("MSFT",),
                    no_match_details=tuple(),
                    not_evaluable_symbols=tuple(),
                    failed_symbols=tuple(),
                    generated_at=GENERATED_AT,
                ),
            ),
            WalkForwardReplayPeriod(
                requested_replay_date=feb,
                replay_result=HistoricalReplayResult(
                    config=self.replay_config(replay_date=feb),
                    requested_symbols=("AAPL", "MSFT"),
                    normalized_symbols=("AAPL", "MSFT"),
                    match_candidates=(feb_candidate_a, feb_candidate_b),
                    no_match_symbols=tuple(),
                    no_match_details=tuple(),
                    not_evaluable_symbols=tuple(),
                    failed_symbols=tuple(),
                    generated_at=GENERATED_AT,
                ),
            ),
        )
        return WalkForwardReplayResult(
            config=self.walk_forward_config(),
            requested_symbols=("AAPL", "MSFT"),
            normalized_symbols=("AAPL", "MSFT"),
            replay_dates=(jan, feb),
            period_results=periods,
            summary=summarize_walk_forward_periods(periods),
            generated_at=GENERATED_AT,
            walk_forward_id="walk_forward_test",
        )

    def report(self, symbol="TEST", *, hit_rate=0.7, resolved=100, cases=tuple()):
        config = self.config()
        hit = int(hit_rate * resolved) if hit_rate is not None else 0
        miss = resolved - hit
        return HistoricalBacktestReport(
            symbol=symbol,
            signal_definition_id=config.signal_definition.id,
            outcome_definition_id=config.outcome_definition.id,
            overlap_policy=config.overlap_policy,
            cooldown_bars=config.cooldown_bars,
            start_date=config.backtest_start_date,
            end_date=config.backtest_end_date,
            backtest_id=f"backtest_{symbol}",
            raw_signal_count=120,
            filtered_signal_count=100,
            hit_count=hit,
            miss_count=miss,
            incomplete_count=1,
            not_evaluable_count=2,
            resolved_count=resolved,
            historical_hit_rate=hit_rate,
            average_max_close_return=0.11,
            median_max_close_return=0.10,
            average_max_adverse_return=-0.05,
            median_max_adverse_return=-0.04,
            average_end_return=0.02,
            median_end_return=-0.02,
            average_hit_bar_index=3.0,
            median_hit_bar_index=3.0,
            max_return_sample_count=resolved,
            max_adverse_sample_count=resolved,
            end_return_sample_count=resolved,
            hit_bar_sample_count=hit,
            raw_events=tuple(),
            evaluated_events=tuple(),
            cases=cases,
            generated_at=GENERATED_AT,
        )

    def candidate(self, symbol, *, hit_rate=0.7, resolved=100):
        config = self.config()
        snapshot = self.snapshot(symbol=symbol)
        signal_match = evaluate_signal_conditions(snapshot, config.signal_definition)
        return build_swing_candidate(
            signal_match=signal_match,
            technical_series=self.technical_series(symbol=symbol, snapshot=snapshot),
            report=self.report(symbol=symbol, hit_rate=hit_rate, resolved=resolved),
            config=config,
        )

    def result(self, candidates=tuple(), **overrides):
        values = {
            "config": self.config(),
            "requested_symbols": ("2330", "2330.TW", "NVDA"),
            "normalized_symbols": ("2330.TW", "NVDA"),
            "matched_candidates": tuple(candidates),
            "no_match_symbols": ("AAPL",),
            "no_match_details": tuple(),
            "not_evaluable_symbols": tuple(),
            "failed_symbols": tuple(),
            "generated_at": GENERATED_AT,
        }
        values.update(overrides)
        return SwingScannerResult(**values)

    def legacy_result_without_current_signal_details(self, **overrides):
        class LegacySwingScannerResult:
            @property
            def requested_count(self):
                return len(self.requested_symbols)

            @property
            def scanned_count(self):
                return len(self.normalized_symbols)

            @property
            def matched_count(self):
                return len(self.matched_candidates)

            @property
            def no_match_count(self):
                return len(self.no_match_symbols)

            @property
            def not_evaluable_count(self):
                return len(self.not_evaluable_symbols)

            @property
            def failure_count(self):
                return len(self.failed_symbols)

        legacy = LegacySwingScannerResult()
        values = {
            "config": self.config(),
            "requested_symbols": ("2330", "0050"),
            "normalized_symbols": ("2330.TW", "0050.TW"),
            "matched_candidates": tuple(),
            "no_match_symbols": ("2330.TW", "0050.TW"),
            "no_match_details": tuple(),
            "not_evaluable_symbols": tuple(),
            "failed_symbols": tuple(),
            "generated_at": GENERATED_AT,
        }
        values.update(overrides)
        for name, value in values.items():
            setattr(legacy, name, value)
        return legacy

    def test_symbol_input_supports_newlines_commas_and_dedupes(self):
        self.assertEqual(
            parse_swing_symbol_input("2330\n2330.TW, NVDA；6488.TWO"),
            ("2330.TW", "NVDA", "6488.TWO"),
        )

    def test_fingerprint_changes_for_symbols_overlap_range_and_preferred_n(self):
        base = build_swing_research_fingerprint(
            normalized_symbols=("2330.TW",),
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
            preferred_sample_minimum=20,
        )
        changed_symbols = build_swing_research_fingerprint(
            normalized_symbols=("2454.TW",),
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
            preferred_sample_minimum=20,
        )
        changed_policy = build_swing_research_fingerprint(
            normalized_symbols=("2330.TW",),
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="COOLDOWN",
            cooldown_bars=20,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
            preferred_sample_minimum=20,
        )
        changed_range = build_swing_research_fingerprint(
            normalized_symbols=("2330.TW",),
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2019, 1, 1),
            end_date=date(2025, 12, 31),
            preferred_sample_minimum=20,
        )
        changed_minimum = build_swing_research_fingerprint(
            normalized_symbols=("2330.TW",),
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
            preferred_sample_minimum=30,
        )

        self.assertNotEqual(base, changed_symbols)
        self.assertNotEqual(base, changed_policy)
        self.assertNotEqual(base, changed_range)
        self.assertNotEqual(base, changed_minimum)

    def test_fingerprint_changes_for_source_mode(self):
        manual = build_swing_research_fingerprint(
            normalized_symbols=("2330.TW",),
            source_type="Manual Input",
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
            preferred_sample_minimum=20,
        )
        saved_universe = build_swing_research_fingerprint(
            normalized_symbols=("2330.TW",),
            source_type="Saved Universe",
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
            preferred_sample_minimum=20,
        )

        self.assertNotEqual(manual, saved_universe)

    def test_fingerprint_changes_for_scan_mode_and_replay_date(self):
        current = build_swing_research_fingerprint(
            normalized_symbols=("2330.TW",),
            source_type="Manual Input",
            scan_mode=CURRENT_SCAN_MODE,
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
            preferred_sample_minimum=20,
        )
        replay = build_swing_research_fingerprint(
            normalized_symbols=("2330.TW",),
            source_type="Manual Input",
            scan_mode=HISTORICAL_REPLAY_MODE,
            replay_date=date(2024, 6, 30),
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=None,
            preferred_sample_minimum=20,
        )
        replay_next_day = build_swing_research_fingerprint(
            normalized_symbols=("2330.TW",),
            source_type="Manual Input",
            scan_mode=HISTORICAL_REPLAY_MODE,
            replay_date=date(2024, 7, 1),
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=None,
            preferred_sample_minimum=20,
        )

        self.assertNotEqual(current, replay)
        self.assertNotEqual(replay, replay_next_day)

    def test_universe_content_change_changes_fingerprint(self):
        first = build_swing_research_fingerprint(
            normalized_symbols=("2330.TW", "2454.TW"),
            source_type="Saved Universe",
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
            preferred_sample_minimum=20,
        )
        edited = build_swing_research_fingerprint(
            normalized_symbols=("2330.TW", "2454.TW", "NVDA"),
            source_type="Saved Universe",
            signal_id="signal",
            outcome_id="outcome",
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
            preferred_sample_minimum=20,
        )

        self.assertNotEqual(first, edited)

    def test_fingerprint_from_config_uses_scanner_config_values(self):
        config = self.config()
        self.assertEqual(
            fingerprint_from_config(("2330.TW",), config),
            build_swing_research_fingerprint(
                normalized_symbols=("2330.TW",),
                signal_id=config.signal_definition.id,
                outcome_id=config.outcome_definition.id,
                overlap_policy=config.overlap_policy.value,
                cooldown_bars=config.cooldown_bars,
                start_date=config.backtest_start_date,
                end_date=config.backtest_end_date,
                preferred_sample_minimum=config.minimum_resolved_samples,
            ),
        )

    def test_replay_fingerprint_from_config_uses_replay_config_values(self):
        config = self.replay_config()

        self.assertEqual(
            replay_fingerprint_from_config(("2330.TW",), config),
            build_swing_research_fingerprint(
                normalized_symbols=("2330.TW",),
                scan_mode=HISTORICAL_REPLAY_MODE,
                replay_date=config.replay_date,
                signal_id=config.signal_definition.id,
                outcome_id=config.outcome_definition.id,
                overlap_policy=config.overlap_policy.value,
                cooldown_bars=config.cooldown_bars,
                start_date=config.historical_start_date,
                end_date=None,
                preferred_sample_minimum=config.preferred_resolved_samples,
            ),
        )

    def test_percentage_formatter(self):
        self.assertEqual(format_percentage(0.72), "72.00%")
        self.assertEqual(format_percentage(-0.08), "-8.00%")
        self.assertEqual(format_percentage(None), "N/A")

    def test_sample_status_labels_are_neutral(self):
        self.assertEqual(sample_status_label(SampleSizeStatus.BELOW_PREFERRED_MINIMUM), "低於偏好最低樣本數")
        self.assertNotIn("confidence", sample_status_label(SampleSizeStatus.BELOW_PREFERRED_MINIMUM).lower())

    def test_candidate_table_uses_service_order_and_display_fields(self):
        small = self.candidate("SMALL", hit_rate=1.0, resolved=3)
        large = self.candidate("LARGE", hit_rate=0.7, resolved=100)
        ranked = rank_swing_candidates((small, large))

        rows = build_candidate_table_rows(ranked)

        self.assertEqual(rows[0]["股票"], "LARGE")
        self.assertEqual(rows[0]["研究優先順序"], 1)
        self.assertEqual(rows[0]["歷史命中率"], "70.00%")
        self.assertEqual(rows[0]["已解析歷史樣本數"], 100)
        self.assertEqual(rows[0]["歷史中位最大有利變動"], "10.00%")
        self.assertEqual(rows[0]["歷史中位最大不利變動"], "-4.00%")
        self.assertEqual(rows[0]["歷史期末中位變動"], "-2.00%")
        self.assertEqual(rows[1]["樣本狀態"], "低於偏好最低樣本數")

    def test_replay_summary_rows_match_current_scan_counts(self):
        candidate = self.replay_candidate()
        result = HistoricalReplayResult(
            config=self.replay_config(),
            requested_symbols=("TEST", "AAPL"),
            normalized_symbols=("TEST", "AAPL"),
            match_candidates=(candidate,),
            no_match_symbols=("AAPL",),
            no_match_details=tuple(),
            not_evaluable_symbols=tuple(),
            failed_symbols=tuple(),
            generated_at=GENERATED_AT,
        )

        rows = build_replay_summary_rows(result)

        self.assertEqual([row["Metric"] for row in rows], ["已掃描", "符合條件", "不符合條件", "資料不足", "掃描失敗"])
        self.assertEqual([row["Value"] for row in rows], [2, 1, 1, 0, 0])

    def test_replay_candidate_table_uses_as_of_labels_and_post_outcome(self):
        candidate = self.replay_candidate()

        row = build_replay_candidate_table_rows((candidate,))[0]

        self.assertEqual(row["指定回放日期"], "2024-06-30")
        self.assertEqual(row["實際使用交易日"], "2024-06-28")
        self.assertIn("回放當時可知歷史命中率", row)
        self.assertIn("回放當時可知已解析樣本數", row)
        self.assertEqual(row["回放日期後的實際歷史結果"], "達成研究目標（HIT）")
        self.assertNotIn("Replay Probability", row)

    def test_replay_candidate_selector_uses_as_of_n_and_actual_date(self):
        candidate = self.replay_candidate()

        label = replay_candidate_selector_label(candidate)

        self.assertIn("TEST", label)
        self.assertIn("n=0", label)
        self.assertIn("Actual=2024-06-28", label)

    def test_post_replay_outcome_rows_are_separate_from_research_priority(self):
        rows = post_replay_outcome_rows(self.replay_candidate())
        labels = [row["Metric"] for row in rows]

        self.assertIn("回放日期後的實際歷史結果", labels)
        self.assertIn("首次達標日期", labels)
        self.assertNotIn("Prediction Result", labels)

    def test_walk_forward_fingerprint_uses_range_frequency_and_historical_start(self):
        config = self.walk_forward_config()

        self.assertEqual(
            walk_forward_fingerprint_from_config(("AAPL",), config),
            build_swing_research_fingerprint(
                normalized_symbols=("AAPL",),
                scan_mode=WALK_FORWARD_REPLAY_MODE,
                frequency="MONTHLY",
                signal_id=config.signal_definition.id,
                outcome_id=config.outcome_definition.id,
                overlap_policy=config.overlap_policy.value,
                cooldown_bars=config.cooldown_bars,
                start_date=config.start_date,
                end_date=config.end_date,
                historical_start_date=config.historical_start_date,
                preferred_sample_minimum=config.preferred_resolved_samples,
            ),
        )

    def test_current_replay_and_walk_forward_fingerprints_are_distinct(self):
        current = build_swing_research_fingerprint(
            normalized_symbols=("AAPL",),
            scan_mode=CURRENT_SCAN_MODE,
            signal_id=self.signal_definition().id,
            outcome_id=self.outcome_definition().id,
            overlap_policy="ALLOW_ALL",
            cooldown_bars=None,
            start_date=date(2018, 1, 1),
            end_date=date(2025, 12, 31),
            preferred_sample_minimum=20,
        )
        replay = replay_fingerprint_from_config(("AAPL",), self.replay_config())
        walk_forward = walk_forward_fingerprint_from_config(("AAPL",), self.walk_forward_config())

        self.assertNotEqual(current, replay)
        self.assertNotEqual(replay, walk_forward)
        self.assertNotEqual(current, walk_forward)

    def test_walk_forward_summary_rows_use_kpis_without_accuracy(self):
        rows = build_walk_forward_summary_rows(self.walk_forward_result())
        labels = [row["Metric"] for row in rows]

        self.assertEqual(
            labels,
            [
                "回放期數",
                "有研究候選的期間",
                "沒有研究候選的期間",
                "不重複候選股票數",
                "候選出現次數",
                "候選出現期間比例",
            ],
        )
        self.assertNotIn("Prediction Accuracy", labels)

    def test_walk_forward_outcome_rows_are_counts_only(self):
        rows = build_walk_forward_outcome_count_rows(self.walk_forward_result())
        labels = [row["Metric"] for row in rows]

        self.assertIn("回放後達成研究目標", labels)
        self.assertIn("回放後未達研究目標", labels)
        self.assertNotIn("Walk-Forward Hit Rate", labels)

    def test_walk_forward_timeline_rows_show_period_counts_and_candidates(self):
        rows = build_walk_forward_timeline_rows(self.walk_forward_result())

        self.assertEqual(rows[0]["回放日期"], "2024-01-31")
        self.assertEqual(rows[0]["候選數"], 1)
        self.assertEqual(rows[0]["不符合條件"], 1)
        self.assertEqual(rows[0]["候選股票"], "AAPL")
        self.assertEqual(rows[1]["候選股票"], "AAPL, MSFT")

    def test_walk_forward_period_selector_label_is_concise(self):
        period = self.walk_forward_result().period_results[0]

        self.assertEqual(walk_forward_period_selector_label(period), "2024-01-31 | 符合條件 1")

    def test_walk_forward_symbol_summary_rows_show_candidate_frequency(self):
        rows = build_walk_forward_symbol_summary_rows(self.walk_forward_result())
        aapl = rows[0]

        self.assertEqual(aapl["股票"], "AAPL")
        self.assertEqual(aapl["候選出現次數"], 2)
        self.assertEqual(aapl["候選出現期間比例"], "100.00%")
        self.assertEqual(aapl["首次出現日期"], "2024-01-31")
        self.assertEqual(aapl["最後出現日期"], "2024-02-29")
        self.assertEqual(aapl["最長連續出現期數"], 2)
        self.assertIn("回放後達成研究目標", aapl)
        self.assertNotIn("Hit Probability", aapl)

    def test_walk_forward_candidate_set_stability_rows_are_descriptive(self):
        rows = build_replay_analytics_candidate_set_rows(self.walk_forward_result())

        self.assertEqual(rows[0]["前一回放日期"], "2024-01-31")
        self.assertEqual(rows[0]["目前回放日期"], "2024-02-29")
        self.assertEqual(rows[0]["共同候選數"], 1)
        self.assertEqual(rows[0]["候選名單相似度"], "50.00%")
        self.assertEqual(rows[0]["候選名單變動率"], "50.00%")

    def test_candidate_selector_shows_hit_rate_and_resolved_n(self):
        self.assertEqual(
            candidate_selector_label(self.candidate("TEST", hit_rate=1.0, resolved=3)),
            "TEST | 100.00% | n=3",
        )

    def test_zero_match_summary_is_safe(self):
        result = self.result()
        rows = build_scan_summary_rows(result)

        self.assertEqual(rows[1], {"Metric": "符合條件", "Value": 0})
        self.assertEqual(build_candidate_table_rows(result.matched_candidates), [])

    def test_condition_trace_comes_from_signal_match(self):
        candidate = self.candidate("TEST")
        rows = build_condition_trace_rows(candidate.signal_match)

        self.assertEqual(rows[0]["條件"], "分析價格")
        self.assertEqual(rows[0]["Operator"], ">")
        self.assertEqual(rows[0]["Expected / Secondary"], "20 日均線")
        self.assertEqual(rows[0]["Status"], "符合")
        self.assertTrue(current_match_trace_is_consistent(candidate.signal_match))

    def test_inconsistent_current_match_trace_is_detected(self):
        candidate = self.candidate("TEST")
        condition = replace(
            candidate.signal_match.evaluated_conditions[0],
            status=SignalEvaluationStatus.NO_MATCH,
            matched=False,
        )
        signal_match = replace(candidate.signal_match, evaluated_conditions=(condition,))

        self.assertFalse(current_match_trace_is_consistent(signal_match))

    def test_technical_snapshot_rows_include_required_current_metrics(self):
        rows = build_technical_snapshot_rows(self.snapshot())
        labels = [row["指標"] for row in rows]

        self.assertIn("20 日均線", labels)
        self.assertIn("RSI 14 日相對強弱指標", labels)
        self.assertIn("MACD 訊號線", labels)
        self.assertIn("距離前 60 日高點", labels)
        self.assertEqual(rows[-1]["Value"], "-4.00%")

    def test_technical_detail_uses_scan_time_values_and_condition_status(self):
        snapshot = self.snapshot(
            symbol="2330.TW",
            volume_ratio_20=1.08,
            rsi_14=58.3,
            distance_to_prior_60d_high=-0.072,
        )
        signal_match = evaluate_signal_conditions(snapshot, TECHNICAL_EXAMPLE_SIGNAL_V1)

        detail = build_technical_condition_detail_view(signal_match)

        self.assertEqual(detail.matched_count, 3)
        self.assertEqual(detail.total_count, 5)
        self.assertEqual(detail.condition_rows[2]["技術條件"], "20 日成交量比率")
        self.assertEqual(detail.condition_rows[2]["目前實際值"], "1.08")
        self.assertEqual(detail.condition_rows[2]["V1 要求"], ">= 1.20")
        self.assertEqual(detail.condition_rows[2]["狀態"], "不符合")
        self.assertEqual(detail.condition_rows[2]["距離門檻"], "尚差 0.12")
        self.assertEqual(detail.condition_rows[4]["目前實際值"], "-7.20%")
        self.assertEqual(detail.condition_rows[4]["V1 要求"], ">= -5.00%")
        self.assertEqual(detail.condition_rows[4]["距離門檻"], "尚差 2.20 percentage points")

    def test_technical_detail_supports_no_match_and_match_selector(self):
        match = evaluate_signal_conditions(self.snapshot(symbol="MATCH"), TECHNICAL_EXAMPLE_SIGNAL_V1)
        no_match = evaluate_signal_conditions(
            self.snapshot(symbol="NO_MATCH", volume_ratio_20=1.0),
            TECHNICAL_EXAMPLE_SIGNAL_V1,
        )
        result = self.result(
            candidates=tuple(),
            current_signal_details=(match, no_match),
            no_match_symbols=("NO_MATCH",),
        )

        selector_matches = technical_detail_selector_matches(result)

        self.assertEqual([item.symbol for item in selector_matches], ["MATCH", "NO_MATCH"])
        self.assertEqual(selector_matches[1].status, SignalEvaluationStatus.NO_MATCH)

    def test_technical_detail_selector_handles_legacy_result_without_current_signal_details(self):
        legacy = self.legacy_result_without_current_signal_details()

        self.assertTrue(technical_detail_result_is_stale(legacy))
        self.assertEqual(technical_detail_selector_matches(legacy), tuple())

    def test_technical_detail_falls_back_to_matched_candidates_for_older_results(self):
        candidate = self.candidate("MATCH")
        result = self.result(candidates=(candidate,), current_signal_details=tuple())

        self.assertEqual(technical_detail_selector_matches(result), (candidate.signal_match,))
        self.assertFalse(technical_detail_result_is_stale(result))

    def test_technical_detail_does_not_include_not_evaluable_or_failed_as_complete(self):
        not_evaluable = replace(
            evaluate_signal_conditions(self.snapshot(symbol="MISS"), TECHNICAL_EXAMPLE_SIGNAL_V1),
            status=SignalEvaluationStatus.NOT_EVALUABLE,
        )
        result = self.result(
            current_signal_details=(not_evaluable,),
            failed_symbols=tuple(),
        )

        self.assertEqual(technical_detail_selector_matches(result), tuple())

    def test_technical_detail_missing_metric_displays_na_without_crash(self):
        signal_match = evaluate_signal_conditions(
            self.snapshot(symbol="MISS", rsi_14=None),
            TECHNICAL_EXAMPLE_SIGNAL_V1,
        )

        rows = build_technical_condition_detail_rows(signal_match)

        self.assertEqual(rows[3]["技術條件"], "RSI 14")
        self.assertEqual(rows[3]["目前實際值"], "N/A")
        self.assertEqual(rows[3]["距離門檻"], "N/A")

    def test_technical_detail_visualization_rows_are_factual_markers(self):
        signal_match = evaluate_signal_conditions(self.snapshot(symbol="2330.TW"), TECHNICAL_EXAMPLE_SIGNAL_V1)

        rows = build_technical_condition_visualization_rows(signal_match)

        self.assertIn({"指標": "20 日成交量比率", "標記": "V1 門檻", "數值": 1.2, "說明": "1.20", "備註": "V1 threshold = 1.20"}, rows)
        self.assertIn({"指標": "距離前 60 日高點", "標記": "前 60 日高點", "數值": 0.0, "說明": "0.00%", "備註": "0% = prior 60-day high；-5% = V1 threshold"}, rows)

    def test_technical_detail_primary_rows_use_traditional_chinese_not_raw_snake_case(self):
        signal_match = evaluate_signal_conditions(self.snapshot(symbol="2330.TW"), TECHNICAL_EXAMPLE_SIGNAL_V1)

        rows = build_technical_condition_detail_rows(signal_match)
        joined = " ".join(" ".join(row.values()) for row in rows)

        self.assertIn("距離前 60 日高點", joined)
        self.assertIn("20 日成交量比率", joined)
        self.assertNotIn("volume_ratio_20", joined)
        self.assertNotIn("distance_to_prior_60d_high", joined)

    def test_developer_rows_keep_internal_ids_outside_primary_rows(self):
        signal_match = evaluate_signal_conditions(self.snapshot(symbol="2330.TW"), TECHNICAL_EXAMPLE_SIGNAL_V1)

        rows = build_technical_condition_developer_rows(signal_match)

        self.assertEqual(rows[0]["Signal ID"], "technical_example_v1")
        self.assertEqual(rows[0]["Raw Metric"], "analysis_close")

    def test_beginner_explanations_do_not_describe_future_probability(self):
        rows = build_beginner_indicator_explanations()
        joined = " ".join(row["說明"] for row in rows)

        self.assertIn("不代表預測上漲機率", joined)
        self.assertNotIn("買進", joined)
        self.assertNotIn("看漲", joined)

    def test_technical_detail_helper_does_not_refetch_rerun_scanner_or_backtest(self):
        source = (SRC_PATH / "swing_research_dashboard.py").read_text(encoding="utf-8")

        detail_source = source[source.index("def technical_detail_selector_matches"):]
        self.assertNotIn("get_historical_prices", detail_source)
        self.assertNotIn("scan_swing_opportunities", detail_source)
        self.assertNotIn("run_historical_backtest", detail_source)

    def test_technical_detail_helper_does_not_mutate_signal_match(self):
        signal_match = evaluate_signal_conditions(self.snapshot(symbol="2330.TW"), TECHNICAL_EXAMPLE_SIGNAL_V1)
        before = signal_match.evaluated_conditions

        build_technical_condition_detail_view(signal_match)

        self.assertEqual(signal_match.evaluated_conditions, before)

    def test_no_match_rows_show_failed_conditions(self):
        from swing_scanner_service import SwingScanCurrentSignalAudit

        result = self.result(
            no_match_details=(
                SwingScanCurrentSignalAudit(
                    symbol="AAPL",
                    status=SignalEvaluationStatus.NO_MATCH,
                    failed_conditions=("analysis_close",),
                ),
            )
        )

        self.assertEqual(build_no_match_rows(result)[0]["未符合的條件"], "分析價格")

    def test_not_evaluable_rows_show_missing_features(self):
        from swing_scanner_service import SwingScanCurrentSignalAudit

        result = self.result(
            not_evaluable_symbols=(
                SwingScanCurrentSignalAudit(
                    symbol="AAPL",
                    status=SignalEvaluationStatus.NOT_EVALUABLE,
                    missing_required_features=("sma_200",),
                ),
            )
        )

        self.assertEqual(build_not_evaluable_rows(result)[0]["缺少必要指標"], "200 日均線")

    def test_failure_rows_use_safe_error_fields(self):
        from swing_scanner_service import SwingScanFailure

        result = self.result(
            failed_symbols=(
                SwingScanFailure(symbol="FAIL", error_type="RuntimeError", message="provider unavailable"),
            )
        )

        self.assertEqual(build_failure_rows(result)[0]["Safe Message"], "provider unavailable")
        self.assertNotIn("traceback", build_failure_rows(result)[0]["Safe Message"].lower())

    def test_case_preview_uses_session_price_cache(self):
        hit_case = HistoricalBacktestCase(
            symbol="TEST",
            signal_event=self.signal_event(),
            outcome=self.outcome(OutcomeEvaluationStatus.HIT),
            case_id="case_hit",
        )
        miss_case = HistoricalBacktestCase(
            symbol="TEST",
            signal_event=self.signal_event(signal_date=date(2025, 1, 4)),
            outcome=self.outcome(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 4)),
            case_id="case_miss",
        )
        candidate = self.candidate("TEST")
        candidate = replace(candidate, historical_backtest_report=self.report(symbol="TEST", cases=(hit_case, miss_case)))

        views = build_case_preview_views(
            candidate=candidate,
            price_series_by_symbol={"TEST": self.price_series("TEST")},
        )

        self.assertEqual(len(views), 2)
        self.assertEqual({view.outcome_status for view in views}, {OutcomeEvaluationStatus.HIT, OutcomeEvaluationStatus.MISS})

    def test_case_preview_missing_price_cache_does_not_fetch(self):
        with self.assertRaises(HistoricalCaseDataError):
            build_case_preview_views(
                candidate=self.candidate("TEST"),
                price_series_by_symbol={},
            )

    def test_case_preview_filters_resolved_hit_and_miss(self):
        hit = replace(self.signal_event(), signal_date=date(2025, 1, 3))
        # Reuse built views from direct helper test shape for filter behavior.
        hit_case = HistoricalBacktestCase("TEST", hit, self.outcome(OutcomeEvaluationStatus.HIT), "hit")
        incomplete_case = HistoricalBacktestCase(
            "TEST",
            self.signal_event(signal_date=date(2025, 1, 4)),
            self.outcome(OutcomeEvaluationStatus.INCOMPLETE, signal_date=date(2025, 1, 4)),
            "incomplete",
        )
        candidate = replace(
            self.candidate("TEST"),
            historical_backtest_report=self.report(symbol="TEST", cases=(hit_case, incomplete_case)),
        )
        views = build_case_preview_views(candidate=candidate, price_series_by_symbol={"TEST": self.price_series("TEST")})

        self.assertEqual(len(filter_case_preview_views(views, "Resolved")), 1)
        self.assertEqual(filter_case_preview_views(views, "HIT")[0].outcome_status, OutcomeEvaluationStatus.HIT)
        self.assertEqual(filter_case_preview_views(views, "MISS"), tuple())

    def test_case_preview_count_rows(self):
        hit_case = HistoricalBacktestCase("TEST", self.signal_event(), self.outcome(OutcomeEvaluationStatus.HIT), "hit")
        miss_case = HistoricalBacktestCase(
            "TEST",
            self.signal_event(signal_date=date(2025, 1, 4)),
            self.outcome(OutcomeEvaluationStatus.MISS, signal_date=date(2025, 1, 4)),
            "miss",
        )
        candidate = replace(
            self.candidate("TEST"),
            historical_backtest_report=self.report(symbol="TEST", cases=(hit_case, miss_case)),
        )
        views = build_case_preview_views(candidate=candidate, price_series_by_symbol={"TEST": self.price_series("TEST")})

        self.assertEqual(build_case_preview_count_rows(views)[0], {"Metric": "達成研究目標案例", "Value": 1})
        self.assertEqual(build_case_preview_count_rows(views)[1], {"Metric": "未達研究目標案例", "Value": 1})

    def test_case_preview_limits_to_latest_five(self):
        views = tuple(
            replace(
                build_case_preview_views(
                    candidate=replace(
                        self.candidate("TEST"),
                        historical_backtest_report=self.report(
                            symbol="TEST",
                            cases=(
                                HistoricalBacktestCase(
                                    "TEST",
                                    self.signal_event(signal_date=date(2025, 1, day)),
                                    self.outcome(OutcomeEvaluationStatus.HIT, signal_date=date(2025, 1, day)),
                                    f"case_{day}",
                                ),
                            ),
                        ),
                    ),
                    price_series_by_symbol={"TEST": self.price_series("TEST")},
                )[0]
            )
            for day in range(1, 7)
        )

        limited = latest_case_preview_rows(views)

        self.assertEqual(len(limited), CASE_PREVIEW_LIMIT)
        self.assertEqual(limited[0].signal_date, date(2025, 1, 6))

    def test_helper_source_does_not_use_recommendation_or_probability_language(self):
        source = (SRC_PATH / "swing_research_dashboard.py").read_text(encoding="utf-8")

        self.assertNotIn("Buy Rank", source)
        self.assertNotIn("Opportunity Score", source)
        self.assertIn("不代表未來上漲機率", source)
        self.assertNotIn("confidence", source)


if __name__ == "__main__":
    unittest.main()
