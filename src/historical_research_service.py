from dataclasses import dataclass
from datetime import date

from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries
from research_metrics import are_consecutive_years
from research_metrics import calculate_eps_yoy_growth
from research_metrics import calculate_yoy_growth
from research_service import ResearchNextStep
from research_service import ResearchObservation


@dataclass(frozen=True)
class HistoricalResearchReport:

    series: HistoricalFinancialSeries

    observations: list[ResearchObservation]

    next_steps: list[ResearchNextStep]


@dataclass(frozen=True)
class PeriodChange:

    previous_period: HistoricalFinancialPeriod

    current_period: HistoricalFinancialPeriod

    previous_value: float

    current_value: float

    absolute_change: float

    relative_change: float | None


HISTORICAL_CATEGORIES = [
    "Revenue（營收）",
    "Earnings（獲利）",
    "Margins（利潤率）",
    "Cash Flow（現金流）",
    "Financial Position（財務結構）",
    "Data Quality（資料完整性）",
]


def build_historical_research_report(
    series: HistoricalFinancialSeries,
) -> HistoricalResearchReport:
    observations = []
    observations.extend(build_revenue_observations(series))
    observations.extend(build_earnings_observations(series))
    observations.extend(build_margin_observations(series))
    observations.extend(build_cash_flow_observations(series))
    observations.extend(build_financial_position_observations(series))
    observations.extend(build_cross_metric_observations(series))
    observations.extend(build_missing_data_observations(series))

    return HistoricalResearchReport(
        series=series,
        observations=observations,
        next_steps=build_historical_next_steps(observations),
    )


def build_revenue_observations(
    series: HistoricalFinancialSeries,
) -> list[ResearchObservation]:
    changes = consecutive_period_changes(series, "revenue")
    observations = []

    if count_valid_periods(series, "revenue") < 2:
        return [
            ResearchObservation(
                category="Data Quality（資料完整性）",
                title="Revenue 歷史資料不足",
                metric="revenue",
                what_happened="Revenue 少於 2 個有效年度，暫時無法計算 period-to-period change。",
                why_it_matters="歷史趨勢至少需要兩個有效年度；資料不足時不應建立趨勢結論。",
                what_to_check=[
                    "補查 Yahoo Finance annual revenue",
                    "確認公司年度財報 Revenue",
                    "標記目前 N/A 對研究判讀的限制",
                ],
                observation_type="info",
            )
        ]

    observations.extend(build_gap_observations(series, "revenue", "Revenue"))
    if not changes:
        return observations

    latest = changes[-1]
    direction = change_direction(latest.absolute_change)
    if direction == "up":
        observations.append(
            ResearchObservation(
                category="Revenue（營收）",
                title="最新年度 Revenue 增加",
                metric="revenue",
                what_happened=(
                    f"{period_label(latest.current_period)} Revenue 較 "
                    f"{period_label(latest.previous_period)} 增加 "
                    f"{format_signed_percent(latest.relative_change)}，由 "
                    f"{format_currency_amount(latest.previous_value, series_currency(series, latest.previous_period))} "
                    f"至 {format_currency_amount(latest.current_value, series_currency(series, latest.current_period))}。"
                ),
                why_it_matters="Revenue 變化是研究需求、價格、出貨與產品組合的起點。",
                what_to_check=[
                    "各年度主要產品或地區營收變化",
                    "產業需求是否同步變化",
                    "同業同期 Revenue 趨勢",
                ],
                observation_type="info",
            )
        )
    elif direction == "down":
        observations.append(
            ResearchObservation(
                category="Revenue（營收）",
                title="最新年度 Revenue 下降",
                metric="revenue",
                what_happened=(
                    f"{period_label(latest.current_period)} Revenue 較 "
                    f"{period_label(latest.previous_period)} 下降 "
                    f"{format_abs_percent(latest.relative_change)}，由 "
                    f"{format_currency_amount(latest.previous_value, series_currency(series, latest.previous_period))} "
                    f"至 {format_currency_amount(latest.current_value, series_currency(series, latest.current_period))}。"
                ),
                why_it_matters="Revenue 下降時，值得進一步拆解是價格、數量、產品組合或市場需求哪一部分需要追查。",
                what_to_check=[
                    "Segment revenue（部門營收）",
                    "產品組合與平均售價",
                    "產業需求與客戶庫存",
                ],
            )
        )

    if len(changes) >= 2:
        previous = changes[-2]
        latest_direction = change_direction(latest.absolute_change)
        previous_direction = change_direction(previous.absolute_change)
        if len(changes) >= 3:
            earlier = changes[-3]
            earlier_direction = change_direction(earlier.absolute_change)
            if (
                is_connected_change_chain([earlier, previous, latest])
                and all_relative_changes_available([earlier, previous, latest])
                and earlier_direction == "down"
                and previous_direction == "up"
                and latest_direction == "up"
            ):
                observations.append(
                    ResearchObservation(
                        category="Revenue（營收）",
                        title="Revenue 前期下降後連續回升",
                        metric="revenue",
                        what_happened=(
                            f"Revenue 在 {period_label(earlier.current_period)} 較前一年下降 "
                            f"{format_abs_percent(earlier.relative_change)}，"
                            f"{period_label(previous.current_period)} 回升 "
                            f"{format_signed_percent(previous.relative_change)}，"
                            f"{period_label(latest.current_period)} 再增加 "
                            f"{format_signed_percent(latest.relative_change)}。"
                        ),
                        why_it_matters="這表示近年的 Revenue 變化不是單一直線，而是先下降後連續回升。",
                        what_to_check=[
                            "產業循環是否同步變化",
                            "產品需求與價格",
                            "公司特定事件或產品組合變化",
                        ],
                        observation_type="info",
                    )
                )
        if previous_direction == "up" and latest_direction == "up":
            observations.append(
                ResearchObservation(
                    category="Revenue（營收）",
                    title="Revenue 連續兩期增加",
                    metric="revenue",
                    what_happened=(
                        f"Revenue 在 {period_label(previous.current_period)} 增加 "
                        f"{format_signed_percent(previous.relative_change)}，"
                        f"{period_label(latest.current_period)} 再增加 "
                        f"{format_signed_percent(latest.relative_change)}。"
                    ),
                    why_it_matters="連續兩期增加表示近期可取得資料中 Revenue 方向一致，後續仍需確認來源與持續性。",
                    what_to_check=[
                        "主要產品或地區營收拆分",
                        "同業同期 Revenue 趨勢",
                        "管理層對需求與出貨的說明",
                    ],
                    observation_type="info",
                )
            )
        elif previous_direction == "down" and latest_direction == "down":
            observations.append(
                ResearchObservation(
                    category="Revenue（營收）",
                    title="Revenue 連續兩期下降",
                    metric="revenue",
                    what_happened=(
                        f"Revenue 在 {period_label(previous.current_period)} 下降 "
                        f"{format_abs_percent(previous.relative_change)}，"
                        f"{period_label(latest.current_period)} 再下降 "
                        f"{format_abs_percent(latest.relative_change)}。"
                    ),
                    why_it_matters="連續兩期下降表示近期可取得資料中 Revenue 方向一致向下，需要把原因作為後續研究題目。",
                    what_to_check=[
                        "客戶需求與庫存變化",
                        "產品價格與出貨量",
                        "同業同期 Revenue 趨勢",
                    ],
                )
            )
        elif previous_direction == "down" and latest_direction == "up":
            observations.append(
                ResearchObservation(
                    category="Revenue（營收）",
                    title="Revenue 前期下降後回升",
                    metric="revenue",
                    what_happened=(
                        f"Revenue 在 {period_label(previous.current_period)} 較前一年下降 "
                        f"{format_abs_percent(previous.relative_change)}，"
                        f"{period_label(latest.current_period)} 回升 "
                        f"{format_signed_percent(latest.relative_change)}。"
                    ),
                    why_it_matters="這表示近年的 Revenue 變化不是單一直線，而是先下降後回升。",
                    what_to_check=[
                        "產業循環是否同步變化",
                        "產品需求與價格",
                        "公司特定事件或產品組合變化",
                    ],
                    observation_type="info",
                )
            )
        elif previous_direction == "up" and latest_direction == "down":
            observations.append(
                ResearchObservation(
                    category="Revenue（營收）",
                    title="Revenue 前期增加後下降",
                    metric="revenue",
                    what_happened=(
                        f"Revenue 在 {period_label(previous.current_period)} 增加 "
                        f"{format_signed_percent(previous.relative_change)}，"
                        f"{period_label(latest.current_period)} 轉為下降 "
                        f"{format_abs_percent(latest.relative_change)}。"
                    ),
                    why_it_matters="Revenue 方向轉變時，值得確認前期增加與最新下降背後的業務脈絡是否不同。",
                    what_to_check=[
                        "產品與客戶組合變化",
                        "產業需求與庫存週期",
                        "一次性大型訂單或基期差異",
                    ],
                )
            )

    return observations


def build_earnings_observations(
    series: HistoricalFinancialSeries,
) -> list[ResearchObservation]:
    observations = []
    observations.extend(build_latest_relationship_observations(series))
    observations.extend(build_eps_observations(series))
    return observations


def build_latest_relationship_observations(
    series: HistoricalFinancialSeries,
) -> list[ResearchObservation]:
    revenue_changes = consecutive_period_changes(series, "revenue")
    net_income_changes = consecutive_period_changes(series, "net_income")
    if not revenue_changes or not net_income_changes:
        return []

    revenue_latest = revenue_changes[-1]
    matched = next(
        (
            change
            for change in reversed(net_income_changes)
            if change.previous_period.period_end == revenue_latest.previous_period.period_end
            and change.current_period.period_end == revenue_latest.current_period.period_end
        ),
        None,
    )
    if matched is None:
        return []

    revenue_direction = change_direction(revenue_latest.absolute_change)
    net_income_direction = change_direction(matched.absolute_change)
    if revenue_direction == "flat" or net_income_direction == "flat":
        return []

    if revenue_direction == net_income_direction:
        return [
            ResearchObservation(
                category="Earnings（獲利）",
                title="Revenue 與 Net Income 最新年度同方向",
                metric="net_income",
                what_happened=(
                    f"{period_label(revenue_latest.current_period)} Revenue 與 Net Income "
                    f"相較 {period_label(revenue_latest.previous_period)} 同方向"
                    f"{direction_text(revenue_direction)}。"
                ),
                why_it_matters="Revenue 與 Net Income 同方向時，可進一步研究收入變化如何轉化為獲利變化。",
                what_to_check=[
                    "Gross Margin",
                    "Operating Margin",
                    "費用結構",
                    "一次性 / 非經常性項目",
                ],
                observation_type="info",
            )
        ]

    return [
        ResearchObservation(
            category="Earnings（獲利）",
            title="Revenue 與 Net Income 最新年度方向不同",
            metric="net_income",
            what_happened=(
                f"{period_label(revenue_latest.current_period)} Revenue "
                f"{direction_text(revenue_direction)}，但 Net Income "
                f"{direction_text(net_income_direction)}。"
            ),
            why_it_matters="營收與淨利方向不同，代表值得進一步研究收入轉化為獲利的過程。",
            what_to_check=[
                "Gross Margin",
                "Operating Margin",
                "expenses",
                "non-operating items",
                "tax",
                "one-time / non-recurring items",
            ],
        )
    ]


def build_eps_observations(series: HistoricalFinancialSeries) -> list[ResearchObservation]:
    observations = []
    eps_changes = consecutive_period_changes(series, "eps", use_eps_growth=True)
    net_income_changes = consecutive_period_changes(series, "net_income")

    if count_valid_periods(series, "eps") < 2:
        latest_period = latest_period_with_any_value(series)
        if latest_period is not None and latest_period.eps is None:
            observations.append(
                ResearchObservation(
                    category="Data Quality（資料完整性）",
                    title="最新年度 EPS unavailable",
                    metric="eps",
                    what_happened=(
                        f"Yahoo Finance 目前未提供 {period_label(latest_period)} EPS，"
                        f"因此無法計算 {period_label(latest_period)} EPS YoY。"
                    ),
                    why_it_matters="EPS 缺漏會限制每股盈餘趨勢與 EPS YoY 判讀；系統不自行計算 Yahoo 未提供的 EPS。",
                    what_to_check=[
                        "公司年度財報 EPS",
                        "Yahoo Finance 後續資料更新",
                        "股本或股數變化",
                    ],
                    observation_type="info",
                )
            )
        return observations

    if eps_changes and net_income_changes:
        eps_latest = eps_changes[-1]
        matched = next(
            (
                change
                for change in reversed(net_income_changes)
                if change.previous_period.period_end == eps_latest.previous_period.period_end
                and change.current_period.period_end == eps_latest.current_period.period_end
            ),
            None,
        )
        if matched is not None:
            eps_direction = change_direction(eps_latest.absolute_change)
            net_income_direction = change_direction(matched.absolute_change)
            if eps_direction != "flat" and eps_direction == net_income_direction:
                observations.append(
                    ResearchObservation(
                        category="Earnings（獲利）",
                        title="EPS 與 Net Income 最新年度同方向",
                        metric="eps",
                        what_happened=(
                            f"{period_label(eps_latest.current_period)} EPS 與 Net Income "
                            f"相較 {period_label(eps_latest.previous_period)} 同方向"
                            f"{direction_text(eps_direction)}。"
                        ),
                        why_it_matters="EPS 與 Net Income 同方向時，仍需搭配股數變化與一次性項目理解每股盈餘品質。",
                        what_to_check=[
                            "Weighted average shares",
                            "Net Income",
                            "一次性 / 非經常性項目",
                        ],
                        observation_type="info",
                    )
                )

    if len(eps_changes) >= 2:
        previous = eps_changes[-2]
        latest = eps_changes[-1]
        previous_direction = change_direction(previous.absolute_change)
        latest_direction = change_direction(latest.absolute_change)
        if previous_direction == "down" and latest_direction == "up":
            observations.append(
                ResearchObservation(
                    category="Earnings（獲利）",
                    title="EPS 前期下降後回升",
                    metric="eps",
                    what_happened=(
                        f"EPS 在 {period_label(previous.current_period)} 下降 "
                        f"{format_abs_percent(previous.relative_change)}，"
                        f"{period_label(latest.current_period)} 回升 "
                        f"{format_signed_percent(latest.relative_change)}。"
                    ),
                    why_it_matters="EPS 先下降後回升時，值得確認每股盈餘變化是否與營收、利潤率及股數變化一致。",
                    what_to_check=[
                        "Revenue",
                        "Net Income",
                        "Margins",
                        "股數變化",
                    ],
                    observation_type="info",
                )
            )
        elif previous_direction == "down" and latest_direction == "down":
            observations.append(
                ResearchObservation(
                    category="Earnings（獲利）",
                    title="EPS 連續兩期下降",
                    metric="eps",
                    what_happened=(
                        f"EPS 在 {period_label(previous.current_period)} 下降 "
                        f"{format_abs_percent(previous.relative_change)}，"
                        f"{period_label(latest.current_period)} 再下降 "
                        f"{format_abs_percent(latest.relative_change)}。"
                    ),
                    why_it_matters="EPS 連續下降時，需要進一步研究每股盈餘與淨利、利潤率及股數變化之間的關係。",
                    what_to_check=[
                        "Net Income",
                        "Gross / Operating / Net Margin",
                        "股數變化",
                    ],
                )
            )

    latest_period = latest_period_with_any_value(series)
    if latest_period is not None and latest_period.eps is None:
        observations.append(
            ResearchObservation(
                category="Data Quality（資料完整性）",
                title="最新年度 EPS unavailable",
                metric="eps",
                what_happened=(
                    f"Yahoo Finance 目前未提供 {period_label(latest_period)} EPS，"
                    f"因此無法計算 {period_label(latest_period)} EPS YoY。"
                ),
                why_it_matters="EPS 缺漏會限制最新年度每股盈餘趨勢判讀；系統不自行計算 Yahoo 未提供的 EPS。",
                what_to_check=[
                    "公司年度財報 EPS",
                    "Yahoo Finance 後續資料更新",
                    "股本或股數變化",
                ],
                observation_type="info",
            )
        )

    return observations


def build_margin_observations(series: HistoricalFinancialSeries) -> list[ResearchObservation]:
    observations = []
    for field, label in [
        ("gross_margin", "Gross Margin"),
        ("operating_margin", "Operating Margin"),
        ("net_margin", "Net Margin"),
    ]:
        changes = consecutive_period_changes(series, field)
        if count_valid_periods(series, field) < 2:
            continue
        if not changes:
            observations.extend(build_gap_observations(series, field, label))
            continue

        latest = changes[-1]
        direction = change_direction(latest.absolute_change)
        if direction == "flat":
            continue
        observations.append(
            ResearchObservation(
                category="Margins（利潤率）",
                title=f"{label} 最新年度{direction_text(direction)}",
                metric=field,
                what_happened=(
                    f"{period_label(latest.current_period)} {label} 較 "
                    f"{period_label(latest.previous_period)} "
                    f"{direction_text(direction)} {format_percentage_points(latest.absolute_change)}，"
                    f"由 {format_percent(latest.previous_value)} 至 "
                    f"{format_percent(latest.current_value)}。"
                ),
                why_it_matters="Margin 變化可協助研究收入扣除成本與費用後的轉化情況；單一變化不是公司品質結論。",
                what_to_check=[
                    "產品組合",
                    "成本結構",
                    "營業費用變化",
                    "一次性 / 非經常性項目",
                ],
                observation_type="info" if direction == "up" else "attention",
            )
        )
    return observations


def build_cash_flow_observations(series: HistoricalFinancialSeries) -> list[ResearchObservation]:
    observations = []
    latest = latest_period_with_any_value(series)
    if latest is None:
        return observations

    if latest.operating_cash_flow is not None:
        ocf_state = cash_flow_state_text(latest.operating_cash_flow)
        observations.append(
            ResearchObservation(
                category="Cash Flow（現金流）",
                title="最新年度 Operating Cash Flow 狀態",
                metric="operating_cash_flow",
                what_happened=(
                    f"{period_label(latest)} Operating Cash Flow 為 "
                    f"{format_currency_amount(latest.operating_cash_flow, series_currency(series, latest))}，"
                    f"{ocf_state}。"
                ),
                why_it_matters="Operating Cash Flow 用來研究本業活動是否產生現金，需要搭配 Net Income 與營運資金變化。",
                what_to_check=[
                    "Net Income 與 Operating Cash Flow 差異",
                    "應收帳款與存貨變化",
                    "營運資金需求",
                ],
                observation_type="info" if latest.operating_cash_flow >= 0 else "attention",
            )
        )

    if latest.free_cash_flow is None:
        observations.append(
            ResearchObservation(
                category="Data Quality（資料完整性）",
                title="Free Cash Flow unavailable",
                metric="free_cash_flow",
                what_happened=f"{period_label(latest)} Free Cash Flow 目前為 N/A。",
                why_it_matters="Free Cash Flow 缺漏會限制營運現金流扣除資本支出後的研究判讀。",
                what_to_check=[
                    "Yahoo Finance Free Cash Flow",
                    "Operating Cash Flow",
                    "Capital Expenditure",
                ],
                observation_type="info",
            )
        )
    else:
        fcf_state = cash_flow_state_text(latest.free_cash_flow)
        observations.append(
            ResearchObservation(
                category="Cash Flow（現金流）",
                title="最新年度 Free Cash Flow 狀態",
                metric="free_cash_flow",
                what_happened=(
                    f"{period_label(latest)} Free Cash Flow 為 "
                    f"{format_currency_amount(latest.free_cash_flow, series_currency(series, latest))}，"
                    f"{fcf_state}。"
                ),
                why_it_matters="Free Cash Flow 可協助研究營運現金流扣除資本支出後留下的現金。",
                what_to_check=[
                    "Operating Cash Flow",
                    "Capital Expenditure",
                    "投資計畫與擴產說明",
                ],
                observation_type="info" if latest.free_cash_flow >= 0 else "attention",
            )
        )

    fcf_changes = consecutive_period_changes(series, "free_cash_flow")
    if fcf_changes:
        current = fcf_changes[-1]
        if current.previous_value > 0 and current.current_value > 0:
            observations.append(
                ResearchObservation(
                    category="Cash Flow（現金流）",
                    title="Free Cash Flow 連續年度為正",
                    metric="free_cash_flow",
                    what_happened=(
                        f"Free Cash Flow 在 {period_label(current.previous_period)} 與 "
                        f"{period_label(current.current_period)} 皆維持正值。"
                    ),
                    why_it_matters="連續正值代表可取得年度資料中營運與資本支出後仍留下現金，後續仍需確認用途與持續性。",
                    what_to_check=[
                        "資本支出用途",
                        "股利與庫藏股",
                        "後續 Operating Cash Flow",
                    ],
                    observation_type="info",
                )
            )
        elif current.previous_value > 0 and current.current_value < 0:
            observations.append(
                ResearchObservation(
                    category="Cash Flow（現金流）",
                    title="Free Cash Flow 轉為負值",
                    metric="free_cash_flow",
                    what_happened=(
                        f"{period_label(current.current_period)} Free Cash Flow 由正值轉為負值，"
                        f"由 {format_currency_amount(current.previous_value, series_currency(series, current.previous_period))} "
                        f"至 {format_currency_amount(current.current_value, series_currency(series, current.current_period))}。"
                    ),
                    why_it_matters="FCF 轉負時，值得分開檢查營運現金流與資本支出的變化。",
                    what_to_check=[
                        "Operating Cash Flow",
                        "Capital Expenditure",
                        "資本支出用途",
                    ],
                )
            )
        elif current.previous_value < 0 and current.current_value > 0:
            observations.append(
                ResearchObservation(
                    category="Cash Flow（現金流）",
                    title="Free Cash Flow 回到正值",
                    metric="free_cash_flow",
                    what_happened=(
                        f"{period_label(current.current_period)} Free Cash Flow 由負值回到正值，"
                        f"由 {format_currency_amount(current.previous_value, series_currency(series, current.previous_period))} "
                        f"至 {format_currency_amount(current.current_value, series_currency(series, current.current_period))}。"
                    ),
                    why_it_matters="FCF 回到正值時，值得確認是營運現金流、資本支出或兩者共同變化。",
                    what_to_check=[
                        "Operating Cash Flow",
                        "Capital Expenditure",
                        "後續年度現金流",
                    ],
                    observation_type="info",
                )
            )

    capex_changes = consecutive_period_changes(series, "capital_expenditure")
    if capex_changes:
        capex = capex_changes[-1]
        previous_spending = abs(capex.previous_value)
        current_spending = abs(capex.current_value)
        if current_spending != previous_spending:
            direction = "增加" if current_spending > previous_spending else "下降"
            observations.append(
                ResearchObservation(
                    category="Cash Flow（現金流）",
                    title=f"Capital Expenditure 現金支出規模{direction}",
                    metric="capital_expenditure",
                    what_happened=(
                        f"{period_label(capex.current_period)} Capital Expenditure 現金支出規模"
                        f"由 {format_currency_amount(previous_spending, series_currency(series, capex.previous_period))} "
                        f"{direction}至 "
                        f"{format_currency_amount(current_spending, series_currency(series, capex.current_period))}。"
                    ),
                    why_it_matters="Yahoo Finance 的 Capital Expenditure 常以負數表示 cash outflow；研究支出規模時應比較絕對值。",
                    what_to_check=[
                        "資本支出用途",
                        "管理層擴產計畫",
                        "後續 Operating Cash Flow 是否支持投資",
                    ],
                    observation_type="info",
                )
            )

    return observations


def build_financial_position_observations(
    series: HistoricalFinancialSeries,
) -> list[ResearchObservation]:
    observations = []
    observations.extend(build_balance_metric_observation(series, "cash_and_cash_equivalents", "Cash"))
    observations.extend(build_balance_metric_observation(series, "total_debt", "Total Debt"))
    observations.extend(build_balance_metric_observation(series, "total_assets", "Total Assets"))
    observations.extend(build_balance_metric_observation(series, "total_equity", "Total Equity"))
    return observations


def build_balance_metric_observation(
    series: HistoricalFinancialSeries,
    field: str,
    label: str,
) -> list[ResearchObservation]:
    changes = consecutive_period_changes(series, field)
    if count_valid_periods(series, field) < 2:
        return []
    if not changes:
        return build_gap_observations(series, field, label)

    latest = changes[-1]
    direction = change_direction(latest.absolute_change)
    if direction == "flat":
        return []

    return [
        ResearchObservation(
            category="Financial Position（財務結構）",
            title=f"{label} 最新年度{direction_text(direction)}",
            metric=field,
            what_happened=(
                f"{period_label(latest.current_period)} {label} 較 "
                f"{period_label(latest.previous_period)} {direction_text(direction)}，"
                f"由 {format_currency_amount(latest.previous_value, series_currency(series, latest.previous_period))} "
                f"至 {format_currency_amount(latest.current_value, series_currency(series, latest.current_period))}。"
            ),
            why_it_matters="Financial Position 的歷史變化可協助研究資本結構、流動性與資金需求。",
            what_to_check=[
                "debt maturity",
                "interest expense",
                "free cash flow",
                "liquidity needs",
                "capital expenditure",
            ],
            observation_type="info",
        )
    ]


def build_cross_metric_observations(
    series: HistoricalFinancialSeries,
) -> list[ResearchObservation]:
    observations = []
    latest = latest_period_with_any_value(series)
    previous = previous_consecutive_period(series, latest) if latest is not None else None
    if latest is None or previous is None:
        return observations

    revenue_change = same_period_change(previous, latest, "revenue")
    net_income_change = same_period_change(previous, latest, "net_income")
    operating_margin_change = same_period_change(previous, latest, "operating_margin")
    fcf_change = same_period_change(previous, latest, "free_cash_flow")

    if revenue_change is not None and net_income_change is not None:
        if revenue_change > 0 and net_income_change < 0:
            observations.append(
                ResearchObservation(
                    category="Cross Metric（跨指標）",
                    title="Revenue 增加但 Net Income 下降",
                    metric="revenue_net_income",
                    what_happened=(
                        f"{period_label(latest)} Revenue 較 {period_label(previous)} 增加，"
                        "但 Net Income 同期下降。"
                    ),
                    why_it_matters="收入與淨利方向不同，代表值得進一步研究收入轉化為獲利的過程。",
                    what_to_check=[
                        "Gross Margin",
                        "Operating Margin",
                        "expenses",
                        "non-operating items",
                        "tax",
                    ],
                )
            )

    if revenue_change is not None and operating_margin_change is not None:
        if revenue_change > 0 and operating_margin_change < 0:
            observations.append(
                ResearchObservation(
                    category="Cross Metric（跨指標）",
                    title="Revenue 增加但 Operating Margin 下降",
                    metric="revenue_operating_margin",
                    what_happened=(
                        f"{period_label(latest)} Revenue 較 {period_label(previous)} 增加，"
                        f"但 Operating Margin 同期下降 {format_percentage_points(operating_margin_change)}。"
                    ),
                    why_it_matters="營收增加但營業利益率下降時，值得檢查收入成長與本業獲利轉化是否同步。",
                    what_to_check=[
                        "產品組合",
                        "成本結構",
                        "營業費用",
                    ],
                )
            )

    if net_income_change is not None and fcf_change is not None:
        if net_income_change > 0 and fcf_change < 0:
            observations.append(
                ResearchObservation(
                    category="Cross Metric（跨指標）",
                    title="Net Income 增加但 Free Cash Flow 下降",
                    metric="earnings_cash_flow",
                    what_happened=(
                        f"{period_label(latest)} Net Income 較 {period_label(previous)} 增加，"
                        "但 Free Cash Flow 同期下降。"
                    ),
                    why_it_matters="盈餘與自由現金流方向不同時，值得檢查營運資金、資本支出與非現金項目。",
                    what_to_check=[
                        "Operating Cash Flow",
                        "Capital Expenditure",
                        "working capital",
                        "non-cash items",
                    ],
                )
            )

    if latest.cash_and_cash_equivalents is not None and latest.total_debt is not None:
        if latest.cash_and_cash_equivalents > latest.total_debt:
            observations.append(
                ResearchObservation(
                    category="Cross Metric（跨指標）",
                    title="Cash 高於 Total Debt",
                    metric="cash_debt",
                    what_happened=(
                        f"{period_label(latest)} Cash 為 "
                        f"{format_currency_amount(latest.cash_and_cash_equivalents, series_currency(series, latest))}，"
                        f"Total Debt 為 {format_currency_amount(latest.total_debt, series_currency(series, latest))}。"
                    ),
                    why_it_matters="Cash 與 Debt 的相對大小提供資本結構研究脈絡，但不是整體財務結論。",
                    what_to_check=[
                        "debt maturity",
                        "interest expense",
                        "liquidity needs",
                        "capital expenditure",
                    ],
                    observation_type="info",
                )
            )
        elif latest.total_debt > latest.cash_and_cash_equivalents:
            observations.append(
                ResearchObservation(
                    category="Cross Metric（跨指標）",
                    title="Total Debt 高於 Cash",
                    metric="cash_debt",
                    what_happened=(
                        f"{period_label(latest)} Total Debt 為 "
                        f"{format_currency_amount(latest.total_debt, series_currency(series, latest))}，"
                        f"Cash 為 {format_currency_amount(latest.cash_and_cash_equivalents, series_currency(series, latest))}。"
                    ),
                    why_it_matters="Debt 高於 Cash 時，值得放在債務到期、利息費用與現金流能力下研究。",
                    what_to_check=[
                        "debt maturity",
                        "interest expense",
                        "free cash flow",
                        "liquidity needs",
                    ],
                )
            )

    return observations


def build_missing_data_observations(
    series: HistoricalFinancialSeries,
) -> list[ResearchObservation]:
    observations = []
    periods = list(series.periods or [])
    if not periods:
        return [
            ResearchObservation(
                category="Data Quality（資料完整性）",
                title="缺少 historical periods",
                metric="historical_periods",
                what_happened="目前沒有可用的 historical financial periods。",
                why_it_matters="沒有年度資料時，系統不能建立歷史趨勢解讀。",
                what_to_check=[
                    "Yahoo Finance annual statements",
                    "SQLite historical cache",
                    "資料來源更新時間",
                ],
                observation_type="info",
            )
        ]

    missing_metrics = []
    for field, label in [
        ("gross_margin", "Gross Margin"),
        ("operating_margin", "Operating Margin"),
        ("net_margin", "Net Margin"),
        ("free_cash_flow", "Free Cash Flow"),
        ("total_assets", "Total Assets"),
        ("total_debt", "Total Debt"),
        ("total_equity", "Total Equity"),
        ("cash_and_cash_equivalents", "Cash"),
    ]:
        if count_valid_periods(series, field) == 0:
            missing_metrics.append(label)

    if missing_metrics:
        observations.append(
            ResearchObservation(
                category="Data Quality（資料完整性）",
                title="部分歷史指標缺漏",
                metric="missing_historical_metrics",
                what_happened="目前缺少可用的歷史指標：" + "、".join(missing_metrics) + "。",
                why_it_matters="缺漏指標會限制跨年度與跨指標研究判讀；缺漏值不應被視為 0。",
                what_to_check=[
                    "公司年度財報",
                    "Yahoo Finance 後續更新",
                    "保留 N/A 欄位的研究限制",
                ],
                observation_type="info",
            )
        )

    return observations


def build_historical_next_steps(
    observations: list[ResearchObservation],
) -> list[ResearchNextStep]:
    groups = []
    seen_categories = []
    for observation in observations:
        if observation.category not in seen_categories:
            seen_categories.append(observation.category)

    checklist_by_category = {
        "Revenue（營收）": [
            "查閱各年度主要產品 / 地區營收變化",
            "確認產業需求是否同步變化",
            "比較同業同期 Revenue 趨勢",
        ],
        "Earnings（獲利）": [
            "比較 Revenue / Net Income / EPS 的同期方向",
            "檢查 Gross Margin、Operating Margin 與費用結構",
            "確認是否存在 one-time / non-recurring items",
        ],
        "Margins（利潤率）": [
            "比較產品組合",
            "檢查成本結構",
            "檢查營業費用變化",
        ],
        "Cash Flow（現金流）": [
            "確認資本支出用途",
            "查看管理層擴產計畫",
            "比較後續 Operating Cash Flow 是否支持投資",
        ],
        "Financial Position（財務結構）": [
            "檢查 debt maturity",
            "比較 interest expense 與 Free Cash Flow",
            "確認 liquidity needs 與 capital expenditure",
        ],
        "Cross Metric（跨指標）": [
            "確認同期間 Revenue、Net Income、Margins 與 Free Cash Flow 的方向差異",
            "回到財報附註檢查費用、稅與非現金項目",
            "比較同業同期是否出現相似變化",
        ],
        "Data Quality（資料完整性）": [
            "補查缺漏年度與缺漏指標",
            "交叉確認公司財報與 Yahoo Finance 資料",
            "標記仍為 N/A 的研究限制",
        ],
    }

    for category in seen_categories:
        items = checklist_by_category.get(category)
        if not items:
            continue
        groups.append(
            ResearchNextStep(
                category=category,
                title="整理 historical research checklist",
                metric="historical_research",
                items=items,
            )
        )

    if not groups:
        groups.append(
            ResearchNextStep(
                category="Historical Research（歷史研究）",
                title="建立基礎 historical research checklist",
                metric="baseline_historical_research",
                items=[
                    "比較 Revenue、Net Income、Margins 與 Cash Flow",
                    "確認各年度 Period End 與資料缺漏",
                    "閱讀公司年度財報與管理層說明",
                ],
            )
        )

    return groups


def build_gap_observations(
    series: HistoricalFinancialSeries,
    field: str,
    label: str,
) -> list[ResearchObservation]:
    valid = valid_periods(series, field)
    if len(valid) < 2:
        return []

    observations = []
    for previous, current in zip(valid, valid[1:]):
        if not are_consecutive_years(current.period_year, previous.period_year):
            observations.append(
                ResearchObservation(
                    category="Data Quality（資料完整性）",
                    title=f"{label} 年度資料不連續",
                    metric=field,
                    what_happened=(
                        f"{label} 有效資料從 {period_label(previous)} 到 "
                        f"{period_label(current)} 中間不連續，因此不建立這段 YoY 或連續趨勢。"
                    ),
                    why_it_matters="年度 gap 會限制 consecutive trend 判讀；系統只比較相鄰 period_year 連續的年度。",
                    what_to_check=[
                        "補查缺漏年度資料",
                        "確認 Yahoo Finance annual statement coverage",
                        "保留 gap 對趨勢判讀的限制",
                    ],
                    observation_type="info",
                )
            )
    return observations


def count_valid_periods(series: HistoricalFinancialSeries, field: str) -> int:
    return len(valid_periods(series, field))


def valid_periods(
    series: HistoricalFinancialSeries,
    field: str,
) -> list[HistoricalFinancialPeriod]:
    return [
        period
        for period in series.periods or []
        if getattr(period, field) is not None
    ]


def consecutive_period_changes(
    series: HistoricalFinancialSeries,
    field: str,
    use_eps_growth: bool = False,
) -> list[PeriodChange]:
    changes = []
    periods = valid_periods(series, field)

    for previous, current in zip(periods, periods[1:]):
        if not are_consecutive_years(current.period_year, previous.period_year):
            continue
        previous_value = getattr(previous, field)
        current_value = getattr(current, field)
        if previous_value is None or current_value is None:
            continue

        if use_eps_growth:
            relative_change = calculate_eps_yoy_growth(
                current_value,
                previous_value,
                current.period_year,
                previous.period_year,
            )
        else:
            relative_change = calculate_yoy_growth(
                current_value,
                previous_value,
                current.period_year,
                previous.period_year,
            )
        changes.append(
            PeriodChange(
                previous_period=previous,
                current_period=current,
                previous_value=previous_value,
                current_value=current_value,
                absolute_change=current_value - previous_value,
                relative_change=relative_change,
            )
        )

    return changes


def is_connected_change_chain(changes: list[PeriodChange]) -> bool:
    if len(changes) < 2:
        return True

    for previous_change, current_change in zip(changes, changes[1:]):
        if previous_change.current_period.period_end != current_change.previous_period.period_end:
            return False
        if previous_change.current_period.period_year != current_change.previous_period.period_year:
            return False

    return True


def all_relative_changes_available(changes: list[PeriodChange]) -> bool:
    return all(change.relative_change is not None for change in changes)


def same_period_change(
    previous: HistoricalFinancialPeriod,
    current: HistoricalFinancialPeriod,
    field: str,
) -> float | None:
    previous_value = getattr(previous, field)
    current_value = getattr(current, field)
    if previous_value is None or current_value is None:
        return None
    return current_value - previous_value


def previous_consecutive_period(
    series: HistoricalFinancialSeries,
    current: HistoricalFinancialPeriod | None,
) -> HistoricalFinancialPeriod | None:
    if current is None:
        return None
    periods = list(series.periods or [])
    try:
        current_index = periods.index(current)
    except ValueError:
        return None
    if current_index == 0:
        return None
    previous = periods[current_index - 1]
    if not are_consecutive_years(current.period_year, previous.period_year):
        return None
    return previous


def latest_period_with_any_value(
    series: HistoricalFinancialSeries,
) -> HistoricalFinancialPeriod | None:
    periods = list(series.periods or [])
    return periods[-1] if periods else None


def change_direction(change: float) -> str:
    if change > 0:
        return "up"
    if change < 0:
        return "down"
    return "flat"


def direction_text(direction: str) -> str:
    if direction == "up":
        return "增加"
    if direction == "down":
        return "下降"
    return "持平"


def cash_flow_state_text(value: float) -> str:
    if value > 0:
        return "維持正值"
    if value < 0:
        return "為負值"
    return "為 0"


def format_currency_amount(value: float | None, currency: str | None = None) -> str:
    if value is None:
        return "N/A"

    absolute_value = abs(value)
    units = [
        (1_000_000_000_000, "T"),
        (1_000_000_000, "B"),
        (1_000_000, "M"),
    ]
    for factor, suffix in units:
        if absolute_value >= factor:
            amount = f"{value / factor:.2f}{suffix}"
            return f"{currency} {amount}" if currency else amount

    amount = f"{value:,.0f}"
    return f"{currency} {amount}" if currency else amount


def format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def format_signed_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.2%}"


def format_abs_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{abs(value) * 100:.2f}%"


def format_percentage_points(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{abs(value) * 100:.2f} percentage points"


def period_label(period: HistoricalFinancialPeriod | date | None) -> str:
    if period is None:
        return "N/A"
    if isinstance(period, date):
        return f"FY{period.year}"
    if period.period_year is not None:
        return f"FY{period.period_year}"
    return f"FY ending {period.period_end.isoformat()}"


def series_currency(
    series: HistoricalFinancialSeries,
    period: HistoricalFinancialPeriod | None = None,
) -> str | None:
    if period is not None and period.currency:
        return period.currency
    return series.currency
