from dataclasses import dataclass
from datetime import date
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from portfolio_state.generation_identity import canonical_sha256
from portfolio_state.position_state import PortfolioPositionState
from portfolio_state.validation import PortfolioSnapshotChecksumMismatchError
from portfolio_state.validation import PortfolioStateValidationError


PORTFOLIO_SNAPSHOT_SCHEMA_VERSION = "1"


class PortfolioSnapshotError(PortfolioStateValidationError):
    """Raised when portfolio snapshot contract validation fails."""


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Frozen immutable portfolio state snapshot."""

    snapshot_id: str
    portfolio_id: str
    as_of_date: date
    valuation_date: date
    positions: tuple[PortfolioPositionState, ...]
    created_at: datetime
    checksum: str | None = None
    schema_version: str = PORTFOLIO_SNAPSHOT_SCHEMA_VERSION
    source_lineage: Mapping[str, str] | None = None

    def __post_init__(self):
        required = {
            "snapshot_id": self.snapshot_id,
            "portfolio_id": self.portfolio_id,
            "schema_version": self.schema_version,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise PortfolioSnapshotError(f"PortfolioSnapshot missing required fields: {', '.join(missing)}")
        if self.schema_version != PORTFOLIO_SNAPSHOT_SCHEMA_VERSION:
            raise PortfolioSnapshotError(f"Unsupported PortfolioSnapshot schema_version: {self.schema_version}.")
        if not isinstance(self.as_of_date, date):
            raise PortfolioSnapshotError("PortfolioSnapshot as_of_date must be a date.")
        if not isinstance(self.valuation_date, date):
            raise PortfolioSnapshotError("PortfolioSnapshot valuation_date must be a date.")
        if not isinstance(self.created_at, datetime):
            raise PortfolioSnapshotError("PortfolioSnapshot created_at must be a datetime.")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise PortfolioSnapshotError("PortfolioSnapshot created_at must be timezone-aware.")
        if not isinstance(self.positions, tuple):
            raise PortfolioSnapshotError("PortfolioSnapshot positions must be a tuple.")
        if not self.source_lineage:
            raise PortfolioSnapshotError("PortfolioSnapshot requires source_lineage.")

        ordered_positions = tuple(sorted(self.positions, key=lambda item: (item.position_id, item.symbol)))
        self._validate_positions(ordered_positions)
        source_lineage = MappingProxyType({str(key): str(self.source_lineage[key]) for key in sorted(self.source_lineage)})
        object.__setattr__(self, "positions", ordered_positions)
        object.__setattr__(self, "source_lineage", source_lineage)

        expected = self.compute_checksum()
        if self.checksum is not None and self.checksum != expected:
            raise PortfolioSnapshotChecksumMismatchError(
                f"PortfolioSnapshot checksum mismatch: expected {expected}, got {self.checksum}."
            )
        object.__setattr__(self, "checksum", expected)

    @property
    def active_position_ids(self) -> tuple[str, ...]:
        return tuple(position.position_id for position in self.positions if position.position_status.value == "ACTIVE")

    @property
    def identity_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "portfolio_id": self.portfolio_id,
            "as_of_date": self.as_of_date,
            "valuation_date": self.valuation_date,
            "positions": tuple(position.identity for position in self.positions),
            "created_at": self.created_at,
            "source_lineage": dict(self.source_lineage or {}),
        }

    def compute_checksum(self) -> str:
        return canonical_sha256(self.identity_payload)

    def _validate_positions(self, positions: tuple[PortfolioPositionState, ...]) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for position in positions:
            if not isinstance(position, PortfolioPositionState):
                raise PortfolioSnapshotError("PortfolioSnapshot positions must contain PortfolioPositionState.")
            if position.portfolio_id != self.portfolio_id:
                raise PortfolioSnapshotError("PortfolioSnapshot position portfolio_id mismatch.")
            if position.position_id in seen:
                duplicates.add(position.position_id)
            seen.add(position.position_id)
        if duplicates:
            raise PortfolioSnapshotError(f"Duplicate portfolio position_id: {', '.join(sorted(duplicates))}")
