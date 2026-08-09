import sys
import unittest
from dataclasses import FrozenInstanceError
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

from models import SignalEvaluationStatus
from models import TechnicalIndicatorSeries
from models import TechnicalIndicatorSnapshot
from signal_condition_diagnostics_service import ConditionDiagnosticObservation
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsConfig
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsError
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsService
from signal_condition_diagnostics_service import build_condition_diagnostic_observation
from signal_condition_diagnostics_service import summarize_condition_diagnostics
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import evaluate_signal_conditions


FETCHED_AT = datetime(2026, 8, 9, 1, 0, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 9, 2, 0, tzinfo=UTC)


class SignalConditionDiagnosticsServiceTestCase(unittest.TestCase):

    def config(self, **overrides):
        values = {
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 31),
            "signal_definition": TECHNICAL_EXAMPLE_SIGNAL_V1,
        }
        values.update(overrides)
        return HistoricalConditionDiagnosticsConfig(**values)

    def snapshot(self, symbol="TEST", trading_date=date(2025, 1, 10), **overrides):
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
            volume_ratio_20=1.5,
            rsi_14=60.0,
            distance_to_prior_60d_high=-0.02,
            prior_high_60d=110.0,
            prior_low_60d=80.0,
        )
        params.update(overrides)
        return TechnicalIndicatorSnapshot(**params)

    def series(self, symbol, snapshots):
        return TechnicalIndicatorSeries(
            symbol=symbol,
            snapshots=tuple(snapshots),
            generated_at=GENERATED_AT,
            source_price_fetched_at=FETCHED_AT,
        )

    def observation(self, symbol="TEST", trading_date=date(2025, 1, 10), **overrides):
        match = evaluate_signal_conditions(
            self.snapshot(symbol=symbol, trading_date=trading_date, **overrides),
            TECHNICAL_EXAMPLE_SIGNAL_V1,
        )
        return build_condition_diagnostic_observation(match)

    def fixture_series(self):
        return self.series(
            "TEST",
            (
                self.snapshot(trading_date=date(2024, 12, 31)),
                self.snapshot(trading_date=date(2025, 1, 1), analysis_close=80, sma_20=100, sma_60=110, volume_ratio_20=0.5, rsi_14=40, distance_to_prior_60d_high=-0.20),
                self.snapshot(trading_date=date(2025, 1, 2), analysis_close=110, sma_20=100, sma_60=110, volume_ratio_20=0.5, rsi_14=40, distance_to_prior_60d_high=-0.20),
                self.snapshot(trading_date=date(2025, 1, 3), analysis_close=110, sma_20=100, sma_60=90, volume_ratio_20=0.5, rsi_14=40, distance_to_prior_60d_high=-0.20),
                self.snapshot(trading_date=date(2025, 1, 4), analysis_close=110, sma_20=100, sma_60=90, volume_ratio_20=1.5, rsi_14=40, distance_to_prior_60d_high=-0.20),
                self.snapshot(trading_date=date(2025, 1, 5), analysis_close=110, sma_20=100, sma_60=90, volume_ratio_20=1.5, rsi_14=60, distance_to_prior_60d_high=-0.20),
                self.snapshot(trading_date=date(2025, 1, 6), analysis_close=110, sma_20=100, sma_60=90, volume_ratio_20=1.5, rsi_14=60, distance_to_prior_60d_high=-0.02),
                self.snapshot(trading_date=date(2025, 1, 7), analysis_close=110, sma_20=100, sma_60=90, volume_ratio_20=1.5, rsi_14=None, distance_to_prior_60d_high=-0.02),
                self.snapshot(trading_date=date(2025, 2, 1), analysis_close=110, sma_20=100, sma_60=90, volume_ratio_20=1.5, rsi_14=60, distance_to_prior_60d_high=-0.02),
            ),
        )

    def test_models_are_frozen(self):
        observation = self.observation()

        with self.assertRaises(FrozenInstanceError):
            observation.symbol = "CHANGED"

    def test_config_rejects_start_after_end(self):
        with self.assertRaises(HistoricalConditionDiagnosticsError):
            self.config(start_date=date(2025, 2, 1), end_date=date(2025, 1, 1))

    def test_distribution_covers_zero_through_five_counts(self):
        service = HistoricalConditionDiagnosticsService(
            price_loader=lambda *args, **kwargs: self.fail("price loader should not be called"),
        )

        result = service.run_diagnostics(
            ("TEST",),
            self.config(),
            technical_series_by_symbol={"TEST": self.fixture_series()},
        )

        self.assertEqual([row.matched_count for row in result.match_count_distribution], [0, 1, 2, 3, 4, 5])
        self.assertEqual([row.observation_count for row in result.match_count_distribution], [1, 1, 1, 1, 1, 1])
        self.assertEqual(result.evaluated_observation_count, 6)
        self.assertEqual(result.not_evaluable_observation_count, 1)
        self.assertEqual(result.total_observation_count, 7)
        self.assertTrue(all(row.share_of_evaluated_observations == 1 / 6 for row in result.match_count_distribution))

    def test_share_denominator_excludes_not_evaluable(self):
        result = summarize_condition_diagnostics(
            (
                self.observation(trading_date=date(2025, 1, 1), analysis_close=80, sma_20=100, sma_60=110, volume_ratio_20=0.5, rsi_14=40, distance_to_prior_60d_high=-0.20),
                self.observation(trading_date=date(2025, 1, 2), rsi_14=None),
            ),
            config=self.config(),
        )

        zero_row = result.match_count_distribution[0]
        self.assertEqual(zero_row.observation_count, 1)
        self.assertEqual(zero_row.share_of_evaluated_observations, 1.0)
        self.assertEqual(result.evaluated_observation_count, 1)
        self.assertEqual(result.not_evaluable_observation_count, 1)

    def test_per_condition_pass_rate(self):
        result = summarize_condition_diagnostics(
            (
                self.observation(trading_date=date(2025, 1, 1)),
                self.observation(trading_date=date(2025, 1, 2), volume_ratio_20=0.5),
            ),
            config=self.config(),
        )
        summaries = {row.condition_id: row for row in result.condition_pass_summaries}

        self.assertEqual(summaries["volume_ratio_20"].passed_count, 1)
        self.assertEqual(summaries["volume_ratio_20"].failed_count, 1)
        self.assertEqual(summaries["volume_ratio_20"].evaluated_count, 2)
        self.assertEqual(summaries["volume_ratio_20"].pass_rate, 0.5)
        self.assertEqual(summaries["analysis_close_vs_sma_20"].display_name, "股價高於 20 日均線")

    def test_zero_evaluated_pass_rate_is_none(self):
        result = summarize_condition_diagnostics(tuple(), config=self.config())

        self.assertTrue(all(row.pass_rate is None for row in result.condition_pass_summaries))
        self.assertTrue(all(row.share_of_evaluated_observations is None for row in result.match_count_distribution))

    def test_four_of_five_missing_condition_count(self):
        result = summarize_condition_diagnostics(
            (
                self.observation(trading_date=date(2025, 1, 1), volume_ratio_20=0.5),
                self.observation(trading_date=date(2025, 1, 2), rsi_14=80),
                self.observation(trading_date=date(2025, 1, 3), volume_ratio_20=0.4),
            ),
            config=self.config(),
        )

        self.assertEqual(result.total_4_of_5_count, 3)
        rows = {row.condition_id: row for row in result.missing_condition_summaries}
        self.assertEqual(rows["volume_ratio_20"].observation_count, 2)
        self.assertEqual(rows["rsi_14"].observation_count, 1)

    def test_zero_four_of_five_is_safe(self):
        result = summarize_condition_diagnostics(
            (
                self.observation(trading_date=date(2025, 1, 1)),
                self.observation(trading_date=date(2025, 1, 2), volume_ratio_20=0.5, rsi_14=80),
            ),
            config=self.config(),
        )

        self.assertEqual(result.total_4_of_5_count, 0)
        self.assertEqual(result.missing_condition_summaries, tuple())

    def test_combination_canonical_ordering_and_determinism(self):
        observation = self.observation(trading_date=date(2025, 1, 1), volume_ratio_20=0.5, rsi_14=80)
        reordered = ConditionDiagnosticObservation(
            symbol=observation.symbol,
            trading_date=date(2025, 1, 2),
            signal_definition_id=observation.signal_definition_id,
            status=observation.status,
            evaluated_conditions=observation.evaluated_conditions,
            matched_condition_count=observation.matched_condition_count,
            total_condition_count=observation.total_condition_count,
            passed_condition_ids=tuple(reversed(observation.passed_condition_ids)),
            missing_condition_ids=observation.missing_condition_ids,
            not_evaluable_condition_ids=observation.not_evaluable_condition_ids,
            source_snapshot=observation.source_snapshot,
        )

        result = summarize_condition_diagnostics((observation, reordered), config=self.config())

        self.assertEqual(len(result.condition_combination_summaries), 1)
        self.assertEqual(
            result.condition_combination_summaries[0].passed_condition_ids,
            (
                "analysis_close_vs_sma_20",
                "sma_20_vs_sma_60",
                "distance_to_prior_60d_high",
            ),
        )
        self.assertEqual(result.condition_combination_summaries[0].observation_count, 2)

    def test_per_symbol_and_multi_symbol_aggregate(self):
        first = self.series(
            "AAA",
            (
                self.snapshot(symbol="AAA", trading_date=date(2025, 1, 1)),
                self.snapshot(symbol="AAA", trading_date=date(2025, 1, 2), rsi_14=None),
            ),
        )
        second = self.series(
            "BBB",
            (
                self.snapshot(symbol="BBB", trading_date=date(2025, 1, 1), volume_ratio_20=0.5),
            ),
        )
        service = HistoricalConditionDiagnosticsService(
            price_loader=lambda *args, **kwargs: self.fail("price loader should not be called"),
        )

        result = service.run_diagnostics(
            ("AAA", "BBB"),
            self.config(),
            technical_series_by_symbol={"AAA": first, "BBB": second},
        )

        self.assertEqual(result.total_observation_count, 3)
        self.assertEqual(result.evaluated_observation_count, 2)
        summaries = {summary.symbol: summary for summary in result.per_symbol_summaries}
        self.assertEqual(summaries["AAA"].total_observation_count, 2)
        self.assertEqual(summaries["AAA"].not_evaluable_observation_count, 1)
        self.assertEqual(summaries["BBB"].evaluated_observation_count, 1)

    def test_no_outcome_or_backtest_call_and_no_yahoo_fetch_with_injected_data(self):
        service = HistoricalConditionDiagnosticsService(
            price_loader=lambda *args, **kwargs: self.fail("price loader should not be called"),
            technical_builder=lambda *args, **kwargs: self.fail("technical builder should not be called"),
        )

        with patch("signal_outcome_service.evaluate_historical_outcome") as outcome_call:
            with patch("backtest_service.run_historical_backtest") as backtest_call:
                result = service.run_diagnostics(
                    ("TEST",),
                    self.config(),
                    technical_series_by_symbol={"TEST": self.fixture_series()},
                )

        outcome_call.assert_not_called()
        backtest_call.assert_not_called()
        self.assertEqual(result.total_observation_count, 7)

    def test_service_builds_each_technical_series_once_when_loading_symbols(self):
        calls = []

        def price_loader(symbol, **kwargs):
            return symbol

        def technical_builder(price_series):
            calls.append(price_series)
            return self.series(
                price_series,
                (self.snapshot(symbol=price_series, trading_date=date(2025, 1, 1)),),
            )

        service = HistoricalConditionDiagnosticsService(
            price_loader=price_loader,
            technical_builder=technical_builder,
        )

        result = service.run_diagnostics(("AAA", "AAA", "BBB"), self.config())

        self.assertEqual(calls, ["AAA", "BBB"])
        self.assertEqual(result.normalized_symbols, ("AAA", "BBB"))
        self.assertEqual(result.total_observation_count, 2)

    def test_injected_data_bypasses_price_loader_and_technical_builder(self):
        service = HistoricalConditionDiagnosticsService(
            price_loader=lambda *args, **kwargs: self.fail("price loader should not be called"),
            technical_builder=lambda *args, **kwargs: self.fail("technical builder should not be called"),
        )

        with patch("signal_outcome_service.evaluate_historical_outcome") as outcome_call:
            result = service.run_diagnostics(
                ("TEST",),
                self.config(),
                technical_series_by_symbol={"TEST": self.fixture_series()},
            )

        outcome_call.assert_not_called()
        self.assertEqual(result.total_observation_count, 7)

    def test_source_signal_definition_semantics_are_reused(self):
        observation = self.observation(rsi_14=80)

        self.assertEqual(observation.status, SignalEvaluationStatus.NO_MATCH)
        self.assertIn("rsi_14", observation.missing_condition_ids)
        self.assertEqual(observation.evaluated_conditions[3].operator.value, "between")

    def test_missing_feature_does_not_become_zero_of_five(self):
        result = summarize_condition_diagnostics(
            (
                self.observation(trading_date=date(2025, 1, 1), rsi_14=None),
            ),
            config=self.config(),
        )

        self.assertEqual(result.evaluated_observation_count, 0)
        self.assertEqual(result.not_evaluable_observation_count, 1)
        self.assertEqual(sum(row.observation_count for row in result.match_count_distribution), 0)

    def test_total_invariants(self):
        result = summarize_condition_diagnostics(
            (
                self.observation(trading_date=date(2025, 1, 1)),
                self.observation(trading_date=date(2025, 1, 2), rsi_14=None),
                self.observation(trading_date=date(2025, 1, 3), volume_ratio_20=0.5),
            ),
            config=self.config(),
        )

        self.assertEqual(
            result.evaluated_observation_count + result.not_evaluable_observation_count,
            result.total_observation_count,
        )
        self.assertEqual(
            sum(row.observation_count for row in result.match_count_distribution),
            result.evaluated_observation_count,
        )

    def test_no_score_or_probability_fields(self):
        names = {
            field.name
            for model in (
                ConditionDiagnosticObservation,
            )
            for field in fields(model)
        }

        self.assertFalse(any("score" in name for name in names))
        self.assertFalse(any("probability" in name for name in names))


if __name__ == "__main__":
    unittest.main()
