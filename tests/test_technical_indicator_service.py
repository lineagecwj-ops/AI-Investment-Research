import sys
import unittest
from dataclasses import fields
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import TechnicalIndicatorSeries
from models import TechnicalIndicatorSnapshot
from technical_indicator_service import TECHNICAL_INDICATOR_DEFINITIONS
from technical_indicator_service import build_technical_indicator_series
from technical_indicator_service import build_technical_indicator_snapshot


FETCHED_AT = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


class TechnicalIndicatorServiceTestCase(unittest.TestCase):

    def bar(
        self,
        day,
        close,
        *,
        high=None,
        low=None,
        raw_close=None,
        adjusted_close=None,
        volume=100,
    ):
        raw_close = close if raw_close is None else raw_close
        return HistoricalPriceBar(
            symbol="TEST",
            trading_date=day,
            open=raw_close,
            high=raw_close + 1 if high is None else high,
            low=raw_close - 1 if low is None else low,
            close=raw_close,
            adjusted_close=close if adjusted_close is None else adjusted_close,
            volume=volume,
        )

    def series(self, bars, symbol="TEST", stale=False):
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="USD",
            bars=tuple(bars),
            fetched_at=FETCHED_AT,
            is_stale=stale,
        )

    def sequential_series(self, count=260, *, start_close=1.0, volume=100):
        bars = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), start_close + index, volume=volume)
            for index in range(count)
        ]
        return self.series(bars)

    def assertFloatAlmostEqual(self, actual, expected, places=8):
        self.assertIsNotNone(actual)
        self.assertAlmostEqual(actual, expected, places=places)

    def test_domain_models_are_frozen_and_series_has_no_dataframe(self):
        snapshot_params = {
            field.name: None
            for field in fields(TechnicalIndicatorSnapshot)
        }
        snapshot_params.update(
            symbol="TEST",
            trading_date=date(2025, 1, 1),
            analysis_close=10.0,
        )
        snapshot = TechnicalIndicatorSnapshot(**snapshot_params)
        technical_series = TechnicalIndicatorSeries(
            symbol="TEST",
            snapshots=(snapshot,),
            generated_at=FETCHED_AT,
            source_price_fetched_at=FETCHED_AT,
        )

        with self.assertRaises(Exception):
            snapshot.analysis_close = 11.0
        self.assertIsInstance(technical_series.snapshots, tuple)
        self.assertFalse(hasattr(technical_series, "dataframe"))

    def test_registry_uses_neutral_categories_and_beginner_labels(self):
        self.assertIn("rsi_14", TECHNICAL_INDICATOR_DEFINITIONS)
        self.assertIn("RSI 14（14日相對強弱指標）", TECHNICAL_INDICATOR_DEFINITIONS["rsi_14"].label)
        categories = {definition.category for definition in TECHNICAL_INDICATOR_DEFINITIONS.values()}

        self.assertIn("Trend", categories)
        self.assertNotIn("Bullish", categories)
        self.assertNotIn("Bearish", categories)

    def test_sma_requires_full_window_and_uses_analysis_close(self):
        bars = [
            self.bar(date(2025, 1, 1), 100.0, raw_close=1000.0, adjusted_close=100.0),
            self.bar(date(2025, 1, 2), 110.0, raw_close=1100.0, adjusted_close=110.0),
            self.bar(date(2025, 1, 3), 120.0, raw_close=1200.0, adjusted_close=120.0),
            self.bar(date(2025, 1, 4), 130.0, raw_close=1300.0, adjusted_close=130.0),
            self.bar(date(2025, 1, 5), 140.0, raw_close=1400.0, adjusted_close=140.0),
        ]

        snapshots = build_technical_indicator_series(self.series(bars)).snapshots

        self.assertIsNone(snapshots[3].sma_5)
        self.assertEqual(snapshots[4].sma_5, 120.0)

    def test_sma_windows_do_not_use_partial_average(self):
        snapshots = build_technical_indicator_series(self.sequential_series(19)).snapshots

        self.assertIsNone(snapshots[-1].sma_20)

    def test_ema_uses_adjust_false_and_warmup(self):
        snapshots = build_technical_indicator_series(self.sequential_series(12)).snapshots

        self.assertIsNone(snapshots[10].ema_12)
        self.assertFloatAlmostEqual(snapshots[11].ema_12, 7.37559918943734)

    def test_rsi_wilder_reference_value_and_warmup(self):
        closes = [
            44.34, 44.09, 44.15, 43.61, 44.33,
            44.83, 45.10, 45.42, 45.84, 46.08,
            45.89, 46.03, 45.61, 46.28, 46.28,
            46.00,
        ]
        bars = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), close)
            for index, close in enumerate(closes)
        ]

        snapshots = build_technical_indicator_series(self.series(bars)).snapshots

        self.assertIsNone(snapshots[13].rsi_14)
        self.assertFloatAlmostEqual(snapshots[14].rsi_14, 70.46413502109705)
        self.assertFloatAlmostEqual(snapshots[15].rsi_14, 66.24961855355505)

    def test_rsi_edge_cases_gain_loss_and_flat(self):
        rising = build_technical_indicator_series(self.sequential_series(15)).snapshots[-1]
        falling_bars = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), 100.0 - index)
            for index in range(15)
        ]
        falling = build_technical_indicator_series(self.series(falling_bars)).snapshots[-1]
        flat_bars = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), 100.0)
            for index in range(15)
        ]
        flat = build_technical_indicator_series(self.series(flat_bars)).snapshots[-1]

        self.assertEqual(rising.rsi_14, 100.0)
        self.assertEqual(falling.rsi_14, 0.0)
        self.assertEqual(flat.rsi_14, 50.0)

    def test_macd_reference_values_and_warmup(self):
        snapshots = build_technical_indicator_series(self.sequential_series(35)).snapshots

        self.assertIsNone(snapshots[24].macd)
        self.assertFloatAlmostEqual(snapshots[25].ema_12, 20.584449291584654)
        self.assertFloatAlmostEqual(snapshots[25].ema_26, 15.325223811411421)
        self.assertFloatAlmostEqual(snapshots[25].macd, 5.259225480173233)
        self.assertIsNone(snapshots[32].macd_signal)
        self.assertFloatAlmostEqual(snapshots[33].macd_signal, 5.737527795403899)
        self.assertFloatAlmostEqual(snapshots[33].macd_histogram, 0.2985522771922149)

    def test_atr_uses_raw_high_low_and_prior_raw_close_basis(self):
        bars = [
            self.bar(date(2025, 1, 1), 100.0, raw_close=100.0, high=101.0, low=99.0),
            self.bar(date(2025, 1, 2), 101.0, raw_close=101.0, high=102.0, low=100.0),
            self.bar(date(2025, 1, 3), 102.0, raw_close=102.0, high=103.0, low=101.0),
            self.bar(date(2025, 1, 4), 103.0, raw_close=103.0, high=104.0, low=102.0),
            self.bar(date(2025, 1, 5), 104.0, raw_close=104.0, high=105.0, low=103.0),
            self.bar(date(2025, 1, 6), 105.0, raw_close=105.0, high=106.0, low=104.0),
            self.bar(date(2025, 1, 7), 106.0, raw_close=106.0, high=107.0, low=105.0),
            self.bar(date(2025, 1, 8), 107.0, raw_close=107.0, high=108.0, low=106.0),
            self.bar(date(2025, 1, 9), 108.0, raw_close=108.0, high=109.0, low=107.0),
            self.bar(date(2025, 1, 10), 109.0, raw_close=109.0, high=110.0, low=108.0),
            self.bar(date(2025, 1, 11), 110.0, raw_close=110.0, high=111.0, low=109.0),
            self.bar(date(2025, 1, 12), 111.0, raw_close=111.0, high=112.0, low=110.0),
            self.bar(date(2025, 1, 13), 112.0, raw_close=112.0, high=113.0, low=111.0),
            self.bar(date(2025, 1, 14), 113.0, raw_close=113.0, high=118.0, low=117.0),
        ]

        snapshot = build_technical_indicator_series(self.series(bars)).snapshots[-1]

        self.assertFloatAlmostEqual(snapshot.atr_14, 2.2857142857142856)
        self.assertFloatAlmostEqual(snapshot.atr_14_pct, 2.2857142857142856 / 113.0)

    def test_volume_sma_includes_current_but_ratio_excludes_current(self):
        bars = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), 100.0 + index, volume=100)
            for index in range(20)
        ]
        bars.append(self.bar(date(2025, 1, 21), 121.0, volume=200))

        snapshot = build_technical_indicator_series(self.series(bars)).snapshots[-1]

        self.assertEqual(snapshot.volume_sma_20, 105.0)
        self.assertEqual(snapshot.volume_ratio_20, 2.0)

    def test_volume_sma_requires_twenty_valid_volume_bars(self):
        snapshot = build_technical_indicator_series(self.sequential_series(19)).snapshots[-1]

        self.assertIsNone(snapshot.volume_sma_20)
        self.assertIsNone(snapshot.volume_ratio_20)

    def test_zero_current_volume_is_valid_for_volume_ratio(self):
        bars = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), 100.0 + index, volume=100)
            for index in range(20)
        ]
        bars.append(self.bar(date(2025, 1, 21), 121.0, volume=0))

        snapshot = build_technical_indicator_series(self.series(bars)).snapshots[-1]

        self.assertEqual(snapshot.volume_ratio_20, 0.0)

    def test_volume_ratio_is_none_when_missing_or_zero_baseline(self):
        zero_baseline = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), 100.0 + index, volume=0)
            for index in range(20)
        ]
        zero_baseline.append(self.bar(date(2025, 1, 21), 121.0, volume=200))
        missing_baseline = [
            self.bar(date(2025, 2, 1) + timedelta(days=index), 100.0 + index, volume=100)
            for index in range(20)
        ]
        missing_baseline[5] = self.bar(date(2025, 2, 6), 105.0, volume=None)
        missing_baseline.append(self.bar(date(2025, 2, 21), 121.0, volume=200))

        zero_snapshot = build_technical_indicator_series(self.series(zero_baseline)).snapshots[-1]
        missing_snapshot = build_technical_indicator_series(self.series(missing_baseline)).snapshots[-1]

        self.assertIsNone(zero_snapshot.volume_ratio_20)
        self.assertIsNone(missing_snapshot.volume_ratio_20)

    def test_returns_use_trading_bars_not_calendar_days(self):
        bars = [
            self.bar(date(2025, 1, 3), 100.0),
            self.bar(date(2025, 1, 6), 101.0),
            self.bar(date(2025, 1, 7), 102.0),
            self.bar(date(2025, 1, 8), 103.0),
            self.bar(date(2025, 1, 9), 104.0),
            self.bar(date(2025, 1, 10), 110.0),
        ]

        snapshot = build_technical_indicator_series(self.series(bars)).snapshots[-1]

        self.assertFloatAlmostEqual(snapshot.return_5d, 0.10)

    def test_return_volatility_uses_sample_stdev_and_is_not_annualized(self):
        bars = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), 100.0 + index)
            for index in range(21)
        ]

        snapshot = build_technical_indicator_series(self.series(bars)).snapshots[-1]

        self.assertFloatAlmostEqual(snapshot.return_volatility_20d, 0.000496425826732139)

    def test_prior_high_excludes_current_bar(self):
        bars = [
            self.bar(date(2025, 1, 1), 9.0, high=10.0, low=8.0),
            self.bar(date(2025, 1, 2), 10.0, high=11.0, low=9.0),
            self.bar(date(2025, 1, 3), 11.0, high=12.0, low=10.0),
            self.bar(date(2025, 1, 4), 13.0, high=99.0, low=12.0),
        ]

        snapshot = build_technical_indicator_series(self.series(bars)).snapshots[-1]

        self.assertEqual(snapshot.high_20d, None)
        self.assertEqual(snapshot.prior_high_20d, None)

    def test_prior_high_20d_excludes_current_even_when_current_high_is_extreme(self):
        bars = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), 10.0 + index, high=10.0 + index, low=9.0)
            for index in range(20)
        ]
        bars.append(self.bar(date(2025, 1, 21), 50.0, high=999.0, low=49.0))

        snapshot = build_technical_indicator_series(self.series(bars)).snapshots[-1]

        self.assertEqual(snapshot.prior_high_20d, 29.0)
        self.assertEqual(snapshot.high_20d, 999.0)
        self.assertTrue(snapshot.is_above_prior_20d_high)
        self.assertFloatAlmostEqual(snapshot.distance_to_prior_20d_high, 50.0 / 29.0 - 1.0)

    def test_prior_60d_range_position_is_not_clamped(self):
        bars = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), 50.0, high=100.0, low=40.0)
            for index in range(60)
        ]
        bars.append(self.bar(date(2025, 3, 2), 130.0, high=131.0, low=129.0))

        snapshot = build_technical_indicator_series(self.series(bars)).snapshots[-1]

        self.assertEqual(snapshot.prior_high_60d, 100.0)
        self.assertEqual(snapshot.prior_low_60d, 40.0)
        self.assertFloatAlmostEqual(snapshot.position_in_prior_60d_range, 1.5)

    def test_rolling_high_and_low_include_current_bar(self):
        bars = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), 50.0, high=100.0, low=40.0)
            for index in range(59)
        ]
        bars.append(self.bar(date(2025, 3, 1), 60.0, high=120.0, low=30.0))

        snapshot = build_technical_indicator_series(self.series(bars)).snapshots[-1]

        self.assertEqual(snapshot.high_60d, 120.0)
        self.assertEqual(snapshot.low_60d, 30.0)
        self.assertIsNone(snapshot.prior_high_60d)

    def test_52_week_uses_252_trading_bar_approximation(self):
        snapshot = build_technical_indicator_series(self.sequential_series(253)).snapshots[-1]

        self.assertEqual(snapshot.prior_high_252d, 253.0)
        self.assertFloatAlmostEqual(snapshot.distance_to_prior_52_week_high, 253.0 / 253.0 - 1.0)

    def test_moving_average_relationships_are_factual_booleans(self):
        snapshot = build_technical_indicator_series(self.sequential_series(121)).snapshots[-1]

        self.assertTrue(snapshot.close_above_sma20)
        self.assertTrue(snapshot.close_above_sma60)
        self.assertTrue(snapshot.sma20_above_sma60)
        self.assertTrue(snapshot.sma60_above_sma120)

    def test_sma_change_5d_uses_prior_sma_value(self):
        snapshot = build_technical_indicator_series(self.sequential_series(65)).snapshots[-1]

        self.assertFloatAlmostEqual(snapshot.sma20_change_5d, 55.5 / 50.5 - 1.0)
        self.assertFloatAlmostEqual(snapshot.sma60_change_5d, 35.5 / 30.5 - 1.0)

    def test_as_of_non_trading_date_uses_latest_available_bar(self):
        bars = [
            self.bar(date(2025, 1, 3), 100.0),
            self.bar(date(2025, 1, 6), 101.0),
        ]

        snapshot = build_technical_indicator_snapshot(self.series(bars), date(2025, 1, 5))

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.trading_date, date(2025, 1, 3))

    def test_as_of_before_earliest_returns_none(self):
        snapshot = build_technical_indicator_snapshot(
            self.sequential_series(5),
            date(2024, 12, 31),
        )

        self.assertIsNone(snapshot)

    def test_full_series_snapshot_matches_as_of_snapshot(self):
        series = self.sequential_series(80)
        full_snapshot = build_technical_indicator_series(series).snapshots[69]
        as_of_snapshot = build_technical_indicator_snapshot(series, full_snapshot.trading_date)

        self.assertEqual(as_of_snapshot, full_snapshot)

    def test_future_data_mutation_does_not_change_as_of_snapshot(self):
        past_bars = list(self.sequential_series(80).bars)
        future_bars = [
            self.bar(date(2025, 4, 1) + timedelta(days=index), 10000.0 + (index * 1000.0), high=99999.0, low=1.0, volume=999999)
            for index in range(10)
        ]
        series_a = self.series(past_bars)
        series_b = self.series([*past_bars, *future_bars])
        as_of_date = past_bars[-1].trading_date

        snapshot_a = build_technical_indicator_snapshot(series_a, as_of_date)
        snapshot_b = build_technical_indicator_snapshot(series_b, as_of_date)

        self.assertEqual(snapshot_a, snapshot_b)

    def test_appending_future_bars_does_not_change_past_full_series_snapshot(self):
        past_bars = list(self.sequential_series(90).bars)
        future_bars = [
            self.bar(date(2025, 4, 1) + timedelta(days=index), 5000.0 + index)
            for index in range(10)
        ]

        series_a_snapshot = build_technical_indicator_series(self.series(past_bars)).snapshots[70]
        series_b_snapshot = build_technical_indicator_series(self.series([*past_bars, *future_bars])).snapshots[70]

        self.assertEqual(series_a_snapshot, series_b_snapshot)

    def test_series_metadata_preserves_source_price_state(self):
        technical_series = build_technical_indicator_series(self.sequential_series(3, volume=0))

        self.assertEqual(technical_series.source_price_fetched_at, FETCHED_AT)
        self.assertFalse(technical_series.source_price_is_stale)

    def test_series_metadata_preserves_stale_source_price_state(self):
        technical_series = build_technical_indicator_series(
            self.sequential_series(3, volume=0).__class__(
                symbol="TEST",
                currency="USD",
                bars=self.sequential_series(3, volume=0).bars,
                fetched_at=FETCHED_AT,
                is_stale=True,
            )
        )

        self.assertTrue(technical_series.source_price_is_stale)

    def test_analysis_close_falls_back_to_raw_close_when_adjusted_close_missing(self):
        bars = [
            self.bar(date(2025, 1, 1) + timedelta(days=index), 100.0 + index, adjusted_close=None)
            for index in range(5)
        ]

        snapshot = build_technical_indicator_series(self.series(bars)).snapshots[-1]

        self.assertEqual(snapshot.analysis_close, 104.0)
        self.assertEqual(snapshot.sma_5, 102.0)

    def test_new_listing_with_insufficient_history_keeps_available_features(self):
        snapshot = build_technical_indicator_series(self.sequential_series(30)).snapshots[-1]

        self.assertIsNotNone(snapshot.sma_20)
        self.assertIsNone(snapshot.sma_60)
        self.assertIsNone(snapshot.sma_120)
        self.assertIsNone(snapshot.sma_200)

    def test_no_non_finite_numeric_values_are_emitted(self):
        snapshot = build_technical_indicator_series(self.sequential_series(260)).snapshots[-1]

        for field in fields(snapshot):
            value = getattr(snapshot, field.name)
            if isinstance(value, float):
                self.assertTrue(value == value)
                self.assertNotIn(value, (float("inf"), float("-inf")))

    def test_technical_snapshot_has_no_signal_score_or_outcome_fields(self):
        snapshot_field_names = {field.name for field in fields(TechnicalIndicatorSnapshot)}

        forbidden_fragments = [
            "score",
            "probability",
            "hit_rate",
            "success",
            "failure",
            "future_return",
            "target_price",
        ]
        for field_name in snapshot_field_names:
            self.assertFalse(any(fragment in field_name for fragment in forbidden_fragments))

    def test_technical_snapshot_boolean_names_are_neutral(self):
        snapshot_field_names = {field.name for field in fields(TechnicalIndicatorSnapshot)}

        self.assertFalse(any("bullish" in field_name for field_name in snapshot_field_names))
        self.assertFalse(any("bearish" in field_name for field_name in snapshot_field_names))
        self.assertFalse(any("strong" in field_name for field_name in snapshot_field_names))
        self.assertIn("is_above_prior_60d_high", snapshot_field_names)

    def test_source_does_not_use_backfill_or_negative_shift(self):
        source = (SRC_PATH / "technical_indicator_service.py").read_text()

        self.assertNotIn("bfill", source)
        self.assertNotIn("backfill", source)
        self.assertNotIn("shift(-", source)


if __name__ == "__main__":
    unittest.main()
