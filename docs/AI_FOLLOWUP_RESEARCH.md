# AI Follow-up Research

## 1. Purpose

AI Follow-up Research adds a controlled research workflow after an initial grounded answer:

```text
Initial Grounded Research
→ Suggested Follow-up Research
→ User selects or edits one question
→ Explicit submit
→ New SelectedResearchContext
→ New GroundedResearchAnswer
```

Each follow-up is a new, independent, traceable grounded research request.

## 2. Why This Is Not Chat

The workflow is a research log, not free chat. The UI does not use `st.chat_input`, `st.chat_message`, assistant/user transcript history, OpenAI conversations, `previous_response_id`, streaming, or automatic follow-up chaining.

## 3. Stateless Provider Requests

Every provider call is stateless. The AI service receives only the new user question and the newly selected context for that turn.

## 4. Previous AI Answer Isolation

Previous AI answer text is never used as factual grounding for the next turn. Prior summaries, findings, next steps, and model wording may support UX continuity and suggested questions, but they are not included in the provider payload as evidence.

## 5. Follow-up Suggestion Sources

Suggestions may come from:

- `GroundedResearchAnswer.next_steps`
- deterministic `ResearchNextStep` items when available
- selected missing-data records
- deterministic fallback suggestions by question type

Suggestions are question prompts only. They are not factual evidence and do not have higher authority because they came from AI output.

## 6. Deterministic Routing

`infer_followup_question_type()` uses keyword rules only. It does not call OpenAI, embeddings, semantic search, or any AI router.

## 7. User Override

Selecting a suggestion only fills the follow-up form and preselects the suggested `ResearchQuestionType`. The user can override the type before submit.

## 8. New SelectedResearchContext Per Turn

Follow-up submit rebuilds stock data through existing cache services, rebuilds `ResearchContext`, and calls `select_research_context()` with the new question type. The previous turn's `SelectedResearchContext` is not reused.

## 9. Turn Model

`AIResearchTurn` is frozen and stores:

- `turn_id`
- `parent_turn_id`
- `symbol`
- `question_type`
- `question`
- `fingerprint`
- `answer`
- `metadata`
- `selected_context`
- `generated_at`

It does not store raw provider responses or API keys.

## 10. Session State

`AIResearchSession` stores the current symbol, display name, successful turns, API request attempt count, and last safe error. The MVP stays in `st.session_state`.

## 11. Five-turn Limit

Each session allows at most 5 successful turns. At the limit, follow-up submit is disabled and the user can clear the session to start over.

## 12. Explicit Submit / Cost Boundary

Suggestion buttons do not call OpenAI. Only `產生 AI 研究` or `產生延伸研究` can send a provider request. The UI shows that each follow-up may create additional API usage.

## 13. Evidence Per Turn

Each turn stores its own `SelectedResearchContext`. Evidence expanders for old turns read the snapshot saved on that turn, not a latest global context.

## 14. Error Handling

Follow-up failures do not append a turn and do not delete previous verified turns. The UI shows a safe error and states that previous research results remain available.

## 15. Token Usage

`aggregate_session_usage()` sums input, output, reasoning, and total tokens across successful turns when metadata usage is available. It does not calculate dollar cost.

## 16. No Persistence

AI sessions, turns, answers, suggestions, and request counters are not written to SQLite or disk.

## 17. No Conversation Memory

The project does not create OpenAI conversation objects, store chat transcripts, or send historical AI messages into a new provider request.

## 18. No AI Router

Routing is deterministic and local. There is no `classify_question_with_ai()`, embedding router, vector DB, or extra routing API call.

## 19. Security

The API key remains environment-only. Turns do not contain secrets, authorization headers, raw prompts, raw responses, or full provider payload dumps.

## 20. Known Limitations

- Suggestions are deterministic and may be generic.
- Missing-data follow-up can ask the system to confirm whether currently available data is enough, but the system does not perform external web search.
- Session state is browser-session local and can be lost on restart.
- The request counter is session-only and not an accounting ledger.
