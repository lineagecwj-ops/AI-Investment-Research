# AI Research Dashboard

## Purpose

AI Research Dashboard connects the existing Grounded AI Research service to Streamlit.

It lets the user submit one explicit stock research question, builds a deterministic selected research context, generates one structured grounded answer, and renders the answer with visible evidence.

## User Flow

```text
Stock
→ Research Question Type
→ User question
→ Explicit form submit
→ Stock / historical data lookup
→ ResearchReport / HistoricalResearchReport
→ ResearchContext
→ SelectedResearchContext
→ GroundedResearchAnswer
→ Streamlit presentation
```

## AI Research Tab

`app.py` renders AI Research as its own tab. It is intentionally separate from deterministic `Research` and `Historical Trends` pages so fixed-rule interpretation and AI output are not mixed.

`app.py` owns only form interaction, orchestration, `st.session_state`, and Streamlit rendering. Prompt rules, OpenAI client handling, structured output parsing, and grounding validation remain in `src/ai_research_service.py`.

## Question Type

The tab uses explicit `ResearchQuestionType` values from `src/research_context_selector.py`.

Friendly labels, helper text, and placeholders are centralized in `src/ai_dashboard.py`, so `app.py` does not scatter enum-label mappings.

The UI does not auto-route or reclassify natural-language questions. If the selected type is `Growth`, the selector uses the growth policy even if the question asks about another topic.

## Explicit Submit / API Cost Boundary

OpenAI calls are made only after `st.form_submit_button("產生 AI 研究")` returns `True`.

The tab displays:

```text
此操作會呼叫 OpenAI API，可能產生 API 使用費用。
```

It does not show estimated pricing because the project has no token pricing calculator. It also does not imply that ChatGPT Plus includes API usage.

## Session State

The latest result is stored in:

```text
st.session_state["ai_research_result"]
```

Stored fields include the last symbol, display name, question type, question, selected context summary, selected context, grounded answer, metadata, error detail, request fingerprint, and stale historical data flag.

Streamlit reruns caused by expanders, widgets, scrolling, or page redraws re-render the stored result and do not call OpenAI again.

## Request Fingerprint

`src/ai_dashboard.py` builds a deterministic SHA256 fingerprint from:

- symbol
- question type
- user question
- selected evidence IDs
- selected missing-data IDs
- selected limitation IDs

The fingerprint never includes the API key. It is displayed as a short UI identifier for the rendered answer. It is not used as an automatic cache key; an explicit new submit may create a new API request.

## Selected Research Context

The tab builds `ResearchContext` from already-normalized domain objects and then calls `select_research_context()`.

The `Research Context Used（本次使用資料）` expander shows counts and evidence IDs grouped by category. It does not dump the full context JSON.

## Grounded Findings

Each `GroundedFinding` displays:

- statement
- evidence expander
- cited evidence IDs

If a cited evidence ID cannot be found in `SelectedResearchContext.selected_evidence`, the UI shows `Evidence unavailable` instead of crashing.

## Evidence Display

Evidence display uses only `SelectedResearchContext.selected_evidence`.

It does not query SQLite, fetch Yahoo Finance again, or inspect the full `ResearchContext`.

Value formatting is presentation-only:

- ratio evidence displays as percentage
- monetary evidence keeps currency context
- price evidence keeps currency and two decimals
- period displays as `FY ending YYYY-MM-DD`

Raw evidence values are not mutated.

## Derived Lineage

Derived evidence is labeled as `衍生計算`.

When `derived_from` is present, the UI shows source evidence details recursively in a nested expander. Missing lineage IDs are handled as unavailable evidence.

## Limitations / Missing Data

The UI separates:

- AI answer limitations
- underlying deterministic context limitations
- AI answer missing information
- deterministic missing-data details

This prevents the AI answer from hiding known system limitations such as annual-only data, stale cache, no FX conversion, or missing provider values.

## Validation Badges

Successful answers show:

```text
Structured Output ✓
Evidence Grounding ✓
Numeric Guard ✓
Advice Guard ✓
```

These are validation status indicators, not confidence scores, reliability scores, or trust scores.

## Provider Metadata

The `AI Request Details` expander can display:

- model
- response ID
- generated_at
- input tokens
- output tokens
- reasoning tokens
- cached input tokens
- total tokens

It never displays API keys, headers, raw prompts, raw responses, or full selected payloads.

## Error Handling

The tab catches domain errors and shows safe user messages.

Grounding, numeric-grounding, structured-output, refusal, incomplete response, configuration, and provider failures are not shown as raw tracebacks.

When grounding validation fails, the unverified answer is not rendered.

## API Key Status

The tab checks only whether `OPENAI_API_KEY` exists in the environment.

It shows `Configured` or `Not configured`. It does not show the key prefix, suffix, length, or value, and it does not provide an API key input box.

## No Automatic Rerun Requests

Initial render, widget changes, expanders, and reruns do not call OpenAI.

Only explicit form submit can create a provider request. The clear-result button only clears session state.

## No Persistence

AI answers are not written to SQLite or any other project database.

The MVP is session-only. Browser or app restart may lose the answer.

## No Chat / No Streaming

This Batch does not add `chat_input`, chat history, conversation memory, follow-up turns, streaming, web search, embeddings, vector DB, or scheduled/background AI requests.

The service waits for full structured output and deterministic validation before the UI renders the answer.

## Live UI Validation Policy

After automated tests pass, a manual live UI validation may use one explicit request, for example:

```text
2454.TW
Growth（成長）
請根據目前提供的資料，說明聯發科近年的營收與盈餘成長變化，並指出目前資料有哪些限制。
```

Validation should confirm the flow from dashboard to selector to AI service to validators to UI, and verify reruns do not send another provider request.
