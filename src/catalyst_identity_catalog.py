"""Version-pinned, offline Taiwan listed-company identity resolution for Catalyst V1I."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re
from types import MappingProxyType


CATALYST_IDENTITY_CATALOG_VERSION = "CATALYST_V1I_TAIWAN_LISTED_COMPANY_IDENTITY_CATALOG_V1"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = (
    PROJECT_ROOT / "data" / "research" / "catalyst_identity" / "taiwan_listed_company_identity_catalog_v1.json"
)
DEFAULT_CATALOG_CHECKSUM = "63a923dece67cdc6bc5e86faaa635883141dc1c9b31a545d5db83649c43c7057"

_SYMBOL = re.compile(r"(?P<code>\d{4})\.(?P<market>TW|TWO)")
_ALIAS_CLASSES = frozenset({"CANONICAL_NAME", "OFFICIAL_SHORT_NAME", "APPROVED_COMMON_ALIAS"})
_ATTRIBUTION_SUFFIXES = "表示|指出|公告|公布|宣布|說明"


class CatalystIdentityCatalogError(ValueError):
    """Raised when the explicit Catalyst identity catalog cannot be trusted."""


@dataclass(frozen=True)
class ApprovedAlias:
    value: str
    alias_class: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise CatalystIdentityCatalogError("Catalog aliases must be non-blank.")
        if self.alias_class not in _ALIAS_CLASSES:
            raise CatalystIdentityCatalogError(f"Unsupported catalog alias class: {self.alias_class}.")


@dataclass(frozen=True)
class ListedCompanyIdentity:
    symbol: str
    canonical_name_zh: str | None
    official_short_name_zh: str | None
    approved_aliases: tuple[ApprovedAlias, ...]
    listing_market: str

    def __post_init__(self) -> None:
        match = _SYMBOL.fullmatch(self.symbol)
        if match is None:
            raise CatalystIdentityCatalogError(f"Malformed catalog symbol: {self.symbol!r}.")
        if self.listing_market not in {"TWSE", "TPEx"}:
            raise CatalystIdentityCatalogError(f"Unsupported catalog market: {self.listing_market}.")
        expected_suffix = "TW" if self.listing_market == "TWSE" else "TWO"
        if match.group("market") != expected_suffix:
            raise CatalystIdentityCatalogError("Catalog symbol suffix does not match listing market.")
        if not self.canonical_name_zh and not self.official_short_name_zh:
            raise CatalystIdentityCatalogError("Catalog identity requires a canonical or official short name.")
        aliases = tuple(sorted(self.approved_aliases, key=lambda item: (item.value, item.alias_class)))
        if len({(item.value, item.alias_class) for item in aliases}) != len(aliases):
            raise CatalystIdentityCatalogError("Catalog identity contains duplicate alias entries.")
        object.__setattr__(self, "approved_aliases", aliases)


class TaiwanListedCompanyIdentityCatalog:
    """Immutable catalog with exact, context-bounded non-target identity detection."""

    def __init__(
        self,
        *,
        version: str,
        checksum: str,
        records: tuple[ListedCompanyIdentity, ...],
        resolvable_alias_count: int,
        ambiguous_alias_count: int,
    ) -> None:
        self.version = version
        self.checksum = checksum
        self.records = tuple(sorted(records, key=lambda record: record.symbol))
        by_symbol: dict[str, ListedCompanyIdentity] = {}
        canonical_names: set[str] = set()
        aliases: dict[str, set[str]] = {}
        for record in self.records:
            if record.symbol in by_symbol:
                raise CatalystIdentityCatalogError(f"Duplicate catalog symbol: {record.symbol}.")
            by_symbol[record.symbol] = record
            if record.canonical_name_zh:
                if record.canonical_name_zh in canonical_names:
                    raise CatalystIdentityCatalogError(
                        f"Duplicate canonical identity: {record.canonical_name_zh}."
                    )
                canonical_names.add(record.canonical_name_zh)
            for alias in record.approved_aliases:
                aliases.setdefault(alias.value, set()).add(record.symbol)

        unique_aliases = {
            alias: by_symbol[next(iter(symbols))]
            for alias, symbols in aliases.items()
            if len(symbols) == 1
        }
        ambiguous_aliases = frozenset(alias for alias, symbols in aliases.items() if len(symbols) > 1)
        if len(unique_aliases) != resolvable_alias_count:
            raise CatalystIdentityCatalogError("Catalog resolvable_alias_count does not match records.")
        if len(ambiguous_aliases) != ambiguous_alias_count:
            raise CatalystIdentityCatalogError("Catalog ambiguous_alias_count does not match records.")

        self._by_symbol = MappingProxyType(by_symbol)
        self._unique_aliases = MappingProxyType(unique_aliases)
        self._ambiguous_aliases = ambiguous_aliases
        self._alias_pattern = _context_pattern(tuple(unique_aliases))

    def resolve_symbol(self, symbol: str) -> ListedCompanyIdentity | None:
        return self._by_symbol.get(symbol.strip().upper())

    def resolve_exact_alias(self, alias: str) -> ListedCompanyIdentity | None:
        return self._unique_aliases.get(alias.strip())

    def is_ambiguous_alias(self, alias: str) -> bool:
        return alias.strip() in self._ambiguous_aliases

    def find_explicit_non_target_identities(
        self,
        text: str,
        target_symbol: str,
    ) -> tuple[ListedCompanyIdentity, ...]:
        if not text or self._alias_pattern is None:
            return ()
        target = target_symbol.strip().upper()
        identities = {
            self._unique_aliases[_matched_alias(match)].symbol: self._unique_aliases[_matched_alias(match)]
            for match in self._alias_pattern.finditer(text)
            if self._unique_aliases[_matched_alias(match)].symbol != target
        }
        return tuple(sorted(identities.values(), key=lambda identity: identity.symbol))


def load_identity_catalog(
    path: Path | str,
    expected_version: str,
    expected_checksum: str,
) -> TaiwanListedCompanyIdentityCatalog:
    catalog_path = Path(path)
    if not catalog_path.is_file():
        raise CatalystIdentityCatalogError(f"Catalog file is missing: {catalog_path}.")
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalystIdentityCatalogError("Catalog file is malformed.") from exc
    if not isinstance(payload, dict):
        raise CatalystIdentityCatalogError("Catalog payload must be an object.")
    version = payload.get("catalog_version")
    if version != expected_version or payload.get("effective_version") != expected_version:
        raise CatalystIdentityCatalogError("Catalog version does not match the required V1 pin.")
    supplied_checksum = payload.get("catalog_checksum")
    if not _checksum_is_valid(supplied_checksum):
        raise CatalystIdentityCatalogError("Catalog checksum is malformed.")
    actual_checksum = catalog_checksum(payload)
    if supplied_checksum != actual_checksum or expected_checksum != actual_checksum:
        raise CatalystIdentityCatalogError("Catalog checksum mismatch.")
    provenance = payload.get("source_provenance")
    source_checksums = payload.get("source_snapshot_checksums")
    if not isinstance(provenance, list) or not provenance or not isinstance(source_checksums, dict) or not source_checksums:
        raise CatalystIdentityCatalogError("Catalog requires source provenance and input checksums.")
    records_payload = payload.get("records")
    if not isinstance(records_payload, list) or payload.get("record_count") != len(records_payload):
        raise CatalystIdentityCatalogError("Catalog record_count does not match records.")
    records = tuple(_identity_from_payload(item) for item in records_payload)
    if tuple(record.symbol for record in records) != tuple(sorted(record.symbol for record in records)):
        raise CatalystIdentityCatalogError("Catalog records must use stable symbol ordering.")
    twse_count = sum(record.listing_market == "TWSE" for record in records)
    tpex_count = sum(record.listing_market == "TPEx" for record in records)
    if payload.get("twse_record_count") != twse_count or payload.get("tpex_record_count") != tpex_count:
        raise CatalystIdentityCatalogError("Catalog market counts do not match records.")
    return TaiwanListedCompanyIdentityCatalog(
        version=expected_version,
        checksum=actual_checksum,
        records=records,
        resolvable_alias_count=_required_nonnegative_int(payload, "resolvable_alias_count"),
        ambiguous_alias_count=_required_nonnegative_int(payload, "ambiguous_alias_count"),
    )


@lru_cache(maxsize=1)
def load_default_identity_catalog() -> TaiwanListedCompanyIdentityCatalog:
    if DEFAULT_CATALOG_CHECKSUM == "CATALOG_CHECKSUM_PENDING_BUILD":
        raise CatalystIdentityCatalogError("Catalyst V1 identity catalog checksum pin is not configured.")
    return load_identity_catalog(
        DEFAULT_CATALOG_PATH,
        CATALYST_IDENTITY_CATALOG_VERSION,
        DEFAULT_CATALOG_CHECKSUM,
    )


def catalog_checksum(payload: dict[str, object]) -> str:
    checksum_payload = {key: value for key, value in payload.items() if key != "catalog_checksum"}
    return sha256(_serialize(checksum_payload)).hexdigest()


def _identity_from_payload(value: object) -> ListedCompanyIdentity:
    if not isinstance(value, dict):
        raise CatalystIdentityCatalogError("Catalog record must be an object.")
    aliases_payload = value.get("approved_aliases")
    if not isinstance(aliases_payload, list):
        raise CatalystIdentityCatalogError("Catalog approved_aliases must be a list.")
    aliases = []
    for alias in aliases_payload:
        if not isinstance(alias, dict):
            raise CatalystIdentityCatalogError("Catalog alias must be an object.")
        alias_value = alias.get("value")
        alias_class = alias.get("alias_class")
        if not isinstance(alias_value, str) or not isinstance(alias_class, str):
            raise CatalystIdentityCatalogError("Catalog alias fields must be strings.")
        aliases.append(ApprovedAlias(alias_value.strip(), alias_class))
    canonical = value.get("canonical_name_zh")
    short = value.get("official_short_name_zh")
    if canonical is not None and not isinstance(canonical, str):
        raise CatalystIdentityCatalogError("Catalog canonical_name_zh must be a string or null.")
    if short is not None and not isinstance(short, str):
        raise CatalystIdentityCatalogError("Catalog official_short_name_zh must be a string or null.")
    symbol = value.get("symbol")
    market = value.get("listing_market")
    if not isinstance(symbol, str) or not isinstance(market, str):
        raise CatalystIdentityCatalogError("Catalog record requires symbol and listing_market.")
    return ListedCompanyIdentity(symbol, canonical.strip() if canonical else None, short.strip() if short else None, tuple(aliases), market)


def _context_pattern(aliases: tuple[str, ...]) -> re.Pattern[str] | None:
    if not aliases:
        return None
    alternatives = "|".join(re.escape(alias) for alias in sorted(aliases, key=lambda item: (-len(item), item)))
    return re.compile(
        rf"(?<![0-9A-Za-z\u4e00-\u9fff])(?:公司名稱\s*[：:]\s*(?P<structured>{alternatives})(?=$|[\s,，。；;（）()])|(?P<attribution>{alternatives})(?:{_ATTRIBUTION_SUFFIXES}))"
    )


def _matched_alias(match: re.Match[str]) -> str:
    return match.group("structured") or match.group("attribution")


def _required_nonnegative_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value < 0:
        raise CatalystIdentityCatalogError(f"Catalog {key} must be a non-negative integer.")
    return value


def _checksum_is_valid(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _serialize(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
