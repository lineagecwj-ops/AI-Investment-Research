import json
from json import JSONDecodeError
from pathlib import Path

from symbol_utils import normalize_stock_symbol


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WATCHLIST_PATH = PROJECT_ROOT / "data" / "watchlist.json"


class WatchlistDataError(Exception):
    """Raised when existing watchlist data is corrupted or unsafe to overwrite."""


def list_watchlist(path: Path | str = DEFAULT_WATCHLIST_PATH) -> list[str]:
    return read_watchlist(path)


def add_stock(symbol: str, path: Path | str = DEFAULT_WATCHLIST_PATH) -> bool:
    normalized_symbol = normalize_stock_symbol(symbol)
    if not normalized_symbol:
        return False

    symbols = read_watchlist(path)
    if normalized_symbol in symbols:
        return False

    symbols.append(normalized_symbol)
    write_watchlist(symbols, path)
    return True


def remove_stock(symbol: str, path: Path | str = DEFAULT_WATCHLIST_PATH) -> bool:
    normalized_symbol = normalize_stock_symbol(symbol)
    symbols = read_watchlist(path)

    if normalized_symbol not in symbols:
        return False

    symbols.remove(normalized_symbol)
    write_watchlist(symbols, path)
    return True


def read_watchlist(path: Path | str = DEFAULT_WATCHLIST_PATH) -> list[str]:
    watchlist_path = Path(path)
    if not watchlist_path.exists() or watchlist_path.stat().st_size == 0:
        return []

    try:
        data = json.loads(watchlist_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise WatchlistDataError("Watchlist 檔案讀取失敗。") from exc
    except JSONDecodeError as exc:
        raise WatchlistDataError("Watchlist 檔案格式錯誤，請先檢查 data/watchlist.json。") from exc

    if not isinstance(data, list):
        raise WatchlistDataError("Watchlist 檔案內容格式錯誤，最外層應為 list。")

    return normalize_watchlist_items(data)


def write_watchlist(symbols: list[str], path: Path | str = DEFAULT_WATCHLIST_PATH) -> None:
    watchlist_path = Path(path)
    watchlist_path.parent.mkdir(parents=True, exist_ok=True)
    watchlist_path.write_text(
        json.dumps(symbols, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def normalize_watchlist_items(items: list[object]) -> list[str]:
    symbols = []
    seen_symbols = set()

    for item in items:
        if not isinstance(item, str):
            continue

        symbol = normalize_stock_symbol(item)
        if not symbol or symbol in seen_symbols:
            continue

        symbols.append(symbol)
        seen_symbols.add(symbol)

    return symbols
