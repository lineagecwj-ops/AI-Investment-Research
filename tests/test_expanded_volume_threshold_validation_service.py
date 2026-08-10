import sqlite3
import sys
import tempfile
import unittest
import json
import hashlib
from dataclasses import fields
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from expanded_volume_threshold_validation_service import EXCLUDED_DATA_COVERAGE
from expanded_volume_threshold_validation_service import EXCLUDED_NOT_TAIWAN_UNIVERSE
from expanded_volume_threshold_validation_service import DEFAULT_DB_PATH
from expanded_volume_threshold_validation_service import ExpandedSymbolUniverseConfig
from expanded_volume_threshold_validation_service import ExpandedThresholdSymbolSummary
from expanded_volume_threshold_validation_service import ExpandedThresholdYearSummary
from expanded_volume_threshold_validation_service import ExpandedVolumeThresholdValidationError
from expanded_volume_threshold_validation_service import ExpandedVolumeThresholdValidationResult
from expanded_volume_threshold_validation_service import LISTING_DATE_SOURCE_FALLBACK
from expanded_volume_threshold_validation_service import LISTING_DATE_SOURCE_OFFICIAL_SNAPSHOT
from expanded_volume_threshold_validation_service import ORIGINAL_FIVE_SYMBOLS
from expanded_volume_threshold_validation_service import READINESS_DATA_QUALITY_BLOCKED
from expanded_volume_threshold_validation_service import READINESS_FULL_WINDOW_ELIGIBLE
from expanded_volume_threshold_validation_service import READINESS_PARTIAL_WINDOW_VALID
from expanded_volume_threshold_validation_service import SymbolBreadthSummary
from expanded_volume_threshold_validation_service import SymbolCoverageAudit
from expanded_volume_threshold_validation_service import audit_expanded_symbol_universe
from expanded_volume_threshold_validation_service import is_final_listing_date_source
from expanded_volume_threshold_validation_service import load_twse_listing_date_snapshot
from expanded_volume_threshold_validation_service import load_historical_price_series_read_only
from expanded_volume_threshold_validation_service import run_final_expanded_volume_threshold_validation
from expanded_volume_threshold_validation_service import _materialized_twse_common_stock_symbols
from expanded_volume_threshold_validation_service import _prepare_research_inputs
from expanded_volume_threshold_validation_service import _readiness_classification_by_symbol
from expanded_volume_threshold_validation_service import _readiness_counts


FETCHED_AT = datetime(2026, 8, 9, 3, 0, tzinfo=UTC).isoformat()


@dataclass(frozen=True)
class FakeObservationStatus:

    name: str


@dataclass(frozen=True)
class FakeOutcomeObservation:

    symbol: str

    trading_date: date

    status: FakeObservationStatus


class ExpandedVolumeThresholdValidationServiceTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE historical_prices (
                    symbol TEXT NOT NULL,
                    trading_date TEXT NOT NULL,
                    open REAL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    adjusted_close REAL,
                    volume INTEGER,
                    dividends REAL,
                    stock_splits REAL,
                    currency TEXT,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY(symbol, trading_date)
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def insert_symbol(self, symbol, *, start_ordinal=0, end_ordinal=3700, invalid=False):
        rows = []
        for ordinal in range(start_ordinal, end_ordinal):
            trading_date = date.fromordinal(date(2017, 1, 1).toordinal() + ordinal)
            high = 11.0
            low = 9.0
            close = 10.0
            if invalid and ordinal == start_ordinal:
                high = 8.0
            rows.append(
                (
                    symbol,
                    trading_date.isoformat(),
                    10.0,
                    high,
                    low,
                    close,
                    10.0,
                    1000,
                    0.0,
                    0.0,
                    "TWD",
                    FETCHED_AT,
                )
            )
        connection = sqlite3.connect(self.db_path)
        try:
            connection.executemany(
                """
                INSERT INTO historical_prices (
                    symbol, trading_date, open, high, low, close, adjusted_close,
                    volume, dividends, stock_splits, currency, fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.commit()
        finally:
            connection.close()

    def write_listing_snapshot(self, records):
        payload = {
            "source_authority": "Taiwan Stock Exchange OpenAPI listed company basic data",
            "source_url": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
            "source_report_date": "2026-08-09",
            "source_report_date_raw": "1150809",
            "retrieved_at": "2026-08-10T00:00:00Z",
            "source_checksum": "source-sha",
            "records": records,
        }
        stable = dict(payload)
        stable.pop("retrieved_at")
        payload["snapshot_checksum"] = hashlib.sha256(
            json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        path = Path(self.temp_dir.name) / "twse_listing_dates.json"
        path.write_text(json.dumps(payload, ensure_ascii=False))
        return path

    def test_universe_audit_is_deterministic_twse_common_stock_based(self):
        for symbol in ORIGINAL_FIVE_SYMBOLS:
            self.insert_symbol(symbol)
        self.insert_symbol("6488.TWO")
        self.insert_symbol("AAPL")
        self.insert_symbol("1111.TW", start_ordinal=700)
        self.insert_symbol("2222.TW", invalid=True)

        first = audit_expanded_symbol_universe(db_path=self.db_path)
        second = audit_expanded_symbol_universe(db_path=self.db_path)
        by_symbol = {audit.symbol: audit for audit in first}

        self.assertEqual(first, second)
        self.assertEqual(tuple(audit.symbol for audit in first), tuple(sorted(by_symbol)))
        self.assertFalse(by_symbol["0050.TW"].included)
        self.assertTrue(all(by_symbol[symbol].included for symbol in ("2330.TW", "2337.TW", "2404.TW", "2454.TW")))
        self.assertFalse(by_symbol["6488.TWO"].included)
        self.assertFalse(by_symbol["AAPL"].included)
        self.assertEqual(by_symbol["AAPL"].exclusion_reason, EXCLUDED_NOT_TAIWAN_UNIVERSE)
        self.assertTrue(by_symbol["1111.TW"].included)
        self.assertFalse(by_symbol["2222.TW"].included)
        self.assertIn("invalid OHLCV", by_symbol["2222.TW"].exclusion_detail)

    def test_official_listing_date_trims_synthetic_pre_listing_bars_before_warmup(self):
        self.insert_symbol("1111.TW", start_ordinal=0, end_ordinal=220)

        raw = load_historical_price_series_read_only("1111.TW", db_path=self.db_path)
        self.assertLess(raw.bars[0].trading_date, date(2017, 3, 1))

        price_series, technical_series = _prepare_research_inputs(
            ("1111.TW",),
            db_path=self.db_path,
            official_listing_dates_by_symbol={"1111.TW": date(2017, 3, 1)},
        )

        prepared = price_series["1111.TW"]
        self.assertGreaterEqual(prepared.bars[0].trading_date, date(2017, 3, 1))
        self.assertIn("1111.TW", technical_series)

    def test_official_listing_date_snapshot_parses_with_checksum_and_required_coverage(self):
        path = self.write_listing_snapshot(
            (
                {"stock_code": "1111", "stock_name": "Example One", "listing_date": "2017-03-01"},
                {"stock_code": "2222", "stock_name": "Example Two", "listing_date": "2018-04-02"},
            )
        )

        snapshot = load_twse_listing_date_snapshot(
            path,
            required_symbols=("1111.TW", "2222.TW"),
        )

        self.assertEqual(snapshot.source_report_date, date(2026, 8, 9))
        self.assertEqual(snapshot.listing_dates_by_symbol["1111.TW"], date(2017, 3, 1))
        self.assertEqual(len(snapshot.records), 2)

    def test_missing_official_listing_date_blocks_final_runner(self):
        self.insert_symbol("1111.TW")
        self.insert_symbol("2222.TW")
        path = self.write_listing_snapshot(
            ({"stock_code": "1111", "stock_name": "Example One", "listing_date": "2017-03-01"},)
        )

        with self.assertRaisesRegex(ExpandedVolumeThresholdValidationError, "missing 1 required symbols"):
            run_final_expanded_volume_threshold_validation(
                listing_date_snapshot_path=path,
                db_path=self.db_path,
            )

    def test_snapshot_checksum_mismatch_blocks_loading(self):
        path = self.write_listing_snapshot(
            ({"stock_code": "1111", "stock_name": "Example One", "listing_date": "2017-03-01"},)
        )
        payload = json.loads(path.read_text())
        payload["records"][0]["listing_date"] = "2017-03-02"
        path.write_text(json.dumps(payload, ensure_ascii=False))

        with self.assertRaisesRegex(ExpandedVolumeThresholdValidationError, "checksum mismatch"):
            load_twse_listing_date_snapshot(path, required_symbols=("1111.TW",))

    def test_snapshot_duplicate_and_invalid_dates_block_loading(self):
        duplicate = self.write_listing_snapshot(
            (
                {"stock_code": "1111", "stock_name": "Example One", "listing_date": "2017-03-01"},
                {"stock_code": "1111", "stock_name": "Example One Again", "listing_date": "2017-03-01"},
            )
        )
        with self.assertRaisesRegex(ExpandedVolumeThresholdValidationError, "duplicate stock codes"):
            load_twse_listing_date_snapshot(duplicate)

        invalid = self.write_listing_snapshot(
            ({"stock_code": "2222", "stock_name": "Example Two", "listing_date": "20170301"},)
        )

        with self.assertRaisesRegex(ExpandedVolumeThresholdValidationError, "invalid listing dates"):
            load_twse_listing_date_snapshot(invalid)

    def test_fallback_run_cannot_claim_official_final_source(self):
        self.assertFalse(is_final_listing_date_source(LISTING_DATE_SOURCE_FALLBACK))
        self.assertTrue(is_final_listing_date_source(LISTING_DATE_SOURCE_OFFICIAL_SNAPSHOT))

    def test_official_snapshot_is_loaded_without_network_dependency(self):
        path = self.write_listing_snapshot(
            ({"stock_code": "1111", "stock_name": "Example One", "listing_date": "2017-03-01"},)
        )

        snapshot = load_twse_listing_date_snapshot(path, required_symbols=("1111.TW",))

        self.assertEqual(snapshot.listing_dates_by_symbol, {"1111.TW": date(2017, 3, 1)})

    def test_repository_official_snapshot_covers_materialized_twse_universe(self):
        snapshot_path = PROJECT_ROOT / "docs" / "research_inputs" / "twse_listing_dates_2026_08_09.json"
        symbols = _materialized_twse_common_stock_symbols(DEFAULT_DB_PATH)

        snapshot = load_twse_listing_date_snapshot(snapshot_path, required_symbols=symbols)

        self.assertEqual(len(symbols), 218)
        self.assertEqual(len(snapshot.records), 218)
        self.assertEqual(len(snapshot.listing_dates_by_symbol), 218)
        self.assertEqual(snapshot.source_report_date, date(2026, 8, 9))

    def test_late_listing_with_zero_outcome_observations_is_partial_not_blocked(self):
        readiness = _readiness_classification_by_symbol(
            ("7769.TW",),
            (),
            official_listing_dates_by_symbol={"7769.TW": date(2025, 11, 27)},
            research_start=date(2018, 1, 1),
        )

        self.assertEqual(readiness["7769.TW"], READINESS_PARTIAL_WINDOW_VALID)

    def test_late_listing_takes_precedence_over_full_year_observation_presence(self):
        observations = tuple(
            FakeOutcomeObservation("3711.TW", date(year, 7, 25), FakeObservationStatus("MISS"))
            for year in range(2018, 2026)
        )

        readiness = _readiness_classification_by_symbol(
            ("3711.TW",),
            observations,
            official_listing_dates_by_symbol={"3711.TW": date(2018, 4, 30)},
            research_start=date(2018, 1, 1),
        )

        self.assertEqual(readiness["3711.TW"], READINESS_PARTIAL_WINDOW_VALID)

    def test_pre_window_listing_with_all_years_remains_full_window_eligible(self):
        observations = tuple(
            FakeOutcomeObservation("6531.TW", date(year, 6, 26), FakeObservationStatus("HIT"))
            for year in range(2018, 2026)
        )

        readiness = _readiness_classification_by_symbol(
            ("6531.TW",),
            observations,
            official_listing_dates_by_symbol={"6531.TW": date(2016, 5, 31)},
            research_start=date(2018, 1, 1),
        )

        self.assertEqual(readiness["6531.TW"], READINESS_FULL_WINDOW_ELIGIBLE)

    def test_old_listing_with_zero_outcome_observations_remains_data_quality_blocked(self):
        readiness = _readiness_classification_by_symbol(
            ("9999.TW",),
            (),
            official_listing_dates_by_symbol={"9999.TW": date(2010, 1, 1)},
            research_start=date(2018, 1, 1),
        )

        self.assertEqual(readiness["9999.TW"], READINESS_DATA_QUALITY_BLOCKED)

    def test_readiness_counts_reconcile_universe_total(self):
        readiness = {
            "1111.TW": READINESS_FULL_WINDOW_ELIGIBLE,
            "2222.TW": READINESS_PARTIAL_WINDOW_VALID,
            "3333.TW": READINESS_PARTIAL_WINDOW_VALID,
            "4444.TW": READINESS_DATA_QUALITY_BLOCKED,
        }

        counts = _readiness_counts(readiness)

        self.assertEqual(counts[READINESS_FULL_WINDOW_ELIGIBLE], 1)
        self.assertEqual(counts[READINESS_PARTIAL_WINDOW_VALID], 2)
        self.assertEqual(counts[READINESS_DATA_QUALITY_BLOCKED], 1)
        self.assertEqual(sum(counts.values()), len(readiness))

    def test_selection_models_do_not_expose_result_based_ranking_or_recommendation_fields(self):
        names = {
            field.name
            for model in (
                ExpandedSymbolUniverseConfig,
                SymbolCoverageAudit,
                ExpandedThresholdSymbolSummary,
                ExpandedThresholdYearSummary,
                SymbolBreadthSummary,
                ExpandedVolumeThresholdValidationResult,
            )
            for field in fields(model)
        }
        forbidden = ("recommended", "best", "optimal", "rank", "score", "probability")

        self.assertFalse(any(term in name for term in forbidden for name in names))


if __name__ == "__main__":
    unittest.main()
