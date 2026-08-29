import math
import sys
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from relative_20d_0050_logistic_baseline import build_benchmark_price_lookup
from relative_strength_20d_0050_logistic_baseline import DEVELOPMENT_EVALUATION
from relative_strength_20d_0050_logistic_baseline import EVALUATED_SPLITS
from relative_strength_20d_0050_logistic_baseline import FEATURE_ORDER
from relative_strength_20d_0050_logistic_baseline import RelativeStrength20DDataset
from relative_strength_20d_0050_logistic_baseline import RelativeStrength20DDatasetRow
from relative_strength_20d_0050_logistic_baseline import build_feature_snapshot_lookup
from relative_strength_20d_0050_logistic_baseline import build_relative_strength_symbol_rows
from relative_strength_20d_0050_logistic_baseline import fit_relative_strength_logistic
from relative_strength_20d_0050_logistic_baseline import relative_strength_feature_values
from relative_strength_20d_0050_logistic_baseline import workflow_split
from upside_20d_logistic_baseline import TRAIN
from upside_20d_logistic_baseline import WORKFLOW_FROZEN_OOS


class RelativeStrength20D0050LogisticBaselineTestCase(unittest.TestCase):
    def bar(self, index, *, symbol="2330.TW", start=date(2022, 1, 3), close=None):
        value = float(close if close is not None else 100 + index)
        return HistoricalPriceBar(
            symbol=symbol,
            trading_date=start + timedelta(days=index * 2),
            open=value,
            high=value,
            low=value,
            close=value,
            adjusted_close=value,
            volume=1000 + index,
        )

    def series(self, bars, *, symbol="2330.TW"):
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="TWD",
            bars=tuple(bars),
            fetched_at=datetime(2026, 8, 13, tzinfo=UTC),
        )

    def snapshots(self, *, stock_date=date(2023, 1, 3), benchmark_date=None):
        stock = SimpleNamespace(
            trading_date=stock_date,
            analysis_close=110.0,
            sma_20=100.0,
            sma_60=105.0,
            return_5d=0.08,
            return_20d=0.15,
            return_60d=0.30,
            rsi_14=62.0,
        )
        benchmark = SimpleNamespace(
            trading_date=benchmark_date or stock_date,
            analysis_close=105.0,
            sma_20=100.0,
            sma_60=102.0,
            return_5d=0.03,
            return_20d=0.05,
            return_60d=0.10,
            rsi_14=54.0,
        )
        return stock, benchmark

    def synthetic_dataset(self):
        rows = []
        for split, year, count in (
            (TRAIN, 2022, 80),
            (DEVELOPMENT_EVALUATION, 2023, 40),
            (DEVELOPMENT_EVALUATION, 2024, 40),
        ):
            for index in range(count):
                signal = (index % 17 - 8) / 8
                features = (
                    signal,
                    math.sin(index / 5),
                    math.cos(index / 7),
                    signal / 2,
                    -signal / 3,
                    (index % 20) - 10,
                )
                rows.append(
                    RelativeStrength20DDatasetRow(
                        symbol=f"{1000 + index % 4}.TW",
                        as_of_date=date(year, 1, 1) + timedelta(days=index),
                        features=features,
                        outperform_20d=int(signal + math.sin(index / 5) > 0),
                        target_date=date(year, 1, 21) + timedelta(days=index),
                        split=split,
                    )
                )
        symbols = tuple(sorted({row.symbol for row in rows}))
        return RelativeStrength20DDataset(tuple(rows), symbols, symbols, (), {}, {})

    def test_rel_return_5d(self):
        self.assertAlmostEqual(relative_strength_feature_values(*self.snapshots())[0], 0.05)

    def test_rel_return_20d(self):
        self.assertAlmostEqual(relative_strength_feature_values(*self.snapshots())[1], 0.10)

    def test_rel_return_60d(self):
        self.assertAlmostEqual(relative_strength_feature_values(*self.snapshots())[2], 0.20)

    def test_rel_trend_20(self):
        self.assertAlmostEqual(relative_strength_feature_values(*self.snapshots())[3], 0.05)

    def test_rel_trend_60(self):
        expected = 110 / 105 - 105 / 102
        self.assertAlmostEqual(relative_strength_feature_values(*self.snapshots())[4], expected)

    def test_rel_rsi14(self):
        self.assertAlmostEqual(relative_strength_feature_values(*self.snapshots())[5], 8.0)

    def test_stock_and_benchmark_feature_dates_must_match_exactly(self):
        stock, benchmark = self.snapshots(benchmark_date=date(2023, 1, 4))

        self.assertIsNone(relative_strength_feature_values(stock, benchmark))

    def test_future_benchmark_bars_do_not_change_as_of_features(self):
        bars = [self.bar(index, symbol="0050.TW") for index in range(80)]
        as_of_date = bars[60].trading_date
        prefix = build_feature_snapshot_lookup(
            self.series(bars[:61], symbol="0050.TW"),
            end_date=as_of_date,
        )
        bars[70] = self.bar(70, symbol="0050.TW", close=10000)
        with_future = build_feature_snapshot_lookup(
            self.series(bars, symbol="0050.TW"),
            end_date=as_of_date,
        )

        self.assertEqual(prefix[as_of_date], with_future[as_of_date])

    def test_fixed_relative_feature_order(self):
        self.assertEqual(
            FEATURE_ORDER,
            (
                "REL_RETURN_5D",
                "REL_RETURN_20D",
                "REL_RETURN_60D",
                "REL_TREND_20",
                "REL_TREND_60",
                "REL_RSI14",
            ),
        )

    def test_split_crossing_target_is_excluded(self):
        bars = tuple(self.bar(index, start=date(2022, 8, 1)) for index in range(100))
        benchmark_bars = tuple(self.bar(index, symbol="0050.TW", start=date(2022, 8, 1)) for index in range(100))
        benchmark_series = self.series(benchmark_bars, symbol="0050.TW")

        rows, exclusions = build_relative_strength_symbol_rows(
            self.series(bars),
            benchmark_prices=build_benchmark_price_lookup(benchmark_series),
            benchmark_snapshots=build_feature_snapshot_lookup(
                benchmark_series,
                end_date=date(2024, 12, 31),
            ),
        )

        self.assertGreater(exclusions["TRAIN_TARGET_CROSSES_SPLIT"], 0)
        self.assertTrue(all(workflow_split(row.target_date) == row.split for row in rows))

    def test_2025_is_not_evaluated(self):
        self.assertEqual(workflow_split(date(2025, 6, 1)), WORKFLOW_FROZEN_OOS)
        self.assertNotIn(WORKFLOW_FROZEN_OOS, EVALUATED_SPLITS)
        self.assertTrue(all(row.as_of_date.year != 2025 for row in self.synthetic_dataset().rows))

    def test_development_probabilities_are_finite_and_bounded(self):
        result = fit_relative_strength_logistic(self.synthetic_dataset())

        self.assertTrue(result["development_probabilities"])
        self.assertTrue(all(math.isfinite(value) and 0 <= value <= 1 for value in result["development_probabilities"]))

    def test_same_input_and_configuration_are_deterministic(self):
        dataset = self.synthetic_dataset()

        first = fit_relative_strength_logistic(dataset)
        second = fit_relative_strength_logistic(dataset)

        self.assertEqual(first["development_probabilities"], second["development_probabilities"])
        self.assertEqual(first["coefficients"], second["coefficients"])
        self.assertEqual(first["development_metrics"], second["development_metrics"])


if __name__ == "__main__":
    unittest.main()
