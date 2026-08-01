# Research Framework

## Scope

This framework supports the Streamlit Research Dashboard.

The system is not investment advice. Research observations are deterministic research prompts based on currently available data. The system does not generate buy / sell / hold recommendations, target prices, overall stock scores, or deterministic buy / sell scores.

The current data source is Yahoo Finance through the existing `Stock` model and SQLite cache. This page does not use OpenAI API, ChatGPT API, or any LLM.

## Eight Research Questions

1. Company Overview（公司概況）：這家公司是誰？它屬於哪個產業？主要業務摘要是什麼？
2. Profitability（獲利能力）：公司目前的獲利品質與效率有哪些 snapshot 指標？
3. Growth（成長性）：近期營收與盈餘成長是否出現需要追蹤的方向？
4. Financial Health（財務健康）：現金、負債與現金流是否提供足夠財務脈絡？
5. Valuation（估值）：目前估值倍數與 forward estimate 之間是否有值得追問的差異？
6. Market Position（市場位置）：目前價格在 52 週區間與均價附近的位置如何？
7. Risk Signals（風險提示）：有哪些可解釋、可追查的 observations 值得注意？
8. Research Next Steps（下一步研究）：接下來應該補查哪些資料或研究問題？

## Metrics by Category

Company Overview（公司概況）：

- Symbol（股票代號）
- Localized Company Name（在台股可用時使用官方繁體中文名稱）
- Sector（產業類別）
- Industry（細分產業）
- Market Cap（市值）
- Company Summary（公司業務摘要）

Profitability（獲利能力）：

- ROE（股東權益報酬率）
- Gross Margin（毛利率）
- Operating Margin（營業利益率）
- Net Margin（淨利率）
- EPS（每股盈餘）

Growth（成長性）：

- Revenue Growth（營收成長率）
- Earnings Growth（盈餘成長率）

Growth metrics currently come from Yahoo Finance snapshot fields. They are not system-calculated 3-year or 5-year CAGR.

Financial Health（財務健康）：

- Total Cash（現金）
- Total Debt（總負債）
- Debt to Equity（負債權益比）
- Operating Cash Flow（營業現金流）
- Free Cash Flow（自由現金流）

Valuation（估值）：

- Trailing P/E（歷史本益比）
- Forward P/E（預估本益比）
- Price to Book（股價淨值比）

Market Position（市場位置）：

- Current Price（目前股價）
- 52-week High（52 週高點）
- 52-week Low（52 週低點）
- 52-week Position（52 週區間位置）
- 50-day Average（50 日均價）
- 200-day Average（200 日均價）

## Metric Interpretation Principles

- Percent fields such as margin, ROE, and growth are displayed as percentages.
- Cash, debt, market cap, and cash flow keep currency context, for example `TWD 1.25T` or `USD 85.40B`.
- Cross-market cash, debt, and cash flow values should not be directly ranked without currency conversion and accounting context.
- Yahoo `debtToEquity` raw numeric value is already provided on a percent scale for user-facing interpretation. The Research Dashboard displays the same numeric value with a `%` suffix and does not multiply by `100`. For example, `15.174` is shown as `15.17%`.
- 52-week Position is calculated as `(current_price - fifty_two_week_low) / (fifty_two_week_high - fifty_two_week_low)`.
- 52-week Position is not clamped in research logic. Values below `0` or above `1` are shown as data observations because the current price may sit outside the available 52-week range.

## Risk Signal Philosophy

Risk Signals are not a score, rating, or recommendation. They are deterministic observations that must:

- State what happened using only facts supported by the current snapshot.
- Explain why the fact is worth researching.
- Suggest what to check next as a checklist.
- Avoid directly judging whether the stock is good or bad.

Current MVP signals include:

- `revenue_growth < 0`
- `earnings_growth < 0`
- `free_cash_flow < 0`
- `operating_cash_flow < 0`
- `total_debt > total_cash`
- `current_price < two_hundred_day_average`
- `fifty_two_week_position > 1.05`
- Missing critical research fields

Each `ResearchObservation` uses one structure:

- `category`
- `title`
- `metric`
- `what_happened`
- `why_it_matters`
- `what_to_check`
- `observation_type`

`what_happened` is for facts. `why_it_matters` is for research relevance. `what_to_check` is a list of follow-up research areas. The same content is not stored again as a separate message string.

## Research Next Steps Philosophy

Research Next Steps are questions for follow-up research, not actions to take in the market.

Research Next Steps do not repeat Risk Signal explanations. Their responsibility is to consolidate triggered observations into a research checklist, for example:

- Growth（成長性）：compare Revenue / EPS changes, margins, expense structure, and non-recurring items.
- Valuation（估值）：confirm EPS estimates, compare peer P/E, and compare company historical valuation range.
- Financial Health（財務健康）：compare Operating Cash Flow, Free Cash Flow, capital expenditure, and net income.
- Data Quality（資料完整性）：complete missing fields and record remaining N/A limits.

The current app does not have a historical fundamental database. Checklist items describe what the user should check; they do not imply the system has already answered those questions.

## Explainability Language Contract

Deterministic research wording must separate:

- Facts: values and conditions directly supported by the current snapshot.
- Research hypotheses: possible explanations that require further evidence.

Facts can say, for example, `Earnings Growth = -12.50%`. If `Revenue Growth` is available, the same observation can include it as current snapshot context.

Research hypotheses must be framed as topics to verify. Deterministic rules must not present possible explanations as facts about the company.

The following causal conclusion wording is not allowed in deterministic company observations or next steps:

- 造成
- 導致
- 證明
- 顯示公司變差
- 顯示公司變好
- 一定
- 必然

These terms are only acceptable when explaining a data definition, not when making a company conclusion.

The following recommendation or rating language is not allowed in observations or next steps:

- Buy
- Sell
- Hold
- 買
- 賣
- 持有
- score
- rating
- target price

## Beginner Glossary

The Research page includes a compact `st.expander()` glossary backed by `src/research_glossary.py`.

Current glossary topics:

- `one_time_items`
- `margin`
- `cash_flow`
- `debt`
- `valuation`

Glossary content uses Traditional Chinese and keeps important English finance terms, such as Gross Margin, Operating Margin, Net Margin, Operating Cash Flow, Free Cash Flow, Total Debt, Debt to Equity, P/E, Forward P/E, and P/B.

## Missing Data Behavior

The Research Dashboard accepts partial `Stock` data.

- Missing metrics display as `N/A`.
- Missing Company Summary shows a friendly message.
- A missing category does not crash the page.
- Missing critical fields trigger a neutral data completeness observation.
- Existing Dashboard, Watchlist, and Comparison features continue to use the same service layer and remain separate from Research observations.

## Explicit Non-Goals

This framework does not include:

- AI / LLM analysis
- News or sentiment analysis
- Buy / sell / hold recommendation
- Overall stock score
- Target price
- Technical indicator suite
- RSI, MACD, candlestick analysis
- Backtesting
- Portfolio management
- Cloud deployment
