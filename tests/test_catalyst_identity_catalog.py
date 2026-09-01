import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCRIPTS_PATH = PROJECT_ROOT / "scripts"
for path in (SRC_PATH, SCRIPTS_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_catalyst_identity_catalog_v1 import build_catalog
from build_catalyst_identity_catalog_v1 import catalog_checksum as builder_catalog_checksum
from catalyst_identity_catalog import CATALYST_IDENTITY_CATALOG_VERSION
from catalyst_identity_catalog import CatalystIdentityCatalogError
from catalyst_identity_catalog import DEFAULT_CATALOG_CHECKSUM
from catalyst_identity_catalog import DEFAULT_CATALOG_PATH
from catalyst_identity_catalog import catalog_checksum
from catalyst_identity_catalog import load_identity_catalog


class CatalystIdentityCatalogTestCase(unittest.TestCase):
    def test_released_catalog_resolves_unique_alias_without_weak_or_brand_aliases(self):
        catalog = load_identity_catalog(
            DEFAULT_CATALOG_PATH,
            CATALYST_IDENTITY_CATALOG_VERSION,
            DEFAULT_CATALOG_CHECKSUM,
        )
        self.assertEqual(catalog.resolve_exact_alias("統一超").symbol, "2912.TW")
        self.assertIsNone(catalog.resolve_exact_alias("統一"))
        for brand in ("7-ELEVEN", "OPENPOINT", "foodomo"):
            self.assertIsNone(catalog.resolve_exact_alias(brand))

    def test_context_bounded_alias_detection_rejects_partial_and_unapproved_prose(self):
        catalog = load_identity_catalog(
            DEFAULT_CATALOG_PATH,
            CATALYST_IDENTITY_CATALOG_VERSION,
            DEFAULT_CATALOG_CHECKSUM,
        )
        self.assertEqual(
            tuple(item.symbol for item in catalog.find_explicit_non_target_identities("統一超表示營運展望", "1216.TW")),
            ("2912.TW",),
        )
        self.assertEqual(
            tuple(item.symbol for item in catalog.find_explicit_non_target_identities("公司名稱：統一超；", "1216.TW")),
            ("2912.TW",),
        )
        for text in ("非統一超表示", "統一超聲明", "7-ELEVEN表示", "OPENPOINT表示", "foodomo表示"):
            self.assertEqual(catalog.find_explicit_non_target_identities(text, "1216.TW"), ())

    def test_loader_fails_closed_for_missing_version_checksum_and_malformed_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            with self.assertRaisesRegex(CatalystIdentityCatalogError, "missing"):
                load_identity_catalog(path, CATALYST_IDENTITY_CATALOG_VERSION, "0" * 64)

            cases = {
                "wrong-version": {"catalog_version": "WRONG"},
                "duplicate-symbol": {"records": [_record("1000.TW", "甲公司", "TWSE"), _record("1000.TW", "乙公司", "TWSE")]},
                "duplicate-canonical": {"records": [_record("1000.TW", "同名公司", "TWSE"), _record("2000.TWO", "同名公司", "TPEx")]},
                "malformed-symbol": {"records": [_record("100.TW", "甲公司", "TWSE")]},
                "unsupported-market": {"records": [_record("1000.TW", "甲公司", "OTHER")]},
                "blank-alias": {"records": [_record("1000.TW", "甲公司", "TWSE", alias="")]},
            }
            for mutation in cases.values():
                payload = _payload(**mutation)
                _write_catalog(path, payload)
                with self.assertRaises(CatalystIdentityCatalogError):
                    load_identity_catalog(path, CATALYST_IDENTITY_CATALOG_VERSION, payload["catalog_checksum"])
            payload = _payload()
            payload["catalog_checksum"] = "0" * 64
            _write_catalog(path, payload)
            with self.assertRaisesRegex(CatalystIdentityCatalogError, "checksum mismatch"):
                load_identity_catalog(path, CATALYST_IDENTITY_CATALOG_VERSION, payload["catalog_checksum"])

    def test_ambiguous_alias_is_explicit_and_never_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            payload = _payload(records=[
                _record("1000.TW", "甲公司", "TWSE", alias="共用別名"),
                _record("2000.TWO", "乙公司", "TPEx", alias="共用別名"),
            ])
            _write_catalog(path, payload)
            catalog = load_identity_catalog(path, CATALYST_IDENTITY_CATALOG_VERSION, payload["catalog_checksum"])
            self.assertIsNone(catalog.resolve_exact_alias("共用別名"))
            self.assertTrue(catalog.is_ambiguous_alias("共用別名"))
            self.assertEqual(catalog.find_explicit_non_target_identities("共用別名表示", "1000.TW"), ())

    def test_builder_is_deterministic_and_excludes_weak_two_character_aliases(self):
        twse_names = {"names": {"1216.TW": "統一", "2912.TW": "統一超"}}
        twse_listing = {"records": [
            {"stock_code": "1216", "stock_name": "統一企業股份有限公司"},
            {"stock_code": "2912", "stock_name": "統一超商股份有限公司"},
        ]}
        tpex_base = {
            "record_count": 1,
            "records": [{
                "symbol": "6488.TWO",
                "official_name_zh": "環球晶圓股份有限公司",
                "market": "TPEx",
                "security_type": "COMMON_STOCK",
            }],
        }
        tpex_normalized = {**tpex_base, "normalized_checksum": builder_catalog_checksum(tpex_base)}
        arguments = {
            "twse_company_names": twse_names,
            "twse_listing": twse_listing,
            "tpex_normalized": tpex_normalized,
            "input_checksums": {"twse_company_names": "a" * 64, "twse_listing": "b" * 64, "tpex_normalized": "c" * 64},
            "input_paths": {"twse_company_names": "twse.json", "twse_listing": "listing.json", "tpex_normalized": "tpex.json"},
        }
        first = build_catalog(**arguments)
        second = build_catalog(**arguments)
        self.assertEqual(json.dumps(first, ensure_ascii=False, sort_keys=True), json.dumps(second, ensure_ascii=False, sort_keys=True))
        records = {record["symbol"]: record for record in first["records"]}
        self.assertEqual(records["1216.TW"]["approved_aliases"], [{"value": "統一企業股份有限公司", "alias_class": "CANONICAL_NAME"}])
        self.assertTrue(any(alias["value"] == "統一超" for alias in records["2912.TW"]["approved_aliases"]))


def _record(symbol, canonical, market, *, alias=None):
    aliases = [{"value": alias if alias is not None else canonical, "alias_class": "CANONICAL_NAME"}]
    return {
        "symbol": symbol,
        "canonical_name_zh": canonical,
        "official_short_name_zh": None,
        "approved_aliases": aliases,
        "listing_market": market,
    }


def _payload(*, records=None, catalog_version=CATALYST_IDENTITY_CATALOG_VERSION, effective_version=CATALYST_IDENTITY_CATALOG_VERSION):
    records = records or [_record("1000.TW", "甲公司", "TWSE")]
    aliases = {}
    for record in records:
        for alias in record["approved_aliases"]:
            aliases.setdefault(alias["value"], set()).add(record["symbol"])
    payload = {
        "catalog_version": catalog_version,
        "effective_version": effective_version,
        "source_provenance": [{"input_key": "fixture"}],
        "source_snapshot_checksums": {"fixture": "a" * 64},
        "record_count": len(records),
        "twse_record_count": sum(record["listing_market"] == "TWSE" for record in records),
        "tpex_record_count": sum(record["listing_market"] == "TPEx" for record in records),
        "resolvable_alias_count": sum(len(symbols) == 1 for symbols in aliases.values()),
        "ambiguous_alias_count": sum(len(symbols) > 1 for symbols in aliases.values()),
        "records": records,
    }
    payload["catalog_checksum"] = catalog_checksum(payload)
    return payload


def _write_catalog(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
