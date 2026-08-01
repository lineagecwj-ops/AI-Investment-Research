from dataclasses import dataclass

from models import Stock
from research_metrics import calculate_52_week_position


@dataclass(frozen=True)
class ResearchObservation:

    category: str

    title: str

    message: str

    metric: str

    observation_type: str = "attention"


@dataclass(frozen=True)
class ResearchNextStep:

    category: str

    title: str

    question: str

    metric: str


@dataclass(frozen=True)
class ResearchReport:

    stock: Stock

    fifty_two_week_position: float | None

    market_position_note: str

    valuation_observations: list[ResearchObservation]

    risk_signals: list[ResearchObservation]

    next_steps: list[ResearchNextStep]

    missing_critical_fields: list[str]


CRITICAL_RESEARCH_FIELDS = {
    "company_summary": "Company Summary（公司業務摘要）",
    "sector": "Sector（產業類別）",
    "industry": "Industry（細分產業）",
    "market_cap": "Market Cap（市值）",
    "return_on_equity": "ROE（股東權益報酬率）",
    "gross_margin": "Gross Margin（毛利率）",
    "operating_margin": "Operating Margin（營業利益率）",
    "net_margin": "Net Margin（淨利率）",
    "revenue_growth": "Revenue Growth（營收成長率）",
    "earnings_growth": "Earnings Growth（盈餘成長率）",
    "total_cash": "Total Cash（現金）",
    "total_debt": "Total Debt（總負債）",
    "operating_cash_flow": "Operating Cash Flow（營業現金流）",
    "free_cash_flow": "Free Cash Flow（自由現金流）",
    "trailing_pe": "Trailing P/E（歷史本益比）",
    "forward_pe": "Forward P/E（預估本益比）",
    "price_to_book": "Price to Book（股價淨值比）",
    "fifty_two_week_high": "52-week High（52 週高點）",
    "fifty_two_week_low": "52-week Low（52 週低點）",
    "two_hundred_day_average": "200-day Average（200 日均價）",
}


FORWARD_PE_LOWER_RATIO = 0.85
SIGNIFICANTLY_ABOVE_52_WEEK_POSITION = 1.05


def build_research_report(stock: Stock) -> ResearchReport:
    position = calculate_52_week_position(stock)
    missing_fields = find_missing_critical_fields(stock)
    valuation_observations = build_valuation_observations(stock)
    risk_signals = build_risk_signals(stock, position, missing_fields)

    return ResearchReport(
        stock=stock,
        fifty_two_week_position=position,
        market_position_note=build_market_position_note(position),
        valuation_observations=valuation_observations,
        risk_signals=risk_signals,
        next_steps=build_research_next_steps(stock, valuation_observations, missing_fields),
        missing_critical_fields=missing_fields,
    )


def find_missing_critical_fields(stock: Stock) -> list[str]:
    missing_fields = []

    for field_name, label in CRITICAL_RESEARCH_FIELDS.items():
        value = getattr(stock, field_name)
        if value is None or value == "":
            missing_fields.append(label)

    return missing_fields


def build_market_position_note(position: float | None) -> str:
    if position is None:
        return "52-week Position 目前無法計算，可能缺少目前股價、52 週高點或 52 週低點。"

    if position < 0:
        return "目前價格已低於資料中的 52-week low；請確認價格與 52 週區間資料時間是否一致。"

    if position > 1:
        return "目前價格已高於資料中的 52-week high；請確認價格與 52 週區間資料時間是否一致。"

    return "52-week Position 只是目前價格在 52 週高低區間的位置，不是強弱評分，也不是買賣訊號。"


def build_valuation_observations(stock: Stock) -> list[ResearchObservation]:
    observations = []

    if is_forward_pe_meaningfully_lower(stock.trailing_pe, stock.forward_pe):
        observations.append(
            ResearchObservation(
                category="Valuation（估值）",
                title="Forward P/E 明顯低於 Trailing P/E",
                message=(
                    "Forward P/E 明顯低於 Trailing P/E，可能反映市場預期未來盈餘較過去改善，"
                    "仍需進一步確認盈利預估與產業循環。"
                ),
                metric="forward_pe",
                observation_type="info",
            )
        )

    return observations


def is_forward_pe_meaningfully_lower(
    trailing_pe: float | None,
    forward_pe: float | None,
) -> bool:
    if trailing_pe is None or forward_pe is None:
        return False

    if trailing_pe <= 0 or forward_pe <= 0:
        return False

    return forward_pe <= trailing_pe * FORWARD_PE_LOWER_RATIO


def build_risk_signals(
    stock: Stock,
    fifty_two_week_position: float | None = None,
    missing_critical_fields: list[str] | None = None,
) -> list[ResearchObservation]:
    position = (
        calculate_52_week_position(stock)
        if fifty_two_week_position is None
        else fifty_two_week_position
    )
    missing_fields = (
        find_missing_critical_fields(stock)
        if missing_critical_fields is None
        else missing_critical_fields
    )
    signals = []

    if stock.revenue_growth is not None and stock.revenue_growth < 0:
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="Revenue Growth（營收成長率）為負值",
                message=(
                    "Revenue Growth（營收成長率）目前為負值。這不一定代表公司長期競爭力下降，"
                    "建議進一步檢查營收下降是否來自產業週期、產品轉換或公司特定因素。"
                ),
                metric="revenue_growth",
            )
        )

    if stock.earnings_growth is not None and stock.earnings_growth < 0:
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="Earnings Growth（盈餘成長率）為負值",
                message=(
                    "Earnings Growth（盈餘成長率）目前為負值。這不一定代表公司品質惡化，"
                    "建議進一步查看毛利率、營業利益率與一次性費用是否影響近期獲利。"
                ),
                metric="earnings_growth",
            )
        )

    if stock.free_cash_flow is not None and stock.free_cash_flow < 0:
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="Free Cash Flow（自由現金流）為負值",
                message=(
                    "Free Cash Flow（自由現金流）目前為負值。這不一定代表公司財務惡化，"
                    "可能與資本支出、擴產或營運週期有關。建議進一步查看近年自由現金流趨勢與資本支出。"
                ),
                metric="free_cash_flow",
            )
        )

    if stock.operating_cash_flow is not None and stock.operating_cash_flow < 0:
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="Operating Cash Flow（營業現金流）為負值",
                message=(
                    "Operating Cash Flow（營業現金流）目前為負值。建議進一步確認是否為營運資金變動、"
                    "季節性因素或核心營運現金創造能力的變化。"
                ),
                metric="operating_cash_flow",
            )
        )

    if (
        stock.total_debt is not None
        and stock.total_cash is not None
        and stock.total_debt > stock.total_cash
    ):
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="Total Debt（總負債）高於 Total Cash（現金）",
                message=(
                    "Total Debt（總負債）高於 Total Cash（現金）。這需要放在同一幣別與公司資本結構下理解，"
                    "建議進一步查看債務到期結構、利息費用與營業現金流覆蓋能力。"
                ),
                metric="total_debt",
            )
        )

    if (
        stock.current_price is not None
        and stock.two_hundred_day_average is not None
        and stock.current_price < stock.two_hundred_day_average
    ):
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="Current Price（目前股價）低於 200-day Average（200 日均價）",
                message=(
                    "Current Price（目前股價）低於 200-day Average（200 日均價）。"
                    "這只是價格位置觀察，不是趨勢或投資結論；建議進一步確認近期價格變動原因與基本面是否同步改變。"
                ),
                metric="two_hundred_day_average",
            )
        )

    if position is not None and position > SIGNIFICANTLY_ABOVE_52_WEEK_POSITION:
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="Current Price（目前股價）明顯高於 52 週區間",
                message=(
                    "Current Price（目前股價）明顯高於目前資料中的 52-week range。"
                    "建議確認資料時間差、近期重大事件，以及市場對未來成長預期是否已有充分依據。"
                ),
                metric="fifty_two_week_position",
            )
        )

    if missing_fields:
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="缺少關鍵研究欄位",
                message=(
                    "目前缺少部分關鍵研究欄位，因此部分判讀只能作為初步觀察。"
                    "建議補齊或交叉確認這些欄位："
                    + "、".join(missing_fields)
                    + "。"
                ),
                metric="missing_fields",
                observation_type="info",
            )
        )

    return signals


def build_research_next_steps(
    stock: Stock,
    valuation_observations: list[ResearchObservation] | None = None,
    missing_critical_fields: list[str] | None = None,
) -> list[ResearchNextStep]:
    valuation_items = valuation_observations or build_valuation_observations(stock)
    missing_fields = (
        find_missing_critical_fields(stock)
        if missing_critical_fields is None
        else missing_critical_fields
    )
    next_steps = []

    if any(item.metric == "forward_pe" for item in valuation_items):
        next_steps.append(
            ResearchNextStep(
                category="Valuation（估值）",
                title="確認 forward earnings 假設",
                question="確認市場對未來 EPS 的預估來源，並比較未來 1-2 年 earnings estimates。",
                metric="forward_pe",
            )
        )

    if stock.revenue_growth is not None and stock.revenue_growth < 0:
        next_steps.append(
            ResearchNextStep(
                category="Growth（成長性）",
                title="拆解營收下降原因",
                question="檢查營收下降是否為產業週期、產品轉換或公司特定因素。",
                metric="revenue_growth",
            )
        )

    if stock.earnings_growth is not None and stock.earnings_growth < 0:
        next_steps.append(
            ResearchNextStep(
                category="Growth（成長性）",
                title="比對盈餘與利潤率",
                question="檢查盈餘下降是否與毛利率、營業利益率、費用結構或一次性項目有關。",
                metric="earnings_growth",
            )
        )

    if stock.free_cash_flow is not None and stock.free_cash_flow < 0:
        next_steps.append(
            ResearchNextStep(
                category="Financial Health（財務健康）",
                title="追蹤自由現金流來源",
                question="查看近年自由現金流趨勢、資本支出與營運現金流，判斷負值是否為短期投資或營運壓力。",
                metric="free_cash_flow",
            )
        )

    if missing_fields:
        next_steps.append(
            ResearchNextStep(
                category="Data Quality（資料完整性）",
                title="補齊缺漏欄位",
                question="優先交叉確認缺漏欄位，避免只根據不完整 snapshot 形成研究結論。",
                metric="missing_fields",
            )
        )

    if not next_steps:
        next_steps.append(
            ResearchNextStep(
                category="Research Next Steps（下一步研究）",
                title="建立同業與歷史脈絡",
                question="比較同業的獲利能力、成長性、估值與現金流，並檢查公司近年趨勢是否支持目前 snapshot。",
                metric="baseline_research",
            )
        )

    return next_steps
