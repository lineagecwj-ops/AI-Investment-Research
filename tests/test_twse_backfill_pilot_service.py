import json
import sqlite3
import sys
import tempfile
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

from database import initialize_database
from etf_constituent_universe_service import COVERAGE_AVAILABLE_LOCAL
from etf_constituent_universe_service import COVERAGE_MISSING_LOCAL
from etf_constituent_universe_service import ETFConstituentMembership
from etf_constituent_universe_service import FrozenETFUniverse
from etf_constituent_universe_service import NORMALIZATION_COMPLETE
from etf_constituent_universe_service import SymbolCoverageAudit
from etf_constituent_universe_service import TPEX
from etf_constituent_universe_service import TWSE
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from twse_backfill_pilot_service import PILOT_SYMBOL_COUNT
from twse_backfill_pilot_service import PRICE_SEMANTICS_CONTRACT
from twse_backfill_pilot_service import TWSEBackfillPilotError
from twse_backfill_pilot_service import build_twse_missing_local_candidate_pool
from twse_backfill_pilot_service import create_sqlite_backup
from twse_backfill_pilot_service import equal_spaced_indexes
from twse_backfill_pilot_service import freeze_pilot_selection
from twse_backfill_pilot_service import save_pilot_price_series_transaction
from twse_backfill_pilot_service import select_twse_backfill_pilot
from twse_backfill_pilot_service import validate_price_series_for_backfill
from twse_backfill_pilot_service import verify_sqlite_backup_read_only


FETCHED_AT = datetime(2026, 8, 9, 6, 0, tzinfo=UTC)
APPROVED_SYMBOLS = (
    "1101.TW",
    "1444.TW",
    "1605.TW",
    "2059.TW",
    "2316.TW",
    "2360.TW",
    "2406.TW",
    "2466.TW",
    "2603.TW",
    "2801.TW",
    "2885.TW",
    "3023.TW",
    "3231.TW",
    "3708.TW",
    "5269.TW",
    "6226.TW",
    "6525.TW",
    "6834.TW",
    "8210.TW",
    "9946.TW",
)
APPROVED_INDEXES = (
    0,
    11,
    22,
    34,
    45,
    56,
    67,
    78,
    90,
    101,
    112,
    123,
    135,
    146,
    157,
    168,
    179,
    191,
    202,
    213,
)
APPROVED_CANDIDATE_COUNT = 214
APPROVED_CANDIDATE_CHECKSUM = "ebd2293e75861fd7dfc86e8f54c3efeb5d3b54f7347e42d82b77a8b9468657d0"
MANIFEST_PATH = PROJECT_ROOT / "docs" / "research_inputs" / "twse_backfill_pilot_2026_08_v1.json"


class TWSEBackfillPilotServiceTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        initialize_database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def universe(self, count=30):
        memberships = []
        for index in range(count):
            stock_code = f"{1100 + index:04d}"
            memberships.append(
                ETFConstituentMembership(
                    symbol=f"{stock_code}.TW",
                    stock_code=stock_code,
                    stock_name=f"上市{stock_code}",
                    exchange=TWSE,
                    source_etfs=("0051",),
                    etf_membership_count=1,
                )
            )
        memberships.extend(
            (
                ETFConstituentMembership(
                    symbol="2330.TW",
                    stock_code="2330",
                    stock_name="台積電",
                    exchange=TWSE,
                    source_etfs=("0050",),
                    etf_membership_count=1,
                ),
                ETFConstituentMembership(
                    symbol="5347.TWO",
                    stock_code="5347",
                    stock_name="世界",
                    exchange=TPEX,
                    source_etfs=("00936",),
                    etf_membership_count=1,
                ),
            )
        )
        return FrozenETFUniverse(
            universe_version="test",
            sources=tuple(),
            memberships=tuple(memberships),
            exclusions=tuple(),
            retrieval_timestamps=(FETCHED_AT,),
            holdings_dates=tuple(),
            raw_membership_count=len(memberships),
            normalized_membership_count=len(memberships),
            unique_stock_count=len(memberships),
            dedup_count=0,
            twse_count=count + 1,
            tpex_count=1,
            excluded_count=0,
            normalization_status=NORMALIZATION_COMPLETE,
        )

    def coverage(self, universe, *, available=("2330.TW",), extra_available=tuple()):
        available_set = set(available) | set(extra_available)
        return tuple(
            SymbolCoverageAudit(
                symbol=membership.symbol,
                coverage_status=(
                    COVERAGE_AVAILABLE_LOCAL
                    if membership.symbol in available_set
                    else COVERAGE_MISSING_LOCAL
                ),
                earliest_raw_price_date=None,
                latest_raw_price_date=None,
                total_rows=0,
                observation_window_rows=0,
                warmup_available_bars=0,
                post_window_available_bars=0,
                duplicate_date_count=0,
                invalid_ohlcv_rows=0,
            )
            for membership in universe.memberships
        )

    def series(self, symbol="1100.TW", *, rows=3, bad_bar=None):
        bars = [
            HistoricalPriceBar(
                symbol=symbol,
                trading_date=date(2025, 1, 1) + timedelta(days=index),
                open=10.0 + index,
                high=11.0 + index,
                low=9.0 + index,
                close=10.5 + index,
                adjusted_close=10.4 + index,
                volume=1000 + index,
                dividends=0.0,
                stock_splits=0.0,
            )
            for index in range(rows)
        ]
        if bad_bar is not None:
            bars.append(bad_bar)
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="TWD",
            bars=tuple(bars),
            fetched_at=FETCHED_AT,
            source="Yahoo Finance",
        )

    def test_candidate_pool_only_missing_local_twse_and_excludes_available_tpex(self):
        universe = self.universe()
        candidates = build_twse_missing_local_candidate_pool(universe, self.coverage(universe))

        symbols = tuple(candidate.symbol for candidate in candidates)
        self.assertNotIn("2330.TW", symbols)
        self.assertNotIn("5347.TWO", symbols)
        self.assertTrue(all(candidate.exchange == TWSE for candidate in candidates))
        self.assertTrue(all(candidate.coverage_status == COVERAGE_MISSING_LOCAL for candidate in candidates))

    def test_selection_uses_exact_20_equal_spacing_and_stable_ordering(self):
        universe = self.universe(count=30)
        selection = select_twse_backfill_pilot(universe, self.coverage(universe))

        self.assertEqual(selection.selected_count, PILOT_SYMBOL_COUNT)
        self.assertEqual(selection.selected_indexes, equal_spaced_indexes(30, 20))
        self.assertEqual(selection.selected_candidates[0].symbol, "1100.TW")
        self.assertEqual(selection.selected_candidates[-1].symbol, "1129.TW")
        self.assertEqual(len(set(selection.selected_indexes)), 20)

    def test_approved_phase6a_manifest_freezes_symbols_indexes_and_checksum(self):
        manifest = json.loads(MANIFEST_PATH.read_text())

        self.assertEqual(manifest["pilot_version"], "2026-08-twse-backfill-pilot-v1")
        self.assertEqual(manifest["frozen_universe_version"], "2026-08-current-etf-constituent-v1")
        self.assertEqual(manifest["candidate_count"], APPROVED_CANDIDATE_COUNT)
        self.assertEqual(manifest["selected_count"], PILOT_SYMBOL_COUNT)
        self.assertEqual(manifest["candidate_ordering"], "numeric stock_code ascending")
        self.assertEqual(manifest["candidate_checksum"], APPROVED_CANDIDATE_CHECKSUM)
        self.assertEqual(tuple(row["symbol"] for row in manifest["selected"]), APPROVED_SYMBOLS)
        self.assertEqual(tuple(row["candidate_index"] for row in manifest["selected"]), APPROVED_INDEXES)
        self.assertTrue(all(row["exchange"] == TWSE for row in manifest["selected"]))
        self.assertTrue(all(row["coverage_status"] == COVERAGE_MISSING_LOCAL for row in manifest["selected"]))
        self.assertFalse(manifest["candidate_filters"]["used_hhr_threshold_scanner_backtest_return"])
        self.assertFalse(manifest["live_backfill_gate"]["db_write_performed"])
        self.assertFalse(manifest["live_backfill_gate"]["price_download_performed"])
        self.assertFalse(manifest["live_backfill_gate"]["threshold_research_performed"])

    def test_approved_selection_indexes_match_formula_for_candidate_count(self):
        self.assertEqual(equal_spaced_indexes(APPROVED_CANDIDATE_COUNT, PILOT_SYMBOL_COUNT), APPROVED_INDEXES)

    def test_selection_freeze_records_checksum_symbols_and_positions(self):
        universe = self.universe(count=30)
        selection = select_twse_backfill_pilot(universe, self.coverage(universe))
        freeze = freeze_pilot_selection(selection, generated_at=FETCHED_AT)
        again = select_twse_backfill_pilot(universe, self.coverage(universe))

        self.assertEqual(freeze.selected_symbols, tuple(candidate.symbol for candidate in selection.selected_candidates))
        self.assertEqual(freeze.selected_indexes, selection.selected_indexes)
        self.assertEqual(selection.ordered_candidate_checksum, again.ordered_candidate_checksum)
        self.assertEqual(freeze.generated_at, FETCHED_AT)

    def test_selection_independent_from_outcome_like_available_extra_changes_only_coverage(self):
        universe = self.universe(count=30)
        base = select_twse_backfill_pilot(universe, self.coverage(universe))
        with_available = select_twse_backfill_pilot(
            universe,
            self.coverage(universe, extra_available=("1110.TW",)),
        )

        self.assertNotEqual(
            tuple(candidate.symbol for candidate in base.selected_candidates),
            tuple(candidate.symbol for candidate in with_available.selected_candidates),
        )
        self.assertNotIn("1110.TW", tuple(candidate.symbol for candidate in with_available.selected_candidates))

    def test_duplicate_date_rejection(self):
        duplicate = HistoricalPriceBar("1100.TW", date(2025, 1, 1), 10.0, 11.0, 9.0, 10.0, 10.0, 1)
        report = validate_price_series_for_backfill(self.series(bad_bar=duplicate))

        self.assertEqual(report.status, "INVALID_DATA")
        self.assertEqual(report.duplicate_dates, 1)

    def test_invalid_ohlc_rejection(self):
        invalid = HistoricalPriceBar("1100.TW", date(2025, 1, 4), 10.0, 8.0, 9.0, 10.0, 10.0, 1)
        report = validate_price_series_for_backfill(self.series(bad_bar=invalid))

        self.assertEqual(report.status, "INVALID_DATA")
        self.assertEqual(report.invalid_ohlc, 1)

    def test_mixed_symbol_rejection(self):
        mixed = HistoricalPriceBar("9999.TW", date(2025, 1, 4), 10.0, 11.0, 9.0, 10.0, 10.0, 1)
        report = validate_price_series_for_backfill(self.series(bad_bar=mixed))

        self.assertEqual(report.status, "INVALID_DATA")
        self.assertEqual(report.mixed_symbol_rows, 1)

    def test_late_listing_semantics_remain_valid_price_data(self):
        series = self.series("6834.TW", rows=5)
        report = validate_price_series_for_backfill(series)

        self.assertEqual(report.status, COVERAGE_AVAILABLE_LOCAL)
        self.assertEqual(report.row_count, 5)

    def test_idempotent_second_backfill_does_not_duplicate_rows(self):
        series = self.series(rows=3)
        save_pilot_price_series_transaction(self.db_path, (series,))
        save_pilot_price_series_transaction(self.db_path, (series,))

        connection = sqlite3.connect(self.db_path)
        try:
            count = connection.execute("SELECT COUNT(*) FROM historical_prices WHERE symbol = '1100.TW'").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 3)

    def test_transaction_rolls_back_when_any_series_invalid(self):
        valid = self.series("1100.TW", rows=2)
        invalid = self.series(
            "1101.TW",
            rows=1,
            bad_bar=HistoricalPriceBar("1101.TW", date(2025, 1, 1), 10.0, 11.0, 9.0, 10.0, 10.0, 1),
        )

        with self.assertRaises(TWSEBackfillPilotError):
            save_pilot_price_series_transaction(self.db_path, (valid, invalid))

        connection = sqlite3.connect(self.db_path)
        try:
            count = connection.execute("SELECT COUNT(*) FROM historical_prices").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 0)

    def test_backup_creation_and_integrity(self):
        backup_path = Path(self.temp_dir.name) / "backups" / "before.db"
        audit = create_sqlite_backup(self.db_path, backup_path)

        self.assertTrue(backup_path.exists())
        self.assertGreater(audit.size_bytes, 0)
        self.assertEqual(audit.integrity_check, "ok")
        self.assertEqual(verify_sqlite_backup_read_only(backup_path), "ok")

    def test_coverage_transition_after_temp_backfill(self):
        universe = self.universe(count=20)
        series = self.series("1100.TW", rows=70)
        save_pilot_price_series_transaction(self.db_path, (series,))

        connection = sqlite3.connect(self.db_path)
        try:
            count = connection.execute("SELECT COUNT(*) FROM historical_prices WHERE symbol = '1100.TW'").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 70)

    def test_no_threshold_research_terms_in_pilot_service_contract(self):
        service_path = SRC_PATH / "twse_backfill_pilot_service.py"
        text = service_path.read_text()

        self.assertNotIn("volume_ratio_20", text)
        self.assertNotIn("historical_hit_rate", text)
        self.assertNotIn("backtest", text.lower())

    def test_price_semantics_contract_matches_existing_yahoo_loader(self):
        from database import HISTORICAL_PRICE_COLUMNS
        from historical_price_service import PRICE_SOURCE
        from historical_price_service import YAHOO_ACTIONS
        from historical_price_service import YAHOO_AUTO_ADJUST
        from historical_price_service import get_analysis_close

        bar = HistoricalPriceBar("1100.TW", date(2025, 1, 1), 10.0, 11.0, 9.0, 10.0, 10.5, 1000)
        fallback = HistoricalPriceBar("1100.TW", date(2025, 1, 2), 10.0, 11.0, 9.0, 10.0, None, 1000)

        self.assertEqual(PRICE_SEMANTICS_CONTRACT["source"], f"{PRICE_SOURCE} via yfinance")
        self.assertEqual(PRICE_SEMANTICS_CONTRACT["auto_adjust"], YAHOO_AUTO_ADJUST)
        self.assertEqual(PRICE_SEMANTICS_CONTRACT["actions"], YAHOO_ACTIONS)
        self.assertEqual(PRICE_SEMANTICS_CONTRACT["db_columns"], tuple(HISTORICAL_PRICE_COLUMNS))
        self.assertEqual(get_analysis_close(bar), 10.5)
        self.assertEqual(get_analysis_close(fallback), 10.0)

    def test_pilot_service_import_contract_has_no_network_or_database_side_effects(self):
        service_text = (SRC_PATH / "twse_backfill_pilot_service.py").read_text()

        self.assertNotIn("import yfinance", service_text)
        self.assertNotIn("import requests", service_text)
        self.assertNotIn("yf.", service_text)
        self.assertEqual(service_text.count("sqlite3.connect"), 4)


if __name__ == "__main__":
    unittest.main()
