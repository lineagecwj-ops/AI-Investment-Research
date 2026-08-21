from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping


TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SCHEMA_V1 = "TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_V1"
TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SCOPE_V1 = "POST_HOLDOUT_DIAGNOSTIC_SUPPORT"
TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SOURCE_AUTHORITY_V1 = "TWSE"
TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SOURCE_URL_V1 = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_ID_V1 = "frozen_twse_research_universe_2026_08_09"
TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_SIZE_V1 = 218
TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_RESEARCH_DIR = Path("data/research/post_holdout_ai_regime_diagnostic")
TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_ARTIFACT_FILENAME_V1 = (
    "technical_risk_official_broad_industry_mapping_218_twse_v1.json"
)
TECH_RISK_CURRENT_OFFICIAL_INDUSTRY_CLASSIFICATION_V1 = "CURRENT_OFFICIAL_INDUSTRY_CLASSIFICATION"
TECH_RISK_PRE_2024_HISTORICAL_INDUSTRY_CLASSIFICATION_V1 = "PRE_2024_HISTORICAL_INDUSTRY_CLASSIFICATION"
TECH_RISK_TECHNOLOGY_REVIEW_CANDIDATE_WORKLOAD_PREVIEW_V1 = (
    "TECHNOLOGY_REVIEW_CANDIDATE_WORKLOAD_PREVIEW_ONLY"
)

TECH_RISK_TECHNOLOGY_RELATED_INDUSTRY_CODES_V1 = frozenset(
    {
        "24",
        "25",
        "26",
        "27",
        "28",
        "29",
        "30",
        "31",
        "36",
    }
)

TWSE_INDUSTRY_CODE_NAMES_V1 = MappingProxyType(
    {
        "01": "水泥工業",
        "02": "食品工業",
        "03": "塑膠工業",
        "04": "紡織纖維",
        "05": "電機機械",
        "06": "電器電纜",
        "08": "玻璃陶瓷",
        "09": "造紙工業",
        "10": "鋼鐵工業",
        "11": "橡膠工業",
        "12": "汽車工業",
        "14": "建材營造",
        "15": "航運業",
        "16": "觀光餐旅",
        "17": "金融保險",
        "18": "貿易百貨",
        "19": "綜合",
        "20": "其他業",
        "21": "化學工業",
        "22": "生技醫療業",
        "23": "油電燃氣業",
        "24": "半導體業",
        "25": "電腦及週邊設備業",
        "26": "光電業",
        "27": "通信網路業",
        "28": "電子零組件業",
        "29": "電子通路業",
        "30": "資訊服務業",
        "31": "其他電子業",
        "32": "文化創意業",
        "33": "農業科技業",
        "34": "電子商務",
        "35": "綠能環保",
        "36": "數位雲端",
        "37": "運動休閒",
        "38": "居家生活",
    }
)


class TechnicalRiskOfficialBroadIndustryMappingError(Exception):
    """Raised when official broad industry mapping fails closed."""


class TechnicalRiskBroadIndustryMappingStatus(StrEnum):
    MAPPED = "MAPPED"
    UNKNOWN = "UNKNOWN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class TechnicalRiskOfficialBroadIndustryRecord:
    symbol: str
    company_name: str
    broad_industry: str
    broad_industry_code: str | None
    industry_source: str
    industry_source_version: str
    classification_as_of_date: date
    mapping_status: TechnicalRiskBroadIndustryMappingStatus | str
    source_record_checksum: str | None = None

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        _require_text(self.industry_source, "industry_source")
        _require_text(self.industry_source_version, "industry_source_version")
        object.__setattr__(
            self,
            "mapping_status",
            TechnicalRiskBroadIndustryMappingStatus(self.mapping_status),
        )
        if self.mapping_status == TechnicalRiskBroadIndustryMappingStatus.MAPPED:
            _require_text(self.company_name, "company_name")
            _require_text(self.broad_industry, "broad_industry")
            _require_text(self.broad_industry_code, "broad_industry_code")
            _require_text(self.source_record_checksum, "source_record_checksum")
        if self.mapping_status != TechnicalRiskBroadIndustryMappingStatus.MAPPED and self.source_record_checksum is not None:
            _require_text(self.source_record_checksum, "source_record_checksum")

    @property
    def is_technology_related_industry(self) -> bool:
        return self.broad_industry_code in TECH_RISK_TECHNOLOGY_RELATED_INDUSTRY_CODES_V1


@dataclass(frozen=True)
class TechnicalRiskOfficialBroadIndustryMappingArtifact:
    artifact_id: str | None
    artifact_schema_version: str
    artifact_checksum: str | None
    diagnostic_scope: str
    universe_id: str
    universe_size: int
    source_authority: str
    source_url: str
    source_payload_checksum: str
    retrieved_at: str
    source_version: str
    classification_temporal_semantics: str
    historical_industry_classification_claim_allowed: bool
    technology_subset_semantics: str
    ai_exposure_classification_claim_allowed: bool
    records: tuple[TechnicalRiskOfficialBroadIndustryRecord, ...]

    def __post_init__(self) -> None:
        _require_version(
            self.artifact_schema_version,
            TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SCHEMA_V1,
            "artifact_schema_version",
        )
        _require_version(self.diagnostic_scope, TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SCOPE_V1, "diagnostic_scope")
        _require_version(self.universe_id, TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_ID_V1, "universe_id")
        if self.universe_size != TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_SIZE_V1:
            raise TechnicalRiskOfficialBroadIndustryMappingError("universe_size mismatch.")
        _require_version(
            self.source_authority,
            TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SOURCE_AUTHORITY_V1,
            "source_authority",
        )
        _require_version(self.source_url, TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SOURCE_URL_V1, "source_url")
        _require_text(self.source_payload_checksum, "source_payload_checksum")
        _require_text(self.retrieved_at, "retrieved_at")
        _require_text(self.source_version, "source_version")
        _require_version(
            self.classification_temporal_semantics,
            TECH_RISK_CURRENT_OFFICIAL_INDUSTRY_CLASSIFICATION_V1,
            "classification_temporal_semantics",
        )
        if self.historical_industry_classification_claim_allowed:
            raise TechnicalRiskOfficialBroadIndustryMappingError(
                "Current official classification cannot claim pre-2024 historical classification."
            )
        _require_version(
            self.technology_subset_semantics,
            TECH_RISK_TECHNOLOGY_REVIEW_CANDIDATE_WORKLOAD_PREVIEW_V1,
            "technology_subset_semantics",
        )
        if self.ai_exposure_classification_claim_allowed:
            raise TechnicalRiskOfficialBroadIndustryMappingError(
                "Technology review candidate preview cannot claim AI exposure classification."
            )
        records = tuple(sorted(self.records, key=lambda record: record.symbol))
        _validate_records(records)
        object.__setattr__(self, "records", records)
        checksum = _artifact_checksum(self)
        artifact_id = _stable_id("technical_risk_official_broad_industry_mapping", {"artifact_checksum": checksum})
        if self.artifact_id is not None and self.artifact_id != artifact_id:
            raise TechnicalRiskOfficialBroadIndustryMappingError("artifact_id mismatch.")
        if self.artifact_checksum is not None and self.artifact_checksum != checksum:
            raise TechnicalRiskOfficialBroadIndustryMappingError("artifact_checksum mismatch.")
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_checksum", checksum)

    @property
    def mapped_count(self) -> int:
        return sum(1 for record in self.records if record.mapping_status == TechnicalRiskBroadIndustryMappingStatus.MAPPED)

    @property
    def unknown_count(self) -> int:
        return sum(1 for record in self.records if record.mapping_status == TechnicalRiskBroadIndustryMappingStatus.UNKNOWN)

    @property
    def review_required_count(self) -> int:
        return sum(
            1 for record in self.records if record.mapping_status == TechnicalRiskBroadIndustryMappingStatus.REVIEW_REQUIRED
        )

    @property
    def technology_related_candidate_count(self) -> int:
        return sum(1 for record in self.records if record.is_technology_related_industry)

    def industry_distribution(self) -> tuple[dict[str, object], ...]:
        counts: dict[tuple[str | None, str], int] = {}
        for record in self.records:
            key = (record.broad_industry_code, record.broad_industry)
            counts[key] = counts.get(key, 0) + 1
        rows = []
        for (code, name), count in sorted(counts.items(), key=lambda item: (item[0][0] or "ZZ", item[0][1])):
            rows.append(
                {
                    "broad_industry_code": code,
                    "broad_industry": name,
                    "symbol_count": count,
                    "percentage_of_universe": round(count / self.universe_size, 6),
                    "technology_related_preview": code in TECH_RISK_TECHNOLOGY_RELATED_INDUSTRY_CODES_V1,
                }
            )
        return tuple(rows)


def build_official_broad_industry_mapping_artifact(
    *,
    universe_symbols: tuple[str, ...],
    official_rows: list[dict[str, object]],
    retrieved_at: str,
    source_url: str = TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SOURCE_URL_V1,
) -> TechnicalRiskOfficialBroadIndustryMappingArtifact:
    if len(universe_symbols) != TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_SIZE_V1:
        raise TechnicalRiskOfficialBroadIndustryMappingError("Frozen universe must contain exactly 218 symbols.")
    if len(set(universe_symbols)) != len(universe_symbols):
        raise TechnicalRiskOfficialBroadIndustryMappingError("Frozen universe contains duplicate symbols.")
    payload_checksum = _stable_hash({"official_rows": official_rows})
    source_version = _source_version(official_rows)
    by_code = _official_rows_by_code(official_rows)
    records = []
    for symbol in sorted(universe_symbols):
        code = symbol.removesuffix(".TW")
        row = by_code.get(code)
        if row is None:
            records.append(
                TechnicalRiskOfficialBroadIndustryRecord(
                    symbol=symbol,
                    company_name="",
                    broad_industry="",
                    broad_industry_code=None,
                    industry_source=TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SOURCE_AUTHORITY_V1,
                    industry_source_version=source_version,
                    classification_as_of_date=_source_date(source_version),
                    mapping_status=TechnicalRiskBroadIndustryMappingStatus.UNKNOWN,
                )
            )
            continue
        name = _first_text(row, ("公司簡稱", "公司名稱", "Name", "CompanyName"))
        raw_code = _first_text(row, ("產業別", "Industry"))
        industry_code = _normalize_industry_code(raw_code)
        industry_name = TWSE_INDUSTRY_CODE_NAMES_V1.get(industry_code or "")
        status = (
            TechnicalRiskBroadIndustryMappingStatus.MAPPED
            if industry_code and industry_name
            else TechnicalRiskBroadIndustryMappingStatus.REVIEW_REQUIRED
        )
        records.append(
            TechnicalRiskOfficialBroadIndustryRecord(
                symbol=symbol,
                company_name=name if status == TechnicalRiskBroadIndustryMappingStatus.MAPPED else name,
                broad_industry=industry_name or "",
                broad_industry_code=industry_code,
                industry_source=TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SOURCE_AUTHORITY_V1,
                industry_source_version=source_version,
                classification_as_of_date=_source_date(source_version),
                mapping_status=status,
                source_record_checksum=_stable_hash(row),
            )
        )
    return TechnicalRiskOfficialBroadIndustryMappingArtifact(
        artifact_id=None,
        artifact_schema_version=TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SCHEMA_V1,
        artifact_checksum=None,
        diagnostic_scope=TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SCOPE_V1,
        universe_id=TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_ID_V1,
        universe_size=TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_SIZE_V1,
        source_authority=TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SOURCE_AUTHORITY_V1,
        source_url=source_url,
        source_payload_checksum=payload_checksum,
        retrieved_at=retrieved_at,
        source_version=source_version,
        classification_temporal_semantics=TECH_RISK_CURRENT_OFFICIAL_INDUSTRY_CLASSIFICATION_V1,
        historical_industry_classification_claim_allowed=False,
        technology_subset_semantics=TECH_RISK_TECHNOLOGY_REVIEW_CANDIDATE_WORKLOAD_PREVIEW_V1,
        ai_exposure_classification_claim_allowed=False,
        records=tuple(records),
    )


def official_broad_industry_mapping_artifact_path(
    output_dir: Path | str = TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_RESEARCH_DIR,
) -> Path:
    return Path(output_dir) / TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_ARTIFACT_FILENAME_V1


def encode_official_broad_industry_mapping_artifact(
    artifact: TechnicalRiskOfficialBroadIndustryMappingArtifact,
) -> dict[str, object]:
    return {
        "artifact_id": artifact.artifact_id,
        "artifact_schema_version": artifact.artifact_schema_version,
        "artifact_checksum": artifact.artifact_checksum,
        "diagnostic_scope": artifact.diagnostic_scope,
        "universe_id": artifact.universe_id,
        "universe_size": artifact.universe_size,
        "source_authority": artifact.source_authority,
        "source_url": artifact.source_url,
        "source_payload_checksum": artifact.source_payload_checksum,
        "retrieved_at": artifact.retrieved_at,
        "source_version": artifact.source_version,
        "classification_temporal_semantics": artifact.classification_temporal_semantics,
        "historical_industry_classification_claim_allowed": artifact.historical_industry_classification_claim_allowed,
        "technology_subset_semantics": artifact.technology_subset_semantics,
        "ai_exposure_classification_claim_allowed": artifact.ai_exposure_classification_claim_allowed,
        "mapped_count": artifact.mapped_count,
        "unknown_count": artifact.unknown_count,
        "review_required_count": artifact.review_required_count,
        "technology_related_candidate_count": artifact.technology_related_candidate_count,
        "industry_distribution": artifact.industry_distribution(),
        "records": [_record_payload(record) for record in artifact.records],
    }


def save_official_broad_industry_mapping_artifact(
    artifact: TechnicalRiskOfficialBroadIndustryMappingArtifact,
    output_dir: Path | str = TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_RESEARCH_DIR,
) -> Path:
    path = official_broad_industry_mapping_artifact_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = encode_official_broad_industry_mapping_artifact(artifact)
    path.write_text(json.dumps(encoded, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def _validate_records(records: tuple[TechnicalRiskOfficialBroadIndustryRecord, ...]) -> None:
    if len(records) != TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_SIZE_V1:
        raise TechnicalRiskOfficialBroadIndustryMappingError("records must account for exactly 218 symbols.")
    symbols = tuple(record.symbol for record in records)
    if len(set(symbols)) != len(symbols):
        raise TechnicalRiskOfficialBroadIndustryMappingError("Duplicate symbol in broad industry mapping.")
    for symbol in symbols:
        _require_symbol(symbol)


def _artifact_checksum(artifact: TechnicalRiskOfficialBroadIndustryMappingArtifact) -> str:
    return _stable_hash(
        {
            "artifact_schema_version": artifact.artifact_schema_version,
            "diagnostic_scope": artifact.diagnostic_scope,
            "universe_id": artifact.universe_id,
            "universe_size": artifact.universe_size,
            "source_authority": artifact.source_authority,
            "source_url": artifact.source_url,
            "source_payload_checksum": artifact.source_payload_checksum,
            "source_version": artifact.source_version,
            "classification_temporal_semantics": artifact.classification_temporal_semantics,
            "historical_industry_classification_claim_allowed": artifact.historical_industry_classification_claim_allowed,
            "technology_subset_semantics": artifact.technology_subset_semantics,
            "ai_exposure_classification_claim_allowed": artifact.ai_exposure_classification_claim_allowed,
            "records": [_record_payload(record) for record in artifact.records],
        }
    )


def _record_payload(record: TechnicalRiskOfficialBroadIndustryRecord) -> dict[str, object]:
    return {
        "symbol": record.symbol,
        "company_name": record.company_name,
        "broad_industry": record.broad_industry,
        "broad_industry_code": record.broad_industry_code,
        "industry_source": record.industry_source,
        "industry_source_version": record.industry_source_version,
        "classification_as_of_date": record.classification_as_of_date.isoformat(),
        "mapping_status": record.mapping_status.value,
        "source_record_checksum": record.source_record_checksum,
        "technology_related_preview": record.is_technology_related_industry,
    }


def _official_rows_by_code(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    by_code: dict[str, dict[str, object]] = {}
    for row in rows:
        code = _normalize_security_code(_first_text(row, ("公司代號", "Code", "SecuritiesCompanyCode")))
        if not code:
            continue
        if code in by_code:
            raise TechnicalRiskOfficialBroadIndustryMappingError("Official payload contains duplicate company code.")
        by_code[code] = row
    return by_code


def _source_version(rows: list[dict[str, object]]) -> str:
    dates = sorted({_first_text(row, ("出表日期", "source_date")) for row in rows if _first_text(row, ("出表日期", "source_date"))})
    if len(dates) != 1:
        raise TechnicalRiskOfficialBroadIndustryMappingError("Official source date must be present and unique.")
    return f"TWSE_t187ap03_L_{dates[0]}"


def _source_date(source_version: str) -> date:
    raw = source_version.rsplit("_", maxsplit=1)[-1]
    if not re.fullmatch(r"\d{7}", raw):
        raise TechnicalRiskOfficialBroadIndustryMappingError("Unsupported TWSE source date format.")
    year = int(raw[:3]) + 1911
    return date(year, int(raw[3:5]), int(raw[5:7]))


def _normalize_security_code(value: str) -> str | None:
    match = re.match(r"^\s*(\d{4})\s*$", str(value or ""))
    return match.group(1) if match else None


def _normalize_industry_code(value: str) -> str | None:
    match = re.match(r"^\s*(\d{1,2})\s*$", str(value or ""))
    return match.group(1).zfill(2) if match else None


def _first_text(row: Mapping[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_symbol(value: str) -> None:
    if not re.fullmatch(r"\d{4}\.TW", value or ""):
        raise TechnicalRiskOfficialBroadIndustryMappingError("symbol must be a four-digit TWSE symbol.")


def _require_text(value: str | None, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskOfficialBroadIndustryMappingError(f"{field_name} must be a non-empty string.")


def _require_version(value: str, expected: str, field_name: str) -> None:
    if value != expected:
        raise TechnicalRiskOfficialBroadIndustryMappingError(f"{field_name} mismatch.")
