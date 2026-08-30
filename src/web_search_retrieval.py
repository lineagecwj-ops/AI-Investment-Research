"""Offline-first contracts for bounded external web-search retrieval."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from enum import StrEnum
import hashlib
import json
from typing import Protocol

from external_source import ExternalSourceRef
from external_source import RawWebSearchSource
from external_source import RelatedCompanyIdentity
from external_source import SourceTier
from external_source import TargetCompanyIdentity
from external_source import deduplicate_sources
from external_source import normalize_external_source


WEB_SEARCH_RETRIEVAL_ARTIFACT_VERSION = "WEB_SEARCH_RETRIEVAL_ARTIFACT_V1"
DEFAULT_RETRIEVAL_MODEL = "gpt-5.6-luna"


class WebSearchRetrievalError(ValueError):
    """Raised when bounded external retrieval is not explicitly authorized."""


class ToolCallAccountingStatus(StrEnum):
    COMPLIANT = "COMPLIANT"
    EXCEEDED_EXPECTED_POLICY = "EXCEEDED_EXPECTED_POLICY"
    UNOBSERVED = "UNOBSERVED"


@dataclass(frozen=True)
class WebSearchRetrievalRequest:
    target: TargetCompanyIdentity
    start_date: date
    end_date: date
    query: str
    retrieval_model: str = DEFAULT_RETRIEVAL_MODEL
    expected_max_tool_calls: int = 1
    explicit_refresh: bool = False
    related_entities: tuple[RelatedCompanyIdentity, ...] = ()

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise WebSearchRetrievalError("start_date must not be after end_date.")
        if not self.query.strip():
            raise WebSearchRetrievalError("query must be non-empty.")
        if not self.retrieval_model.strip():
            raise WebSearchRetrievalError("retrieval_model must be non-empty.")
        if self.expected_max_tool_calls < 0:
            raise WebSearchRetrievalError("expected_max_tool_calls must not be negative.")


@dataclass(frozen=True)
class WebSearchRetrievalResponse:
    response_status: str
    observed_web_search_call_count: int | None
    sources: tuple[RawWebSearchSource, ...]
    usage: dict[str, int] | None = None


class WebSearchRetrievalClient(Protocol):
    def retrieve(self, request: WebSearchRetrievalRequest) -> WebSearchRetrievalResponse:
        """Perform an explicit retrieval; production transport is intentionally absent in V1F."""


@dataclass(frozen=True)
class WebSearchRetrievalArtifact:
    target_symbol: str
    target_company_name: str
    query: str
    research_window_start: date
    research_window_end: date
    retrieved_at: datetime
    model: str
    responses_request_count: int
    observed_web_search_call_count: int | None
    expected_max_tool_calls: int
    response_status: str
    sources: tuple[ExternalSourceRef, ...]
    normalization_warnings: tuple[str, ...]
    tool_call_accounting_status: ToolCallAccountingStatus
    checksum: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "checksum", _checksum(self.identity_payload))

    @property
    def identity_payload(self) -> dict[str, object]:
        return {
            "artifact_version": WEB_SEARCH_RETRIEVAL_ARTIFACT_VERSION,
            "target_symbol": self.target_symbol,
            "target_company_name": self.target_company_name,
            "query": self.query,
            "research_window_start": self.research_window_start.isoformat(),
            "research_window_end": self.research_window_end.isoformat(),
            "model": self.model,
            "responses_request_count": self.responses_request_count,
            "observed_web_search_call_count": self.observed_web_search_call_count,
            "expected_max_tool_calls": self.expected_max_tool_calls,
            "response_status": self.response_status,
            "sources": [source.identity_payload() for source in self.sources],
            "normalization_warnings": list(self.normalization_warnings),
            "tool_call_accounting_status": self.tool_call_accounting_status.value,
        }


class WebSearchRetrievalService:
    """Requires an explicit refresh and an injected client before any retrieval occurs."""

    def __init__(self, client: WebSearchRetrievalClient, *, domain_map: dict[str, SourceTier] | None = None) -> None:
        self._client = client
        self._domain_map = domain_map or {}

    def retrieve_external_sources(self, request: WebSearchRetrievalRequest, *, retrieved_at: datetime) -> WebSearchRetrievalArtifact:
        if not request.explicit_refresh:
            raise WebSearchRetrievalError("External retrieval requires explicit_refresh=True.")
        response = self._client.retrieve(request)
        return build_retrieval_artifact(request, response, retrieved_at=retrieved_at, domain_map=self._domain_map)


def build_retrieval_artifact(
    request: WebSearchRetrievalRequest,
    response: WebSearchRetrievalResponse,
    *,
    retrieved_at: datetime,
    domain_map: dict[str, SourceTier] | None = None,
) -> WebSearchRetrievalArtifact:
    normalized = tuple(
        normalize_external_source(
            source,
            target=request.target,
            retrieved_at=retrieved_at,
            domain_map=domain_map,
            related_entities=request.related_entities,
        )
        for source in response.sources
    )
    sources = deduplicate_sources(normalized)
    warnings: list[str] = []
    if len(sources) != len(normalized):
        warnings.append("DUPLICATE_SOURCES_REMOVED")
    accounting = _tool_call_accounting(response.observed_web_search_call_count, request.expected_max_tool_calls)
    if accounting is ToolCallAccountingStatus.EXCEEDED_EXPECTED_POLICY:
        warnings.append("OBSERVED_WEB_SEARCH_CALL_COUNT_EXCEEDS_EXPECTED_POLICY")
    if accounting is ToolCallAccountingStatus.UNOBSERVED:
        warnings.append("OBSERVED_WEB_SEARCH_CALL_COUNT_UNAVAILABLE")
    return WebSearchRetrievalArtifact(
        target_symbol=request.target.symbol,
        target_company_name=request.target.canonical_name,
        query=request.query,
        research_window_start=request.start_date,
        research_window_end=request.end_date,
        retrieved_at=retrieved_at,
        model=request.retrieval_model,
        responses_request_count=1,
        observed_web_search_call_count=response.observed_web_search_call_count,
        expected_max_tool_calls=request.expected_max_tool_calls,
        response_status=response.response_status,
        sources=sources,
        normalization_warnings=tuple(sorted(warnings)),
        tool_call_accounting_status=accounting,
    )


def _tool_call_accounting(observed: int | None, expected: int) -> ToolCallAccountingStatus:
    if observed is None:
        return ToolCallAccountingStatus.UNOBSERVED
    if observed > expected:
        return ToolCallAccountingStatus.EXCEEDED_EXPECTED_POLICY
    return ToolCallAccountingStatus.COMPLIANT


def _checksum(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
