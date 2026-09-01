"""Local, safe-forensics provenance for explicit Catalyst Deep Dive runs."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC
from datetime import date
from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from uuid import uuid4

from catalyst_event import EventCandidate
from catalyst_event import ValidatedCatalystEvent
from catalyst_impact import ImpactHypothesis
from external_source import ExternalSourceRef
from web_search_retrieval import WebSearchRetrievalArtifact


CATALYST_RUNTIME_PROVENANCE_VERSION = "CATALYST_RUNTIME_PROVENANCE_V1"
DEFAULT_RUNTIME_PROVENANCE_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "data" / "research" / "catalyst_runtime_provenance"
)
MAX_SANITIZED_ERROR_LENGTH = 512
_API_KEY_ASSIGNMENT = re.compile(r"(?i)\b(api[_-]?key|authorization|token|secret)\s*([=:])\s*[^\s,;]+")
_BEARER_TOKEN = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_OPENAI_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")


class CatalystRuntimeProvenanceError(RuntimeError):
    """Raised only when local provenance cannot be persisted."""


class CatalystRuntimeProvenanceRun:
    """One explicit refresh collector; it never invokes providers or mutates research logic."""

    def __init__(
        self,
        *,
        symbol: str,
        trigger: str,
        started_at: datetime | None = None,
        output_directory: Path | str = DEFAULT_RUNTIME_PROVENANCE_DIRECTORY,
        run_id: str | None = None,
        known_secrets: Iterable[str] = (),
    ) -> None:
        if not symbol.strip() or not trigger.strip():
            raise ValueError("Runtime provenance requires a symbol and explicit trigger.")
        self._started_at = _utc(started_at or datetime.now(UTC))
        self._run_id = run_id or _build_run_id(symbol, self._started_at)
        self._output_directory = Path(output_directory)
        self._known_secrets = tuple(value for value in known_secrets if value)
        self._payload: dict[str, Any] = {
            "schema_version": CATALYST_RUNTIME_PROVENANCE_VERSION,
            "run_id": self._run_id,
            "symbol": symbol.strip().upper(),
            "trigger": trigger,
            "started_at": self._started_at.isoformat(),
            "completed_at": None,
            "run_status": "PIPELINE_FAILED",
            "retrieval": {
                "attempted": False,
                "request_count": 0,
                "status": "NOT_ATTEMPTED",
                "model": None,
                "provider_response_id": None,
                "artifact_checksum": None,
                "source_count": 0,
                "sources": [],
            },
            "event_pipeline": {"candidates": [], "events": []},
            "impact_attempts": [],
            "failures": [],
            "call_accounting": {
                "retrieval_call_count": 0,
                "impact_call_count": 0,
                "total_external_call_count": 0,
            },
        }

    @property
    def run_id(self) -> str:
        return self._run_id

    def record_retrieval(self, artifact: WebSearchRetrievalArtifact) -> None:
        self._payload["retrieval"] = {
            "attempted": True,
            "request_count": artifact.responses_request_count,
            "status": artifact.response_status,
            "model": artifact.model,
            "provider_response_id": None,
            "artifact_checksum": artifact.checksum,
            "source_count": len(artifact.sources),
            "sources": [_source_payload(source) for source in artifact.sources],
        }
        self._set_call_counts(retrieval=artifact.responses_request_count)

    def record_retrieval_failure(self, error: Exception) -> None:
        self._payload["retrieval"] = {
            "attempted": True,
            "request_count": 1,
            "status": "FAILED",
            "model": None,
            "provider_response_id": None,
            "artifact_checksum": None,
            "source_count": 0,
            "sources": [],
        }
        self._set_call_counts(retrieval=1)
        self.record_failure(stage="RETRIEVAL", error=error)

    def record_event_pipeline(
        self,
        *,
        candidates: Iterable[EventCandidate],
        events: Iterable[ValidatedCatalystEvent],
    ) -> None:
        self._payload["event_pipeline"] = {
            "candidates": [_candidate_payload(candidate) for candidate in candidates],
            "events": [_event_payload(event) for event in events],
        }

    def record_failure(
        self,
        *,
        stage: str,
        error: Exception,
        event_id: str | None = None,
        impact_call_index: int | None = None,
    ) -> None:
        self._payload["failures"].append({
            "error_stage": stage,
            "exception_class": type(error).__name__,
            "sanitized_error_message": sanitize_error_message(str(error), self._known_secrets),
            "event_id": event_id,
            "impact_call_index": impact_call_index,
        })

    def record_impact_success(
        self,
        *,
        event: ValidatedCatalystEvent,
        call_index: int,
        hypothesis: ImpactHypothesis,
    ) -> None:
        self._record_impact(
            event=event,
            call_index=call_index,
            status="SUCCESS",
            hypothesis=_impact_payload(hypothesis),
        )

    def record_impact_failure(
        self,
        *,
        event: ValidatedCatalystEvent,
        call_index: int,
        error: Exception,
    ) -> None:
        self._record_impact(event=event, call_index=call_index, status="FAILED", hypothesis=None)
        self.record_failure(
            stage="IMPACT_PROVIDER",
            error=error,
            event_id=event.event_id,
            impact_call_index=call_index,
        )

    def record_impact_context_failure(
        self,
        *,
        event: ValidatedCatalystEvent,
        error: Exception,
    ) -> None:
        """Record deterministic local context failure without claiming a provider attempt."""
        self._record_impact(
            event=event,
            call_index=None,
            status="CONTEXT_FAILED",
            hypothesis=None,
            impact_attempted=False,
        )
        self.record_failure(stage="IMPACT_CONTEXT", error=error, event_id=event.event_id)

    def finalize_and_persist(self, *, run_status: str, completed_at: datetime | None = None) -> Path:
        self._payload["run_status"] = run_status
        self._payload["completed_at"] = _utc(completed_at or datetime.now(UTC)).isoformat()
        self._payload["impact_attempts"].sort(key=lambda item: (
            item["impact_call_index"] is not None,
            item["impact_call_index"] or 0,
            item["event_id"],
        ))
        self._payload["failures"].sort(key=lambda item: (
            item["error_stage"], item["event_id"] or "", item["impact_call_index"] or 0,
        ))
        return _atomic_write_json(self._output_directory / f"{self._run_id}.json", self._payload)

    def _record_impact(
        self,
        *,
        event: ValidatedCatalystEvent,
        call_index: int | None,
        status: str,
        hypothesis: dict[str, Any] | None,
        impact_attempted: bool = True,
    ) -> None:
        self._payload["impact_attempts"].append({
            "event_id": event.event_id,
            "event_key": event.event_key,
            "impact_attempted": impact_attempted,
            "impact_call_index": call_index,
            "impact_status": status,
            "hypothesis": hypothesis,
        })
        if impact_attempted:
            self._set_call_counts(
                impact=self._payload["call_accounting"]["impact_call_count"] + 1,
            )

    def _set_call_counts(self, *, retrieval: int | None = None, impact: int | None = None) -> None:
        counts = self._payload["call_accounting"]
        if retrieval is not None:
            counts["retrieval_call_count"] = retrieval
        if impact is not None:
            counts["impact_call_count"] = impact
        counts["total_external_call_count"] = counts["retrieval_call_count"] + counts["impact_call_count"]


def sanitize_error_message(message: str, known_secrets: Iterable[str] = ()) -> str:
    """Retain a bounded diagnostic while removing credentials and common secret forms."""
    sanitized = message or type(message).__name__
    for secret in sorted({value for value in known_secrets if value}, key=len, reverse=True):
        sanitized = sanitized.replace(secret, "[REDACTED_SECRET]")
    sanitized = _BEARER_TOKEN.sub("Bearer [REDACTED_TOKEN]", sanitized)
    sanitized = _OPENAI_KEY.sub("[REDACTED_OPENAI_KEY]", sanitized)
    sanitized = _API_KEY_ASSIGNMENT.sub(r"\1\2[REDACTED_SECRET]", sanitized)
    return sanitized[:MAX_SANITIZED_ERROR_LENGTH]


def _source_payload(source: ExternalSourceRef) -> dict[str, Any]:
    payload = source.identity_payload()
    payload["retrieved_at"] = source.retrieved_at.isoformat()
    payload["content_hash"] = source.content_hash
    return payload


def _candidate_payload(candidate: EventCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "source_id": candidate.source_id,
        "target_symbol": candidate.target_symbol,
        "candidate_anchor": candidate.candidate_anchor,
        "candidate_type": candidate.candidate_type.value,
        "candidate_status": candidate.candidate_status.value,
        "company_association_status": candidate.company_association_status.value,
        "extraction_basis": candidate.extraction_basis.value,
        "temporal_evidence": [_temporal_payload(item) for item in candidate.temporal_evidence],
    }


def _event_payload(event: ValidatedCatalystEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_key": event.event_key,
        "event_type": event.event_type.value,
        "event_fact": event.event_fact,
        "event_temporal_evidence": _temporal_payload(event.event_temporal_evidence),
        "event_temporal_status": event.event_temporal_status.value,
        "source_ids": list(event.source_ids),
        "candidate_ids": list(event.candidate_ids),
        "primary_source_id": event.primary_source_id,
        "support_count": event.support_count,
        "company_association_status": event.company_association_status.value,
        "validation_status": event.validation_status.value,
        "conflict_status": event.conflict_status.value,
    }


def _impact_payload(hypothesis: ImpactHypothesis) -> dict[str, Any]:
    return {
        "hypothesis_id": hypothesis.hypothesis_id,
        "event_id": hypothesis.event_id,
        "impact_channel": hypothesis.impact_channel.value,
        "hypothesis_status": hypothesis.hypothesis_status.value,
        "hypothesis_text": hypothesis.hypothesis_text,
        "why_it_matters_text": hypothesis.why_it_matters_text,
        "contradiction_or_limit_text": hypothesis.contradiction_or_limit_text,
        "uncertainty_text": hypothesis.uncertainty_text,
        "next_checks": list(hypothesis.next_checks),
        "supporting_evidence_refs": list(hypothesis.supporting_evidence_refs),
        "contradictory_evidence_refs": list(hypothesis.contradictory_evidence_refs),
        "missing_evidence": list(hypothesis.missing_evidence),
        "version": hypothesis.version,
    }


def _temporal_payload(evidence: Any) -> dict[str, Any] | None:
    if evidence is None:
        return None
    return {
        "value": evidence.value.isoformat(),
        "precision": evidence.precision.value,
        "kind": evidence.kind.value,
        "basis": evidence.basis.value,
        "raw_text": evidence.raw_text,
        "confidence_status": evidence.confidence_status.value,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> Path:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".tmp", dir=path.parent)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
    except OSError as exc:
        raise CatalystRuntimeProvenanceError("Local runtime provenance persistence failed.") from exc
    return path


def _build_run_id(symbol: str, started_at: datetime) -> str:
    safe_symbol = re.sub(r"[^A-Za-z0-9]+", "-", symbol.upper()).strip("-")
    timestamp = started_at.strftime("%Y%m%dT%H%M%S%fZ")
    return f"catalyst-runtime-{safe_symbol}-{timestamp}-{uuid4().hex[:12]}"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
