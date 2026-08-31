"""Immutable, bounded impact-hypothesis contracts for validated Catalyst events."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


CATALYST_IMPACT_HYPOTHESIS_VERSION = "CATALYST_IMPACT_HYPOTHESIS_V1"
MAX_IMPACT_TEXT_LENGTH = 420


class CatalystImpactError(ValueError):
    """Raised when a bounded Catalyst impact hypothesis is malformed."""


class ImpactChannel(StrEnum):
    REVENUE = "REVENUE"
    MARGIN_COST = "MARGIN_COST"
    CAPACITY = "CAPACITY"
    CAPITAL_ALLOCATION = "CAPITAL_ALLOCATION"
    GOVERNANCE = "GOVERNANCE"
    OTHER = "OTHER"


class HypothesisStatus(StrEnum):
    PLAUSIBLE = "PLAUSIBLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTRADICTED = "CONTRADICTED"
    SUPPORTED = "SUPPORTED"


@dataclass(frozen=True)
class ImpactHypothesis:
    """Program-assembled interpretation that remains separate from event facts."""

    hypothesis_id: str
    event_id: str
    target_symbol: str
    target_company_name: str
    impact_channel: ImpactChannel
    hypothesis_text: str
    why_it_matters_text: str
    hypothesis_status: HypothesisStatus
    supporting_evidence_refs: tuple[str, ...]
    contradictory_evidence_refs: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    contradiction_or_limit_text: str
    uncertainty_text: str
    next_checks: tuple[str, ...]
    version: str = CATALYST_IMPACT_HYPOTHESIS_VERSION

    def __post_init__(self) -> None:
        for field_name in ("hypothesis_id", "event_id", "target_symbol", "target_company_name", "version"):
            _require_text(getattr(self, field_name), field_name)
        for field_name in (
            "hypothesis_text",
            "why_it_matters_text",
            "contradiction_or_limit_text",
            "uncertainty_text",
        ):
            _require_bounded_text(getattr(self, field_name), field_name)
        if not isinstance(self.impact_channel, ImpactChannel):
            raise CatalystImpactError("impact_channel must be an ImpactChannel.")
        if not isinstance(self.hypothesis_status, HypothesisStatus):
            raise CatalystImpactError("hypothesis_status must be a HypothesisStatus.")
        if self.version != CATALYST_IMPACT_HYPOTHESIS_VERSION:
            raise CatalystImpactError("ImpactHypothesis must use the V1 contract version.")
        _require_ordered_refs(self.supporting_evidence_refs, "supporting_evidence_refs")
        _require_ordered_refs(self.contradictory_evidence_refs, "contradictory_evidence_refs")
        _require_ordered_refs(self.missing_evidence, "missing_evidence")
        if set(self.supporting_evidence_refs) & set(self.contradictory_evidence_refs):
            raise CatalystImpactError("Supporting and contradictory evidence must remain distinct.")
        if not self.next_checks or len(self.next_checks) > 1:
            raise CatalystImpactError("V1 requires exactly one bounded next check.")
        for item in self.next_checks:
            _require_bounded_text(item, "next_checks")
        if self.hypothesis_status is HypothesisStatus.SUPPORTED and not self.supporting_evidence_refs:
            raise CatalystImpactError("SUPPORTED requires independent supporting evidence.")
        if self.hypothesis_status is HypothesisStatus.CONTRADICTED and not self.contradictory_evidence_refs:
            raise CatalystImpactError("CONTRADICTED requires approved contradictory evidence.")


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CatalystImpactError(f"{field_name} must be non-empty text.")


def _require_bounded_text(value: object, field_name: str) -> None:
    _require_text(value, field_name)
    if len(value.strip()) > MAX_IMPACT_TEXT_LENGTH:
        raise CatalystImpactError(f"{field_name} exceeds the V1 bounded-text limit.")


def _require_ordered_refs(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple) or any(not isinstance(item, str) or not item for item in values):
        raise CatalystImpactError(f"{field_name} must be a tuple of non-empty evidence references.")
    if tuple(sorted(set(values))) != values:
        raise CatalystImpactError(f"{field_name} must be unique and deterministically ordered.")
