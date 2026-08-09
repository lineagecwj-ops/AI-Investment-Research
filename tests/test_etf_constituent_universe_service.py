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

from etf_constituent_universe_service import COVERAGE_AVAILABLE_LOCAL
from etf_constituent_universe_service import COVERAGE_INSUFFICIENT
from etf_constituent_universe_service import COVERAGE_MISSING_LOCAL
from etf_constituent_universe_service import EXCLUSION_INVALID_SYMBOL
from etf_constituent_universe_service import EXCLUSION_NON_STOCK
from etf_constituent_universe_service import ETFConstituentRecord
from etf_constituent_universe_service import ETFConstituentSnapshot
from etf_constituent_universe_service import ETFConstituentUniverseError
from etf_constituent_universe_service import ETFUniverseBuildResult
from etf_constituent_universe_service import ETFUniverseSource
from etf_constituent_universe_service import FrozenETFUniverse
from etf_constituent_universe_service import SOURCE_STATUS_AVAILABLE
from etf_constituent_universe_service import SOURCE_STATUS_UNAVAILABLE
from etf_constituent_universe_service import SymbolCoverageAudit
from etf_constituent_universe_service import UNIVERSE_VERSION
from etf_constituent_universe_service import audit_universe_local_coverage
from etf_constituent_universe_service import build_frozen_etf_universe
from etf_constituent_universe_service import build_source_unavailable_universe
from etf_constituent_universe_service import build_universe_with_coverage_audit
from etf_constituent_universe_service import database_file_audit
from etf_constituent_universe_service import mark_sources_unavailable
from etf_constituent_universe_service import normalize_constituent_record
from etf_constituent_universe_service import predefined_etf_sources


FETCHED_AT = datetime(2026, 8, 9, 4, 0, tzinfo=UTC).isoformat()
RETRIEVED_AT = datetime(2026, 8, 9, 4, 30, tzinfo=UTC)


class ETFConstituentUniverseServiceTestCase(unittest.TestCase):

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

    def insert_symbol(self, symbol, *, start_ordinal=0, end_ordinal=3700):
        rows = []
        for ordinal in range(start_ordinal, end_ordinal):
            trading_date = date.fromordinal(date(2017, 1, 1).toordinal() + ordinal)
            rows.append(
                (
                    symbol,
                    trading_date.isoformat(),
                    10.0,
                    11.0,
                    9.0,
                    10.0,
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

    def snapshots(self):
        snapshots = []
        for source in predefined_etf_sources():
            constituents = tuple()
            if source.etf_code == "0050":
                constituents = (
                    ETFConstituentRecord(
                        etf_code="0050",
                        stock_code="2330",
                        stock_name="台積電",
                        raw_market_info="上市",
                        raw_weight=58.98,
                        holdings_date=date(2026, 7, 27),
                        source_url=source.official_source_url,
                    ),
                    ETFConstituentRecord(
                        etf_code="0050",
                        stock_code="TX",
                        stock_name="臺股期貨",
                        raw_market_info="期貨",
                        raw_weight=0.26,
                        holdings_date=date(2026, 7, 27),
                        source_url=source.official_source_url,
                    ),
                )
            elif source.etf_code == "0052":
                constituents = (
                    ETFConstituentRecord(
                        etf_code="0052",
                        stock_code="2330",
                        stock_name="台積電",
                        raw_market_info="TWSE",
                        raw_weight=63.41,
                        holdings_date=date(2026, 6, 30),
                        source_url=source.official_source_url,
                    ),
                    ETFConstituentRecord(
                        etf_code="0052",
                        stock_code="6488",
                        stock_name="環球晶",
                        raw_market_info="TPEx",
                        raw_weight=0.5,
                        holdings_date=date(2026, 6, 30),
                        source_url=source.official_source_url,
                    ),
                )
            elif source.etf_code == "00936":
                constituents = (
                    ETFConstituentRecord(
                        etf_code="00936",
                        stock_code="12AB",
                        stock_name="Invalid",
                        raw_market_info="TWSE",
                        holdings_date=date(2026, 7, 31),
                        source_url=source.official_source_url,
                    ),
                )
            snapshots.append(
                ETFConstituentSnapshot(
                    source=ETFUniverseSource(
                        etf_code=source.etf_code,
                        etf_name=source.etf_name,
                        issuer=source.issuer,
                        category=source.category,
                        official_source_url=source.official_source_url,
                        source_type=source.source_type,
                        source_status=SOURCE_STATUS_AVAILABLE,
                        holdings_date=date(2026, 7, 31),
                        retrieved_date=date(2026, 8, 9),
                        raw_constituent_count=len(constituents),
                    ),
                    constituents=constituents,
                )
            )
        return tuple(snapshots)

    def test_predefined_etf_sources_are_exactly_ordered_and_metadata_complete(self):
        sources = predefined_etf_sources()

        self.assertEqual(
            tuple(source.etf_code for source in sources),
            ("0050", "0051", "0052", "0056", "00733", "00878", "00919", "00936"),
        )
        self.assertEqual(len(sources), 8)
        self.assertTrue(all(source.issuer for source in sources))
        self.assertTrue(all(source.category for source in sources))
        self.assertTrue(all(source.official_source_url.startswith("https://") for source in sources))
        self.assertTrue(all(source.source_type for source in sources))

    def test_build_rejects_out_of_order_or_outcome_selected_sources(self):
        snapshots = self.snapshots()

        with self.assertRaises(ETFConstituentUniverseError):
            build_frozen_etf_universe(tuple(reversed(snapshots)), retrieved_at=RETRIEVED_AT)

    def test_snapshot_metadata_dedup_membership_lineage_and_exclusions(self):
        universe = build_frozen_etf_universe(self.snapshots(), retrieved_at=RETRIEVED_AT)
        by_symbol = {membership.symbol: membership for membership in universe.memberships}

        self.assertEqual(universe.universe_version, UNIVERSE_VERSION)
        self.assertEqual(universe.raw_membership_count, 5)
        self.assertEqual(universe.normalized_membership_count, 3)
        self.assertEqual(universe.unique_stock_count, 2)
        self.assertEqual(universe.dedup_count, 1)
        self.assertEqual(universe.twse_count, 1)
        self.assertEqual(universe.tpex_count, 1)
        self.assertEqual(by_symbol["2330.TW"].source_etfs, ("0050", "0052"))
        self.assertEqual(by_symbol["2330.TW"].etf_membership_count, 2)
        self.assertEqual(by_symbol["6488.TWO"].exchange, "TPEx")
        self.assertEqual(
            tuple(exclusion.reason for exclusion in universe.exclusions),
            (EXCLUSION_NON_STOCK, EXCLUSION_INVALID_SYMBOL),
        )

    def test_tw_two_and_invalid_symbol_normalization(self):
        tw = normalize_constituent_record(
            ETFConstituentRecord("0050", "2330", "台積電", raw_market_info="上市")
        )
        two = normalize_constituent_record(
            ETFConstituentRecord("0052", "6488", "環球晶", raw_market_info="上櫃")
        )
        invalid = normalize_constituent_record(
            ETFConstituentRecord("00936", "ABC", "Invalid", raw_market_info="上市")
        )

        self.assertEqual(tw.symbol, "2330.TW")
        self.assertEqual(two.symbol, "6488.TWO")
        self.assertEqual(invalid.reason, EXCLUSION_INVALID_SYMBOL)

    def test_source_unavailable_handling_keeps_all_sources(self):
        universe = build_source_unavailable_universe(
            reason_by_etf={"0050": "TLS certificate verification failed."},
            retrieved_at=RETRIEVED_AT,
        )
        sources = mark_sources_unavailable(retrieved_date=date(2026, 8, 9))

        self.assertEqual(len(sources), 8)
        self.assertEqual(len(universe.sources), 8)
        self.assertTrue(all(source.source_status == SOURCE_STATUS_UNAVAILABLE for source in universe.sources))
        self.assertEqual(universe.unique_stock_count, 0)
        self.assertIn("TLS", universe.sources[0].unavailable_reason)

    def test_coverage_classification_retains_zero_sample_stock_and_does_not_backfill(self):
        self.insert_symbol("2330.TW")
        self.insert_symbol("6488.TWO", start_ordinal=600)
        universe = build_frozen_etf_universe(self.snapshots(), retrieved_at=RETRIEVED_AT)

        audits = audit_universe_local_coverage(universe, db_path=self.db_path)
        by_symbol = {audit.symbol: audit for audit in audits}

        self.assertEqual(by_symbol["2330.TW"].coverage_status, COVERAGE_AVAILABLE_LOCAL)
        self.assertEqual(by_symbol["6488.TWO"].coverage_status, COVERAGE_INSUFFICIENT)
        self.assertIn("warmup bars", by_symbol["6488.TWO"].detail)
        self.assertNotIn("9999.TW", by_symbol)

    def test_missing_local_classification_and_database_file_unchanged(self):
        self.insert_symbol("2330.TW")
        before = database_file_audit(self.db_path)
        result = build_universe_with_coverage_audit(
            self.snapshots(),
            db_path=self.db_path,
            retrieved_at=RETRIEVED_AT,
        )
        after = database_file_audit(self.db_path)
        by_symbol = {audit.symbol: audit for audit in result.coverage_audits}

        self.assertIsInstance(result, ETFUniverseBuildResult)
        self.assertEqual(by_symbol["6488.TWO"].coverage_status, COVERAGE_MISSING_LOCAL)
        self.assertEqual(before, after)
        self.assertEqual(result.db_before, result.db_after)

    def test_models_do_not_expose_threshold_result_recommendation_fields(self):
        names = {
            field.name
            for model in (
                ETFUniverseSource,
                FrozenETFUniverse,
                SymbolCoverageAudit,
                ETFUniverseBuildResult,
            )
            for field in fields(model)
        }
        forbidden = (
            "score",
            "rank",
            "best_threshold",
            "recommended_threshold",
            "probability",
            "recommendation",
        )

        self.assertFalse(any(term in name for term in forbidden for name in names))


if __name__ == "__main__":
    unittest.main()
