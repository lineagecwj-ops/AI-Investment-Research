# Historical Interpretation Framework

## Scope

Historical Interpretation turns annual `HistoricalFinancialSeries` data into deterministic research observations.

The goal is to help answer:

- What happened
- Why it matters
- What to check next

This layer does not use OpenAI API, ChatGPT API, LLMs, sentiment, Buy / Sell / Hold recommendations, target price, overall score, historical score, growth score, quality score, or company ratings.

## Architecture

`src/historical_research_service.py` owns historical interpretation rules.

It consumes `HistoricalFinancialSeries` and returns a `HistoricalResearchReport` containing:

- `ResearchObservation`
- `ResearchNextStep`

`src/historical_interpretation_presentation.py` owns the UX presentation refinement:

- Historical Highlights
- Detailed Interpretation category grouping
- Research Next Steps deterministic deduplication and display limits

`historical_financial_service.py` remains responsible for Yahoo annual statement normalization and cache behavior.

`database.py` remains responsible for SQLite persistence.

`app.py` only renders the report in the Historical Trends page.

## Facts vs Interpretation

Allowed facts:

- FY2025 Revenue increased compared with FY2024.
- FY2025 Gross Margin decreased by 2.14 percentage points.
- FY2025 Free Cash Flow turned negative.
- Yahoo Finance currently does not provide FY2025 EPS.

Allowed research interpretation:

- This is worth checking against product mix, demand, expenses, non-operating items, tax, capital expenditure, or liquidity needs.

Forbidden deterministic company conclusions:

- The company is strong or weak.
- The financial position is healthy or unhealthy.
- The company is improving or deteriorating.
- The stock is undervalued or overvalued.
- Buy, Sell, Hold, target price, or any score.

## Trend Language

Allowed trend language:

- increased
- decreased
- recovered
- declined
- remained positive
- remained negative
- consecutive increases
- consecutive declines
- moved in different directions

Forbidden judgment language:

- strong
- weak
- healthy
- unhealthy
- excellent
- poor
- improving company
- deteriorating company
- undervalued
- overvalued
- 強勁
- 疲弱
- 健康
- 惡化
- 優秀
- 差
- 低估
- 高估

## Data Sufficiency

Every metric is checked before interpretation.

- Fewer than 2 valid periods: no trend conclusion.
- 2 valid periods: only one period-to-period change can be described.
- 3 or more valid periods: consecutive increases, repeated declines, recovery, or direction change can be described only if the valid period years are consecutive.

Missing values are never treated as `0`.

The service reuses `research_metrics.are_consecutive_years()` and the existing YoY helper semantics, so a gap such as FY2022, FY2024, FY2025 does not become a FY2022 to FY2025 consecutive trend.

## Revenue Rules

Revenue observations describe only historical annual values and YoY changes.

Supported MVP patterns:

- Latest YoY greater than `0`
- Latest YoY less than `0`
- Recent two consecutive YoY values greater than `0`
- Recent two consecutive YoY values less than `0`
- Prior decline followed by latest recovery
- Prior decline followed by two consecutive recovery years
- Prior growth followed by latest decline
- Non-consecutive year gap
- Insufficient valid periods

Revenue recovery can be described as a historical fact when the annual data directly supports it. Possible reasons such as product demand, price, industry cycle, or company-specific factors are only listed as research checklist items.

## Earnings Rules

Earnings observations cover:

- Revenue and Net Income moving in the same direction
- Revenue increasing while Net Income decreases
- Revenue decreasing while Net Income increases
- EPS and Net Income moving in the same direction
- EPS decline followed by recovery
- EPS repeated decline
- Missing or latest unavailable EPS

Relationships are only created when both metrics have values in the same consecutive periods.

## Margin Rules

Margin observations cover:

- Gross Margin
- Operating Margin
- Net Margin

Margin change is calculated as:

```text
latest margin - previous margin
```

The user-facing text uses percentage-point change, for example:

```text
49.64% to 47.50% = decreased 2.14 percentage points
```

The MVP does not define a stable-margin threshold. It describes positive or negative percentage-point changes without claiming stability or significance as a financial standard.

## Cash Flow Rules

Cash Flow observations cover:

- Operating Cash Flow positive or negative
- Free Cash Flow positive or negative
- Consecutive positive Free Cash Flow
- Free Cash Flow turning negative
- Free Cash Flow recovering positive
- Capital Expenditure spending scale increasing or decreasing
- Missing Free Cash Flow

Yahoo Finance commonly reports `Capital Expenditure` as a negative cash outflow. When comparing spending scale, the service compares absolute values:

```text
abs(capital_expenditure)
```

For example, `-18.91B` to `-25.42B` is described as cash spending scale increasing from `18.91B` to `25.42B`.

## Financial Position Rules

Financial Position observations cover:

- Total Assets
- Total Debt
- Total Equity
- Cash

The service describes historical changes only. It can say Cash increased or Total Debt decreased in a period. It cannot say financial quality improved or worsened.

## Cross Metric Rules

MVP cross-metric observations are intentionally limited:

- Revenue increased while Net Income decreased
- Revenue increased while Operating Margin decreased
- Net Income increased while Free Cash Flow decreased
- Cash compared with Total Debt

Every cross-metric observation requires both metrics to have values in the same period pair. Missing data prevents the observation.

## Period Semantics

Historical interpretation uses `FY{period_year}` labels.

For a period ending `2026-01-31`, the observation says `FY2026`. It does not call the period calendar year 2026.

Detailed tables still use `FY ending YYYY-MM-DD`.

## Research Next Steps

Historical Research Next Steps are deterministic checklists grouped by triggered observation category.

They are research tasks, not conclusions. They should not repeat full observation sentences.

## Progressive Disclosure UX

The Historical Trends page presents Historical Interpretation in three layers.

### Historical Highlights

Historical Highlights are short factual summaries selected from existing deterministic observations.

Highlights answer only what happened. They do not include Why it matters, What to check, recommendation wording, score, rating, or ranking.

The MVP selection strategy is deterministic:

- Use a fixed category order.
- Select at most one highlight per category.
- Prefer multi-period Revenue patterns before latest single-period changes.
- Prefer important EPS availability, margin change, FCF / CapEx facts, Cash / Debt facts, and data-quality limitations.
- Limit default highlights to 6.

Some category highlights may concatenate two existing factual observations from the same category, such as Free Cash Flow status plus Capital Expenditure spending-scale change. The presentation helper does not recalculate financial metrics.

### Detailed Interpretation

Detailed Interpretation groups full observations by category:

1. Revenue
2. Earnings
3. Margins
4. Cash Flow
5. Financial Position
6. Cross Metric
7. Data Quality

Each category is rendered in a collapsed expander by default. Opening the expander shows the full Observation, Why it matters, and What to check fields.

Color semantics:

- Blue means general historical data observation.
- Yellow means worth checking further.
- Yellow does not mean a negative signal or investment recommendation.

### Next Steps UX

Research Next Steps reuse `HistoricalResearchReport.next_steps`.

The presentation helper applies deterministic cleanup only:

- Trim whitespace.
- Lowercase English for comparison.
- Remove exact normalized duplicates within a category.
- Keep category order deterministic.
- Display up to 3 items per category.
- Display up to 10 visible items across the page by default.
- Preserve overflow items inside a collapsed `查看更多研究項目` expander.

No semantic AI deduplication is used.
