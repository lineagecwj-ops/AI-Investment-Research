"""Explicit, event-level Catalyst Deep Dive orchestration for the Research UI."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
import os
from pathlib import Path
from typing import Any

from ai_config import get_ai_research_config
from catalyst_event import EventValidationStatus
from catalyst_event import ValidatedCatalystEvent
from catalyst_event_extraction import cluster_validated_events
from catalyst_event_extraction import extract_event_candidates
from catalyst_impact import ImpactHypothesis
from catalyst_impact_service import build_event_impact_context
from catalyst_impact_service import generate_event_impact_hypothesis
from catalyst_runtime_provenance import CatalystRuntimeProvenanceRun
from external_source import TargetCompanyIdentity
from openai_web_search_client import build_company_research_query
from openai_web_search_client import build_openai_web_search_retrieval_service
from research_context import MissingDataItem
from research_context import build_research_context
from research_context_selector import ResearchQuestionType
from research_context_selector import ResearchSelectionRequest
from research_context_selector import SelectedResearchContext
from research_context_selector import select_research_context
from research_service import ResearchReport
from models import Stock
from web_search_retrieval import WebSearchRetrievalRequest


CATALYST_DEEP_DIVE_WINDOW_DAYS = 30
MAX_WEB_SEARCH_RESPONSES_REQUESTS = 1
MAX_IMPACT_AI_CALLS = 2


@dataclass(frozen=True)
class CatalystDeepDiveCard:
    """One program-owned event card, with an optional bounded AI interpretation."""

    event: ValidatedCatalystEvent
    impact_hypothesis: ImpactHypothesis | None
    missing_evidence: tuple[MissingDataItem, ...]
    impact_error: str | None = None


@dataclass(frozen=True)
class CatalystDeepDiveResult:
    """Session-only result of one explicit company refresh."""

    target_symbol: str
    target_company_name: str
    state: str
    message: str
    cards: tuple[CatalystDeepDiveCard, ...] = ()
    validated_event_count: int = 0
    omitted_validated_event_count: int = 0
    retrieval_request_count: int = 0
    impact_call_count: int = 0
    provenance_run_id: str | None = None
    provenance_status: str = "NOT_TRIGGERED"
    provenance_warning: str | None = None


def build_selected_catalyst_context(
    *,
    stock: Stock,
    research_report: ResearchReport,
    display_name: str,
    generated_at: datetime | None = None,
) -> SelectedResearchContext:
    """Reuse the released selected-company Research Context without another data fetch."""
    context = build_research_context(
        stock=stock,
        research_report=research_report,
        display_name=display_name,
        generated_at=generated_at,
    )
    return select_research_context(
        context,
        ResearchSelectionRequest(question_type=ResearchQuestionType.GENERAL_RESEARCH),
    )


def run_catalyst_deep_dive_refresh(
    *,
    selected_context: SelectedResearchContext,
    explicit_refresh: bool,
    as_of_date: date | None = None,
    retrieved_at: datetime | None = None,
    api_key_available: Callable[[], bool] | None = None,
    retrieval_service: Any | None = None,
    impact_generator: Callable[..., ImpactHypothesis] = generate_event_impact_hypothesis,
    impact_client: Any | None = None,
    impact_config: Any | None = None,
    provenance_directory: Path | str | None = None,
    provenance_factory: Callable[..., CatalystRuntimeProvenanceRun] = CatalystRuntimeProvenanceRun,
) -> CatalystDeepDiveResult:
    """Run the one-retrieval, at-most-two-event Catalyst flow after an explicit click."""
    target = _target_from_context(selected_context)
    if not explicit_refresh:
        return _result(target, "NOT_REFRESHED", "尚未更新 Catalyst 深度分析。")

    provenance = provenance_factory(
        symbol=target.symbol,
        trigger="CATALYST_DEEP_DIVE_EXPLICIT_REFRESH",
        started_at=retrieved_at or datetime.now(UTC),
        output_directory=provenance_directory or _default_provenance_directory(),
        known_secrets=_runtime_known_secrets(),
    )

    key_available = api_key_available or _openai_api_key_available
    if not key_available():
        return _finalize_with_provenance(
            _result(target, "API_KEY_MISSING", "未設定 OPENAI_API_KEY，尚未進行 Catalyst 深度分析。"),
            provenance=provenance,
            run_status="PIPELINE_FAILED",
            completed_at=retrieved_at,
        )

    end_date = as_of_date or datetime.now(UTC).date()
    start_date = end_date - timedelta(days=CATALYST_DEEP_DIVE_WINDOW_DAYS)
    request = WebSearchRetrievalRequest(
        target=target,
        start_date=start_date,
        end_date=end_date,
        query=build_company_research_query(
            target=target,
            start_date=start_date,
            end_date=end_date,
        ),
        expected_max_tool_calls=MAX_WEB_SEARCH_RESPONSES_REQUESTS,
        explicit_refresh=True,
    )
    service = retrieval_service or build_openai_web_search_retrieval_service()
    try:
        artifact = service.retrieve_external_sources(
            request,
            retrieved_at=retrieved_at or datetime.now(UTC),
        )
    except Exception as exc:
        provenance.record_retrieval_failure(exc)
        return _finalize_with_provenance(
            _result(
            target,
            "RETRIEVAL_FAILED",
            "Catalyst 來源擷取暫時無法完成，請稍後由使用者再次更新。",
            retrieval_request_count=1,
            ),
            provenance=provenance,
            run_status="RETRIEVAL_FAILED",
            completed_at=retrieved_at,
        )

    provenance.record_retrieval(artifact)

    if not artifact.sources:
        provenance.record_event_pipeline(candidates=(), events=())
        return _finalize_with_provenance(
            _result(
                target,
                "NO_USABLE_SOURCES",
                "目前沒有可用的 Catalyst 來源證據。",
                retrieval_request_count=1,
            ),
            provenance=provenance,
            run_status="NO_VALIDATED_EVENTS",
            completed_at=retrieved_at,
        )

    try:
        candidates = extract_event_candidates(
            artifact.sources,
            target_symbol=target.symbol,
            target_company_name=target.canonical_name,
            validated_aliases=target.supported_aliases,
            research_window=(start_date, end_date),
        )
        events = cluster_validated_events(
            candidates,
            sources=artifact.sources,
            research_window=(start_date, end_date),
        )
    except Exception as exc:
        provenance.record_failure(stage="EVENT_EXTRACTION", error=exc)
        return _finalize_with_provenance(
            _result(
                target,
                "EVENT_EXTRACTION_FAILED",
                "Catalyst 事件證據無法安全整理，因此未產生深度分析。",
                retrieval_request_count=1,
            ),
            provenance=provenance,
            run_status="PIPELINE_FAILED",
            completed_at=retrieved_at,
        )

    provenance.record_event_pipeline(candidates=candidates, events=events)

    validated = _ordered_validated_events(events)
    if not validated:
        return _finalize_with_provenance(
            _result(
                target,
                "NO_VALIDATED_EVENTS",
                "目前沒有足夠已驗證的 Catalyst 事件可供深度分析。",
                retrieval_request_count=1,
            ),
            provenance=provenance,
            run_status="NO_VALIDATED_EVENTS",
            completed_at=retrieved_at,
        )

    selected_events = validated[:MAX_IMPACT_AI_CALLS]
    cards: list[CatalystDeepDiveCard] = []
    impact_calls = 0
    missing_refs = tuple(item.id for item in selected_context.selected_missing_data)
    for event in selected_events:
        try:
            impact_context = build_event_impact_context(
                event=event,
                selected_context=selected_context,
                missing_evidence_refs=missing_refs,
            )
        except Exception as exc:
            provenance.record_impact_context_failure(event=event, error=exc)
            cards.append(
                CatalystDeepDiveCard(
                    event=event,
                    impact_hypothesis=None,
                    missing_evidence=tuple(selected_context.selected_missing_data),
                    impact_error="分析暫時無法產生；此事件未進行自動重試。",
                )
            )
            continue

        impact_calls += 1
        try:
            hypothesis = impact_generator(
                impact_context,
                client=impact_client,
                config=impact_config or get_ai_research_config(),
                generated_at=retrieved_at or datetime.now(UTC),
            )
        except Exception as exc:
            provenance.record_impact_failure(event=event, call_index=impact_calls, error=exc)
            cards.append(
                CatalystDeepDiveCard(
                    event=event,
                    impact_hypothesis=None,
                    missing_evidence=tuple(selected_context.selected_missing_data),
                    impact_error="分析暫時無法產生；此事件未進行自動重試。",
                )
            )
        else:
            provenance.record_impact_success(
                event=event,
                call_index=impact_calls,
                hypothesis=hypothesis,
            )
            cards.append(
                CatalystDeepDiveCard(
                    event=event,
                    impact_hypothesis=hypothesis,
                    missing_evidence=tuple(selected_context.selected_missing_data),
                )
            )

    result = CatalystDeepDiveResult(
        target_symbol=target.symbol,
        target_company_name=target.canonical_name,
        state="COMPLETED",
        message="Catalyst 深度分析已依已驗證事件完成更新。",
        cards=tuple(cards),
        validated_event_count=len(validated),
        omitted_validated_event_count=max(0, len(validated) - len(selected_events)),
        retrieval_request_count=1,
        impact_call_count=impact_calls,
    )
    return _finalize_with_provenance(
        result,
        provenance=provenance,
        run_status="COMPLETED_WITH_EVENT_FAILURES" if any(card.impact_error for card in cards) else "COMPLETED",
        completed_at=retrieved_at,
    )


def catalyst_result_for_symbol(
    results_by_symbol: dict[str, CatalystDeepDiveResult],
    symbol: str,
) -> CatalystDeepDiveResult | None:
    """Return only the current company's session result; never reuse another symbol."""
    result = results_by_symbol.get(symbol)
    return result if result is not None and result.target_symbol == symbol else None


def catalyst_card_display(card: CatalystDeepDiveCard) -> dict[str, object]:
    """Expose program-owned display fields; factual event fields never come from AI text."""
    event = card.event
    temporal_value = event.event_temporal_value
    display: dict[str, object] = {
        "事件日期": temporal_value.isoformat() if temporal_value is not None else "未確認",
        "事件類型": event.event_type.value,
        "發生了什麼": event.event_fact,
        "事件來源數量": event.support_count,
        "仍缺少的證據": tuple(item.reason for item in card.missing_evidence),
    }
    if card.impact_hypothesis is None:
        display["分析狀態"] = card.impact_error or "分析暫時無法產生。"
        return display

    impact = card.impact_hypothesis
    display.update({
        "影響面向": impact.impact_channel.value,
        "可能的影響路徑": impact.hypothesis_text,
        "為什麼可能重要": impact.why_it_matters_text,
        "限制 / 反證": impact.contradiction_or_limit_text,
        "不確定性": impact.uncertainty_text,
        "下一步要查什麼": impact.next_checks,
        "證據狀態": impact.hypothesis_status.value,
        "支持證據數": len(impact.supporting_evidence_refs),
        "反證數": len(impact.contradictory_evidence_refs),
    })
    return display


def _target_from_context(context: SelectedResearchContext) -> TargetCompanyIdentity:
    symbol = (context.symbol or "").strip().upper()
    company_name = (context.display_name or "").strip()
    if not symbol or not company_name:
        raise ValueError("Catalyst 深度分析需要目前選定公司的股票代號與公司名稱。")
    return TargetCompanyIdentity(symbol=symbol, canonical_name=company_name)


def _ordered_validated_events(
    events: tuple[ValidatedCatalystEvent, ...],
) -> tuple[ValidatedCatalystEvent, ...]:
    eligible = [
        event for event in events
        if event.validation_status is EventValidationStatus.VALIDATED
    ]
    return tuple(sorted(eligible, key=lambda event: (-_event_ordinal(event), event.event_id)))


def _event_ordinal(event: ValidatedCatalystEvent) -> int:
    value = event.event_temporal_value
    if isinstance(value, datetime):
        return value.date().toordinal()
    if isinstance(value, date):
        return value.toordinal()
    return -1


def _openai_api_key_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def _runtime_known_secrets() -> tuple[str, ...]:
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    return (value,) if value else ()


def _default_provenance_directory() -> Path:
    from catalyst_runtime_provenance import DEFAULT_RUNTIME_PROVENANCE_DIRECTORY

    return DEFAULT_RUNTIME_PROVENANCE_DIRECTORY


def _finalize_with_provenance(
    result: CatalystDeepDiveResult,
    *,
    provenance: CatalystRuntimeProvenanceRun,
    run_status: str,
    completed_at: datetime | None,
) -> CatalystDeepDiveResult:
    try:
        provenance.finalize_and_persist(run_status=run_status, completed_at=completed_at)
    except Exception:
        return replace(
            result,
            provenance_run_id=provenance.run_id,
            provenance_status="PROVENANCE_PERSIST_FAILED",
            provenance_warning="Catalyst 分析結果已保留，但本次本機追溯紀錄未能寫入。",
        )
    return replace(
        result,
        provenance_run_id=provenance.run_id,
        provenance_status="PROVENANCE_SAVED",
    )


def _result(
    target: TargetCompanyIdentity,
    state: str,
    message: str,
    *,
    retrieval_request_count: int = 0,
) -> CatalystDeepDiveResult:
    return CatalystDeepDiveResult(
        target_symbol=target.symbol,
        target_company_name=target.canonical_name,
        state=state,
        message=message,
        retrieval_request_count=retrieval_request_count,
    )
