from __future__ import annotations

import sqlite3
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from database import get_cached_historical_financials
from database import get_cached_historical_prices
from database import get_cached_stock
from database import get_historical_price_fetch_state
from database import initialize_live_cache_database
from database import save_historical_financials
from database import save_historical_prices
from database import save_stock
from database_config import DEFAULT_DATABASE_PATH_CONFIG
from database_config import resolve_database_runtime_config
from models import HistoricalFinancialSeries
from models import HistoricalPriceSeries
from models import Stock


class LiveDataStoreError(Exception):
    """Raised when a mutable live store operation is not allowed."""


PRODUCTION_DB_TEST_GUARD_ENV = "AIIR_BLOCK_PRODUCTION_DB_IN_TESTS"
PRODUCTION_DB_TEST_ALLOW_ENV = "AIIR_ALLOW_PRODUCTION_DB_INTEGRATION_TEST"


@dataclass(frozen=True)
class LiveDataStore:
    """Mutable access boundary for current/live cache operations."""

    db_path: Path | str | None = None
    mutable: bool = True

    @property
    def resolved_db_path(self) -> Path:
        if self.db_path is None:
            return resolve_database_runtime_config().active_live_db_path.resolve()
        return Path(self.db_path).resolve()

    def connect_writable(self) -> sqlite3.Connection:
        self._ensure_live_path()
        path = self.resolved_db_path
        path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(path)

    def initialize(self) -> None:
        self._ensure_live_path()
        initialize_live_cache_database(self.resolved_db_path)

    def get_cached_stock(self, symbol: str) -> Stock | None:
        self._ensure_live_path()
        return get_cached_stock(symbol, db_path=self.resolved_db_path)

    def save_stock(self, stock: Stock, *, fetched_at: datetime | None = None) -> None:
        self._ensure_live_path()
        save_stock(stock, db_path=self.resolved_db_path, fetched_at=fetched_at)

    def get_cached_historical_prices(self, *args, **kwargs) -> HistoricalPriceSeries | None:
        self._ensure_live_path()
        kwargs["db_path"] = self.resolved_db_path
        return get_cached_historical_prices(*args, **kwargs)

    def save_historical_prices(
        self,
        series: HistoricalPriceSeries,
        *,
        fetched_at: datetime | None = None,
        full_history_fetched: bool = False,
    ) -> None:
        self._ensure_live_path()
        save_historical_prices(
            series,
            db_path=self.resolved_db_path,
            fetched_at=fetched_at,
            full_history_fetched=full_history_fetched,
        )

    def get_historical_price_fetch_state(self, symbol: str) -> dict | None:
        self._ensure_live_path()
        return get_historical_price_fetch_state(symbol, db_path=self.resolved_db_path)

    def get_cached_historical_financials(
        self,
        symbol: str,
        *,
        include_expired: bool = False,
    ) -> HistoricalFinancialSeries | None:
        self._ensure_live_path()
        return get_cached_historical_financials(
            symbol,
            db_path=self.resolved_db_path,
            include_expired=include_expired,
        )

    def save_historical_financials(
        self,
        series: HistoricalFinancialSeries,
        *,
        fetched_at: datetime | None = None,
    ) -> None:
        self._ensure_live_path()
        save_historical_financials(series, db_path=self.resolved_db_path, fetched_at=fetched_at)

    def _ensure_live_path(self) -> None:
        if not self.mutable:
            raise LiveDataStoreError("LiveDataStore must be mutable for write-capable operations.")
        production_path = DEFAULT_DATABASE_PATH_CONFIG.legacy_db_path.resolve()
        if (
            os.environ.get(PRODUCTION_DB_TEST_GUARD_ENV) == "1"
            and os.environ.get(PRODUCTION_DB_TEST_ALLOW_ENV) != "1"
            and self.resolved_db_path == production_path
        ):
            raise LiveDataStoreError(
                "Test environment cannot use production data/stocks.db through LiveDataStore; "
                "inject a temp LiveDataStore or opt in with explicit integration-test permission."
            )
        research_path = DEFAULT_DATABASE_PATH_CONFIG.research_db_path.resolve()
        research_root = research_path.parent
        if (
            self.resolved_db_path == research_path
            or research_path in self.resolved_db_path.parents
            or self.resolved_db_path.parent == research_root
            or research_root in self.resolved_db_path.parents
        ):
            raise LiveDataStoreError("LiveDataStore cannot target a released research snapshot path.")
