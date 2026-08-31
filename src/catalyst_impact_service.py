"""Bounded, grounded impact-hypothesis generation for validated Catalyst events."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC
from datetime import datetime
import hashlib
import json
import re
from typing import Any

from ai_analyst_shortlist import validate_analyst_numeric_free_narrative
from ai_research_service import AIGroundingError
from ai_research_service import AIResponseMetadata
from ai_research_service import AIResearchError
from ai_research_service import GroundedFinding
from ai_research_service import GroundedResearchAnswer
from ai_research_service import generate_grounded_research_answer
from ai_research_service import validate_forbidden_output_policy
from ai_research_service import validate_non_percentage_numeric_claims
from ai_research_service import validate_numeric_percentage_claims
from catalyst_event import EventValidationStatus
from catalyst_event import ValidatedCatalystEvent
from catalyst_impact import CATALYST_IMPACT_HYPOTHESIS_VERSION
from catalyst_impact import CatalystImpactError
from catalyst_impact import HypothesisStatus
from catalyst_impact import ImpactChannel
from catalyst_impact import ImpactHypothesis
from research_context import EvidenceItem
from research_context import MissingDataItem
from research_context_selector import SelectedResearchContext


MAX_AI_CALLS_PER_EVENT = 1
MAX_AI_CALLS_PER_COMPANY_RUN = 2
AUTO_RETRY_COUNT = 0
REPAIR_CALL_COUNT = 0
_EVENT_EVIDENCE_ID_PREFIX = "event:"
_BACKGROUND_EVIDENCE_ID_PREFIX = "background:"
_SUPPORTING_EVIDENCE_ID_PREFIX = "supporting:"
_CONTRADICTORY_EVIDENCE_ID_PREFIX = "contradictory:"


class CatalystImpactServiceError(CatalystImpactError):
    """Raised when Catalyst impact generation cannot safely proceed."""


class DuplicateEventContextConflictError(CatalystImpactServiceError):
    """Raised before provider use when one event has materially different inputs."""


@dataclass(frozen=True)
class ApprovedSupportingEvidence:
    """V1J-owned provenance needed to prove support is independent of one event."""

    evidence_ref: str
    provenance_source_ids: tuple[str, ...]
    provenance_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_ordered_refs((self.evidence_ref,), "evidence_ref")
        _require_ordered_refs(self.provenance_source_ids, "provenance_source_ids")
        _require_ordered_refs(self.provenance_event_ids, "provenance_event_ids")


@dataclass(frozen=True)
class EventImpactContext:
    """Program-owned, role-separated input to one event-scoped AI interpretation."""

    event: ValidatedCatalystEvent
    company_background: tuple[EvidenceItem, ...]
    supporting_evidence: tuple[EvidenceItem, ...]
    supporting_evidence_provenance: tuple[ApprovedSupportingEvidence, ...]
    contradictory_evidence: tuple[EvidenceItem, ...]
    missing_evidence: tuple[MissingDataItem, ...]
    selected_context: SelectedResearchContext

    @property
    def supporting_evidence_refs(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.supporting_evidence)

    @property
    def contradictory_evidence_refs(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.contradictory_evidence)

    @property
    def missing_evidence_refs(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.missing_evidence)


@dataclass(frozen=True)
class _ImpactAIOutput:
    impact_channel: ImpactChannel
    hypothesis_status: HypothesisStatus
    impact_hypothesis: str
    why_it_matters: str
    contradiction_or_limit: str
    uncertainty: str
    next_check: str


IMPACT_OUTPUT_FORMAT = {
    "type": "json_schema",
    "name": "catalyst_impact_hypothesis_v1",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "impact_channel",
            "hypothesis_status",
            "impact_hypothesis",
            "why_it_matters",
            "contradiction_or_limit",
            "uncertainty",
            "next_check",
        ],
        "properties": {
            "impact_channel": {"type": "string", "enum": [item.value for item in ImpactChannel]},
            "hypothesis_status": {"type": "string", "enum": [item.value for item in HypothesisStatus]},
            "impact_hypothesis": {"type": "string", "maxLength": 420},
            "why_it_matters": {"type": "string", "maxLength": 420},
            "contradiction_or_limit": {"type": "string", "maxLength": 420},
            "uncertainty": {"type": "string", "maxLength": 420},
            "next_check": {"type": "string", "maxLength": 420},
        },
    },
}


def build_event_impact_context(
    *,
    event: ValidatedCatalystEvent,
    selected_context: SelectedResearchContext,
    supporting_evidence_refs: tuple[str, ...] = (),
    supporting_evidence_provenance: tuple[ApprovedSupportingEvidence, ...] = (),
    contradictory_evidence_refs: tuple[str, ...] = (),
    missing_evidence_refs: tuple[str, ...] = (),
) -> EventImpactContext:
    """Separate event fact, background, explicit support, contradiction and gaps."""
    if event.validation_status is not EventValidationStatus.VALIDATED:
        raise CatalystImpactServiceError("Only VALIDATED Catalyst events may be primary impact inputs.")
    if selected_context.symbol != event.target_symbol or selected_context.display_name != event.target_company_name:
        raise CatalystImpactServiceError("Selected research context must match the validated event target.")
    supporting_evidence_refs = _canonical_refs(
        supporting_evidence_refs, "supporting_evidence_refs",
    )
    contradictory_evidence_refs = _canonical_refs(
        contradictory_evidence_refs, "contradictory_evidence_refs",
    )
    missing_evidence_refs = _canonical_refs(missing_evidence_refs, "missing_evidence_refs")
    supporting_evidence_provenance = _canonical_supporting_provenance(
        supporting_evidence_provenance,
    )
    _require_supporting_provenance(supporting_evidence_refs, supporting_evidence_provenance)
    if set(supporting_evidence_refs) & set(contradictory_evidence_refs):
        raise CatalystImpactServiceError("Supporting and contradictory evidence must remain distinct.")

    evidence_by_id = {item.id: item for item in selected_context.selected_evidence}
    missing_by_id = {item.id: item for item in selected_context.selected_missing_data}
    _require_known_refs(supporting_evidence_refs, evidence_by_id, "supporting")
    _require_known_refs(contradictory_evidence_refs, evidence_by_id, "contradictory")
    _require_known_refs(missing_evidence_refs, missing_by_id, "missing")
    provenance_by_ref = {item.evidence_ref: item for item in supporting_evidence_provenance}
    for item_id in supporting_evidence_refs:
        if not _is_independent_supporting_evidence(
            evidence_by_id[item_id], event, provenance_by_ref[item_id],
        ):
            raise CatalystImpactServiceError(
                "Supporting evidence cannot prove independence from the Catalyst event."
            )

    approved = set(supporting_evidence_refs) | set(contradictory_evidence_refs)
    background = tuple(item for item in selected_context.selected_evidence if item.id not in approved)
    return EventImpactContext(
        event=event,
        company_background=background,
        supporting_evidence=tuple(evidence_by_id[item_id] for item_id in supporting_evidence_refs),
        supporting_evidence_provenance=supporting_evidence_provenance,
        contradictory_evidence=tuple(evidence_by_id[item_id] for item_id in contradictory_evidence_refs),
        missing_evidence=tuple(missing_by_id[item_id] for item_id in missing_evidence_refs),
        selected_context=_build_event_scoped_selected_context(event, selected_context, background, supporting_evidence_refs, contradictory_evidence_refs, missing_evidence_refs),
    )


def build_event_impact_payload(context: EventImpactContext) -> dict[str, Any]:
    """Expose the program-owned role separation used by the bounded request."""
    return {
        "CATALYST_EVENT_FACT": {
            "event_id": context.event.event_id,
            "target_symbol": context.event.target_symbol,
            "target_company_name": context.event.target_company_name,
            "event_type": context.event.event_type.value,
            "event_fact": context.event.event_fact,
            "event_temporal_value": context.event.event_temporal_value.isoformat(),
        },
        "COMPANY_BACKGROUND": [item.id for item in context.company_background],
        "SUPPORTING_EVIDENCE": list(context.supporting_evidence_refs),
        "CONTRADICTORY_EVIDENCE": list(context.contradictory_evidence_refs),
        "MISSING_EVIDENCE": list(context.missing_evidence_refs),
    }


def generate_event_impact_hypothesis(
    context: EventImpactContext,
    *,
    client: Any | None = None,
    config: Any | None = None,
    generated_at: datetime | None = None,
) -> ImpactHypothesis:
    """Make one bounded call through the released grounded-answer transport."""
    if context.event.validation_status is not EventValidationStatus.VALIDATED:
        raise CatalystImpactServiceError("Only VALIDATED Catalyst events may be primary impact inputs.")
    _validate_event_impact_context(context)
    ai_output = generate_grounded_research_answer(
        question=_impact_question(context),
        selected_context=context.selected_context,
        client=client,
        config=config,
        generated_at=generated_at or datetime.now(UTC),
        response_format=IMPACT_OUTPUT_FORMAT,
        answer_builder=_build_impact_ai_output,
        answer_validator=lambda output, selected: _validate_impact_ai_output(output, context, selected),
    )
    return _assemble_impact_hypothesis(context, ai_output)


def generate_company_event_impact_hypotheses(
    contexts: tuple[EventImpactContext, ...],
    *,
    client: Any | None = None,
    config: Any | None = None,
    generated_at: datetime | None = None,
) -> tuple[ImpactHypothesis, ...]:
    """Process the first two deterministic validated events without retry or repair calls."""
    ordered = _canonical_company_contexts(contexts)
    if ordered and any(item.event.target_symbol != ordered[0].event.target_symbol for item in ordered):
        raise CatalystImpactServiceError("A company run may contain events for one target only.")
    results = []
    for context in ordered[:MAX_AI_CALLS_PER_COMPANY_RUN]:
        try:
            results.append(generate_event_impact_hypothesis(
                context, client=client, config=config, generated_at=generated_at,
            ))
        except (AIResearchError, CatalystImpactServiceError):
            continue
    return tuple(results)


def build_impact_hypothesis_id(event_id: str, *, version: str = CATALYST_IMPACT_HYPOTHESIS_VERSION) -> str:
    if not isinstance(event_id, str) or not event_id:
        raise CatalystImpactServiceError("event_id is required for deterministic hypothesis identity.")
    digest = hashlib.sha256(f"{version}:{event_id}".encode("utf-8")).hexdigest()[:20]
    return f"catalyst_impact_{digest}"


def _build_event_scoped_selected_context(
    event: ValidatedCatalystEvent,
    selected: SelectedResearchContext,
    background: tuple[EvidenceItem, ...],
    supporting_refs: tuple[str, ...],
    contradictory_refs: tuple[str, ...],
    missing_refs: tuple[str, ...],
) -> SelectedResearchContext:
    evidence_by_id = {item.id: item for item in selected.selected_evidence}
    role_evidence = [_event_fact_evidence(event)]
    role_evidence.extend(_role_evidence(_BACKGROUND_EVIDENCE_ID_PREFIX, evidence_by_id[item.id]) for item in background)
    role_evidence.extend(_role_evidence(_SUPPORTING_EVIDENCE_ID_PREFIX, evidence_by_id[item_id]) for item_id in supporting_refs)
    role_evidence.extend(_role_evidence(_CONTRADICTORY_EVIDENCE_ID_PREFIX, evidence_by_id[item_id]) for item_id in contradictory_refs)
    missing_by_id = {item.id: item for item in selected.selected_missing_data}
    role_missing = [replace(missing_by_id[item_id], id=f"missing:{item_id}") for item_id in missing_refs]
    return replace(
        selected,
        selected_evidence=sorted(role_evidence, key=lambda item: item.id),
        selected_observation_links=[],
        selected_observations=[],
        selected_missing_data=role_missing,
        selected_limitations=[],
        selection_notes=["event-scoped Catalyst impact context"],
        source_evidence_count=len(role_evidence),
    )


def _event_fact_evidence(event: ValidatedCatalystEvent) -> EvidenceItem:
    return EvidenceItem(
        id=f"{_EVENT_EVIDENCE_ID_PREFIX}{event.event_id}",
        category="CATALYST_EVENT_FACT",
        metric="CATALYST_EVENT_FACT",
        value=event.event_fact,
        unit=None,
        currency=None,
        period_end=event.event_temporal_value if hasattr(event.event_temporal_value, "year") else None,
        period_year=None,
        source="program-owned ValidatedCatalystEvent",
        source_type="catalyst_event",
        note=event.event_type.value,
    )


def _role_evidence(prefix: str, item: EvidenceItem) -> EvidenceItem:
    return replace(item, id=f"{prefix}{item.id}")


def _impact_question(context: EventImpactContext) -> str:
    return (
        "根據角色分隔的 Catalyst event context，僅對已驗證事件提出有限的商業影響假說。"
        "事件事實、公司背景、支持證據、反證與缺失資料不可互相混用。"
        "不要改寫事件事實、不要產生證據引用或數字、不要做投資建議。"
        "只回傳指定 JSON 欄位。"
    )


def _build_impact_ai_output(data: Any, _metadata: Any) -> _ImpactAIOutput:
    expected = {
        "impact_channel", "hypothesis_status", "impact_hypothesis", "why_it_matters",
        "contradiction_or_limit", "uncertainty", "next_check",
    }
    if not isinstance(data, dict) or set(data) != expected:
        raise CatalystImpactServiceError("Impact output must match the strict V1 schema exactly.")
    try:
        return _ImpactAIOutput(
            impact_channel=ImpactChannel(data["impact_channel"]),
            hypothesis_status=HypothesisStatus(data["hypothesis_status"]),
            impact_hypothesis=_bounded_slot(data["impact_hypothesis"], "impact_hypothesis"),
            why_it_matters=_bounded_slot(data["why_it_matters"], "why_it_matters"),
            contradiction_or_limit=_bounded_slot(data["contradiction_or_limit"], "contradiction_or_limit"),
            uncertainty=_bounded_slot(data["uncertainty"], "uncertainty"),
            next_check=_bounded_slot(data["next_check"], "next_check"),
        )
    except (TypeError, ValueError) as exc:
        raise CatalystImpactServiceError("Impact output contains an unsupported enum or malformed slot.") from exc


def _validate_impact_ai_output(
    output: _ImpactAIOutput,
    context: EventImpactContext,
    selected_context: SelectedResearchContext,
) -> None:
    if output.hypothesis_status is HypothesisStatus.SUPPORTED and not context.supporting_evidence_refs:
        raise CatalystImpactServiceError("SUPPORTED requires independent program-approved supporting evidence.")
    if output.hypothesis_status is HypothesisStatus.CONTRADICTED and not context.contradictory_evidence_refs:
        raise CatalystImpactServiceError("CONTRADICTED requires program-approved contradictory evidence.")
    for text in (
        output.impact_hypothesis,
        output.why_it_matters,
        output.contradiction_or_limit,
        output.uncertainty,
        output.next_check,
    ):
        _validate_impact_slot(text, selected_context)


def _assemble_impact_hypothesis(context: EventImpactContext, output: _ImpactAIOutput) -> ImpactHypothesis:
    return ImpactHypothesis(
        hypothesis_id=build_impact_hypothesis_id(context.event.event_id),
        event_id=context.event.event_id,
        target_symbol=context.event.target_symbol,
        target_company_name=context.event.target_company_name,
        impact_channel=output.impact_channel,
        hypothesis_text=output.impact_hypothesis,
        why_it_matters_text=output.why_it_matters,
        hypothesis_status=output.hypothesis_status,
        supporting_evidence_refs=context.supporting_evidence_refs,
        contradictory_evidence_refs=context.contradictory_evidence_refs,
        missing_evidence=context.missing_evidence_refs,
        contradiction_or_limit_text=output.contradiction_or_limit,
        uncertainty_text=output.uncertainty,
        next_checks=(output.next_check,),
    )


def _bounded_slot(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 420:
        raise CatalystImpactServiceError(f"{field_name} must be non-empty bounded text.")
    return value.strip()


def _validate_impact_slot(text: str, selected_context: SelectedResearchContext) -> None:
    """Reuse released numeric and recommendation guards without current/radar routing."""
    if "http://" in text.lower() or "https://" in text.lower():
        raise AIGroundingError("Impact slots cannot create source URLs.")
    lowered = text.lower()
    if re.search(r"(?:source|event|evidence)[ _-]?id\\b", lowered):
        raise AIGroundingError("Impact slots cannot create evidence identifiers.")
    if _has_stock_price_direction(text):
        raise AIGroundingError("Impact slots cannot make stock-price directional calls.")
    finding = GroundedFinding(text, [item.id for item in selected_context.selected_evidence])
    answer = GroundedResearchAnswer(
        symbol=selected_context.symbol,
        question_type=selected_context.question_type.value,
        summary="",
        findings=[finding],
        limitations=[],
        missing_information=[],
        next_steps=[],
        metadata=AIResponseMetadata(
            "program-owned", None, selected_context.generated_at, selected_context.question_type.value,
        ),
    )
    validate_forbidden_output_policy(answer)
    validate_analyst_numeric_free_narrative(answer, selected_context)
    evidence_by_id = {item.id: item for item in selected_context.selected_evidence}
    validate_numeric_percentage_claims(text, finding.evidence_ids, evidence_by_id)
    validate_non_percentage_numeric_claims(text, finding.evidence_ids, evidence_by_id)


def _require_ordered_refs(values: tuple[str, ...], field_name: str) -> None:
    if (
        not isinstance(values, tuple)
        or any(not isinstance(item, str) or not item for item in values)
        or tuple(sorted(set(values))) != values
    ):
        raise CatalystImpactServiceError(f"{field_name} must be unique and deterministically ordered.")


def _require_known_refs(values: tuple[str, ...], known: dict[str, Any], role: str) -> None:
    unknown = [item for item in values if item not in known]
    if unknown:
        raise CatalystImpactServiceError(f"Unknown {role} evidence reference: {unknown[0]}")


def _is_independent_supporting_evidence(
    item: EvidenceItem,
    event: ValidatedCatalystEvent,
    provenance: ApprovedSupportingEvidence,
) -> bool:
    """Require explicit non-event provenance; unknown provenance fails closed."""
    event_provenance = {event.event_id, *event.source_ids}
    if event.primary_source_id is not None:
        event_provenance.add(event.primary_source_id)
    if item.id in event_provenance or item.value == event.event_fact:
        return False
    if event_provenance & set(provenance.provenance_source_ids):
        return False
    if event.event_id in provenance.provenance_event_ids:
        return False
    return not bool(event_provenance & set(item.derived_from))


def _validate_event_impact_context(context: EventImpactContext) -> None:
    """Recheck program-owned role and provenance boundaries at the provider entrypoint."""
    if (
        context.selected_context.symbol != context.event.target_symbol
        or context.selected_context.display_name != context.event.target_company_name
    ):
        raise CatalystImpactServiceError("Selected research context must match the validated event target.")
    _require_supporting_provenance(
        context.supporting_evidence_refs,
        context.supporting_evidence_provenance,
    )
    if set(context.supporting_evidence_refs) & set(context.contradictory_evidence_refs):
        raise CatalystImpactServiceError("Supporting and contradictory evidence must remain distinct.")
    provenance_by_ref = {
        item.evidence_ref: item for item in context.supporting_evidence_provenance
    }
    for item in context.supporting_evidence:
        if not _is_independent_supporting_evidence(
            item,
            context.event,
            provenance_by_ref[item.id],
        ):
            raise CatalystImpactServiceError(
                "Supporting evidence cannot prove independence from the Catalyst event."
            )


def _has_stock_price_direction(text: str) -> bool:
    normalized = text.lower()
    patterns = (
        r"股價\s*(?:將|會|可能|可望|預期)?\s*(?:上漲|下跌)",
        r"(?:stock|share)\s+price\s+(?:will|may|could|is\s+likely\s+to)\s+(?:rise|fall)",
        r"\bshares?\s+(?:will|may|could)\s+(?:rise|fall)\b",
        r"\b(?:bullish|bearish)\s+on\s+(?:the\s+)?stock\b",
    )
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)


def _canonical_company_contexts(contexts: tuple[EventImpactContext, ...]) -> tuple[EventImpactContext, ...]:
    grouped: dict[str, list[EventImpactContext]] = {}
    for context in contexts:
        grouped.setdefault(context.event.event_id, []).append(context)
    canonical = []
    for event_id in sorted(grouped):
        candidates = grouped[event_id]
        fingerprints = {_event_context_fingerprint(item) for item in candidates}
        if len(fingerprints) != 1:
            raise DuplicateEventContextConflictError(
                f"DUPLICATE_EVENT_CONTEXT_CONFLICT: {event_id}"
            )
        canonical.append(candidates[0])
    return tuple(canonical)


def _event_context_fingerprint(context: EventImpactContext) -> str:
    event = context.event
    payload = {
        "event": {
            "event_id": event.event_id,
            "target_symbol": event.target_symbol,
            "target_company_name": event.target_company_name,
            "event_type": event.event_type.value,
            "event_fact": event.event_fact,
            "event_temporal_value": event.event_temporal_value.isoformat() if event.event_temporal_value else None,
            "source_ids": sorted(event.source_ids),
            "primary_source_id": event.primary_source_id,
            "validation_status": event.validation_status.value,
            "conflict_status": event.conflict_status.value,
        },
        "company_background": _canonical_collection(
            _evidence_fingerprint(item) for item in context.company_background
        ),
        "supporting_evidence": _canonical_collection(
            _evidence_fingerprint(item) for item in context.supporting_evidence
        ),
        "supporting_evidence_provenance": _canonical_collection(
            {
                "evidence_ref": item.evidence_ref,
                "provenance_source_ids": item.provenance_source_ids,
                "provenance_event_ids": item.provenance_event_ids,
            }
            for item in context.supporting_evidence_provenance
        ),
        "contradictory_evidence": _canonical_collection(
            _evidence_fingerprint(item) for item in context.contradictory_evidence
        ),
        "missing_evidence": _canonical_collection(
            _missing_evidence_fingerprint(item) for item in context.missing_evidence
        ),
        "provider_context": {
            "symbol": context.selected_context.symbol,
            "display_name": context.selected_context.display_name,
            "question_type": context.selected_context.question_type.value,
            "selected_evidence": _canonical_collection(
                _evidence_fingerprint(item) for item in context.selected_context.selected_evidence
            ),
            "selected_missing_data": _canonical_collection(
                _missing_evidence_fingerprint(item) for item in context.selected_context.selected_missing_data
            ),
        },
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _evidence_fingerprint(item: EvidenceItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "category": item.category,
        "metric": item.metric,
        "value": item.value,
        "unit": item.unit,
        "currency": item.currency,
        "period_end": item.period_end.isoformat() if item.period_end else None,
        "period_year": item.period_year,
        "source": item.source,
        "source_type": item.source_type,
        "derived_from": item.derived_from,
        "note": item.note,
    }


def _missing_evidence_fingerprint(item: MissingDataItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "area": item.area,
        "metric": item.metric,
        "period_end": item.period_end.isoformat() if item.period_end else None,
        "period_year": item.period_year,
        "reason": item.reason,
        "impact": item.impact,
        "source": item.source,
    }


def _canonical_collection(items: Any) -> list[dict[str, Any]]:
    """Sort collection members without changing any item-level content or multiplicity."""
    return sorted(
        items,
        key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def _canonical_refs(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if (
        not isinstance(values, tuple)
        or any(not isinstance(item, str) or not item for item in values)
        or len(set(values)) != len(values)
    ):
        raise CatalystImpactServiceError(f"{field_name} must be unique non-empty evidence references.")
    return tuple(sorted(values))


def _canonical_supporting_provenance(
    provenance: tuple[ApprovedSupportingEvidence, ...],
) -> tuple[ApprovedSupportingEvidence, ...]:
    if not isinstance(provenance, tuple) or any(
        not isinstance(item, ApprovedSupportingEvidence) for item in provenance
    ):
        raise CatalystImpactServiceError("Supporting evidence provenance must be immutable V1J records.")
    if len({item.evidence_ref for item in provenance}) != len(provenance):
        raise CatalystImpactServiceError("Supporting evidence provenance must cover each evidence reference once.")
    return tuple(sorted(provenance, key=lambda item: item.evidence_ref))


def _require_supporting_provenance(
    evidence_refs: tuple[str, ...],
    provenance: tuple[ApprovedSupportingEvidence, ...],
) -> None:
    if not isinstance(provenance, tuple) or any(not isinstance(item, ApprovedSupportingEvidence) for item in provenance):
        raise CatalystImpactServiceError("Supporting evidence provenance must be immutable V1J records.")
    provenance_refs = tuple(item.evidence_ref for item in provenance)
    if provenance_refs != evidence_refs:
        raise CatalystImpactServiceError("Supporting evidence requires exact deterministic provenance coverage.")
