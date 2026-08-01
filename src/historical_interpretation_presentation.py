from dataclasses import dataclass

from research_service import ResearchNextStep
from research_service import ResearchObservation


@dataclass(frozen=True)
class HistoricalHighlight:

    category: str

    title: str

    summary: str


@dataclass(frozen=True)
class HistoricalObservationGroup:

    category: str

    observations: list[ResearchObservation]


@dataclass(frozen=True)
class HistoricalNextStepGroup:

    category: str

    visible_items: list[str]

    overflow_items: list[str]


DETAILED_INTERPRETATION_CATEGORY_ORDER = [
    "Revenue（營收）",
    "Earnings（獲利）",
    "Margins（利潤率）",
    "Cash Flow（現金流）",
    "Financial Position（財務結構）",
    "Cross Metric（跨指標）",
    "Data Quality（資料完整性）",
]


HIGHLIGHT_CATEGORY_ORDER = [
    "Revenue（營收）",
    "Earnings（獲利）",
    "Margins（利潤率）",
    "Cash Flow（現金流）",
    "Financial Position（財務結構）",
    "Data Quality（資料完整性）",
]


HIGHLIGHT_TITLE_PRIORITY = [
    "Revenue 前期下降後連續回升",
    "Revenue 前期下降後回升",
    "Revenue 前期增加後下降",
    "Revenue 連續兩期增加",
    "Revenue 連續兩期下降",
    "最新年度 Revenue 增加",
    "最新年度 Revenue 下降",
    "Revenue 與 Net Income 最新年度方向不同",
    "最新年度 EPS unavailable",
    "EPS 前期下降後回升",
    "EPS 連續兩期下降",
    "Revenue 與 Net Income 最新年度同方向",
    "Gross Margin 最新年度下降",
    "Operating Margin 最新年度下降",
    "Net Margin 最新年度下降",
    "Gross Margin 最新年度增加",
    "Operating Margin 最新年度增加",
    "Net Margin 最新年度增加",
    "Free Cash Flow 連續年度為正",
    "Free Cash Flow 轉為負值",
    "Free Cash Flow 回到正值",
    "Capital Expenditure 現金支出規模增加",
    "Capital Expenditure 現金支出規模下降",
    "最新年度 Free Cash Flow 狀態",
    "Cash 最新年度增加",
    "Total Debt 最新年度下降",
    "Total Debt 最新年度增加",
    "Cash 高於 Total Debt",
    "Total Debt 高於 Cash",
    "部分歷史指標缺漏",
]


NEXT_STEP_CATEGORY_ORDER = [
    "Revenue（營收）",
    "Earnings（獲利）",
    "Margins（利潤率）",
    "Cash Flow（現金流）",
    "Financial Position（財務結構）",
    "Cross Metric（跨指標）",
    "Data Quality（資料完整性）",
    "Historical Research（歷史研究）",
]


ATTENTION_COLOR_EXPLANATION = (
    "顏色說明：藍色代表一般歷史資料觀察；黃色代表值得進一步確認的研究項目，"
    "不代表負面訊號或投資建議。"
)


FY_PERIOD_CAPTION = "FY 代表財務期間，詳細結束日期可於 Historical Table 查看。"


def build_historical_highlights(
    observations: list[ResearchObservation],
    max_count: int = 6,
) -> list[HistoricalHighlight]:
    highlights = []
    used_summaries = set()

    for category in HIGHLIGHT_CATEGORY_ORDER:
        selected = select_highlight_observations(observations, category)
        if not selected:
            continue
        summary = " ".join(observation.what_happened for observation in selected)
        normalized_summary = normalize_text(summary)
        if normalized_summary in used_summaries:
            continue
        used_summaries.add(normalized_summary)
        highlights.append(
            HistoricalHighlight(
                category=category,
                title=selected[0].title,
                summary=summary,
            )
        )
        if len(highlights) >= max_count:
            break

    return highlights


def select_highlight_observations(
    observations: list[ResearchObservation],
    category: str,
) -> list[ResearchObservation]:
    primary = select_highlight_observation(observations, category)
    if primary is None:
        return []

    selected = [primary]

    if category == "Cash Flow（現金流）":
        complementary = find_first_title_containing(
            observations,
            category,
            "Capital Expenditure 現金支出規模",
            excluded_titles={primary.title},
        )
        if complementary is not None:
            selected.append(complementary)

    if category == "Financial Position（財務結構）":
        complementary = find_first_title_containing(
            observations,
            category,
            "Total Debt 最新年度",
            excluded_titles={primary.title},
        )
        if complementary is not None:
            selected.append(complementary)

    return selected


def select_highlight_observation(
    observations: list[ResearchObservation],
    category: str,
) -> ResearchObservation | None:
    category_observations = [
        observation
        for observation in observations
        if observation.category == category
    ]
    if not category_observations:
        return None

    priority_lookup = {
        title: index
        for index, title in enumerate(HIGHLIGHT_TITLE_PRIORITY)
    }
    return min(
        category_observations,
        key=lambda observation: priority_lookup.get(
            observation.title,
            len(HIGHLIGHT_TITLE_PRIORITY),
        ),
    )


def find_first_title_containing(
    observations: list[ResearchObservation],
    category: str,
    title_fragment: str,
    excluded_titles: set[str] | None = None,
) -> ResearchObservation | None:
    excluded = excluded_titles or set()
    for observation in observations:
        if observation.category != category:
            continue
        if observation.title in excluded:
            continue
        if title_fragment in observation.title:
            return observation
    return None


def group_detailed_interpretation(
    observations: list[ResearchObservation],
) -> list[HistoricalObservationGroup]:
    groups = []
    for category in DETAILED_INTERPRETATION_CATEGORY_ORDER:
        category_observations = [
            observation
            for observation in observations
            if observation.category == category
        ]
        if category_observations:
            groups.append(
                HistoricalObservationGroup(
                    category=category,
                    observations=category_observations,
                )
            )
    return groups


def build_next_step_display_groups(
    next_steps: list[ResearchNextStep],
    per_category_limit: int = 3,
    max_visible_total: int = 10,
) -> list[HistoricalNextStepGroup]:
    grouped_items: dict[str, list[str]] = {}
    seen_by_category: dict[str, set[str]] = {}

    for step in next_steps:
        grouped_items.setdefault(step.category, [])
        seen_by_category.setdefault(step.category, set())
        for item in step.items:
            normalized = normalize_text(item)
            if normalized in seen_by_category[step.category]:
                continue
            seen_by_category[step.category].add(normalized)
            grouped_items[step.category].append(item.strip())

    groups = []
    visible_total = 0
    for category in NEXT_STEP_CATEGORY_ORDER:
        items = grouped_items.get(category, [])
        if not items:
            continue
        remaining_total_slots = max(0, max_visible_total - visible_total)
        visible_count = min(per_category_limit, remaining_total_slots)
        visible_items = items[:visible_count]
        overflow_items = items[visible_count:]
        visible_total += len(visible_items)
        groups.append(
            HistoricalNextStepGroup(
                category=category,
                visible_items=visible_items,
                overflow_items=overflow_items,
            )
        )
    return groups


def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())
