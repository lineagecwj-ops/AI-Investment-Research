"""Immutable, source-linked Catalyst event contracts.

These models deliberately represent factual event evidence only. They do not
contain impact, ranking, recommendation, or prediction semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from enum import StrEnum

from external_source import CompanyAssociationStatus
from external_source import SourceTemporalEvidence
from external_source import SourceTier


CATALYST_EVENT_ARTIFACT_VERSION = "CATALYST_EVENT_V1"
MAX_CANDIDATE_ANCHOR_LENGTH = 360
MAX_EVENT_FACT_LENGTH = 360


class CatalystEventError(ValueError):
    """Raised when a source-linked Catalyst event contract is malformed."""


class CatalystEventType(StrEnum):
    EARNINGS_RESULT = "EARNINGS_RESULT"
    REVENUE_UPDATE = "REVENUE_UPDATE"
    MANAGEMENT_GOVERNANCE = "MANAGEMENT_GOVERNANCE"
    CAPEX_CAPACITY = "CAPEX_CAPACITY"
    DIVIDEND_CAPITAL_RETURN = "DIVIDEND_CAPITAL_RETURN"
    OTHER = "OTHER"


class CandidateStatus(StrEnum):
    EVENT_LIKE = "EVENT_LIKE"
    BACKGROUND_ONLY = "BACKGROUND_ONLY"


class ExtractionBasis(StrEnum):
    STRUCTURED_DATE_BLOCK = "STRUCTURED_DATE_BLOCK"
    EXACT_DATE_SPAN = "EXACT_DATE_SPAN"
    TITLE_OR_EXCERPT_FALLBACK = "TITLE_OR_EXCERPT_FALLBACK"


class EventTemporalStatus(StrEnum):
    TIME_CONFIRMED = "TIME_CONFIRMED"
    TIME_PARTIAL = "TIME_PARTIAL"
    TIME_UNKNOWN = "TIME_UNKNOWN"


class EventValidationStatus(StrEnum):
    VALIDATED = "VALIDATED"
    PARTIALLY_VALIDATED = "PARTIALLY_VALIDATED"
    BACKGROUND_ONLY = "BACKGROUND_ONLY"
    REJECTED = "REJECTED"


class EventConflictStatus(StrEnum):
    NONE = "NONE"
    SOURCE_DATE = "SOURCE_DATE"
    FACT = "FACT"
    IDENTITY = "IDENTITY"


@dataclass(frozen=True)
class EventCandidate:
    """A bounded, source-local span that may describe a factual event."""

    candidate_id: str
    source_id: str
    target_symbol: str
    target_company_name: str
    candidate_anchor: str
    candidate_start: int
    candidate_end: int
    candidate_type: CatalystEventType
    temporal_evidence: tuple[SourceTemporalEvidence, ...]
    company_association_status: CompanyAssociationStatus
    source_tier: SourceTier
    candidate_status: CandidateStatus
    extraction_basis: ExtractionBasis
    candidate_key: str

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.source_id:
            raise CatalystEventError("EventCandidate requires candidate_id and source_id.")
        if not self.target_symbol or not self.target_company_name:
            raise CatalystEventError("EventCandidate requires target identity.")
        if not self.candidate_anchor or len(self.candidate_anchor) > MAX_CANDIDATE_ANCHOR_LENGTH:
            raise CatalystEventError("EventCandidate anchor must be non-empty and bounded.")
        if self.candidate_start < 0 or self.candidate_end <= self.candidate_start:
            raise CatalystEventError("EventCandidate offsets must be a non-empty source-local span.")
        if not self.candidate_key:
            raise CatalystEventError("EventCandidate requires candidate_key.")


@dataclass(frozen=True)
class ValidatedCatalystEvent:
    """A deterministic event cluster whose factual state remains explicit."""

    event_id: str
    target_symbol: str
    target_company_name: str
    event_type: CatalystEventType
    event_fact: str
    event_temporal_evidence: SourceTemporalEvidence | None
    event_temporal_status: EventTemporalStatus
    source_ids: tuple[str, ...]
    primary_source_id: str | None
    support_count: int
    event_key: str
    candidate_ids: tuple[str, ...]
    company_association_status: CompanyAssociationStatus
    validation_status: EventValidationStatus
    conflict_status: EventConflictStatus
    artifact_version: str = CATALYST_EVENT_ARTIFACT_VERSION

    def __post_init__(self) -> None:
        if not self.event_id or not self.target_symbol or not self.target_company_name:
            raise CatalystEventError("ValidatedCatalystEvent requires identity fields.")
        if not self.event_fact or len(self.event_fact) > MAX_EVENT_FACT_LENGTH:
            raise CatalystEventError("Event fact must be non-empty and bounded.")
        if not self.source_ids or tuple(sorted(set(self.source_ids))) != self.source_ids:
            raise CatalystEventError("Event source_ids must be non-empty, unique, and sorted.")
        if self.primary_source_id is not None and self.primary_source_id not in self.source_ids:
            raise CatalystEventError("primary_source_id must reference source_ids.")
        if self.support_count != len(self.source_ids):
            raise CatalystEventError("support_count must equal the source_ids count.")
        if not self.event_key or not self.candidate_ids:
            raise CatalystEventError("ValidatedCatalystEvent requires event and candidate identity.")
        if self.validation_status is EventValidationStatus.VALIDATED:
            if self.event_temporal_evidence is None or self.event_temporal_status is not EventTemporalStatus.TIME_CONFIRMED:
                raise CatalystEventError("Validated event requires confirmed temporal evidence.")
            if self.company_association_status not in {
                CompanyAssociationStatus.DIRECT_EXACT,
                CompanyAssociationStatus.DIRECT_SUPPORTED,
            }:
                raise CatalystEventError("Validated event requires direct target-company association.")
            if self.conflict_status is not EventConflictStatus.NONE:
                raise CatalystEventError("Validated event cannot retain an unresolved conflict.")

    @property
    def event_temporal_value(self) -> date | datetime | None:
        return self.event_temporal_evidence.value if self.event_temporal_evidence else None
