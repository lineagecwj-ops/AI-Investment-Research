import dataclasses
import sys
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ai_followup import AIResearchSession
from ai_followup import MAX_RESEARCH_TURNS
from ai_followup import aggregate_session_usage
from ai_followup import append_verified_turn
from ai_followup import build_followup_suggestions
from ai_followup import build_turn_id
from ai_followup import create_research_turn
from ai_followup import dedupe_suggestions
from ai_followup import infer_followup_question_type
from ai_followup import make_suggestion
from ai_followup import normalize_followup_question
from ai_research_service import AIResponseMetadata
from ai_research_service import GroundedFinding
from ai_research_service import GroundedResearchAnswer
from ai_research_service import build_ai_research_payload
from research_context import EvidenceItem
from research_context import MissingDataItem
from research_context import ResearchLimitation
from research_context_selector import ResearchQuestionType
from research_context_selector import SelectedResearchContext
from research_service import ResearchNextStep


GENERATED_AT = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


class AIFollowUpTestCase(unittest.TestCase):

    def metadata(self, *, usage=None, reasoning_tokens=None):
        return AIResponseMetadata(
            model="gpt-5-mini",
            response_id="resp_test",
            generated_at=GENERATED_AT,
            question_type="growth",
            reasoning_tokens=reasoning_tokens,
            cached_input_tokens=None,
            usage=usage,
        )

    def answer(self, *, summary="Revenue will definitely double.", next_steps=None):
        return GroundedResearchAnswer(
            symbol="2454.TW",
            question_type="growth",
            summary=summary,
            findings=[GroundedFinding("Revenue Growth 為 12.32%。", ["current:revenue_growth"])],
            limitations=["僅包含目前 selected context。"],
            missing_information=["FY2025 EPS unavailable."],
            next_steps=next_steps if next_steps is not None else [
                "請比較近年 Gross Margin、Operating Margin 與 Net Margin 的變化。",
                "請查看近年 Free Cash Flow 的變化。",
            ],
            metadata=self.metadata(),
        )

    def selected_context(self, *, question_type=ResearchQuestionType.GROWTH, evidence=None, missing=None):
        return SelectedResearchContext(
            symbol="2454.TW",
            display_name="聯發科",
            question_type=question_type,
            selected_evidence=evidence if evidence is not None else [
                EvidenceItem(
                    id="current:revenue_growth",
                    category="current_snapshot",
                    metric="revenue_growth",
                    value=0.1232,
                    unit="ratio",
                    currency=None,
                    period_end=None,
                    period_year=None,
                    source="Yahoo Finance snapshot",
                    source_type="source",
                )
            ],
            selected_observation_links=[],
            selected_observations=[],
            selected_missing_data=missing if missing is not None else [
                MissingDataItem(
                    id="missing:historical:eps:2025-12-31",
                    area="historical",
                    metric="eps",
                    period_end=date(2025, 12, 31),
                    period_year=2025,
                    reason="provider value unavailable",
                    impact="EPS YoY cannot be confirmed.",
                    source="Yahoo Finance annual statement",
                )
            ],
            selected_limitations=[
                ResearchLimitation(
                    id="global:annual_historical_data_only",
                    category="data_scope",
                    message="Historical data is annual only.",
                    scope="global",
                )
            ],
            selection_notes=[],
            generated_at=GENERATED_AT,
            source_context_generated_at=GENERATED_AT,
            source_evidence_count=20,
        )

    def turn(self, *, question_type=ResearchQuestionType.GROWTH, fingerprint="abc123", usage=None, symbol="2454.TW"):
        answer = self.answer()
        metadata = self.metadata(usage=usage, reasoning_tokens=(usage or {}).get("reasoning_tokens"))
        answer = GroundedResearchAnswer(
            symbol=symbol,
            question_type=question_type.value,
            summary=answer.summary,
            findings=answer.findings,
            limitations=answer.limitations,
            missing_information=answer.missing_information,
            next_steps=answer.next_steps,
            metadata=metadata,
        )
        return create_research_turn(
            parent_turn_id=None,
            symbol=symbol,
            question_type=question_type,
            question="請說明成長變化。",
            fingerprint=fingerprint,
            answer=answer,
            selected_context=self.selected_context(question_type=question_type),
            generated_at=GENERATED_AT,
        )

    def test_followup_router_maps_english_keywords(self):
        cases = {
            "How did revenue change?": ResearchQuestionType.HISTORICAL_REVENUE,
            "Please compare EPS and earnings.": ResearchQuestionType.HISTORICAL_EARNINGS,
            "How has free cash flow changed?": ResearchQuestionType.HISTORICAL_CASH_FLOW,
            "Check Forward P/E valuation.": ResearchQuestionType.VALUATION,
            "Debt and assets trend": ResearchQuestionType.HISTORICAL_FINANCIAL_POSITION,
            "52-week and 200-day price position": ResearchQuestionType.MARKET_POSITION,
            "risk and attention items": ResearchQuestionType.RISKS_AND_ATTENTION,
            "ROE profitability": ResearchQuestionType.PROFITABILITY,
        }
        for question, expected in cases.items():
            self.assertEqual(infer_followup_question_type(question), expected)

    def test_followup_router_maps_chinese_keywords(self):
        cases = {
            "近年營收怎麼變？": ResearchQuestionType.HISTORICAL_REVENUE,
            "EPS 與盈餘的歷史變化？": ResearchQuestionType.HISTORICAL_EARNINGS,
            "近年毛利率怎麼變？": ResearchQuestionType.HISTORICAL_MARGINS,
            "請看自由現金流": ResearchQuestionType.HISTORICAL_CASH_FLOW,
            "負債與資產結構": ResearchQuestionType.HISTORICAL_FINANCIAL_POSITION,
            "本益比與估值": ResearchQuestionType.VALUATION,
            "52 週市場位置": ResearchQuestionType.MARKET_POSITION,
            "有哪些風險或注意事項？": ResearchQuestionType.RISKS_AND_ATTENTION,
        }
        for question, expected in cases.items():
            self.assertEqual(infer_followup_question_type(question), expected)

    def test_unknown_question_routes_to_general_or_default(self):
        self.assertEqual(
            infer_followup_question_type("請看看還有什麼可以研究。"),
            ResearchQuestionType.GENERAL_RESEARCH,
        )
        self.assertEqual(
            infer_followup_question_type("", ResearchQuestionType.VALUATION),
            ResearchQuestionType.VALUATION,
        )

    def test_question_normalization_for_dedupe(self):
        self.assertEqual(
            normalize_followup_question("  How   has Revenue changed?  "),
            "how has revenue changed?",
        )

    def test_suggestions_prioritize_ai_then_deterministic_then_missing_then_fallback(self):
        selected = self.selected_context()
        deterministic = [
            ResearchNextStep(
                category="Growth",
                title="檢查 Revenue",
                metric="revenue",
                items=["請比較近年 Revenue 的變化。"],
            )
        ]

        suggestions = build_followup_suggestions(
            current_question_type=ResearchQuestionType.GROWTH,
            answer_next_steps=["請比較近年 Gross Margin、Operating Margin 與 Net Margin 的變化。"],
            selected_context=selected,
            deterministic_next_steps=deterministic,
        )

        self.assertEqual(suggestions[0].source, "ai_next_step")
        self.assertEqual(suggestions[0].question_type, ResearchQuestionType.HISTORICAL_MARGINS)
        self.assertEqual(suggestions[1].source, "deterministic_next_step")
        self.assertTrue(any(item.source == "missing_data" for item in suggestions))

    def test_suggestions_are_deduped_and_limited_to_five(self):
        repeated = "請比較近年 Revenue 的變化。"
        suggestions = build_followup_suggestions(
            current_question_type=ResearchQuestionType.GENERAL_RESEARCH,
            answer_next_steps=[repeated, "  請比較近年 revenue 的變化。  "],
            deterministic_next_steps=[
                ResearchNextStep("Growth", "Revenue", "revenue", [repeated])
            ],
        )

        normalized = [normalize_followup_question(item.question) for item in suggestions]
        self.assertEqual(len(normalized), len(set(normalized)))
        self.assertLessEqual(len(suggestions), 5)

    def test_fallback_suggestions_exist_when_ai_next_steps_empty(self):
        suggestions = build_followup_suggestions(
            current_question_type=ResearchQuestionType.GROWTH,
            answer_next_steps=[],
            selected_context=self.selected_context(missing=[]),
        )

        self.assertGreaterEqual(len(suggestions), 3)
        self.assertTrue(all(item.source == "deterministic_fallback" for item in suggestions))

    def test_missing_data_suggestion_does_not_promise_web_search(self):
        suggestions = build_followup_suggestions(
            current_question_type=ResearchQuestionType.GROWTH,
            answer_next_steps=[],
            selected_context=self.selected_context(),
        )

        missing_suggestion = next(item for item in suggestions if item.source == "missing_data")
        self.assertIn("若仍不足請明確說明限制", missing_suggestion.question)
        self.assertNotIn("網路", missing_suggestion.question)

    def test_make_suggestion_has_stable_safe_id(self):
        first = make_suggestion(
            title="研究利潤率變化",
            question="請比較近年 Gross Margin。",
            question_type=ResearchQuestionType.HISTORICAL_MARGINS,
            source="ai_next_step",
            related_metrics=("gross_margin",),
        )
        second = make_suggestion(
            title="研究利潤率變化",
            question="請比較近年 Gross Margin。",
            question_type=ResearchQuestionType.HISTORICAL_MARGINS,
            source="ai_next_step",
            related_metrics=("gross_margin",),
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(len(first.id), 12)

    def test_dedupe_uses_exact_normalized_comparison(self):
        first = make_suggestion(
            title="A",
            question="How has Revenue changed?",
            question_type=ResearchQuestionType.HISTORICAL_REVENUE,
            source="ai_next_step",
            related_metrics=(),
        )
        duplicate = make_suggestion(
            title="B",
            question="  how   has revenue changed? ",
            question_type=ResearchQuestionType.GROWTH,
            source="deterministic_next_step",
            related_metrics=(),
        )

        self.assertEqual(dedupe_suggestions([first, duplicate]), [first])

    def test_build_turn_id_is_deterministic_and_input_sensitive(self):
        first = build_turn_id(
            symbol="2454.TW",
            question_type=ResearchQuestionType.GROWTH,
            question="請說明成長。",
            fingerprint="fingerprint-a",
            generated_at=GENERATED_AT,
        )
        second = build_turn_id(
            symbol="2454.TW",
            question_type=ResearchQuestionType.GROWTH,
            question="請說明成長。",
            fingerprint="fingerprint-a",
            generated_at=GENERATED_AT,
        )
        changed = build_turn_id(
            symbol="2454.TW",
            question_type=ResearchQuestionType.VALUATION,
            question="請說明成長。",
            fingerprint="fingerprint-a",
            generated_at=GENERATED_AT,
        )

        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)
        self.assertEqual(len(first), 16)

    def test_create_research_turn_is_frozen_and_keeps_snapshot_context(self):
        turn = self.turn()

        self.assertEqual(turn.selected_context.selected_evidence[0].id, "current:revenue_growth")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            turn.question = "mutate"

    def test_append_verified_turn_success_and_hard_limit(self):
        session = AIResearchSession(symbol="2454.TW", display_name="聯發科")

        for index in range(MAX_RESEARCH_TURNS):
            append_verified_turn(session, self.turn(fingerprint=f"fp-{index}"))

        self.assertEqual(session.turn_count, 5)
        self.assertFalse(session.can_add_turn)
        with self.assertRaisesRegex(ValueError, "5 回合上限"):
            append_verified_turn(session, self.turn(fingerprint="fp-overflow"))

    def test_append_rejects_cross_symbol_turn(self):
        session = AIResearchSession(symbol="2454.TW")

        with self.assertRaisesRegex(ValueError, "symbol"):
            append_verified_turn(session, self.turn(symbol="2330.TW"))

    def test_failed_turn_not_appended_and_previous_turns_preserved(self):
        session = AIResearchSession(symbol="2454.TW")
        append_verified_turn(session, self.turn(fingerprint="ok"))
        session.last_error = "延伸研究未完成，先前研究結果仍保留。"

        self.assertEqual(session.turn_count, 1)
        self.assertEqual(session.turns[0].fingerprint, "ok")
        self.assertIn("仍保留", session.last_error)

    def test_clear_session_equivalent_resets_turns_and_counter(self):
        session = AIResearchSession(symbol="2454.TW", api_request_count=2)
        append_verified_turn(session, self.turn())

        cleared = AIResearchSession(symbol="2454.TW", display_name="聯發科")

        self.assertEqual(cleared.turn_count, 0)
        self.assertEqual(cleared.api_request_count, 0)
        self.assertNotEqual(session.turn_count, cleared.turn_count)

    def test_aggregate_session_usage_handles_none_safely(self):
        turns = [
            self.turn(
                fingerprint="a",
                usage={
                    "input_tokens": 100,
                    "output_tokens": 80,
                    "reasoning_tokens": 12,
                    "total_tokens": 180,
                },
            ),
            self.turn(fingerprint="b", usage=None),
            self.turn(
                fingerprint="c",
                usage={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
            ),
        ]

        self.assertEqual(
            aggregate_session_usage(turns),
            {
                "input_tokens": 107,
                "output_tokens": 83,
                "reasoning_tokens": 12,
                "total_tokens": 190,
            },
        )

    def test_previous_answer_text_is_not_in_next_payload(self):
        previous_answer = self.answer(summary="Revenue will definitely double.")
        history = [previous_answer]
        selected_context = self.selected_context(question_type=ResearchQuestionType.VALUATION)

        payload = build_ai_research_payload(
            question="請檢查 Forward P/E 與歷史估值資料。",
            selected_context=selected_context,
        )

        self.assertNotIn(history[0].summary, str(payload))
        self.assertNotIn("Revenue will definitely double.", str(payload))
        self.assertEqual(payload["question_type"], "valuation")

    def test_new_context_per_question_type_has_separate_evidence_snapshot(self):
        growth_turn = self.turn(question_type=ResearchQuestionType.GROWTH, fingerprint="growth")
        valuation_evidence = [
            EvidenceItem(
                id="current:forward_pe",
                category="current_snapshot",
                metric="forward_pe",
                value=18.5,
                unit="multiple",
                currency=None,
                period_end=None,
                period_year=None,
                source="Yahoo Finance snapshot",
                source_type="source",
            )
        ]
        valuation_turn = create_research_turn(
            parent_turn_id=growth_turn.turn_id,
            symbol="2454.TW",
            question_type=ResearchQuestionType.VALUATION,
            question="請檢查 Forward P/E。",
            fingerprint="valuation",
            answer=GroundedResearchAnswer(
                symbol="2454.TW",
                question_type="valuation",
                summary="估值資料。",
                findings=[GroundedFinding("Forward P/E 為 18.50。", ["current:forward_pe"])],
                limitations=[],
                missing_information=[],
                next_steps=[],
                metadata=self.metadata(),
            ),
            selected_context=self.selected_context(
                question_type=ResearchQuestionType.VALUATION,
                evidence=valuation_evidence,
            ),
            generated_at=GENERATED_AT,
        )

        growth_ids = {item.id for item in growth_turn.selected_context.selected_evidence}
        valuation_ids = {item.id for item in valuation_turn.selected_context.selected_evidence}
        self.assertNotEqual(growth_ids, valuation_ids)
        self.assertEqual(valuation_turn.parent_turn_id, growth_turn.turn_id)

    def test_same_question_explicit_resubmit_can_create_new_turn_identity(self):
        first = create_research_turn(
            parent_turn_id=None,
            symbol="2454.TW",
            question_type=ResearchQuestionType.GROWTH,
            question="請說明成長變化。",
            fingerprint="same-fingerprint",
            answer=self.answer(),
            selected_context=self.selected_context(),
            generated_at=GENERATED_AT,
        )
        second = create_research_turn(
            parent_turn_id=None,
            symbol="2454.TW",
            question_type=ResearchQuestionType.GROWTH,
            question="請說明成長變化。",
            fingerprint="same-fingerprint",
            answer=self.answer(),
            selected_context=self.selected_context(),
            generated_at=datetime(2026, 8, 2, 9, 1, tzinfo=UTC),
        )

        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertNotEqual(first.turn_id, second.turn_id)

    def test_no_secret_or_raw_provider_response_in_turn(self):
        turn = self.turn()
        rendered = repr(turn)

        self.assertNotIn("OPENAI_API_KEY", rendered)
        self.assertNotIn("sk-", rendered)
        self.assertFalse(hasattr(turn, "raw_response"))
        self.assertFalse(hasattr(turn, "provider_response"))


if __name__ == "__main__":
    unittest.main()
