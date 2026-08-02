from dataclasses import dataclass
from datetime import date
import hashlib
import json
import os
from numbers import Real
from typing import Any

from ai_research_service import AIConfigurationError
from ai_research_service import AIIncompleteResponseError
from ai_research_service import AINumericGroundingError
from ai_research_service import AIRefusalError
from ai_research_service import AIResearchError
from ai_research_service import AIGroundingError
from ai_research_service import AIProviderError
from ai_research_service import AIStructuredOutputError
from research_context import EvidenceItem
from research_context import MissingDataItem
from research_context import ResearchLimitation
from research_context import json_safe_value
from research_context_selector import ResearchQuestionType
from research_context_selector import SelectedResearchContext


@dataclass(frozen=True)
class QuestionTypeDisplay:
    label: str
    help_text: str
    placeholder: str


QUESTION_TYPE_DISPLAY = {
    ResearchQuestionType.COMPANY_OVERVIEW: QuestionTypeDisplay(
        "Company Overview（公司概覽）",
        "聚焦公司基本資料、產業分類、市值與可用的公司摘要。",
        "請整理這家公司目前的基本面輪廓與需要補查的資訊。",
    ),
    ResearchQuestionType.PROFITABILITY: QuestionTypeDisplay(
        "Profitability（獲利能力）",
        "聚焦 ROE、Margins、EPS 與相關獲利品質資料。",
        "請整理目前獲利能力資料，並說明有哪些限制。",
    ),
    ResearchQuestionType.GROWTH: QuestionTypeDisplay(
        "Growth（成長）",
        "聚焦目前與歷史 Revenue、Earnings、EPS 成長資料。",
        "請說明近期與歷史營收、盈餘成長的主要變化。",
    ),
    ResearchQuestionType.FINANCIAL_HEALTH: QuestionTypeDisplay(
        "Financial Health（財務健康）",
        "聚焦 Cash、Debt、Debt to Equity、Operating Cash Flow 與 Free Cash Flow。",
        "請整理現金、負債與現金流資料，並列出下一步要確認的地方。",
    ),
    ResearchQuestionType.VALUATION: QuestionTypeDisplay(
        "Valuation（估值）",
        "聚焦 P/E、P/B、EPS 與相關估值觀察。",
        "請整理目前估值指標，並說明有哪些需要進一步確認的地方。",
    ),
    ResearchQuestionType.MARKET_POSITION: QuestionTypeDisplay(
        "Market Position（市場位置）",
        "聚焦目前價格、52 週區間與均價位置。",
        "請整理目前市場價格位置與可用證據。",
    ),
    ResearchQuestionType.HISTORICAL_REVENUE: QuestionTypeDisplay(
        "Historical Revenue（歷史營收）",
        "聚焦年度 Revenue 與 Revenue YoY。",
        "請說明近年 Revenue 與 Revenue YoY 的變化。",
    ),
    ResearchQuestionType.HISTORICAL_EARNINGS: QuestionTypeDisplay(
        "Historical Earnings（歷史獲利）",
        "聚焦年度 Net Income、EPS 與 EPS YoY。",
        "請說明近年 Net Income 與 EPS 資料的變化。",
    ),
    ResearchQuestionType.HISTORICAL_MARGINS: QuestionTypeDisplay(
        "Historical Margins（歷史利潤率）",
        "聚焦年度 Gross Margin、Operating Margin 與 Net Margin。",
        "請整理近年利潤率變化與可追蹤項目。",
    ),
    ResearchQuestionType.HISTORICAL_CASH_FLOW: QuestionTypeDisplay(
        "Historical Cash Flow（歷史現金流）",
        "聚焦年度 Operating Cash Flow、Free Cash Flow 與 Capital Expenditure。",
        "請整理近年現金流與資本支出的主要變化。",
    ),
    ResearchQuestionType.HISTORICAL_FINANCIAL_POSITION: QuestionTypeDisplay(
        "Historical Financial Position（歷史財務結構）",
        "聚焦年度 Cash、Total Debt、Total Assets 與 Total Equity。",
        "請整理近年財務結構資料與需要補查的項目。",
    ),
    ResearchQuestionType.RISKS_AND_ATTENTION: QuestionTypeDisplay(
        "Risks & Attention（值得注意事項）",
        "聚焦 deterministic observations 中需要進一步確認的資料點。",
        "請整理目前資料中最值得注意的研究觀察。",
    ),
    ResearchQuestionType.RESEARCH_NEXT_STEPS: QuestionTypeDisplay(
        "Research Next Steps（下一步研究）",
        "聚焦已選資料可支持的後續研究方向。",
        "請依目前資料整理下一步研究清單。",
    ),
    ResearchQuestionType.GENERAL_RESEARCH: QuestionTypeDisplay(
        "General Research（綜合研究）",
        "跨多個基本面與歷史面向進行綜合整理。",
        "請整理目前最值得注意的基本面與歷史趨勢。",
    ),
}


def question_type_options() -> list[ResearchQuestionType]:
    return list(QUESTION_TYPE_DISPLAY)


def normalize_question_type(question_type: ResearchQuestionType | str) -> ResearchQuestionType:
    if isinstance(question_type, ResearchQuestionType):
        return question_type
    value = getattr(question_type, "value", question_type)
    return ResearchQuestionType(str(value))


def question_type_label(question_type: ResearchQuestionType | str) -> str:
    return QUESTION_TYPE_DISPLAY[normalize_question_type(question_type)].label


def question_type_help(question_type: ResearchQuestionType | str) -> str:
    return QUESTION_TYPE_DISPLAY[normalize_question_type(question_type)].help_text


def question_type_placeholder(question_type: ResearchQuestionType | str) -> str:
    return QUESTION_TYPE_DISPLAY[normalize_question_type(question_type)].placeholder


def is_openai_api_configured(environ: dict[str, str] | None = None) -> bool:
    source = environ if environ is not None else os.environ
    return bool(source.get("OPENAI_API_KEY", "").strip())


def build_request_fingerprint(
    *,
    symbol: str | None,
    question_type: ResearchQuestionType,
    question: str,
    selected_context: SelectedResearchContext,
) -> str:
    payload = {
        "symbol": symbol,
        "question_type": question_type.value,
        "question": question.strip(),
        "selected_evidence_ids": [item.id for item in selected_context.selected_evidence],
        "selected_missing_data_ids": [item.id for item in selected_context.selected_missing_data],
        "selected_limitation_ids": [item.id for item in selected_context.selected_limitations],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def evidence_lookup(selected_context: SelectedResearchContext) -> dict[str, EvidenceItem]:
    return {item.id: item for item in selected_context.selected_evidence}


def resolve_evidence_lineage(
    evidence_id: str,
    selected_evidence: dict[str, EvidenceItem],
    *,
    visited: set[str] | None = None,
) -> list[EvidenceItem | str]:
    visited = visited or set()
    if evidence_id in visited:
        return []
    visited.add(evidence_id)

    evidence = selected_evidence.get(evidence_id)
    if evidence is None:
        return [evidence_id]

    lineage: list[EvidenceItem | str] = []
    for source_id in evidence.derived_from:
        source_evidence = selected_evidence.get(source_id)
        if source_evidence is None:
            lineage.append(source_id)
            continue
        lineage.append(source_evidence)
        lineage.extend(resolve_evidence_lineage(source_id, selected_evidence, visited=visited))
    return lineage


def source_type_label(source_type: str | None) -> str:
    if source_type == "source":
        return "原始資料"
    if source_type == "derived":
        return "衍生計算"
    return source_type or "N/A"


def format_evidence_value(item: EvidenceItem) -> str:
    value = item.value
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return value or "N/A"
    if not isinstance(value, Real):
        return str(value)

    numeric_value = float(value)
    if item.unit == "ratio":
        if item.metric == "debt_to_equity":
            return f"{numeric_value:.2f}%"
        return f"{numeric_value * 100:.2f}%"
    if item.unit in {"currency", "currency_amount"}:
        formatted = format_compact_number(numeric_value)
        if item.currency:
            return f"{item.currency} {formatted}"
        return formatted
    if item.unit == "price":
        formatted = f"{numeric_value:,.2f}"
        if item.currency:
            return f"{item.currency} {formatted}"
        return formatted
    if item.unit in {"per_share", "multiple"}:
        return f"{numeric_value:,.2f}"
    if numeric_value.is_integer():
        return f"{int(numeric_value):,}"
    return f"{numeric_value:,.2f}"


def format_compact_number(value: float) -> str:
    absolute_value = abs(value)
    for factor, suffix in (
        (1_000_000_000_000, "T"),
        (1_000_000_000, "B"),
        (1_000_000, "M"),
    ):
        if absolute_value >= factor:
            return f"{value / factor:.2f}{suffix}"
    return f"{value:,.2f}"


def format_evidence_period(period_end: date | None) -> str:
    if period_end is None:
        return "N/A"
    return f"FY ending {period_end.isoformat()}"


def format_generated_at(value: Any) -> str:
    if value is None:
        return "N/A"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def summarize_selected_context(selected_context: SelectedResearchContext) -> dict[str, int | str | None]:
    return {
        "symbol": selected_context.symbol,
        "display_name": selected_context.display_name,
        "question_type": selected_context.question_type.value,
        "evidence_count": len(selected_context.selected_evidence),
        "missing_data_count": len(selected_context.selected_missing_data),
        "limitation_count": len(selected_context.selected_limitations),
        "source_evidence_count": selected_context.source_evidence_count,
    }


def format_missing_data_item(item: MissingDataItem) -> dict[str, str]:
    return {
        "id": item.id,
        "metric": item.metric,
        "period": format_evidence_period(item.period_end),
        "reason": item.reason,
        "impact": item.impact,
        "source": item.source or "N/A",
    }


def format_limitation_item(item: ResearchLimitation) -> str:
    return f"{item.id} · {item.message}"


def safe_error_message(error: Exception) -> str:
    if isinstance(error, AIConfigurationError):
        return "尚未設定 OpenAI API Key。"
    if isinstance(error, AIProviderError):
        return "OpenAI 服務目前無法完成請求，請稍後再試。"
    if isinstance(error, AIIncompleteResponseError):
        if error.reason == "max_output_tokens":
            return "AI 回答未完整產生；回答在完成前達到輸出上限。"
        return "AI 回答未完整產生。"
    if isinstance(error, AIRefusalError):
        return "此請求未能產生回答。"
    if isinstance(error, AIStructuredOutputError):
        return "AI 回答格式未通過系統驗證。"
    if isinstance(error, (AIGroundingError, AINumericGroundingError)):
        return "AI 回答未通過資料一致性驗證，因此未顯示。"
    if isinstance(error, AIResearchError):
        return str(error)
    if isinstance(error, ValueError):
        return str(error)
    return "AI Research 無法完成，請稍後再試。"


def safe_error_details(error: Exception) -> dict[str, Any]:
    details: dict[str, Any] = {"error_type": error.__class__.__name__}
    if isinstance(error, AIIncompleteResponseError):
        details.update(
            {
                "response_id": error.response_id,
                "incomplete_reason": error.reason,
                "input_tokens": error.input_tokens,
                "output_tokens": error.output_tokens,
                "reasoning_tokens": error.reasoning_tokens,
                "cached_input_tokens": error.cached_input_tokens,
                "total_tokens": error.total_tokens,
            }
        )
    return {key: value if value is not None else "N/A" for key, value in details.items()}


def json_safe_selected_context_summary(selected_context: SelectedResearchContext) -> dict[str, Any]:
    return json_safe_value(summarize_selected_context(selected_context))
