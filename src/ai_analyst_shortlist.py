"""Session-only, two-stage grounded review for a small research shortlist."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
import json
import re
from typing import Any, Callable

from ai_config import AIResearchConfig, get_ai_research_config
from ai_research_service import (
    AIConfigurationError,
    AIForbiddenRecommendationError,
    AIGroundingError,
    AIProviderError,
    AIResearchError,
    GroundedFinding,
    GroundedResearchAnswer,
    OpenAIResearchClient,
    extract_non_percentage_numeric_claims,
    extract_percentage_claims,
    generate_grounded_research_answer,
    format_analyst_evidence_value,
    validate_grounded_ai_answer,
    validate_grounded_ai_evidence,
)
from models import Stock
from research_context import EvidenceItem, MissingDataItem, build_research_context
from research_context_selector import (
    ResearchQuestionType,
    ResearchSelectionRequest,
    SelectedResearchContext,
    select_research_context,
    validate_selected_research_context,
)
from research_service import build_research_report


AI_ANALYST_CARD_VERSION = "AI_ANALYST_CARD_V0"
AI_ANALYST_SHORTLIST_MAX_SIZE = 5
RESEARCH_PRIORITIES = ("優先深入研究", "值得觀察", "證據不足")


class AIAnalystShortlistError(Exception):
    """Raised when shortlist input or structured output is invalid."""


class AIAnalystCardFormatError(AIAnalystShortlistError):
    """Raised for one-shot-repairable Analyst Card structure errors."""


class AIAnalystValuationComparatorOverclaimError(AIAnalystCardFormatError):
    """A valuation classification needs comparator evidence that is absent."""

    code = "VALUATION_COMPARATOR_OVERCLAIM"

    def __init__(self) -> None:
        super().__init__(
            "Standalone valuation multiples cannot classify valuation without peer or historical comparators."
        )


class AIAnalystMissingRequiredEvidenceRefsError(AIAnalystCardFormatError):
    """A qualitative finding needs an exact canonical evidence reference."""

    code = "MISSING_REQUIRED_EVIDENCE_REFS"

    def __init__(self) -> None:
        super().__init__("Qualitative interpretation is missing required evidence references.")


class AIAnalystStageTwoNumericError(AIAnalystShortlistError):
    """Retain the first rejected Stage-2 numeric token without retaining model text."""

    def __init__(self, *, matched_numeric: str, field: str, classification: str) -> None:
        self.matched_numeric = matched_numeric
        self.field = field
        self.classification = classification
        super().__init__("Synthesis contains an unsupported numerical claim.")


class AIAnalystStageTwoPolicyError(AIAnalystShortlistError):
    """Safe Stage-2 recommendation-policy metadata without retaining model text."""

    def __init__(self, *, rule: str, term: str, field: str) -> None:
        self.rule = rule
        self.term = term
        self.field = field
        super().__init__(
            "Stage-2 output contains prohibited recommendation language "
            f"(matched_rule={rule}; matched_term={term}; field={field})."
        )


ANALYST_QUESTION = """
僅依 evidence 產繁中初步研究，非投資建議。
summary 首行：研究優先度：優先深入研究、值得觀察或證據不足。
finding 需完整 evidence_ids、質化解讀；missing_information 留空，缺漏由程式處理；next_steps 可留空，若提供須附可用 ID。
估值僅倍數及比較缺口，無 peer／history 禁定性估值；市場僅價格趨勢／相對 0050 缺口，區段不得重複。
""".strip()


ANALYST_EVIDENCE_REFERENCE_INSTRUCTIONS = """
Use only exact CATALOG evidence_id strings; no aliases or observations[n]/evidence[n] IDs.
""".strip()


SYNTHESIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["priority_deep_dive", "cross_company_observations", "overall_note"],
    "properties": {
        "priority_deep_dive": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["symbol", "reason", "main_unresolved_risk"],
                "properties": {
                    "symbol": {"type": "string"},
                    "reason": {"type": "string"},
                    "main_unresolved_risk": {"type": "string"},
                },
            },
        },
        "cross_company_observations": {
            "type": "array",
            "maxItems": 6,
            "items": {"type": "string"},
        },
        "overall_note": {"type": "string"},
    },
}


SYNTHESIS_FORMAT = {
    "type": "json_schema",
    "name": "ai_analyst_shortlist_synthesis_v0",
    "description": "Comparison based only on validated AI_ANALYST_CARD_V0 cards.",
    "strict": True,
    "schema": SYNTHESIS_SCHEMA,
}


SYNTHESIS_INSTRUCTIONS = """
你是研究清單比較助手。只能使用提供的 validated AI_ANALYST_CARD_V0 cards。
不得取得或推測原始資料，不得加入 cards 未支持的數字或公司。
不得重述百分比、價格、估值倍數、財務金額或證據表格中的原始數值。
最多列出三個優先深入研究標的；空清單有效，不得強迫選出標的。
不得把證據較完整等同更具投資吸引力；只能比較研究優先度與待補證據。
輸出是研究注意力排序，不是投資建議。不得使用買進、賣出、持有、目標價、機率或分數。
使用繁體中文並嚴格遵守 JSON schema。
""".strip()


PROHIBITED_PATTERNS = (
    r"\bstrong\s+buy\b",
    r"\bstrong\s+sell\b",
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\bscore\b",
    r"\bprobability\b",
    r"\bprice\s+target\b",
    r"買進",
    r"賣出",
    r"持有",
    r"加碼",
    r"減碼",
    r"停損",
    r"看多",
    r"看空",
    r"最佳股票",
    r"最可能上漲",
    r"預期.*報酬率",
    r"預估.*報酬率",
    r"預計.*報酬率",
    r"目標.*報酬率",
    r"未來.*報酬率",
    r"報酬率.*預期",
    r"報酬率.*預估",
    r"\bexpected\s+return\b",
    r"\bexpected\s+upside\b",
    r"\btarget\s+return\b",
    r"預期.*上漲",
    r"預估.*上漲",
    r"預計.*上漲",
    r"勝率最高",
    r"目標價",
    r"投資推薦",
    r"上漲機率",
    r"機率",
    r"概率",
    r"評分",
)


STAGE_TWO_PROHIBITED_RULES = (
    ("BUY_ACTION", r"\bbuy\b|買進", "buy_or_買進"),
    ("SELL_ACTION", r"\bsell\b|賣出", "sell_or_賣出"),
    ("HOLD_ACTION", r"\bhold\b|持有", "hold_or_持有"),
    ("ADD_POSITION", r"加碼", "加碼"),
    ("REDUCE_POSITION", r"減碼", "減碼"),
    ("PRICE_TARGET", r"\bprice\s+target\b|目標價", "price_target_or_目標價"),
    ("EXPECTED_RETURN", r"\bexpected\s+(?:return|upside)\b|\btarget\s+return\b|(?:預期|預估|預計|目標|未來).*報酬率", "expected_return"),
    ("BULLISH_CALL", r"看多", "看多"),
    ("BEARISH_CALL", r"看空", "看空"),
    ("INVESTMENT_RECOMMENDATION", r"投資推薦|最佳股票|最可能上漲", "investment_recommendation"),
)


FUNDAMENTAL_METRICS = {
    "return_on_equity", "gross_margin", "operating_margin", "net_margin",
    "trailing_eps", "revenue_growth", "earnings_growth", "total_cash",
    "total_debt", "debt_to_equity", "operating_cash_flow", "free_cash_flow",
}
VALUATION_METRICS = {"trailing_pe", "forward_pe", "price_to_book"}
MARKET_METRICS = {
    "current_price", "fifty_two_week_high", "fifty_two_week_low",
    "fifty_day_average", "two_hundred_day_average", "fifty_two_week_position",
    "rel_return_20d", "rel_return_60d",
}
OPPORTUNITY_METRICS = {"revenue_yoy", "revenue_mom", "radar_condition_flags"}
ANALYST_SECTION_METRICS = {
    "opportunity_interpretation": OPPORTUNITY_METRICS,
    "fundamental_quality": FUNDAMENTAL_METRICS,
    "valuation_context": VALUATION_METRICS,
    "market_confirmation": MARKET_METRICS,
}
VALUATION_COMPARATOR_METRIC_KEYWORDS = ("peer", "historical")
VALUATION_CLASSIFICATION_PATTERN = re.compile(
    r"(?:估值|倍數).{0,12}(?:偏低|低估|合理|偏高|高估|便宜|昂貴|非高估)"
    r"|(?:偏低|低估|合理|偏高|高估|便宜|昂貴|非高估).{0,12}(?:估值|倍數)",
    flags=re.IGNORECASE,
)
VALUATION_INSUFFICIENCY_PATTERN = re.compile(
    r"(?:不足|無法|尚無|尚未|缺少|不能|不宜).{0,12}(?:判定|判斷|分類|估值|倍數)"
    r"|(?:判定|判斷|分類).{0,12}(?:不足|無法|尚無|尚未|缺少)",
    flags=re.IGNORECASE,
)


ANALYST_MODEL_EVIDENCE_METRICS = (
    "revenue_yoy",
    "revenue_mom",
    "rel_return_20d",
    "rel_return_60d",
    "earnings_growth",
    "return_on_equity",
    "operating_margin",
    "total_cash",
    "total_debt",
    "debt_to_equity",
    "trailing_pe",
    "price_to_book",
    "current_price",
    "fifty_day_average",
    "two_hundred_day_average",
)


VERIFIED_EVIDENCE_FIELDS = (
    ("Opportunity Radar", "revenue_period", "營收月份"),
    ("Opportunity Radar", "revenue_yoy", "Revenue YoY"),
    ("Opportunity Radar", "revenue_mom", "Revenue MoM"),
    ("Opportunity Radar", "rel_return_20d", "20D 相對 0050"),
    ("Opportunity Radar", "rel_return_60d", "60D 相對 0050"),
    ("基本面", "revenue_growth", "Revenue Growth"),
    ("基本面", "earnings_growth", "Earnings Growth"),
    ("基本面", "return_on_equity", "ROE"),
    ("基本面", "gross_margin", "Gross Margin"),
    ("基本面", "operating_margin", "Operating Margin"),
    ("基本面", "net_margin", "Net Margin"),
    ("基本面", "trailing_eps", "EPS"),
    ("基本面", "total_cash", "Total Cash"),
    ("基本面", "total_debt", "Total Debt"),
    ("基本面", "debt_to_equity", "Debt to Equity"),
    ("基本面", "operating_cash_flow", "Operating Cash Flow"),
    ("基本面", "free_cash_flow", "Free Cash Flow"),
    ("估值", "trailing_pe", "Trailing P/E"),
    ("估值", "forward_pe", "Forward P/E"),
    ("估值", "price_to_book", "P/B"),
    ("市場", "current_price", "Current Price"),
    ("市場", "fifty_two_week_high", "52-week High"),
    ("市場", "fifty_two_week_low", "52-week Low"),
    ("市場", "fifty_day_average", "50-day Average"),
    ("市場", "two_hundred_day_average", "200-day Average"),
)


MISSING_EVIDENCE_LABELS = {
    "revenue_period": "月營收資料期間",
    "revenue_yoy": "Revenue YoY 資料",
    "revenue_mom": "Revenue MoM 資料",
    "rel_return_20d": "20D 相對 0050",
    "rel_return_60d": "60D 相對 0050",
    "revenue_growth": "營收成長資料",
    "earnings_growth": "獲利成長資料",
    "return_on_equity": "ROE 資料",
    "gross_margin": "毛利率資料",
    "operating_margin": "營業利益率資料",
    "net_margin": "淨利率資料",
    "trailing_eps": "EPS 資料",
    "operating_cash_flow": "營業現金流資料",
    "free_cash_flow": "自由現金流資料",
    "total_cash": "現金資料",
    "total_debt": "負債資料",
    "debt_to_equity": "負債權益比資料",
    "trailing_pe": "Trailing P/E 資料",
    "forward_pe": "Forward P/E 資料",
    "price_to_book": "P/B 資料",
    "current_price": "目前價格資料",
    "market_cap": "市值資料",
    "fifty_two_week_high": "52 週高點資料",
    "fifty_two_week_low": "52 週低點資料",
    "fifty_day_average": "50 日均線資料",
    "two_hundred_day_average": "200 日均線資料",
    "series": "足夠歷史財務序列",
    "sector": "產業類別資料",
    "snapshot_retrieved_at": "Radar 資料擷取時間",
}
INTERNAL_EVIDENCE_GAP_LABELS = {
    "global:no_quarterly_or_ttm": "缺少足夠歷史財務序列",
    "context:no_historical_series": "缺少足夠歷史財務序列",
}
INTERNAL_EVIDENCE_GAP_PATTERN = re.compile(
    r"(?:missing:[A-Za-z0-9._-]+(?::[A-Za-z0-9._-]+)+|context:[a-z_]+|global:[a-z_]+)"
)


ANALYST_SECTION_ROLE_REPAIR = """
FORMAT REPAIR ONLY: previous response combined valuation and market confirmation.
Return separate grounded findings. Valuation uses valuation evidence; market confirmation uses market evidence.
Keep exact canonical evidence_ids from CATALOG. Do not add facts, projections, recommendations, or unsupported numbers.
""".strip()


ANALYST_VALUATION_COMPARATOR_OVERCLAIM_REPAIR = """
FORMAT REPAIR ONLY: current valuation multiples have no peer or historical comparator.
Do not call valuation cheap, expensive, low, high, fair, undervalued, or overvalued.
Describe only available multiples, the missing comparator context, and the next check. Same CATALOG facts and IDs; no new facts.
""".strip()


ANALYST_MISSING_REQUIRED_EVIDENCE_REFS_REPAIR = """
FORMAT REPAIR ONLY: one or more qualitative findings omitted required evidence references.
Every factual qualitative finding must cite exact supplied CATALOG evidence_ids that support it.
Do not add facts or invent IDs. Remove any finding with no supplied supporting evidence.
""".strip()


def build_shortlist_selected_context(
    row: dict[str, Any],
    *,
    stock: Stock | None = None,
    generated_at: datetime | None = None,
    radar_evidence_resolver: Callable[[str], dict[str, Any] | None] | None = None,
) -> SelectedResearchContext:
    symbol = _required_text(row.get("股票代號"), "股票代號")
    company_name = _optional_text(row.get("公司名稱"))
    industry = _optional_text(row.get("產業"))
    resolved_stock = stock or Stock(symbol=symbol, company_name=company_name, industry=industry)
    if resolved_stock.symbol != symbol:
        raise AIAnalystShortlistError("Cached stock symbol does not match shortlist symbol.")
    if resolved_stock.company_name is None:
        resolved_stock.company_name = company_name
    if resolved_stock.industry is None:
        resolved_stock.industry = industry

    timestamp = generated_at or datetime.now(UTC)
    source_context = build_research_context(
        stock=resolved_stock,
        research_report=build_research_report(resolved_stock),
        display_name=company_name or symbol,
        generated_at=timestamp,
    )
    selected = select_research_context(
        source_context,
        ResearchSelectionRequest(question_type=ResearchQuestionType.GENERAL_RESEARCH),
    )
    canonical_radar_evidence = (
        radar_evidence_resolver(symbol) if radar_evidence_resolver is not None else None
    )
    radar_evidence, radar_missing = _radar_evidence(
        row,
        timestamp,
        canonical_radar_evidence=canonical_radar_evidence,
        canonical_resolution_requested=radar_evidence_resolver is not None,
    )
    identity = EvidenceItem(
        id=f"shortlist:{symbol}:identity",
        category="shortlist_identity",
        metric="symbol",
        value=symbol,
        unit=None,
        currency=None,
        period_end=None,
        period_year=None,
        source="Current session research shortlist",
        source_type="source",
        note="Company-isolated shortlist identity.",
    )
    combined = replace(
        selected,
        selected_evidence=sorted(
            [*selected.selected_evidence, identity, *radar_evidence],
            key=lambda item: item.id,
        ),
        selected_missing_data=[*selected.selected_missing_data, *radar_missing],
        source_evidence_count=selected.source_evidence_count + 1 + len(radar_evidence),
    )
    validate_selected_research_context(combined)
    return combined


def analyze_research_shortlist(
    rows: list[dict[str, Any]],
    *,
    stock_loader: Callable[[str], Stock | None],
    grounded_generator: Callable[..., GroundedResearchAnswer] = generate_grounded_research_answer,
    synthesis_generator: Callable[..., dict[str, Any]] | None = None,
    generated_at: datetime | None = None,
    radar_evidence_resolver: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    if not rows:
        raise AIAnalystShortlistError("本次研究清單尚無標的，請先加入股票。")
    if len(rows) > AI_ANALYST_SHORTLIST_MAX_SIZE:
        raise AIAnalystShortlistError("AI 分析 V0 一次最多分析 5 檔，請先縮小本次研究清單。")

    cards = []
    call_count = 0
    successful_count = 0
    format_repair_count = 0
    policy_regeneration_count = 0
    successful_cards = []
    excluded_symbols = []
    for row in rows:
        symbol = _required_text(row.get("股票代號"), "股票代號")
        context = None
        try:
            context = build_shortlist_selected_context(
                row,
                stock=stock_loader(symbol),
                generated_at=generated_at,
                radar_evidence_resolver=radar_evidence_resolver,
            )
            model_context = build_analyst_model_context(context)
            call_count += 1
            try:
                answer = grounded_generator(
                    question=build_analyst_stage_one_question(model_context),
                    selected_context=model_context,
                )
                validate_grounded_ai_answer(answer, model_context)
                card = normalize_analyst_card(answer, context, row)
            except (AIForbiddenRecommendationError, AIAnalystCardFormatError, AIGroundingError) as error:
                if isinstance(error, AIForbiddenRecommendationError):
                    # Policy is checked first by the provider adapter. Mixed failures cannot retry.
                    validate_grounded_ai_evidence(error.answer, model_context)
                    validate_analyst_qualitative_answer(error.answer, model_context)
                    build_analyst_available_next_checks(error.answer, model_context)
                    question = build_analyst_policy_regeneration_question(model_context, error)
                    policy_regeneration_count += 1
                else:
                    format_error = _repairable_analyst_card_format_error(error)
                    if format_error is None:
                        raise
                    question = build_analyst_format_repair_question(model_context, format_error)
                    format_repair_count += 1
                call_count += 1
                repaired_answer = grounded_generator(
                    question=question,
                    selected_context=model_context,
                )
                validate_grounded_ai_answer(repaired_answer, model_context)
                card = normalize_analyst_card(repaired_answer, context, row)
            successful_count += 1
            successful_cards.append(card)
        except Exception as error:
            card = build_failed_analyst_card(row, error, context=context)
            excluded_symbols.append(symbol)
        cards.append(card)

    for card in cards:
        validate_analyst_card(card)

    synthesis = None
    synthesis_error = None
    stage2_diagnostic = None
    synthesis_skip_reason = None
    if successful_count >= 2:
        try:
            call_count += 1
            if synthesis_generator is None:
                synthesis = generate_shortlist_synthesis(cards=successful_cards)
            else:
                synthesis = synthesis_generator(cards=build_stage_two_cards(successful_cards))
            validate_shortlist_synthesis(synthesis, successful_cards)
        except Exception as error:
            synthesis = None
            stage2_diagnostic = build_stage_two_failure_diagnostic(error, successful_cards)
            synthesis_error = stage2_diagnostic["code"]
    else:
        synthesis_skip_reason = (
            "僅一檔通過初步審查，至少需要兩檔才能進行清單比較。"
            if successful_count == 1
            else "尚無標的通過初步審查，因此未進行清單比較。"
        )

    return {
        "cards": cards,
        "synthesis": synthesis,
        "synthesis_error": synthesis_error,
        "stage2_diagnostic": stage2_diagnostic,
        "synthesis_skip_reason": synthesis_skip_reason,
        "stage2_excluded_symbols": excluded_symbols,
        "provider_call_count": call_count,
        "stage1_success_count": successful_count,
        "stage1_format_repair_count": format_repair_count,
        "stage1_policy_regeneration_count": policy_regeneration_count,
    }


def build_analyst_stage_one_question(context: SelectedResearchContext) -> str:
    """Attach an exact-ID catalog without introducing another evidence source."""
    catalog = "\n".join(_compact_evidence_catalog_line(item) for item in context.selected_evidence)
    availability = build_analyst_section_availability(context)
    section_labels = {
        "opportunity_interpretation": "opportunity",
        "fundamental_quality": "fundamental",
        "valuation_context": "valuation",
        "market_confirmation": "market",
    }
    allowed_sections = ",".join(
        section_labels[section]
        for section, available in availability.items()
        if available
    )
    return "\n\n".join((
        ANALYST_QUESTION,
        ANALYST_EVIDENCE_REFERENCE_INSTRUCTIONS,
        f"FINDINGS={allowed_sections or 'none'}; code owns others as insufficient.",
        "CATALOG (evidence_id|unit|value):\n" + catalog,
    ))


def build_analyst_format_repair_question(
    context: SelectedResearchContext,
    error: AIAnalystCardFormatError,
) -> str:
    if isinstance(error, AIAnalystValuationComparatorOverclaimError):
        repair_instruction = ANALYST_VALUATION_COMPARATOR_OVERCLAIM_REPAIR
    elif isinstance(error, AIAnalystMissingRequiredEvidenceRefsError):
        repair_instruction = ANALYST_MISSING_REQUIRED_EVIDENCE_REFS_REPAIR
    elif str(error) == "SECTION_ROLE_OVERLAP":
        repair_instruction = ANALYST_SECTION_ROLE_REPAIR
    else:
        raise AIAnalystShortlistError("Unsupported Analyst Card repair classification.")
    return "\n\n".join((build_analyst_stage_one_question(context), repair_instruction))


def _repairable_analyst_card_format_error(
    error: AIAnalystCardFormatError | AIGroundingError,
) -> AIAnalystCardFormatError | None:
    if isinstance(error, AIAnalystCardFormatError):
        return error
    if str(error) == "Factual finding must include evidence_ids.":
        return AIAnalystMissingRequiredEvidenceRefsError()
    return None


def build_analyst_policy_regeneration_question(
    context: SelectedResearchContext,
    error: AIForbiddenRecommendationError,
) -> str:
    instruction = (
        f"Rejected policy: {error.rule} / {error.term}. Regenerate research interpretation only. "
        "No buy/sell/hold/add/reduce/targets/expected returns. "
        "Same company, same CATALOG facts and exact evidence IDs; no new facts."
    )
    return "\n\n".join((build_analyst_stage_one_question(context), instruction))


def build_analyst_model_context(context: SelectedResearchContext) -> SelectedResearchContext:
    """Bound Stage-1 input while keeping the complete context for deterministic UI output."""
    evidence_by_metric = {item.metric: item for item in context.selected_evidence}
    compact_evidence = [
        evidence_by_metric[metric]
        for metric in ANALYST_MODEL_EVIDENCE_METRICS
        if metric in evidence_by_metric
    ]
    compact = replace(
        context,
        selected_evidence=compact_evidence,
        selected_observation_links=[],
        selected_observations=[],
        selected_missing_data=[],
        selected_limitations=[],
        selection_notes=[],
        source_evidence_count=len(compact_evidence),
    )
    validate_selected_research_context(compact)
    return compact


def build_analyst_section_availability(
    context: SelectedResearchContext,
) -> dict[str, bool]:
    return _analyst_section_availability_from_metrics({
        item.metric for item in context.selected_evidence
    })


def _analyst_section_availability_from_metrics(
    available_metrics: set[str],
) -> dict[str, bool]:
    return {
        section: not available_metrics.isdisjoint(metrics)
        for section, metrics in ANALYST_SECTION_METRICS.items()
    }


def _compact_evidence_catalog_line(item: EvidenceItem) -> str:
    unit = item.unit or "value"
    if item.currency:
        unit = f"{unit}:{item.currency}"
    return f"{item.id}|{unit}|{json.dumps(item.value, ensure_ascii=False, separators=(',', ':'))}"


def _display_missing_evidence(items: list[str]) -> list[str]:
    return _display_analyst_texts(items)


def _display_analyst_texts(items: list[str]) -> list[str]:
    display_items = []
    for item in items:
        display = _humanize_internal_evidence_references(item)
        if display not in display_items:
            display_items.append(display)
    return display_items


def _humanize_internal_evidence_references(text: str) -> str:
    metric = _missing_evidence_metric(text)
    if metric is not None:
        if metric in MISSING_EVIDENCE_LABELS:
            return MISSING_EVIDENCE_LABELS[metric]
        return text if text.startswith("缺少 ") else "其他尚缺研究資料"

    def replace_reference(match: re.Match[str]) -> str:
        reference = match.group(0)
        reference_metric = _missing_evidence_metric(reference)
        if reference_metric is not None:
            return MISSING_EVIDENCE_LABELS.get(reference_metric, "相關研究資料")
        return INTERNAL_EVIDENCE_GAP_LABELS.get(reference, "相關研究資料")

    return INTERNAL_EVIDENCE_GAP_PATTERN.sub(replace_reference, text)


def humanize_analyst_display_text(text: str) -> str:
    """Return normal-UI text without internal evidence-gap identifiers."""
    return _humanize_internal_evidence_references(text)


def _missing_evidence_metric(item: str) -> str | None:
    if item.startswith("missing:"):
        return item.rsplit(":", maxsplit=1)[-1]
    if item.startswith("缺少 "):
        return item.removeprefix("缺少 ")
    return None


def normalize_analyst_card(
    answer: GroundedResearchAnswer,
    context: SelectedResearchContext,
    row: dict[str, Any],
) -> dict[str, Any]:
    validate_analyst_qualitative_answer(answer, context)
    priority = _extract_priority(answer)
    evidence_by_id = {item.id: item for item in context.selected_evidence}
    opportunity = _display_analyst_texts(_statements_for_metrics(answer, evidence_by_id, OPPORTUNITY_METRICS))
    fundamental = _section_text(answer, evidence_by_id, FUNDAMENTAL_METRICS)
    valuation = _section_text(answer, evidence_by_id, VALUATION_METRICS)
    market = _section_text(answer, evidence_by_id, MARKET_METRICS)
    contradictions = detect_contradictions(context)
    extreme_warnings = detect_extreme_value_warnings(context)
    missing, missing_checks = build_analyst_missing_evidence(context)
    risks = _display_analyst_texts([*answer.limitations, *extreme_warnings])
    evidence_refs = list(dict.fromkeys(
        evidence_id
        for finding in answer.findings
        for evidence_id in finding.evidence_ids
    ))
    card = {
        "symbol": context.symbol,
        "company_name": context.display_name or _optional_text(row.get("公司名稱")) or context.symbol,
        "research_priority": priority,
        "verified_evidence": build_verified_evidence(context),
        "opportunity_interpretation": opportunity,
        "fundamental_quality": fundamental,
        "valuation_context": valuation,
        "market_confirmation": market,
        "risks": risks,
        "contradictions": contradictions,
        "missing_evidence": missing,
        "next_checks": _display_analyst_texts([
            *missing_checks,
            *build_analyst_available_next_checks(answer, build_analyst_model_context(context)),
        ]),
        "evidence_refs": evidence_refs,
        "evidence_dates": _evidence_dates(context),
    }
    validate_analyst_card(card)
    return card


def build_analyst_missing_evidence(context: SelectedResearchContext) -> tuple[list[str], list[str]]:
    """Keep missing labels and follow-up tasks independent of generated text."""
    metrics = list(dict.fromkeys(item.metric for item in context.selected_missing_data))
    labels = [MISSING_EVIDENCE_LABELS.get(metric, "其他尚缺研究資料") for metric in metrics]
    checks = []
    for metric in metrics:
        if metric in {"operating_cash_flow", "free_cash_flow"}:
            check = "補足現金流資料"
        elif metric in {"rel_return_20d", "rel_return_60d"}:
            check = "補足相對 0050 市場確認"
        elif metric == "revenue_period":
            check = "確認月營收資料期間"
        elif metric == "series":
            check = "補足歷史財務序列"
        else:
            check = "補足" + MISSING_EVIDENCE_LABELS.get(metric, "其他尚缺研究資料")
        checks.append(check)
    if not _has_valuation_comparator(context):
        labels.append("歷史或同業估值比較")
        checks.append("補足歷史或同業估值比較")
    return list(dict.fromkeys(labels)), list(dict.fromkeys(checks))


def build_analyst_available_next_checks(
    answer: GroundedResearchAnswer, context: SelectedResearchContext,
) -> list[str]:
    """Optional AI tasks must cite available facts; unreferenced tasks are not displayed."""
    evidence_by_id = {item.id: item for item in context.selected_evidence}
    checks = []
    for text in answer.next_steps:
        if INTERNAL_EVIDENCE_GAP_PATTERN.search(text):
            continue
        refs = re.findall(r"(?:radar:[A-Za-z0-9._-]+|current):[a-z_0-9]+", text)
        if not refs:
            continue
        task_answer = replace(answer, findings=[GroundedFinding(text, refs)], next_steps=[])
        validate_grounded_ai_evidence(task_answer, context)
        validate_analyst_qualitative_answer(task_answer, context)
        for ref in dict.fromkeys(refs):
            metric = evidence_by_id[ref].metric
            text = text.replace(ref, MISSING_EVIDENCE_LABELS.get(metric, metric))
        checks.append(text)
    return checks


def build_failed_analyst_card(
    row: dict[str, Any],
    error: Exception,
    *,
    context: SelectedResearchContext | None = None,
) -> dict[str, Any]:
    symbol = _required_text(row.get("股票代號"), "股票代號")
    error_message = str(error) or error.__class__.__name__
    safety_diagnostic = re.search(
        r"\((matched_rule=[A-Z_]+; matched_term=[^;()]+; field=[a-z_]+)\)",
        error_message,
    )
    if "forbidden recommendation language" in error_message:
        error_message = "AI 輸出未通過投資安全檢查。"
        if safety_diagnostic is not None:
            error_message += f"（{safety_diagnostic.group(1)}）"
    return {
        "symbol": symbol,
        "company_name": _optional_text(row.get("公司名稱")) or symbol,
        "research_priority": "證據不足",
        "verified_evidence": build_verified_evidence(context) if context is not None else [],
        "opportunity_interpretation": [],
        "fundamental_quality": "AI 初步審查未完成。",
        "valuation_context": "AI 初步審查未完成。",
        "market_confirmation": "AI 初步審查未完成。",
        "risks": [],
        "contradictions": [],
        "missing_evidence": [f"AI 初步審查失敗：{error_message}"],
        "next_checks": ["保留原始研究資料並稍後重試 AI 分析。"],
        "evidence_refs": [],
        "evidence_dates": {},
    }


def validate_analyst_card(card: dict[str, Any]) -> None:
    required = {
        "symbol", "company_name", "research_priority", "verified_evidence", "opportunity_interpretation",
        "fundamental_quality", "valuation_context", "market_confirmation", "risks",
        "contradictions", "missing_evidence", "next_checks", "evidence_refs", "evidence_dates",
    }
    if set(card) != required:
        raise AIAnalystShortlistError("AI_ANALYST_CARD_V0 schema mismatch.")
    if card["research_priority"] not in RESEARCH_PRIORITIES:
        raise AIAnalystShortlistError("Invalid research priority.")
    if not isinstance(card["symbol"], str) or not card["symbol"]:
        raise AIAnalystShortlistError("Analyst card symbol is required.")
    for key in ("verified_evidence", "opportunity_interpretation", "risks", "contradictions", "missing_evidence", "next_checks", "evidence_refs"):
        if not isinstance(card[key], list):
            raise AIAnalystShortlistError(f"Analyst card {key} must be a list.")
    for row in card["verified_evidence"]:
        if not isinstance(row, dict) or set(row) != {
            "section", "metric", "label", "display_value", "status", "evidence_id",
        }:
            raise AIAnalystShortlistError("Verified evidence row schema mismatch.")
        if row["status"] not in {"available", "missing"}:
            raise AIAnalystShortlistError("Verified evidence row status is invalid.")
    verified_metrics = [row["metric"] for row in card["verified_evidence"]]
    if len(verified_metrics) != len(set(verified_metrics)):
        raise AIAnalystShortlistError("Verified evidence metrics must have unique section ownership.")
    _validate_prohibited_text(_card_texts(card))


def generate_shortlist_synthesis(
    *,
    cards: list[dict[str, Any]],
    client: Any | None = None,
    config: AIResearchConfig | None = None,
) -> dict[str, Any]:
    if len(cards) < 2:
        raise AIAnalystShortlistError("Comparison requires at least two validated Stage-1 cards.")
    for card in cards:
        validate_analyst_card(card)
    resolved_config = config or get_ai_research_config()
    resolved_client = client or OpenAIResearchClient(timeout=resolved_config.timeout_seconds)
    payload = build_stage_two_request_payload(cards)
    response = resolved_client.create_grounded_answer(
        model=resolved_config.model,
        instructions=SYNTHESIS_INSTRUCTIONS,
        payload=payload,
        max_output_tokens=resolved_config.max_output_tokens,
        reasoning_effort=resolved_config.reasoning_effort,
        text_verbosity=resolved_config.text_verbosity,
        response_format=SYNTHESIS_FORMAT,
    )
    output_text = getattr(response, "output_text", None)
    if output_text is None and isinstance(response, dict):
        output_text = response.get("output_text")
    if not isinstance(output_text, str) or not output_text.strip():
        raise AIAnalystShortlistError("AI synthesis response is empty.")
    try:
        synthesis = json.loads(output_text)
    except json.JSONDecodeError as error:
        raise AIAnalystShortlistError("AI synthesis response is not valid JSON.") from error
    validate_shortlist_synthesis(synthesis, cards)
    return synthesis


def build_stage_two_request_payload(cards: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the validated-card-only payload sent to the comparison provider."""
    return {"card_version": AI_ANALYST_CARD_VERSION, "validated_cards": build_stage_two_cards(cards)}


def build_stage_two_failure_diagnostic(error: Exception, cards: list[dict[str, Any]]) -> dict[str, Any]:
    """Return minimal safe metadata; never retain the raw provider response or prompt."""
    diagnostic = {
        "code": "STAGE2_UNEXPECTED_ERROR",
        "exception_class": error.__class__.__name__,
        "input_length": len(json.dumps(build_stage_two_request_payload(cards), ensure_ascii=False, separators=(",", ":"))),
        "prompt_length": len(SYNTHESIS_INSTRUCTIONS),
    }
    if isinstance(error, AIAnalystStageTwoPolicyError):
        diagnostic.update({
            "code": "RECOMMENDATION_POLICY_REJECTED",
            "matched_rule": error.rule,
            "matched_term": error.term,
            "field": error.field,
        })
    elif isinstance(error, AIAnalystStageTwoNumericError):
        diagnostic.update({
            "code": "STAGE2_NUMERIC_OUTPUT_REJECTED",
            "matched_numeric": error.matched_numeric,
            "field": error.field,
            "numeric_classification": error.classification,
        })
    elif isinstance(error, AIProviderError):
        diagnostic["code"] = "PROVIDER_ERROR"
    elif isinstance(error, AIConfigurationError):
        diagnostic["code"] = "CONFIGURATION_ERROR"
    elif isinstance(error, AIResearchError) and "question 長度超過限制" in str(error):
        diagnostic["code"] = "QUESTION_LENGTH_EXCEEDED"
    elif isinstance(error, AIAnalystShortlistError):
        message = str(error)
        if "response is empty" in message:
            diagnostic["code"] = "STRUCTURED_OUTPUT_EMPTY"
        elif "not valid JSON" in message:
            diagnostic["code"] = "STRUCTURED_OUTPUT_PARSE_ERROR"
        elif "schema mismatch" in message or "schema mismatch" in message.lower():
            diagnostic["code"] = "STRUCTURED_OUTPUT_SCHEMA_ERROR"
        elif "unsupported numerical" in message:
            diagnostic["code"] = "STAGE2_NUMERIC_OUTPUT_REJECTED"
        else:
            diagnostic["code"] = "STAGE2_RESULT_VALIDATION_ERROR"
    return diagnostic


def format_stage_two_failure_diagnostic(diagnostic: dict[str, Any]) -> str:
    """Render only safe cause metadata for the collapsed technical diagnostic."""
    parts = [f"Stage-2 comparison failed: {diagnostic['code']}"]
    for key in (
        "exception_class", "matched_rule", "matched_term", "matched_numeric",
        "field", "numeric_classification",
    ):
        if key in diagnostic:
            parts.append(f"{key}={diagnostic[key]}")
    return "; ".join(parts)


def validate_shortlist_synthesis(synthesis: dict[str, Any], cards: list[dict[str, Any]]) -> None:
    if not isinstance(synthesis, dict) or set(synthesis) != {
        "priority_deep_dive", "cross_company_observations", "overall_note",
    }:
        raise AIAnalystShortlistError("Shortlist synthesis schema mismatch.")
    deep_dive = synthesis["priority_deep_dive"]
    observations = synthesis["cross_company_observations"]
    if not isinstance(deep_dive, list) or len(deep_dive) > 3:
        raise AIAnalystShortlistError("Shortlist synthesis may contain at most 3 priority companies.")
    if not isinstance(observations, list) or not isinstance(synthesis["overall_note"], str):
        raise AIAnalystShortlistError("Shortlist synthesis text fields are malformed.")
    allowed_symbols = {card["symbol"] for card in cards}
    texts_with_fields = [("overall_note", synthesis["overall_note"])]
    texts_with_fields.extend(("cross_company_observations", text) for text in observations)
    for item in deep_dive:
        if not isinstance(item, dict) or set(item) != {"symbol", "reason", "main_unresolved_risk"}:
            raise AIAnalystShortlistError("Priority company schema mismatch.")
        if item["symbol"] not in allowed_symbols:
            raise AIAnalystShortlistError("Synthesis contains a symbol outside validated cards.")
        texts_with_fields.extend([
            ("reason", item["reason"]),
            ("main_unresolved_risk", item["main_unresolved_risk"]),
        ])
    if not all(isinstance(text, str) for _field, text in texts_with_fields):
        raise AIAnalystShortlistError("Synthesis text must be strings.")
    _validate_stage_two_prohibited_text(texts_with_fields)
    for field, text in texts_with_fields:
        percentage_claims = extract_percentage_claims(text)
        if percentage_claims:
            raise AIAnalystStageTwoNumericError(
                matched_numeric=percentage_claims[0].text,
                field=field,
                classification="PERCENTAGE",
            )
        non_percentage_claims = extract_non_percentage_numeric_claims(text)
        if non_percentage_claims:
            raise AIAnalystStageTwoNumericError(
                matched_numeric=non_percentage_claims[0].text,
                field=field,
                classification="NON_PERCENTAGE",
            )


def build_verified_evidence(context: SelectedResearchContext) -> list[dict[str, Any]]:
    evidence_by_metric = {
        item.metric: item
        for item in context.selected_evidence
        if item.category in {"current_snapshot", "opportunity_radar"}
    }
    rows = []
    for section, metric, label in VERIFIED_EVIDENCE_FIELDS:
        item = evidence_by_metric.get(metric)
        rows.append({
            "section": section,
            "metric": metric,
            "label": label,
            "display_value": format_analyst_evidence_value(item) if item is not None else "資料不足",
            "status": "available" if item is not None else "missing",
            "evidence_id": item.id if item is not None else None,
        })
    metrics = [row["metric"] for row in rows]
    if len(metrics) != len(set(metrics)):
        raise AIAnalystShortlistError("Verified evidence metrics must have unique section ownership.")
    return rows


def build_stage_two_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stage_two_cards = []
    for card in cards:
        validate_analyst_card(card)
        stage_two_cards.append({
            "symbol": card["symbol"],
            "company_name": card["company_name"],
            "research_priority": card["research_priority"],
            "opportunity_interpretation": card["opportunity_interpretation"],
            "fundamental_quality": card["fundamental_quality"],
            "valuation_context": card["valuation_context"],
            "market_confirmation": card["market_confirmation"],
            "risks": card["risks"],
            "contradictions": card["contradictions"],
            "missing_evidence": card["missing_evidence"],
            "next_checks": card["next_checks"],
            "evidence_refs": card["evidence_refs"],
            "verified_evidence_summary": [
                {
                    "metric": item["metric"],
                    "status": item["status"],
                    "evidence_id": item["evidence_id"],
                }
                for item in card["verified_evidence"]
            ],
        })
    return stage_two_cards


def validate_analyst_qualitative_answer(
    answer: GroundedResearchAnswer,
    context: SelectedResearchContext,
) -> None:
    if not answer.findings:
        raise AIAnalystShortlistError("AI_ANALYST_CARD_V0 requires grounded qualitative findings.")
    evidence_by_id = {item.id: item for item in context.selected_evidence}
    has_valuation_comparator = _has_valuation_comparator(context)
    for finding in answer.findings:
        cited_metrics = {
            evidence_by_id[evidence_id].metric
            for evidence_id in finding.evidence_ids
            if evidence_id in evidence_by_id
        }
        lowered = finding.statement.lower()
        required_metrics = set()
        required_metric_groups = []
        if ("年增" in finding.statement and "月增" in finding.statement) or (
            "revenue yoy" in lowered and "revenue mom" in lowered
        ):
            required_metrics.update({"revenue_yoy", "revenue_mom"})
        if ("負債" in finding.statement and "現金" in finding.statement) or (
            "total debt" in lowered and "total cash" in lowered
        ):
            required_metrics.update({"total_debt", "total_cash"})
        if "短中期" in finding.statement and ("相對" in finding.statement or "relative" in lowered):
            required_metrics.update({"rel_return_20d", "rel_return_60d"})
        if "營收方向" in finding.statement or "月營收" in finding.statement:
            required_metric_groups.append({"revenue_yoy", "revenue_mom", "revenue_growth"})
        if "相對市場" in finding.statement or "相對強弱" in finding.statement:
            required_metric_groups.append({"rel_return_20d", "rel_return_60d"})
        if "估值" in finding.statement:
            required_metric_groups.append(VALUATION_METRICS)
        if "市場位置" in finding.statement:
            required_metric_groups.append(MARKET_METRICS)
        if "roe" in lowered or "資本效率" in finding.statement:
            required_metrics.add("return_on_equity")
        if "獲利成長" in finding.statement or "earnings growth" in lowered:
            required_metrics.add("earnings_growth")
        if (
            cited_metrics & VALUATION_METRICS
            and not has_valuation_comparator
            and VALUATION_CLASSIFICATION_PATTERN.search(finding.statement)
            and not VALUATION_INSUFFICIENCY_PATTERN.search(finding.statement)
        ):
            raise AIAnalystValuationComparatorOverclaimError()
        if (cited_metrics & VALUATION_METRICS) and (cited_metrics & MARKET_METRICS):
            raise AIAnalystCardFormatError("SECTION_ROLE_OVERLAP")
        missing_required_metrics = not required_metrics.issubset(cited_metrics)
        missing_required_group = any(
            cited_metrics.isdisjoint(group) for group in required_metric_groups
        )
        if missing_required_metrics or missing_required_group:
            related_reference_exists = bool(cited_metrics & required_metrics) or any(
                bool(cited_metrics & group) for group in required_metric_groups
            )
            if related_reference_exists:
                raise AIAnalystMissingRequiredEvidenceRefsError()
            raise AIAnalystShortlistError(
                "Qualitative interpretation is missing required evidence references."
            )


def detect_contradictions(context: SelectedResearchContext) -> list[str]:
    values = {item.metric: item.value for item in context.selected_evidence}
    contradictions = []
    if _positive(values.get("revenue_yoy")) and _negative(values.get("revenue_mom")):
        contradictions.append("Revenue YoY 為正，但 Revenue MoM 為負。")
    if _positive(values.get("rel_return_60d")) and _negative(values.get("rel_return_20d")):
        contradictions.append("60D 相對強勢為正，但 20D 相對強勢為負。")
    if _positive(values.get("earnings_growth")) and not _positive(values.get("return_on_equity")):
        contradictions.append("Earnings Growth 為正，但 ROE 尚未形成正向確認。")
    return contradictions or ["目前未發現明確互相衝突的已驗證證據。"]


def detect_extreme_value_warnings(context: SelectedResearchContext) -> list[str]:
    values = {item.metric: item.value for item in context.selected_evidence}
    thresholds = {"revenue_yoy": 1.0, "revenue_mom": 1.0, "rel_return_60d": 0.7}
    if any(isinstance(values.get(metric), (int, float)) and values[metric] > limit for metric, limit in thresholds.items()):
        return ["極端數值，建議先驗證資料／基期。"]
    return []


def _radar_evidence(
    row: dict[str, Any],
    generated_at: datetime,
    *,
    canonical_radar_evidence: dict[str, Any] | None = None,
    canonical_resolution_requested: bool = False,
) -> tuple[list[EvidenceItem], list[MissingDataItem]]:
    internal = row.get("_analyst_evidence") if isinstance(row.get("_analyst_evidence"), dict) else {}
    resolved = canonical_radar_evidence or {}
    condition_flags = resolved.get("condition_flags") if canonical_resolution_requested else internal.get("condition_flags", row.get("研究條件"))
    if isinstance(condition_flags, list):
        condition_flags = "、".join(str(item) for item in condition_flags)
    values = {
        "revenue_period": resolved.get("revenue_period") if canonical_resolution_requested else internal.get("revenue_period", row.get("營收月份")),
        "revenue_yoy": resolved.get("revenue_yoy") if canonical_resolution_requested else internal.get("revenue_yoy", _percentage_value(row.get("Revenue YoY"))),
        "revenue_mom": resolved.get("revenue_mom") if canonical_resolution_requested else internal.get("revenue_mom", _percentage_value(row.get("Revenue MoM"))),
        "rel_return_20d": resolved.get("relative_return_20d") if canonical_resolution_requested else internal.get("relative_return_20d", _percentage_value(row.get("REL_RETURN_20D"))),
        "rel_return_60d": resolved.get("relative_return_60d") if canonical_resolution_requested else internal.get("relative_return_60d", _percentage_value(row.get("REL_RETURN_60D"))),
        "radar_condition_flags": condition_flags,
        "snapshot_retrieved_at": resolved.get("retrieved_at") if canonical_resolution_requested else internal.get("retrieved_at"),
        "long_term_research_availability": row.get("長期研究"),
        "historical_trends_availability": row.get("歷史趨勢"),
        "ai_research_availability": row.get("AI 研究"),
        "swing_research_availability": row.get("波段研究"),
    }
    period = _period_date(values["revenue_period"])
    evidence = []
    missing = []
    symbol = _required_text(row.get("股票代號"), "股票代號")
    for metric, value in values.items():
        unavailable = value is None or (
            isinstance(value, str) and value in {"", "N/A", "unavailable"}
        )
        if unavailable:
            missing.append(MissingDataItem(
                id=f"missing:radar:{symbol}:{metric}",
                area="opportunity_radar",
                metric=metric,
                period_end=period if metric.startswith("revenue") else None,
                period_year=period.year if period and metric.startswith("revenue") else None,
                reason="Current local Opportunity Radar data is unavailable.",
                impact="The analyst must preserve the missing state.",
                source="Opportunity Radar local snapshot",
            ))
            continue
        evidence.append(EvidenceItem(
            id=f"radar:{symbol}:{metric}",
            category="opportunity_radar",
            metric=metric,
            value=value,
            unit="ratio" if metric in {"revenue_yoy", "revenue_mom", "rel_return_20d", "rel_return_60d"} else None,
            currency=None,
            period_end=period if metric.startswith("revenue") else None,
            period_year=period.year if period and metric.startswith("revenue") else None,
            source="Opportunity Radar local snapshot",
            source_type="source",
            note=f"Local evidence package generated at {generated_at.isoformat()}.",
        ))
    return evidence, missing


def _extract_priority(answer: GroundedResearchAnswer) -> str:
    text = "\n".join([answer.summary, *(item.statement for item in answer.findings)])
    matches = [priority for priority in RESEARCH_PRIORITIES if priority in text]
    return matches[0] if len(matches) == 1 else "證據不足"


def _statements_for_metrics(answer, evidence_by_id, metrics):
    statements = []
    for finding in answer.findings:
        if any(evidence_by_id[item].metric in metrics for item in finding.evidence_ids if item in evidence_by_id):
            statements.append(finding.statement)
    return list(dict.fromkeys(statements))


def _section_text(answer, evidence_by_id, metrics):
    statements = _display_analyst_texts(_statements_for_metrics(answer, evidence_by_id, metrics))
    return "；".join(statements) if statements else "目前證據不足。"


def _has_valuation_comparator(context: SelectedResearchContext) -> bool:
    return any(
        "valuation" in item.metric
        and any(keyword in item.metric for keyword in VALUATION_COMPARATOR_METRIC_KEYWORDS)
        for item in context.selected_evidence
    )


def _evidence_dates(context: SelectedResearchContext) -> dict[str, str]:
    dates = {}
    for item in context.selected_evidence:
        if item.period_end is not None:
            dates[item.metric] = item.period_end.isoformat()
        if item.metric == "snapshot_retrieved_at" and isinstance(item.value, str):
            dates["radar_retrieved_at"] = item.value
    dates["context_generated_at"] = context.generated_at.isoformat()
    return dates


def _card_texts(card: dict[str, Any]) -> list[str]:
    texts = [card["company_name"], card["fundamental_quality"], card["valuation_context"], card["market_confirmation"]]
    for key in ("opportunity_interpretation", "risks", "contradictions", "missing_evidence", "next_checks"):
        texts.extend(
            text for text in card[key]
            if not _is_safe_investment_safety_diagnostic(text)
        )
    return texts


def _is_safe_investment_safety_diagnostic(text: str) -> bool:
    return bool(re.fullmatch(
        r"AI 初步審查失敗：AI 輸出未通過投資安全檢查。"
        r"（matched_rule=[A-Z_]+; matched_term=[^;（）]+; field=[a-z_]+）",
        text,
    ))


def _validate_prohibited_text(texts: list[str]) -> None:
    for text in texts:
        lowered = text.lower()
        if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in PROHIBITED_PATTERNS):
            raise AIAnalystShortlistError("AI output contains prohibited recommendation language.")


def _validate_stage_two_prohibited_text(texts_with_fields: list[tuple[str, str]]) -> None:
    for field, text in texts_with_fields:
        lowered = text.lower()
        for rule, pattern, term in STAGE_TWO_PROHIBITED_RULES:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                raise AIAnalystStageTwoPolicyError(rule=rule, term=term, field=field)
    _validate_prohibited_text([text for _field, text in texts_with_fields])


def _required_text(value: Any, field: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise AIAnalystShortlistError(f"{field} is required.")
    return text


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip() or value.strip() in {"N/A", "unavailable"}:
        return None
    return value.strip()


def _percentage_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip().endswith("%"):
        try:
            return float(value.strip()[:-1].replace(",", "")) / 100
        except ValueError:
            return None
    return None


def _period_date(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}", value):
        return None
    try:
        return date(int(value[:4]), int(value[5:]), 1)
    except ValueError:
        return None


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _negative(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value < 0
