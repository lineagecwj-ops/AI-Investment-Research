import math
import sys
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from market_inputs import MarketInputValidationError
from market_inputs import MarketSourceUnavailableError
from market_inputs import TechnicalCloseBasis
from market_inputs import TechnicalCloseObservationSeries
from market_inputs import TechnicalCloseSeriesRequest
from market_inputs import TechnicalCloseSeriesSource
from market_inputs import TechnicalMarketDataProvider
from market_inputs import YahooFinanceTechnicalCloseSeriesSource
from market_inputs import YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1


class FakeTicker:
    def __init__(self, frame=None, exception=None):
        self.frame = frame
        self.exception = exception
        self.history_calls = []

    def history(self, **kwargs):
        self.history_calls.append(kwargs)
        if self.exception is not None:
            raise self.exception
        return self.frame


class FakeTickerFactory:
    def __init__(self, ticker):
        self.ticker = ticker
        self.symbols = []

    def __call__(self, symbol):
        self.symbols.append(symbol)
        return self.ticker


class YahooFinanceTechnicalCloseSeriesSourceTestCase(unittest.TestCase):

    def setUp(self):
        self.fetched_at = datetime(2026, 8, 16, 1, 2, 3, tzinfo=UTC)

    def request(self, **overrides):
        values = {
            "symbol": "2330.TW",
            "provider_symbol": "2330.TW",
            "valuation_date": date(2026, 8, 14),
            "start_date": date(2026, 8, 12),
            "timezone": "Asia/Taipei",
            "close_basis": TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE,
            "provider": TechnicalMarketDataProvider.YAHOO_FINANCE_V1,
        }
        values.update(overrides)
        return TechnicalCloseSeriesRequest(**values)

    def frame(self, *, index=None, close=None, adj_close=None):
        if index is None:
            index = pd.DatetimeIndex(
                [
                    pd.Timestamp("2026-08-12 00:00:00", tz="Asia/Taipei"),
                    pd.Timestamp("2026-08-14 00:00:00", tz="Asia/Taipei"),
                ]
            )
        if close is None:
            close = [100.0, 110.0]
        payload = {"Close": close}
        if adj_close is not None:
            payload["Adj Close"] = adj_close
        return pd.DataFrame(payload, index=index)

    def source(self, frame=None, *, exception=None, clock=None):
        ticker = FakeTicker(frame=frame, exception=exception)
        factory = FakeTickerFactory(ticker)
        source = YahooFinanceTechnicalCloseSeriesSource(
            ticker_factory=factory,
            clock=clock or (lambda: self.fetched_at),
        )
        return source, ticker, factory

    def fetch(self, frame=None, request=None):
        source, ticker, factory = self.source(frame if frame is not None else self.frame())
        series = source.fetch(request or self.request())
        return series, ticker, factory

    def test_satisfies_source_protocol_and_constructor_does_not_fetch(self):
        ticker = FakeTicker(frame=self.frame())
        factory = FakeTickerFactory(ticker)

        source = YahooFinanceTechnicalCloseSeriesSource(
            ticker_factory=factory,
            clock=lambda: self.fetched_at,
        )

        self.assertIsInstance(source, TechnicalCloseSeriesSource)
        self.assertEqual(factory.symbols, [])
        self.assertEqual(ticker.history_calls, [])

    def test_valid_one_row_response(self):
        frame = self.frame(
            index=pd.DatetimeIndex([pd.Timestamp("2026-08-14", tz="Asia/Taipei")]),
            close=[110.0],
            adj_close=[109.5],
        )

        series, _, _ = self.fetch(frame)

        self.assertIsInstance(series, TechnicalCloseObservationSeries)
        self.assertEqual(tuple(item.market_session_date for item in series.observations), (date(2026, 8, 14),))
        self.assertEqual(series.observations[0].technical_close, 109.5)

    def test_valid_multi_row_response_and_request_output_identity(self):
        series, _, _ = self.fetch(self.frame(adj_close=[99.5, 109.5]))

        self.assertEqual(series.symbol, "2330.TW")
        self.assertEqual(series.provider, "YAHOO_FINANCE_V1")
        self.assertEqual(series.provider_symbol, "2330.TW")
        self.assertEqual(series.timezone, "Asia/Taipei")
        self.assertEqual(series.close_basis, TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE)
        self.assertEqual(series.valuation_date, date(2026, 8, 14))

    def test_wrong_request_type_and_provider_rejected(self):
        source, _, _ = self.source(self.frame())
        with self.assertRaisesRegex(MarketInputValidationError, "request"):
            source.fetch({"symbol": "2330.TW"})

        with self.assertRaisesRegex(MarketInputValidationError, "provider"):
            source.fetch(self.request(provider="UNSUPPORTED_PROVIDER"))

    def test_ticker_factory_receives_provider_symbol_and_fetch_kwargs_are_fixed(self):
        request = self.request(symbol="台積電", provider_symbol="2330.TW")

        _, ticker, factory = self.fetch(self.frame(), request=request)

        self.assertEqual(factory.symbols, ["2330.TW"])
        self.assertEqual(
            ticker.history_calls,
            [
                {
                    "interval": "1d",
                    "auto_adjust": False,
                    "actions": True,
                    "start": "2026-08-12",
                    "end": "2026-08-15",
                }
            ],
        )

    def test_numeric_only_provider_symbol_rejected(self):
        source, _, _ = self.source(self.frame())

        with self.assertRaisesRegex(MarketInputValidationError, "provider_symbol"):
            source.fetch(self.request(symbol="2330", provider_symbol="2330"))

    def test_valuation_date_exact_required_and_weekend_has_no_fallback(self):
        source, _, _ = self.source(
            self.frame(
                index=pd.DatetimeIndex([pd.Timestamp("2026-08-14", tz="Asia/Taipei")]),
                close=[110.0],
                adj_close=[109.5],
            )
        )

        with self.assertRaisesRegex(MarketInputValidationError, "valuation_date"):
            source.fetch(self.request(valuation_date=date(2026, 8, 15)))

    def test_outside_range_rows_are_excluded_from_revision(self):
        frame = self.frame(
            index=pd.DatetimeIndex(
                [
                    pd.Timestamp("2026-08-10", tz="Asia/Taipei"),
                    pd.Timestamp("2026-08-12", tz="Asia/Taipei"),
                    pd.Timestamp("2026-08-14", tz="Asia/Taipei"),
                    pd.Timestamp("2026-08-17", tz="Asia/Taipei"),
                ]
            ),
            close=[1.0, 100.0, 110.0, 999.0],
            adj_close=[1.0, 99.5, 109.5, 999.0],
        )
        expected = self.fetch(self.frame(adj_close=[99.5, 109.5]))[0]

        actual, _, _ = self.fetch(frame)

        self.assertEqual(actual.market_revision_id, expected.market_revision_id)
        self.assertEqual(tuple(item.market_session_date for item in actual.observations), (date(2026, 8, 12), date(2026, 8, 14)))

    def test_adj_close_selection_rules(self):
        cases = (
            ("missing", self.frame(adj_close=None), [100.0, 110.0]),
            ("nan", self.frame(adj_close=[math.nan, math.nan]), [100.0, 110.0]),
            ("pos_inf", self.frame(adj_close=[math.inf, math.inf]), [100.0, 110.0]),
            ("neg_inf", self.frame(adj_close=[-math.inf, -math.inf]), [100.0, 110.0]),
            ("valid", self.frame(adj_close=[99.5, 109.5]), [99.5, 109.5]),
        )
        for name, frame, expected in cases:
            with self.subTest(name=name):
                series, _, _ = self.fetch(frame)
                self.assertEqual([item.technical_close for item in series.observations], expected)

    def test_adj_close_zero_negative_and_bool_rejected(self):
        cases = (
            [0.0, 109.5],
            [-1.0, 109.5],
            [True, 109.5],
        )
        for adj_close in cases:
            with self.subTest(adj_close=adj_close):
                source, _, _ = self.source(self.frame(adj_close=adj_close))
                with self.assertRaises(MarketInputValidationError):
                    source.fetch(self.request())

    def test_close_invalid_values_rejected_even_when_adj_close_valid(self):
        cases = (
            [0.0, 110.0],
            [-1.0, 110.0],
            [math.nan, 110.0],
            [math.inf, 110.0],
            [True, 110.0],
            ["100", 110.0],
        )
        for close in cases:
            with self.subTest(close=close):
                source, _, _ = self.source(self.frame(close=close, adj_close=[99.5, 109.5]))
                with self.assertRaises(MarketInputValidationError):
                    source.fetch(self.request())

    def test_duplicate_normalized_dates_rejected(self):
        frame = self.frame(
            index=pd.DatetimeIndex(
                [
                    pd.Timestamp("2026-08-14 00:30:00", tz="Asia/Taipei"),
                    pd.Timestamp("2026-08-14 12:00:00", tz="Asia/Taipei"),
                ]
            ),
            close=[110.0, 111.0],
            adj_close=[109.5, 110.5],
        )
        source, _, _ = self.source(frame)

        with self.assertRaisesRegex(MarketInputValidationError, "duplicate"):
            source.fetch(self.request(start_date=date(2026, 8, 14)))

    def test_row_order_does_not_change_revision(self):
        first = self.frame(adj_close=[99.5, 109.5])
        second = first.iloc[::-1]

        self.assertEqual(self.fetch(first)[0].market_revision_id, self.fetch(second)[0].market_revision_id)

    def test_provider_exceptions_and_empty_responses_are_unavailable(self):
        source, _, _ = self.source(exception=OSError("network"))
        with self.assertRaises(MarketSourceUnavailableError) as context:
            source.fetch(self.request())
        self.assertIsInstance(context.exception.__cause__, OSError)

        outside_range = self.frame(
            index=pd.DatetimeIndex([pd.Timestamp("2026-08-10")]),
            close=[100.0],
        )
        for response in (None, pd.DataFrame(), outside_range):
            with self.subTest(response_type=type(response).__name__):
                source, _, _ = self.source(response)
                with self.assertRaises(MarketSourceUnavailableError):
                    source.fetch(self.request())

    def test_dataframe_structural_errors_rejected(self):
        missing_close = pd.DataFrame({"Adj Close": [100.0]}, index=pd.DatetimeIndex([pd.Timestamp("2026-08-14")]))

        duplicate_columns = pd.DataFrame(
            [[100.0, 101.0]],
            columns=["Close", "Close"],
            index=pd.DatetimeIndex([pd.Timestamp("2026-08-14")]),
        )

        multiindex = self.frame()
        multiindex.columns = pd.MultiIndex.from_product([["Price"], multiindex.columns])

        bad_index = pd.DataFrame({"Close": [100.0]}, index=["2026-08-14"])

        for frame in (missing_close, duplicate_columns, multiindex, bad_index, {"Close": [100.0]}):
            with self.subTest(frame_type=type(frame).__name__):
                source, _, _ = self.source(frame)
                with self.assertRaises(MarketInputValidationError):
                    source.fetch(self.request(start_date=date(2026, 8, 14)))

    def test_timezone_conversion_and_naive_timestamp_semantics(self):
        aware = self.frame(
            index=pd.DatetimeIndex(
                [
                    pd.Timestamp("2026-08-13 13:30:00", tz="UTC"),
                    pd.Timestamp("2026-08-14 02:00:00", tz="UTC"),
                ]
            ),
            close=[100.0, 110.0],
        )
        naive = self.frame(
            index=pd.DatetimeIndex([pd.Timestamp("2026-08-12"), pd.Timestamp("2026-08-14")]),
            close=[100.0, 110.0],
        )

        aware_series, _, _ = self.fetch(aware)
        naive_series, _, _ = self.fetch(naive)

        self.assertEqual(tuple(item.market_session_date for item in aware_series.observations), (date(2026, 8, 13), date(2026, 8, 14)))
        self.assertEqual(tuple(item.market_session_date for item in naive_series.observations), (date(2026, 8, 12), date(2026, 8, 14)))

    def test_fetched_at_clock_and_revision_boundaries(self):
        first = self.fetch(self.frame(), request=self.request())[0]
        second_source, _, _ = self.source(
            self.frame(),
            clock=lambda: datetime(2026, 8, 17, 1, 2, 3, tzinfo=UTC),
        )
        second = second_source.fetch(self.request())
        changed = self.fetch(self.frame(close=[100.0, 111.0]))[0]

        self.assertEqual(first.fetched_at, self.fetched_at)
        self.assertEqual(first.market_revision_id, second.market_revision_id)
        self.assertNotEqual(first.market_revision_id, changed.market_revision_id)

        source, _, _ = self.source(self.frame(), clock=lambda: datetime(2026, 8, 16, 1, 2, 3))
        with self.assertRaisesRegex(MarketInputValidationError, "timezone-aware"):
            source.fetch(self.request())

    def test_producer_version_exact_and_participates_revision(self):
        yahoo = self.fetch(self.frame())[0]
        generic = TechnicalCloseObservationSeries(
            symbol=yahoo.symbol,
            provider=yahoo.provider,
            provider_symbol=yahoo.provider_symbol,
            timezone=yahoo.timezone,
            close_basis=yahoo.close_basis,
            valuation_date=yahoo.valuation_date,
            observations=yahoo.observations,
            fetched_at=yahoo.fetched_at,
        )

        self.assertEqual(yahoo.producer_version, YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1)
        self.assertNotEqual(yahoo.market_revision_id, generic.market_revision_id)

    def test_source_boundary_and_production_safety(self):
        source_text = (SRC_PATH / "market_inputs" / "yahoo_finance_technical_close_series_source.py").read_text()
        forbidden = (
            "LiveDataStore",
            "database",
            "risk_persistence",
            "FilesystemTechnicalCloseSeriesStore",
            "TechnicalCloseSeriesStore",
            "historical_price_service",
            "technical_indicator_service",
            "RiskEvaluationInput",
            "RiskSignalProductionInput",
            "SMA20",
            "SMA60",
            "RSI14",
            "open(",
            "write_text",
            "mkdir",
        )
        for term in forbidden:
            self.assertNotIn(term, source_text)
        self.assertFalse((PROJECT_ROOT / "data" / "production").exists())

    def test_no_real_network_when_fake_ticker_is_injected(self):
        ticker = FakeTicker(frame=self.frame())
        factory = FakeTickerFactory(ticker)
        source = YahooFinanceTechnicalCloseSeriesSource(
            ticker_factory=factory,
            clock=lambda: self.fetched_at,
        )

        source.fetch(self.request())

        self.assertEqual(factory.symbols, ["2330.TW"])
        self.assertEqual(len(ticker.history_calls), 1)


if __name__ == "__main__":
    unittest.main()
