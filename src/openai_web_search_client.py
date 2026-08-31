"""Explicit OpenAI Responses Web Search transport for Catalyst V1H."""
from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from datetime import date
import os
from typing import Any

from external_source import RawWebSearchSource
from external_source import SourceTier
from external_source import TargetCompanyIdentity
from external_source import canonicalize_url
from web_search_retrieval import DEFAULT_RETRIEVAL_MODEL
from web_search_retrieval import WebSearchRetrievalClient
from web_search_retrieval import WebSearchRetrievalError
from web_search_retrieval import WebSearchRetrievalRequest
from web_search_retrieval import WebSearchRetrievalResponse
from web_search_retrieval import WebSearchRetrievalService


OPENAI_WEB_SEARCH_INCLUDE = (
    "web_search_call.action.sources",
    "web_search_call.results",
)
OPENAI_WEB_SEARCH_TOOL = {"type": "web_search", "search_context_size": "low"}
OPENAI_WEB_SEARCH_DOMAIN_MAP = {
    "twse.com.tw": SourceTier.TIER_1_OFFICIAL,
    "mops.twse.com.tw": SourceTier.TIER_1_OFFICIAL,
    "wwwc.twse.com.tw": SourceTier.TIER_1_OFFICIAL,
    "tw.stock.yahoo.com": SourceTier.TIER_2_ESTABLISHED_MEDIA,
    "moneydj.com": SourceTier.TIER_2_ESTABLISHED_MEDIA,
    "marketscreener.com": SourceTier.TIER_2_ESTABLISHED_MEDIA,
    "goodinfo.tw": SourceTier.TIER_3_OTHER_ATTRIBUTABLE,
    "reddit.com": SourceTier.TIER_4_SOCIAL_COMMUNITY,
}


class OpenAIWebSearchRetrievalError(WebSearchRetrievalError):
    """Raised for a sanitized V1H OpenAI Web Search transport failure."""


def build_company_research_query(
    *,
    target: TargetCompanyIdentity,
    start_date: date,
    end_date: date,
) -> str:
    """Build one bounded, factual company request without investment advice."""
    aliases = ", ".join(alias for alias in target.supported_aliases if alias)
    identity = f"{target.validated_english_name or target.canonical_name} ({target.canonical_name}, Taiwan stock {target.security_code})"
    if aliases:
        identity += f"; validated aliases: {aliases}"
    return (
        f"Find factual recent developments specifically concerning {identity} published or announced "
        f"between {start_date.isoformat()} and {end_date.isoformat()}. Prefer official sources then "
        "established financial/business media. Return source-grounded facts only. Do not provide "
        "investment advice, price targets, predictions, expected return, probability, or portfolio advice."
    )


class OpenAIWebSearchRetrievalClient(WebSearchRetrievalClient):
    """One-request, no-retry transport; credentials are resolved only at call time."""

    def __init__(
        self,
        *,
        client_factory: Callable[..., Any] | None = None,
        environ: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._environ = environ if environ is not None else os.environ
        self._timeout = timeout

    def retrieve(self, request: WebSearchRetrievalRequest) -> WebSearchRetrievalResponse:
        if not request.explicit_refresh:
            raise OpenAIWebSearchRetrievalError("EXPLICIT_REFRESH_REQUIRED")
        api_key = self._environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise OpenAIWebSearchRetrievalError("OPENAI_API_KEY_MISSING")

        client = self._create_client(api_key)
        try:
            response = client.responses.create(**_request_payload(request))
        except Exception as exc:
            raise _map_provider_error(exc) from exc

        try:
            return adapt_openai_web_search_response(response)
        except OpenAIWebSearchRetrievalError:
            raise
        except Exception as exc:
            raise OpenAIWebSearchRetrievalError("NORMALIZATION_FAILED") from exc

    def _create_client(self, api_key: str) -> Any:
        factory = self._client_factory
        if factory is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise OpenAIWebSearchRetrievalError("OPENAI_PROVIDER_ERROR") from exc
            factory = OpenAI
        return factory(api_key=api_key, timeout=self._timeout)


def build_openai_web_search_retrieval_service(
    *,
    client: OpenAIWebSearchRetrievalClient | None = None,
) -> WebSearchRetrievalService:
    """Return the V1F service wired to the small V1H transport and tier map."""
    return WebSearchRetrievalService(client or OpenAIWebSearchRetrievalClient(), domain_map=OPENAI_WEB_SEARCH_DOMAIN_MAP)


def adapt_openai_web_search_response(response: Any) -> WebSearchRetrievalResponse:
    """Extract deterministic evidence fields without using generated message prose."""
    payload = _mapping(response)
    response_status = _string(payload.get("status"))
    if response_status != "completed":
        raise OpenAIWebSearchRetrievalError("OPENAI_RESPONSE_NOT_COMPLETED")
    output = _mapping_sequence(payload.get("output"))
    observed_calls = sum(item.get("type") == "web_search_call" for item in output)
    if observed_calls == 0:
        raise OpenAIWebSearchRetrievalError("WEB_SEARCH_NOT_EXECUTED")

    candidates: list[_SourceCandidate] = []
    completed_call_count = 0
    for item in output:
        if item.get("type") == "web_search_call":
            if item.get("status") == "completed":
                completed_call_count += 1
                candidates.extend(_result_candidates(item))
                candidates.extend(_action_source_candidates(item))
        elif item.get("type") == "message":
            candidates.extend(_citation_candidates(item))
    if completed_call_count == 0:
        raise OpenAIWebSearchRetrievalError("WEB_SEARCH_NOT_COMPLETED")
    sources = _merge_candidates(candidates)
    if not sources:
        raise OpenAIWebSearchRetrievalError("NO_CURRENT_EVENT_SOURCES")

    return WebSearchRetrievalResponse(
        response_status=response_status,
        observed_web_search_call_count=observed_calls,
        sources=sources,
        usage=_usage(payload.get("usage")),
    )


def _request_payload(request: WebSearchRetrievalRequest) -> dict[str, object]:
    return {
        "model": request.retrieval_model or DEFAULT_RETRIEVAL_MODEL,
        "input": request.query,
        "store": False,
        "tools": [OPENAI_WEB_SEARCH_TOOL],
        "tool_choice": "required",
        "max_tool_calls": request.expected_max_tool_calls,
        "include": list(OPENAI_WEB_SEARCH_INCLUDE),
    }


def _result_candidates(item: Mapping[str, Any]) -> list["_SourceCandidate"]:
    return [
        _SourceCandidate(
            url=_string(result.get("url")),
            title=_string(result.get("title")),
            snippet=_string(result.get("snippet")),
            source_published_at=_string(result.get("published_at")),
            source_type="openai_web_search_result",
            priority=3,
        )
        for result in _mapping_sequence(item.get("results"))
    ]


def _action_source_candidates(item: Mapping[str, Any]) -> list["_SourceCandidate"]:
    action = _mapping(item.get("action"))
    return [
        _SourceCandidate(
            url=_string(source.get("url")),
            title=_string(source.get("title")),
            snippet=None,
            source_published_at=_string(source.get("published_at")),
            source_type="openai_web_search_action_source",
            priority=1,
        )
        for source in _mapping_sequence(action.get("sources"))
    ]


def _citation_candidates(message: Mapping[str, Any]) -> list["_SourceCandidate"]:
    candidates: list[_SourceCandidate] = []
    containers = [message, *_mapping_sequence(message.get("content"))]
    for container in containers:
        for annotation in _mapping_sequence(container.get("annotations")):
            citation = _mapping(annotation.get("url_citation")) if annotation.get("type") != "url_citation" else annotation
            url = _string(citation.get("url"))
            if url:
                candidates.append(_SourceCandidate(
                    url=url,
                    title=_string(citation.get("title")),
                    snippet=None,
                    source_published_at=None,
                    source_type="openai_url_citation",
                    priority=2,
                ))
    return candidates


def _merge_candidates(candidates: list["_SourceCandidate"]) -> tuple[RawWebSearchSource, ...]:
    grouped: dict[str, list[_SourceCandidate]] = {}
    for index, candidate in enumerate(candidates):
        key = _candidate_key(candidate, index)
        grouped.setdefault(key, []).append(candidate)

    sources: list[RawWebSearchSource] = []
    for key in sorted(grouped):
        group = grouped[key]
        sources.append(RawWebSearchSource(
            url=_best_value(group, "url"),
            title=_best_value(group, "title"),
            snippet=_best_value(group, "snippet"),
            source_type=_best_value(group, "source_type") or "openai_web_search_result",
            source_published_at=_best_value(group, "source_published_at"),
        ))
    return tuple(sources)


def _candidate_key(candidate: "_SourceCandidate", index: int) -> str:
    if candidate.url:
        try:
            canonical = canonicalize_url(candidate.url)
        except ValueError:
            canonical = candidate.url.strip()
        if canonical:
            return "url:" + canonical
    if candidate.title:
        return "title:" + " ".join(candidate.title.split()).casefold()
    return f"unidentified:{index:08d}"


def _best_value(candidates: list["_SourceCandidate"], field: str) -> str | None:
    if not any(getattr(candidate, field) for candidate in candidates):
        return None
    ranked = sorted(
        (candidate for candidate in candidates if getattr(candidate, field)),
        key=lambda candidate: (-candidate.priority, -len(getattr(candidate, field)), getattr(candidate, field).casefold()),
    )
    return getattr(ranked[0], field)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dict(dumped)
    return {
        key: getattr(value, key)
        for key in ("status", "output", "usage", "type", "results", "action", "content", "annotations", "url_citation", "url", "title", "snippet", "published_at", "sources")
        if hasattr(value, key)
    }


def _mapping_sequence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [_mapping(item) for item in value]


def _string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _usage(value: Any) -> dict[str, int] | None:
    usage = _mapping(value)
    safe = {key: item for key, item in usage.items() if key in {"input_tokens", "output_tokens", "total_tokens"} and isinstance(item, int)}
    return safe or None


def _map_provider_error(exc: Exception) -> OpenAIWebSearchRetrievalError:
    status_code = getattr(exc, "status_code", None)
    if status_code == 401:
        return OpenAIWebSearchRetrievalError("OPENAI_AUTH_FAILED")
    if status_code == 403:
        return OpenAIWebSearchRetrievalError("OPENAI_ACCESS_DENIED")
    if status_code == 429:
        return OpenAIWebSearchRetrievalError("OPENAI_RATE_OR_QUOTA_LIMIT")
    return OpenAIWebSearchRetrievalError("OPENAI_REQUEST_FAILED")


class _SourceCandidate:
    def __init__(
        self,
        *,
        url: str | None,
        title: str | None,
        snippet: str | None,
        source_published_at: str | None,
        source_type: str,
        priority: int,
    ) -> None:
        self.url = url
        self.title = title
        self.snippet = snippet
        self.source_published_at = source_published_at
        self.source_type = source_type
        self.priority = priority
