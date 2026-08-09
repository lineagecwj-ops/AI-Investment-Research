from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from types import MappingProxyType


TWSE = "TWSE"
TPEX = "TPEx"

SECURITY_TYPE_COMMON_STOCK = "COMMON_STOCK"
SECURITY_TYPE_ETF = "ETF"
SECURITY_TYPE_ETN = "ETN"
SECURITY_TYPE_PREFERRED = "PREFERRED"
SECURITY_TYPE_DR = "DR"
SECURITY_TYPE_WARRANT = "WARRANT"
SECURITY_TYPE_BOND = "BOND"
SECURITY_TYPE_OTHER = "OTHER"

RESOLUTION_RESOLVED = "RESOLVED"
RESOLUTION_UNRESOLVED = "EXCHANGE_UNRESOLVED"

NAME_MATCH = "NAME_MATCH"
NAME_VARIANT = "NAME_VARIANT"
NAME_CONFLICT = "NAME_CONFLICT"
NAME_NOT_CHECKED = "NAME_NOT_CHECKED"

TWSE_LISTED_COMPANY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TWSE_FUND_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap47_L"
TWSE_WARRANT_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap37_L"
TPEX_LISTED_COMPANY_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
TPEX_WARRANT_URL = "https://www.tpex.org.tw/openapi/v1/tpex_warrant_issue"


@dataclass(frozen=True)
class TaiwanSecurityMasterSourceMetadata:
    source_authority: str
    source_url: str
    retrieved_at: datetime
    source_date: date | None
    record_count: int
    checksum_sha256: str


@dataclass(frozen=True)
class TaiwanSecurityMasterRecord:
    stock_code: str
    stock_name: str
    exchange: str
    security_type: str
    source_authority: str
    source_url: str
    source_date: date | None = None


@dataclass(frozen=True)
class TaiwanSecurityResolution:
    status: str
    record: TaiwanSecurityMasterRecord | None
    name_match_status: str = NAME_NOT_CHECKED
    detail: str | None = None


class TaiwanSecurityMaster:
    def __init__(
        self,
        records: tuple[TaiwanSecurityMasterRecord, ...],
        *,
        metadata: tuple[TaiwanSecurityMasterSourceMetadata, ...] = tuple(),
    ) -> None:
        self.records = tuple(sorted(records, key=lambda record: (record.stock_code, record.exchange)))
        self.metadata = tuple(metadata)
        by_code: dict[str, TaiwanSecurityMasterRecord] = {}
        duplicate_codes: set[str] = set()
        for record in self.records:
            if record.stock_code in by_code and by_code[record.stock_code] != record:
                duplicate_codes.add(record.stock_code)
                continue
            by_code[record.stock_code] = record
        self._by_code = MappingProxyType(by_code)
        self._duplicate_codes = frozenset(duplicate_codes)

    def resolve(self, stock_code: str, stock_name: str | None = None) -> TaiwanSecurityResolution:
        code = normalize_security_code(stock_code)
        if code is None:
            return TaiwanSecurityResolution(
                status=RESOLUTION_UNRESOLVED,
                record=None,
                detail="Security code is not a normalized four-digit Taiwan identifier.",
            )
        if code in self._duplicate_codes:
            return TaiwanSecurityResolution(
                status=RESOLUTION_UNRESOLVED,
                record=None,
                detail="Security code is duplicated across official master records.",
            )
        record = self._by_code.get(code)
        if record is None:
            return TaiwanSecurityResolution(
                status=RESOLUTION_UNRESOLVED,
                record=None,
                detail="Security code not found in official Taiwan security master.",
            )
        return TaiwanSecurityResolution(
            status=RESOLUTION_RESOLVED,
            record=record,
            name_match_status=name_match_status(stock_name, record.stock_name),
        )

    @property
    def common_stock_count(self) -> int:
        return sum(1 for record in self.records if record.security_type == SECURITY_TYPE_COMMON_STOCK)

    @property
    def twse_common_stock_count(self) -> int:
        return sum(
            1
            for record in self.records
            if record.exchange == TWSE and record.security_type == SECURITY_TYPE_COMMON_STOCK
        )

    @property
    def tpex_common_stock_count(self) -> int:
        return sum(
            1
            for record in self.records
            if record.exchange == TPEX and record.security_type == SECURITY_TYPE_COMMON_STOCK
        )


def build_official_taiwan_security_master(
    *,
    retrieved_at: datetime | None = None,
    fetch_json=None,
) -> TaiwanSecurityMaster:
    retrieved_at = retrieved_at or datetime.now(UTC)
    fetcher = fetch_json or _fetch_official_json
    sources = (
        ("TWSE", TWSE_LISTED_COMPANY_URL, TWSE, SECURITY_TYPE_COMMON_STOCK),
        ("TWSE", TWSE_FUND_URL, TWSE, SECURITY_TYPE_ETF),
        ("TWSE", TWSE_WARRANT_URL, TWSE, SECURITY_TYPE_WARRANT),
        ("TPEx", TPEX_LISTED_COMPANY_URL, TPEX, SECURITY_TYPE_COMMON_STOCK),
        ("TPEx", TPEX_WARRANT_URL, TPEX, SECURITY_TYPE_WARRANT),
    )
    records: list[TaiwanSecurityMasterRecord] = []
    metadata: list[TaiwanSecurityMasterSourceMetadata] = []
    for authority, url, exchange, security_type in sources:
        payload = fetcher(url)
        parsed = parse_official_security_master_payload(
            payload,
            source_authority=authority,
            source_url=url,
            exchange=exchange,
            security_type=security_type,
        )
        records.extend(parsed)
        metadata.append(
            TaiwanSecurityMasterSourceMetadata(
                source_authority=authority,
                source_url=url,
                retrieved_at=retrieved_at,
                source_date=_source_date_from_rows(payload),
                record_count=len(parsed),
                checksum_sha256=_payload_checksum(payload),
            )
        )
    return TaiwanSecurityMaster(tuple(records), metadata=tuple(metadata))


def parse_official_security_master_payload(
    payload: str | list[dict[str, object]],
    *,
    source_authority: str,
    source_url: str,
    exchange: str,
    security_type: str,
) -> tuple[TaiwanSecurityMasterRecord, ...]:
    rows = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(rows, list):
        raise ValueError("Official security master payload must be a JSON list.")
    records = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        stock_code = _first_text(row, ("公司代號", "基金代號", "權證代號", "SecuritiesCompanyCode", "SecurityCode"))
        code = normalize_security_code(stock_code)
        if code is None:
            continue
        stock_name = _first_text(
            row,
            (
                "公司簡稱",
                "公司名稱",
                "基金簡稱",
                "權證簡稱",
                "CompanyAbbreviation",
                "CompanyName",
                "SecurityName",
            ),
        )
        records.append(
            TaiwanSecurityMasterRecord(
                stock_code=code,
                stock_name=stock_name.strip(),
                exchange=exchange,
                security_type=security_type,
                source_authority=source_authority,
                source_url=source_url,
                source_date=_row_source_date(row),
            )
        )
    return tuple(records)


def normalize_security_code(value: object) -> str | None:
    text = str(value or "").strip().upper()
    match = re.search(r"\b(\d{4})\b", text)
    return match.group(1) if match else None


def name_match_status(raw_name: str | None, official_name: str | None) -> str:
    if raw_name is None or not raw_name.strip() or official_name is None or not official_name.strip():
        return NAME_NOT_CHECKED
    raw = _normalized_name(raw_name)
    official = _normalized_name(official_name)
    if raw == official:
        return NAME_MATCH
    if raw in official or official in raw:
        return NAME_VARIANT
    return NAME_CONFLICT


def _fetch_official_json(url: str) -> list[dict[str, object]]:
    if "tpex.org.tw" in url:
        return _fetch_official_json_with_verified_curl(url)

    import requests

    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
        verify=True,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.json()


def _fetch_official_json_with_verified_curl(url: str) -> list[dict[str, object]]:
    command = [
        "curl",
        "-L",
        "--fail",
        "--silent",
        "--show-error",
        url,
    ]
    if any(arg in {"-k", "--insecure"} for arg in command):
        raise ValueError("Official security master curl transport must not disable TLS verification.")
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)


def _first_text(row: dict[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def _source_date_from_rows(rows: object) -> date | None:
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict):
            parsed = _row_source_date(row)
            if parsed is not None:
                return parsed
    return None


def _row_source_date(row: dict[str, object]) -> date | None:
    for key in ("出表日期", "Date"):
        parsed = _roc_date(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _roc_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{7}", text):
        return None
    return date(int(text[:3]) + 1911, int(text[3:5]), int(text[5:7]))


def _payload_checksum(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_name(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()
