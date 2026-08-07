import sys
import tempfile
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from database import save_historical_prices
from historical_price_service import HistoricalPriceDataError
from historical_price_service import HistoricalPriceSourceError
from historical_price_service import build_historical_price_series
from historical_price_service import fetch_historical_prices_from_yahoo
from historical_price_service import get_analysis_close
from historical_price_service import get_historical_prices
from historical_price_service import get_recent_bars
from historical_price_service import normalize_trading_date
from historical_price_service import slice_price_series_as_of
from models import HistoricalPriceBar
from models import HistoricalPriceSeries


class HistoricalPriceParsingTestCase(unittest.TestCase):

    def setUp(self):
        self.fetched_at = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

    def price_frame(self, index=None, close_values=None):
        if index is None:
            index = pd.DatetimeIndex(
                [
                    pd.Timestamp("2025-01-02", tz="America/New_York"),
                    pd.Timestamp("2025-01-03", tz="America/New_York"),
                ]
            )
        if close_values is None:
            close_values = [105.0, 125.0]
        return pd.DataFrame(
            {
                "Open": [100.0, 120.0],
                "High": [110.0, 130.0],
                "Low": [95.0, 115.0],
                "Close": close_values,
                "Adj Close": [104.5, 124.5],
                "Volume": [1000, 1100],
                "Dividends": [0.0, 0.5],
                "Stock Splits": [0.0, 4.0],
            },
            index=index,
        )

    def test_builds_chronological_price_series_without_dataframe_in_domain_model(self):
        reversed_frame = self.price_frame().iloc[::-1]

        series, quality = build_historical_price_series(
            symbol="NVDA",
            currency="USD",
            frame=reversed_frame,
            fetched_at=self.fetched_at,
        )

        self.assertEqual(series.symbol, "NVDA")
        self.assertEqual(series.currency, "USD")
        self.assertEqual([bar.trading_date for bar in series.bars], [date(2025, 1, 2), date(2025, 1, 3)])
        self.assertEqual(series.bars[-1].dividends, 0.5)
        self.assertEqual(series.bars[-1].stock_splits, 4.0)
        self.assertEqual(quality.raw_rows, 2)
        self.assertEqual(quality.retained_rows, 2)
        self.assertIsInstance(series.bars, tuple)

    def test_timezone_aware_index_normalizes_to_trading_date_without_utc_shift(self):
        taiwan_date = normalize_trading_date(pd.Timestamp("2025-01-02 00:00:00", tz="Asia/Taipei"))
        us_date = normalize_trading_date(pd.Timestamp("2025-01-02 00:00:00", tz="America/New_York"))

        self.assertEqual(taiwan_date, date(2025, 1, 2))
        self.assertEqual(us_date, date(2025, 1, 2))

    def test_empty_frame_raises_data_error(self):
        with self.assertRaises(HistoricalPriceDataError):
            build_historical_price_series(
                symbol="EMPTY",
                currency="USD",
                frame=pd.DataFrame(),
                fetched_at=self.fetched_at,
            )

    def test_nan_inf_and_non_positive_prices_are_filtered(self):
        frame = self.price_frame()
        frame.loc[frame.index[0], "Close"] = float("nan")
        frame.loc[frame.index[1], "High"] = -1.0

        with self.assertRaises(HistoricalPriceDataError):
            build_historical_price_series(
                symbol="BAD",
                currency="USD",
                frame=frame,
                fetched_at=self.fetched_at,
            )

    def test_invalid_rows_are_filtered_when_valid_rows_remain(self):
        frame = self.price_frame()
        frame.loc[frame.index[0], "Close"] = float("inf")

        series, quality = build_historical_price_series(
            symbol="PARTIAL",
            currency="USD",
            frame=frame,
            fetched_at=self.fetched_at,
        )

        self.assertEqual(len(series.bars), 1)
        self.assertEqual(series.bars[0].trading_date, date(2025, 1, 3))
        self.assertEqual(quality.non_finite_values, 1)

    def test_price_relationship_violation_is_filtered(self):
        frame = self.price_frame()
        frame.loc[frame.index[0], "High"] = 90.0

        series, quality = build_historical_price_series(
            symbol="REL",
            currency="USD",
            frame=frame,
            fetched_at=self.fetched_at,
        )

        self.assertEqual(len(series.bars), 1)
        self.assertEqual(quality.price_relationship_violations, 1)

    def test_negative_volume_is_filtered_but_zero_volume_is_allowed(self):
        frame = self.price_frame()
        frame.loc[frame.index[0], "Volume"] = 0
        frame.loc[frame.index[1], "Volume"] = -10

        series, quality = build_historical_price_series(
            symbol="VOL",
            currency="USD",
            frame=frame,
            fetched_at=self.fetched_at,
        )

        self.assertEqual(len(series.bars), 1)
        self.assertEqual(series.bars[0].volume, 0)
        self.assertEqual(quality.negative_volume, 1)

    def test_string_numeric_and_bool_values_do_not_pollute_domain_model(self):
        frame = self.price_frame()
        frame["Close"] = frame["Close"].astype(object)
        frame["Volume"] = frame["Volume"].astype(object)
        frame.loc[frame.index[0], "Close"] = "105"
        frame.loc[frame.index[1], "Volume"] = True

        series, quality = build_historical_price_series(
            symbol="COERCE",
            currency="USD",
            frame=frame,
            fetched_at=self.fetched_at,
        )

        self.assertEqual(len(series.bars), 1)
        self.assertEqual(series.bars[0].trading_date, date(2025, 1, 3))
        self.assertIsNone(series.bars[0].volume)
        self.assertEqual(quality.non_finite_values, 1)

    def test_none_bool_and_missing_required_prices_are_filtered(self):
        valid = self.price_frame().iloc[[1]]

        none_close = self.price_frame().iloc[[0]].copy()
        none_close["Close"] = none_close["Close"].astype(object)
        none_close.iloc[0, none_close.columns.get_loc("Close")] = None

        bool_high = self.price_frame().iloc[[0]].copy()
        bool_high["High"] = bool_high["High"].astype(object)
        bool_high.iloc[0, bool_high.columns.get_loc("High")] = True

        missing_low = self.price_frame().iloc[[0]].copy().drop(columns=["Low"])
        frame = pd.concat([none_close, bool_high, missing_low, valid])

        series, quality = build_historical_price_series(
            symbol="PARTIAL",
            currency="USD",
            frame=frame,
            fetched_at=self.fetched_at,
        )

        self.assertEqual(len(series.bars), 1)
        self.assertEqual(series.bars[0].trading_date, date(2025, 1, 3))
        self.assertEqual(quality.non_finite_values, 3)

    def test_negative_adjusted_close_is_filtered(self):
        frame = self.price_frame()
        frame.loc[frame.index[0], "Adj Close"] = -1.0

        series, quality = build_historical_price_series(
            symbol="ADJ",
            currency="USD",
            frame=frame,
            fetched_at=self.fetched_at,
        )

        self.assertEqual(len(series.bars), 1)
        self.assertEqual(quality.invalid_prices, 1)

    def test_missing_optional_open_column_is_allowed(self):
        frame = self.price_frame().drop(columns=["Open"])

        series, quality = build_historical_price_series(
            symbol="NOOPEN",
            currency="USD",
            frame=frame,
            fetched_at=self.fetched_at,
        )

        self.assertEqual(len(series.bars), 2)
        self.assertIsNone(series.bars[0].open)
        self.assertEqual(quality.filtered_rows, 0)

    def test_identical_duplicate_date_collapses_deterministically(self):
        frame = pd.concat([self.price_frame().iloc[[0]], self.price_frame().iloc[[0]]])

        series, quality = build_historical_price_series(
            symbol="DUP",
            currency="USD",
            frame=frame,
            fetched_at=self.fetched_at,
        )

        self.assertEqual(len(series.bars), 1)
        self.assertEqual(quality.duplicate_dates, 1)
        self.assertEqual(quality.conflicting_duplicate_dates, 0)

    def test_conflicting_duplicate_date_uses_last_row_deterministically(self):
        first = self.price_frame().iloc[[0]]
        second = self.price_frame().iloc[[0]].copy()
        second.loc[second.index[0], "Close"] = 106.0
        frame = pd.concat([first, second])

        series, quality = build_historical_price_series(
            symbol="DUP",
            currency="USD",
            frame=frame,
            fetched_at=self.fetched_at,
        )

        self.assertEqual(len(series.bars), 1)
        self.assertEqual(series.bars[0].close, 106.0)
        self.assertEqual(quality.conflicting_duplicate_dates, 1)

    def test_multiindex_columns_raise_data_error(self):
        frame = self.price_frame()
        frame.columns = pd.MultiIndex.from_product([["Price"], frame.columns])

        with self.assertRaises(HistoricalPriceDataError):
            build_historical_price_series(
                symbol="MULTI",
                currency="USD",
                frame=frame,
                fetched_at=self.fetched_at,
            )

    def test_analysis_close_uses_adjusted_close_when_available(self):
        bar = HistoricalPriceBar(
            symbol="AAPL",
            trading_date=date(2020, 8, 31),
            open=128.0,
            high=132.0,
            low=126.0,
            close=129.04,
            adjusted_close=125.17,
            volume=1000,
        )
        unadjusted_bar = HistoricalPriceBar(
            symbol="NEW",
            trading_date=date(2025, 1, 2),
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            adjusted_close=None,
            volume=100,
        )

        self.assertEqual(get_analysis_close(bar), 125.17)
        self.assertEqual(get_analysis_close(unadjusted_bar), 10.5)


class HistoricalPriceNoLookAheadTestCase(unittest.TestCase):

    def setUp(self):
        self.series = HistoricalPriceSeries(
            symbol="TEST",
            currency="USD",
            bars=(
                self.bar(date(2025, 1, 1), 100.0),
                self.bar(date(2025, 1, 2), 101.0),
                self.bar(date(2025, 1, 6), 102.0),
            ),
            fetched_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
        )

    def bar(self, trading_date, close):
        return HistoricalPriceBar(
            symbol="TEST",
            trading_date=trading_date,
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            adjusted_close=close,
            volume=1000,
        )

    def test_slice_as_of_exact_date_excludes_future_bars(self):
        sliced = slice_price_series_as_of(self.series, date(2025, 1, 2))

        self.assertEqual([bar.trading_date for bar in sliced.bars], [date(2025, 1, 1), date(2025, 1, 2)])
        self.assertTrue(all(bar.trading_date <= date(2025, 1, 2) for bar in sliced.bars))

    def test_slice_as_of_between_trading_dates(self):
        sliced = slice_price_series_as_of(self.series, date(2025, 1, 5))

        self.assertEqual([bar.trading_date for bar in sliced.bars], [date(2025, 1, 1), date(2025, 1, 2)])

    def test_slice_as_of_before_earliest_and_after_latest(self):
        before = slice_price_series_as_of(self.series, date(2024, 12, 31))
        after = slice_price_series_as_of(self.series, date(2025, 12, 31))

        self.assertEqual(before.bars, tuple())
        self.assertEqual(len(after.bars), 3)

    def test_recent_bars_uses_trading_bar_count_not_calendar_days(self):
        recent = get_recent_bars(self.series, date(2025, 1, 6), 2)

        self.assertEqual([bar.trading_date for bar in recent], [date(2025, 1, 2), date(2025, 1, 6)])

    def test_recent_bars_respects_end_date_and_non_positive_count(self):
        recent = get_recent_bars(self.series, date(2025, 1, 5), 2)
        empty = get_recent_bars(self.series, date(2025, 1, 6), 0)

        self.assertEqual([bar.trading_date for bar in recent], [date(2025, 1, 1), date(2025, 1, 2)])
        self.assertEqual(empty, tuple())


class HistoricalPriceYahooFetchTestCase(unittest.TestCase):

    @patch("historical_price_service.yf.Ticker")
    def test_fetch_from_yahoo_uses_ticker_history_with_raw_ohlc_and_actions(self, mock_ticker):
        yahoo_ticker = Mock()
        yahoo_ticker.history.return_value = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [110.0],
                "Low": [95.0],
                "Close": [105.0],
                "Adj Close": [104.5],
                "Volume": [1000],
                "Dividends": [0.0],
                "Stock Splits": [0.0],
            },
            index=pd.DatetimeIndex([pd.Timestamp("2025-01-02", tz="America/New_York")]),
        )
        yahoo_ticker.fast_info = {"currency": "USD"}
        mock_ticker.return_value = yahoo_ticker

        series = fetch_historical_prices_from_yahoo(
            "NVDA",
            start=date(2025, 1, 2),
            end=date(2025, 1, 2),
        )

        mock_ticker.assert_called_once_with("NVDA")
        yahoo_ticker.history.assert_called_once_with(
            auto_adjust=False,
            actions=True,
            start="2025-01-02",
            end="2025-01-03",
        )
        self.assertEqual(series.currency, "USD")
        self.assertEqual(series.bars[0].adjusted_close, 104.5)

    @patch("historical_price_service.yf.Ticker")
    def test_fetch_from_yahoo_uses_period_max_for_default_history(self, mock_ticker):
        yahoo_ticker = Mock()
        yahoo_ticker.history.return_value = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [110.0],
                "Low": [95.0],
                "Close": [105.0],
                "Adj Close": [104.5],
                "Volume": [1000],
                "Dividends": [0.0],
                "Stock Splits": [0.0],
            },
            index=pd.DatetimeIndex([pd.Timestamp("2025-01-02", tz="America/New_York")]),
        )
        yahoo_ticker.fast_info = {"currency": "USD"}
        mock_ticker.return_value = yahoo_ticker

        fetch_historical_prices_from_yahoo("NVDA")

        yahoo_ticker.history.assert_called_once_with(
            period="max",
            auto_adjust=False,
            actions=True,
        )

    @patch("historical_price_service.yf.Ticker")
    def test_fetch_from_yahoo_wraps_network_error(self, mock_ticker):
        yahoo_ticker = Mock()
        yahoo_ticker.history.side_effect = OSError("network")
        mock_ticker.return_value = yahoo_ticker

        with self.assertRaises(HistoricalPriceSourceError):
            fetch_historical_prices_from_yahoo("NVDA")


class HistoricalPriceServiceCacheTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        self.now = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

    def tearDown(self):
        self.temp_dir.cleanup()

    def sample_series(self, symbol="NVDA", close=105.0):
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="USD",
            bars=(
                HistoricalPriceBar(
                    symbol=symbol,
                    trading_date=date(2025, 1, 2),
                    open=100.0,
                    high=110.0,
                    low=95.0,
                    close=close,
                    adjusted_close=close,
                    volume=1000,
                ),
            ),
            fetched_at=self.now,
        )

    def test_fresh_full_history_cache_does_not_query_yahoo(self):
        save_historical_prices(
            self.sample_series(),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=True,
        )

        with patch("database.utc_now", return_value=self.now + timedelta(hours=1)):
            with patch("historical_price_service.fetch_historical_prices_from_yahoo") as mock_fetch:
                series = get_historical_prices("NVDA", db_path=self.db_path)

        mock_fetch.assert_not_called()
        self.assertEqual(series.bars[0].close, 105.0)

    def test_numeric_symbol_is_normalized_before_cache_and_fetch(self):
        refreshed = self.sample_series(symbol="2330.TW")

        with patch(
            "historical_price_service.fetch_historical_prices_from_yahoo",
            return_value=refreshed,
        ) as mock_fetch:
            series = get_historical_prices("2330", db_path=self.db_path)

        mock_fetch.assert_called_once_with("2330.TW", start=None, end=None)
        self.assertEqual(series.symbol, "2330.TW")

    def test_stale_cache_is_returned_when_provider_fails(self):
        save_historical_prices(
            self.sample_series(),
            self.db_path,
            fetched_at=self.now - timedelta(hours=13),
            full_history_fetched=True,
        )

        with patch("database.utc_now", return_value=self.now):
            with patch(
                "historical_price_service.fetch_historical_prices_from_yahoo",
                side_effect=OSError("network"),
            ):
                with self.assertLogs(level="WARNING"):
                    series = get_historical_prices("NVDA", db_path=self.db_path)

        self.assertTrue(series.is_stale)
        self.assertEqual(series.bars[0].close, 105.0)

    def test_provider_failure_without_cache_raises_domain_error(self):
        with patch(
            "historical_price_service.fetch_historical_prices_from_yahoo",
            side_effect=OSError("network"),
        ):
            with self.assertRaises(HistoricalPriceSourceError):
                get_historical_prices("NVDA", db_path=self.db_path)


if __name__ == "__main__":
    unittest.main()
