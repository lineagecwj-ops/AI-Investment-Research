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
from etf_constituent_universe_service import PARSER_STATUS_FAILED
from etf_constituent_universe_service import PARSER_STATUS_NOT_RUN
from etf_constituent_universe_service import PARSER_STATUS_PARSED
from etf_constituent_universe_service import SOURCE_STATUS_AVAILABLE
from etf_constituent_universe_service import SOURCE_STATUS_UNAVAILABLE
from etf_constituent_universe_service import SymbolCoverageAudit
from etf_constituent_universe_service import UNIVERSE_VERSION
from etf_constituent_universe_service import audit_universe_local_coverage
from etf_constituent_universe_service import audit_official_source_access
from etf_constituent_universe_service import build_frozen_etf_universe
from etf_constituent_universe_service import build_source_unavailable_universe
from etf_constituent_universe_service import build_universe_with_coverage_audit
from etf_constituent_universe_service import database_file_audit
from etf_constituent_universe_service import mark_sources_unavailable
from etf_constituent_universe_service import normalize_constituent_record
from etf_constituent_universe_service import parse_fubon_asset_page
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
        self.assertEqual(sources[0].official_source_url, "https://www.yuantaetfs.com/product/detail/0050/ratio")
        self.assertEqual(sources[1].official_source_url, "https://www.yuantaetfs.com/product/detail/0051/ratio")
        self.assertEqual(sources[3].official_source_url, "https://www.yuantaetfs.com/product/detail/0056/ratio")
        self.assertEqual(
            sources[2].official_source_url,
            "https://websys.fsit.com.tw/FubonETF/Fund/Assets.aspx?stkId=0052",
        )
        self.assertEqual(
            sources[4].official_source_url,
            "https://websys.fsit.com.tw/FubonETF/Fund/Assets.aspx?stkId=00733",
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

    def test_official_access_audit_records_redirect_tls_and_parser_state_separately(self):
        source = predefined_etf_sources()[2]
        html = """
        <html><head><title>富邦投信ETF投資網</title></head>
        <body>
          <p>資料日期：2026/08/07</p>
          <table><tr><td>期貨代碼</td></tr><tr><td>WTEQ6F</td></tr></table>
          <table>
            <tr><td>股票代碼</td><td>股票名稱</td><td>股數</td><td>金額</td><td>權重(%)</td></tr>
            <tr><td>2330</td><td>台積電</td><td>1</td><td>100</td><td>65.37</td></tr>
            <tr><td>2454</td><td>聯發科</td><td>1</td><td>100</td><td>6.49</td></tr>
          </table>
        </body></html>
        """

        audit = audit_official_source_access(
            source,
            fetcher=lambda url: {
                "http_status": 200,
                "final_url": url + "&redirected=1",
                "text": html,
            },
        )

        self.assertEqual(audit.source_access_status, SOURCE_STATUS_AVAILABLE)
        self.assertEqual(audit.http_status, 200)
        self.assertTrue(audit.tls_verified)
        self.assertTrue(audit.constituent_table_available)
        self.assertEqual(audit.holdings_date, date(2026, 8, 7))
        self.assertEqual(audit.parser_status, PARSER_STATUS_PARSED)
        self.assertEqual(audit.raw_constituent_count, 2)
        self.assertIn("redirected=1", audit.final_url)

    def test_parser_failure_is_not_source_unavailable(self):
        source = predefined_etf_sources()[2]
        html = """
        <html><head><title>富邦投信ETF投資網</title></head>
        <body>資料日期：2026/08/07 股票代碼 股票名稱 權重</body></html>
        """

        audit = audit_official_source_access(
            source,
            fetcher=lambda url: {
                "http_status": 200,
                "final_url": url,
                "text": html,
            },
        )

        self.assertEqual(audit.source_access_status, SOURCE_STATUS_AVAILABLE)
        self.assertEqual(audit.parser_status, PARSER_STATUS_FAILED)
        self.assertIn("No Fubon stock holdings table", audit.error)

    def test_tls_failure_is_source_unavailable_and_parser_not_run(self):
        source = predefined_etf_sources()[0]

        audit = audit_official_source_access(
            source,
            fetcher=lambda _url: (_ for _ in ()).throw(RuntimeError("certificate verify failed")),
        )

        self.assertEqual(audit.source_access_status, SOURCE_STATUS_UNAVAILABLE)
        self.assertFalse(audit.tls_verified)
        self.assertEqual(audit.parser_status, PARSER_STATUS_NOT_RUN)
        self.assertIn("certificate verify failed", audit.error)

    def test_parse_fubon_asset_page_uses_only_stock_holdings_table(self):
        html = """
        <html><body>
          <table><tr><td>期貨代碼</td><td>期貨名稱</td></tr><tr><td>WTEQ6F</td><td>電子期貨</td></tr></table>
          <table>
            <tr><td>股票代碼</td><td>股票名稱</td><td>股數</td><td>金額</td><td>權重(%)</td></tr>
            <tr><td>2330</td><td>台積電</td><td>44,371,027</td><td>105,159,333,990</td><td>65.3782</td></tr>
            <tr><td>2454</td><td>聯發科</td><td>2,679,703</td><td>10,450,841,700</td><td>6.4973</td></tr>
          </table>
        </body></html>
        """

        records = parse_fubon_asset_page(
            html,
            etf_code="0052",
            holdings_date=date(2026, 8, 7),
            source_url="https://websys.fsit.com.tw/FubonETF/Fund/Assets.aspx?stkId=0052",
        )

        self.assertEqual(tuple(record.stock_code for record in records), ("2330", "2454"))
        self.assertEqual(records[0].raw_weight, 65.3782)
        self.assertEqual(records[0].holdings_date, date(2026, 8, 7))

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
