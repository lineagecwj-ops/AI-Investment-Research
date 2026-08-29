import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from twse_institutional_flow_materialization import CONSERVATIVE_NEXT_SESSION_PROXY
from twse_institutional_flow_materialization import T86_FIELDS_V1
from twse_institutional_flow_materialization import TWSEInstitutionalFlowMaterializationError
from twse_institutional_flow_materialization import TWSEInstitutionalFlowMaterializer
from twse_institutional_flow_materialization import TWSE_T86_AVAILABILITY_V1


class _FixtureStore:
    def __init__(self, db_path, calendar, symbols):
        self.resolved_db_path = db_path
        self._calendar = calendar
        self._symbols = symbols

    def load_historical_price_series(self, symbol):
        if symbol != "0050.TW":
            raise AssertionError(symbol)
        return HistoricalPriceSeries(
            symbol=symbol,
            currency="TWD",
            bars=tuple(
                HistoricalPriceBar(
                    symbol=symbol,
                    trading_date=day,
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    adjusted_close=None,
                    volume=1,
                )
                for day in self._calendar
            ),
            fetched_at=datetime(2026, 8, 29, tzinfo=UTC),
        )

    def materialized_twse_common_stock_symbols(self):
        return self._symbols


class TWSEInstitutionalFlowMaterializationTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "prices.sqlite"
        self.flow_path = self.root / "flows.sqlite"
        self.manifest_path = self.root / "manifest.json"
        self.symbols = tuple(f"{1101 + index:04d}.TW" for index in range(217)) + ("2330.TW",)
        self.calendar = (date(2018, 1, 2), date(2018, 1, 3), date(2024, 12, 31), date(2025, 1, 2))
        connection = sqlite3.connect(self.db_path)
        connection.execute("CREATE TABLE historical_prices (symbol TEXT, trading_date TEXT, PRIMARY KEY (symbol, trading_date))")
        for day in self.calendar[:3]:
            connection.execute("INSERT INTO historical_prices VALUES (?, ?)", ("2330.TW", day.isoformat()))
        connection.commit()
        connection.close()
        self.store = _FixtureStore(self.db_path, self.calendar, self.symbols)
        self.requests = []

    def payload(self, rows=None, *, fields=T86_FIELDS_V1, stat="OK"):
        return json.dumps({"stat": stat, "fields": list(fields), "data": rows if rows is not None else [self.row()]}).encode()

    def row(self, code="2330", *, foreign_buy="10", foreign_sell="4", trust_buy="3", trust_sell="1", proprietary_buy="2", proprietary_sell="1", hedge_buy="5", hedge_sell="3"):
        foreign_net = str(int(foreign_buy) - int(foreign_sell))
        trust_net = str(int(trust_buy) - int(trust_sell))
        prop_net = str(int(proprietary_buy) - int(proprietary_sell))
        hedge_net = str(int(hedge_buy) - int(hedge_sell))
        dealer_total = str(int(prop_net) + int(hedge_net))
        total = str(int(foreign_net) + int(trust_net) + int(dealer_total))
        return [code, "fixture", foreign_buy, foreign_sell, foreign_net, "0", "0", "0", trust_buy, trust_sell, trust_net, dealer_total, proprietary_buy, proprietary_sell, prop_net, hedge_buy, hedge_sell, hedge_net, total]

    def fetcher(self, payload=None):
        response = payload or self.payload()
        def fetch(url):
            self.requests.append(url)
            return response
        return fetch

    def materialize(self, **kwargs):
        return TWSEInstitutionalFlowMaterializer(fetch_payload=self.fetcher(kwargs.pop("payload", None)), sleep=lambda _seconds: None).materialize(
            research_store=self.store,
            output_database_path=self.flow_path,
            output_manifest_path=self.manifest_path,
            retrieval_timestamp=datetime(2026, 8, 29, tzinfo=UTC),
            request_pause_seconds=0,
            **kwargs,
        )

    def read(self, query):
        connection = sqlite3.connect(self.flow_path)
        try:
            return connection.execute(query).fetchall()
        finally:
            connection.close()

    def test_normalizes_official_fields_and_preserves_all_category_nets(self):
        result = self.materialize()
        row = self.read("SELECT foreign_ex_dealer_net, trust_net, dealer_total_net, total_institutional_net FROM normalized_flows")[0]
        self.assertEqual(row, (6, 2, 3, 11))
        self.assertEqual(result.normalized_rows, 3)

    def test_buy_sell_and_total_invariants_fail_closed(self):
        bad = self.row()
        bad[4] = "5"
        with self.assertRaisesRegex(TWSEInstitutionalFlowMaterializationError, "foreign_ex_dealer_net"):
            self.materialize(payload=self.payload([bad]))

    def test_filters_non_universe_products_without_creating_candidate_record(self):
        self.materialize(payload=self.payload([self.row("2330"), self.row("0050")]))
        self.assertEqual(self.read("SELECT DISTINCT symbol FROM normalized_flows"), [("2330.TW",)])

    def test_absent_universe_symbol_is_coverage_not_zero_flow(self):
        self.materialize()
        rows = self.read("SELECT source_coverage_status FROM daily_symbol_coverage WHERE symbol = '1101.TW'")
        self.assertEqual(rows, [("NOT_IN_SOURCE_RESPONSE",)] * 3)
        self.assertEqual(self.read("SELECT COUNT(*) FROM normalized_flows WHERE symbol = '1101.TW'")[0][0], 0)

    def test_uses_next_session_availability_proxy(self):
        self.materialize()
        rows = self.read("SELECT trade_date, available_date, availability_semantics FROM normalized_flows ORDER BY trade_date")
        self.assertEqual(rows[-1], ("2024-12-31", "2025-01-02", TWSE_T86_AVAILABILITY_V1))
        manifest = json.loads(self.manifest_path.read_text())
        self.assertEqual(manifest["availability"]["quality"], CONSERVATIVE_NEXT_SESSION_PROXY)

    def test_raw_payload_hash_and_normalized_checksum_are_persisted(self):
        result = self.materialize()
        self.assertEqual(len(self.read("SELECT payload_sha256 FROM source_payloads")[0][0]), 64)
        manifest = json.loads(self.manifest_path.read_text())
        self.assertEqual(manifest["payload_lineage"]["normalized_data_sha256"], result.normalized_data_sha256)

    def test_schema_mismatch_fails_closed(self):
        with self.assertRaisesRegex(TWSEInstitutionalFlowMaterializationError, "SCHEMA_VERSION_REVIEW_REQUIRED"):
            self.materialize(payload=self.payload(fields=T86_FIELDS_V1[:-1]))

    def test_resuming_existing_successes_does_not_redownload_or_duplicate_rows(self):
        first = self.materialize()
        first_requests = len(self.requests)
        second = self.materialize()
        self.assertEqual(first.requested_dates, second.requested_dates)
        self.assertEqual(len(self.requests), first_requests)
        self.assertEqual(self.read("SELECT COUNT(*) FROM normalized_flows")[0][0], 3)

    def test_no_2025_t86_request_is_made(self):
        self.materialize()
        queried_dates = {parse_qs(urlparse(url).query)["date"][0] for url in self.requests}
        self.assertTrue(all(value <= "20241231" for value in queried_dates))
        self.assertNotIn("20250102", queried_dates)

    def test_exact_price_date_coverage_never_uses_nearest_date(self):
        self.materialize()
        manifest = json.loads(self.manifest_path.read_text())
        self.assertEqual(manifest["exact_price_date_coverage"], {"matches": 3, "missing_pairs": 0})

    def test_explicit_audited_no_data_does_not_create_flow_rows(self):
        result = self.materialize(payload=self.payload([], fields=(), stat="NOT_FOUND"))
        self.assertEqual(result.normalized_rows, 0)
        self.assertEqual(result.audited_no_data_dates, 3)
        self.assertEqual(self.read("SELECT COUNT(*) FROM daily_symbol_coverage WHERE source_coverage_status = 'EXPLICITLY_AUDITED_NO_DATA'")[0][0], 654)

    def test_output_cannot_target_production(self):
        with self.assertRaisesRegex(TWSEInstitutionalFlowMaterializationError, "data/production"):
            TWSEInstitutionalFlowMaterializer(fetch_payload=self.fetcher(), sleep=lambda _seconds: None).materialize(
                research_store=self.store,
                output_database_path=PROJECT_ROOT / "data" / "production" / "forbidden.sqlite",
                output_manifest_path=self.manifest_path,
                request_pause_seconds=0,
            )


if __name__ == "__main__":
    unittest.main()
