#!/usr/bin/env python3
"""Build the explicit Catalyst V1I identity catalog from frozen local inputs only."""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re


CATALOG_VERSION = "CATALYST_V1I_TAIWAN_LISTED_COMPANY_IDENTITY_CATALOG_V1"
_TWSE_SYMBOL = re.compile(r"(?P<code>\d{4})\.TW")
_TPEX_SYMBOL = re.compile(r"(?P<code>\d{4})\.TWO")
_CJK = re.compile(r"[\u4e00-\u9fff]")


class CatalystIdentityCatalogBuildError(ValueError):
    """Raised when frozen build inputs cannot safely produce the V1 catalog."""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--twse-company-names", type=Path, required=True)
    parser.add_argument("--twse-listing", type=Path, required=True)
    parser.add_argument("--tpex-normalized", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-twse-company-names-sha256", required=True)
    parser.add_argument("--expected-twse-listing-sha256", required=True)
    parser.add_argument("--expected-tpex-normalized-sha256", required=True)
    args = parser.parse_args()
    inputs = {
        "twse_company_names": _load_pinned(args.twse_company_names, args.expected_twse_company_names_sha256),
        "twse_listing": _load_pinned(args.twse_listing, args.expected_twse_listing_sha256),
        "tpex_normalized": _load_pinned(args.tpex_normalized, args.expected_tpex_normalized_sha256),
    }
    catalog = build_catalog(
        twse_company_names=inputs["twse_company_names"][0],
        twse_listing=inputs["twse_listing"][0],
        tpex_normalized=inputs["tpex_normalized"][0],
        input_checksums={key: value[1] for key, value in inputs.items()},
        input_paths={
            "twse_company_names": str(args.twse_company_names),
            "twse_listing": str(args.twse_listing),
            "tpex_normalized": str(args.tpex_normalized),
        },
    )
    _write_new(args.output, _serialize(catalog))


def build_catalog(
    *,
    twse_company_names: object,
    twse_listing: object,
    tpex_normalized: object,
    input_checksums: dict[str, str],
    input_paths: dict[str, str],
) -> dict[str, object]:
    twse_names = _twse_names(twse_company_names)
    listing_names = _twse_listing_names(twse_listing)
    tpex_records = _tpex_records(tpex_normalized)
    records = [
        _identity_record(
            symbol=f"{code}.TW",
            canonical_name=listing_names.get(code),
            official_short_name=name,
            market="TWSE",
        )
        for code, name in twse_names.items()
    ]
    records.extend(
        _identity_record(
            symbol=record["symbol"],
            canonical_name=record["official_name_zh"],
            official_short_name=None,
            market="TPEx",
        )
        for record in tpex_records
    )
    records.sort(key=lambda record: record["symbol"])
    _validate_records(records)
    alias_symbols: dict[str, set[str]] = defaultdict(set)
    for record in records:
        for alias in record["approved_aliases"]:
            alias_symbols[alias["value"]].add(record["symbol"])
    catalog: dict[str, object] = {
        "catalog_version": CATALOG_VERSION,
        "effective_version": CATALOG_VERSION,
        "source_provenance": [
            {
                "input_key": "twse_company_names",
                "input_path": input_paths["twse_company_names"],
                "input_role": "BUILD_INPUT_ONLY",
                "source_authority": "Taiwan Stock Exchange OpenAPI listed company basic data",
                "source_url": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
            },
            {
                "input_key": "twse_listing",
                "input_path": input_paths["twse_listing"],
                "input_role": "CANONICAL_NAME_ENRICHMENT_BUILD_INPUT_ONLY",
                "source_authority": "Taiwan Stock Exchange OpenAPI listed company basic data",
                "source_url": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
            },
            {
                "input_key": "tpex_normalized",
                "input_path": input_paths["tpex_normalized"],
                "input_role": "FROZEN_BUILD_INPUT",
                "source_authority": "Taipei Exchange",
                "source_url": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
            },
        ],
        "source_snapshot_checksums": dict(sorted(input_checksums.items())),
        "record_count": len(records),
        "twse_record_count": sum(record["listing_market"] == "TWSE" for record in records),
        "tpex_record_count": sum(record["listing_market"] == "TPEx" for record in records),
        "resolvable_alias_count": sum(len(symbols) == 1 for symbols in alias_symbols.values()),
        "ambiguous_alias_count": sum(len(symbols) > 1 for symbols in alias_symbols.values()),
        "records": records,
    }
    catalog["catalog_checksum"] = catalog_checksum(catalog)
    return catalog


def catalog_checksum(payload: dict[str, object]) -> str:
    return sha256(_serialize({key: value for key, value in payload.items() if key != "catalog_checksum"})).hexdigest()


def _twse_names(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("names"), dict):
        raise CatalystIdentityCatalogBuildError("TWSE company-name input is malformed.")
    result = {}
    for symbol, name in payload["names"].items():
        if not isinstance(symbol, str) or not isinstance(name, str):
            continue
        match = _TWSE_SYMBOL.fullmatch(symbol.strip().upper())
        if match is None:
            continue
        if not name.strip():
            raise CatalystIdentityCatalogBuildError(f"TWSE company-name input has blank name: {symbol}.")
        result[match.group("code")] = name.strip()
    if not result:
        raise CatalystIdentityCatalogBuildError("TWSE company-name input has no four-digit listed common stocks.")
    return dict(sorted(result.items()))


def _twse_listing_names(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise CatalystIdentityCatalogBuildError("TWSE listing input is malformed.")
    result = {}
    for record in payload["records"]:
        if not isinstance(record, dict):
            raise CatalystIdentityCatalogBuildError("TWSE listing input contains a malformed record.")
        code = record.get("stock_code")
        name = record.get("stock_name")
        if not isinstance(code, str) or not re.fullmatch(r"\d{4}", code):
            raise CatalystIdentityCatalogBuildError("TWSE listing input contains a malformed stock code.")
        if not isinstance(name, str) or not name.strip():
            raise CatalystIdentityCatalogBuildError("TWSE listing input contains a blank stock name.")
        if code in result:
            raise CatalystIdentityCatalogBuildError(f"TWSE listing input duplicates stock code: {code}.")
        result[code] = name.strip()
    return result


def _tpex_records(payload: object) -> list[dict[str, str]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise CatalystIdentityCatalogBuildError("TPEx normalized input is malformed.")
    expected_checksum = payload.get("normalized_checksum")
    if not isinstance(expected_checksum, str) or catalog_checksum({
        key: value for key, value in payload.items() if key != "normalized_checksum"
    }) != expected_checksum:
        raise CatalystIdentityCatalogBuildError("TPEx normalized input checksum mismatch.")
    records: list[dict[str, str]] = []
    seen = set()
    for record in payload["records"]:
        if not isinstance(record, dict):
            raise CatalystIdentityCatalogBuildError("TPEx normalized input contains a malformed record.")
        symbol = record.get("symbol")
        name = record.get("official_name_zh")
        if not isinstance(symbol, str) or _TPEX_SYMBOL.fullmatch(symbol) is None:
            raise CatalystIdentityCatalogBuildError("TPEx normalized input contains a malformed symbol.")
        if not isinstance(name, str) or not name.strip():
            raise CatalystIdentityCatalogBuildError("TPEx normalized input contains a blank official name.")
        if record.get("market") != "TPEx" or record.get("security_type") != "COMMON_STOCK":
            raise CatalystIdentityCatalogBuildError("TPEx normalized input is outside common-stock scope.")
        if symbol in seen:
            raise CatalystIdentityCatalogBuildError(f"TPEx normalized input duplicates symbol: {symbol}.")
        seen.add(symbol)
        records.append({"symbol": symbol, "official_name_zh": name.strip()})
    if len(records) != payload.get("record_count"):
        raise CatalystIdentityCatalogBuildError("TPEx normalized record_count does not match records.")
    return sorted(records, key=lambda record: record["symbol"])


def _identity_record(
    *,
    symbol: str,
    canonical_name: str | None,
    official_short_name: str | None,
    market: str,
) -> dict[str, object]:
    aliases = []
    if canonical_name and _is_safe_alias(canonical_name):
        aliases.append({"value": canonical_name, "alias_class": "CANONICAL_NAME"})
    if official_short_name and _is_safe_alias(official_short_name):
        aliases.append({"value": official_short_name, "alias_class": "OFFICIAL_SHORT_NAME"})
    return {
        "symbol": symbol,
        "canonical_name_zh": canonical_name,
        "official_short_name_zh": official_short_name,
        "approved_aliases": sorted(aliases, key=lambda alias: (alias["value"], alias["alias_class"])),
        "listing_market": market,
    }


def _is_safe_alias(value: str) -> bool:
    normalized = value.strip()
    return len(_CJK.findall(normalized)) >= 3 or bool(re.search(r"[A-Za-z0-9]", normalized))


def _validate_records(records: list[dict[str, object]]) -> None:
    symbols = set()
    canonical_names = set()
    for record in records:
        symbol = record["symbol"]
        if symbol in symbols:
            raise CatalystIdentityCatalogBuildError(f"Catalog input duplicates symbol: {symbol}.")
        symbols.add(symbol)
        canonical = record["canonical_name_zh"]
        if canonical:
            if canonical in canonical_names:
                raise CatalystIdentityCatalogBuildError(f"Catalog input duplicates canonical identity: {canonical}.")
            canonical_names.add(canonical)


def _load_pinned(path: Path, expected_checksum: str) -> tuple[object, str]:
    content = path.read_bytes()
    actual_checksum = sha256(content).hexdigest()
    if actual_checksum != expected_checksum:
        raise CatalystIdentityCatalogBuildError(f"Frozen input checksum mismatch: {path}.")
    try:
        return json.loads(content.decode("utf-8-sig")), actual_checksum
    except json.JSONDecodeError as exc:
        raise CatalystIdentityCatalogBuildError(f"Frozen input is not JSON: {path}.") from exc


def _serialize(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_new(path: Path, content: bytes) -> None:
    if path.exists():
        raise CatalystIdentityCatalogBuildError(f"Refusing to overwrite frozen catalog: {path}.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


if __name__ == "__main__":
    main()
