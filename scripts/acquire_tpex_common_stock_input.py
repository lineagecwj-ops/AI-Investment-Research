#!/usr/bin/env python3
"""Normalize a frozen official TPEx listed-company response without network access."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


SOURCE_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
MARKET = "TPEx"
SECURITY_TYPE = "COMMON_STOCK"
FORMAT_VERSION = "TPEX_LISTED_COMMON_STOCKS_2026_09_01_V1"
CODE_PATTERN = re.compile(r"\d{4}")


class TPExCommonStockInputError(ValueError):
    """Raised when a frozen TPEx input cannot be normalized safely."""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--normalized", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--retrieved-at", required=True)
    args = parser.parse_args()

    raw_bytes = args.raw.read_bytes()
    payload = json.loads(raw_bytes.decode("utf-8-sig"))
    normalized = normalize_payload(payload, raw_checksum=_sha256(raw_bytes))
    normalized_checksum = _sha256(_serialize(normalized))
    normalized["normalized_checksum"] = normalized_checksum
    output_bytes = _serialize(normalized)
    report = build_acquisition_report(
        payload,
        raw_path=args.raw,
        raw_checksum=_sha256(raw_bytes),
        normalized_path=args.normalized,
        normalized_file_checksum=_sha256(output_bytes),
        normalized_content_checksum=normalized_checksum,
        retrieved_at=args.retrieved_at,
    )
    _write_new_file(args.normalized, output_bytes)
    _write_new_file(args.report, _serialize(report))


def normalize_payload(payload: object, *, raw_checksum: str) -> dict[str, object]:
    if not isinstance(payload, list):
        raise TPExCommonStockInputError("TPEx raw snapshot must be a JSON list.")

    records: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    source_dates: set[str] = set()
    for row in payload:
        if not isinstance(row, dict):
            raise TPExCommonStockInputError("TPEx raw snapshot contains a non-object record.")
        code = _required_text(row, "SecuritiesCompanyCode")
        if not CODE_PATTERN.fullmatch(code):
            raise TPExCommonStockInputError(f"TPEx security code is not four digits: {code!r}.")
        if code in seen_codes:
            raise TPExCommonStockInputError(f"Duplicate TPEx security code: {code}.")
        seen_codes.add(code)
        name = _required_text(row, "CompanyName")
        common_stock_par_value = _required_text(row, "ParValueOfCommonStock")
        if _is_zero_common_stock_par_value(common_stock_par_value):
            raise TPExCommonStockInputError(f"TPEx record lacks a common-stock par value: {code}.")
        source_dates.add(_required_text(row, "Date"))
        records.append(
            {
                "symbol": f"{code}.TWO",
                "official_code": code,
                "official_name_zh": name,
                "market": MARKET,
                "security_type": SECURITY_TYPE,
                "classification_basis": "TPEx listed-company basic-data record with official common-stock par value.",
            }
        )

    if len(source_dates) != 1:
        raise TPExCommonStockInputError("TPEx raw snapshot has inconsistent official report dates.")
    records.sort(key=lambda record: record["official_code"])
    result: dict[str, object] = {
        "format_version": FORMAT_VERSION,
        "source_provenance": {
            "source_authority": "Taipei Exchange",
            "source_url": SOURCE_URL,
            "official_report_date_raw": next(iter(source_dates)),
            "raw_checksum": raw_checksum,
        },
        "normalization_policy": {
            "market": MARKET,
            "security_type": SECURITY_TYPE,
            "required_fields": ["SecuritiesCompanyCode", "CompanyName", "ParValueOfCommonStock", "Date"],
            "symbol_suffix": ".TWO",
            "excluded_instrument_policy": "Only official listed-company records with a four-digit code and non-zero common-stock par value are included.",
        },
        "record_count": len(records),
        "records": records,
    }
    return result


def build_acquisition_report(
    payload: object,
    *,
    raw_path: Path,
    raw_checksum: str,
    normalized_path: Path,
    normalized_file_checksum: str,
    normalized_content_checksum: str,
    retrieved_at: str,
) -> dict[str, object]:
    if not isinstance(payload, list):
        raise TPExCommonStockInputError("TPEx raw snapshot must be a JSON list.")
    excluded_counts = Counter()
    for row in payload:
        if not isinstance(row, dict):
            excluded_counts["malformed_record"] += 1
            continue
        code = str(row.get("SecuritiesCompanyCode") or "").strip()
        name = str(row.get("CompanyName") or "").strip()
        par_value = str(row.get("ParValueOfCommonStock") or "").strip()
        if not CODE_PATTERN.fullmatch(code):
            excluded_counts["invalid_security_code"] += 1
        elif not name:
            excluded_counts["blank_company_name"] += 1
        elif not par_value or _is_zero_common_stock_par_value(par_value):
            excluded_counts["missing_common_stock_par_value"] += 1
    return {
        "format_version": FORMAT_VERSION,
        "official_source_url": SOURCE_URL,
        "retrieved_at": retrieved_at,
        "http_result_status": 200,
        "raw_snapshot_path": str(raw_path),
        "raw_sha256": raw_checksum,
        "normalized_snapshot_path": str(normalized_path),
        "normalized_sha256": normalized_file_checksum,
        "normalized_content_checksum": normalized_content_checksum,
        "raw_record_count": len(payload),
        "normalized_common_stock_count": len(payload) - sum(excluded_counts.values()),
        "excluded_record_counts": dict(sorted(excluded_counts.items())),
        "classification_scope": "Official TPEx listed-company basic-data records with non-zero common-stock par value.",
    }


def _required_text(row: dict[str, object], field: str) -> str:
    value = str(row.get(field) or "").strip()
    if not value:
        raise TPExCommonStockInputError(f"TPEx record has blank required field: {field}.")
    return value


def _is_zero_common_stock_par_value(value: str) -> bool:
    normalized = re.sub(r"[^0-9.]", "", value)
    try:
        return not normalized or float(normalized) == 0.0
    except ValueError:
        return True


def _serialize(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_new_file(path: Path, content: bytes) -> None:
    if path.exists():
        raise TPExCommonStockInputError(f"Refusing to overwrite frozen input: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


if __name__ == "__main__":
    main()
