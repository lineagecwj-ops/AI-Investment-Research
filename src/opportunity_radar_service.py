"""Current official monthly-revenue snapshots for descriptive research screening."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from database_config import PROJECT_ROOT

TWSE_MONTHLY_REVENUE_FORWARD_SNAPSHOT_V0 = "TWSE_MONTHLY_REVENUE_FORWARD_SNAPSHOT_V0"
TWSE_MONTHLY_REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
SNAPSHOT_DIRECTORY = PROJECT_ROOT / "data" / "research" / "opportunity_radar"


class OpportunityRadarRevenueError(Exception):
    pass


@dataclass(frozen=True)
class MonthlyRevenueRecord:
    symbol: str
    company_name: str | None
    reported_year_month: str
    current_month_revenue: int | None
    previous_month_revenue: int | None
    same_month_prior_year_revenue: int | None
    revenue_yoy: float | None
    revenue_mom: float | None


def request_official_monthly_revenue(url: str = TWSE_MONTHLY_REVENUE_URL) -> list[dict]:
    try:
        with urlopen(url, timeout=15) as response:
            payload = response.read().decode("utf-8-sig")
        records = json.loads(payload)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise OpportunityRadarRevenueError(str(error)) from error
    if not isinstance(records, list):
        raise OpportunityRadarRevenueError("官方月營收回應格式不正確。")
    return records


def normalize_monthly_revenue_records(records: list[dict], universe_symbols: set[str]) -> tuple[MonthlyRevenueRecord, ...]:
    normalized = []
    for raw in records:
        if not isinstance(raw, dict):
            continue
        code = _text(raw, "公司代號", "公司代碼", "SecuritiesCompanyCode")
        symbol = f"{code}.TW" if code and code.isdigit() else None
        if symbol not in universe_symbols:
            continue
        current = _number(raw, "當月營收", "營業收入-當月營收")
        previous = _number(raw, "上月營收", "營業收入-上月營收")
        prior = _number(raw, "去年當月營收", "營業收入-去年當月營收")
        official_yoy = _number(raw, "去年同月增減(%)", "營業收入-去年同月增減(%)")
        normalized.append(MonthlyRevenueRecord(
            symbol=symbol,
            company_name=_text(raw, "公司名稱", "公司簡稱"),
            reported_year_month=_reported_month(raw),
            current_month_revenue=current,
            previous_month_revenue=previous,
            same_month_prior_year_revenue=prior,
            revenue_yoy=(official_yoy / 100 if official_yoy is not None else _change(current, prior)),
            revenue_mom=_change(current, previous),
        ))
    return tuple(sorted(normalized, key=lambda record: record.symbol))


def persist_monthly_revenue_snapshot(records: tuple[MonthlyRevenueRecord, ...], raw_records: list[dict], *, now=None) -> Path:
    retrieved_at = (now or datetime.now(ZoneInfo("Asia/Taipei"))).isoformat()
    raw_payload = json.dumps(raw_records, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    payload_sha256 = hashlib.sha256(raw_payload.encode()).hexdigest()
    identity = f"{TWSE_MONTHLY_REVENUE_FORWARD_SNAPSHOT_V0}|{payload_sha256}"
    path = SNAPSHOT_DIRECTORY / f"monthly_revenue_{hashlib.sha256(identity.encode()).hexdigest()[:20]}.json"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"snapshot_version": TWSE_MONTHLY_REVENUE_FORWARD_SNAPSHOT_V0, "retrieved_at": retrieved_at, "source_url": TWSE_MONTHLY_REVENUE_URL, "payload_sha256": payload_sha256, "records": [asdict(record) for record in records]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_latest_monthly_revenue_snapshot() -> tuple[dict, tuple[MonthlyRevenueRecord, ...]] | None:
    paths = sorted(SNAPSHOT_DIRECTORY.glob("monthly_revenue_*.json")) if SNAPSHOT_DIRECTORY.exists() else []
    if not paths:
        return None
    try:
        payload = json.loads(paths[-1].read_text(encoding="utf-8"))
        return payload, tuple(MonthlyRevenueRecord(**record) for record in payload["records"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def find_latest_monthly_revenue_record(
    symbol: str,
    *,
    snapshot_loader=load_latest_monthly_revenue_snapshot,
) -> tuple[dict, MonthlyRevenueRecord] | None:
    """Resolve one symbol from the canonical local monthly-revenue snapshot."""
    loaded = snapshot_loader()
    if loaded is None:
        return None
    payload, records = loaded
    return next(
        ((payload, record) for record in records if record.symbol == symbol),
        None,
    )


def _text(record, *keys):
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip(): return value.strip()
    return None

def _number(record, *keys):
    value = _text(record, *keys)
    if value is None: return None
    try: return int(value.replace(",", ""))
    except ValueError: return None

def _change(current, base):
    return current / base - 1 if current is not None and base not in (None, 0) else None

def _reported_month(record):
    combined = _text(record, "資料年月")
    if combined:
        digits = "".join(character for character in combined if character.isdigit())
        if len(digits) in (5, 6):
            return _format_reported_month(digits[:-2], digits[-2:])
    return _format_reported_month(
        _text(record, "資料年", "年度"),
        _text(record, "資料月份", "月份"),
    )


def _format_reported_month(year, month):
    if not year or not month or not str(year).isdigit() or not str(month).isdigit():
        return "N/A"
    numeric_year = int(year)
    numeric_month = int(month)
    if numeric_year <= 1911:
        numeric_year += 1911
    if numeric_month < 1 or numeric_month > 12:
        return "N/A"
    return f"{numeric_year:04d}-{numeric_month:02d}"
