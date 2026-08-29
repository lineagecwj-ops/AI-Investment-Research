import math
import sys
import unittest
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
from relative_20d_0050_logistic_baseline import Relative20DDataset
from relative_20d_0050_logistic_baseline import Relative20DDatasetRow
from relative_20d_0050_logistic_baseline import build_benchmark_price_lookup
from relative_20d_0050_logistic_baseline import fit_relative_logistic_baseline
from relative_20d_0050_logistic_baseline import relative_outperform_20d_target
from upside_20d_logistic_baseline import EVALUATED_SPLITS
from upside_20d_logistic_baseline import FEATURE_ORDER
from upside_20d_logistic_baseline import TRAIN
from upside_20d_logistic_baseline import VALIDATION
from upside_20d_logistic_baseline import WORKFLOW_FROZEN_OOS
from upside_20d_logistic_baseline import build_symbol_dataset_rows
from upside_20d_logistic_baseline import workflow_split


class Relative20D0050LogisticBaselineTestCase(unittest.TestCase):
    def bar(self, index, *, symbol="2330.TW", start=date(2022, 1, 3), close=None, adjusted=None):
        value = float(close if close is not None else 100 + index)
        return HistoricalPriceBar(
            symbol=symbol,
            trading_date=start + timedelta(days=index * 2),
            open=value,
            high=value,
            low=value,
            close=value,
            adjusted_close=adjusted,
            volume=1000 + index,
        )

    def series(self, bars, *, symbol="2330.TW"):
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="TWD",
            bars=tuple(bars),
            fetched_at=datetime(2026, 8, 13, tzinfo=UTC),
        )

    def benchmark_prices(self, bars, *, start_price=100.0, end_price=105.0):
        return {
            bars[0].trading_date: start_price,
            bars[20].trading_date: end_price,
        }

    def synthetic_dataset(self):
        rows = []
        for split, year, count in ((TRAIN, 2022, 80), (VALIDATION, 2023, 40), (VALIDATION, 2024, 40)):
            for index in range(count):
                signal = (index % 17 - 8) / 8
                features = (
                    signal,
                    math.sin(index / 5),
                    math.cos(index / 7),
                    signal / 2,
                    -signal / 3,
                    50 + index % 20,
                    0.01 + (index % 5) / 100,
                    0.8 + (index % 7) / 10,
                )
                rows.append(
                    Relative20DDatasetRow(
                        symbol=f"{1000 + index % 4}.TW",
                        as_of_date=date(year, 1, 1) + timedelta(days=index),
                        features=features,
                        outperform_20d=int(signal + math.sin(index / 5) > 0),
                        target_date=date(year, 1, 21) + timedelta(days=index),
                        split=split,
                    )
                )
        symbols = tuple(sorted({row.symbol for row in rows}))
        return Relative20DDataset(tuple(rows), symbols, symbols, (), {}, {})

    def test_relative_target_compares_stock_and_benchmark_returns(self):
        bars = tuple(self.bar(index) for index in range(21))
        benchmark = self.benchmark_prices(bars, end_price=110.0)

        result = relative_outperform_20d_target(bars, 0, benchmark)

        self.assertEqual(result.outperform_20d, 1)

    def test_target_date_is_stock_twentieth_future_trading_row(self):
        bars = tuple(self.bar(index) for index in range(21))

        result = relative_outperform_20d_target(bars, 0, self.benchmark_prices(bars))

        self.assertEqual(result.target_date, bars[20].trading_date)
        self.assertNotEqual(result.target_date, bars[0].trading_date + timedelta(days=20))

    def test_benchmark_uses_exact_stock_start_and_end_dates(self):
        bars = tuple(self.bar(index) for index in range(21))
        benchmark = self.benchmark_prices(bars)

        result = relative_outperform_20d_target(bars, 0, benchmark)

        self.assertIsNone(result.exclusion_reason)
        self.assertEqual(set(benchmark), {bars[0].trading_date, bars[20].trading_date})

    def test_equal_stock_and_benchmark_returns_are_not_outperformance(self):
        bars = tuple(self.bar(index) for index in range(21))
        benchmark = self.benchmark_prices(bars, end_price=120.0)

        result = relative_outperform_20d_target(bars, 0, benchmark)

        self.assertEqual(result.outperform_20d, 0)

    def test_missing_benchmark_start_or_end_excludes_row(self):
        bars = tuple(self.bar(index) for index in range(21))

        result = relative_outperform_20d_target(bars, 0, {bars[0].trading_date: 100.0})

        self.assertIsNone(result.outperform_20d)
        self.assertEqual(result.exclusion_reason, "BENCHMARK_EXACT_DATE_ALIGNMENT_MISSING")

    def test_nearby_benchmark_date_is_not_forward_filled(self):
        bars = tuple(self.bar(index) for index in range(21))
        benchmark = {
            bars[0].trading_date: 100.0,
            bars[20].trading_date - timedelta(days=1): 105.0,
        }

        result = relative_outperform_20d_target(bars, 0, benchmark)

        self.assertEqual(result.exclusion_reason, "BENCHMARK_EXACT_DATE_ALIGNMENT_MISSING")

    def test_split_crossing_rows_are_excluded_before_relative_target(self):
        bars = tuple(self.bar(index, start=date(2022, 8, 1)) for index in range(100))
        benchmark = {bar.trading_date: 100 + index for index, bar in enumerate(bars)}

        def resolver(candidate_bars, reference_index, _target_index):
            result = relative_outperform_20d_target(candidate_bars, reference_index, benchmark)
            return result.outperform_20d, result.exclusion_reason

        rows, exclusions = build_symbol_dataset_rows(
            self.series(bars),
            target_value_resolver=resolver,
            row_factory=lambda symbol, as_of, features, target, target_date, split: Relative20DDatasetRow(
                symbol, as_of, features, target, target_date, split
            ),
        )

        self.assertGreater(exclusions["TRAIN_TARGET_CROSSES_SPLIT"], 0)
        self.assertTrue(all(workflow_split(row.target_date) == row.split for row in rows))

    def test_adjusted_close_first_applies_to_stock_and_benchmark(self):
        bars = [self.bar(index) for index in range(21)]
        bars[0] = self.bar(0, close=100, adjusted=100)
        bars[20] = self.bar(20, close=120, adjusted=105)
        benchmark_bars = [
            self.bar(0, symbol="0050.TW", close=100, adjusted=50),
            HistoricalPriceBar(
                symbol="0050.TW",
                trading_date=bars[20].trading_date,
                open=100,
                high=100,
                low=100,
                close=100,
                adjusted_close=55,
                volume=1000,
            ),
        ]
        lookup = build_benchmark_price_lookup(self.series(benchmark_bars, symbol="0050.TW"))

        result = relative_outperform_20d_target(tuple(bars), 0, lookup)

        self.assertEqual(result.outperform_20d, 0)

    def test_fixed_feature_order_is_preserved(self):
        self.assertEqual(len(FEATURE_ORDER), 8)
        self.assertEqual(FEATURE_ORDER[0], "RETURN_5D")
        self.assertEqual(FEATURE_ORDER[-1], "VOLUME_RATIO20")

    def test_sprint_one_does_not_evaluate_2025(self):
        self.assertEqual(workflow_split(date(2025, 6, 1)), WORKFLOW_FROZEN_OOS)
        self.assertNotIn(WORKFLOW_FROZEN_OOS, EVALUATED_SPLITS)
        self.assertTrue(all(row.as_of_date.year != 2025 for row in self.synthetic_dataset().rows))

    def test_validation_probabilities_are_finite_and_bounded(self):
        result = fit_relative_logistic_baseline(self.synthetic_dataset())

        self.assertTrue(result["validation_probabilities"])
        self.assertTrue(all(math.isfinite(value) and 0 <= value <= 1 for value in result["validation_probabilities"]))

    def test_same_input_and_configuration_are_deterministic(self):
        dataset = self.synthetic_dataset()

        first = fit_relative_logistic_baseline(dataset)
        second = fit_relative_logistic_baseline(dataset)

        self.assertEqual(first["validation_probabilities"], second["validation_probabilities"])
        self.assertEqual(first["coefficients"], second["coefficients"])
        self.assertEqual(first["validation_metrics"], second["validation_metrics"])


if __name__ == "__main__":
    unittest.main()
