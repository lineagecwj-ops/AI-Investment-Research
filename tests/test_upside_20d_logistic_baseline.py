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
from upside_20d_logistic_baseline import FEATURE_ORDER
from upside_20d_logistic_baseline import EVALUATED_SPLITS
from upside_20d_logistic_baseline import TRAIN
from upside_20d_logistic_baseline import VALIDATION
from upside_20d_logistic_baseline import WORKFLOW_FROZEN_OOS
from upside_20d_logistic_baseline import Upside20DDataset
from upside_20d_logistic_baseline import Upside20DDatasetRow
from upside_20d_logistic_baseline import build_symbol_dataset_rows
from upside_20d_logistic_baseline import canonical_research_price_series
from upside_20d_logistic_baseline import fit_logistic_baseline
from upside_20d_logistic_baseline import research_price
from upside_20d_logistic_baseline import up_20d_target
from upside_20d_logistic_baseline import workflow_split


class Upside20DLogisticBaselineTestCase(unittest.TestCase):
    def bar(self, index, *, start=date(2022, 1, 3), close=None, adjusted=None):
        value = float(close if close is not None else 100 + index)
        return HistoricalPriceBar(
            symbol="2330.TW",
            trading_date=start + timedelta(days=index * 2),
            open=value,
            high=value,
            low=value,
            close=value,
            adjusted_close=adjusted,
            volume=1000 + index,
        )

    def series(self, bars):
        return HistoricalPriceSeries(
            symbol="2330.TW",
            currency="TWD",
            bars=tuple(bars),
            fetched_at=datetime(2026, 8, 13, tzinfo=UTC),
        )

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
                    Upside20DDatasetRow(
                        symbol=f"{1000 + index % 4}.TW",
                        as_of_date=date(year, 1, 1) + timedelta(days=index),
                        features=features,
                        up_20d=int(signal + math.sin(index / 5) > 0),
                        target_date=date(year, 1, 21) + timedelta(days=index),
                        split=split,
                    )
                )
        symbols = tuple(sorted({row.symbol for row in rows}))
        return Upside20DDataset(tuple(rows), symbols, symbols, (), {}, {})

    def test_target_uses_twentieth_future_trading_row(self):
        bars = tuple(self.bar(index) for index in range(25))

        target, target_date = up_20d_target(bars, 0)

        self.assertEqual(target, 1)
        self.assertEqual(target_date, bars[20].trading_date)
        self.assertNotEqual(target_date, bars[0].trading_date + timedelta(days=20))

    def test_equal_future_price_is_not_up(self):
        bars = [self.bar(index) for index in range(21)]
        bars[0] = self.bar(0, close=100)
        bars[20] = self.bar(20, close=100)

        target, _target_date = up_20d_target(tuple(bars), 0)

        self.assertEqual(target, 0)

    def test_cross_split_targets_are_excluded(self):
        start = date(2022, 8, 1)
        bars = tuple(self.bar(index, start=start) for index in range(100))

        rows, exclusions = build_symbol_dataset_rows(self.series(bars))

        self.assertGreater(exclusions["TRAIN_TARGET_CROSSES_SPLIT"], 0)
        self.assertTrue(all(workflow_split(row.target_date) == row.split for row in rows))

    def test_adjusted_close_first_semantics_are_canonicalized(self):
        bar = self.bar(0, close=100, adjusted=75)

        canonical = canonical_research_price_series(self.series((bar,)))

        self.assertEqual(research_price(bar), 75)
        self.assertEqual(canonical.bars[0].close, 75)
        self.assertEqual(canonical.bars[0].adjusted_close, 75)

    def test_raw_close_fallback_when_adjusted_close_is_absent(self):
        bar = self.bar(0, close=88, adjusted=None)

        self.assertEqual(research_price(bar), 88)

    def test_feature_order_is_frozen(self):
        self.assertEqual(
            FEATURE_ORDER,
            (
                "RETURN_5D",
                "RETURN_20D",
                "RETURN_60D",
                "CLOSE_VS_SMA20",
                "CLOSE_VS_SMA60",
                "RSI14",
                "VOLATILITY_20D",
                "VOLUME_RATIO20",
            ),
        )

    def test_validation_probabilities_are_bounded(self):
        result = fit_logistic_baseline(self.synthetic_dataset())

        self.assertTrue(result["validation_probabilities"])
        self.assertTrue(all(0 <= value <= 1 for value in result["validation_probabilities"]))

    def test_sprint_one_does_not_evaluate_2025(self):
        self.assertEqual(workflow_split(date(2025, 6, 1)), WORKFLOW_FROZEN_OOS)
        self.assertNotIn(WORKFLOW_FROZEN_OOS, EVALUATED_SPLITS)
        self.assertIsNone(workflow_split(date(2026, 1, 1)))
        dataset = self.synthetic_dataset()

        self.assertTrue(all(row.split in EVALUATED_SPLITS for row in dataset.rows))
        self.assertTrue(all(row.as_of_date.year != 2025 for row in dataset.rows))

    def test_model_fit_is_deterministic(self):
        dataset = self.synthetic_dataset()

        first = fit_logistic_baseline(dataset)
        second = fit_logistic_baseline(dataset)

        self.assertEqual(first["validation_probabilities"], second["validation_probabilities"])
        self.assertEqual(first["coefficients"], second["coefficients"])
        self.assertEqual(first["validation_metrics"], second["validation_metrics"])


if __name__ == "__main__":
    unittest.main()
