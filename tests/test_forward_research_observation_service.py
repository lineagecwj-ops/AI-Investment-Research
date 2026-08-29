from __future__ import annotations

import math
import sys
import tempfile
import unittest
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from forward_research_observation_service import FORWARD_RESEARCH_OBSERVATION_VERSION
from forward_research_observation_service import ForwardResearchObservationContext
from forward_research_observation_service import ForwardResearchObservationError
from forward_research_observation_service import ForwardResearchObservationRepository
from forward_research_observation_service import POINT_IN_TIME_CLASSIFICATION
from forward_research_observation_service import RELATIVE_ALIGNMENT_AVAILABLE
from forward_research_observation_service import RELATIVE_ALIGNMENT_UNAVAILABLE
from forward_research_observation_service import build_local_observation_context
from forward_research_observation_service import deterministic_observation_id
from forward_research_observation_service import live_market_data_status
from forward_research_observation_service import load_live_historical_price_series
from database import save_historical_prices
from models import HistoricalPriceBar
from models import HistoricalPriceSeries


TAIPEI = ZoneInfo("Asia/Taipei")


class ForwardResearchObservationServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "forward.sqlite"
        self.capture_time = datetime(2026, 8, 29, 15, 30, tzinfo=TAIPEI)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_observation_cannot_be_backfilled_before_v0_start(self):
        repository = self.repository(datetime(2026, 8, 28, 12, tzinfo=TAIPEI))
        with self.assertRaisesRegex(ForwardResearchObservationError, "2026-08-29"):
            repository.capture(self.context())

    def test_2025_observation_creation_is_prohibited(self):
        with self.assertRaisesRegex(ForwardResearchObservationError, "允許起點"):
            self.repository().capture(
                self.context(as_of_date=date(2025, 12, 31), data_date=date(2025, 12, 31))
            )

    def test_capture_timestamp_is_timezone_aware_and_actual_clock_value(self):
        result = self.repository().capture(self.context())
        self.assertEqual(result.observation.captured_at, self.capture_time)
        self.assertIsNotNone(result.observation.captured_at.utcoffset())

    def test_naive_capture_timestamp_fails_closed(self):
        repository = self.repository(datetime(2026, 8, 29, 15, 30))
        with self.assertRaisesRegex(ForwardResearchObservationError, "含時區"):
            repository.capture(self.context())

    def test_previous_trading_day_is_valid_for_weekend_capture(self):
        result = self.repository().capture(self.context(as_of_date=date(2026, 8, 28)))
        self.assertEqual(result.observation.as_of_date, date(2026, 8, 28))

    def test_identity_is_deterministic_from_version_symbol_and_as_of_date(self):
        identity = deterministic_observation_id("2330.tw", date(2026, 8, 28))
        self.assertEqual(identity, deterministic_observation_id("2330.TW", date(2026, 8, 28)))
        self.assertNotEqual(identity, deterministic_observation_id("2330.TW", date(2026, 8, 29)))
        self.assertIn("forward_research_observation_", identity)

    def test_duplicate_save_is_idempotent_and_retains_original_values(self):
        repository = self.repository()
        first = repository.capture(self.context())
        second = repository.capture(self.context(research_price=999.0, return_20d=0.9))
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(repository.count(), 1)
        self.assertEqual(second.observation.research_price, first.observation.research_price)
        self.assertEqual(second.observation.observation_checksum, first.observation.observation_checksum)

    def test_checksum_is_deterministic_for_same_logical_context(self):
        first = self.repository().capture(self.context()).observation
        second_path = Path(self.temp_dir.name) / "second.sqlite"
        second = ForwardResearchObservationRepository(second_path, now=lambda: self.capture_time).capture(self.context()).observation
        self.assertEqual(first.observation_checksum, second.observation_checksum)

    def test_no_future_outcome_fields_are_stored(self):
        observation = self.repository().capture(self.context()).observation
        self.assertFalse(any("future" in key or "target" in key or "outperform" in key for key in observation.__dict__))
        self.assertFalse(any("future" in row[1] or "target" in row[1] for row in self.schema_columns()))

    def test_missing_required_local_data_fails_safely(self):
        with self.assertRaisesRegex(ForwardResearchObservationError, "有限數值"):
            self.repository().capture(self.context(research_price=math.nan))

    def test_local_context_never_fetches_network_data(self):
        context = build_local_observation_context(
            stock_series=self.series("2330.TW"),
            benchmark_series=self.series("0050.TW"),
            company_name="台積電",
            industry="半導體業",
            in_watchlist=True,
            long_term_research_available=False,
            historical_trends_available=False,
            ai_research_available=False,
            swing_research_available=False,
        )
        self.assertEqual(context.market_data_source, "LOCAL_LIVE_HISTORICAL_CACHE")
        self.assertEqual(context.as_of_date, date(2026, 8, 28))

    def test_relative_fields_require_exact_date_alignment(self):
        benchmark = self.series("0050.TW", omit_dates={date(2026, 8, 8)})
        context = build_local_observation_context(
            stock_series=self.series("2330.TW"),
            benchmark_series=benchmark,
            company_name=None,
            industry=None,
            in_watchlist=False,
            long_term_research_available=False,
            historical_trends_available=False,
            ai_research_available=False,
            swing_research_available=False,
        )
        self.assertEqual(context.relative_alignment_status, RELATIVE_ALIGNMENT_UNAVAILABLE)
        self.assertIsNone(context.rel_return_20d)
        self.assertIsNone(context.rel_return_60d)

    def test_relative_fields_are_captured_when_exact_dates_exist(self):
        context = build_local_observation_context(
            stock_series=self.series("2330.TW"),
            benchmark_series=self.series("0050.TW"),
            company_name=None,
            industry=None,
            in_watchlist=False,
            long_term_research_available=False,
            historical_trends_available=False,
            ai_research_available=False,
            swing_research_available=False,
        )
        self.assertEqual(context.relative_alignment_status, RELATIVE_ALIGNMENT_AVAILABLE)
        self.assertIsNotNone(context.rel_return_20d)
        self.assertIsNotNone(context.rel_return_60d)

    def test_production_path_is_never_used(self):
        result = self.repository().capture(self.context())
        self.assertTrue(self.db_path.exists())
        self.assertNotIn("production", str(self.db_path))
        self.assertEqual(result.observation.point_in_time_classification, POINT_IN_TIME_CLASSIFICATION)
        self.assertEqual(result.observation.observation_version, FORWARD_RESEARCH_OBSERVATION_VERSION)

    def test_live_cache_reader_uses_existing_local_rows_only(self):
        live_path = Path(self.temp_dir.name) / "stocks_live.db"
        save_historical_prices(self.series("2330.TW"), db_path=live_path, full_history_fetched=True)
        loaded = load_live_historical_price_series("2330.TW", db_path=live_path)
        self.assertEqual(loaded.bars[-1].trading_date, date(2026, 8, 28))
        self.assertEqual(loaded.bars[-1].adjusted_close, 169.0)

    def test_weekend_freshness_accepts_latest_friday_bar(self):
        live_path = Path(self.temp_dir.name) / "stocks_live.db"
        save_historical_prices(self.series("2330.TW"), db_path=live_path, full_history_fetched=True)
        save_historical_prices(self.series("0050.TW"), db_path=live_path, full_history_fetched=True)
        status = live_market_data_status(
            "2330.TW",
            captured_at=self.capture_time,
            db_path=live_path,
        )
        self.assertEqual(status.expected_latest_date, date(2026, 8, 28))
        self.assertTrue(status.selected_market_data_is_fresh)

    def test_stale_market_data_cannot_be_saved(self):
        with self.assertRaisesRegex(ForwardResearchObservationError, "市場資料過舊"):
            self.repository().capture(self.context(as_of_date=date(2026, 8, 21), data_date=date(2026, 8, 21)))

    def repository(self, now: datetime | None = None) -> ForwardResearchObservationRepository:
        return ForwardResearchObservationRepository(self.db_path, now=lambda: now or self.capture_time)

    def context(self, **overrides) -> ForwardResearchObservationContext:
        values = {
            "symbol": "2330.TW",
            "company_name": "台積電",
            "industry": "半導體業",
            "as_of_date": date(2026, 8, 28),
            "research_price": 100.0,
            "return_20d": 0.05,
            "return_60d": 0.12,
            "close_vs_sma20": 0.03,
            "close_vs_sma60": 0.06,
            "rsi14": 55.0,
            "rel_return_20d": 0.01,
            "rel_return_60d": 0.02,
            "relative_alignment_status": RELATIVE_ALIGNMENT_AVAILABLE,
            "in_watchlist": True,
            "long_term_research_available": True,
            "historical_trends_available": True,
            "ai_research_available": True,
            "swing_research_available": True,
            "data_date": date(2026, 8, 28),
        }
        values.update(overrides)
        return ForwardResearchObservationContext(**values)

    def series(self, symbol: str, omit_dates: set[date] | None = None) -> HistoricalPriceSeries:
        omit_dates = omit_dates or set()
        end_date = date(2026, 8, 28)
        bars = []
        for index in range(70):
            trading_date = end_date - timedelta(days=69 - index)
            if trading_date in omit_dates:
                continue
            price = 100.0 + index
            bars.append(
                HistoricalPriceBar(
                    symbol=symbol,
                    trading_date=trading_date,
                    open=price,
                    high=price + 1.0,
                    low=price - 1.0,
                    close=price,
                    adjusted_close=price,
                    volume=1000,
                )
            )
        return HistoricalPriceSeries(symbol=symbol, currency="TWD", bars=tuple(bars), fetched_at=self.capture_time)

    def schema_columns(self):
        connection = __import__("sqlite3").connect(self.db_path)
        try:
            return connection.execute("PRAGMA table_info(forward_research_observations)").fetchall()
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
