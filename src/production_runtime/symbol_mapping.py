from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any
from typing import Mapping

from market_inputs import TechnicalMarketDataProvider


PROVIDER_SYMBOL_MAPPING_SCHEMA_VERSION = "1"


class ProviderSymbolMappingError(ValueError):
    """Raised when controlled provider symbol mapping is invalid."""


@dataclass(frozen=True)
class ProviderSymbolMappingEntry:
    domain_symbol: str
    provider: TechnicalMarketDataProvider | str
    provider_symbol: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain_symbol", _require_text(self.domain_symbol, "domain_symbol"))
        object.__setattr__(self, "provider", _coerce_provider(self.provider))
        object.__setattr__(self, "provider_symbol", _require_text(self.provider_symbol, "provider_symbol"))


@dataclass(frozen=True)
class ProviderSymbolMapping:
    schema_version: str
    mapping_version: str
    mappings: tuple[ProviderSymbolMappingEntry, ...]

    def __post_init__(self) -> None:
        if self.schema_version != PROVIDER_SYMBOL_MAPPING_SCHEMA_VERSION:
            raise ProviderSymbolMappingError("unsupported provider symbol mapping schema_version.")
        object.__setattr__(self, "mapping_version", _require_text(self.mapping_version, "mapping_version"))
        mappings = tuple(
            entry if isinstance(entry, ProviderSymbolMappingEntry) else ProviderSymbolMappingEntry(**entry)
            for entry in self.mappings
        )
        if not mappings:
            raise ProviderSymbolMappingError("provider symbol mapping requires at least one mapping.")
        domain_symbols = tuple(entry.domain_symbol for entry in mappings)
        if len(set(domain_symbols)) != len(domain_symbols):
            raise ProviderSymbolMappingError("duplicate provider symbol mapping domain_symbol.")
        object.__setattr__(self, "mappings", tuple(sorted(mappings, key=lambda entry: entry.domain_symbol)))

    @property
    def provider_symbol_by_symbol(self) -> Mapping[str, str]:
        return MappingProxyType({entry.domain_symbol: entry.provider_symbol for entry in self.mappings})

    def provider_symbols_for(
        self,
        domain_symbols: tuple[str, ...],
        *,
        provider: TechnicalMarketDataProvider | str = TechnicalMarketDataProvider.YAHOO_FINANCE_V1,
    ) -> Mapping[str, str]:
        provider = _coerce_provider(provider)
        result: dict[str, str] = {}
        for symbol in domain_symbols:
            symbol = _require_text(symbol, "domain_symbol")
            matches = tuple(entry for entry in self.mappings if entry.domain_symbol == symbol and entry.provider == provider)
            if len(matches) != 1:
                raise ProviderSymbolMappingError(f"provider symbol mapping missing for domain symbol: {symbol}.")
            result[symbol] = matches[0].provider_symbol
        return MappingProxyType(result)


def load_provider_symbol_mapping(path: str | Path) -> ProviderSymbolMapping:
    payload = _read_json(path)
    _require_exact_fields(payload, frozenset({"schema_version", "mapping_version", "mappings"}), "provider symbol mapping")
    mappings = payload["mappings"]
    if not isinstance(mappings, list):
        raise ProviderSymbolMappingError("mappings must be a JSON array.")
    entries = tuple(_entry_from_payload(item, index) for index, item in enumerate(mappings))
    return ProviderSymbolMapping(
        schema_version=_require_text(payload["schema_version"], "schema_version"),
        mapping_version=_require_text(payload["mapping_version"], "mapping_version"),
        mappings=entries,
    )


def _entry_from_payload(payload: object, index: int) -> ProviderSymbolMappingEntry:
    if not isinstance(payload, dict):
        raise ProviderSymbolMappingError(f"mappings[{index}] must be a JSON object.")
    _require_exact_fields(payload, frozenset({"domain_symbol", "provider", "provider_symbol"}), f"mappings[{index}]")
    return ProviderSymbolMappingEntry(
        domain_symbol=_require_text(payload["domain_symbol"], f"mappings[{index}].domain_symbol"),
        provider=_require_text(payload["provider"], f"mappings[{index}].provider"),
        provider_symbol=_require_text(payload["provider_symbol"], f"mappings[{index}].provider_symbol"),
    )


def _read_json(path: str | Path) -> dict[str, Any]:
    source_path = Path(path)
    if not source_path.exists():
        raise ProviderSymbolMappingError("provider symbol mapping file does not exist.")
    if not source_path.is_file():
        raise ProviderSymbolMappingError("provider symbol mapping path must be a file.")
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except ProviderSymbolMappingError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderSymbolMappingError("provider symbol mapping file cannot be loaded.") from exc
    if not isinstance(payload, dict):
        raise ProviderSymbolMappingError("provider symbol mapping document must be a JSON object.")
    return payload


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProviderSymbolMappingError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_exact_fields(payload: dict[str, Any], expected_fields: frozenset[str], label: str) -> None:
    actual_fields = set(payload)
    missing = sorted(expected_fields - actual_fields)
    if missing:
        raise ProviderSymbolMappingError(f"{label} missing required field: {missing[0]}")
    unknown = sorted(actual_fields - expected_fields)
    if unknown:
        raise ProviderSymbolMappingError(f"{label} contains unknown field: {unknown[0]}")


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise ProviderSymbolMappingError(f"{field_name} must be a non-empty single-line string.")
    return value


def _coerce_provider(value: TechnicalMarketDataProvider | str) -> TechnicalMarketDataProvider:
    try:
        return value if isinstance(value, TechnicalMarketDataProvider) else TechnicalMarketDataProvider(value)
    except ValueError as exc:
        raise ProviderSymbolMappingError("unsupported market data provider.") from exc
