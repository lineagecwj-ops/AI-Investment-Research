import hashlib
import re
from datetime import datetime

from models import ResearchUniverse
from frozen_twse_research_universe_service import FrozenTWSEResearchUniverse
from frozen_twse_research_universe_service import load_frozen_twse_research_universe
from universe_service import MAX_UNIVERSE_DESCRIPTION_LENGTH
from universe_service import MAX_UNIVERSE_NAME_LENGTH
from universe_service import normalize_universe_symbols
from ui_terminology import get_source_label


MANUAL_SOURCE = "Manual Input"
WATCHLIST_SOURCE = "Watchlist"
SAVED_UNIVERSE_SOURCE = "Saved Universe"
FROZEN_TWSE_RESEARCH_SOURCE = "Frozen TWSE Research Universe"
SOURCE_OPTIONS = (
    MANUAL_SOURCE,
    WATCHLIST_SOURCE,
    SAVED_UNIVERSE_SOURCE,
    FROZEN_TWSE_RESEARCH_SOURCE,
)
LARGE_UNIVERSE_WARNING_THRESHOLD = 50
UNIVERSE_SEMANTICS_CAPTION = "股票池只是研究標的集合，不代表投資建議或預測。"
FROZEN_TWSE_RESEARCH_SOURCE_INFO = "使用目前鎖定的 TWSE 研究股票池，共 218 檔。"
FROZEN_TWSE_RESEARCH_DISCLOSURE = (
    "此股票池為目前研究使用的 Frozen TWSE universe，不是全部上市櫃股票，"
    "且為 2026 current ETF constituent-derived universe。"
)


def parse_universe_symbol_text(symbol_text: str) -> tuple[str, ...]:
    raw_symbols = [
        raw_symbol
        for raw_symbol in re.split(r"[\s,;，；]+", symbol_text or "")
        if raw_symbol.strip()
    ]
    return normalize_universe_symbols(raw_symbols)


def symbols_to_text(symbols: tuple[str, ...]) -> str:
    return "\n".join(symbols)


def universe_selector_label(universe: ResearchUniverse) -> str:
    return f"{universe.name} ({universe.symbol_count})"


def format_universe_updated_at(universe: ResearchUniverse) -> str:
    return _format_datetime(universe.updated_at)


def source_display_name(
    *,
    source_type: str,
    universe_name: str | None = None,
) -> str:
    if source_type == SAVED_UNIVERSE_SOURCE and universe_name:
        return f"{get_source_label(SAVED_UNIVERSE_SOURCE)} - {universe_name}"
    return get_source_label(source_type)


def build_source_context(
    *,
    source_type: str,
    symbols: tuple[str, ...],
    universe_id: str | None = None,
    universe_name: str | None = None,
) -> dict[str, object]:
    return {
        "source_type": source_type,
        "source_universe_id": universe_id,
        "source_universe_name": universe_name,
        "symbols_copy": tuple(symbols),
        "symbol_count": len(symbols),
    }


def load_frozen_twse_research_source() -> FrozenTWSEResearchUniverse:
    return load_frozen_twse_research_universe()


def frozen_twse_research_source_context(
    universe: FrozenTWSEResearchUniverse,
) -> dict[str, object]:
    return build_source_context(
        source_type=FROZEN_TWSE_RESEARCH_SOURCE,
        symbols=universe.symbols,
        universe_id=universe.universe_id,
        universe_name=get_source_label(FROZEN_TWSE_RESEARCH_SOURCE),
    )


def universe_symbols_fingerprint(symbols: tuple[str, ...]) -> str:
    digest = hashlib.sha256("\n".join(symbols).encode("utf-8")).hexdigest()[:16]
    return f"universe_symbols_{digest}"


def source_fingerprint(
    *,
    source_type: str,
    symbols: tuple[str, ...],
    universe_id: str | None = None,
) -> str:
    identity = "|".join(
        (
            source_type,
            universe_id or "",
            "\n".join(symbols),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"swing_source_{digest}"


def build_universe_form_defaults(universe: ResearchUniverse | None) -> dict[str, str]:
    if universe is None:
        return {"name": "", "description": "", "symbols": ""}
    return {
        "name": universe.name,
        "description": universe.description or "",
        "symbols": symbols_to_text(universe.symbols),
    }


def should_warn_large_universe(symbols: tuple[str, ...]) -> bool:
    return len(symbols) > LARGE_UNIVERSE_WARNING_THRESHOLD


def validate_form_lengths(name: str, description: str | None) -> list[str]:
    errors = []
    if len((name or "").strip()) > MAX_UNIVERSE_NAME_LENGTH:
        errors.append(f"股票池名稱不可超過 {MAX_UNIVERSE_NAME_LENGTH} 字。")
    if description and len(description.strip()) > MAX_UNIVERSE_DESCRIPTION_LENGTH:
        errors.append(f"股票池描述不可超過 {MAX_UNIVERSE_DESCRIPTION_LENGTH} 字。")
    return errors


def _format_datetime(value: datetime) -> str:
    return value.isoformat()
