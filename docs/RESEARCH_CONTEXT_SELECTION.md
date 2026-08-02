# Research Context Selection

## Purpose

Research Context Selection is the deterministic AI-ready context selection layer.

It prevents future AI workflows from receiving the entire `ResearchContext` for every question. Instead, callers provide an explicit `ResearchQuestionType`, and the selector returns only the relevant evidence, observations, missing data, limitations, and selection metadata.

This layer does not classify natural language. Natural language routing belongs to a future routing or AI layer.

## Architecture Boundary

`src/research_context_selector.py` consumes an already-built `ResearchContext`.

It does not:

- fetch Yahoo Finance data
- read or write SQLite
- build `ResearchContext`
- build `ResearchReport`
- build `HistoricalResearchReport`
- render Streamlit UI
- call OpenAI, ChatGPT, or any LLM
- generate prompts
- create embeddings or vector search
- produce recommendation, rating, score, target price, or Buy / Sell / Hold output

The selector only chooses a deterministic subset from the source context.

## ResearchQuestionType

MVP question types:

- `company_overview`
- `profitability`
- `growth`
- `financial_health`
- `valuation`
- `market_position`
- `historical_revenue`
- `historical_earnings`
- `historical_margins`
- `historical_cash_flow`
- `historical_financial_position`
- `risks_and_attention`
- `research_next_steps`
- `general_research`

The API accepts only `ResearchQuestionType` enum values. It does not accept arbitrary natural-language questions.

## Selection Request

`ResearchSelectionRequest` contains:

- `question_type`
- `max_evidence`
- `include_observations`
- `include_missing_data`
- `include_limitations`

It intentionally does not include model name, temperature, prompt text, token count, API key, or LLM settings.

## SelectedResearchContext

`SelectedResearchContext` contains:

- `symbol`
- `display_name`
- `question_type`
- `selected_evidence`
- `selected_observation_links`
- `selected_observations`
- `selected_missing_data`
- `selected_limitations`
- `selection_notes`
- `generated_at`
- `source_context_generated_at`
- `source_evidence_count`

It does not copy the full `ResearchContext`.

## Metric Groups

Metric groups are centralized in `research_context_selector.py`.

Current groups include:

- Company overview: sector, industry, market cap
- Profitability: ROE, margins, trailing EPS, historical margin support
- Growth: revenue growth, earnings growth, revenue, Revenue YoY, net income, EPS, EPS YoY
- Financial health: cash, debt, debt to equity, operating cash flow, free cash flow, historical cash-flow and balance-sheet support
- Valuation: trailing P/E, forward P/E, P/B, trailing EPS, earnings growth, limited revenue / earnings history
- Market position: current price, 52-week high / low, 52-week position, 50-day average, 200-day average
- Historical-specific groups for revenue, earnings, margins, cash flow, and financial position

Metric names follow actual `EvidenceItem.metric` values from `ResearchContext`.

## Question-Type Policy

Each question type maps to a deterministic metric scope.

Examples:

- `growth` selects current revenue / earnings growth and relevant annual revenue, Revenue YoY, net income, EPS, EPS YoY.
- `valuation` selects P/E, P/B, trailing EPS, earnings growth, and limited historical EPS / net income / revenue support.
- `market_position` selects price-position evidence and does not select historical fundamentals.
- `risks_and_attention` starts from current and historical attention observations, then pulls only evidence needed to support them.
- `research_next_steps` starts from deterministic next-step metrics, then pulls supporting evidence where available.
- `general_research` is the broadest policy, but still metric-scoped and not a full context dump.

## Historical Window Policy

Historical-specific questions keep all available annual periods for their metric scope.

Current-focused questions keep the latest 3 relevant historical periods.

`general_research` keeps all available annual periods within its metric scope.

`market_position` does not include historical fundamentals.

## Evidence Lineage Closure

Derived evidence is never selected alone.

When the selector includes derived evidence such as:

```text
derived:revenue_yoy:2025-12-31
```

it recursively includes its `derived_from` evidence:

```text
historical:revenue:2024-12-31
historical:revenue:2025-12-31
```

Circular derived lineage raises `SelectionError`.

## Observation Selection

Observations are selected by question type, linked evidence, and metric relevance.

The selector does not include every observation by default. If an observation link would reference evidence or missing-data records that are not selected, the selector either pulls the evidence lineage or drops the broken observation link.

## Observation Identity Stability

`ObservationEvidenceLink.id` no longer depends on list index.

The context linking layer now builds stable IDs from:

- scope
- category slug
- metric slug
- title slug
- deterministic semantic digest

`observation_index` remains available only as a lookup pointer back to the original observation list.

## Missing-Data Denoising

Missing data is selected by metric relevance, period relevance, and linked observation references.

The selector deduplicates derived missing records when a primary source missing record explains the same period. For example, if FY2025 EPS is missing, the selected context can keep `missing:historical:eps:2025-12-31` and omit the lower-level `missing:historical:eps_yoy:2025-12-31`.

The original `ResearchContext.missing_data` is not modified.

## Limitation Selection

Limitations are selected by question relevance.

Historical-specific questions include annual-only and no-quarterly / TTM limitations.

Market-position questions omit annual-history limitations because historical fundamentals are not part of that selection.

Currency and stock-specific context limitations are retained when relevant.

## Evidence Budget

`max_evidence` is an evidence-count budget, not a token budget.

When a budget is supplied, selector priority is deterministic:

1. derived evidence
2. current evidence
3. latest historical evidence
4. older historical evidence

The budget is applied after lineage closure.

## Atomic Evidence Groups

Evidence budget selection operates on atomic lineage groups.

If a selected derived evidence item requires two source evidence items, the selector keeps the full group or omits the group. It does not split derived evidence from its lineage.

If a single lineage group is larger than the requested budget, the selector may exceed the budget for that group because lineage integrity has priority.

## Serialization

`SelectedResearchContext.to_dict()` is JSON-safe:

- enum values serialize to stable strings
- dates and datetimes serialize to ISO strings through existing context serialization helpers
- tuples serialize to lists
- Evidence IDs remain unchanged

## Validation

Validation confirms:

- valid question type
- `max_evidence >= 1` when provided
- unique selected evidence IDs
- complete derived evidence lineage
- observation links reference selected evidence and selected missing data
- unique selected missing-data IDs
- no NaN or infinity values
- JSON-safe serialization

## No AI / No Recommendation

This layer does not add AI analysis, recommendation language, scores, ratings, target prices, or Buy / Sell / Hold output.

It only prepares deterministic, traceable context for future AI or export layers.

## Future Routing / Prompt Boundary

Future work may add a natural-language router:

```text
"近年的營收表現如何？" -> ResearchQuestionType.HISTORICAL_REVENUE
```

That router must remain outside this selector. Prompt generation and LLM calls must also remain outside this selector.
