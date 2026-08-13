from __future__ import annotations

import json
import sqlite3
import hashlib
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path

from database import historical_price_bar_from_row
from database import parse_cache_datetime
from database_config import DEFAULT_DATABASE_PATH_CONFIG
from database_config import DEFAULT_RESEARCH_DB_SHA256
from database_config import DEFAULT_RESEARCH_MATERIALIZATION_VERSION
from database_config import PROJECT_ROOT
from database_config import resolve_database_runtime_config
from models import HistoricalPriceSeries


DEFAULT_RESEARCH_SNAPSHOT_ID = "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1"
DEFAULT_RESEARCH_SNAPSHOT_VERSION = "v1"
DEFAULT_RESEARCH_SEMANTIC_CHECKSUM = "a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91"
DEFAULT_RESEARCH_MANIFEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "manifests"
    / f"{DEFAULT_RESEARCH_SNAPSHOT_ID}_materialization_{DEFAULT_RESEARCH_MATERIALIZATION_VERSION}_manifest.json"
)


class ResearchDataStoreError(Exception):
    """Raised when a research snapshot reader cannot be used safely."""


@dataclass(frozen=True)
class ResearchDataStore:
    """Read-only access boundary for released research snapshot readers."""

    db_path: Path | str | None = None
    research_snapshot_id: str | None = None
    manifest_path: Path | str | None = None
    research_snapshot_version: str | None = None
    expected_materialization_version: str | None = None
    expected_semantic_checksum: str | None = None
    expected_db_sha256: str | None = None
    verify_default_runtime: bool = True

    def __post_init__(self) -> None:
        if (
            self.verify_default_runtime
            and self.db_path is None
            and self.research_snapshot_id is None
            and self.manifest_path is None
        ):
            self.verify_runtime_identity()

    @property
    def resolved_db_path(self) -> Path:
        if self.db_path is None:
            return resolve_database_runtime_config().active_research_db_path.resolve()
        return Path(self.db_path).resolve()

    @property
    def resolved_manifest_path(self) -> Path:
        if self.manifest_path is None:
            return resolve_database_runtime_config().manifest_path.resolve()
        return Path(self.manifest_path).resolve()

    @property
    def resolved_research_snapshot_id(self) -> str:
        return self.research_snapshot_id or DEFAULT_DATABASE_PATH_CONFIG.research_snapshot_id

    @property
    def resolved_research_snapshot_version(self) -> str:
        return self.research_snapshot_version or DEFAULT_DATABASE_PATH_CONFIG.research_snapshot_version

    @property
    def resolved_materialization_version(self) -> str:
        return self.expected_materialization_version or DEFAULT_DATABASE_PATH_CONFIG.research_materialization_version

    @property
    def resolved_semantic_checksum(self) -> str:
        return self.expected_semantic_checksum or DEFAULT_DATABASE_PATH_CONFIG.research_semantic_checksum

    @property
    def resolved_db_sha256(self) -> str:
        return self.expected_db_sha256 or DEFAULT_DATABASE_PATH_CONFIG.research_db_sha256

    def connect_read_only(self) -> sqlite3.Connection:
        live_path = DEFAULT_DATABASE_PATH_CONFIG.live_db_path.resolve()
        legacy_path = DEFAULT_DATABASE_PATH_CONFIG.legacy_db_path.resolve()
        if self.resolved_db_path == live_path or live_path in self.resolved_db_path.parents:
            raise ResearchDataStoreError("ResearchDataStore cannot target the mutable Live Store path.")
        if self.resolved_db_path == legacy_path:
            raise ResearchDataStoreError("ResearchDataStore cannot target the mutable Legacy Store path.")
        connection = sqlite3.connect(self.resolved_db_path.as_uri() + "?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        return connection

    def verify_manifest_reference(self) -> dict:
        manifest_path = self.resolved_manifest_path
        if not manifest_path.exists():
            raise ResearchDataStoreError(f"Research snapshot manifest not found: {manifest_path}")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        identity = payload.get("identity", {})
        snapshot_id = identity.get("snapshot_id")
        if snapshot_id != self.resolved_research_snapshot_id:
            raise ResearchDataStoreError(
                f"Research snapshot manifest mismatch: expected {self.resolved_research_snapshot_id}, got {snapshot_id}."
            )
        snapshot_version = identity.get("snapshot_version")
        if snapshot_version != self.resolved_research_snapshot_version:
            raise ResearchDataStoreError(
                f"Research snapshot version mismatch: expected {self.resolved_research_snapshot_version}, got {snapshot_version}."
            )
        return payload

    def verify_runtime_identity(self, *, verify_db_sha: bool = True) -> dict:
        payload = self.verify_manifest_reference()
        identity = payload.get("identity", {})
        materialization_version = identity.get("materialization_version")
        if materialization_version != self.resolved_materialization_version:
            raise ResearchDataStoreError(
                "Research materialization version mismatch: "
                f"expected {self.resolved_materialization_version}, got {materialization_version}."
            )

        semantic = payload.get("semantic_checksum", {})
        expected_semantic = self.resolved_semantic_checksum
        for field in ("expected", "materialized", "recomputed"):
            if semantic.get(field) != expected_semantic:
                raise ResearchDataStoreError(
                    f"Research semantic checksum mismatch in manifest field {field}: "
                    f"expected {expected_semantic}, got {semantic.get(field)}."
                )

        database = payload.get("database", {})
        expected_db_sha = self.resolved_db_sha256
        manifest_db_sha = database.get("sha256")
        if manifest_db_sha != expected_db_sha:
            raise ResearchDataStoreError(
                f"Research DB SHA mismatch in manifest: expected {expected_db_sha}, got {manifest_db_sha}."
            )

        metadata = self._load_snapshot_metadata()
        if metadata.get("snapshot_id") != self.resolved_research_snapshot_id:
            raise ResearchDataStoreError("Research DB metadata snapshot_id mismatch.")
        if metadata.get("snapshot_version") != self.resolved_research_snapshot_version:
            raise ResearchDataStoreError("Research DB metadata snapshot_version mismatch.")
        if metadata.get("materialization_version") != self.resolved_materialization_version:
            raise ResearchDataStoreError("Research DB metadata materialization_version mismatch.")
        if metadata.get("semantic_checksum") != expected_semantic:
            raise ResearchDataStoreError("Research DB metadata semantic_checksum mismatch.")

        actual_db_sha = None
        if verify_db_sha:
            actual_db_sha = hashlib.sha256(self.resolved_db_path.read_bytes()).hexdigest()
            if actual_db_sha != expected_db_sha:
                raise ResearchDataStoreError(
                    f"Research DB SHA mismatch on disk: expected {expected_db_sha}, got {actual_db_sha}."
                )

        return {
            "active_db_mode": resolve_database_runtime_config().active_db_mode,
            "active_research_db_path": str(self.resolved_db_path),
            "active_research_snapshot_id": self.resolved_research_snapshot_id,
            "active_research_snapshot_version": self.resolved_research_snapshot_version,
            "active_research_materialization_version": self.resolved_materialization_version,
            "active_research_manifest_path": str(self.resolved_manifest_path),
            "active_research_db_sha": actual_db_sha or expected_db_sha,
            "active_research_semantic_checksum": expected_semantic,
        }

    def _load_snapshot_metadata(self) -> dict[str, str]:
        connection = self.connect_read_only()
        try:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT key, value FROM snapshot_metadata").fetchall()
        finally:
            connection.close()
        return {row["key"]: row["value"] for row in rows}

    def load_historical_price_series(self, symbol: str) -> HistoricalPriceSeries:
        connection = self.connect_read_only()
        try:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT symbol, trading_date, open, high, low, close, adjusted_close,
                       volume, dividends, stock_splits, currency, fetched_at
                FROM historical_prices
                WHERE symbol = ?
                ORDER BY trading_date ASC
                """,
                (symbol,),
            ).fetchall()
        finally:
            connection.close()
        if not rows:
            raise ResearchDataStoreError(f"No historical prices found for {symbol}.")
        fetched_at_values = tuple(parse_cache_datetime(row["fetched_at"]) for row in rows if row["fetched_at"])
        fetched_at = min(fetched_at_values) if fetched_at_values else datetime.now(UTC)
        currency = next((row["currency"] for row in rows if row["currency"]), None)
        return HistoricalPriceSeries(
            symbol=symbol,
            currency=currency,
            bars=tuple(historical_price_bar_from_row(row) for row in rows),
            fetched_at=fetched_at,
            is_stale=False,
        )

    def materialized_twse_common_stock_symbols(self) -> tuple[str, ...]:
        connection = self.connect_read_only()
        try:
            rows = connection.execute(
                """
                SELECT DISTINCT symbol
                FROM historical_prices
                WHERE symbol GLOB '[0-9][0-9][0-9][0-9].TW'
                  AND symbol != '0050.TW'
                ORDER BY symbol ASC
                """
            ).fetchall()
        finally:
            connection.close()
        return tuple(row[0] for row in rows)
