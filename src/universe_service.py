import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from pathlib import Path

from database import DEFAULT_DB_PATH
from database import datetime_to_cache_value
from database import initialize_database
from database import parse_cache_datetime
from database import utc_now
from models import ResearchUniverse
from symbol_utils import normalize_stock_symbol


MAX_UNIVERSE_NAME_LENGTH = 100
MAX_UNIVERSE_DESCRIPTION_LENGTH = 500


class UniverseError(Exception):
    """Base error for research universe operations."""


class UniverseNotFoundError(UniverseError):
    """Raised when a requested universe does not exist."""


class UniverseValidationError(UniverseError):
    """Raised when universe input is invalid."""


class UniverseAlreadyExistsError(UniverseError):
    """Raised when a universe name collides with an existing universe."""


class UniverseDataError(UniverseError):
    """Raised when persisted universe data is malformed."""


def create_universe(
    *,
    name: str,
    symbols=tuple(),
    description: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
    now: datetime | None = None,
    id_factory: Callable[[], str] | None = None,
) -> ResearchUniverse:
    timestamp = _normalized_now(now)
    universe_id = (id_factory or _generate_universe_id)()
    normalized_name = _validate_name(name)
    normalized_description = _validate_description(description)
    normalized_symbols = normalize_universe_symbols(symbols)

    initialize_database(db_path)
    connection = sqlite3.connect(Path(db_path))
    try:
        connection.execute("BEGIN")
        _ensure_name_available(connection, normalized_name)
        connection.execute(
            """
            INSERT INTO research_universes (
                id,
                name,
                description,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                universe_id,
                normalized_name,
                normalized_description,
                datetime_to_cache_value(timestamp),
                datetime_to_cache_value(timestamp),
            ),
        )
        _replace_symbol_rows(connection, universe_id, normalized_symbols)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return get_universe(universe_id, db_path=db_path)


def get_universe(
    universe_id: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> ResearchUniverse:
    initialize_database(db_path)
    connection = sqlite3.connect(Path(db_path))
    try:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT id, name, description, created_at, updated_at
            FROM research_universes
            WHERE id = ?
            """,
            (universe_id,),
        ).fetchone()
        if row is None:
            raise UniverseNotFoundError("找不到指定股票池。")
        symbol_rows = _fetch_symbol_rows(connection, universe_id)
    finally:
        connection.close()

    return _universe_from_rows(row, symbol_rows)


def list_universes(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[ResearchUniverse]:
    initialize_database(db_path)
    connection = sqlite3.connect(Path(db_path))
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, name, description, created_at, updated_at
            FROM research_universes
            ORDER BY lower(name) ASC, created_at ASC, id ASC
            """
        ).fetchall()
        universes = [
            _universe_from_rows(row, _fetch_symbol_rows(connection, row["id"]))
            for row in rows
        ]
    finally:
        connection.close()

    return universes


def update_universe(
    universe_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    symbols=None,
    db_path: Path | str = DEFAULT_DB_PATH,
    now: datetime | None = None,
) -> ResearchUniverse:
    timestamp = _normalized_now(now)
    initialize_database(db_path)
    connection = sqlite3.connect(Path(db_path))
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        existing = connection.execute(
            """
            SELECT id, name, description, created_at, updated_at
            FROM research_universes
            WHERE id = ?
            """,
            (universe_id,),
        ).fetchone()
        if existing is None:
            raise UniverseNotFoundError("找不到指定股票池。")

        next_name = _validate_name(name) if name is not None else existing["name"]
        next_description = (
            _validate_description(description)
            if description is not None
            else existing["description"]
        )
        _ensure_name_available(connection, next_name, exclude_universe_id=universe_id)

        connection.execute(
            """
            UPDATE research_universes
            SET name = ?,
                description = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_name,
                next_description,
                datetime_to_cache_value(timestamp),
                universe_id,
            ),
        )
        if symbols is not None:
            _replace_symbol_rows(
                connection,
                universe_id,
                normalize_universe_symbols(symbols),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return get_universe(universe_id, db_path=db_path)


def replace_symbols(
    universe_id: str,
    symbols,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    now: datetime | None = None,
) -> ResearchUniverse:
    return update_universe(
        universe_id,
        symbols=symbols,
        db_path=db_path,
        now=now,
    )


def add_symbols(
    universe_id: str,
    symbols,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    now: datetime | None = None,
) -> ResearchUniverse:
    universe = get_universe(universe_id, db_path=db_path)
    merged = list(universe.symbols)
    seen = set(merged)
    for symbol in normalize_universe_symbols(symbols):
        if symbol in seen:
            continue
        merged.append(symbol)
        seen.add(symbol)
    return replace_symbols(universe_id, merged, db_path=db_path, now=now)


def remove_symbols(
    universe_id: str,
    symbols,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    now: datetime | None = None,
) -> ResearchUniverse:
    universe = get_universe(universe_id, db_path=db_path)
    to_remove = set(normalize_universe_symbols(symbols))
    remaining = [symbol for symbol in universe.symbols if symbol not in to_remove]
    return replace_symbols(universe_id, remaining, db_path=db_path, now=now)


def delete_universe(
    universe_id: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    initialize_database(db_path)
    connection = sqlite3.connect(Path(db_path))
    try:
        connection.execute("BEGIN")
        existing = connection.execute(
            "SELECT id FROM research_universes WHERE id = ?",
            (universe_id,),
        ).fetchone()
        if existing is None:
            raise UniverseNotFoundError("找不到指定股票池。")
        connection.execute(
            "DELETE FROM research_universe_symbols WHERE universe_id = ?",
            (universe_id,),
        )
        connection.execute(
            "DELETE FROM research_universes WHERE id = ?",
            (universe_id,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def normalize_universe_symbols(symbols) -> tuple[str, ...]:
    normalized_symbols = []
    seen_symbols = set()
    for raw_symbol in symbols:
        symbol = normalize_stock_symbol(raw_symbol)
        if not symbol or symbol in seen_symbols:
            continue
        normalized_symbols.append(symbol)
        seen_symbols.add(symbol)
    return tuple(normalized_symbols)


def _fetch_symbol_rows(
    connection: sqlite3.Connection,
    universe_id: str,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT position, symbol
        FROM research_universe_symbols
        WHERE universe_id = ?
        ORDER BY position ASC, symbol ASC
        """,
        (universe_id,),
    ).fetchall()


def _replace_symbol_rows(
    connection: sqlite3.Connection,
    universe_id: str,
    symbols: tuple[str, ...],
) -> None:
    connection.execute(
        "DELETE FROM research_universe_symbols WHERE universe_id = ?",
        (universe_id,),
    )
    connection.executemany(
        """
        INSERT INTO research_universe_symbols (
            universe_id,
            position,
            symbol
        )
        VALUES (?, ?, ?)
        """,
        (
            (universe_id, position, symbol)
            for position, symbol in enumerate(symbols)
        ),
    )


def _universe_from_rows(row: sqlite3.Row, symbol_rows: list[sqlite3.Row]) -> ResearchUniverse:
    _validate_symbol_rows(symbol_rows)
    return ResearchUniverse(
        id=row["id"],
        name=_validate_name(row["name"]),
        description=_validate_description(row["description"]),
        symbols=tuple(symbol_row["symbol"] for symbol_row in symbol_rows),
        created_at=_parse_required_datetime(row["created_at"], "created_at"),
        updated_at=_parse_required_datetime(row["updated_at"], "updated_at"),
    )


def _validate_symbol_rows(symbol_rows: list[sqlite3.Row]) -> None:
    seen_symbols = set()
    seen_positions = set()
    expected_position = 0
    for row in symbol_rows:
        position = row["position"]
        symbol = row["symbol"]
        if not isinstance(position, int) or position < 0:
            raise UniverseDataError("股票池 symbol position 資料異常。")
        if position in seen_positions:
            raise UniverseDataError("股票池 symbol position 重複。")
        if position != expected_position:
            raise UniverseDataError("股票池 symbol position 不連續。")
        if not symbol or normalize_stock_symbol(symbol) != symbol:
            raise UniverseDataError("股票池 symbol 資料異常。")
        if symbol in seen_symbols:
            raise UniverseDataError("股票池 symbol 重複。")
        seen_positions.add(position)
        seen_symbols.add(symbol)
        expected_position += 1


def _validate_name(name: str) -> str:
    normalized_name = str(name).strip()
    if not normalized_name:
        raise UniverseValidationError("股票池名稱不可空白。")
    if len(normalized_name) > MAX_UNIVERSE_NAME_LENGTH:
        raise UniverseValidationError(
            f"股票池名稱不可超過 {MAX_UNIVERSE_NAME_LENGTH} 字。"
        )
    return normalized_name


def _validate_description(description: str | None) -> str | None:
    if description is None:
        return None
    normalized_description = str(description).strip()
    if not normalized_description:
        return None
    if len(normalized_description) > MAX_UNIVERSE_DESCRIPTION_LENGTH:
        raise UniverseValidationError(
            f"股票池描述不可超過 {MAX_UNIVERSE_DESCRIPTION_LENGTH} 字。"
        )
    return normalized_description


def _ensure_name_available(
    connection: sqlite3.Connection,
    name: str,
    *,
    exclude_universe_id: str | None = None,
) -> None:
    row = connection.execute(
        """
        SELECT id
        FROM research_universes
        WHERE lower(name) = lower(?)
        """,
        (name,),
    ).fetchone()
    if row is None:
        return
    existing_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
    if exclude_universe_id is not None and existing_id == exclude_universe_id:
        return
    raise UniverseAlreadyExistsError("股票池名稱已存在。")


def _parse_required_datetime(value: str, field_name: str) -> datetime:
    try:
        return parse_cache_datetime(value)
    except Exception as exc:
        raise UniverseDataError(f"股票池 {field_name} 時間格式異常。") from exc


def _normalized_now(now: datetime | None) -> datetime:
    value = now or utc_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _generate_universe_id() -> str:
    return str(uuid.uuid4())
