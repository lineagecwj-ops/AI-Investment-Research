import sqlite3
import sys
import tempfile
import unittest
from dataclasses import fields
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
from expanded_volume_threshold_validation_service import ExpandedSymbolUniverseConfig
from expanded_volume_threshold_validation_service import ExpandedThresholdSymbolSummary
from expanded_volume_threshold_validation_service import ExpandedThresholdYearSummary
from expanded_volume_threshold_validation_service import ExpandedVolumeThresholdValidationResult
from expanded_volume_threshold_validation_service import ORIGINAL_FIVE_SYMBOLS
from expanded_volume_threshold_validation_service import SymbolBreadthSummary
from expanded_volume_threshold_validation_service import SymbolCoverageAudit
from expanded_volume_threshold_validation_service import audit_expanded_symbol_universe


FETCHED_AT = datetime(2026, 8, 9, 3, 0, tzinfo=UTC).isoformat()


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

    def test_universe_audit_is_deterministic_coverage_based_and_keeps_original_five(self):
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
        self.assertTrue(all(by_symbol[symbol].included for symbol in ORIGINAL_FIVE_SYMBOLS))
        self.assertTrue(by_symbol["6488.TWO"].included)
        self.assertFalse(by_symbol["AAPL"].included)
        self.assertEqual(by_symbol["AAPL"].exclusion_reason, EXCLUDED_NOT_TAIWAN_UNIVERSE)
        self.assertFalse(by_symbol["1111.TW"].included)
        self.assertEqual(by_symbol["1111.TW"].exclusion_reason, EXCLUDED_DATA_COVERAGE)
        self.assertIn("warmup bars", by_symbol["1111.TW"].exclusion_detail)
        self.assertFalse(by_symbol["2222.TW"].included)
        self.assertIn("invalid OHLCV", by_symbol["2222.TW"].exclusion_detail)

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
