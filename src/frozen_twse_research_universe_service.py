from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from database import DEFAULT_DB_PATH
from etf_constituent_universe_service import UNIVERSE_VERSION
from expanded_volume_threshold_validation_service import _materialized_twse_common_stock_symbols


FROZEN_TWSE_RESEARCH_UNIVERSE_ID = "frozen_twse_research_universe_2026_08_09"
FROZEN_TWSE_RESEARCH_SYMBOL_COUNT = 218
FROZEN_TAIWAN_TOTAL_COUNT = 224
FROZEN_TPEX_EXCLUDED_COUNT = 6
FROZEN_TWSE_RESEARCH_SELECTION_RULE = (
    "Materialized frozen TWSE common-stock universe in data/stocks.db; "
    "four-digit .TW symbols excluding ETF 0050.TW and non-Taiwan symbols."
)


class FrozenTWSEResearchUniverseError(Exception):
    """Raised when the frozen TWSE research universe cannot be used safely."""


@dataclass(frozen=True)
class FrozenTWSEResearchUniverse:

    universe_id: str

    universe_version: str

    symbols: tuple[str, ...]

    frozen_total_count: int

    twse_count: int

    tpex_excluded_count: int

    selection_rule: str


def load_frozen_twse_research_universe(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    symbol_loader=None,
) -> FrozenTWSEResearchUniverse:
    try:
        symbols = tuple(
            symbol_loader(db_path)
            if symbol_loader is not None
            else _materialized_twse_common_stock_symbols(db_path)
        )
    except FrozenTWSEResearchUniverseError:
        raise
    except Exception as exc:
        raise FrozenTWSEResearchUniverseError(
            "研究股票池資料驗證失敗：canonical frozen universe artifact 無法讀取。"
        ) from exc
    _validate_frozen_twse_symbols(symbols)
    return FrozenTWSEResearchUniverse(
        universe_id=FROZEN_TWSE_RESEARCH_UNIVERSE_ID,
        universe_version=UNIVERSE_VERSION,
        symbols=symbols,
        frozen_total_count=FROZEN_TAIWAN_TOTAL_COUNT,
        twse_count=FROZEN_TWSE_RESEARCH_SYMBOL_COUNT,
        tpex_excluded_count=FROZEN_TPEX_EXCLUDED_COUNT,
        selection_rule=FROZEN_TWSE_RESEARCH_SELECTION_RULE,
    )


def load_frozen_twse_research_symbols(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    symbol_loader=None,
) -> tuple[str, ...]:
    return load_frozen_twse_research_universe(
        db_path=db_path,
        symbol_loader=symbol_loader,
    ).symbols


def _validate_frozen_twse_symbols(symbols: tuple[str, ...]) -> None:
    if len(symbols) != FROZEN_TWSE_RESEARCH_SYMBOL_COUNT:
        raise FrozenTWSEResearchUniverseError(
            "研究股票池資料驗證失敗："
            f"Frozen TWSE 研究股票池必須包含 {FROZEN_TWSE_RESEARCH_SYMBOL_COUNT} 檔，"
            f"目前為 {len(symbols)} 檔。"
        )
    duplicate_count = len(symbols) - len(set(symbols))
    if duplicate_count:
        raise FrozenTWSEResearchUniverseError(
            f"研究股票池資料驗證失敗：Frozen TWSE 研究股票池包含 {duplicate_count} 個重複股票代號。"
        )
    invalid_symbols = tuple(
        symbol
        for symbol in symbols
        if not _is_valid_twse_common_stock_symbol(symbol)
    )
    if invalid_symbols:
        preview = ", ".join(invalid_symbols[:5])
        raise FrozenTWSEResearchUniverseError(
            "研究股票池資料驗證失敗：Frozen TWSE 研究股票池包含非 TWSE common-stock symbol："
            f"{preview}。"
        )
    if tuple(sorted(symbols)) != symbols:
        raise FrozenTWSEResearchUniverseError(
            "研究股票池資料驗證失敗：Frozen TWSE 研究股票池順序必須為 deterministic ascending order。"
        )


def _is_valid_twse_common_stock_symbol(symbol: str) -> bool:
    code, separator, suffix = symbol.partition(".")
    return (
        separator == "."
        and code.isdigit()
        and len(code) == 4
        and suffix == "TW"
        and symbol != "0050.TW"
    )
