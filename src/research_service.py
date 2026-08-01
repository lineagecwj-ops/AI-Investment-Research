from dataclasses import dataclass

from models import Stock
from research_metrics import calculate_52_week_position


@dataclass(frozen=True)
class ResearchObservation:

    category: str

    title: str

    metric: str

    what_happened: str

    why_it_matters: str

    what_to_check: list[str]

    observation_type: str = "attention"


@dataclass(frozen=True)
class ResearchNextStep:

    category: str

    title: str

    metric: str

    items: list[str]


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


def format_percent_snapshot(value: float) -> str:
    return f"{value:+.2%}"


def format_number_snapshot(value: float) -> str:
    return f"{value:,.2f}"


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
                metric="forward_pe",
                what_happened=(
                    "Forward P/E（預估本益比）目前低於 Trailing P/E（歷史本益比）"
                    f"至少 {int((1 - FORWARD_PE_LOWER_RATIO) * 100)}%。"
                ),
                why_it_matters=(
                    "這表示目前估值 snapshot 中，市場預估盈餘與過去盈餘使用的估值倍數不同，"
                    "值得進一步確認預估來源與假設。這不是單獨的便宜或昂貴判定。"
                ),
                what_to_check=[
                    "Forward EPS estimates（未來 EPS 預估）",
                    "同業 P/E 區間",
                    "公司歷史估值區間",
                    "產業循環與獲利假設",
                ],
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
                metric="revenue_growth",
                what_happened=(
                    "Revenue Growth（營收成長率）目前為 "
                    f"{format_percent_snapshot(stock.revenue_growth)}。"
                ),
                why_it_matters=(
                    "營收是觀察需求、價格與出貨變化的起點。單一 snapshot 為負值時，"
                    "值得進一步研究這是短期波動、產業週期，或公司產品組合變化。"
                ),
                what_to_check=[
                    "近年 Revenue（營收）變化",
                    "Segment revenue（部門營收）",
                    "產品組合與平均售價",
                    "產業需求與客戶庫存",
                ],
            )
        )

    if stock.earnings_growth is not None and stock.earnings_growth < 0:
        what_happened = (
            "Earnings Growth（盈餘成長率）目前為 "
            f"{format_percent_snapshot(stock.earnings_growth)}。"
        )
        if stock.revenue_growth is not None:
            what_happened += (
                " Revenue Growth（營收成長率）目前為 "
                f"{format_percent_snapshot(stock.revenue_growth)}。"
            )

        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="Earnings Growth（盈餘成長率）為負值",
                metric="earnings_growth",
                what_happened=what_happened,
                why_it_matters=(
                    "若目前 snapshot 中營收仍為正成長、但盈餘成長為負，"
                    "值得進一步研究收入如何轉化為獲利。"
                    "這不代表公司品質惡化，也不能直接判定原因。"
                )
                if stock.revenue_growth is not None and stock.revenue_growth >= 0
                else (
                    "盈餘成長率為負值時，值得進一步研究獲利率、費用結構與非經常性項目。"
                    "這不代表公司品質惡化，也不能直接判定原因。"
                ),
                what_to_check=[
                    "Gross Margin（毛利率）",
                    "Operating Margin（營業利益率）",
                    "Net Margin（淨利率）",
                    "費用結構",
                    "一次性 / 非經常性項目",
                ],
            )
        )

    if stock.free_cash_flow is not None and stock.free_cash_flow < 0:
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="Free Cash Flow（自由現金流）為負值",
                metric="free_cash_flow",
                what_happened=(
                    "Free Cash Flow（自由現金流）目前為 "
                    f"{format_number_snapshot(stock.free_cash_flow)}。"
                ),
                why_it_matters=(
                    "自由現金流可協助研究公司在營運與資本支出後留下多少現金。"
                    "負值值得追查，但不等同財務品質結論。"
                ),
                what_to_check=[
                    "Operating Cash Flow（營業現金流）",
                    "Capital Expenditure（資本支出）",
                    "近年 Free Cash Flow 變化",
                    "擴產或大型投資計畫",
                ],
            )
        )

    if stock.operating_cash_flow is not None and stock.operating_cash_flow < 0:
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="Operating Cash Flow（營業現金流）為負值",
                metric="operating_cash_flow",
                what_happened=(
                    "Operating Cash Flow（營業現金流）目前為 "
                    f"{format_number_snapshot(stock.operating_cash_flow)}。"
                ),
                why_it_matters=(
                    "營業現金流用來觀察核心營運是否產生現金。負值值得研究營運資金、收付款節奏與季節性因素。"
                ),
                what_to_check=[
                    "應收帳款與存貨變化",
                    "應付帳款與付款條件",
                    "季節性營運資金需求",
                    "Net Income 與 Operating Cash Flow 差異",
                ],
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
                metric="total_debt",
                what_happened=(
                    "Total Debt（總負債）目前為 "
                    f"{format_number_snapshot(stock.total_debt)}；Total Cash（現金）目前為 "
                    f"{format_number_snapshot(stock.total_cash)}。"
                ),
                why_it_matters=(
                    "負債高於現金時，值得放在公司資本結構、產業特性與現金流能力下研究。"
                    "這不是單獨的財務健康結論。"
                ),
                what_to_check=[
                    "Debt maturity（債務到期結構）",
                    "Interest expense（利息費用）",
                    "Operating Cash Flow 覆蓋能力",
                    "產業常見槓桿水準",
                ],
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
                metric="two_hundred_day_average",
                what_happened=(
                    "Current Price（目前股價）目前為 "
                    f"{format_number_snapshot(stock.current_price)}；200-day Average（200 日均價）目前為 "
                    f"{format_number_snapshot(stock.two_hundred_day_average)}。"
                ),
                why_it_matters=(
                    "價格低於 200 日均價是價格位置觀察，值得確認市場價格變化是否已有基本面或事件脈絡。"
                    "這不是投資結論。"
                ),
                what_to_check=[
                    "近期公司公告",
                    "最新財報重點",
                    "產業或同業價格表現",
                    "基本面指標是否同步變化",
                ],
            )
        )

    if position is not None and position > SIGNIFICANTLY_ABOVE_52_WEEK_POSITION:
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="Current Price（目前股價）明顯高於 52 週區間",
                metric="fifty_two_week_position",
                what_happened=(
                    "52-week Position（52 週區間位置）目前為 "
                    f"{format_percent_snapshot(position)}，高於目前資料中的 52-week range。"
                ),
                why_it_matters=(
                    "價格高於既有 52 週區間時，值得先確認資料時間是否一致，再研究近期事件與預期變化。"
                    "這不是高估或低估判定。"
                ),
                what_to_check=[
                    "價格與 52 週區間資料時間",
                    "近期重大公告或財報",
                    "Forward estimates 是否更新",
                    "同業估值與價格變化",
                ],
            )
        )

    if missing_fields:
        signals.append(
            ResearchObservation(
                category="Risk Signals（風險提示）",
                title="缺少關鍵研究欄位",
                metric="missing_fields",
                what_happened="目前缺少部分關鍵研究欄位：" + "、".join(missing_fields) + "。",
                why_it_matters=(
                    "資料不完整時，Research Dashboard 只能建立初步問題，"
                    "不應把缺資料情境下的 observation 當成完整研究結論。"
                ),
                what_to_check=[
                    "補齊缺漏欄位",
                    "交叉確認資料來源",
                    "確認 Yahoo snapshot 更新時間",
                    "保留 N/A 欄位的研究限制",
                ],
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
                metric="forward_pe",
                title="整理估值研究清單",
                items=[
                    "確認未來 EPS estimates 的來源與期間",
                    "比較同業 P/E 與 Forward P/E",
                    "比較公司歷史估值區間",
                ],
            )
        )

    if stock.revenue_growth is not None and stock.revenue_growth < 0:
        next_steps.append(
            ResearchNextStep(
                category="Growth（成長性）",
                metric="revenue_growth",
                title="整理營收研究清單",
                items=[
                    "比較近年 Revenue 變化",
                    "檢查部門或產品線營收分布",
                    "查詢產業需求與客戶庫存背景",
                ],
            )
        )

    if stock.earnings_growth is not None and stock.earnings_growth < 0:
        next_steps.append(
            ResearchNextStep(
                category="Growth（成長性）",
                metric="earnings_growth",
                title="整理獲利轉化研究清單",
                items=[
                    "比較近年 Revenue / EPS 變化",
                    "檢查 Gross / Operating / Net Margin 變化",
                    "確認是否存在非經常性損益",
                ],
            )
        )

    if stock.free_cash_flow is not None and stock.free_cash_flow < 0:
        next_steps.append(
            ResearchNextStep(
                category="Financial Health（財務健康）",
                metric="free_cash_flow",
                title="整理現金流研究清單",
                items=[
                    "比較近年 Operating Cash Flow 與 Free Cash Flow",
                    "檢查資本支出與擴產計畫",
                    "比對淨利與現金流方向",
                ],
            )
        )

    if missing_fields:
        next_steps.append(
            ResearchNextStep(
                category="Data Quality（資料完整性）",
                metric="missing_fields",
                title="整理資料補查清單",
                items=[
                    "優先補齊缺漏欄位",
                    "使用公司財報或交易所資料交叉確認",
                    "標記仍為 N/A 的研究限制",
                ],
            )
        )

    if not next_steps:
        next_steps.append(
            ResearchNextStep(
                category="Research Next Steps（下一步研究）",
                metric="baseline_research",
                title="建立基礎研究清單",
                items=[
                    "比較同業獲利能力與成長性",
                    "檢查公司近年財報與管理層說明",
                    "整理估值、現金流與產業脈絡",
                ],
            )
        )

    return next_steps
