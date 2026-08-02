from dataclasses import dataclass
from dataclasses import fields
from dataclasses import is_dataclass
from dataclasses import replace
from enum import Enum
import math
from numbers import Real
from typing import Any

from research_context import EvidenceItem
from research_context import MissingDataItem
from research_context import ObservationEvidenceLink
from research_context import ResearchContext
from research_context import ResearchLimitation
from research_context import json_safe_value
from research_service import ResearchNextStep
from research_service import ResearchObservation


class SelectionError(Exception):
    """Raised when deterministic research context selection is invalid."""


class ResearchQuestionType(Enum):
    COMPANY_OVERVIEW = "company_overview"
    PROFITABILITY = "profitability"
    GROWTH = "growth"
    FINANCIAL_HEALTH = "financial_health"
    VALUATION = "valuation"
    MARKET_POSITION = "market_position"
    HISTORICAL_REVENUE = "historical_revenue"
    HISTORICAL_EARNINGS = "historical_earnings"
    HISTORICAL_MARGINS = "historical_margins"
    HISTORICAL_CASH_FLOW = "historical_cash_flow"
    HISTORICAL_FINANCIAL_POSITION = "historical_financial_position"
    RISKS_AND_ATTENTION = "risks_and_attention"
    RESEARCH_NEXT_STEPS = "research_next_steps"
    GENERAL_RESEARCH = "general_research"


@dataclass(frozen=True)
class ResearchSelectionRequest:
    question_type: ResearchQuestionType
    max_evidence: int | None = None
    include_observations: bool = True
    include_missing_data: bool = True
    include_limitations: bool = True


@dataclass(frozen=True)
class SelectedResearchContext:
    symbol: str | None
    display_name: str | None
    question_type: ResearchQuestionType
    selected_evidence: list[EvidenceItem]
    selected_observation_links: list[ObservationEvidenceLink]
    selected_observations: list[ResearchObservation]
    selected_missing_data: list[MissingDataItem]
    selected_limitations: list[ResearchLimitation]
    selection_notes: list[str]
    generated_at: Any
    source_context_generated_at: Any
    source_evidence_count: int

    def to_dict(self) -> dict[str, Any]:
        payload = json_safe_value(self)
        payload["question_type"] = self.question_type.value
        return payload


COMPANY_OVERVIEW_METRICS = {
    "sector",
    "industry",
    "market_cap",
}

PROFITABILITY_METRICS = {
    "return_on_equity",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "trailing_eps",
}

GROWTH_METRICS = {
    "revenue_growth",
    "earnings_growth",
    "revenue",
    "revenue_yoy",
    "net_income",
    "eps",
    "eps_yoy",
}

FINANCIAL_HEALTH_METRICS = {
    "total_cash",
    "total_debt",
    "debt_to_equity",
    "operating_cash_flow",
    "free_cash_flow",
    "cash_and_cash_equivalents",
}

VALUATION_METRICS = {
    "trailing_pe",
    "forward_pe",
    "price_to_book",
    "trailing_eps",
    "earnings_growth",
    "eps",
    "net_income",
    "revenue",
}

MARKET_POSITION_METRICS = {
    "current_price",
    "fifty_two_week_high",
    "fifty_two_week_low",
    "fifty_day_average",
    "two_hundred_day_average",
    "fifty_two_week_position",
}

HISTORICAL_REVENUE_METRICS = {
    "revenue",
    "revenue_yoy",
}

HISTORICAL_EARNINGS_METRICS = {
    "net_income",
    "eps",
    "eps_yoy",
}

HISTORICAL_MARGINS_METRICS = {
    "gross_margin",
    "operating_margin",
    "net_margin",
    "gross_profit",
    "operating_income",
    "net_income",
}

HISTORICAL_CASH_FLOW_METRICS = {
    "operating_cash_flow",
    "capital_expenditure",
    "free_cash_flow",
    "net_income",
}

HISTORICAL_FINANCIAL_POSITION_METRICS = {
    "total_assets",
    "total_debt",
    "total_equity",
    "cash_and_cash_equivalents",
}

GENERAL_RESEARCH_METRICS = (
    COMPANY_OVERVIEW_METRICS
    | PROFITABILITY_METRICS
    | {"revenue_growth", "earnings_growth"}
    | {"revenue", "revenue_yoy", "net_income", "eps", "eps_yoy"}
    | {"trailing_pe", "forward_pe", "price_to_book"}
    | FINANCIAL_HEALTH_METRICS
    | MARKET_POSITION_METRICS
    | {"gross_margin", "operating_margin", "net_margin"}
)


QUESTION_METRIC_POLICY = {
    ResearchQuestionType.COMPANY_OVERVIEW: COMPANY_OVERVIEW_METRICS,
    ResearchQuestionType.PROFITABILITY: PROFITABILITY_METRICS | HISTORICAL_MARGINS_METRICS | {"eps"},
    ResearchQuestionType.GROWTH: GROWTH_METRICS,
    ResearchQuestionType.FINANCIAL_HEALTH: FINANCIAL_HEALTH_METRICS | HISTORICAL_CASH_FLOW_METRICS | HISTORICAL_FINANCIAL_POSITION_METRICS,
    ResearchQuestionType.VALUATION: VALUATION_METRICS,
    ResearchQuestionType.MARKET_POSITION: MARKET_POSITION_METRICS,
    ResearchQuestionType.HISTORICAL_REVENUE: HISTORICAL_REVENUE_METRICS,
    ResearchQuestionType.HISTORICAL_EARNINGS: HISTORICAL_EARNINGS_METRICS,
    ResearchQuestionType.HISTORICAL_MARGINS: HISTORICAL_MARGINS_METRICS,
    ResearchQuestionType.HISTORICAL_CASH_FLOW: HISTORICAL_CASH_FLOW_METRICS,
    ResearchQuestionType.HISTORICAL_FINANCIAL_POSITION: HISTORICAL_FINANCIAL_POSITION_METRICS,
    ResearchQuestionType.RISKS_AND_ATTENTION: set(),
    ResearchQuestionType.RESEARCH_NEXT_STEPS: set(),
    ResearchQuestionType.GENERAL_RESEARCH: GENERAL_RESEARCH_METRICS,
}

HISTORICAL_SPECIFIC_TYPES = {
    ResearchQuestionType.HISTORICAL_REVENUE,
    ResearchQuestionType.HISTORICAL_EARNINGS,
    ResearchQuestionType.HISTORICAL_MARGINS,
    ResearchQuestionType.HISTORICAL_CASH_FLOW,
    ResearchQuestionType.HISTORICAL_FINANCIAL_POSITION,
}

CURRENT_FOCUSED_HISTORICAL_WINDOW = 3

LIMITATION_POLICY = {
    ResearchQuestionType.MARKET_POSITION: {"currency", "freshness"},
    ResearchQuestionType.COMPANY_OVERVIEW: {"missing_data", "currency"},
}


def select_research_context(
    context: ResearchContext,
    request: ResearchSelectionRequest,
) -> SelectedResearchContext:
    validate_selection_request(request)

    evidence_by_id = {item.id: item for item in context.evidence}
    selected_metrics = set(QUESTION_METRIC_POLICY[request.question_type])
    selected_periods = selected_historical_periods(context, request.question_type)
    seed_ids = initial_evidence_ids(context.evidence, request.question_type, selected_metrics, selected_periods)

    observation_links = []
    observations = []
    next_step_metrics = selected_next_step_metrics(context, request.question_type)

    if request.include_observations:
        observation_links = select_observation_links(
            context,
            request.question_type,
            selected_metrics,
            seed_ids,
            next_step_metrics,
            selected_periods,
            evidence_by_id,
        )
        observations = materialize_observations(context, observation_links)
        for link in observation_links:
            seed_ids.update(link.evidence_ids)

    selected_ids = include_evidence_lineage(seed_ids, evidence_by_id)
    notes = build_selection_notes(context, request, selected_periods)
    selected_ids, budget_applied = apply_evidence_budget(
        selected_ids,
        evidence_by_id,
        request.max_evidence,
        request.question_type,
    )
    if budget_applied:
        notes.append("evidence budget applied with atomic lineage groups")

    selected_evidence = sort_evidence_items([evidence_by_id[item_id] for item_id in selected_ids])

    if request.include_observations:
        observation_links = [
            link for link in observation_links
            if all(item in selected_ids for item in link.evidence_ids)
        ]
        observations = materialize_observations(context, observation_links)

    selected_missing = []
    if request.include_missing_data:
        linked_missing_ids = {
            missing_id
            for link in observation_links
            for missing_id in link.missing_data_ids
        }
        selected_missing = select_missing_data(
            context.missing_data,
            request.question_type,
            selected_metrics | next_step_metrics,
            selected_periods,
            linked_missing_ids,
        )
        if len(selected_missing) < len([
            item for item in context.missing_data
            if item.metric in selected_metrics or item.id in linked_missing_ids
        ]):
            notes.append("missing-data items deduplicated")
        selected_missing_ids = {item.id for item in selected_missing}
        observation_links = [
            link for link in observation_links
            if all(item in selected_missing_ids for item in link.missing_data_ids)
        ]
        observations = materialize_observations(context, observation_links)

    selected_limitations = []
    if request.include_limitations:
        selected_limitations = select_limitations(
            context.limitations,
            request.question_type,
            bool(selected_periods),
        )

    selected = SelectedResearchContext(
        symbol=context.symbol,
        display_name=context.display_name,
        question_type=request.question_type,
        selected_evidence=selected_evidence,
        selected_observation_links=observation_links,
        selected_observations=observations,
        selected_missing_data=selected_missing,
        selected_limitations=selected_limitations,
        selection_notes=notes,
        generated_at=context.generated_at,
        source_context_generated_at=context.generated_at,
        source_evidence_count=len(context.evidence),
    )
    validate_selected_research_context(selected)
    return selected


def validate_selection_request(request: ResearchSelectionRequest) -> None:
    if not isinstance(request.question_type, ResearchQuestionType):
        raise SelectionError("question_type must be a ResearchQuestionType.")
    if request.max_evidence is not None and request.max_evidence < 1:
        raise SelectionError("max_evidence must be greater than or equal to 1.")


def selected_historical_periods(
    context: ResearchContext,
    question_type: ResearchQuestionType,
) -> set[str]:
    historical = context.historical_financials
    if historical is None:
        return set()

    all_periods = sorted(period.period_end.isoformat() for period in historical.periods)
    if question_type in HISTORICAL_SPECIFIC_TYPES or question_type == ResearchQuestionType.GENERAL_RESEARCH:
        return set(all_periods)
    if question_type == ResearchQuestionType.MARKET_POSITION:
        return set()
    return set(all_periods[-CURRENT_FOCUSED_HISTORICAL_WINDOW:])


def initial_evidence_ids(
    evidence: list[EvidenceItem],
    question_type: ResearchQuestionType,
    selected_metrics: set[str],
    selected_periods: set[str],
) -> set[str]:
    if question_type in {
        ResearchQuestionType.RISKS_AND_ATTENTION,
        ResearchQuestionType.RESEARCH_NEXT_STEPS,
    }:
        return set()

    ids = set()
    for item in evidence:
        if item.metric not in selected_metrics:
            continue
        if item.period_end is not None and item.period_end.isoformat() not in selected_periods:
            continue
        if question_type == ResearchQuestionType.COMPANY_OVERVIEW and item.id.startswith("historical:"):
            continue
        ids.add(item.id)
    return ids


def include_evidence_lineage(
    selected_ids: set[str],
    evidence_by_id: dict[str, EvidenceItem],
) -> set[str]:
    resolved = set()
    visiting = set()

    def visit(evidence_id: str) -> None:
        if evidence_id in resolved:
            return
        if evidence_id in visiting:
            raise SelectionError(f"Circular evidence lineage detected: {evidence_id}")
        if evidence_id not in evidence_by_id:
            raise SelectionError(f"Selected evidence references missing ID: {evidence_id}")
        visiting.add(evidence_id)
        for source_id in evidence_by_id[evidence_id].derived_from:
            visit(source_id)
        visiting.remove(evidence_id)
        resolved.add(evidence_id)

    for selected_id in sorted(selected_ids):
        visit(selected_id)
    return resolved


def select_observation_links(
    context: ResearchContext,
    question_type: ResearchQuestionType,
    selected_metrics: set[str],
    seed_ids: set[str],
    next_step_metrics: set[str],
    selected_periods: set[str],
    evidence_by_id: dict[str, EvidenceItem],
) -> list[ObservationEvidenceLink]:
    links = []
    effective_metrics = selected_metrics | next_step_metrics
    for link in context.observation_links:
        scoped_link = scope_observation_link(
            link,
            question_type,
            effective_metrics,
            selected_periods,
            evidence_by_id,
        )
        if scoped_link is None:
            continue
        if question_type == ResearchQuestionType.RISKS_AND_ATTENTION:
            if scoped_link.observation_scope == "current" or scoped_link.category.startswith(("Risk", "Data Quality")):
                links.append(scoped_link)
            continue
        if question_type == ResearchQuestionType.RESEARCH_NEXT_STEPS:
            if scoped_link.metric in next_step_metrics or intersects(scoped_link.evidence_ids, seed_ids):
                links.append(scoped_link)
            continue
        if question_type == ResearchQuestionType.GENERAL_RESEARCH:
            if scoped_link.metric in effective_metrics or intersects(scoped_link.evidence_ids, seed_ids):
                links.append(scoped_link)
            continue
        if scoped_link.metric in effective_metrics or intersects(scoped_link.evidence_ids, seed_ids):
            links.append(scoped_link)
    return sort_observation_links(links)


def scope_observation_link(
    link: ObservationEvidenceLink,
    question_type: ResearchQuestionType,
    selected_metrics: set[str],
    selected_periods: set[str],
    evidence_by_id: dict[str, EvidenceItem],
) -> ObservationEvidenceLink | None:
    if question_type in {
        ResearchQuestionType.RISKS_AND_ATTENTION,
        ResearchQuestionType.RESEARCH_NEXT_STEPS,
    }:
        return link

    scoped_evidence_ids = []
    for evidence_id in link.evidence_ids:
        item = evidence_by_id.get(evidence_id)
        if item is None:
            continue
        if item.metric not in selected_metrics:
            continue
        if item.period_end is not None and item.period_end.isoformat() not in selected_periods:
            continue
        scoped_evidence_ids.append(evidence_id)

    scoped_missing_ids = tuple(
        missing_id for missing_id in link.missing_data_ids
        if missing_id_matches_metrics(missing_id, selected_metrics)
    )
    if not scoped_evidence_ids and not scoped_missing_ids:
        return None
    return replace(
        link,
        evidence_ids=tuple(scoped_evidence_ids),
        missing_data_ids=scoped_missing_ids,
    )


def missing_id_matches_metrics(missing_id: str, selected_metrics: set[str]) -> bool:
    parts = missing_id.split(":")
    if len(parts) < 3:
        return False
    return parts[2] in selected_metrics


def selected_next_step_metrics(
    context: ResearchContext,
    question_type: ResearchQuestionType,
) -> set[str]:
    if question_type != ResearchQuestionType.RESEARCH_NEXT_STEPS:
        return set()
    metrics = set()
    for next_step in context.fundamental_research.next_steps:
        metrics.add(next_step.metric)
    if context.historical_research is not None:
        for next_step in context.historical_research.next_steps:
            metrics.add(next_step.metric)
    return metrics


def materialize_observations(
    context: ResearchContext,
    links: list[ObservationEvidenceLink],
) -> list[ResearchObservation]:
    observations = []
    for link in links:
        source = observation_source_for_link(context, link)
        if source is None:
            continue
        if 0 <= link.observation_index < len(source):
            observations.append(source[link.observation_index])
    return observations


def observation_source_for_link(
    context: ResearchContext,
    link: ObservationEvidenceLink,
) -> list[ResearchObservation] | None:
    if link.observation_scope == "current":
        return (
            context.fundamental_research.valuation_observations
            + context.fundamental_research.risk_signals
        )
    if link.observation_scope == "historical" and context.historical_research is not None:
        return context.historical_research.observations
    return None


def select_missing_data(
    missing_data: list[MissingDataItem],
    question_type: ResearchQuestionType,
    selected_metrics: set[str],
    selected_periods: set[str],
    linked_missing_ids: set[str],
) -> list[MissingDataItem]:
    selected = []
    for item in missing_data:
        if item.id in linked_missing_ids:
            selected.append(item)
            continue
        if question_type == ResearchQuestionType.GENERAL_RESEARCH:
            if item.metric in GENERAL_RESEARCH_METRICS or item.id == "missing:historical:series":
                selected.append(item)
            continue
        if item.metric in selected_metrics:
            if item.period_end is None or not selected_periods or item.period_end.isoformat() in selected_periods:
                selected.append(item)
    return denoise_missing_data(selected)


def denoise_missing_data(items: list[MissingDataItem]) -> list[MissingDataItem]:
    by_id = {item.id: item for item in items}
    drop_ids = set()
    for item in items:
        if not item.metric.endswith("_yoy") or item.period_end is None:
            continue
        base_metric = item.metric.removesuffix("_yoy")
        source_id = f"missing:historical:{base_metric}:{item.period_end.isoformat()}"
        if source_id in by_id:
            drop_ids.add(item.id)
    return sorted(
        [item for item in items if item.id not in drop_ids],
        key=lambda item: (
            item.period_end.isoformat() if item.period_end else "",
            item.area,
            item.metric,
            item.id,
        ),
    )


def select_limitations(
    limitations: list[ResearchLimitation],
    question_type: ResearchQuestionType,
    has_historical_periods: bool,
) -> list[ResearchLimitation]:
    selected = []
    allowed_categories = LIMITATION_POLICY.get(question_type)
    for item in limitations:
        if allowed_categories is not None:
            if item.category in allowed_categories:
                selected.append(item)
            continue
        if question_type in HISTORICAL_SPECIFIC_TYPES:
            if item.scope == "global" or item.category in {"missing_data", "freshness", "currency"}:
                selected.append(item)
            continue
        if question_type == ResearchQuestionType.GENERAL_RESEARCH:
            selected.append(item)
            continue
        if item.id == "global:no_fx_conversion" or item.scope == "context":
            selected.append(item)
        elif has_historical_periods and item.id in {
            "global:annual_historical_data_only",
            "global:no_quarterly_or_ttm",
        }:
            selected.append(item)
    return selected


def apply_evidence_budget(
    selected_ids: set[str],
    evidence_by_id: dict[str, EvidenceItem],
    max_evidence: int | None,
    question_type: ResearchQuestionType,
) -> tuple[set[str], bool]:
    if max_evidence is None or len(selected_ids) <= max_evidence:
        return selected_ids, False

    groups = []
    for evidence_id in selected_ids:
        group_ids = include_evidence_lineage({evidence_id}, evidence_by_id)
        groups.append(group_ids)

    selected = set()
    for group in sorted(groups, key=lambda group: group_priority_key(group, evidence_by_id, question_type)):
        if len(selected | group) <= max_evidence:
            selected.update(group)

    if not selected:
        first_group = sorted(groups, key=lambda group: group_priority_key(group, evidence_by_id, question_type))[0]
        selected.update(first_group)
    return selected, True


def group_priority_key(
    group: set[str],
    evidence_by_id: dict[str, EvidenceItem],
    question_type: ResearchQuestionType,
) -> tuple[int, int, str]:
    items = [evidence_by_id[item_id] for item_id in group]
    latest_period = max((item.period_end.isoformat() for item in items if item.period_end), default="")
    type_rank = min(evidence_priority(item, question_type) for item in items)
    return (type_rank, -period_sort_value(latest_period), sorted(group)[0])


def period_sort_value(period: str) -> int:
    if not period:
        return 0
    return int(period.replace("-", ""))


def evidence_priority(item: EvidenceItem, question_type: ResearchQuestionType) -> int:
    if item.source_type == "derived":
        return 1
    if item.id.startswith("current:"):
        return 2
    if item.period_end is not None:
        return 3
    if question_type == ResearchQuestionType.COMPANY_OVERVIEW:
        return 0
    return 4


def build_selection_notes(
    context: ResearchContext,
    request: ResearchSelectionRequest,
    selected_periods: set[str],
) -> list[str]:
    notes = []
    if selected_periods:
        if request.question_type in HISTORICAL_SPECIFIC_TYPES or request.question_type == ResearchQuestionType.GENERAL_RESEARCH:
            notes.append("selected all available annual periods within metric scope")
        else:
            notes.append(f"selected latest {len(selected_periods)} historical periods within metric scope")
    if request.question_type not in {
        ResearchQuestionType.HISTORICAL_CASH_FLOW,
        ResearchQuestionType.FINANCIAL_HEALTH,
        ResearchQuestionType.GENERAL_RESEARCH,
    }:
        notes.append("omitted unrelated cash-flow and balance-sheet evidence when outside metric scope")
    if len(context.evidence) > 0:
        notes.append("selected context is a deterministic subset of source ResearchContext")
    return notes


def validate_selected_research_context(selected: SelectedResearchContext) -> None:
    if not isinstance(selected.question_type, ResearchQuestionType):
        raise SelectionError("Selected question_type is invalid.")
    ensure_no_non_finite(selected)

    evidence_ids = [item.id for item in selected.selected_evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise SelectionError("Selected evidence IDs must be unique.")
    evidence_id_set = set(evidence_ids)
    for item in selected.selected_evidence:
        for source_id in item.derived_from:
            if source_id not in evidence_id_set:
                raise SelectionError(f"Derived evidence lineage incomplete: {item.id}")

    missing_ids = [item.id for item in selected.selected_missing_data]
    if len(missing_ids) != len(set(missing_ids)):
        raise SelectionError("Selected missing-data IDs must be unique.")
    missing_id_set = set(missing_ids)

    for link in selected.selected_observation_links:
        for evidence_id in link.evidence_ids:
            if evidence_id not in evidence_id_set:
                raise SelectionError(f"Selected observation link references missing evidence: {link.id}")
        for missing_data_id in link.missing_data_ids:
            if missing_data_id not in missing_id_set:
                raise SelectionError(f"Selected observation link references missing data: {link.id}")

    json_safe_value(selected)


def ensure_no_non_finite(value) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, Real):
        if not math.isfinite(float(value)):
            raise SelectionError("Selected context contains non-finite numeric value.")
        return
    if isinstance(value, (str, bytes)):
        return
    if isinstance(value, dict):
        for item in value.values():
            ensure_no_non_finite(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            ensure_no_non_finite(item)
        return
    if is_dataclass(value):
        for field in fields(value):
            ensure_no_non_finite(getattr(value, field.name))


def sort_evidence_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    return sorted(
        items,
        key=lambda item: (
            item.period_end.isoformat() if item.period_end else "",
            item.category,
            item.metric,
            item.id,
        ),
    )


def sort_observation_links(links: list[ObservationEvidenceLink]) -> list[ObservationEvidenceLink]:
    return sorted(links, key=lambda item: (item.observation_scope, item.category, item.metric, item.id))


def intersects(left: tuple[str, ...], right: set[str]) -> bool:
    return any(item in right for item in left)
