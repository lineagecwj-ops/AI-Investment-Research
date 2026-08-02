from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
import hashlib
import json
import re
from typing import Any

from ai_research_service import AIResponseMetadata
from ai_research_service import GroundedResearchAnswer
from research_context_selector import ResearchQuestionType
from research_context_selector import SelectedResearchContext
from research_service import ResearchNextStep


MAX_RESEARCH_TURNS = 5
FOLLOWUP_SUGGESTION_LIMIT = 5


@dataclass(frozen=True)
class FollowUpResearchSuggestion:
    id: str
    title: str
    question: str
    question_type: ResearchQuestionType
    source: str
    related_metrics: tuple[str, ...] = ()


@dataclass(frozen=True)
class AIResearchTurn:
    turn_id: str
    parent_turn_id: str | None
    symbol: str
    question_type: ResearchQuestionType
    question: str
    fingerprint: str
    answer: GroundedResearchAnswer
    metadata: AIResponseMetadata
    selected_context: SelectedResearchContext
    generated_at: datetime


@dataclass
class AIResearchSession:
    symbol: str
    display_name: str | None = None
    turns: list[AIResearchTurn] | None = None
    api_request_count: int = 0
    last_error: str | None = None
    last_error_details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.turns is None:
            self.turns = []

    @property
    def turn_count(self) -> int:
        return len(self.turns or [])

    @property
    def can_add_turn(self) -> bool:
        return self.turn_count < MAX_RESEARCH_TURNS


KEYWORD_ROUTING_RULES: tuple[tuple[tuple[str, ...], ResearchQuestionType], ...] = (
    (
        (
            "gross margin",
            "operating margin",
            "net margin",
            "margin",
            "毛利",
            "營業利益率",
            "營益率",
            "淨利率",
            "利潤率",
        ),
        ResearchQuestionType.HISTORICAL_MARGINS,
    ),
    (
        ("free cash flow", "cash flow", "fcf", "ocf", "現金流", "自由現金流", "營業現金流"),
        ResearchQuestionType.HISTORICAL_CASH_FLOW,
    ),
    (
        ("forward p/e", "trailing p/e", "p/e", "pe", "p/b", "valuation", "估值", "本益比", "股價淨值比"),
        ResearchQuestionType.VALUATION,
    ),
    (
        ("debt", "assets", "asset", "equity", "cash", "負債", "資產", "權益", "現金", "財務結構"),
        ResearchQuestionType.HISTORICAL_FINANCIAL_POSITION,
    ),
    (
        ("52-week", "52 week", "200-day", "200 day", "price position", "market position", "52 週", "200 日", "市場位置", "股價位置"),
        ResearchQuestionType.MARKET_POSITION,
    ),
    (
        ("risk", "attention", "風險", "注意", "值得注意"),
        ResearchQuestionType.RISKS_AND_ATTENTION,
    ),
    (
        ("eps", "earnings", "earning", "盈餘", "每股盈餘", "獲利"),
        ResearchQuestionType.HISTORICAL_EARNINGS,
    ),
    (
        ("revenue", "sales", "營收", "收入"),
        ResearchQuestionType.HISTORICAL_REVENUE,
    ),
    (
        ("roe", "profitability", "獲利能力"),
        ResearchQuestionType.PROFITABILITY,
    ),
)


FOLLOWUP_POLICY: dict[ResearchQuestionType, tuple[ResearchQuestionType, ...]] = {
    ResearchQuestionType.GROWTH: (
        ResearchQuestionType.HISTORICAL_REVENUE,
        ResearchQuestionType.HISTORICAL_EARNINGS,
        ResearchQuestionType.HISTORICAL_MARGINS,
        ResearchQuestionType.HISTORICAL_CASH_FLOW,
    ),
    ResearchQuestionType.VALUATION: (
        ResearchQuestionType.PROFITABILITY,
        ResearchQuestionType.GROWTH,
        ResearchQuestionType.HISTORICAL_EARNINGS,
    ),
    ResearchQuestionType.FINANCIAL_HEALTH: (
        ResearchQuestionType.HISTORICAL_CASH_FLOW,
        ResearchQuestionType.HISTORICAL_FINANCIAL_POSITION,
    ),
    ResearchQuestionType.PROFITABILITY: (
        ResearchQuestionType.HISTORICAL_MARGINS,
        ResearchQuestionType.HISTORICAL_EARNINGS,
        ResearchQuestionType.HISTORICAL_CASH_FLOW,
    ),
    ResearchQuestionType.MARKET_POSITION: (
        ResearchQuestionType.VALUATION,
        ResearchQuestionType.RISKS_AND_ATTENTION,
    ),
    ResearchQuestionType.RISKS_AND_ATTENTION: (
        ResearchQuestionType.FINANCIAL_HEALTH,
        ResearchQuestionType.HISTORICAL_CASH_FLOW,
        ResearchQuestionType.MARKET_POSITION,
    ),
    ResearchQuestionType.GENERAL_RESEARCH: (
        ResearchQuestionType.GROWTH,
        ResearchQuestionType.PROFITABILITY,
        ResearchQuestionType.VALUATION,
        ResearchQuestionType.HISTORICAL_CASH_FLOW,
    ),
}


DEFAULT_SUGGESTIONS: dict[ResearchQuestionType, tuple[tuple[str, str, ResearchQuestionType, tuple[str, ...]], ...]] = {
    ResearchQuestionType.GROWTH: (
        (
            "比較 Revenue / EPS 歷史趨勢",
            "請比較近年 Revenue、Net Income 與 EPS 的歷史變化，並指出目前資料缺口。",
            ResearchQuestionType.HISTORICAL_EARNINGS,
            ("revenue", "net_income", "eps"),
        ),
        (
            "檢查利潤率是否同步變化",
            "請比較近年 Gross Margin、Operating Margin 與 Net Margin 的變化。",
            ResearchQuestionType.HISTORICAL_MARGINS,
            ("gross_margin", "operating_margin", "net_margin"),
        ),
        (
            "查看 Free Cash Flow",
            "請整理近年 Operating Cash Flow、Free Cash Flow 與 Capital Expenditure 的變化。",
            ResearchQuestionType.HISTORICAL_CASH_FLOW,
            ("operating_cash_flow", "free_cash_flow", "capital_expenditure"),
        ),
    ),
    ResearchQuestionType.VALUATION: (
        (
            "比較 Trailing / Forward P/E",
            "請整理 Trailing P/E、Forward P/E 與 P/B 的目前估值資料限制。",
            ResearchQuestionType.VALUATION,
            ("trailing_pe", "forward_pe", "price_to_book"),
        ),
        (
            "查看 earnings context",
            "請比較近年 Net Income 與 EPS 的變化，作為估值研究背景。",
            ResearchQuestionType.HISTORICAL_EARNINGS,
            ("net_income", "eps"),
        ),
        (
            "檢查獲利能力",
            "請整理 ROE 與 Margin 資料，說明目前獲利能力證據與限制。",
            ResearchQuestionType.PROFITABILITY,
            ("return_on_equity", "gross_margin", "operating_margin", "net_margin"),
        ),
    ),
    ResearchQuestionType.FINANCIAL_HEALTH: (
        (
            "查看 Cash Flow 歷史",
            "請整理近年 Operating Cash Flow 與 Free Cash Flow 的變化。",
            ResearchQuestionType.HISTORICAL_CASH_FLOW,
            ("operating_cash_flow", "free_cash_flow"),
        ),
        (
            "檢查財務結構",
            "請比較近年 Cash、Total Debt、Total Assets 與 Total Equity 的變化。",
            ResearchQuestionType.HISTORICAL_FINANCIAL_POSITION,
            ("cash_and_cash_equivalents", "total_debt", "total_assets", "total_equity"),
        ),
    ),
    ResearchQuestionType.GENERAL_RESEARCH: (
        (
            "研究成長資料",
            "請整理 Revenue、Earnings 與 EPS 的成長資料與限制。",
            ResearchQuestionType.GROWTH,
            ("revenue_growth", "earnings_growth", "eps"),
        ),
        (
            "研究獲利能力",
            "請整理 ROE、Gross Margin、Operating Margin 與 Net Margin 的資料。",
            ResearchQuestionType.PROFITABILITY,
            ("return_on_equity", "gross_margin", "operating_margin", "net_margin"),
        ),
        (
            "研究估值資料",
            "請整理 Trailing P/E、Forward P/E 與 P/B 的目前資料。",
            ResearchQuestionType.VALUATION,
            ("trailing_pe", "forward_pe", "price_to_book"),
        ),
    ),
}


FALLBACK_GENERAL_SUGGESTIONS = DEFAULT_SUGGESTIONS[ResearchQuestionType.GENERAL_RESEARCH]


def normalize_followup_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip()).lower()


def infer_followup_question_type(
    question: str,
    default_type: ResearchQuestionType | None = None,
) -> ResearchQuestionType:
    normalized = normalize_followup_question(question)
    if not normalized:
        return default_type or ResearchQuestionType.GENERAL_RESEARCH

    for keywords, question_type in KEYWORD_ROUTING_RULES:
        if any(keyword.lower() in normalized for keyword in keywords):
            return question_type
    return default_type or ResearchQuestionType.GENERAL_RESEARCH


def build_followup_suggestions(
    *,
    current_question_type: ResearchQuestionType,
    answer_next_steps: list[str] | tuple[str, ...] | None = None,
    selected_context: SelectedResearchContext | None = None,
    deterministic_next_steps: list[ResearchNextStep] | tuple[ResearchNextStep, ...] | None = None,
    limit: int = FOLLOWUP_SUGGESTION_LIMIT,
) -> list[FollowUpResearchSuggestion]:
    suggestions: list[FollowUpResearchSuggestion] = []

    for index, item in enumerate(answer_next_steps or [], start=1):
        question = item.strip()
        if not question:
            continue
        suggestions.append(
            make_suggestion(
                title=f"延伸研究方向 {index}",
                question=question,
                question_type=infer_followup_question_type(question, suggested_policy_default(current_question_type)),
                source="ai_next_step",
                related_metrics=(),
            )
        )

    for step in deterministic_next_steps or []:
        for item in step.items:
            question = item.strip()
            if not question:
                continue
            suggestions.append(
                make_suggestion(
                    title=step.title,
                    question=question,
                    question_type=infer_followup_question_type(question, suggested_policy_default(current_question_type)),
                    source="deterministic_next_step",
                    related_metrics=(step.metric,),
                )
            )

    if selected_context is not None:
        for missing in selected_context.selected_missing_data:
            if len(suggestions) >= limit:
                break
            metric = missing.metric.replace("_", " ").upper() if missing.metric else "資料"
            period = f" FY{missing.period_year}" if missing.period_year else ""
            question = f"請確認{period} {metric} 缺漏是否能從目前可靠資料中補齊，若仍不足請明確說明限制。"
            suggestions.append(
                make_suggestion(
                    title="確認缺漏資料",
                    question=question,
                    question_type=infer_followup_question_type(question, selected_context.question_type),
                    source="missing_data",
                    related_metrics=(missing.metric,),
                )
            )

    for title, question, question_type, metrics in default_suggestions_for(current_question_type):
        suggestions.append(
            make_suggestion(
                title=title,
                question=question,
                question_type=question_type,
                source="deterministic_fallback",
                related_metrics=metrics,
            )
        )

    return dedupe_suggestions(suggestions)[:limit]


def suggested_policy_default(question_type: ResearchQuestionType) -> ResearchQuestionType:
    policy = FOLLOWUP_POLICY.get(question_type)
    if policy:
        return policy[0]
    return ResearchQuestionType.GENERAL_RESEARCH


def default_suggestions_for(
    question_type: ResearchQuestionType,
) -> tuple[tuple[str, str, ResearchQuestionType, tuple[str, ...]], ...]:
    if question_type in DEFAULT_SUGGESTIONS:
        return DEFAULT_SUGGESTIONS[question_type]
    policy = FOLLOWUP_POLICY.get(question_type)
    if not policy:
        return FALLBACK_GENERAL_SUGGESTIONS

    generated = []
    for target_type in policy:
        generated.extend(DEFAULT_SUGGESTIONS.get(target_type, ()))
    return tuple(generated) if generated else FALLBACK_GENERAL_SUGGESTIONS


def make_suggestion(
    *,
    title: str,
    question: str,
    question_type: ResearchQuestionType,
    source: str,
    related_metrics: tuple[str, ...],
) -> FollowUpResearchSuggestion:
    suggestion_id = hashlib.sha256(
        json.dumps(
            {
                "question": normalize_followup_question(question),
                "question_type": question_type.value,
                "source": source,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:12]
    return FollowUpResearchSuggestion(
        id=suggestion_id,
        title=title.strip(),
        question=question.strip(),
        question_type=question_type,
        source=source,
        related_metrics=related_metrics,
    )


def dedupe_suggestions(
    suggestions: list[FollowUpResearchSuggestion],
) -> list[FollowUpResearchSuggestion]:
    deduped = []
    seen = set()
    for suggestion in suggestions:
        normalized = normalize_followup_question(suggestion.question)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(suggestion)
    return deduped


def build_turn_id(
    *,
    symbol: str,
    question_type: ResearchQuestionType,
    question: str,
    fingerprint: str,
    generated_at: datetime,
) -> str:
    payload = {
        "symbol": symbol,
        "question_type": question_type.value,
        "question": normalize_followup_question(question),
        "fingerprint": fingerprint,
        "generated_at": generated_at.isoformat(),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def create_research_turn(
    *,
    parent_turn_id: str | None,
    symbol: str,
    question_type: ResearchQuestionType,
    question: str,
    fingerprint: str,
    answer: GroundedResearchAnswer,
    selected_context: SelectedResearchContext,
    generated_at: datetime | None = None,
) -> AIResearchTurn:
    timestamp = generated_at or answer.metadata.generated_at or datetime.now(UTC)
    return AIResearchTurn(
        turn_id=build_turn_id(
            symbol=symbol,
            question_type=question_type,
            question=question,
            fingerprint=fingerprint,
            generated_at=timestamp,
        ),
        parent_turn_id=parent_turn_id,
        symbol=symbol,
        question_type=question_type,
        question=question.strip(),
        fingerprint=fingerprint,
        answer=answer,
        metadata=answer.metadata,
        selected_context=selected_context,
        generated_at=timestamp,
    )


def append_verified_turn(
    session: AIResearchSession,
    turn: AIResearchTurn,
    *,
    max_turns: int = MAX_RESEARCH_TURNS,
) -> AIResearchSession:
    if len(session.turns or []) >= max_turns:
        raise ValueError(f"此研究工作階段已達 {max_turns} 回合上限。")
    if session.symbol != turn.symbol:
        raise ValueError("turn symbol 與 session symbol 不一致。")
    session.turns.append(turn)
    session.last_error = None
    session.last_error_details = None
    return session


def aggregate_session_usage(turns: list[AIResearchTurn] | tuple[AIResearchTurn, ...]) -> dict[str, int]:
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
    }
    for turn in turns:
        usage = turn.metadata.usage if isinstance(turn.metadata.usage, dict) else {}
        totals["input_tokens"] += safe_int(usage.get("input_tokens"))
        totals["output_tokens"] += safe_int(usage.get("output_tokens"))
        totals["total_tokens"] += safe_int(usage.get("total_tokens"))
        totals["reasoning_tokens"] += safe_int(turn.metadata.reasoning_tokens)
    return totals


def safe_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value
