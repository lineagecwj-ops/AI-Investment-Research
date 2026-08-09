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
from etf_constituent_universe_service import COMPLETENESS_UNKNOWN
from etf_constituent_universe_service import EXCLUSION_INVALID_SYMBOL
from etf_constituent_universe_service import EXCLUSION_NON_STOCK
from etf_constituent_universe_service import ETFConstituentRecord
from etf_constituent_universe_service import ETFConstituentSnapshot
from etf_constituent_universe_service import ETFConstituentUniverseError
from etf_constituent_universe_service import ETFUniverseBuildResult
from etf_constituent_universe_service import ETFUniverseFinalizationAudit
from etf_constituent_universe_service import ETFUniverseSource
from etf_constituent_universe_service import FrozenETFUniverse
from etf_constituent_universe_service import PARSED_COMPLETE
from etf_constituent_universe_service import PARSED_INCOMPLETE
from etf_constituent_universe_service import PARSER_STATUS_FAILED
from etf_constituent_universe_service import PARSER_STATUS_NOT_RUN
from etf_constituent_universe_service import PARSER_STATUS_PARSED
from etf_constituent_universe_service import OfficialSourceAccessAudit
from etf_constituent_universe_service import PartialParsedUniverseAudit
from etf_constituent_universe_service import SOURCE_STATUS_AVAILABLE
from etf_constituent_universe_service import SOURCE_STATUS_AVAILABLE_HOLDINGS_ENDPOINT_UNRESOLVED
from etf_constituent_universe_service import SOURCE_STATUS_UNAVAILABLE
from etf_constituent_universe_service import SymbolCoverageAudit
from etf_constituent_universe_service import TRANSPORT_CURL_VERIFIED
from etf_constituent_universe_service import UNIVERSE_STATUS_FINALIZED
from etf_constituent_universe_service import UNIVERSE_STATUS_NOT_FINALIZED
from etf_constituent_universe_service import UNIVERSE_VERSION
from etf_constituent_universe_service import audit_etf_universe_finalization
from etf_constituent_universe_service import audit_universe_local_coverage
from etf_constituent_universe_service import audit_official_source_access
from etf_constituent_universe_service import build_partial_parsed_universe_audit
from etf_constituent_universe_service import build_frozen_etf_universe
from etf_constituent_universe_service import build_source_unavailable_universe
from etf_constituent_universe_service import build_universe_with_coverage_audit
from etf_constituent_universe_service import database_file_audit
from etf_constituent_universe_service import mark_sources_unavailable
from etf_constituent_universe_service import normalize_constituent_record
from etf_constituent_universe_service import parse_capital_portfolio_page
from etf_constituent_universe_service import parse_fubon_asset_page
from etf_constituent_universe_service import parse_taishin_holdings_page
from etf_constituent_universe_service import parse_yuanta_pcf_page
from etf_constituent_universe_service import parse_yuanta_ratio_page
from etf_constituent_universe_service import predefined_etf_sources
from etf_constituent_universe_service import _verified_curl_command


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
        self.assertEqual(sources[0].official_source_url, "https://www.yuantaetfs.com/tradeInfo/pcf/0050")
        self.assertEqual(sources[1].official_source_url, "https://www.yuantaetfs.com/tradeInfo/pcf/0051")
        self.assertEqual(sources[3].official_source_url, "https://www.yuantaetfs.com/tradeInfo/pcf/0056")
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
        self.assertEqual(audit.full_row_count, 2)
        self.assertEqual(audit.dedup_constituent_count, 2)
        self.assertEqual(audit.completeness_status, PARSED_COMPLETE)
        self.assertIn("redirected=1", audit.final_url)

    def test_yuanta_ratio_parser_and_verified_curl_transport_do_not_disable_tls(self):
        command = _verified_curl_command("https://www.yuantaetfs.com/product/detail/0050/ratio")
        html = """
        <html><body>
          <h3>基金權重-股票</h3>
          <div class="each_table">
            <div class="tr"><div class="td">商品代碼</div><div class="td">商品名稱</div><div class="td">商品數量</div><div class="td">商品權重</div></div>
            <div class="tr">
              <div class="td"><span>商品代碼</span><span>2330</span></div>
              <div class="td"><span>商品名稱</span><span>台積電</span></div>
              <div class="td"><span>商品數量</span><span>570337837</span></div>
              <div class="td"><span>商品權重</span><span>58.64</span></div>
            </div>
          </div>
        </body></html>
        """
        source = predefined_etf_sources()[0]

        records = parse_yuanta_ratio_page(
            html,
            etf_code="0050",
            holdings_date=date(2026, 8, 7),
            source_url=source.official_source_url,
        )

        self.assertNotIn("-k", command)
        self.assertNotIn("--insecure", command)
        self.assertEqual(records[0].stock_code, "2330")
        self.assertEqual(records[0].raw_weight, 58.64)

    def test_yuanta_pcf_parser_keeps_full_payload_separate_from_visible_preview(self):
        html = """
        <html><body>
          <h3>股票實物申贖</h3>
          <div class="tr"><div>股票代碼</div><div>股票名稱</div><div>是否為現金替代</div><div>可否參予最小實物申購</div><div>股數</div></div>
          <div class="tr"><div>股票代碼 2330</div><div>股票名稱 台積電</div><div>是否為現金替代 N</div><div>可否參予最小實物申購 Y</div><div>股數 1</div></div>
          <script>window.__NUXT__=(function(a,b,c,d,e,f,g,h,i,j){var x=1;return {data:[{}, {pcfData:{FundWeights:{StockWeights:[{code:c,ym:b,name:d,ename:e,weights:58.64,qty:1},{code:f,ym:b,name:g,ename:h,weights:.76,qty:1}]},InKind:{FundComposition:[{stkcd:c,name:d,ename:e,qty:1,cashinlieu:i,minimum:j},{stkcd:f,name:g,ename:h,qty:1,cashinlieu:i,minimum:j}]}}}]}})(false,null,"2330","台積電","TSMC","2454","聯發科","MediaTek","N","Y");</script>
        </body></html>
        """
        source = predefined_etf_sources()[0]

        records, pcf_stock_count = parse_yuanta_pcf_page(
            html,
            etf_code="0050",
            holdings_date=date(2026, 8, 7),
            source_url=source.official_source_url,
        )
        audit = audit_official_source_access(
            source,
            fetcher=lambda url: {
                "http_status": 200,
                "final_url": url,
                "text": html,
                "transport_method": TRANSPORT_CURL_VERIFIED,
            },
        )

        self.assertEqual(tuple(record.stock_code for record in records), ("2330", "2454"))
        self.assertEqual(records[1].raw_weight, 0.76)
        self.assertEqual(pcf_stock_count, 2)
        self.assertEqual(audit.parser_status, PARSER_STATUS_PARSED)
        self.assertEqual(audit.transport_method, TRANSPORT_CURL_VERIFIED)
        self.assertEqual(audit.raw_dom_stock_row_count, 1)
        self.assertEqual(audit.full_row_count, 2)
        self.assertEqual(audit.official_expected_count, 50)
        self.assertEqual(audit.completeness_status, PARSED_INCOMPLETE)

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

    def test_parse_capital_portfolio_deduplicates_responsive_presentation_rows(self):
        html = """
        <html><body>
          <div id="buyback-stocks-section">
            <div class="tr"><div>股票代號</div><div>股票名稱</div><div>持股權重(%)</div><div>股數</div></div>
            <div class="tr show-for-medium"><div>2881</div><div>富邦金</div><div>14.29%</div><div>608,790,000</div></div>
            <div class="tr hide-for-medium"><div>2881</div><div>富邦金</div><div>14.29%</div><div>608,790,000</div></div>
            <div class="tr show-for-medium"><div>2882</div><div>國泰金</div><div>13.10%</div><div>500,000,000</div></div>
          </div>
        </body></html>
        """

        records, raw_dom_rows = parse_capital_portfolio_page(
            html,
            etf_code="00919",
            holdings_date=None,
            source_url="https://www.capitalfund.com.tw/etf/product/detail/195/portfolio",
        )

        self.assertEqual(raw_dom_rows, 3)
        self.assertEqual(tuple(record.stock_code for record in records), ("2881", "2882"))
        self.assertEqual(records[0].raw_weight, 14.29)

    def test_parse_taishin_holdings_keeps_raw_code_without_exchange_guess(self):
        html = """
        <html><body>
          <table>
            <tr><th>代號</th><th>名稱</th><th>股數</th><th>持股權重</th></tr>
            <tr><td>8046 TT</td><td>南電</td><td>100,000</td><td>4.1234%</td></tr>
            <tr><td>5347 TT</td><td>世界</td><td>90,000</td><td>3.0000%</td></tr>
            <tr><td>股票合計</td><td></td><td></td><td>97.1000%</td></tr>
          </table>
        </body></html>
        """

        records = parse_taishin_holdings_page(
            html,
            etf_code="00936",
            holdings_date=date(2026, 7, 31),
            source_url="https://www.tsit.com.tw/ETF/Home/ETFSeriesDetail/00936",
        )

        self.assertEqual(tuple(record.stock_code for record in records), ("8046", "5347"))
        self.assertTrue(all(record.raw_market_info is None for record in records))

    def test_partial_snapshot_audit_is_not_finalized_and_does_not_touch_db(self):
        self.insert_symbol("2330.TW")
        before = database_file_audit(self.db_path)
        snapshots = (
            ETFConstituentSnapshot(
                source=predefined_etf_sources()[0],
                constituents=(
                    ETFConstituentRecord("0050", "2330", "台積電", raw_market_info="上市"),
                    ETFConstituentRecord("0050", "9999", "未知", raw_market_info=None),
                ),
            ),
        )

        audit = build_partial_parsed_universe_audit(snapshots)
        after = database_file_audit(self.db_path)

        self.assertIsInstance(audit, PartialParsedUniverseAudit)
        self.assertEqual(audit.universe_status, UNIVERSE_STATUS_NOT_FINALIZED)
        self.assertEqual(audit.parsed_source_count, 1)
        self.assertEqual(audit.raw_membership_count, 2)
        self.assertEqual(audit.normalized_membership_count, 1)
        self.assertEqual(audit.unique_stock_count, 1)
        self.assertEqual(before, after)

    def test_00878_unresolved_holdings_endpoint_is_not_parser_success(self):
        source = predefined_etf_sources()[5]

        audit = audit_official_source_access(
            source,
            fetcher=lambda url: {
                "http_status": 200,
                "final_url": url,
                "text": "<html><title>00878 國泰永續高股息</title><body>查看基金持股權重</body></html>",
            },
        )

        self.assertEqual(audit.source_access_status, SOURCE_STATUS_AVAILABLE_HOLDINGS_ENDPOINT_UNRESOLVED)
        self.assertEqual(audit.parser_status, PARSER_STATUS_NOT_RUN)
        self.assertEqual(audit.completeness_status, COMPLETENESS_UNKNOWN)

    def test_00919_visible_ten_rows_are_parser_incomplete_until_expanded_rows_exist(self):
        source = predefined_etf_sources()[6]
        html = """
        <html><body>
          <div id="buyback-stocks-section">
            <div class="tr"><div>股票代號</div><div>股票名稱</div><div>持股權重(%)</div><div>股數</div></div>
            <div class="tr"><div>2881</div><div>富邦金</div><div>14.29%</div><div>1</div></div>
            <div class="tr"><div>2882</div><div>國泰金</div><div>13.10%</div><div>1</div></div>
            <div class="tr"><div>2883</div><div>凱基金</div><div>9.10%</div><div>1</div></div>
            <div class="tr"><div>2884</div><div>玉山金</div><div>8.10%</div><div>1</div></div>
            <div class="tr"><div>2885</div><div>元大金</div><div>7.10%</div><div>1</div></div>
            <div class="tr"><div>2886</div><div>兆豐金</div><div>6.10%</div><div>1</div></div>
            <div class="tr"><div>2887</div><div>台新新光金</div><div>5.10%</div><div>1</div></div>
            <div class="tr"><div>2890</div><div>永豐金</div><div>4.10%</div><div>1</div></div>
            <div class="tr"><div>2891</div><div>中信金</div><div>3.10%</div><div>1</div></div>
            <div class="tr"><div>2892</div><div>第一金</div><div>2.10%</div><div>1</div></div>
          </div>
          <button>展開全部</button>
        </body></html>
        """

        audit = audit_official_source_access(
            source,
            fetcher=lambda url: {
                "http_status": 200,
                "final_url": url,
                "text": html,
            },
        )

        self.assertEqual(audit.parser_status, PARSER_STATUS_PARSED)
        self.assertEqual(audit.raw_dom_stock_row_count, 10)
        self.assertEqual(audit.full_row_count, 10)
        self.assertEqual(audit.dedup_constituent_count, 10)
        self.assertEqual(audit.completeness_status, PARSED_INCOMPLETE)

    def test_final_frozen_universe_requires_all_eight_sources_complete(self):
        complete_audit = OfficialSourceAccessAudit(
            etf_code="0050",
            canonical_url="https://example.test",
            http_status=200,
            final_url="https://example.test",
            tls_verified=True,
            source_access_status=SOURCE_STATUS_AVAILABLE,
            page_title=None,
            constituent_table_available=True,
            holdings_date=date(2026, 8, 7),
            parser_status=PARSER_STATUS_PARSED,
            raw_constituent_count=50,
            completeness_status=PARSED_COMPLETE,
        )
        incomplete_audit = OfficialSourceAccessAudit(
            etf_code="00919",
            canonical_url="https://example.test",
            http_status=200,
            final_url="https://example.test",
            tls_verified=True,
            source_access_status=SOURCE_STATUS_AVAILABLE,
            page_title=None,
            constituent_table_available=True,
            holdings_date=date(2026, 8, 7),
            parser_status=PARSER_STATUS_PARSED,
            raw_constituent_count=10,
            completeness_status=PARSED_INCOMPLETE,
        )

        blocked = audit_etf_universe_finalization((complete_audit,) * 7 + (incomplete_audit,))
        finalized = audit_etf_universe_finalization((complete_audit,) * 8)

        self.assertIsInstance(blocked, ETFUniverseFinalizationAudit)
        self.assertEqual(blocked.universe_status, UNIVERSE_STATUS_NOT_FINALIZED)
        self.assertEqual(blocked.complete_source_count, 7)
        self.assertEqual(blocked.incomplete_source_count, 1)
        self.assertIn("8/8", blocked.blocker)
        self.assertEqual(finalized.universe_status, UNIVERSE_STATUS_FINALIZED)
        self.assertEqual(finalized.complete_source_count, 8)
        self.assertIsNone(finalized.blocker)

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
