from __future__ import annotations

from copy import deepcopy
import json
import re
import sys
import unittest
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_analyst_shortlist import (
    AI_ANALYST_SHORTLIST_MAX_SIZE,
    AIAnalystCardFormatError,
    AIAnalystFinancialNumericNarrativeError,
    generate_analyst_grounded_answer,
    validate_analyst_grounded_answer,
    AIAnalystMissingRequiredEvidenceRefsError,
    AIAnalystShortlistError,
    AIAnalystStageTwoNumericError,
    AIAnalystStageTwoPolicyError,
    AIAnalystValuationComparatorOverclaimError,
    SYNTHESIS_INSTRUCTIONS,
    analyze_research_shortlist as analyze_section_shortlist,
    ANALYST_TEXT_SLOTS,
    ANALYST_SLOT_FALLBACK,
    ANALYST_UNAVAILABLE,
    ANALYST_SECTION_QUESTION,
    build_analyst_section_contexts,
    build_analyst_section_request,
    build_analyst_section_format,
    generate_analyst_section_texts,
    assemble_section_analyst_card,
    validate_analyst_section_text,
    build_failed_analyst_card,
    _required_text,
    build_analyst_repair_request,
    apply_analyst_repair_patch,
    classify_analyst_numbers,
    collect_analyst_final_errors,
    validate_analyst_final_answer,
    generate_analyst_repair_patch,
    ANALYST_PATCH_QUESTION,
    ANALYST_MODEL_EVIDENCE_METRICS,
    build_analyst_model_context,
    build_analyst_missing_evidence,
    build_analyst_section_availability,
    build_analyst_stage_one_question,
    build_stage_two_cards,
    build_stage_two_failure_diagnostic,
    format_stage_two_failure_diagnostic,
    build_stage_two_request_payload,
    build_shortlist_selected_context,
    build_verified_evidence,
    detect_contradictions,
    detect_extreme_value_warnings,
    generate_shortlist_synthesis,
    normalize_analyst_card,
    validate_analyst_card,
    validate_shortlist_synthesis,
)
from ai_research_service import (
    AIForbiddenRecommendationError,
    AIGroundingError,
    AIMissingContextRoleMisuseError,
    AINumericGroundingError,
    AIResponseMetadata,
    AIProviderError,
    AIResearchError,
    GroundedFinding,
    GroundedResearchAnswer,
    STRUCTURED_OUTPUT_FORMAT,
    extract_non_percentage_numeric_claims,
    build_ai_research_payload,
    generate_grounded_research_answer,
    percentage_value_for_metric,
    numeric_evidence_candidate,
    validate_grounded_ai_answer,
)
from ai_config import AIResearchConfig, MAX_RESEARCH_QUESTION_LENGTH
from models import Stock


NOW = datetime(2026, 8, 29, tzinfo=UTC)


def _analyze_research_shortlist(
    rows: list[dict[str, Any]],
    *,
    stock_loader: Callable[[str], Stock | None],
    grounded_generator: Callable[..., GroundedResearchAnswer] = generate_analyst_grounded_answer,
    repair_generator: Callable[..., dict[str, Any]] = generate_analyst_repair_patch,
    synthesis_generator: Callable[..., dict[str, Any]] | None = None,
    generated_at: datetime | None = None,
    radar_evidence_resolver: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    # Historical replay harness only; never a production generation entry point.
    if rows and len(rows) <= AI_ANALYST_SHORTLIST_MAX_SIZE and grounded_generator is generate_analyst_grounded_answer:
        raise AssertionError("Legacy replay requires injected offline outputs.")
    if not rows:
        raise AIAnalystShortlistError("本次研究清單尚無標的，請先加入股票。")
    if len(rows) > AI_ANALYST_SHORTLIST_MAX_SIZE:
        raise AIAnalystShortlistError("AI 分析 V0 一次最多分析 5 檔，請先縮小本次研究清單。")

    cards = []
    call_count = 0
    successful_count = 0
    format_repair_count = 0
    policy_regeneration_count = 0
    successful_cards = []
    excluded_symbols = []
    for row in rows:
        symbol = _required_text(row.get("股票代號"), "股票代號")
        context = None
        try:
            context = build_shortlist_selected_context(
                row,
                stock=stock_loader(symbol),
                generated_at=generated_at,
                radar_evidence_resolver=radar_evidence_resolver,
            )
            model_context = build_analyst_model_context(context)
            call_count += 1
            answer = deepcopy(grounded_generator(
                question=build_analyst_stage_one_question(model_context),
                selected_context=model_context,
            ))
            request = build_analyst_repair_request(answer, model_context)
            if request["slots"]:
                reasons = [reason for slot in request["slots"] for reason in slot["reasons"]]
                policy_regeneration_count += int(any(reason.startswith("POLICY_SAFE_WORDING") for reason in reasons))
                format_repair_count += int(any(not reason.startswith("POLICY_SAFE_WORDING") for reason in reasons))
                call_count += 1
                response = repair_generator(request=deepcopy(request), selected_context=deepcopy(model_context))
                answer = apply_analyst_repair_patch(answer, request, response, model_context)
            validate_analyst_final_answer(answer, model_context)
            card = normalize_analyst_card(answer, context, row)
            successful_count += 1
            successful_cards.append(card)
        except Exception as error:
            card = build_failed_analyst_card(row, error, context=context)
            excluded_symbols.append(symbol)
        cards.append(card)

    for card in cards:
        validate_analyst_card(card)

    synthesis = None
    synthesis_error = None
    stage2_diagnostic = None
    synthesis_skip_reason = None
    if successful_count >= 2:
        try:
            call_count += 1
            if synthesis_generator is None:
                synthesis = generate_shortlist_synthesis(cards=successful_cards)
            else:
                synthesis = synthesis_generator(cards=build_stage_two_cards(successful_cards))
            validate_shortlist_synthesis(synthesis, successful_cards)
        except Exception as error:
            synthesis = None
            stage2_diagnostic = build_stage_two_failure_diagnostic(error, successful_cards)
            synthesis_error = stage2_diagnostic["code"]
    else:
        synthesis_skip_reason = (
            "僅一檔通過初步審查，至少需要兩檔才能進行清單比較。"
            if successful_count == 1
            else "尚無標的通過初步審查，因此未進行清單比較。"
        )

    return {
        "cards": cards,
        "synthesis": synthesis,
        "synthesis_error": synthesis_error,
        "stage2_diagnostic": stage2_diagnostic,
        "synthesis_skip_reason": synthesis_skip_reason,
        "stage2_excluded_symbols": excluded_symbols,
        "provider_call_count": call_count,
        "stage1_success_count": successful_count,
        "stage1_format_repair_count": format_repair_count,
        "stage1_policy_regeneration_count": policy_regeneration_count,
    }


def _scripted_patches(request, answer):
    """Translate older two-answer fixtures into the new provider patch wire format."""
    if isinstance(answer, dict):
        return answer
    patches = []
    for slot in request["slots"]:
        values = getattr(answer, slot["field"])
        if slot["index"] >= len(values):
            return {"findings": []}
        value = values[slot["index"]]
        item = {"slot_id": slot["slot_id"]}
        if "rewritten_text" in slot["allowed_patch_fields"]:
            item["rewritten_text"] = value.statement if slot["field"] == "findings" else value
        if slot["field"] == "findings" and (
            "evidence_refs" in slot["allowed_patch_fields"] or value.evidence_ids != slot["locked_evidence_refs"]
        ):
            item["evidence_refs"] = value.evidence_ids
        patches.append(item)
    return {"patches": patches}


def analyze_research_shortlist(*args, **kwargs):
    """Keep existing scripted regression fixtures offline; production never accepts full-card repairs."""
    generator = kwargs.get("grounded_generator")
    if generator is not None and "repair_generator" not in kwargs:
        def repair(*, request, selected_context):
            answer = generator(question=request["question"], selected_context=selected_context)
            return _scripted_patches(request, answer)
        kwargs["repair_generator"] = repair
    return _analyze_research_shortlist(*args, **kwargs)


def shortlist_row(symbol="2330.TW", *, yoy=0.25, mom=0.10, rel20=0.05, rel60=0.12):
    return {
        "股票代號": symbol,
        "公司名稱": "台積電" if symbol == "2330.TW" else "聯發科",
        "產業": "半導體業",
        "營收月份": "2026-08",
        "Revenue YoY": f"{yoy:.2%}" if yoy is not None else "unavailable",
        "Revenue MoM": f"{mom:.2%}" if mom is not None else "unavailable",
        "REL_RETURN_20D": f"{rel20:.2%}" if rel20 is not None else "unavailable",
        "REL_RETURN_60D": f"{rel60:.2%}" if rel60 is not None else "unavailable",
        "研究條件": "營收年增為正、60D 強於 0050",
        "長期研究": "有資料",
        "歷史趨勢": "尚無資料",
        "AI 研究": "尚無資料",
        "波段研究": "有資料",
        "_analyst_evidence": {
            "revenue_period": "2026-08",
            "revenue_yoy": yoy,
            "revenue_mom": mom,
            "relative_return_20d": rel20,
            "relative_return_60d": rel60,
            "condition_flags": ["營收年增為正", "60D 強於 0050"],
        },
    }


def canonical_2027_radar(symbol):
    if symbol != "2027.TW":
        return None
    return {
        "revenue_period": "N/A",
        "revenue_yoy": 0.4612,
        "revenue_mom": 0.0597,
        "relative_return_20d": 0.1260,
        "relative_return_60d": 0.2047,
        "condition_flags": ["營收年增為正", "60D 強於 0050"],
        "retrieved_at": "2026-08-30T00:00:00+08:00",
    }


def cached_stock(symbol="2330.TW"):
    return Stock(
        symbol=symbol,
        company_name="台積電" if symbol == "2330.TW" else "聯發科",
        industry="Semiconductors",
        current_price=100.0,
        currency="TWD",
        return_on_equity=0.2,
        gross_margin=0.5,
        operating_margin=0.3,
        net_margin=0.25,
        revenue_growth=0.15,
        earnings_growth=0.12,
        trailing_pe=20.0,
        forward_pe=18.0,
        price_to_book=4.0,
        fifty_two_week_high=110.0,
        fifty_two_week_low=70.0,
        fifty_day_average=98.0,
        two_hundred_day_average=90.0,
    )


def grounded_answer_with_findings(context, findings):
    return GroundedResearchAnswer(
        symbol=context.symbol,
        question_type=context.question_type.value,
        summary="研究優先度：值得觀察\n目前證據供初步研究使用。",
        findings=findings,
        limitations=[],
        missing_information=[],
        next_steps=["確認最新公司揭露資料。"],
        metadata=AIResponseMetadata(
            model="test",
            response_id="test-response",
            generated_at=NOW,
            question_type=context.question_type.value,
        ),
    )


def acceptance_stock(symbol):
    names = {"1216.TW": "統一", "1608.TW": "華榮", "2027.TW": "大成鋼"}
    if symbol != "2027.TW":
        return Stock(symbol=symbol, company_name=names[symbol], currency="TWD")
    stock = cached_stock(symbol)
    stock.company_name = names[symbol]
    stock.current_price = 48.4
    stock.fifty_day_average = 44.076
    stock.two_hundred_day_average = 39.54675
    stock.trailing_pe = 9.6994
    stock.forward_pe = 8.0862
    stock.price_to_book = 1.508352
    stock.earnings_growth = 3.622
    stock.return_on_equity = .1703
    stock.debt_to_equity = 54.759
    stock.total_cash = 7_774_000_000
    stock.total_debt = 36_820_000_000
    stock.trailing_eps = 1.23
    stock.operating_cash_flow = 2_100_000_000
    stock.free_cash_flow = 1_200_000_000
    return stock


def acceptance_answer(context):
    if context.symbol != "2027.TW":
        return grounded_answer(context)
    return grounded_answer_with_findings(context, [
        GroundedFinding("營收方向提供研究線索。", ["radar:2027.TW:revenue_yoy"]),
        GroundedFinding("獲利成長資料可作為後續研究線索。", ["current:earnings_growth"]),
        GroundedFinding("估值倍數已可觀察，但缺少同業與歷史比較脈絡。", ["current:trailing_pe", "current:price_to_book"]),
        GroundedFinding("目前市場位置仍需以中短期趨勢持續確認。", ["current:current_price", "current:fifty_day_average", "current:two_hundred_day_average"]),
    ])


def section_answer(context):
    texts = {
        "opportunity_text": "營收方向提供研究線索，仍需確認持續性。",
        "fundamental_text": "目前財務證據可供初步研究，仍需追蹤持續性。",
        "valuation_text": "目前已有估值倍數可供觀察，但缺少歷史或同業比較。",
        "market_text": "目前市場資料可供初步研究，仍需持續確認。",
    }
    return {**{slot: texts[slot] for slot in build_analyst_section_contexts(context)},
            "priority_label": "值得觀察", "priority_reason": "先查核現有線索的持續性。"}


def bound_finding(statement, bindings, *, evidence_ids=None):
    return GroundedFinding(
        statement,
        evidence_ids if evidence_ids is not None else list(dict.fromkeys(key for key, _ in bindings)),
    )


def refreshed_binding_stock(symbol):
    stock = cached_stock(symbol)
    stock.current_price = 75.70
    stock.fifty_day_average = 76.572
    stock.two_hundred_day_average = 74.363
    stock.trailing_pe = 3.28891
    stock.price_to_book = 1.41983
    stock.total_cash = 1_810_000_000
    stock.total_debt = 4_190_000_000
    stock.debt_to_equity = 54.759
    stock.earnings_growth = 9.249
    stock.fetched_at = NOW
    return stock


def refreshed_bound_findings():
    return [
        bound_finding(
            "目前股價為 75.70，50 日均價為 76.57，200 日均價為 74.36。",
            [("current:current_price", "75.70"), ("current:fifty_day_average", "76.57"),
             ("current:two_hundred_day_average", "74.36")],
        ),
        bound_finding(
            "Trailing P/E 為 3.29，P/B 為 1.42；缺少同業與歷史比較依據。",
            [("current:trailing_pe", "3.29"), ("current:price_to_book", "1.42")],
        ),
        bound_finding(
            "Total Cash 為 TWD 1.81B，Total Debt 為 TWD 4.19B，Debt to Equity 為 54.76%。",
            [("current:total_cash", "TWD 1.81B"), ("current:total_debt", "TWD 4.19B"),
             ("current:debt_to_equity", "54.76%")],
        ),
        bound_finding("Earnings Growth 為 924.90%。", [("current:earnings_growth", "924.90%")]),
    ]


def grounded_answer(context, priority="值得觀察"):
    evidence_by_metric = {item.metric: item.id for item in context.selected_evidence}
    findings = []
    groups = (
        ("營收方向提供研究線索。", ("revenue_yoy", "revenue_mom")),
        ("基本面品質目前有正向資料。", ("return_on_equity",)),
        ("估值資料可供後續比較。", ("trailing_pe",)),
        ("市場位置仍需持續確認。", ("current_price",)),
    )
    for statement, metrics in groups:
        evidence_id = next((evidence_by_metric[metric] for metric in metrics if metric in evidence_by_metric), None)
        if evidence_id is not None:
            findings.append(GroundedFinding(statement, [evidence_id]))
    return GroundedResearchAnswer(
        symbol=context.symbol,
        question_type=context.question_type.value,
        summary=f"研究優先度：{priority}\n目前證據供初步研究使用。",
        findings=findings,
        limitations=["資料時點與完整性仍需確認。"],
        missing_information=[],
        next_steps=["確認最新公司揭露資料。"],
        metadata=AIResponseMetadata(
            model="test",
            response_id="test-response",
            generated_at=NOW,
            question_type=context.question_type.value,
        ),
    )


def valid_synthesis(cards):
    return {
        "priority_deep_dive": [],
        "cross_company_observations": ["各公司證據完整度不同，應分別補齊。"],
        "overall_note": "本結果只用於研究注意力安排。",
    }


class AIAnalystShortlistTest(unittest.TestCase):
    def test_analyst_payload_has_only_available_citations_including_sparse_radar(self):
        for symbol, yoy, mom in (("1216.TW", .0885, .0663), ("1608.TW", .4267, .1496)):
            with self.subTest(symbol=symbol):
                row = shortlist_row(symbol, yoy=yoy, mom=mom, rel20=None, rel60=None)
                row["_analyst_evidence"]["revenue_period"] = None
                context = build_shortlist_selected_context(row, stock=Stock(symbol=symbol), generated_at=NOW)
                before = context.to_dict()
                self.assertIn("revenue_period", {item.metric for item in context.selected_missing_data})
                model_context = build_analyst_model_context(context)
                payload = build_ai_research_payload(
                    question=build_analyst_stage_one_question(model_context), selected_context=model_context,
                )
                self.assertEqual(payload["allowed_missing_context_ids"], [])
                self.assertEqual(payload["missing_data"], [])
                self.assertNotRegex(json.dumps(payload), r"(?:missing|context|global):")
                self.assertEqual(payload["available_evidence_ids"], [
                    f"radar:{symbol}:revenue_yoy", f"radar:{symbol}:revenue_mom",
                ])
                self.assertEqual(context.to_dict(), before)

    def test_missing_labels_and_tasks_are_deterministic_not_model_generated(self):
        row = shortlist_row("1216.TW", yoy=.0885, mom=.0663, rel20=None, rel60=None)
        row["_analyst_evidence"]["revenue_period"] = None
        context = build_shortlist_selected_context(row, stock=Stock(symbol="1216.TW"), generated_at=NOW)
        labels, checks = build_analyst_missing_evidence(context)
        answer = grounded_answer(context)
        malicious_gap = replace(answer, missing_information=["任意捏造缺漏"], next_steps=[])
        first = normalize_analyst_card(answer, context, row)
        second = normalize_analyst_card(malicious_gap, context, row)
        self.assertEqual(first["missing_evidence"], second["missing_evidence"])
        self.assertEqual(first["next_checks"], second["next_checks"])
        self.assertEqual(labels.count("月營收資料期間"), 1)
        self.assertIn("20D 相對 0050", labels)
        self.assertIn("60D 相對 0050", labels)
        for check in ("確認月營收資料期間", "補足現金流資料", "補足歷史或同業估值比較", "補足相對 0050 市場確認"):
            self.assertEqual(checks.count(check), 1)
        self.assertEqual(len(labels), len(set(labels)))
        self.assertEqual(len(checks), len(set(checks)))
        self.assertNotRegex(json.dumps([labels, checks]), r"(?:missing|context|global):")

    def _run_adapter_findings(self, outputs, *, stock=None, symbol="1608.TW"):
        """Exercise the real adapter's validate-before-return path without any network."""
        payloads, contexts = [], []
        class FakeClient:
            def create_grounded_answer(_self, **kwargs):
                payload = kwargs["payload"]
                payloads.append(payload)
                findings = outputs[len(payloads) - 1]
                if "slots" in payload:
                    self.assertEqual(kwargs["response_format"]["name"], "analyst_slot_patch")
                    if isinstance(findings, dict):
                        data = findings
                    else:
                        answer = grounded_answer_with_findings(contexts[0], [
                            GroundedFinding(item["statement"], item.get("evidence_ids", [])) for item in findings
                        ])
                        data = _scripted_patches(payload, answer)
                else:
                    self.assertEqual(kwargs["response_format"], STRUCTURED_OUTPUT_FORMAT)
                    data = {
                        "symbol": payload["symbol"], "question_type": payload["question_type"],
                        "summary": "研究優先度：值得觀察", "findings": findings,
                        "limitations": [], "missing_information": [], "next_steps": [],
                    }
                return SimpleNamespace(output_text=json.dumps(data, ensure_ascii=False), id="mock")

        def generate(**kwargs):
            contexts.append(kwargs["selected_context"])
            return generate_analyst_grounded_answer(
                **kwargs, client=FakeClient(),
                config=AIResearchConfig("mock", 2400, "minimal", "low", 30), generated_at=NOW,
            )
        def repair(**kwargs):
            contexts.append(kwargs["selected_context"])
            return generate_analyst_repair_patch(
                **kwargs, client=FakeClient(), config=AIResearchConfig("mock", 2400, "minimal", "low", 30),
            )
        result = analyze_research_shortlist(
            [shortlist_row(symbol, yoy=.4267, mom=.1496, rel20=None, rel60=None)],
            stock_loader=lambda _: stock or Stock(symbol=symbol),
            grounded_generator=generate, repair_generator=repair,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )
        if len(contexts) == 2:
            self.assertEqual(contexts[0], contexts[1])
        return result, payloads

    def test_model_output_uses_shared_schema_without_numeric_mentions(self):
        qualitative = [{
            "statement": "市場位置仍需持續確認。",
            "evidence_ids": ["current:current_price"],
        }]
        result, payloads = self._run_adapter_findings([qualitative], stock=refreshed_binding_stock("1216.TW"), symbol="1216.TW")
        self.assertEqual(len(payloads), 1)
        self.assertEqual(result["stage1_success_count"], 1, result["cards"])
        self.assertNotIn("numeric_mentions", json.dumps(payloads[0]))
        self.assertNotIn("75.70", result["cards"][0]["market_confirmation"])

    def test_numeric_rich_real_style_findings_get_one_qualitative_repair_for_each_company(self):
        for symbol in ("1216.TW", "1608.TW", "2027.TW"):
            with self.subTest(symbol=symbol):
                numeric_rich = [{
                    "statement": "目前價格為 TWD 75.70。",
                    "evidence_ids": ["current:current_price"],
                }]
                qualitative = [{
                    "statement": "市場位置仍需持續確認。",
                    "evidence_ids": ["current:current_price"],
                }]
                result, payloads = self._run_adapter_findings(
                    [numeric_rich, qualitative], stock=refreshed_binding_stock(symbol), symbol=symbol,
                )
                self.assertEqual(len(payloads), 2)
                self.assertEqual(result["stage1_success_count"], 1, result["cards"])
                self.assertEqual(result["stage1_format_repair_count"], 1)
                self.assertIn("FINANCIAL_NUMERIC_NARRATIVE_PRESENT", payloads[1]["slots"][0]["reasons"])
                self.assertNotRegex(result["cards"][0]["market_confirmation"], r"\d")

    def test_latest_real_1608_currency_and_moving_average_skips_prose_metric_inference(self):
        stock = refreshed_binding_stock("1608.TW")
        stock.current_price = 37.85
        stock.fifty_day_average = 33.806
        stock.two_hundred_day_average = 34.70875
        numeric_rich = [{
            "statement": "目前股價 TWD 37.85，位於 50 日均線之上。",
            "evidence_ids": ["current:current_price", "current:fifty_day_average"],
        }]
        qualitative = [{
            "statement": "目前價格相對中期均價偏強，但仍需更多市場確認。",
            "evidence_ids": ["current:current_price", "current:fifty_day_average"],
        }]

        result, payloads = self._run_adapter_findings(
            [numeric_rich, qualitative], stock=stock, symbol="1608.TW",
        )

        self.assertEqual(len(payloads), 2)
        self.assertEqual(result["stage1_success_count"], 1, result["cards"])
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertNotIn("current_price=50", json.dumps(result, ensure_ascii=False))
        self.assertEqual(payloads[1]["slots"][0]["reasons"], ["FINANCIAL_NUMERIC_NARRATIVE_PRESENT"])

    def test_currency_without_space_is_numeric_free_format_repairable(self):
        qualitative = [{
            "statement": "市場位置仍需持續確認。",
            "evidence_ids": ["current:current_price"],
        }]
        for currency_value in ("TWD37.85", "TWD 37.85"):
            with self.subTest(currency_value=currency_value):
                numeric_rich = [{
                    "statement": f"目前股價為 {currency_value}。",
                    "evidence_ids": ["current:current_price"],
                }]
                stock = refreshed_binding_stock("1608.TW")
                stock.current_price = 37.85
                result, payloads = self._run_adapter_findings(
                    [numeric_rich, qualitative], stock=stock, symbol="1608.TW",
                )
                self.assertEqual(len(payloads), 2)
                self.assertEqual(result["stage1_success_count"], 1, result["cards"])
                self.assertEqual(result["stage1_format_repair_count"], 1)

    def test_numeric_free_repair_preserves_valid_original_refs_for_1216_and_1608(self):
        for symbol in ("1216.TW", "1608.TW"):
            with self.subTest(symbol=symbol):
                calls = []

                def initial_generator(*, selected_context, **_kwargs):
                    calls.append("initial")
                    return grounded_answer_with_findings(selected_context, [GroundedFinding(
                        "目前股價 TWD 37.85，位於 50 日均線之上。",
                        ["current:current_price", "current:fifty_day_average"],
                    )])

                def repair_generator(*, request, **_kwargs):
                    calls.append("repair")
                    return {"patches": [{"slot_id": request["slots"][0]["slot_id"],
                                         "rewritten_text": "目前價格相對中期均價偏強，但仍需更多市場確認。"}]}

                stock = refreshed_binding_stock(symbol)
                stock.current_price = 37.85
                stock.fifty_day_average = 33.806
                result = analyze_research_shortlist(
                    [shortlist_row(symbol, yoy=.4267, mom=.1496, rel20=None, rel60=None)],
                    stock_loader=lambda _symbol: stock,
                    grounded_generator=initial_generator,
                    repair_generator=repair_generator,
                    synthesis_generator=lambda *, cards: valid_synthesis(cards),
                    generated_at=NOW,
                )

                self.assertEqual(calls, ["initial", "repair"])
                self.assertEqual(result["stage1_success_count"], 1, result["cards"])
                self.assertEqual(result["stage1_format_repair_count"], 1)
                self.assertEqual(
                    result["cards"][0]["evidence_refs"],
                    ["current:current_price", "current:fifty_day_average"],
                )

    def test_numeric_free_repair_still_fails_when_rewritten_text_exceeds_preserved_refs(self):
        row = shortlist_row("1608.TW", yoy=.4267, mom=.1496, rel20=None, rel60=None)

        def initial_generator(*, selected_context, **_kwargs):
            return grounded_answer_with_findings(selected_context, [GroundedFinding(
                "目前股價 TWD 37.85。", ["current:current_price"],
            )])

        def repair_generator(*, request, **_kwargs):
            return {"patches": [{"slot_id": request["slots"][0]["slot_id"],
                                 "rewritten_text": "獲利成長資料可作為後續研究線索。"}]}

        stock = refreshed_binding_stock("1608.TW")
        stock.current_price = 37.85
        result = analyze_research_shortlist(
            [row],
            stock_loader=lambda _symbol: stock,
            grounded_generator=initial_generator,
            repair_generator=repair_generator,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )

        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertIn("required evidence references", result["cards"][0]["missing_evidence"][0])

    def test_second_numeric_rich_response_fails_without_third_generation(self):
        numeric_rich = [{"statement": "目前價格為 TWD 75.70。", "evidence_ids": ["current:current_price"]}]
        result, payloads = self._run_adapter_findings(
            [numeric_rich, numeric_rich], stock=refreshed_binding_stock("2027.TW"), symbol="2027.TW",
        )
        self.assertEqual(len(payloads), 2)
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertIn("FINANCIAL_NUMERIC_NARRATIVE_PRESENT", result["cards"][0]["missing_evidence"][0])

    def test_structural_numbers_without_financial_values_do_not_regenerate(self):
        for statement in (
            "價格仍需持續確認。",
            "價格位於 50-day 與 200-day 趨勢觀察區間，52-week 脈絡仍需補充。",
            "股價位於 50 日均線之上。",
            "1216.TW 的資料時點為 2026-08-30，版本為 V1.0。",
        ):
            with self.subTest(statement=statement):
                findings = [{"statement": statement, "evidence_ids": ["current:current_price"]}]
                result, payloads = self._run_adapter_findings([findings], stock=refreshed_binding_stock("1216.TW"), symbol="1216.TW")
                self.assertEqual(len(payloads), 1)
                self.assertEqual(result["stage1_success_count"], 1, result["cards"])

    def test_unknown_evidence_and_recommendation_are_not_numeric_free_repairable(self):
        unknown = [{"statement": "目前股價 TWD 37.85。", "evidence_ids": ["current:invented"]}]
        policy = [{"statement": "可買進。", "evidence_ids": ["current:current_price"]}]
        result, payloads = self._run_adapter_findings([unknown], stock=refreshed_binding_stock("1608.TW"))
        self.assertEqual(len(payloads), 1)
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["stage1_format_repair_count"], 0)

        result, payloads = self._run_adapter_findings([policy], stock=refreshed_binding_stock("1608.TW"))
        self.assertEqual(len(payloads), 2)
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["stage1_policy_regeneration_count"], 1)
        self.assertEqual(result["stage1_format_repair_count"], 0)

    def test_numeric_free_repair_question_preserves_original_limit(self):
        context = build_analyst_model_context(build_shortlist_selected_context(
            shortlist_row("2027.TW"), stock=refreshed_binding_stock("2027.TW"), generated_at=NOW,
        ))
        answer = grounded_answer_with_findings(context, [GroundedFinding("目前股價 TWD 75.70。", ["current:current_price"])])
        question = build_analyst_repair_request(answer, context)["question"]
        self.assertEqual(MAX_RESEARCH_QUESTION_LENGTH, 1500)
        self.assertLessEqual(len(question), 1500)

    def test_hold_action_regenerates_once_through_real_adapter_and_validates_safe_answer(self):
        unsafe = [{"statement": "可持有觀察。",
                   "evidence_ids": ["radar:1608.TW:revenue_yoy", "radar:1608.TW:revenue_mom"]}]
        safe = [{"statement": "目前營收動能值得進一步研究，但其他研究證據仍不足。",
                 "evidence_ids": ["radar:1608.TW:revenue_yoy", "radar:1608.TW:revenue_mom"]}]
        result, payloads = self._run_adapter_findings([unsafe, safe])
        self.assertEqual(len(payloads), 2)
        self.assertEqual(result["stage1_policy_regeneration_count"], 1)
        self.assertEqual(result["stage1_format_repair_count"], 0)
        self.assertEqual(result["stage1_success_count"], 1)
        self.assertEqual(result["provider_call_count"], 2)  # Two Stage-1 attempts; no singleton comparison.
        self.assertIn("POLICY_SAFE_WORDING:HOLD_ACTION", payloads[1]["slots"][0]["reasons"])
        self.assertLessEqual(len(payloads[1]["question"]), 1500)
        self.assertEqual(payloads[1]["slots"][0]["locked_evidence_refs"], unsafe[0]["evidence_ids"])
        self.assertEqual(payloads[1]["slots"][0]["allowed_patch_fields"], ["rewritten_text"])
        self.assertNotIn("持有", json.dumps(result["cards"], ensure_ascii=False))
        self.assertEqual(unsafe[0]["statement"], "可持有觀察。")
        self.assertEqual(result["cards"][0]["fundamental_quality"], "目前證據不足。")

    def test_second_policy_violation_fails_closed_without_third_attempt(self):
        for phrase in ("持有", "買進", "賣出", "加碼", "減碼", "目標價", "預期報酬率"):
            with self.subTest(phrase=phrase):
                first = [{"statement": "可持有觀察。", "evidence_ids": ["radar:1608.TW:revenue_yoy"]}]
                second = [{"statement": phrase, "evidence_ids": ["radar:1608.TW:revenue_yoy"]}]
                result, payloads = self._run_adapter_findings([first, second])
                self.assertEqual(len(payloads), 2)
                self.assertEqual(result["stage1_success_count"], 0)
                self.assertEqual(result["provider_call_count"], 2)
                self.assertIsNone(result["synthesis"])

    def test_policy_regeneration_never_masks_other_first_or_second_attempt_failures(self):
        unsafe = [{"statement": "可持有觀察。", "evidence_ids": ["radar:1608.TW:revenue_yoy"]}]
        failures = [
            {"statement": "營收方向提供線索。", "evidence_ids": ["observations[0]"]},
            {"statement": "ROE 顯示資本效率。", "evidence_ids": ["radar:1608.TW:revenue_yoy"]},
        ]
        stock = Stock(symbol="1608.TW", currency="TWD", current_price=48.4)
        for failure in failures:
            for mode in ("only", "mixed", "second"):
                with self.subTest(failure=failure, mode=mode):
                    outputs = ([failure],) if mode == "only" else (
                        (unsafe + [failure],) if mode == "mixed" else (unsafe, [failure])
                    )
                    result, payloads = self._run_adapter_findings(outputs, stock=stock)
                    self.assertEqual(result["stage1_success_count"], 0)
                    self.assertEqual(len(payloads), 2 if mode == "second" else 1)
                    self.assertEqual(result["stage1_policy_regeneration_count"], int(mode == "second"))

    def test_rich_policy_regeneration_question_keeps_original_1500_limit(self):
        stock = cached_stock("2027.TW")
        stock.total_cash, stock.total_debt, stock.debt_to_equity = 16097614848, 51051364352, 54.759
        context = build_analyst_model_context(build_shortlist_selected_context(
            shortlist_row("2027.TW"), stock=stock, generated_at=NOW,
        ))
        answer = grounded_answer_with_findings(context, [GroundedFinding("可持有觀察。", ["current:current_price"])])
        self.assertEqual(MAX_RESEARCH_QUESTION_LENGTH, 1500)
        self.assertLessEqual(len(build_analyst_repair_request(answer, context)["question"]), 1500)

    def test_format_and_policy_repairs_share_one_extra_attempt_budget(self):
        unsafe = [{"statement": "可持有觀察。", "evidence_ids": ["radar:1608.TW:revenue_yoy"]}]
        overlap = [{"statement": "估值與市場位置可供初步研究。",
                    "evidence_ids": ["current:trailing_pe", "current:current_price"]}]
        for outputs, policy_count, format_count in (([unsafe, overlap], 1, 0), ([overlap, unsafe], 0, 1)):
            with self.subTest(policy_count=policy_count):
                result, payloads = self._run_adapter_findings(outputs, stock=cached_stock("1608.TW"))
                self.assertEqual(len(payloads), 2)
                self.assertEqual(result["stage1_success_count"], 0)
                self.assertEqual(result["stage1_policy_regeneration_count"], policy_count)
                self.assertEqual(result["stage1_format_repair_count"], format_count)

    def test_optional_ai_next_check_requires_available_reference_and_numeric_free_text(self):
        row = shortlist_row("2027.TW")
        context = build_shortlist_selected_context(row, stock=cached_stock("2027.TW"), generated_at=NOW)
        answer = grounded_answer(context)
        baseline = normalize_analyst_card(replace(answer, next_steps=[]), context, row)
        ungrounded = normalize_analyst_card(replace(answer, next_steps=["任意新增研究論點。"]), context, row)
        self.assertEqual(baseline["next_checks"], ungrounded["next_checks"])
        for text, error in (
            ("確認 Revenue YoY = 99%（radar:2027.TW:revenue_yoy）。", AIAnalystFinancialNumericNarrativeError),
            ("確認 current:invented_metric。", AIGroundingError),
        ):
            with self.subTest(text=text), self.assertRaises(error):
                normalize_analyst_card(replace(answer, next_steps=[text]), context, row)

    def test_window_tokens_never_bind_to_any_financial_metric(self):
        windows = (
            "50 日均線", "50日均線", "50-day average", "50 日 均線", "50 日移動平均線",
            "200 日均線", "200日均線", "200-day average", "200 日 均線",
            "52 週高點", "52週高點", "52-week high", "52 週 高點",
            "52 週低點", "52週低點", "52-week low", "52 週 低點", "50\u2011day average",
        )
        for metric in ("Current price", "目前價格", "Revenue YoY", "Revenue MoM", "Cash", "Debt", "P/B"):
            for window in windows:
                with self.subTest(metric=metric, window=window):
                    self.assertEqual(extract_non_percentage_numeric_claims(f"{metric} compared with {window}。"), [])

    def test_2027_windows_do_not_hide_explicit_price_or_average_values(self):
        stock = Stock(symbol="2027.TW", currency="TWD", current_price=48.4, fifty_day_average=44.08)
        context = build_shortlist_selected_context(shortlist_row("2027.TW"), stock=stock, generated_at=NOW)
        refs = ["current:current_price", "current:fifty_day_average"]
        for statement, metric, value in (
            ("50-day average is TWD 44.08", "fifty_day_average", "44.08"),
            ("50 日 均線為 TWD 44.08", "fifty_day_average", "44.08"),
            ("Current Price is TWD 48.40 and above the 50-day average.", "current_price", "48.40"),
        ):
            claims = extract_non_percentage_numeric_claims(statement)
            self.assertEqual([(claim.metric, str(claim.canonical_value)) for claim in claims], [(metric, value)])
            validate_grounded_ai_answer(grounded_answer_with_findings(context, [GroundedFinding(statement, refs)]), context)
        for statement in ("Current Price = TWD 50.00", "目前價格為 TWD 50.00，高於 50 日 均線。"):
            with self.assertRaises(AINumericGroundingError):
                validate_grounded_ai_answer(grounded_answer_with_findings(context, [GroundedFinding(statement, refs)]), context)

        # Both canonical raw and the exact UI representation are supported.
        stock.fifty_day_average = 44.076
        exact_context = build_shortlist_selected_context(shortlist_row("2027.TW"), stock=stock, generated_at=NOW)
        exact = grounded_answer_with_findings(exact_context, [GroundedFinding("50-day average is TWD 44.076", refs)])
        validate_grounded_ai_answer(exact, exact_context)
        validate_grounded_ai_answer(replace(exact, findings=[GroundedFinding("50-day average is TWD 44.08", refs)]), exact_context)
        with self.assertRaises(AINumericGroundingError):
            validate_grounded_ai_answer(replace(exact, findings=[GroundedFinding("50-day average is TWD 44.07", refs)]), exact_context)

    def test_2027_percentage_metrics_share_display_and_grounding_encoding(self):
        row = shortlist_row("2027.TW", yoy=.4612, mom=.0597, rel20=.126, rel60=.2047)
        stock = cached_stock("2027.TW")
        stock.earnings_growth = 3.622
        stock.return_on_equity = .1703
        stock.operating_margin = .2111
        stock.debt_to_equity = 54.759
        context = build_shortlist_selected_context(row, stock=stock, generated_at=NOW)
        display = {item["metric"]: item["display_value"] for item in build_verified_evidence(context)}
        self.assertEqual(display["earnings_growth"], "362.20%")
        self.assertEqual(display["return_on_equity"], "17.03%")
        self.assertEqual(display["operating_margin"], "21.11%")
        self.assertEqual(display["debt_to_equity"], "54.76%")
        self.assertEqual(display["revenue_yoy"], "46.12%")
        self.assertEqual(display["revenue_mom"], "5.97%")
        evidence_ids = [
            "current:earnings_growth", "current:return_on_equity", "current:operating_margin",
            "current:debt_to_equity", "radar:2027.TW:revenue_yoy", "radar:2027.TW:revenue_mom",
        ]
        correct = grounded_answer_with_findings(context, [GroundedFinding(
            "Earnings Growth 為 362.20%、ROE 為 17.03%、Operating Margin 為 21.11%、"
            "Debt to Equity 為 54.76%、Revenue YoY 為 46.12%、Revenue MoM 為 5.97%。",
            evidence_ids,
        )])
        validate_grounded_ai_answer(correct, context)
        for incorrect in ("Earnings Growth 為 3.62%。", "Earnings Growth 為 36.22%。", "ROE 為 1703%。", "Debt to Equity 為 5475.9%。"):
            with self.subTest(incorrect=incorrect), self.assertRaises(AINumericGroundingError):
                validate_grounded_ai_answer(
                    grounded_answer_with_findings(context, [GroundedFinding(incorrect, evidence_ids)]), context,
                )

    def test_current_price_aliases_preserve_specific_price_to_book_binding(self):
        for alias in ("目前股價", "Current Price", "current price", "股價", "現價"):
            with self.subTest(alias=alias):
                claims = extract_non_percentage_numeric_claims(f"{alias} is TWD 48.4")
                self.assertEqual([claim.metric for claim in claims], ["current_price"])
        claims = extract_non_percentage_numeric_claims("股價淨值比為 0.61")
        self.assertEqual([claim.metric for claim in claims], ["price_to_book"])

    def test_explicit_market_metric_spans_bind_three_values_without_cross_binding(self):
        cases = (
            "Current Price TWD 75.70, 50-day Average TWD 76.57, 200-day Average TWD 74.36.",
            "目前股價 TWD 75.70，50 日均線 TWD 76.57，200 日均線 TWD 74.36。",
        )
        expected = [
            ("current_price", "75.70"),
            ("fifty_day_average", "76.57"),
            ("two_hundred_day_average", "74.36"),
        ]
        for statement in cases:
            with self.subTest(statement=statement):
                claims = extract_non_percentage_numeric_claims(statement)
                self.assertEqual([(claim.metric, claim.raw_value_text) for claim in claims], expected)

    def test_explicit_cash_and_debt_metric_spans_bind_values_without_swapping(self):
        claims = extract_non_percentage_numeric_claims(
            "Total Cash TWD 1,809,931,008; Total Debt TWD 4,191,009,024."
        )

        self.assertEqual(
            [(claim.metric, claim.raw_value_text) for claim in claims],
            [("total_cash", "1809931008"), ("total_debt", "4191009024")],
        )

    def test_structural_window_numbers_never_claim_metric_values(self):
        claims = extract_non_percentage_numeric_claims(
            "50-day Average TWD 76.57；200 日均線 TWD 74.36；52 週高點 TWD 80.00。"
        )

        self.assertEqual(
            [(claim.metric, claim.raw_value_text) for claim in claims],
            [("fifty_day_average", "76.57"), ("two_hundred_day_average", "74.36"), ("fifty_two_week_high", "80.00")],
        )

    def test_numeric_candidates_reuse_the_actual_evidence_display(self):
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW"), stock=acceptance_stock("2027.TW"), generated_at=NOW,
        )
        displayed = {item["evidence_id"]: item["display_value"] for item in build_verified_evidence(context)}
        candidates = {}
        for item in context.selected_evidence:
            candidate = numeric_evidence_candidate(item.id, item)
            if candidate is not None:
                candidates[item.metric] = candidate
                if item.id in displayed:
                    self.assertEqual(candidate.display_text, displayed[item.id])
        for metric, raw, display in (
            ("trailing_pe", "9.6994", "9.70"),
            ("forward_pe", "8.0862", "8.09"),
            ("price_to_book", "1.508352", "1.51"),
            ("current_price", "48.4", "48.40"),
            ("fifty_day_average", "44.076", "44.08"),
            ("two_hundred_day_average", "39.54675", "39.55"),
        ):
            self.assertEqual(str(candidates[metric].canonical_value), raw)
            self.assertEqual(str(candidates[metric].display_value), display)
        self.assertIsNone(candidates["earnings_growth"].display_value)

    def test_valuation_multiple_display_equivalence_and_metric_aliases_are_fail_closed(self):
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW"), stock=acceptance_stock("2027.TW"), generated_at=NOW,
        )
        refs = ["current:trailing_pe", "current:forward_pe", "current:price_to_book"]
        for text in (
            "Trailing P/E = 9.6994", "Trailing P/E = 9.70", "Forward P/E = 8.0862",
            "Forward P/E = 8.09", "P/B = 1.508352", "P/B = 1.51", "P／B = 1.51",
            "PB = 1.51", "Price to Book = 1.51", "Price-to-Book = 1.51", "股價淨值比 = 1.51",
        ):
            with self.subTest(text=text):
                validate_grounded_ai_answer(grounded_answer_with_findings(context, [GroundedFinding(text, refs)]), context)
        for text, metric in (
            ("Trailing P/E = 9.70", "trailing_pe"), ("Forward P/E = 8.09", "forward_pe"),
            ("P/B = 1.51", "price_to_book"), ("P／B = 1.51", "price_to_book"),
            ("PB = 1.51", "price_to_book"), ("Price to Book = 1.51", "price_to_book"),
            ("股價淨值比 = 1.51", "price_to_book"),
        ):
            with self.subTest(text=text):
                self.assertEqual(extract_non_percentage_numeric_claims(text)[0].metric, metric)
        for text in (
            "Trailing P/E = 10.70", "Forward P/E = 9.09", "P/B = 2.51",
            "Trailing P/E = 1.51", "Forward P/E = 9.70", "P/B = 9.70",
        ):
            with self.subTest(text=text), self.assertRaises(AINumericGroundingError):
                validate_grounded_ai_answer(grounded_answer_with_findings(context, [GroundedFinding(text, refs)]), context)
        with self.assertRaises(AINumericGroundingError):
            validate_grounded_ai_answer(
                grounded_answer_with_findings(context, [GroundedFinding("P/B = 1.51", ["current:trailing_pe"])]), context,
            )

    def test_2027_raw_and_display_claims_pass_but_wrong_metric_currency_and_values_fail(self):
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW"), stock=acceptance_stock("2027.TW"), generated_at=NOW,
        )
        refs = ["current:current_price", "current:fifty_day_average", "current:two_hundred_day_average"]
        for text in (
            "目前股價為 TWD 48.4", "Current Price is TWD 48.40", "股價 TWD 48.4",
            "50-day average is TWD 44.076", "50-day average is TWD 44.08",
            "200-day average is TWD 39.54675", "200-day average is TWD 39.55",
        ):
            with self.subTest(text=text):
                validate_grounded_ai_answer(grounded_answer_with_findings(context, [GroundedFinding(text, refs)]), context)
        for text in (
            "Current Price TWD 50", "50-day average TWD 44.07", "50-day average TWD 45.08",
            "200-day average TWD 40.55", "50-day average TWD 44.1",
            "Current Price USD 48.4", "50-day average USD 44.08", "200-day average USD 39.55",
            "Current Price TWD 44.08", "50-day average TWD 39.55", "200-day average TWD 44.08",
            "TWD 44.08",  # Rounded alternatives require a matching metric, not just a currency.
        ):
            with self.subTest(text=text), self.assertRaises(AINumericGroundingError):
                validate_grounded_ai_answer(grounded_answer_with_findings(context, [GroundedFinding(text, refs)]), context)

    def test_real_style_2027_display_and_large_percentage_pass_stage_one(self):
        result = analyze_research_shortlist(
            [shortlist_row("2027.TW")], stock_loader=acceptance_stock,
            grounded_generator=lambda *, selected_context, **kwargs: acceptance_answer(selected_context),
            generated_at=NOW,
        )
        self.assertEqual(result["stage1_success_count"], 1, result["cards"])
        self.assertEqual(result["provider_call_count"], 1)
        self.assertEqual(result["stage1_format_repair_count"], 0)
        self.assertEqual(result["stage1_policy_regeneration_count"], 0)

    def test_stage_two_minimum_and_failed_card_exclusion_for_all_acceptance_cases(self):
        symbols = ["1216.TW", "1608.TW", "2027.TW"]
        for valid_count in (3, 2, 1, 0):
            with self.subTest(valid_count=valid_count):
                received = []
                def generate(*, selected_context, **kwargs):
                    if selected_context.symbol not in symbols[:valid_count]:
                        raise RuntimeError("fixture failure")
                    return acceptance_answer(selected_context)
                def synthesize(*, cards):
                    received.append([card["symbol"] for card in cards])
                    return valid_synthesis(cards)
                result = analyze_research_shortlist(
                    [shortlist_row(symbol) for symbol in symbols], stock_loader=acceptance_stock,
                    grounded_generator=generate, synthesis_generator=synthesize, generated_at=NOW,
                )
                self.assertEqual(result["stage1_success_count"], valid_count, result["cards"])
                self.assertEqual(result["stage2_excluded_symbols"], symbols[valid_count:])
                self.assertEqual(received, [symbols[:valid_count]] if valid_count >= 2 else [])
                self.assertEqual(result["provider_call_count"], 3 + int(valid_count >= 2))
                self.assertEqual(result["synthesis_skip_reason"] is None, valid_count >= 2)
                self.assertIsNone(result["synthesis_error"])

    def test_synthesis_adapter_rejects_zero_or_one_card_before_provider_call(self):
        context = build_shortlist_selected_context(shortlist_row(), stock=cached_stock(), generated_at=NOW)
        card = normalize_analyst_card(grounded_answer(context), context, shortlist_row())
        for cards in ([], [card]):
            with self.subTest(size=len(cards)), self.assertRaisesRegex(AIAnalystShortlistError, "at least two"):
                generate_shortlist_synthesis(cards=cards, client=object())

    def test_failed_company_cannot_be_reintroduced_in_partial_synthesis(self):
        def generate(*, selected_context, **kwargs):
            if selected_context.symbol == "2027.TW":
                raise RuntimeError("fixture failure")
            return acceptance_answer(selected_context)
        def synthesize(*, cards):
            answer = valid_synthesis(cards)
            answer["priority_deep_dive"] = [{
                "symbol": "2027.TW", "reason": "確認營收來源。", "main_unresolved_risk": "資料時點仍待確認。",
            }]
            return answer
        result = analyze_research_shortlist(
            [shortlist_row(symbol) for symbol in ("1216.TW", "1608.TW", "2027.TW")],
            stock_loader=acceptance_stock, grounded_generator=generate,
            synthesis_generator=synthesize, generated_at=NOW,
        )
        self.assertEqual(result["stage1_success_count"], 2)
        self.assertIsNone(result["synthesis"])
        self.assertEqual(result["synthesis_error"], "STAGE2_RESULT_VALIDATION_ERROR")

    def test_ratio_percentage_encoding_handles_large_and_negative_growth_without_magnitude_heuristics(self):
        for raw_value, expected in ((3.622, 362.2), (-1.25, -125.0), (.15, 15.0)):
            with self.subTest(raw_value=raw_value):
                self.assertEqual(percentage_value_for_metric("earnings_growth", raw_value), expected)
        self.assertEqual(percentage_value_for_metric("return_on_equity", .1703), 17.03)
        self.assertEqual(percentage_value_for_metric("operating_margin", .2111), 21.11)
        self.assertEqual(percentage_value_for_metric("debt_to_equity", 54.759), 54.759)

    def test_failed_company_cannot_enter_stage_two_with_successful_company(self):
        received = []
        def generate(*, selected_context, **_kwargs):
            if selected_context.symbol == "1608.TW":
                raise RuntimeError("provider unavailable")
            return grounded_answer(selected_context)
        result = analyze_research_shortlist(
            [shortlist_row("1216.TW"), shortlist_row("1608.TW"), shortlist_row("2027.TW")],
            stock_loader=lambda symbol: cached_stock(symbol), grounded_generator=generate,
            synthesis_generator=lambda *, cards: received.extend(cards) or valid_synthesis(cards), generated_at=NOW,
        )
        self.assertEqual(len(result["cards"]), 3)
        self.assertEqual([card["symbol"] for card in received], ["1216.TW", "2027.TW"])
        self.assertEqual(result["stage1_success_count"], 2)

    def test_stage_one_prompt_supplies_only_canonical_evidence_ids(self):
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW", yoy=0.4612, mom=0.0597),
            stock=cached_stock("2027.TW"),
            generated_at=NOW,
        )

        model_context = build_analyst_model_context(context)
        question = build_analyst_stage_one_question(model_context)

        self.assertIn("Use only exact CATALOG evidence_id strings", question)
        self.assertIn("observations[n]", question)
        self.assertIn("radar:2027.TW:revenue_yoy|ratio|0.4612", question)
        self.assertIn("radar:2027.TW:revenue_mom|ratio|0.0597", question)
        self.assertNotIn("observations[0]|", question)
        self.assertLessEqual(len(question), MAX_RESEARCH_QUESTION_LENGTH * 0.7)

    def test_evidence_rich_stage_one_context_is_bounded_and_fits_shared_limit(self):
        stock = cached_stock("2027.TW")
        stock.total_cash = 54_780_000_000
        stock.total_debt = 238_070_000_000
        stock.debt_to_equity = 56.0
        stock.free_cash_flow = 2_000_000_000
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=0.126, rel60=0.2047),
            stock=stock,
            generated_at=NOW,
        )
        model_context = build_analyst_model_context(context)
        question = build_analyst_stage_one_question(model_context)

        self.assertLessEqual(len(model_context.selected_evidence), len(ANALYST_MODEL_EVIDENCE_METRICS))
        self.assertTrue(all(item.metric in ANALYST_MODEL_EVIDENCE_METRICS for item in model_context.selected_evidence))
        self.assertLessEqual(len(question), MAX_RESEARCH_QUESTION_LENGTH * 0.7)
        self.assertEqual(model_context.selected_observations, [])
        compact_metrics = {item.metric for item in model_context.selected_evidence}
        self.assertTrue({"revenue_yoy", "revenue_mom"}.issubset(compact_metrics))
        self.assertTrue({"earnings_growth", "return_on_equity", "operating_margin"}.issubset(compact_metrics))
        self.assertTrue({"total_cash", "total_debt", "debt_to_equity"}.issubset(compact_metrics))
        self.assertTrue({"trailing_pe", "price_to_book"}.issubset(compact_metrics))
        self.assertTrue({"current_price", "fifty_day_average", "two_hundred_day_average"}.issubset(compact_metrics))

    def test_2027_category_balanced_context_supports_qualitative_market_and_valuation(self):
        row = shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=None, rel60=None)
        stock = cached_stock("2027.TW")
        stock.current_price = 26.5
        stock.trailing_pe = 9.70
        stock.forward_pe = 8.09
        stock.price_to_book = 1.51
        stock.fifty_day_average = 28.1
        stock.two_hundred_day_average = 30.1
        stock.total_cash = 54_780_000_000
        stock.total_debt = 238_070_000_000
        stock.debt_to_equity = 56.0
        context = build_shortlist_selected_context(row, stock=stock, generated_at=NOW)
        model_context = build_analyst_model_context(context)
        metrics = {item.metric for item in model_context.selected_evidence}

        self.assertTrue({"trailing_pe", "price_to_book"}.issubset(metrics))
        self.assertTrue({"current_price", "fifty_day_average", "two_hundred_day_average"}.issubset(metrics))
        self.assertLessEqual(len(build_analyst_stage_one_question(model_context)), MAX_RESEARCH_QUESTION_LENGTH * 0.7)

        answer = grounded_answer_with_findings(context, [
            GroundedFinding("營運動能改善，但仍需確認成長來源持續性。", [
                "radar:2027.TW:revenue_yoy", "radar:2027.TW:revenue_mom",
            ]),
            GroundedFinding("基本面品質可供後續研究。", ["current:return_on_equity"]),
            GroundedFinding("目前估值可與獲利品質一併解讀。", ["current:trailing_pe"]),
            GroundedFinding("絕對價格趨勢可供市場確認。", [
                "current:current_price", "current:fifty_day_average", "current:two_hundred_day_average",
            ]),
        ])
        answer = GroundedResearchAnswer(
            symbol=answer.symbol,
            question_type=answer.question_type,
            summary=answer.summary,
            findings=answer.findings,
            limitations=answer.limitations,
            missing_information=["相對市場報酬率證據不足。", "缺少 free_cash_flow"],
            next_steps=answer.next_steps,
            metadata=answer.metadata,
        )
        card = normalize_analyst_card(answer, context, row)

        self.assertNotEqual(card["valuation_context"], "目前證據不足。")
        self.assertNotEqual(card["market_confirmation"], "目前證據不足。")
        self.assertIn("20D 相對 0050", card["missing_evidence"])
        self.assertNotIn("相對市場報酬率證據不足。", card["missing_evidence"])
        self.assertIn("自由現金流資料", card["missing_evidence"])

    def test_2027_quality_contract_separates_valuation_market_and_hides_internal_gaps(self):
        row = shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=None, rel60=None)
        stock = cached_stock("2027.TW")
        stock.current_price = 26.5
        stock.trailing_pe = 9.70
        stock.forward_pe = 8.09
        stock.price_to_book = 1.51
        stock.fifty_day_average = 28.1
        stock.two_hundred_day_average = 30.1
        context = build_shortlist_selected_context(row, stock=stock, generated_at=NOW)
        answer = grounded_answer_with_findings(context, [
            GroundedFinding("營運動能提供後續研究線索。", [
                "radar:2027.TW:revenue_yoy", "radar:2027.TW:revenue_mom",
            ]),
            GroundedFinding("基本面品質可供後續研究。", ["current:return_on_equity"]),
            GroundedFinding("目前估值倍數可供初步觀察，但缺少自身歷史區間與同業比較。", [
                "current:trailing_pe", "current:forward_pe", "current:price_to_book",
            ]),
            GroundedFinding("絕對價格趨勢可供市場確認，但相對大盤表現仍待補足。", [
                "current:current_price", "current:fifty_day_average", "current:two_hundred_day_average",
            ]),
        ])
        answer = GroundedResearchAnswer(
            symbol=answer.symbol,
            question_type=answer.question_type,
            summary=answer.summary,
            findings=answer.findings,
            limitations=["global:no_quarterly_or_ttm"],
            missing_information=[
                "context:no_historical_series",
                "missing:current:free_cash_flow",
                "缺少 free_cash_flow",
                "missing:radar:2027.TW:rel_return_20d",
            ],
            next_steps=["確認 missing:radar:2027.TW:rel_return_60d。"],
            metadata=answer.metadata,
        )

        card = normalize_analyst_card(answer, context, row)
        stage_two_card = build_stage_two_cards([card])[0]
        normal_display = json.dumps({
            "opportunity": card["opportunity_interpretation"],
            "fundamental": card["fundamental_quality"],
            "valuation": card["valuation_context"],
            "market": card["market_confirmation"],
            "risks": card["risks"],
            "contradictions": card["contradictions"],
            "missing": card["missing_evidence"],
            "next_checks": card["next_checks"],
            "stage_two_visible": {
                key: value
                for key, value in stage_two_card.items()
                if key not in {"evidence_refs", "verified_evidence_summary"}
            },
        }, ensure_ascii=False)

        self.assertIn("估值倍數", card["valuation_context"])
        self.assertNotIn("市場確認", card["valuation_context"])
        self.assertIn("絕對價格趨勢", card["market_confirmation"])
        self.assertNotIn("估值", card["market_confirmation"])
        self.assertEqual(card["contradictions"], ["目前未發現明確互相衝突的已驗證證據。"])
        self.assertEqual(card["missing_evidence"].count("自由現金流資料"), 1)
        self.assertIn("缺少足夠歷史財務序列", card["risks"])
        self.assertIn("20D 相對 0050", card["missing_evidence"])
        self.assertNotRegex(normal_display, r"(?:missing|context|global):")
        self.assertNotIn("evidence_refs", normal_display)
        self.assertEqual(card["evidence_refs"], [
            "radar:2027.TW:revenue_yoy",
            "radar:2027.TW:revenue_mom",
            "current:return_on_equity",
            "current:trailing_pe",
            "current:forward_pe",
            "current:price_to_book",
            "current:current_price",
            "current:fifty_day_average",
            "current:two_hundred_day_average",
        ])

    def test_standalone_valuation_multiples_cannot_classify_valuation(self):
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW"), stock=cached_stock("2027.TW"), generated_at=NOW,
        )
        for statement in ("估值合理。", "估值非高估。", "估值偏低。", "估值偏高。"):
            answer = grounded_answer_with_findings(context, [GroundedFinding(
                statement,
                ["current:trailing_pe", "current:price_to_book"],
            )])
            with self.assertRaisesRegex(AIAnalystValuationComparatorOverclaimError, "Standalone valuation multiples"):
                normalize_analyst_card(answer, context, shortlist_row("2027.TW"))

    def test_missing_or_incomplete_required_evidence_refs_are_retryable_format_errors(self):
        context = build_shortlist_selected_context(
            shortlist_row("1216.TW", yoy=.0885, mom=.0663, rel20=None, rel60=None),
            stock=Stock(symbol="1216.TW"),
            generated_at=NOW,
        )
        incomplete = grounded_answer_with_findings(context, [GroundedFinding(
            "月營收年增與月增方向一致。", ["radar:1216.TW:revenue_yoy"],
        )])

        with self.assertRaises(AIAnalystMissingRequiredEvidenceRefsError):
            normalize_analyst_card(incomplete, context, {"股票代號": "1216.TW"})

    def test_1216_missing_evidence_refs_get_one_grounded_repair(self):
        row = shortlist_row("1216.TW", yoy=.0885, mom=.0663, rel20=None, rel60=None)
        context = build_shortlist_selected_context(row, stock=Stock(symbol="1216.TW"), generated_at=NOW)
        initial = grounded_answer_with_findings(context, [GroundedFinding(
            "月營收年增與月增方向一致。", [],
        )])
        repaired = grounded_answer_with_findings(context, [GroundedFinding(
            "月營收年增與月增方向一致。",
            ["radar:1216.TW:revenue_yoy", "radar:1216.TW:revenue_mom"],
        )])
        questions, contexts = [], []

        def generate(*, question, selected_context, **_kwargs):
            questions.append(question)
            contexts.append(selected_context)
            return initial if len(questions) == 1 else repaired

        result = analyze_research_shortlist(
            [row], stock_loader=lambda _symbol: Stock(symbol="1216.TW"),
            grounded_generator=generate, generated_at=NOW,
        )

        self.assertEqual(result["stage1_success_count"], 1, result["cards"])
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertEqual(contexts[0], contexts[1])
        self.assertEqual(questions[1], ANALYST_PATCH_QUESTION)
        self.assertLessEqual(len(questions[1]), MAX_RESEARCH_QUESTION_LENGTH)
        self.assertEqual(result["cards"][0]["evidence_refs"], [
            "radar:1216.TW:revenue_yoy", "radar:1216.TW:revenue_mom",
        ])

    def test_second_missing_evidence_refs_failure_is_closed_without_third_generation(self):
        row = shortlist_row("1216.TW", yoy=.0885, mom=.0663, rel20=None, rel60=None)
        context = build_shortlist_selected_context(row, stock=Stock(symbol="1216.TW"), generated_at=NOW)
        missing_refs = grounded_answer_with_findings(context, [GroundedFinding(
            "月營收年增與月增方向一致。", [],
        )])
        calls = []
        result = analyze_research_shortlist(
            [row], stock_loader=lambda _symbol: Stock(symbol="1216.TW"),
            grounded_generator=lambda **kwargs: calls.append(kwargs) or missing_refs,
            generated_at=NOW,
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["cards"][0]["research_priority"], "證據不足")

    def test_valuation_comparator_overclaim_gets_one_neutral_repair_and_preserves_context(self):
        row = shortlist_row("2027.TW", yoy=.4612, mom=.0597, rel20=.126, rel60=.2047)
        full_context = build_shortlist_selected_context(row, stock=acceptance_stock("2027.TW"), generated_at=NOW)
        initial = grounded_answer_with_findings(full_context, [
            GroundedFinding("營收動能可供持續研究。", ["radar:2027.TW:revenue_yoy"]),
            GroundedFinding("目前估值合理且未高估。", ["current:trailing_pe", "current:price_to_book"]),
        ])
        repaired = grounded_answer_with_findings(full_context, [
            GroundedFinding("營收動能可供持續研究。", ["radar:2027.TW:revenue_yoy"]),
            GroundedFinding(
                "目前已有估值倍數可供觀察，但缺少歷史區間與同業比較，因此目前不足以判斷估值高低。",
                ["current:trailing_pe", "current:price_to_book"],
            ),
        ])
        questions, contexts = [], []

        def generate(*, question, selected_context, **kwargs):
            questions.append(question)
            contexts.append(selected_context)
            return initial if len(questions) == 1 else repaired

        result = analyze_research_shortlist(
            [row], stock_loader=acceptance_stock, grounded_generator=generate, generated_at=NOW,
        )

        self.assertEqual(result["stage1_success_count"], 1, result["cards"])
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertEqual(result["stage1_policy_regeneration_count"], 0)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertEqual(len(questions), 2)
        self.assertEqual(contexts[0], contexts[1])
        self.assertEqual(questions[1], ANALYST_PATCH_QUESTION)
        self.assertLessEqual(len(questions[1]), MAX_RESEARCH_QUESTION_LENGTH)
        self.assertNotIn("合理", result["cards"][0]["valuation_context"])
        self.assertIn("缺少歷史區間與同業比較", result["cards"][0]["valuation_context"])

    def test_second_valuation_comparator_overclaim_fails_closed_without_third_generation(self):
        row = shortlist_row("2027.TW")
        context = build_shortlist_selected_context(row, stock=acceptance_stock("2027.TW"), generated_at=NOW)
        overclaim = grounded_answer_with_findings(context, [GroundedFinding(
            "目前估值偏低。", ["current:trailing_pe", "current:price_to_book"],
        )])
        calls = []
        result = analyze_research_shortlist(
            [row], stock_loader=acceptance_stock,
            grounded_generator=lambda **kwargs: calls.append(kwargs) or overclaim,
            generated_at=NOW,
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["cards"][0]["research_priority"], "證據不足")

    def test_valuation_overclaim_repair_question_is_not_used_for_non_retryable_errors(self):
        context = build_analyst_model_context(build_shortlist_selected_context(
            shortlist_row("2027.TW"), stock=acceptance_stock("2027.TW"), generated_at=NOW,
        ))
        answer = grounded_answer_with_findings(context, [GroundedFinding("目前估值合理。", ["current:trailing_pe"])])
        request = build_analyst_repair_request(answer, context)
        self.assertIn("VALUATION_COMPARATOR_OVERCLAIM", request["slots"][0]["reasons"])
        self.assertLessEqual(len(request["question"]), MAX_RESEARCH_QUESTION_LENGTH)

    def test_mixed_valuation_and_market_finding_is_rejected_to_prevent_duplicate_sections(self):
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW"), stock=cached_stock("2027.TW"), generated_at=NOW,
        )
        answer = grounded_answer_with_findings(context, [GroundedFinding(
            "估值與市場位置可一併觀察。",
            ["current:trailing_pe", "current:current_price"],
        )])

        with self.assertRaisesRegex(AIAnalystCardFormatError, "SECTION_ROLE_OVERLAP"):
            normalize_analyst_card(answer, context, shortlist_row("2027.TW"))

    def _assert_sparse_revenue_company(self, symbol, yoy, mom):
        row = shortlist_row(symbol, yoy=yoy, mom=mom, rel20=None, rel60=None)
        full_context = build_shortlist_selected_context(
            row, stock=Stock(symbol=symbol), generated_at=NOW,
        )
        availability = build_analyst_section_availability(full_context)
        self.assertEqual(availability, {
            "opportunity_interpretation": True,
            "fundamental_quality": False,
            "valuation_context": False,
            "market_confirmation": False,
        })
        model_context = build_analyst_model_context(full_context)
        model_missing_ids = {item.id for item in model_context.selected_missing_data}
        self.assertNotIn("missing:current:current_price", model_missing_ids)
        self.assertNotIn("missing:current:gross_margin", model_missing_ids)
        calls = []

        def generator(*, selected_context, **_kwargs):
            calls.append(selected_context.symbol)
            return grounded_answer_with_findings(selected_context, [bound_finding(
                "營收年增與月增方向可供後續研究。",
                [(f"radar:{symbol}:revenue_yoy", f"{yoy:.2%}"), (f"radar:{symbol}:revenue_mom", f"{mom:.2%}")],
            )])

        result = analyze_research_shortlist(
            [row],
            stock_loader=lambda _symbol: Stock(symbol=symbol),
            grounded_generator=generator,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )
        card = result["cards"][0]

        self.assertEqual(calls, [symbol])
        self.assertEqual(result["stage1_success_count"], 1)
        self.assertEqual(result["stage1_format_repair_count"], 0)
        self.assertEqual(card["fundamental_quality"], "目前證據不足。")
        self.assertEqual(card["valuation_context"], "目前證據不足。")
        self.assertEqual(card["market_confirmation"], "目前證據不足。")
        self.assertIn("營收年增與月增方向可供後續研究。", card["opportunity_interpretation"])

    def test_1216_sparse_exact_grounded_revenue_numbers_produce_valid_card(self):
        self._assert_sparse_revenue_company("1216.TW", 0.0885, 0.0663)

    def test_1216_supplied_missing_context_id_supports_gap_statement_only(self):
        row = shortlist_row("1216.TW", yoy=0.0885, mom=0.0663, rel20=None, rel60=None)
        context = build_shortlist_selected_context(
            row, stock=Stock(symbol="1216.TW"), generated_at=NOW,
        )
        supplied_missing_ids = {item.id for item in context.selected_missing_data}
        self.assertIn("missing:current:gross_margin", supplied_missing_ids)

        answer = grounded_answer_with_findings(context, [
            GroundedFinding(
                "Revenue YoY 為 8.85%，Revenue MoM 為 6.63%。",
                ["radar:1216.TW:revenue_yoy", "radar:1216.TW:revenue_mom"],
            ),
        ])
        answer = GroundedResearchAnswer(
            symbol=answer.symbol,
            question_type=answer.question_type,
            summary=answer.summary,
            findings=answer.findings,
            limitations=answer.limitations,
            missing_information=["目前缺少毛利率等基本面證據：missing:current:gross_margin。"],
            next_steps=["確認並補足 missing:current:gross_margin。"],
            metadata=answer.metadata,
        )

        validate_grounded_ai_answer(answer, context)
        card = normalize_analyst_card(answer, context, row)

        self.assertIn("毛利率資料", card["missing_evidence"])
        self.assertFalse(any(item.startswith("missing:") for item in card["missing_evidence"]))

        invented = grounded_answer_with_findings(context, [GroundedFinding(
            "目前缺少額外基本面證據。",
            ["missing:current:invented_metric"],
        )])
        with self.assertRaisesRegex(AIGroundingError, "Unknown evidence ID"):
            validate_grounded_ai_answer(invented, context)

        factual_misuse = grounded_answer_with_findings(context, [GroundedFinding(
            "毛利率表現穩健。",
            ["missing:current:gross_margin"],
        )])
        with self.assertRaisesRegex(AIMissingContextRoleMisuseError, "MISSING_CONTEXT_ROLE_MISUSE"):
            validate_grounded_ai_answer(factual_misuse, context)

    def test_1608_sparse_exact_grounded_revenue_numbers_produce_valid_card(self):
        self._assert_sparse_revenue_company("1608.TW", 0.4267, 0.1496)

    def test_1216_invented_missing_citation_is_not_repairable(self):
        row = shortlist_row("1216.TW", yoy=0.0885, mom=0.0663, rel20=None, rel60=None)
        context = build_shortlist_selected_context(row, stock=Stock(symbol="1216.TW"), generated_at=NOW)
        initial = grounded_answer_with_findings(context, [
            GroundedFinding("Revenue YoY 為 8.85%，Revenue MoM 為 6.63%。", [
                "radar:1216.TW:revenue_yoy", "radar:1216.TW:revenue_mom",
            ]),
            GroundedFinding("歷史趨勢已形成正向確認。", ["missing:historical:series"]),
        ])
        questions = []

        def generator(*, question, **_kwargs):
            questions.append(question)
            return initial

        result = analyze_research_shortlist(
            [row],
            stock_loader=lambda _symbol: Stock(symbol="1216.TW"),
            grounded_generator=generator,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )

        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["stage1_format_repair_count"], 0)
        self.assertEqual(result["stage1_policy_regeneration_count"], 0)
        self.assertEqual(result["provider_call_count"], 1)
        self.assertEqual(len(questions), 1)
        self.assertIn("Unknown evidence ID", result["cards"][0]["missing_evidence"][0])

    def test_1608_invented_missing_citation_is_not_repairable(self):
        row = shortlist_row("1608.TW", yoy=0.4267, mom=0.1496, rel20=None, rel60=None)
        context = build_shortlist_selected_context(row, stock=Stock(symbol="1608.TW"), generated_at=NOW)
        self.assertIn("missing:historical:series", {item.id for item in context.selected_missing_data})
        initial = grounded_answer_with_findings(context, [
            GroundedFinding("Revenue YoY 為 42.67%，Revenue MoM 為 14.96%。", [
                "radar:1608.TW:revenue_yoy", "radar:1608.TW:revenue_mom",
            ]),
            GroundedFinding("歷史趨勢已形成正向確認。", ["missing:historical:series"]),
        ])
        calls = []
        result = analyze_research_shortlist(
            [row],
            stock_loader=lambda _symbol: Stock(symbol="1608.TW"),
            grounded_generator=lambda **_kwargs: calls.append("call") or initial,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )

        self.assertEqual(calls, ["call"])
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["stage1_format_repair_count"], 0)
        self.assertEqual(result["stage1_policy_regeneration_count"], 0)
        self.assertIn("Unknown evidence ID", result["cards"][0]["missing_evidence"][0])

    def test_2027_compact_currency_rounding_is_metric_and_currency_bound(self):
        stock = cached_stock("2027.TW")
        stock.total_cash = 16_097_614_848
        stock.total_debt = 51_051_364_352
        stock.debt_to_equity = 54.759
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW"), stock=stock, generated_at=NOW,
        )
        evidence_ids = ["current:total_cash", "current:total_debt"]
        valid = grounded_answer_with_findings(context, [GroundedFinding(
            "Cash: TWD 16.1B；Debt: TWD 51.05B。",
            evidence_ids,
        )])

        validate_grounded_ai_answer(valid, context)

        real_style = grounded_answer_with_findings(context, [GroundedFinding(
            "Total Cash TWD 16.1B；Total Debt TWD 51.05B；Debt to Equity 54.759。",
            ["current:total_cash", "current:total_debt", "current:debt_to_equity"],
        )])
        validate_grounded_ai_answer(real_style, context)

        parsed = extract_non_percentage_numeric_claims(
            "Cash: TWD 16.1B；Total Debt: TWD 51.05B；Debt to Equity: 54.759。"
        )
        self.assertEqual(
            [(claim.metric, claim.raw_value_text, claim.scale, claim.decimal_places) for claim in parsed],
            [
                ("total_cash", "16.1", "B", 1),
                ("total_debt", "51.05", "B", 2),
                ("debt_to_equity", "54.759", None, 3),
            ],
        )

        for statement in (
            "Cash: TWD 18.1B。",
            "Debt: TWD 55.05B。",
            "Cash: USD 16.1B。",
            "Cash: TWD 51.05B。",
            "Debt: TWD 16.1B。",
        ):
            invalid = grounded_answer_with_findings(context, [GroundedFinding(statement, evidence_ids)])
            with self.subTest(statement=statement), self.assertRaises(AINumericGroundingError):
                validate_grounded_ai_answer(invalid, context)

    def test_specific_metric_aliases_take_precedence_over_contained_generic_aliases(self):
        claims = extract_non_percentage_numeric_claims(
            "Debt to Equity 54.759；Total Debt TWD 51.05B；"
            "Operating Cash Flow TWD 5.00B；Cash TWD 16.1B。"
        )

        self.assertEqual(
            [claim.metric for claim in claims],
            ["debt_to_equity", "total_debt", "operating_cash_flow", "total_cash"],
        )

    def test_section_overlap_cannot_split_findings_or_change_locked_refs(self):
        row = shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=None, rel60=None)
        context = build_shortlist_selected_context(row, stock=cached_stock("2027.TW"), generated_at=NOW)
        initial = grounded_answer_with_findings(context, [GroundedFinding(
            "估值與市場位置可一併觀察。",
            ["current:trailing_pe", "current:current_price"],
        )])
        repaired = grounded_answer_with_findings(context, [
            GroundedFinding(
                "目前估值倍數可供初步觀察，但缺少歷史與同業比較。",
                ["current:trailing_pe", "current:price_to_book"],
            ),
            GroundedFinding(
                "絕對價格趨勢可供市場確認。",
                ["current:current_price", "current:fifty_day_average", "current:two_hundred_day_average"],
            ),
        ])
        questions = []

        def generator(*, question, **_kwargs):
            questions.append(question)
            return initial if len(questions) == 1 else repaired

        result = analyze_research_shortlist(
            [row],
            stock_loader=lambda _symbol: cached_stock("2027.TW"),
            grounded_generator=generator,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )
        card = result["cards"][0]

        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[1], ANALYST_PATCH_QUESTION)
        self.assertLessEqual(len(questions[1]), MAX_RESEARCH_QUESTION_LENGTH)
        self.assertIn("locked fields", card["missing_evidence"][0])

    def test_2027_invalid_second_format_response_fails_after_one_repair(self):
        row = shortlist_row("2027.TW")
        context = build_shortlist_selected_context(row, stock=cached_stock("2027.TW"), generated_at=NOW)
        mixed = grounded_answer_with_findings(context, [GroundedFinding(
            "估值與市場位置可一併觀察。",
            ["current:trailing_pe", "current:current_price"],
        )])
        calls = []

        result = analyze_research_shortlist(
            [row],
            stock_loader=lambda _symbol: cached_stock("2027.TW"),
            grounded_generator=lambda **_kwargs: calls.append("call") or mixed,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )

        self.assertEqual(calls, ["call", "call"])
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertEqual(result["cards"][0]["research_priority"], "證據不足")

    def test_grounding_errors_never_trigger_regeneration(self):
        row = shortlist_row("2027.TW", yoy=0.4612)
        context = build_shortlist_selected_context(row, stock=cached_stock("2027.TW"), generated_at=NOW)
        cases = (
            grounded_answer_with_findings(context, [GroundedFinding(
                "營收方向提供研究線索。", ["observations[0]"],
            )]),
            GroundedResearchAnswer(
                symbol=context.symbol,
                question_type=context.question_type.value,
                summary="研究優先度：值得觀察\n目前證據供初步研究使用。",
                findings=[GroundedFinding(
                    "營收方向提供研究線索。", ["radar:2027.TW:revenue_yoy"],
                )],
                limitations=[],
                missing_information=["目前缺少資料：missing:current:invented_metric。"],
                next_steps=["確認最新公司揭露資料。"],
                metadata=AIResponseMetadata(
                    model="test",
                    response_id="test-response",
                    generated_at=NOW,
                    question_type=context.question_type.value,
                ),
            ),
        )
        for answer in cases:
            with self.subTest(statement=answer.findings[0].statement):
                calls = []
                result = analyze_research_shortlist(
                    [row],
                    stock_loader=lambda _symbol: cached_stock("2027.TW"),
                    grounded_generator=lambda **_kwargs: calls.append("call") or answer,
                    synthesis_generator=lambda *, cards: valid_synthesis(cards),
                    generated_at=NOW,
                )
                self.assertEqual(calls, ["call"])
                self.assertEqual(result["stage1_success_count"], 0)
                self.assertEqual(result["stage1_format_repair_count"], 0)
                self.assertEqual(result["stage1_policy_regeneration_count"], 0)
                self.assertEqual(result["provider_call_count"], 1)

    def test_investment_safety_failure_exposes_only_exact_diagnostic_metadata(self):
        row = shortlist_row("2027.TW", yoy=0.4612)
        context = build_shortlist_selected_context(row, stock=cached_stock("2027.TW"), generated_at=NOW)
        unsafe = grounded_answer_with_findings(context, [GroundedFinding(
            "目前看多，建議買進。", ["radar:2027.TW:revenue_yoy"],
        )])
        result = analyze_research_shortlist(
            [row],
            stock_loader=lambda _symbol: cached_stock("2027.TW"),
            grounded_generator=lambda **_kwargs: unsafe,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )

        failure = result["cards"][0]["missing_evidence"][0]
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["stage1_format_repair_count"], 0)
        self.assertIn("matched_rule=BUY_ACTION", failure)
        self.assertIn("matched_term=買進", failure)
        self.assertIn("field=findings", failure)
        self.assertNotIn("目前看多", failure)

    def test_rich_2027_verified_evidence_has_unique_fixed_section_ownership(self):
        stock = cached_stock("2027.TW")
        stock.trailing_eps = 2.5
        stock.total_cash = 54_780_000_000
        stock.total_debt = 238_070_000_000
        stock.debt_to_equity = 56.0
        stock.operating_cash_flow = 5_000_000_000
        stock.free_cash_flow = 2_000_000_000
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW"), stock=stock, generated_at=NOW,
        )
        rows = build_verified_evidence(context)
        metrics = [item["metric"] for item in rows]
        section_by_metric = {item["metric"]: item["section"] for item in rows}

        self.assertEqual(len(metrics), len(set(metrics)))
        for metric in (
            "net_margin", "trailing_eps", "total_cash", "total_debt", "debt_to_equity",
            "operating_cash_flow", "free_cash_flow",
        ):
            self.assertEqual(metrics.count(metric), 1)
            self.assertEqual(section_by_metric[metric], "基本面")
        for metric in ("trailing_pe", "forward_pe", "price_to_book"):
            self.assertEqual(section_by_metric[metric], "估值")
        for metric in ("current_price", "fifty_day_average", "two_hundred_day_average"):
            self.assertEqual(section_by_metric[metric], "市場")

    def test_noncanonical_evidence_references_fail_closed_without_mapping(self):
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW", yoy=0.4612, mom=0.0597),
            stock=cached_stock("2027.TW"),
            generated_at=NOW,
        )
        for invalid_reference in ("observations[0]", "evidence[0]", "revenue_yoy"):
            answer = grounded_answer_with_findings(context, [GroundedFinding(
                "月營收年增與月增方向一致。",
                [invalid_reference],
            )])
            with self.assertRaisesRegex(AIGroundingError, f"Unknown evidence ID cited: {re.escape(invalid_reference)}"):
                validate_grounded_ai_answer(answer, context)

        failed = analyze_research_shortlist(
            [shortlist_row("2027.TW", yoy=0.4612, mom=0.0597)],
            stock_loader=lambda _symbol: cached_stock("2027.TW"),
            grounded_generator=lambda **_kwargs: grounded_answer_with_findings(context, [GroundedFinding(
                "月營收年增與月增方向一致。",
                ["observations[0]"],
            )]),
            generated_at=NOW,
        )
        self.assertEqual(failed["stage1_success_count"], 0)
        self.assertEqual(failed["cards"][0]["research_priority"], "證據不足")
        self.assertIn("Unknown evidence ID cited: observations[0]", failed["cards"][0]["missing_evidence"][0])

    def test_research_guidance_and_research_priorities_are_allowed(self):
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW", yoy=0.4612, mom=0.0597),
            stock=cached_stock("2027.TW"),
            generated_at=NOW,
        )
        for priority in ("值得觀察", "優先深入研究"):
            answer = grounded_answer(context, priority)
            answer = GroundedResearchAnswer(
                symbol=answer.symbol,
                question_type=answer.question_type,
                summary=answer.summary,
                findings=answer.findings,
                limitations=answer.limitations,
                missing_information=answer.missing_information,
                next_steps=["下一步需確認營收成長來源。", "需要驗證現金流與負債結構。"],
                metadata=answer.metadata,
            )
            validate_grounded_ai_answer(answer, context)
            self.assertEqual(normalize_analyst_card(answer, context, shortlist_row("2027.TW"))["research_priority"], priority)

    def test_investment_action_recommendations_remain_rejected(self):
        context = build_shortlist_selected_context(shortlist_row(), stock=cached_stock(), generated_at=NOW)
        base = grounded_answer(context)
        for prohibited in (
            "建議買進。",
            "建議持有。",
            "可以加碼。",
            "目標價為 60 元。",
            "預期上漲 20%。",
        ):
            answer = GroundedResearchAnswer(
                symbol=base.symbol,
                question_type=base.question_type,
                summary=base.summary,
                findings=base.findings,
                limitations=base.limitations,
                missing_information=base.missing_information,
                next_steps=[prohibited],
                metadata=base.metadata,
            )
            with self.assertRaisesRegex(AIGroundingError, "forbidden recommendation"):
                validate_grounded_ai_answer(answer, context)

    def test_forbidden_recommendation_diagnostic_identifies_rule_and_field(self):
        context = build_shortlist_selected_context(shortlist_row(), stock=cached_stock(), generated_at=NOW)
        base = grounded_answer(context)
        cases = (
            (
                GroundedResearchAnswer(
                    symbol=base.symbol,
                    question_type=base.question_type,
                    summary="研究優先度：值得觀察\n建議買進。",
                    findings=base.findings,
                    limitations=base.limitations,
                    missing_information=base.missing_information,
                    next_steps=base.next_steps,
                    metadata=base.metadata,
                ),
                "matched_rule=BUY_ACTION; matched_term=買進; field=summary",
            ),
            (
                GroundedResearchAnswer(
                    symbol=base.symbol,
                    question_type=base.question_type,
                    summary=base.summary,
                    findings=[GroundedFinding("目前看多。", [base.findings[0].evidence_ids[0]])],
                    limitations=base.limitations,
                    missing_information=base.missing_information,
                    next_steps=base.next_steps,
                    metadata=base.metadata,
                ),
                "matched_rule=BULLISH_CALL; matched_term=看多; field=findings",
            ),
            (
                GroundedResearchAnswer(
                    symbol=base.symbol,
                    question_type=base.question_type,
                    summary=base.summary,
                    findings=base.findings,
                    limitations=base.limitations,
                    missing_information=base.missing_information,
                    next_steps=["可以加碼。"],
                    metadata=base.metadata,
                ),
                "matched_rule=ADD_POSITION; matched_term=加碼; field=next_steps",
            ),
        )

        for answer, expected_diagnostic in cases:
            with self.assertRaisesRegex(AIGroundingError, re.escape(expected_diagnostic)):
                validate_grounded_ai_answer(answer, context)

    def test_descriptive_return_language_is_allowed_but_forward_return_is_rejected(self):
        context = build_shortlist_selected_context(shortlist_row(), stock=cached_stock(), generated_at=NOW)
        base = grounded_answer(context)
        for descriptive in (
            "目前缺少相對報酬率資料。",
            "相對市場報酬率證據不足。",
            "歷史報酬率僅供研究參考。",
            "0050 相對報酬目前缺少完整證據。",
            "需要補足相對市場表現證據。",
        ):
            answer = GroundedResearchAnswer(
                symbol=base.symbol,
                question_type=base.question_type,
                summary=base.summary,
                findings=base.findings,
                limitations=base.limitations,
                missing_information=[descriptive],
                next_steps=base.next_steps,
                metadata=base.metadata,
            )
            validate_grounded_ai_answer(answer, context)

        for forward, term in (
            ("預期報酬率為 20%。", "預期報酬率"),
            ("預估報酬率約 15%。", "預估報酬率"),
            ("目標報酬率為 10%。", "目標報酬率"),
            ("未來報酬率可達 25%。", "未來報酬率"),
            ("預期上漲 20%。", "預期上漲"),
            ("expected return is 15%.", "expected_return"),
        ):
            answer = GroundedResearchAnswer(
                symbol=base.symbol,
                question_type=base.question_type,
                summary=base.summary,
                findings=[GroundedFinding(forward, [base.findings[0].evidence_ids[0]])],
                limitations=base.limitations,
                missing_information=base.missing_information,
                next_steps=base.next_steps,
                metadata=base.metadata,
            )
            expected = f"matched_rule=EXPECTED_RETURN; matched_term={term}; field=findings"
            with self.assertRaisesRegex(AIGroundingError, re.escape(expected)):
                validate_grounded_ai_answer(answer, context)

    def test_2027_qualitative_research_guidance_card_is_valid(self):
        row = shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=None, rel60=None)
        context = build_shortlist_selected_context(row, stock=cached_stock("2027.TW"), generated_at=NOW)
        answer = grounded_answer_with_findings(context, [
            GroundedFinding(
                "營運動能改善，但仍需確認成長來源的持續性。",
                ["radar:2027.TW:revenue_yoy", "radar:2027.TW:revenue_mom"],
            ),
            GroundedFinding("獲利能力改善，仍需確認現金流品質。", ["current:return_on_equity"]),
            GroundedFinding("目前估值需要與獲利品質一併解讀。", ["current:trailing_pe"]),
            GroundedFinding("市場位置仍需持續確認。", ["current:current_price"]),
        ])
        answer = GroundedResearchAnswer(
            symbol=answer.symbol,
            question_type=answer.question_type,
            summary=answer.summary,
            findings=answer.findings,
            limitations=["景氣循環與負債結構仍需追蹤。"],
            missing_information=["缺少完整相對市場確認與現金流資料。"],
            next_steps=["確認營收成長來源與景氣敏感度（radar:2027.TW:revenue_yoy）。"],
            metadata=answer.metadata,
        )

        validate_grounded_ai_answer(answer, context)
        card = normalize_analyst_card(answer, context, row)

        self.assertEqual(card["research_priority"], "值得觀察")
        self.assertIn("確認營收成長來源與景氣敏感度（Revenue YoY 資料）。", card["next_checks"])
        self.assertIn("補足現金流資料", card["next_checks"])

    def test_2027_exact_canonical_references_succeed_and_missing_evidence_is_allowed(self):
        row = shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=None, rel60=None)
        result = analyze_research_shortlist(
            [row],
            stock_loader=lambda _symbol: cached_stock("2027.TW"),
            grounded_generator=lambda *, selected_context, **_kwargs: GroundedResearchAnswer(
                symbol=selected_context.symbol,
                question_type=selected_context.question_type.value,
                summary="研究優先度：值得觀察\n目前證據供初步研究使用。",
                findings=[GroundedFinding(
                    "月營收年增與月增方向一致。",
                    ["radar:2027.TW:revenue_yoy", "radar:2027.TW:revenue_mom"],
                )],
                limitations=[],
                missing_information=["相對市場資料不足，待後續確認。"],
                next_steps=["確認最新公司揭露資料。"],
                metadata=AIResponseMetadata(
                    model="test",
                    response_id="test-response",
                    generated_at=NOW,
                    question_type=selected_context.question_type.value,
                ),
            ),
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )

        self.assertEqual(result["stage1_success_count"], 1)
        self.assertEqual(result["cards"][0]["research_priority"], "值得觀察")
        self.assertIn("20D 相對 0050", result["cards"][0]["missing_evidence"])
        self.assertNotIn("相對市場資料不足，待後續確認。", result["cards"][0]["missing_evidence"])

    def test_company_contexts_are_isolated(self):
        first = build_shortlist_selected_context(shortlist_row("2330.TW"), stock=cached_stock("2330.TW"), generated_at=NOW)
        second = build_shortlist_selected_context(shortlist_row("2454.TW"), stock=cached_stock("2454.TW"), generated_at=NOW)

        self.assertTrue(all("2454.TW" not in item.id for item in first.selected_evidence))
        self.assertTrue(all("2330.TW" not in item.id for item in second.selected_evidence))
        self.assertEqual(first.symbol, "2330.TW")
        self.assertEqual(second.symbol, "2454.TW")
        metrics = {item.metric for item in first.selected_evidence}
        self.assertIn("long_term_research_availability", metrics)
        self.assertIn("swing_research_availability", metrics)

    def test_card_schema_and_priority_are_strict(self):
        context = build_shortlist_selected_context(shortlist_row(), stock=cached_stock(), generated_at=NOW)
        card = normalize_analyst_card(grounded_answer(context, "優先深入研究"), context, shortlist_row())

        validate_analyst_card(card)
        self.assertEqual(card["research_priority"], "優先深入研究")
        card["research_priority"] = "最高分"
        with self.assertRaises(AIAnalystShortlistError):
            validate_analyst_card(card)

    def test_missing_evidence_remains_explicit(self):
        row = shortlist_row(yoy=None, rel20=None)
        context = build_shortlist_selected_context(row, stock=Stock(symbol="2330.TW"), generated_at=NOW)
        card = normalize_analyst_card(grounded_answer(context), context, row)

        self.assertIn("Revenue YoY 資料", card["missing_evidence"])
        self.assertIn("20D 相對 0050", card["missing_evidence"])

    def test_missing_evidence_display_hides_internal_ids_and_deduplicates(self):
        context = build_shortlist_selected_context(shortlist_row(), stock=cached_stock(), generated_at=NOW)
        answer = grounded_answer(context)
        answer = GroundedResearchAnswer(
            symbol=answer.symbol,
            question_type=answer.question_type,
            summary=answer.summary,
            findings=answer.findings,
            limitations=answer.limitations,
            missing_information=["missing:current:free_cash_flow", "缺少 free_cash_flow"],
            next_steps=answer.next_steps,
            metadata=answer.metadata,
        )

        card = normalize_analyst_card(answer, context, shortlist_row())

        self.assertEqual(card["missing_evidence"].count("自由現金流資料"), 1)
        self.assertFalse(any(item.startswith("missing:") for item in card["missing_evidence"]))

    def test_canonical_radar_resolution_is_independent_of_shortlist_entry_path(self):
        radar_row = shortlist_row("2027.TW", yoy=0.01, mom=0.01, rel20=0.01, rel60=0.01)
        candidate_row = {"股票代號": "2027.TW", "公司名稱": "大成鋼", "產業": "鋼鐵業"}
        radar_context = build_shortlist_selected_context(
            radar_row,
            stock=cached_stock("2027.TW"),
            generated_at=NOW,
            radar_evidence_resolver=canonical_2027_radar,
        )
        candidate_context = build_shortlist_selected_context(
            candidate_row,
            stock=cached_stock("2027.TW"),
            generated_at=NOW,
            radar_evidence_resolver=canonical_2027_radar,
        )

        canonical_metrics = {
            "revenue_yoy", "revenue_mom", "rel_return_20d", "rel_return_60d",
        }
        radar_values = {
            item.metric: item.value
            for item in radar_context.selected_evidence
            if item.metric in canonical_metrics
        }
        candidate_values = {
            item.metric: item.value
            for item in candidate_context.selected_evidence
            if item.metric in canonical_metrics
        }

        self.assertEqual(radar_values, candidate_values)
        self.assertEqual(radar_values["revenue_yoy"], 0.4612)
        self.assertEqual(radar_values["revenue_mom"], 0.0597)
        self.assertEqual(radar_values["rel_return_20d"], 0.1260)
        self.assertEqual(radar_values["rel_return_60d"], 0.2047)

        result = analyze_research_shortlist(
            [candidate_row],
            stock_loader=lambda _symbol: cached_stock("2027.TW"),
            grounded_generator=lambda *, selected_context, **_kwargs: grounded_answer(selected_context),
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
            radar_evidence_resolver=canonical_2027_radar,
        )
        analyst_evidence = {
            item["metric"]: item["display_value"]
            for item in result["cards"][0]["verified_evidence"]
        }
        self.assertEqual(result["stage1_success_count"], 1)
        self.assertEqual(analyst_evidence["revenue_yoy"], "46.12%")
        self.assertEqual(analyst_evidence["rel_return_60d"], "20.47%")

    def test_canonical_radar_period_and_metric_missing_states_are_independent(self):
        def resolver(symbol):
            evidence = canonical_2027_radar(symbol)
            evidence["relative_return_20d"] = None
            return evidence

        context = build_shortlist_selected_context(
            {"股票代號": "2027.TW", "公司名稱": "大成鋼", "產業": "鋼鐵業"},
            stock=cached_stock("2027.TW"),
            generated_at=NOW,
            radar_evidence_resolver=resolver,
        )
        card = normalize_analyst_card(
            grounded_answer(context),
            context,
            {"股票代號": "2027.TW", "公司名稱": "大成鋼"},
        )
        evidence = {item["metric"]: item["display_value"] for item in card["verified_evidence"]}

        self.assertEqual(evidence["revenue_period"], "資料不足")
        self.assertEqual(evidence["revenue_yoy"], "46.12%")
        self.assertEqual(evidence["revenue_mom"], "5.97%")
        self.assertEqual(evidence["rel_return_20d"], "資料不足")
        self.assertEqual(evidence["rel_return_60d"], "20.47%")

    def test_absent_canonical_radar_does_not_fall_back_to_shortlist_fields(self):
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=0.1260, rel60=0.2047),
            stock=cached_stock("2027.TW"),
            generated_at=NOW,
            radar_evidence_resolver=lambda _symbol: None,
        )
        card = normalize_analyst_card(
            grounded_answer(context),
            context,
            {"股票代號": "2027.TW", "公司名稱": "大成鋼"},
        )
        evidence = {item["metric"]: item["display_value"] for item in card["verified_evidence"]}

        self.assertEqual(evidence["revenue_yoy"], "資料不足")
        self.assertEqual(evidence["revenue_mom"], "資料不足")
        self.assertEqual(evidence["rel_return_20d"], "資料不足")
        self.assertEqual(evidence["rel_return_60d"], "資料不足")

    def test_2027_deterministic_evidence_renders_values_without_numeric_ai_prose(self):
        row = shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=0.1260, rel60=0.2047)
        stock = cached_stock("2027.TW")
        stock.fifty_day_average = 28.10
        stock.two_hundred_day_average = 30.10
        context = build_shortlist_selected_context(row, stock=stock, generated_at=NOW)
        answer = grounded_answer_with_findings(context, [GroundedFinding(
            "月營收年增與月增方向一致。",
            ["radar:2027.TW:revenue_yoy", "radar:2027.TW:revenue_mom"],
        ), GroundedFinding(
            "短中期相對市場表現偏強。",
            ["radar:2027.TW:rel_return_20d", "radar:2027.TW:rel_return_60d"],
        )])

        card = normalize_analyst_card(answer, context, row)
        evidence = {item["metric"]: item["display_value"] for item in card["verified_evidence"]}

        self.assertEqual(evidence["revenue_yoy"], "46.12%")
        self.assertEqual(evidence["revenue_mom"], "5.97%")
        self.assertEqual(evidence["rel_return_20d"], "12.60%")
        self.assertEqual(evidence["rel_return_60d"], "20.47%")
        self.assertEqual(evidence["fifty_day_average"], "TWD 28.10")
        self.assertEqual(evidence["two_hundred_day_average"], "TWD 30.10")
        self.assertNotRegex(json.dumps(card["opportunity_interpretation"], ensure_ascii=False), r"46\.12|5\.97|12\.60|20\.47")

    def test_missing_0050_evidence_is_unavailable_but_stage_one_succeeds(self):
        row = shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=None, rel60=None)
        context = build_shortlist_selected_context(row, stock=cached_stock("2027.TW"), generated_at=NOW)
        answer = grounded_answer_with_findings(context, [GroundedFinding(
            "月營收年增與月增方向一致。",
            ["radar:2027.TW:revenue_yoy", "radar:2027.TW:revenue_mom"],
        )])

        result = analyze_research_shortlist(
            [row],
            stock_loader=lambda _symbol: cached_stock("2027.TW"),
            grounded_generator=lambda **_kwargs: answer,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )
        evidence = {item["metric"]: item for item in result["cards"][0]["verified_evidence"]}

        self.assertEqual(result["stage1_success_count"], 1)
        self.assertEqual(evidence["rel_return_20d"]["display_value"], "資料不足")
        self.assertEqual(evidence["rel_return_60d"]["display_value"], "資料不足")

    def test_qualitative_comparison_requires_all_supporting_references(self):
        row = shortlist_row("2027.TW")
        stock = cached_stock("2027.TW")
        stock.total_debt = 200.0
        stock.total_cash = 100.0
        context = build_shortlist_selected_context(row, stock=stock, generated_at=NOW)

        valid = grounded_answer_with_findings(context, [GroundedFinding(
            "負債高於現金，需確認現金流覆蓋與債務結構。",
            ["current:total_debt", "current:total_cash"],
        )])
        normalize_analyst_card(valid, context, row)

        unsupported = grounded_answer_with_findings(context, [GroundedFinding(
            "負債高於現金，需確認現金流覆蓋與債務結構。",
            ["current:total_debt"],
        )])
        with self.assertRaisesRegex(AIAnalystShortlistError, "required evidence references"):
            normalize_analyst_card(unsupported, context, row)

        unsupported_revenue = grounded_answer_with_findings(context, [GroundedFinding(
            "月營收年增與月增方向一致。",
            ["radar:2027.TW:revenue_yoy"],
        )])
        with self.assertRaisesRegex(AIAnalystShortlistError, "required evidence references"):
            normalize_analyst_card(unsupported_revenue, context, row)

        unsupported_roe = grounded_answer_with_findings(context, [GroundedFinding(
            "ROE 顯示資本效率仍需確認。",
            ["current:trailing_pe"],
        )])
        with self.assertRaisesRegex(AIAnalystShortlistError, "required evidence references"):
            normalize_analyst_card(unsupported_roe, context, row)

    def test_financial_numeric_narrative_requires_qualitative_repair(self):
        row = shortlist_row("2027.TW", mom=0.0597)
        context = build_shortlist_selected_context(row, stock=cached_stock("2027.TW"), generated_at=NOW)
        answer = grounded_answer_with_findings(context, [bound_finding(
            "Revenue MoM 為 50%。",
            [("radar:2027.TW:revenue_mom", "50%")],
        )])

        result = analyze_research_shortlist(
            [row],
            stock_loader=lambda _symbol: cached_stock("2027.TW"),
            grounded_generator=lambda **_kwargs: answer,
            repair_generator=lambda **_kwargs: {"patches": [{
                "slot_id": "findings:0", "rewritten_text": "營收動能仍需持續確認。",
            }]},
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )

        self.assertEqual(result["stage1_success_count"], 1, result["cards"])
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertEqual(result["provider_call_count"], 2)

        supported_but_repeated = grounded_answer_with_findings(context, [GroundedFinding(
            "Revenue MoM 為 5.97%。",
            ["radar:2027.TW:revenue_mom"],
        )])
        with self.assertRaises(AIAnalystFinancialNumericNarrativeError):
            validate_analyst_grounded_answer(supported_but_repeated, context)
        validate_grounded_ai_answer(supported_but_repeated, context)

    def test_2027_radar_percentages_are_grounded_by_shared_validator(self):
        row = shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=0.1260, rel60=0.2047)
        context = build_shortlist_selected_context(row, stock=cached_stock("2027.TW"), generated_at=NOW)
        evidence_ids = [
            "radar:2027.TW:revenue_yoy",
            "radar:2027.TW:revenue_mom",
            "radar:2027.TW:rel_return_20d",
            "radar:2027.TW:rel_return_60d",
        ]
        answer = grounded_answer_with_findings(context, [GroundedFinding(
            "Revenue YoY 為 46.12%、Revenue MoM 為 5.97%、"
            "REL_RETURN_20D 為 12.60%、REL_RETURN_60D 為 20.47%。",
            evidence_ids,
        ), GroundedFinding(
            "Revenue YoY 的 canonical ratio 為 0.4612。",
            ["radar:2027.TW:revenue_yoy"],
        )])

        validate_grounded_ai_answer(answer, context)

        answer = grounded_answer_with_findings(context, [GroundedFinding(
            "Revenue YoY 為 46.12%、Revenue MoM 為 5.97%、"
            "REL_RETURN_20D 為 12.60%、REL_RETURN_60D 為 99.99%。",
            evidence_ids,
        )])
        with self.assertRaises(AINumericGroundingError):
            validate_grounded_ai_answer(answer, context)

        incorrect_mom = grounded_answer_with_findings(context, [GroundedFinding(
            "Revenue MoM 為 50%。",
            ["radar:2027.TW:revenue_mom"],
        )])
        with self.assertRaises(AINumericGroundingError):
            validate_grounded_ai_answer(incorrect_mom, context)

    def test_chinese_structural_windows_do_not_attach_to_revenue_mom(self):
        row = shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=0.1260, rel60=0.2047)
        stock = cached_stock("2027.TW")
        stock.fifty_day_average = 28.10
        stock.two_hundred_day_average = 30.10
        stock.fifty_two_week_high = 31.10
        stock.fifty_two_week_low = 23.30
        context = build_shortlist_selected_context(row, stock=stock, generated_at=NOW)
        cases = (
            ("Revenue MoM 為 5.97%，高於 50 日均線。", ["radar:2027.TW:revenue_mom"]),
            ("Revenue MoM 為 5.97%，50日均線為 28.10。", ["radar:2027.TW:revenue_mom", "current:fifty_day_average"]),
            ("Revenue MoM 為 5.97%，200 日均線為 30.10。", ["radar:2027.TW:revenue_mom", "current:two_hundred_day_average"]),
            ("Revenue MoM 為 5.97%，52 週高點為 31.10。", ["radar:2027.TW:revenue_mom", "current:fifty_two_week_high"]),
            ("Revenue MoM 為 5.97%，52 週低點為 23.30。", ["radar:2027.TW:revenue_mom", "current:fifty_two_week_low"]),
            ("Revenue MoM 為 5.97%，50-day average 為 28.10。", ["radar:2027.TW:revenue_mom", "current:fifty_day_average"]),
        )

        for statement, evidence_ids in cases:
            answer = grounded_answer_with_findings(context, [GroundedFinding(statement, evidence_ids)])
            validate_grounded_ai_answer(answer, context)

    def test_representative_fundamental_numeric_claims_are_fail_closed(self):
        row = shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=0.1260, rel60=0.2047)
        stock = cached_stock("2027.TW")
        stock.return_on_equity = 0.0661
        stock.trailing_pe = 13.91
        stock.price_to_book = 0.61
        stock.current_price = 28.10
        stock.total_cash = 54_780_000_000
        stock.total_debt = 238_070_000_000
        context = build_shortlist_selected_context(row, stock=stock, generated_at=NOW)
        evidence_ids = [
            "current:return_on_equity",
            "current:trailing_pe",
            "current:price_to_book",
            "current:current_price",
            "current:total_cash",
            "current:total_debt",
        ]
        answer = grounded_answer_with_findings(context, [GroundedFinding(
            "ROE 為 6.61%、Trailing P/E = 13.91x、P/B = 0.61、Current Price = TWD 28.10、"
            "Total Cash = TWD 54.78B、Total Debt = TWD 238.07B。",
            evidence_ids,
        )])

        validate_grounded_ai_answer(answer, context)

        for invalid_statement in (
            "P/B = 1.61。",
            "Total Debt = TWD 138.07B。",
            "Current Price = USD 28.10。",
        ):
            invalid = grounded_answer_with_findings(context, [GroundedFinding(invalid_statement, evidence_ids)])
            with self.assertRaises(AINumericGroundingError):
                validate_grounded_ai_answer(invalid, context)

    def test_missing_numeric_evidence_cannot_be_claimed(self):
        row = shortlist_row("2027.TW", yoy=0.4612, mom=0.0597, rel20=None, rel60=0.2047)
        stock = cached_stock("2027.TW")
        stock.price_to_book = None
        context = build_shortlist_selected_context(row, stock=stock, generated_at=NOW)

        missing_relative = grounded_answer_with_findings(context, [GroundedFinding(
            "REL_RETURN_20D 為 12.60%。",
            ["radar:2027.TW:revenue_yoy"],
        )])
        with self.assertRaises(AINumericGroundingError):
            validate_grounded_ai_answer(missing_relative, context)

        missing_pb = grounded_answer_with_findings(context, [GroundedFinding(
            "P/B = 0.61。",
            ["current:trailing_pe"],
        )])
        with self.assertRaises(AINumericGroundingError):
            validate_grounded_ai_answer(missing_pb, context)

    def test_dates_symbols_and_versions_are_not_financial_numeric_claims(self):
        context = build_shortlist_selected_context(
            shortlist_row("2027.TW"),
            stock=cached_stock("2027.TW"),
            generated_at=NOW,
        )
        answer = grounded_answer_with_findings(context, [GroundedFinding(
            "資料日期為 2026-08-29，股票代號為 2027.TW，卡片版本為 AI_ANALYST_CARD_V0。",
            ["shortlist:2027.TW:identity"],
        )])

        validate_grounded_ai_answer(answer, context)

    def test_one_company_failure_does_not_abort_remaining_cards(self):
        def generator(*, selected_context, **_kwargs):
            if selected_context.symbol == "2454.TW":
                raise RuntimeError("provider unavailable")
            return grounded_answer(selected_context)

        result = analyze_research_shortlist(
            [shortlist_row("2330.TW"), shortlist_row("2454.TW")],
            stock_loader=cached_stock,
            grounded_generator=generator,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )

        self.assertEqual(len(result["cards"]), 2)
        failed = next(card for card in result["cards"] if card["symbol"] == "2454.TW")
        self.assertEqual(failed["research_priority"], "證據不足")
        self.assertIn("provider unavailable", failed["missing_evidence"][0])
        self.assertEqual(result["stage1_success_count"], 1)

    def test_one_company_failed_numeric_repair_is_isolated(self):
        def generator(*, selected_context, **_kwargs):
            if selected_context.symbol == "2454.TW":
                return grounded_answer_with_findings(selected_context, [bound_finding(
                    "REL_RETURN_60D 為 99.99%。",
                    [("radar:2454.TW:rel_return_60d", "99.99%")],
                )])
            return grounded_answer(selected_context)

        result = analyze_research_shortlist(
            [shortlist_row("2330.TW"), shortlist_row("2454.TW")],
            stock_loader=cached_stock,
            grounded_generator=generator,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )

        failed = next(card for card in result["cards"] if card["symbol"] == "2454.TW")
        self.assertEqual(failed["research_priority"], "證據不足")
        self.assertIn("FINANCIAL_NUMERIC_NARRATIVE_PRESENT", failed["missing_evidence"][0])
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertEqual(result["stage1_success_count"], 1)

    def test_all_stage_one_failures_skip_synthesis_call(self):
        synthesis_calls = []

        result = analyze_research_shortlist(
            [shortlist_row("2330.TW"), shortlist_row("2454.TW")],
            stock_loader=cached_stock,
            grounded_generator=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
            synthesis_generator=lambda *, cards: synthesis_calls.append(cards),
            generated_at=NOW,
        )

        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertIsNone(result["synthesis"])
        self.assertEqual(synthesis_calls, [])

    def test_extreme_values_are_flagged_without_priority_upgrade(self):
        row = shortlist_row(yoy=1.5, rel60=0.8)
        context = build_shortlist_selected_context(row, stock=cached_stock(), generated_at=NOW)
        warnings = detect_extreme_value_warnings(context)
        card = normalize_analyst_card(grounded_answer(context, "值得觀察"), context, row)

        self.assertEqual(warnings, ["極端數值，建議先驗證資料／基期。"])
        self.assertIn(warnings[0], card["risks"])
        self.assertEqual(card["research_priority"], "值得觀察")

    def test_contradictions_are_captured(self):
        row = shortlist_row(yoy=0.2, mom=-0.1, rel20=-0.03, rel60=0.12)
        context = build_shortlist_selected_context(row, stock=cached_stock(), generated_at=NOW)

        contradictions = detect_contradictions(context)

        self.assertIn("Revenue YoY 為正，但 Revenue MoM 為負。", contradictions)
        self.assertIn("60D 相對強勢為正，但 20D 相對強勢為負。", contradictions)

    def test_prohibited_recommendation_vocabulary_is_rejected(self):
        context = build_shortlist_selected_context(shortlist_row(), stock=cached_stock(), generated_at=NOW)
        original = grounded_answer(context)
        answer = GroundedResearchAnswer(
            symbol=original.symbol,
            question_type=original.question_type,
            summary=original.summary,
            findings=[GroundedFinding("建議買進。", original.findings[0].evidence_ids), *original.findings[1:]],
            limitations=original.limitations,
            missing_information=original.missing_information,
            next_steps=original.next_steps,
            metadata=original.metadata,
        )

        with self.assertRaisesRegex(AIAnalystShortlistError, "prohibited"):
            normalize_analyst_card(answer, context, shortlist_row())

    def test_shortlist_limit_is_five_and_does_not_truncate(self):
        self.assertEqual(AI_ANALYST_SHORTLIST_MAX_SIZE, 5)
        rows = [shortlist_row(f"{index:04d}.TW") for index in range(6)]
        with self.assertRaisesRegex(AIAnalystShortlistError, "最多分析 5 檔"):
            analyze_research_shortlist(rows, stock_loader=lambda _symbol: None)

    def test_stage_two_receives_validated_cards_only(self):
        captured = []

        def synthesize(*, cards):
            captured.extend(cards)
            return valid_synthesis(cards)

        result = analyze_research_shortlist(
            [shortlist_row(), shortlist_row("2454.TW")],
            stock_loader=cached_stock,
            grounded_generator=lambda *, selected_context, **_kwargs: grounded_answer(selected_context),
            synthesis_generator=synthesize,
            generated_at=NOW,
        )

        self.assertEqual(captured, build_stage_two_cards(result["cards"]))
        self.assertNotIn("selected_context", json.dumps(captured, ensure_ascii=False))
        self.assertNotIn("display_value", json.dumps(captured, ensure_ascii=False))

    def test_stage_two_rejects_invented_symbol_and_more_than_three(self):
        context = build_shortlist_selected_context(shortlist_row(), stock=cached_stock(), generated_at=NOW)
        card = normalize_analyst_card(grounded_answer(context), context, shortlist_row())
        invented = valid_synthesis([card])
        invented["priority_deep_dive"] = [{"symbol": "9999.TW", "reason": "證據較完整", "main_unresolved_risk": "仍待確認"}]
        with self.assertRaisesRegex(AIAnalystShortlistError, "outside validated"):
            validate_shortlist_synthesis(invented, [card])

        too_many = valid_synthesis([card])
        too_many["priority_deep_dive"] = [
            {"symbol": "2330.TW", "reason": "證據較完整", "main_unresolved_risk": "仍待確認"}
            for _ in range(4)
        ]
        with self.assertRaisesRegex(AIAnalystShortlistError, "at most 3"):
            validate_shortlist_synthesis(too_many, [card])

    def _real_style_stage_two_cards(self):
        cards = []
        for symbol in ("1216.TW", "1608.TW", "2027.TW"):
            row = shortlist_row(symbol)
            context = build_shortlist_selected_context(row, stock=acceptance_stock(symbol), generated_at=NOW)
            cards.append(normalize_analyst_card(acceptance_answer(context), context, row))
        return cards

    def test_stage_two_three_card_payload_is_validated_card_only_and_has_no_request_length_guard(self):
        cards = self._real_style_stage_two_cards()
        payload = build_stage_two_request_payload(cards)
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        self.assertEqual([card["symbol"] for card in payload["validated_cards"]], ["1216.TW", "1608.TW", "2027.TW"])
        self.assertGreater(len(serialized), MAX_RESEARCH_QUESTION_LENGTH)
        self.assertNotIn("display_value", serialized)
        self.assertNotIn("missing:", serialized)
        self.assertNotIn("context:", serialized)
        self.assertNotIn("global:", serialized)
        for card in payload["validated_cards"]:
            self.assertEqual(set(card), {
                "symbol", "company_name", "research_priority", "opportunity_interpretation",
                "fundamental_quality", "valuation_context", "market_confirmation", "risks",
                "contradictions", "missing_evidence", "next_checks", "evidence_refs",
                "verified_evidence_summary",
            })
            self.assertTrue(all(set(item) == {"metric", "status", "evidence_id"} for item in card["verified_evidence_summary"]))
        self.assertGreater(len(SYNTHESIS_INSTRUCTIONS), 0)

    def test_stage_two_failure_diagnostics_are_safe_and_exactly_classified(self):
        cards = self._real_style_stage_two_cards()
        cases = (
            (AIResearchError("question 長度超過限制。"), "QUESTION_LENGTH_EXCEEDED", "AIResearchError"),
            (AIProviderError("provider detail that must not be shown"), "PROVIDER_ERROR", "AIProviderError"),
            (AIAnalystShortlistError("AI synthesis response is not valid JSON."), "STRUCTURED_OUTPUT_PARSE_ERROR", "AIAnalystShortlistError"),
            (AIAnalystShortlistError("Shortlist synthesis schema mismatch."), "STRUCTURED_OUTPUT_SCHEMA_ERROR", "AIAnalystShortlistError"),
            (RuntimeError("raw response must never be retained"), "STAGE2_UNEXPECTED_ERROR", "RuntimeError"),
        )
        for error, code, exception_class in cases:
            with self.subTest(code=code):
                diagnostic = build_stage_two_failure_diagnostic(error, cards)
                self.assertEqual(diagnostic["code"], code)
                self.assertEqual(diagnostic["exception_class"], exception_class)
                self.assertGreater(diagnostic["input_length"], 0)
                self.assertGreater(diagnostic["prompt_length"], 0)
                self.assertNotIn("raw response", json.dumps(diagnostic, ensure_ascii=False))

    def test_stage_two_numeric_diagnostic_preserves_first_token_and_field(self):
        cards = self._real_style_stage_two_cards()
        cases = (
            ("reason", "Revenue YoY 為 42.67%。", "42.67%", "PERCENTAGE"),
            ("reason", "市盈率約為18.33倍。", "18.33", "NON_PERCENTAGE"),
            ("reason", "ROE為１２％。", "12%", "PERCENTAGE"),
            ("main_unresolved_risk", "Current Price 為 TWD 48.40。", "TWD 48.40", "NON_PERCENTAGE"),
            ("cross_company_observations", "50-day 平均線仍待確認。", None, None),
            ("cross_company_observations", "0050 相對市場資料不足，近4季、12個月歷史序列待補。", None, None),
            ("overall_note", "仍需確認 42.67%。", "42.67%", "PERCENTAGE"),
        )
        for field, text, matched_numeric, classification in cases:
            with self.subTest(field=field, text=text):
                synthesis = valid_synthesis(cards)
                if field in {"reason", "main_unresolved_risk"}:
                    synthesis["priority_deep_dive"] = [{
                        "symbol": "2027.TW",
                        "reason": text if field == "reason" else "仍待確認資料。",
                        "main_unresolved_risk": text if field == "main_unresolved_risk" else "仍待確認資料。",
                    }]
                elif field == "cross_company_observations":
                    synthesis["cross_company_observations"] = [text]
                else:
                    synthesis["overall_note"] = text
                if matched_numeric is None:
                    validate_shortlist_synthesis(synthesis, cards)
                    continue
                with self.assertRaises(AIAnalystStageTwoNumericError) as raised:
                    validate_shortlist_synthesis(synthesis, cards)
                diagnostic = build_stage_two_failure_diagnostic(raised.exception, cards)
                self.assertEqual(diagnostic["code"], "STAGE2_NUMERIC_OUTPUT_REJECTED")
                self.assertEqual(diagnostic["matched_numeric"], matched_numeric)
                self.assertEqual(diagnostic["field"], field)
                self.assertEqual(diagnostic["numeric_classification"], classification)
                self.assertNotIn(text, json.dumps(diagnostic, ensure_ascii=False))
                rendered = format_stage_two_failure_diagnostic(diagnostic)
                self.assertIn(f"matched_numeric={matched_numeric}", rendered)
                self.assertIn(f"field={field}", rendered)

    def test_stage_two_symbol_field_is_not_scanned_as_numeric_output(self):
        cards = self._real_style_stage_two_cards()
        synthesis = valid_synthesis(cards)
        synthesis["priority_deep_dive"] = [{
            "symbol": "2027.TW", "reason": "需補足比較資料。", "main_unresolved_risk": "資料時點仍待確認。",
        }]

        validate_shortlist_synthesis(synthesis, cards)

    def test_stage_two_policy_rejection_preserves_safe_match_metadata(self):
        cards = self._real_style_stage_two_cards()
        synthesis = valid_synthesis(cards)
        synthesis["priority_deep_dive"] = [{
            "symbol": "1608.TW", "reason": "建議持有。", "main_unresolved_risk": "仍需確認資料。",
        }]
        with self.assertRaises(AIAnalystStageTwoPolicyError) as raised:
            validate_shortlist_synthesis(synthesis, cards)

        diagnostic = build_stage_two_failure_diagnostic(raised.exception, cards)
        self.assertEqual(diagnostic["code"], "RECOMMENDATION_POLICY_REJECTED")
        self.assertEqual(diagnostic["matched_rule"], "HOLD_ACTION")
        self.assertEqual(diagnostic["matched_term"], "hold_or_持有")
        self.assertEqual(diagnostic["field"], "reason")

    def test_stage_two_result_captures_safe_diagnostics_without_changing_cards(self):
        def synthesis_error(*, cards):
            raise AIProviderError("raw provider response must not be stored")

        result = analyze_research_shortlist(
            [shortlist_row(symbol) for symbol in ("1216.TW", "1608.TW", "2027.TW")],
            stock_loader=acceptance_stock,
            grounded_generator=lambda *, selected_context, **kwargs: acceptance_answer(selected_context),
            synthesis_generator=synthesis_error,
            generated_at=NOW,
        )
        self.assertEqual(result["stage1_success_count"], 3)
        self.assertEqual([card["symbol"] for card in result["cards"]], ["1216.TW", "1608.TW", "2027.TW"])
        self.assertIsNone(result["synthesis"])
        self.assertEqual(result["synthesis_error"], "PROVIDER_ERROR")
        self.assertEqual(result["stage2_diagnostic"]["exception_class"], "AIProviderError")
        self.assertNotIn("raw provider response", json.dumps(result["stage2_diagnostic"], ensure_ascii=False))

    def test_stage_two_allows_empty_priority_list(self):
        context = build_shortlist_selected_context(shortlist_row(), stock=cached_stock(), generated_at=NOW)
        card = normalize_analyst_card(grounded_answer(context), context, shortlist_row())

        validate_shortlist_synthesis(valid_synthesis([card]), [card])

    def test_stage_two_rejects_recommendation_and_unsupported_number(self):
        context = build_shortlist_selected_context(shortlist_row(), stock=cached_stock(), generated_at=NOW)
        card = normalize_analyst_card(grounded_answer(context), context, shortlist_row())
        recommendation = valid_synthesis([card])
        recommendation["overall_note"] = "建議買進。"
        with self.assertRaisesRegex(AIAnalystShortlistError, "prohibited"):
            validate_shortlist_synthesis(recommendation, [card])

        for recommendation_text in ("可以加碼。", "目標價為 60 元。", "投資推薦。"):
            recommendation["overall_note"] = recommendation_text
            with self.assertRaisesRegex(AIAnalystShortlistError, "prohibited"):
                validate_shortlist_synthesis(recommendation, [card])

        descriptive_return = valid_synthesis([card])
        descriptive_return["overall_note"] = "相對報酬率證據不足。"
        validate_shortlist_synthesis(descriptive_return, [card])

        recommendation["overall_note"] = "預期報酬率為 20%。"
        with self.assertRaisesRegex(AIAnalystShortlistError, "prohibited"):
            validate_shortlist_synthesis(recommendation, [card])

        unsupported = valid_synthesis([card])
        unsupported["overall_note"] = "預期增加 99%。"
        with self.assertRaisesRegex(AIAnalystShortlistError, "unsupported numerical"):
            validate_shortlist_synthesis(unsupported, [card])

    def test_malformed_synthesis_fails_without_deleting_stage_one_cards(self):
        result = analyze_research_shortlist(
            [shortlist_row(), shortlist_row("2454.TW")],
            stock_loader=cached_stock,
            grounded_generator=lambda *, selected_context, **_kwargs: grounded_answer(selected_context),
            synthesis_generator=lambda *, cards: {"bad": cards},
            generated_at=NOW,
        )

        self.assertEqual(len(result["cards"]), 2)
        self.assertIsNone(result["synthesis"])
        self.assertIsNotNone(result["synthesis_error"])

    def test_synthesis_adapter_reuses_existing_provider_interface(self):
        cards = []
        for symbol in ("2330.TW", "2454.TW"):
            row = shortlist_row(symbol)
            context = build_shortlist_selected_context(row, stock=cached_stock(symbol), generated_at=NOW)
            cards.append(normalize_analyst_card(grounded_answer(context), context, row))
        payload = valid_synthesis(cards)

        class Client:
            def create_grounded_answer(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(output_text=json.dumps(payload, ensure_ascii=False))

        client = Client()
        result = generate_shortlist_synthesis(cards=cards, client=client)

        self.assertEqual(result, payload)
        self.assertEqual(client.kwargs["payload"]["validated_cards"], build_stage_two_cards(cards))
        self.assertNotIn("raw_financial", client.kwargs["payload"])


class UnifiedAnalystRepairTest(unittest.TestCase):
    def setUp(self):
        self.stock = refreshed_binding_stock("1608.TW")
        self.stock.current_price = 37.85
        self.stock.fifty_day_average = 33.806
        self.row = shortlist_row("1608.TW")
        self.context = build_analyst_model_context(build_shortlist_selected_context(
            self.row, stock=self.stock, generated_at=NOW,
        ))

    def answer(self, findings):
        return grounded_answer_with_findings(self.context, findings)

    def run_candidate(self, answer, response):
        calls = []
        def repair(**kwargs):
            calls.append(kwargs)
            return response
        result = _analyze_research_shortlist(
            [self.row], stock_loader=lambda _: self.stock,
            grounded_generator=lambda **_: answer, repair_generator=repair, generated_at=NOW,
        )
        return result, calls

    def test_combined_policy_numeric_and_valuation_are_patched_once_in_original_order(self):
        answer = self.answer([
            GroundedFinding("可持有觀察。", ["radar:1608.TW:revenue_yoy"]),
            GroundedFinding("目前股價 TWD37.85，位於 50 日均線之上。", ["current:current_price", "current:fifty_day_average"]),
            GroundedFinding("目前估值合理。", ["current:trailing_pe"]),
            GroundedFinding("獲利成長可供研究。", ["current:earnings_growth"]),
        ])
        before = asdict(answer)
        request = build_analyst_repair_request(answer, self.context)
        self.assertEqual([slot["slot_id"] for slot in request["slots"]], ["findings:0", "findings:1", "findings:2"])
        self.assertTrue(all(slot["allowed_patch_fields"] == ["rewritten_text"] for slot in request["slots"]))
        response = {"patches": [
            {"slot_id": "findings:2", "rewritten_text": "估值倍數可供觀察，缺少同業與歷史比較。"},
            {"slot_id": "findings:1", "rewritten_text": "目前價格相對中期均價偏強，仍需市場確認。"},
            {"slot_id": "findings:0", "rewritten_text": "營收動能可供持續研究。"},
        ]}
        merged = apply_analyst_repair_patch(answer, request, response, self.context)
        self.assertEqual(asdict(answer), before)
        self.assertEqual(len(merged.findings), len(answer.findings))
        self.assertEqual([item.evidence_ids for item in merged.findings], [item.evidence_ids for item in answer.findings])
        self.assertEqual(merged.findings[3], answer.findings[3])
        self.assertEqual(merged.symbol, answer.symbol)
        self.assertEqual(merged.summary, answer.summary)
        self.assertEqual(merged.metadata, answer.metadata)
        self.assertEqual(merged.findings[0].statement, response["patches"][2]["rewritten_text"])
        result, calls = self.run_candidate(answer, response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertEqual(result["stage1_success_count"], 1, result["cards"][0]["missing_evidence"])
        self.assertEqual(result["stage1_policy_regeneration_count"], 1)
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertEqual(result["cards"][0]["research_priority"], "值得觀察")

    def test_single_slot_combined_numeric_and_hold_needs_only_one_text_patch(self):
        answer = self.answer([GroundedFinding("目前股價 TWD 37.85，可持有觀察。", ["current:current_price"])])
        request = build_analyst_repair_request(answer, self.context)
        self.assertEqual(len(request["slots"]), 1)
        self.assertEqual(len(request["slots"][0]["reasons"]), 2)
        result, calls = self.run_candidate(answer, {"patches": [
            {"slot_id": "findings:0", "rewritten_text": "市場位置仍需確認。"},
        ]})
        self.assertEqual(result["stage1_success_count"], 1)
        self.assertEqual(len(calls), 1)

    def test_missing_ref_patch_only_exposes_semantic_catalog_for_affected_slot(self):
        answer = self.answer([
            GroundedFinding("市場位置仍需確認。", ["current:current_price"]),
            GroundedFinding("月營收年增與月增方向一致。", ["radar:1608.TW:revenue_yoy"]),
        ])
        request = build_analyst_repair_request(answer, self.context)
        self.assertEqual(len(request["slots"]), 1)
        slot = request["slots"][0]
        self.assertEqual(slot["slot_id"], "findings:1")
        self.assertEqual(slot["allowed_patch_fields"], ["evidence_refs"])
        self.assertEqual(set(slot["allowed_evidence_ids"]), {"radar:1608.TW:revenue_yoy", "radar:1608.TW:revenue_mom"})
        refs = ["radar:1608.TW:revenue_yoy", "radar:1608.TW:revenue_mom"]
        response = {"patches": [{"slot_id": "findings:1", "evidence_refs": refs}]}
        merged = apply_analyst_repair_patch(answer, request, response, self.context)
        self.assertEqual(merged.findings[0], answer.findings[0])
        self.assertEqual(merged.findings[1].statement, answer.findings[1].statement)
        self.assertEqual(merged.findings[1].evidence_ids, refs)
        result, calls = self.run_candidate(answer, response)
        self.assertEqual(result["stage1_success_count"], 1)
        self.assertEqual(len(calls), 1)

    def test_empty_refs_are_patchable_only_with_an_unambiguous_supported_domain(self):
        answer = self.answer([GroundedFinding("月營收年增與月增方向一致。", [])])
        result, calls = self.run_candidate(answer, {"patches": [{
            "slot_id": "findings:0", "evidence_refs": ["radar:1608.TW:revenue_yoy", "radar:1608.TW:revenue_mom"],
        }]})
        self.assertEqual(result["stage1_success_count"], 1)
        self.assertEqual(len(calls), 1)

    def test_invalid_patch_shapes_and_locked_fields_fail_without_second_repair(self):
        answer = self.answer([GroundedFinding("可持有觀察。", ["current:current_price"])])
        valid = {"slot_id": "findings:0", "rewritten_text": "市場位置仍需確認。"}
        cases = [
            {"patches": [{**valid, "slot_id": "findings:9"}]},
            {"patches": [valid, valid]}, {"patches": []},
            {"patches": [{"slot_id": "findings:0"}]},
            {"patches": [{**valid, "evidence_refs": ["current:current_price"]}]},
            {"patches": [{**valid, "symbol": "2330.TW"}]},
            {"patches": [{**valid, "section": "valuation_context"}]},
            {"patches": [{**valid, "research_priority": "優先深入研究"}]},
            {"patches": [{**valid, "delete": True}]},
            {"patches": [valid], "findings": []},
            {"findings": [{"statement": "市場位置仍需確認。", "evidence_ids": ["current:current_price"]}]},
            {"patches": [{**valid, "rewritten_text": ""}]},
        ]
        for response in cases:
            with self.subTest(response=response):
                result, calls = self.run_candidate(answer, response)
                self.assertEqual(result["stage1_success_count"], 0)
                self.assertEqual(len(calls), 1)
                self.assertEqual(result["provider_call_count"], 2)

    def test_invented_wrong_domain_and_incomplete_ref_patches_fail_final_grounding(self):
        answer = self.answer([GroundedFinding("月營收年增與月增方向一致。", ["radar:1608.TW:revenue_yoy"])])
        for refs in (["current:invented"], ["current:current_price"], ["radar:1608.TW:revenue_yoy"],
                     ["radar:1608.TW:revenue_mom"], ["radar:1608.TW:revenue_yoy"] * 2):
            with self.subTest(refs=refs):
                result, calls = self.run_candidate(answer, {"patches": [{"slot_id": "findings:0", "evidence_refs": refs}]})
                self.assertEqual(result["stage1_success_count"], 0)
                self.assertEqual(len(calls), 1)

    def test_nonrepairable_original_errors_block_before_any_repair(self):
        cases = [
            GroundedFinding("可持有，目前股價 TWD 37.85。", ["current:invented"]),
            GroundedFinding("ROE 顯示資本效率。", ["current:current_price"]),
        ]
        for finding in cases:
            with self.subTest(text=finding.statement):
                result, calls = self.run_candidate(self.answer([
                    GroundedFinding("可持有觀察。", ["current:current_price"]), finding,
                ]), {"patches": []})
                self.assertEqual(calls, [])
                self.assertEqual(result["stage1_success_count"], 0)
                self.assertEqual(result["provider_call_count"], 1)

    def test_analyst_numeric_prose_is_patched_without_metric_value_inference(self):
        cases = (
            "目前股價 TWD 99。",
            "目前股價 USD37.85。",
            "Current Price = TWD 33.806。",
            "Revenue MoM 為 99%。",
            "Revenue MoM 為 25%。",
        )
        for text in cases:
            with self.subTest(text=text):
                refs = ["current:current_price"] if "股價" in text or "Price" in text else [
                    "radar:1608.TW:revenue_yoy", "radar:1608.TW:revenue_mom",
                ]
                answer = self.answer([GroundedFinding(text, refs)])
                result, calls = self.run_candidate(answer, {"patches": [{
                    "slot_id": "findings:0", "rewritten_text": "相關研究訊號仍需持續確認。",
                }]})
                self.assertEqual(result["stage1_success_count"], 1, result["cards"])
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]["request"]["slots"][0]["reasons"], [
                    "FINANCIAL_NUMERIC_NARRATIVE_PRESENT",
                ])

    def test_2027_missing_ref_is_collected_before_final_normalize(self):
        stock = refreshed_binding_stock("2027.TW")
        row = shortlist_row("2027.TW")
        context = build_analyst_model_context(build_shortlist_selected_context(
            row, stock=stock, generated_at=NOW,
        ))
        answer = grounded_answer_with_findings(context, [GroundedFinding(
            "月營收年增與月增方向一致。", ["radar:2027.TW:revenue_yoy"],
        )])
        request = build_analyst_repair_request(answer, context)
        self.assertEqual(request["slots"][0]["slot_id"], "findings:0")
        self.assertEqual(request["slots"][0]["reasons"], ["MISSING_REQUIRED_EVIDENCE_REFS"])
        self.assertEqual(request["slots"][0]["allowed_patch_fields"], ["evidence_refs"])

    def test_invalid_locked_narrative_blocks_before_any_repair(self):
        answer = self.answer([GroundedFinding("可持有觀察。", ["current:current_price"])])
        answer = replace(answer, summary="目前股價 USD 999。")
        result, calls = self.run_candidate(answer, {"patches": []})
        self.assertEqual(calls, [])
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["provider_call_count"], 1)

    def test_repaired_unsafe_numeric_or_unsupported_meaning_fails_without_retry(self):
        answer = self.answer([GroundedFinding("目前股價 TWD 37.85。", ["current:current_price"])])
        for text in ("可持有觀察。", "目前股價 TWD 37.85。", "ROE 顯示資本效率。"):
            with self.subTest(text=text):
                result, calls = self.run_candidate(answer, {"patches": [{"slot_id": "findings:0", "rewritten_text": text}]})
                self.assertEqual(result["stage1_success_count"], 0)
                self.assertEqual(len(calls), 1)

    def test_provider_patch_schema_contains_only_authorized_fields(self):
        answer = self.answer([
            GroundedFinding("可持有觀察。", ["current:current_price"]),
            GroundedFinding("月營收年增與月增方向一致。", []),
        ])
        request = build_analyst_repair_request(answer, self.context)
        response = {"patches": [
            {"slot_id": "findings:0", "rewritten_text": "市場位置仍需確認。"},
            {"slot_id": "findings:1", "evidence_refs": ["radar:1608.TW:revenue_yoy", "radar:1608.TW:revenue_mom"]},
        ]}
        class Client:
            def create_grounded_answer(client, **kwargs):
                client.kwargs = kwargs
                return SimpleNamespace(output_text=json.dumps(response))
        client = Client()
        actual = generate_analyst_repair_patch(
            request=request, selected_context=self.context, client=client,
            config=AIResearchConfig("mock", 2400, "minimal", "low", 30),
        )
        self.assertEqual(actual, response)
        schema = client.kwargs["response_format"]["schema"]
        self.assertEqual(set(schema["properties"]), {"patches"})
        variants = schema["properties"]["patches"]["items"]["anyOf"]
        self.assertEqual(set(variants[0]["properties"]), {"slot_id", "rewritten_text"})
        self.assertEqual(set(variants[1]["properties"]), {"slot_id", "evidence_refs"})
        self.assertNotIn("numeric_mentions", json.dumps(client.kwargs))
        self.assertLessEqual(len(request["question"]), MAX_RESEARCH_QUESTION_LENGTH)
        self.assertEqual(MAX_RESEARCH_QUESTION_LENGTH, 1500)

    def test_latest_real_three_company_path_preserves_1216_and_reaches_stage_two(self):
        symbols = ["1216.TW", "1608.TW", "2027.TW"]
        calls, stage_two = [], []
        def initial(*, selected_context, **_):
            symbol = selected_context.symbol
            findings = {
                "1216.TW": [GroundedFinding("營收方向提供研究線索。", ["radar:1216.TW:revenue_yoy"])],
                "1608.TW": [GroundedFinding("目前股價 TWD 75.70。", ["current:current_price"]),
                            GroundedFinding("獲利成長可供研究。", ["current:earnings_growth"])],
                "2027.TW": [GroundedFinding("月營收年增與月增方向一致。", ["radar:2027.TW:revenue_yoy"])],
            }[symbol]
            answer = grounded_answer_with_findings(selected_context, findings)
            return replace(answer, summary=(
                "研究優先度：優先深入研究\n目前證據供初步研究使用。"
                if symbol == "1216.TW" else answer.summary
            ))
        def repair(*, request, selected_context):
            calls.append(selected_context.symbol)
            slot = request["slots"][0]
            item = {"slot_id": slot["slot_id"]}
            if "evidence_refs" in slot["allowed_patch_fields"]:
                item["evidence_refs"] = slot["allowed_evidence_ids"]
            else:
                item["rewritten_text"] = "市場位置仍需確認。"
            return {"patches": [item]}
        def synthesis(*, cards):
            stage_two.extend(card["symbol"] for card in cards)
            return valid_synthesis(cards)
        result = _analyze_research_shortlist(
            [shortlist_row(symbol) for symbol in symbols], stock_loader=refreshed_binding_stock,
            grounded_generator=initial, repair_generator=repair, synthesis_generator=synthesis, generated_at=NOW,
        )
        self.assertEqual(result["stage1_success_count"], 3, [card["missing_evidence"] for card in result["cards"]])
        self.assertEqual(calls, ["1608.TW", "2027.TW"])
        self.assertEqual(stage_two, symbols)
        self.assertEqual(result["provider_call_count"], 6)
        self.assertIsNotNone(result["synthesis"])
        self.assertEqual(result["cards"][0]["research_priority"], "優先深入研究")

    def test_already_valid_2027_requires_no_repair(self):
        stock = refreshed_binding_stock("2027.TW")
        calls = []
        result = _analyze_research_shortlist(
            [shortlist_row("2027.TW")], stock_loader=lambda _: stock,
            grounded_generator=lambda *, selected_context, **_: acceptance_answer(selected_context),
            repair_generator=lambda **_: calls.append(True), generated_at=NOW,
        )
        self.assertEqual(calls, [])
        self.assertEqual(result["stage1_success_count"], 1, result["cards"])



# Captured on 2026-08-30 from gpt-5-mini. Keep exact structured output,
# not response IDs, credentials, prompts, or a live dependency on local caches.
REAL_ANALYST_CAPTURE = json.loads(r'''{
  "1216.TW": {
    "stock": {
      "symbol": "1216.TW",
      "currency": "TWD",
      "company_name": "Uni-President Enterprises Corp.",
      "current_price": 75.7,
      "trailing_pe": 18.329296,
      "return_on_equity": 0.17834,
      "operating_margin": 0.05864,
      "earnings_growth": 0.443,
      "total_cash": 153698451456,
      "total_debt": 315199619072,
      "debt_to_equity": 148.861,
      "price_to_book": 3.15535,
      "fifty_day_average": 76.572,
      "two_hundred_day_average": 74.3635,
      "industry": "Packaged Foods"
    },
    "row": {
      "股票代號": "1216.TW",
      "公司名稱": "Uni-President Enterprises Corp.",
      "產業": "Packaged Foods"
    },
    "radar": {
      "revenue_period": "N/A",
      "revenue_yoy": 0.0884909301522625,
      "revenue_mom": 0.06633707089497709,
      "relative_return_20d": null,
      "relative_return_60d": null,
      "condition_flags": [
        "營收年增為正",
        "營收月增為正"
      ],
      "retrieved_at": "2026-08-29T18:55:48.832558+08:00",
      "relative_provenance": {
        "as_of_date": "2026-08-28",
        "stock_fetched_at": "2026-08-30T05:07:52.571939+00:00",
        "benchmark_fetched_at": "2026-08-30T05:07:57.728312+00:00",
        "source": "Yahoo Finance"
      }
    },
    "responses": {
      "initial": {
        "symbol": "1216.TW",
        "question_type": "general_research",
        "summary": "研究優先度：優先深入研究。公司呈現營收與盈餘成長跡象，但負債結構與估值比較需進一步釐清。",
        "findings": [
          {
            "statement": "Opportunity：月度營收呈年增與環比正成長，顯示短期需求動能。",
            "evidence_ids": [
              "radar:1216.TW:revenue_yoy",
              "radar:1216.TW:revenue_mom"
            ]
          },
          {
            "statement": "Fundamental：近期期盈餘成長率與ROE顯示獲利能力改善且資本報酬率為正。",
            "evidence_ids": [
              "current:earnings_growth",
              "current:return_on_equity"
            ]
          },
          {
            "statement": "Fundamental（營運效率）：營業毛利或營業利潤率存在正值但不高，需檢視毛利結構與成本控制可持續性。",
            "evidence_ids": [
              "current:operating_margin"
            ]
          },
          {
            "statement": "Valuation：trailing P/E 約 18.33 倍，P/B 約 3.16 倍，需評估與可比基準或歷史倍數的缺口。",
            "evidence_ids": [
              "current:trailing_pe",
              "current:price_to_book"
            ]
          },
          {
            "statement": "Market／財務風險：公司現金與總負債規模顯著，且債務對股東權益比偏高，需進一步評估償債能力與資本結構風險；股價目前接近 50 日均線且略高於 200 日均線。",
            "evidence_ids": [
              "current:total_cash",
              "current:total_debt",
              "current:debt_to_equity",
              "current:current_price",
              "current:fifty_day_average",
              "current:two_hundred_day_average"
            ]
          }
        ],
        "limitations": [
          "僅有快照指標，缺少現金流量表、利息費用、分季/年度盈餘明細與業務細分資料。"
        ],
        "missing_information": [
          "無可比公司或歷史倍數資料以量化估值缺口（可用於比較 P/E 或 P/B）。",
          "缺乏毛利率分項、利息支出與到期債務結構以評估短期償債壓力。"
        ],
        "next_steps": [
          "取得歷史 P/E 與 P/B 時序資料以及可比公司估值以量化估值缺口（use IDs: current:trailing_pe,current:price_to_book）。",
          "收集完整資產負債與現金流明細、利息費用與到期負債表以評估償債能力（use IDs: current:total_cash,current:total_debt,current:debt_to_equity）。",
          "取得分季/年度營收與毛利分項以檢驗營收成長與營業利潤可持續性（use IDs: radar:1216.TW:revenue_yoy,radar:1216.TW:revenue_mom,current:operating_margin）"
        ]
      },
      "repair": {
        "patches": [
          {
            "slot_id": "findings:3",
            "rewritten_text": "估值為基於過去十二個月盈利計算的市盈率約為18.33倍，市淨率約為3.16倍；需要在對照同類可比公司或自身歷史倍數的情境下評估這些倍數差異的意義。"
          }
        ]
      }
    }
  },
  "1608.TW": {
    "stock": {
      "symbol": "1608.TW",
      "currency": "TWD",
      "company_name": "Hua Eng Wire & Cable Co., Ltd.",
      "current_price": 37.85,
      "trailing_pe": 3.2884445,
      "return_on_equity": 0.48089,
      "operating_margin": 0.085939996,
      "earnings_growth": 9.249,
      "total_cash": 1809931008,
      "total_debt": 4191009024,
      "debt_to_equity": 33.453,
      "price_to_book": 1.4206358,
      "fifty_day_average": 33.806,
      "two_hundred_day_average": 34.70875,
      "industry": "Electrical Equipment & Parts"
    },
    "row": {
      "股票代號": "1608.TW",
      "公司名稱": "Hua Eng Wire & Cable Co., Ltd.",
      "產業": "Electrical Equipment & Parts"
    },
    "radar": {
      "revenue_period": "N/A",
      "revenue_yoy": 0.4266714973997303,
      "revenue_mom": 0.1495995314418137,
      "relative_return_20d": null,
      "relative_return_60d": null,
      "condition_flags": [
        "營收年增為正",
        "營收月增為正"
      ],
      "retrieved_at": "2026-08-29T18:55:48.832558+08:00",
      "relative_provenance": {
        "as_of_date": "2026-08-28",
        "stock_fetched_at": "2026-08-30T05:07:54.585842+00:00",
        "benchmark_fetched_at": "2026-08-30T05:07:57.728312+00:00",
        "source": "Yahoo Finance"
      }
    },
    "responses": {
      "initial": {
        "symbol": "1608.TW",
        "question_type": "general_research",
        "summary": "研究優先度：優先深入研究。公司呈現營收及獲利動能跡象且估值倍數相對低檔，但需補充財報明細與同業／歷史比較以確認持續性與風險。",
        "findings": [
          {
            "statement": "Opportunity：月度營收呈正向成長，最近一個月年增與月增皆顯著正向。",
            "evidence_ids": [
              "radar:1608.TW:revenue_yoy",
              "radar:1608.TW:revenue_mom"
            ]
          },
          {
            "statement": "Fundamental：報表顯示強勁的ROE與正向營業利潤率，且近年（或當前）盈利成長為正。",
            "evidence_ids": [
              "current:return_on_equity",
              "current:operating_margin",
              "current:earnings_growth"
            ]
          },
          {
            "statement": "Valuation：市盈率與市淨率均位於可觀區間，trailing P/E 明顯偏低（僅以倍數描述，需與同業或歷史比較確認缺口來源）。",
            "evidence_ids": [
              "current:trailing_pe",
              "current:price_to_book"
            ]
          },
          {
            "statement": "Market：現價高於50日與200日均線，顯示近期價格趨勢上升，與長短期均線存在差距。",
            "evidence_ids": [
              "current:current_price",
              "current:fifty_day_average",
              "current:two_hundred_day_average"
            ]
          }
        ],
        "limitations": [
          "僅使用提供之快照資料，缺乏完整財報分項、現金流與利潤表歷史序列。"
        ],
        "missing_information": [
          "公司損益表、資產負債表與現金流量表的分項明細與多期趨勢"
        ],
        "next_steps": [
          "取得最近數季或年度財報以驗證營收／獲利持續性（use evidence id current:earnings_growth,current:return_on_equity,current:operating_margin）",
          "蒐集同業與歷史估值倍數比較以量化估值缺口（use evidence id current:trailing_pe,current:price_to_book）",
          "檢視負債結構與流動性細項以評估資本風險（use evidence id current:total_cash,current:total_debt,current:debt_to_equity）"
        ]
      },
      "repair": {
        "patches": [
          {
            "slot_id": "findings:2",
            "rewritten_text": "估值：以市盈率和市淨率衡量，兩者位於可觀區間；其中 trailing P/E 顯著較低（僅描述為倍數現象，應與同業或公司歷史比較以確認差異來源）。"
          }
        ]
      }
    }
  },
  "2027.TW": {
    "stock": {
      "symbol": "2027.TW",
      "currency": "TWD",
      "company_name": "Ta Chen Stainless Pipe Co., Ltd.",
      "current_price": 48.4,
      "trailing_pe": 9.6994,
      "return_on_equity": 0.1703,
      "operating_margin": 0.21106,
      "earnings_growth": 3.622,
      "total_cash": 16097614848,
      "total_debt": 51051364352,
      "debt_to_equity": 54.759,
      "price_to_book": 1.508352,
      "fifty_day_average": 44.076,
      "two_hundred_day_average": 39.54675,
      "industry": "Steel"
    },
    "row": {
      "股票代號": "2027.TW",
      "公司名稱": "Ta Chen Stainless Pipe Co., Ltd.",
      "產業": "Steel"
    },
    "radar": {
      "revenue_period": "N/A",
      "revenue_yoy": 0.4611671250325682,
      "revenue_mom": 0.05966405566231092,
      "relative_return_20d": null,
      "relative_return_60d": null,
      "condition_flags": [
        "營收年增為正",
        "營收月增為正"
      ],
      "retrieved_at": "2026-08-29T18:55:48.832558+08:00",
      "relative_provenance": {
        "as_of_date": "2026-08-28",
        "stock_fetched_at": "2026-08-30T05:07:56.674822+00:00",
        "benchmark_fetched_at": "2026-08-30T05:07:57.728312+00:00",
        "source": "Yahoo Finance"
      }
    },
    "responses": {
      "initial": {
        "symbol": "2027.TW",
        "question_type": "general_research",
        "summary": "研究優先度：值得觀察。營收呈現顯著年增與月增，但估值與財務槓桿需進一步釐清。",
        "findings": [
          {
            "statement": "Opportunity：近期營收顯示年增與月增動能，可能反映需求回溫。",
            "evidence_ids": [
              "radar:2027.TW:revenue_yoy",
              "radar:2027.TW:revenue_mom"
            ]
          },
          {
            "statement": "Fundamental：營業利益率與股東報酬率顯示獲利能力存在，且每股盈餘成長率為正。",
            "evidence_ids": [
              "current:operating_margin",
              "current:return_on_equity",
              "current:earnings_growth"
            ]
          },
          {
            "statement": "Valuation：trailing P/E 約 9.70 倍，P/B 約 1.51 倍，提示市場對應估值位階需與同類或歷史比較以判斷折價或溢價空間。",
            "evidence_ids": [
              "current:trailing_pe",
              "current:price_to_book"
            ]
          },
          {
            "statement": "Market：股價高於 50 日與 200 日均線，現價呈相對上漲趨勢；相對 0050 缺口需另行計算比較。",
            "evidence_ids": [
              "current:current_price",
              "current:fifty_day_average",
              "current:two_hundred_day_average"
            ]
          },
          {
            "statement": "Balance sheet / leverage：公司現金與負債規模並存，負債對股東權益比顯著，需關注資本結構風險。",
            "evidence_ids": [
              "current:total_cash",
              "current:total_debt",
              "current:debt_to_equity"
            ]
          }
        ],
        "limitations": [
          "本次資料為快照，缺乏時間序列與同業比較，難以斷定趨勢持續性或相對估值位置。"
        ],
        "missing_information": [
          "營收與獲利的時間序列明細與季節性拆解（例如過去 4 季或 12 個月數據）",
          "同業與歷史估值比較資料以判斷估值缺口",
          "現金流量與資本支出明細以評估負債償還能力"
        ],
        "next_steps": [
          "取得過去 4 季或 12 個月營收與淨利時間序列以驗證營收成長持續性（use evidence IDs: radar:2027.TW:revenue_yoy, radar:2027.TW:revenue_mom）",
          "蒐集同業與歷史 P/E、P/B 倍數作比較（use evidence IDs: current:trailing_pe, current:price_to_book）",
          "取得現金流量表與資本支出資料評估償債能力（use evidence IDs: current:total_cash, current:total_debt, current:debt_to_equity）"
        ]
      }
    }
  }
}''')


# Original authorized slot maps are part of the captured request, not a new repair.
REAL_ANALYST_REPAIR_RECORDS = json.loads(r'''{
  "1216.TW": {
    "slots": [
      {
        "slot_id": "findings:3",
        "field": "findings",
        "index": 3,
        "section": [
          "valuation_context"
        ],
        "original_text": "Valuation：trailing P/E 約 18.33 倍，P/B 約 3.16 倍，需評估與可比基準或歷史倍數的缺口。",
        "locked_evidence_refs": [
          "current:trailing_pe",
          "current:price_to_book"
        ],
        "allowed_patch_fields": [
          "rewritten_text"
        ],
        "allowed_evidence_ids": [],
        "reasons": [
          "FINANCIAL_NUMERIC_NARRATIVE_PRESENT"
        ]
      }
    ],
    "response": {
      "patches": [
        {
          "slot_id": "findings:3",
          "rewritten_text": "估值為基於過去十二個月盈利計算的市盈率約為18.33倍，市淨率約為3.16倍；需要在對照同類可比公司或自身歷史倍數的情境下評估這些倍數差異的意義。"
        }
      ]
    }
  },
  "1608.TW": {
    "slots": [
      {
        "slot_id": "findings:2",
        "field": "findings",
        "index": 2,
        "section": [
          "valuation_context"
        ],
        "original_text": "Valuation：市盈率與市淨率均位於可觀區間，trailing P/E 明顯偏低（僅以倍數描述，需與同業或歷史比較確認缺口來源）。",
        "locked_evidence_refs": [
          "current:trailing_pe",
          "current:price_to_book"
        ],
        "allowed_patch_fields": [
          "rewritten_text"
        ],
        "allowed_evidence_ids": [],
        "reasons": [
          "VALUATION_COMPARATOR_OVERCLAIM"
        ]
      }
    ],
    "response": {
      "patches": [
        {
          "slot_id": "findings:2",
          "rewritten_text": "估值：以市盈率和市淨率衡量，兩者位於可觀區間；其中 trailing P/E 顯著較低（僅描述為倍數現象，應與同業或公司歷史比較以確認差異來源）。"
        }
      ]
    }
  },
  "2027.TW": {
    "slots": [
      {
        "slot_id": "findings:2",
        "field": "findings",
        "index": 2,
        "section": [
          "valuation_context"
        ],
        "original_text": "Valuation：trailing P/E 約 9.70 倍，P/B 約 1.51 倍，提示市場對應估值位階需與同類或歷史比較以判斷折價或溢價空間。",
        "locked_evidence_refs": [
          "current:trailing_pe",
          "current:price_to_book"
        ],
        "allowed_patch_fields": [
          "rewritten_text"
        ],
        "allowed_evidence_ids": [],
        "reasons": [
          "FINANCIAL_NUMERIC_NARRATIVE_PRESENT"
        ]
      },
      {
        "slot_id": "findings:3",
        "field": "findings",
        "index": 3,
        "section": [
          "market_confirmation"
        ],
        "original_text": "Market：股價高於 50 日與 200 日均線，現價呈相對上漲趨勢；相對 0050 缺口需另行計算比較。",
        "locked_evidence_refs": [
          "current:current_price",
          "current:fifty_day_average",
          "current:two_hundred_day_average"
        ],
        "allowed_patch_fields": [
          "rewritten_text"
        ],
        "allowed_evidence_ids": [],
        "reasons": [
          "FINANCIAL_NUMERIC_NARRATIVE_PRESENT"
        ]
      },
      {
        "slot_id": "missing_information:0",
        "field": "missing_information",
        "index": 0,
        "section": [
          "missing_information"
        ],
        "original_text": "營收與獲利的時間序列明細與季節性拆解（例如過去 4 季或 12 個月數據）",
        "locked_evidence_refs": [],
        "allowed_patch_fields": [
          "rewritten_text"
        ],
        "allowed_evidence_ids": [],
        "reasons": [
          "FINANCIAL_NUMERIC_NARRATIVE_PRESENT"
        ]
      },
      {
        "slot_id": "next_steps:0",
        "field": "next_steps",
        "index": 0,
        "section": [
          "next_steps"
        ],
        "original_text": "取得過去 4 季或 12 個月營收與淨利時間序列以驗證營收成長持續性（use evidence IDs: radar:2027.TW:revenue_yoy, radar:2027.TW:revenue_mom）",
        "locked_evidence_refs": [
          "radar:2027.TW:revenue_yoy",
          "radar:2027.TW:revenue_mom"
        ],
        "allowed_patch_fields": [
          "rewritten_text"
        ],
        "allowed_evidence_ids": [],
        "reasons": [
          "FINANCIAL_NUMERIC_NARRATIVE_PRESENT"
        ]
      }
    ],
    "response": {
      "patches": [
        {
          "slot_id": "findings:2",
          "rewritten_text": "Valuation：以市盈率與市淨率衡量時，報告使用最近報表的 trailing P/E 與 P/B 作為參考；需透過與同業或公司歷史的多期間比較，來理解目前倍數位於相對高低的哪個區間，並說明比較基準與期間的選擇。"
        },
        {
          "slot_id": "findings:3",
          "rewritten_text": "Market：目前股價高於短中期與長期移動平均線，顯示近期呈現上漲的相對趨勢；若欲與特定指標（如 0050）做相對表現比較，應明確定義比較方法（例如計算相對強弱比或報酬差異）與時窗。"
        },
        {
          "slot_id": "missing_information:0",
          "rewritten_text": "需補充營收與獲利的時間序列資料並拆解季節性影響（例如列示過去若干季或 12 個月的季度/同年成長率與季變化），以便檢視趨勢與周期性。"
        },
        {
          "slot_id": "next_steps:0",
          "rewritten_text": "蒐集與整理過去 4 季或 12 個月的營收與淨利時間序列資料，計算年增率與環比變動以驗證營收成長的持續性；並註明使用的證據欄位與計算方法。"
        }
      ]
    }
  }
}''')



class CapturedAnalystLifecycleTest(unittest.TestCase):
    def test_structural_taxonomy_uses_context_not_numeric_value(self):
        _, _, context, _ = self.fixture("2027.TW")
        cases = {
            "0050 相對市場資料不足": {"BENCHMARK"},
            "如 0050，作為比較基準": {"BENCHMARK"},
            "0050.TW 相對市場資料不足": {"SYMBOL"},
            "股票代號 2330，ticker 1608": {"SYMBOL"},
            "20D、60D、20 日、60 日": {"PERIOD"},
            "50-day、50 日、50日、200-day、200 日、200日": {"PERIOD"},
            "高於50日與200日均線，52-week、52 週、52週": {"PERIOD"},
            "近 4 季、4季、12 個月、12個月歷史序列不足": {"PERIOD"},
            "4 quarters and 12 months，TTM": {"PERIOD"},
            "資料日期2026-08-30與2026/08/30": {"DATE"},
            "民國115/08/30、115年8月30日": {"DATE", "PERIOD"},
            "V0、V1、V1A、V1.0、AI_ANALYST_CARD_V0": {"VERSION"},
            "FY2023": {"FISCAL_YEAR"},
            "radar:2027.TW:revenue_yoy": {"EVIDENCE_ID"},
        }
        for text, roles in cases.items():
            with self.subTest(text=text):
                tokens = classify_analyst_numbers(text, context)
                self.assertTrue(tokens)
                self.assertLessEqual({item["role"] for item in tokens}, roles)
        self.assertEqual(classify_analyst_numbers("TTM quarter quarters months", context), [])

    def test_financial_values_are_not_exempted_by_structural_numeric_collisions(self):
        _, _, context, _ = self.fixture("2027.TW")
        for text in (
            "P/E 4.0", "价格 50 元", "價格 50 元", "價格50", "ROE 12%", "EPS為4.0", "市盈率約18.33倍",
            "市淨率3.16倍", "現金TWD0050", "負債USD200", "TWD 50日", "price 0050", "P/E 0050",
            "營業利益率12", "growth 4", "ratio 200", "毛利率為１２％", "股價為２０２７元",
            "營收增加4個百分點", "收益12percentage points", "股票的價格達2330", "費用50日圓",
            "近4季資料；P/E4.0，價格50元，ROE12%", "0050 相對市場資料不足；價格0050元",
            "2026-08-30 的 EPS 2026", "價格50日均線為50元", "2026/02/31", "代碼V1，cash 1",
        ):
            with self.subTest(text=text):
                tokens = classify_analyst_numbers(text, context)
                self.assertTrue(any(item["role"] in {"FINANCIAL_VALUE", "UNCLASSIFIED_NUMBER"} for item in tokens), tokens)

    def test_valuation_classification_is_clause_local_and_requires_cited_comparator(self):
        _, _, context, answer = self.fixture("2027.TW")
        for claim in ("合理", "便宜", "昂貴", "低估", "高估", "偏低", "偏高", "非高估", "較低", "較高",
                      "undervalued", "overvalued", "cheap", "expensive", "fairly valued", "lower"):
            for text in (f"估值{claim}。", f"P/E {claim}，但缺少同業比較。", f"估值無法判斷。但估值{claim}。"):
                with self.subTest(text=text):
                    candidate = replace(answer, summary="研究優先度：值得觀察。",
                        findings=[GroundedFinding(text, ["current:trailing_pe"])], next_steps=[], missing_information=[])
                    self.assertTrue(any(isinstance(e, AIAnalystValuationComparatorOverclaimError)
                                        for _, e in collect_analyst_final_errors(candidate, context)))
        for text in (
            "目前已有估值倍數可供觀察，但缺少歷史或同業比較。",
            "缺少比較基準，因此無法判斷估值是否合理。",
            "無法判定估值便宜或昂貴。", "Cannot determine whether valuation is cheap.",
            "需透過同業比較以判斷估值是否偏高。", "需比較估值位於相對高低的哪個區間。",
        ):
            with self.subTest(text=text):
                candidate = replace(answer, summary="研究優先度：值得觀察。",
                    findings=[GroundedFinding(text, ["current:trailing_pe"])], next_steps=[], missing_information=[])
                validate_analyst_final_answer(candidate, context)
        comparator = replace(context.selected_evidence[0], id="current:valuation_peer_comparison",
                             metric="valuation_peer_comparison", value="Verified peer comparison")
        compared_context = replace(context, selected_evidence=[*context.selected_evidence, comparator])
        candidate = replace(answer, summary="研究優先度：值得觀察。", findings=[
            GroundedFinding("目前估值合理。", ["current:trailing_pe"]),
        ], next_steps=[], missing_information=[])
        with self.assertRaises(AIAnalystValuationComparatorOverclaimError):
            validate_analyst_final_answer(candidate, compared_context)
        candidate.findings[0].evidence_ids.append(comparator.id)
        validate_analyst_final_answer(candidate, compared_context)

    def test_complete_validation_collects_numeric_policy_identity_and_semantic_defects(self):
        _, _, context, answer = self.fixture("1608.TW")
        candidate = replace(answer, symbol="9999.TW", findings=[
            GroundedFinding("估值18.33倍而且便宜，可持有。", ["current:trailing_pe", "current:current_price"]),
            GroundedFinding("ROE可供觀察。", ["current:invented"]),
            GroundedFinding("月營收年增與月增方向一致。", ["radar:1608.TW:revenue_yoy"]),
        ])
        before = asdict(candidate)
        with self.assertRaises(Exception) as caught:
            validate_analyst_final_answer(candidate, context)
        defects = caught.exception.validation_defects
        codes = {item["code"] for item in defects}
        self.assertTrue({"FINANCIAL_NUMERIC_NARRATIVE_PRESENT", "VALUATION_COMPARATOR_OVERCLAIM",
                         "AIForbiddenRecommendationError", "AIGroundingError", "MISSING_REQUIRED_EVIDENCE_REFS"} <= codes)
        self.assertTrue(any(item["message"] == "SECTION_ROLE_OVERLAP" for item in defects))
        self.assertEqual(before, asdict(candidate))
        self.assertEqual([(field, type(error), str(error)) for field, error in collect_analyst_final_errors(candidate, context)],
                         [(field, type(error), str(error)) for field, error in collect_analyst_final_errors(candidate, context)])

    def test_relative_research_request_is_not_an_asserted_relative_performance_fact(self):
        _, _, context, answer = self.fixture("2027.TW")
        good = replace(answer, findings=[GroundedFinding(
            "股價高於短中期與長期移動平均線；若欲計算相對強弱比，應另行取得比較資料。",
            ["current:current_price", "current:fifty_day_average", "current:two_hundred_day_average"],
        )], next_steps=[])
        validate_analyst_final_answer(good, context)
        for text in ("短中期相對市場表現偏強。", "相對強弱已確認。", "短中期相對表現偏強。",
                     "短中期相對市場偏強；若欲比較，需補資料。", "相對市場已確認，若欲補足比較資料可繼續研究。",
                     "相對市場表現偏強但有缺口。"):
            bad = replace(good, findings=[GroundedFinding(text, good.findings[0].evidence_ids)])
            with self.subTest(text=text), self.assertRaises(AIAnalystShortlistError):
                validate_analyst_final_answer(bad, context)

    def test_new_request_still_rejects_historical_extra_patch_slots(self):
        result, calls, _, _ = self.replay("2027.TW", historical_request=False)
        self.assertEqual(len(calls[0]["request"]["slots"]), 1)
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertIn("Unknown or duplicate Analyst patch slot", result["cards"][0]["missing_evidence"][0])

    def test_real_candidate_defect_collection_is_deterministic_and_nonmutating(self):
        for symbol in REAL_ANALYST_CAPTURE:
            with self.subTest(symbol=symbol):
                _, _, context, answer = self.fixture(symbol)
                before = asdict(answer)
                first = build_analyst_repair_request(answer, context)
                self.assertEqual(first, build_analyst_repair_request(answer, context))
                self.assertEqual(before, asdict(answer))

    def test_REAL_CAPTURE_2027_REPLAY_passes_with_original_request_and_single_repair(self):
        result, calls, context, original = self.replay("2027.TW")
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]["request"]["slots"]), 4)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertEqual(result["stage1_success_count"], 1, result["cards"])
        self.assertEqual(self.final_defects, [])
        self.assertIsNone(result["synthesis"])

    def fixture(self, symbol):
        item = json.loads(json.dumps(REAL_ANALYST_CAPTURE[symbol]))
        stock = Stock(**item["stock"])
        context = build_analyst_model_context(build_shortlist_selected_context(
            item["row"], stock=stock, generated_at=NOW,
            radar_evidence_resolver=lambda _: item["radar"],
        ))
        answer = generate_analyst_grounded_answer(
            question=build_analyst_stage_one_question(context), selected_context=context,
            client=SimpleNamespace(create_grounded_answer=lambda **_: SimpleNamespace(
                output_text=json.dumps(item["responses"]["initial"], ensure_ascii=False),
            )), config=AIResearchConfig("mock", 2400, "minimal", "low", 30),
        )
        return item, stock, context, answer

    def replay(self, symbol, response=None, *, historical_request=True):
        item, stock, context, answer = self.fixture(symbol)
        calls = []
        self.final_defects = []
        request = build_analyst_repair_request(answer, context)
        if historical_request:
            request["slots"] = json.loads(json.dumps(REAL_ANALYST_REPAIR_RECORDS[symbol]["slots"]))
        def final_check(*args):
            try:
                return validate_analyst_final_answer(*args)
            except Exception as error:
                self.final_defects.extend(getattr(error, "validation_defects", ()))
                raise
        def repair(**kwargs):
            calls.append(kwargs)
            return generate_analyst_repair_patch(
                **kwargs, client=SimpleNamespace(create_grounded_answer=lambda **_: SimpleNamespace(
                    output_text=json.dumps(response if response is not None else REAL_ANALYST_REPAIR_RECORDS[symbol]["response"], ensure_ascii=False),
                )), config=AIResearchConfig("mock", 2400, "minimal", "low", 30),
            )
        with patch("socket.socket.connect", side_effect=AssertionError("Offline replay")), patch(
            "ai_research_service.numeric_claim_metric", side_effect=AssertionError("No prose metric inference"),
        ), patch(__name__ + ".build_analyst_repair_request", return_value=request), patch(
            "ai_analyst_shortlist.validate_analyst_final_answer", side_effect=final_check,
        ):
            result = _analyze_research_shortlist(
                [item["row"]], stock_loader=lambda _: stock,
                radar_evidence_resolver=lambda _: item["radar"],
                grounded_generator=lambda **_: answer, repair_generator=repair, generated_at=NOW,
            )
        return result, calls, context, answer

    def test_REAL_CAPTURE_1216_REPLAY_financial_repair_is_rejected(self):
        result, calls, context, answer = self.replay("1216.TW")
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertIn("FINANCIAL_NUMERIC_NARRATIVE_PRESENT", result["cards"][0]["missing_evidence"][0])
        self.assertEqual(calls[0]["request"]["slots"][0]["slot_id"], "findings:3")
        self.assertEqual(answer.findings[3].evidence_ids, ["current:trailing_pe", "current:price_to_book"])
        self.assertIsNone(result["synthesis"])

    def test_REAL_CAPTURE_1608_REPLAY_rejects_valuation_assertions_not_windows(self):
        result, calls, context, answer = self.replay("1608.TW")
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual([slot["slot_id"] for slot in calls[0]["request"]["slots"]], ["findings:2"])
        self.assertEqual({(d["field"], d["code"]) for d in self.final_defects}, {
            ("summary", "VALUATION_COMPARATOR_OVERCLAIM"), ("findings:2", "VALUATION_COMPARATOR_OVERCLAIM"),
        })

    def test_2027_exact_initial_collects_all_defects_before_any_hard_numeric_gate(self):
        item, stock, context, answer = self.fixture("2027.TW")
        before = asdict(answer)
        request = build_analyst_repair_request(answer, context)
        self.assertEqual([slot["slot_id"] for slot in request["slots"]], [
            "findings:2",
        ])
        self.assertTrue(all(slot["allowed_patch_fields"] == ["rewritten_text"] for slot in request["slots"]))
        self.assertEqual(asdict(answer), before)
        self.assertLessEqual(len(request["question"]), MAX_RESEARCH_QUESTION_LENGTH)

    def test_program_owned_merge_and_renderer_accept_complete_offline_control_patches(self):
        # Control patches are explicitly synthetic, NOT claimed as real-AI success.
        rewrites = {
            "1216.TW": {"findings:3": "估值倍數仍需與同業或自身歷史脈絡比較。"},
            "2027.TW": {
                "findings:2": "估值倍數仍需補足同業與歷史比較。",
            },
        }
        for symbol, slots in rewrites.items():
            with self.subTest(symbol=symbol):
                item, stock, context, original = self.fixture(symbol)
                before = asdict(original)
                request = build_analyst_repair_request(original, context)
                response = {"patches": [{"slot_id": key, "rewritten_text": text} for key, text in slots.items()]}
                merged = apply_analyst_repair_patch(original, request, response, context)
                self.assertEqual(asdict(original), before)
                self.assertEqual(merged.symbol, original.symbol)
                self.assertEqual(merged.summary, original.summary)
                self.assertEqual(merged.metadata, original.metadata)
                self.assertEqual([f.evidence_ids for f in merged.findings], [f.evidence_ids for f in original.findings])
                self.assertEqual(len(merged.missing_information), len(original.missing_information))
                if symbol == "2027.TW":
                    for ref in ("radar:2027.TW:revenue_yoy", "radar:2027.TW:revenue_mom"):
                        self.assertIn(ref, merged.next_steps[0])
                result, calls, _, _ = self.replay(symbol, response, historical_request=False)
                self.assertEqual(result["stage1_success_count"], 1, result["cards"])
                self.assertEqual(len(calls), 1)
                full_context = build_shortlist_selected_context(item["row"], stock=stock, generated_at=NOW,
                    radar_evidence_resolver=lambda _: item["radar"])
                self.assertEqual(result["cards"][0]["missing_evidence"], build_analyst_missing_evidence(full_context)[0])

    def test_unknown_identity_or_references_fail_before_repair_on_real_shape(self):
        for symbol in REAL_ANALYST_CAPTURE:
            item, stock, context, answer = self.fixture(symbol)
            for malformed in (
                replace(answer, symbol="9999.TW"),
                replace(answer, findings=[GroundedFinding(answer.findings[0].statement, ["current:invented"])]),
                replace(answer, missing_information=["缺少 missing:current:invented"]),
            ):
                with self.subTest(symbol=symbol, answer=malformed):
                    with self.assertRaises(AIGroundingError):
                        build_analyst_repair_request(malformed, context)

    def test_numeric_free_guard_does_not_depend_on_language_word_boundaries(self):
        item, stock, context, answer = self.fixture("1216.TW")
        for text in ("市盈率約為18.33倍", "現價為18.33元", "ROE為18.33%", "ROE為１８.３３％", "資料為18"):
            with self.subTest(text=text), self.assertRaises(AIAnalystFinancialNumericNarrativeError):
                validate_analyst_grounded_answer(replace(answer,
                    findings=[GroundedFinding(text, ["current:current_price"])],
                    missing_information=[], next_steps=[]), context)

    def test_next_check_patch_cannot_introduce_even_an_existing_unlocked_reference(self):
        item, stock, context, answer = self.fixture("2027.TW")
        request = build_analyst_repair_request(answer, context)
        request["slots"] = REAL_ANALYST_REPAIR_RECORDS["2027.TW"]["slots"]
        patches = [{"slot_id": slot["slot_id"], "rewritten_text": "研究脈絡仍需進一步確認。"}
                   for slot in request["slots"]]
        patches[-1]["rewritten_text"] += " current:current_price"
        with self.assertRaisesRegex(AIGroundingError, "unauthorized evidence reference"):
            apply_analyst_repair_patch(answer, request, {"patches": patches}, context)


class SectionBoundedAnalystTest(unittest.TestCase):
    def setUp(self):
        self.network = patch("socket.socket.connect", side_effect=AssertionError("Offline architecture sprint"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.row = shortlist_row()
        self.context = build_shortlist_selected_context(self.row, stock=cached_stock(), generated_at=NOW)
        self.sections = build_analyst_section_contexts(self.context)

    def card(self, **changes):
        output = section_answer(self.context)
        output.update(changes)
        return assemble_section_analyst_card(output, self.context, self.row)

    def assert_local_rejection(self, slot, text):
        card = self.card(**{slot: text})
        self.assertEqual(card["section_status"][slot], "REJECTED")
        self.assertEqual(sum(s == "VALID" for s in card["section_status"].values()), 3)
        field = ANALYST_TEXT_SLOTS[slot][0]
        self.assertEqual(card[field], [ANALYST_SLOT_FALLBACK] if slot == "opportunity_text" else ANALYST_SLOT_FALLBACK)
        self.assertNotIn(text, json.dumps(card, ensure_ascii=False))
        projected = build_stage_two_cards([card])[0]
        self.assertNotIn(field, projected)
        self.assertNotIn(text, json.dumps(projected, ensure_ascii=False))
        return card

    def test_schema_is_only_available_slots_and_priority_without_model_structures(self):
        schema = build_analyst_section_format(self.context)["schema"]
        self.assertEqual(set(schema["properties"]), set(ANALYST_TEXT_SLOTS) | {"priority_label", "priority_reason"})
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["priority_label"]["enum"], ["優先深入研究", "值得觀察", "證據不足"])
        self.assertTrue(all(prop["type"] == "string" for prop in schema["properties"].values()))
        for forbidden in ("findings", "evidence_refs", "numeric_mentions", "symbol", "missing_information"):
            self.assertNotIn(forbidden, schema["properties"])

    def test_model_cannot_supply_structures_or_unrequested_sections(self):
        for key in ("symbol", "findings", "evidence_refs", "numeric_mentions", "next_checks", "section_status"):
            with self.subTest(key=key), self.assertRaises(AIAnalystShortlistError):
                self.card(**{key: []})
        self.assert_local_rejection("opportunity_text", "請參考 radar:2330.TW:revenue_yoy")

    def test_section_evidence_is_partitioned_with_only_explicit_relative_overlap(self):
        payload = build_analyst_section_request(self.context)
        self.assertNotIn("evidence", payload)
        for slot, section in self.sections.items():
            metrics = {item.metric for item in section.selected_evidence}
            self.assertLessEqual(metrics, ANALYST_TEXT_SLOTS[slot][1])
            self.assertEqual([item["id"] for item in payload["sections"][slot]["evidence"]],
                             [item.id for item in section.selected_evidence])
        self.assertFalse(payload["sections"]["valuation_text"]["comparator_available"])
        self.assertTrue({"rel_return_20d", "rel_return_60d"} <=
                        {item.metric for item in self.sections["opportunity_text"].selected_evidence})
        self.assertTrue({"rel_return_20d", "rel_return_60d"} <=
                        {item.metric for item in self.sections["market_text"].selected_evidence})

    def test_refs_are_exact_program_owned_deterministic_and_do_not_mutate_context(self):
        before = asdict(self.context)
        first = self.card()
        second = self.card()
        self.assertEqual(first, second)
        for slot, section in self.sections.items():
            self.assertEqual(first["section_evidence_refs"][slot], [item.id for item in section.selected_evidence])
        self.assertEqual(first["evidence_refs"], sorted({item.id for section in self.sections.values()
                                                      for item in section.selected_evidence}))
        self.assertEqual(asdict(self.context), before)

    def test_sparse_1216_omits_unavailable_sections_from_request(self):
        row = shortlist_row("1216.TW", rel20=None, rel60=None)
        context = build_shortlist_selected_context(row, stock=acceptance_stock("1216.TW"), generated_at=NOW)
        self.assertEqual(set(build_analyst_section_request(context)["sections"]), {"opportunity_text"})
        schema = build_analyst_section_format(context)["schema"]
        self.assertEqual(set(schema["properties"]), {"opportunity_text", "priority_label", "priority_reason"})
        card = assemble_section_analyst_card(section_answer(context), context, row)
        for slot in ("fundamental_text", "valuation_text", "market_text"):
            self.assertEqual(card["section_status"][slot], "UNAVAILABLE")
            self.assertEqual(card[ANALYST_TEXT_SLOTS[slot][0]], ANALYST_UNAVAILABLE)
        self.assertEqual(card["section_status"]["opportunity_text"], "VALID")

    def test_missing_or_malformed_single_slot_is_local(self):
        for value in (None, [], {}, 123, "", "  "):
            with self.subTest(value=value):
                card = self.card(fundamental_text=value)
                self.assertEqual(card["section_status"]["fundamental_text"], "REJECTED")
                self.assertEqual(sum(s == "VALID" for s in card["section_status"].values()), 3)
        output = section_answer(self.context)
        del output["fundamental_text"]
        card = assemble_section_analyst_card(output, self.context, self.row)
        self.assertEqual(card["section_status"]["fundamental_text"], "REJECTED")

    def test_numeric_rich_opportunity_is_rejected_locally(self):
        self.assert_local_rejection("opportunity_text", "營收年增25%，提供研究線索。")

    def test_numeric_rich_fundamental_is_rejected_locally(self):
        self.assert_local_rejection("fundamental_text", "ROE 12%，獲利成長為正。")

    def test_numeric_rich_valuation_is_rejected_locally(self):
        self.assert_local_rejection("valuation_text", "P/E 4.0，目前可供比較。")

    def test_numeric_rich_market_is_rejected_locally(self):
        for text in ("價格 50 元", "TWD 37.85", "股價２０２７元", "均線價值200元"):
            with self.subTest(text=text):
                self.assert_local_rejection("market_text", text)

    def test_recommendation_violations_are_rejected_without_sanitization(self):
        for text in ("可以持有。", "建議買進。", "應該賣出。", "可加碼。", "應減碼。", "目標價可提高。",
                     "預期報酬率更高。", "Buy", "Sell", "Hold"):
            with self.subTest(text=text):
                self.assert_local_rejection("opportunity_text", text)

    def test_valuation_classification_is_local_and_requires_comparator(self):
        for text in ("估值便宜。", "估值合理。", "目前低估。", "目前高估。", "非高估。", "倍數相對低檔。",
                     "P/E 顯著較低。", "undervalued", "fairly valued"):
            with self.subTest(text=text):
                self.assert_local_rejection("valuation_text", text)
        self.assertEqual(self.card()["section_status"]["valuation_text"], "VALID")

    def test_cross_section_claims_fail_closed(self):
        for slot, text in (
            ("opportunity_text", "ROE 強勁。"), ("opportunity_text", "資產負債表穩健。"),
            ("opportunity_text", "估值倍數可供研究。"), ("fundamental_text", "價格呈上漲趨勢。"),
            ("valuation_text", "股價高於均線。"), ("market_text", "營業利益率顯示獲利改善。"),
            ("market_text", "現金流已轉正。"),
        ):
            with self.subTest(slot=slot, text=text):
                self.assert_local_rejection(slot, text)

    def test_unavailable_metric_within_section_is_not_implicitly_grounded(self):
        context = replace(self.context, selected_evidence=[item for item in self.context.selected_evidence
                                                          if item.metric != "return_on_equity"])
        output = section_answer(context)
        output["fundamental_text"] = "ROE 已改善。"
        card = assemble_section_analyst_card(output, context, self.row)
        self.assertEqual(card["section_status"]["fundamental_text"], "REJECTED")

    def test_missing_next_checks_risks_and_contradictions_are_program_owned(self):
        card = self.card()
        labels, checks = build_analyst_missing_evidence(self.context)
        self.assertEqual(card["missing_evidence"], labels)
        self.assertEqual(card["next_checks"], checks)
        self.assertEqual(card["contradictions"], detect_contradictions(self.context))
        self.assertEqual(card["risks"], list(dict.fromkeys([*detect_extreme_value_warnings(self.context), *labels])))
        self.assertEqual(len(labels), len(set(labels)))
        self.assertNotRegex(" ".join(labels + checks), r"(?:missing|context|global):")
        context = build_shortlist_selected_context(shortlist_row(mom=-0.1), stock=cached_stock(), generated_at=NOW)
        contradicted = assemble_section_analyst_card(section_answer(context), context, self.row)
        self.assertIn("Revenue YoY 為正，但 Revenue MoM 為負。", contradicted["contradictions"])

    def test_priority_is_exact_enum_and_invalid_values_fall_back(self):
        for label in ("優先深入研究", "值得觀察", "證據不足"):
            self.assertEqual(self.card(priority_label=label)["research_priority"], label)
        for label in ("買進", " 優先深入研究 ", None, [], {}, 1):
            with self.subTest(label=label):
                self.assertEqual(self.card(priority_label=label)["research_priority"], "證據不足")

    def test_priority_reason_failure_does_not_destroy_card(self):
        for text in ("ROE 12%", "可以持有。", "估值相對低檔。", "目標價仍可提高。", None, []):
            with self.subTest(text=text):
                card = self.card(priority_reason=text)
                self.assertEqual(card["priority_reason"], "")
                self.assertTrue(all(state == "VALID" for state in card["section_status"].values()))

    def test_zero_valid_slots_is_evidence_only_and_cannot_enter_stage_two(self):
        card = self.card(**{slot: "價格50元" for slot in ANALYST_TEXT_SLOTS}, priority_label="優先深入研究")
        self.assertTrue(card["verified_evidence"])
        self.assertEqual(card["research_priority"], "證據不足")
        self.assertEqual(card["priority_reason"], "")
        with self.assertRaises(AIAnalystShortlistError):
            build_stage_two_cards([card])

    def test_one_valid_core_slot_is_sufficient_but_priority_reason_alone_is_not(self):
        for valid in ANALYST_TEXT_SLOTS:
            output = section_answer(self.context)
            for slot in ANALYST_TEXT_SLOTS:
                if slot != valid:
                    output[slot] = "ROE 12%"
            card = assemble_section_analyst_card(output, self.context, self.row)
            self.assertEqual(sum(state == "VALID" for state in card["section_status"].values()), 1)
            self.assertTrue(build_stage_two_cards([card]))

    def test_structural_periods_and_benchmark_do_not_trigger_numeric_failure(self):
        for text in ("近4季與12個月資料仍需查核。", "20D、60D 相對0050資料可供觀察。",
                     "0050.TW 相對市場資料仍需查核。", "V1A資料日期2026-08-30。"):
            with self.subTest(text=text):
                card = self.card(opportunity_text=text)
                self.assertEqual(card["section_status"]["opportunity_text"], "VALID")
        card = self.card(market_text="股價高於50-day與200-day均線，52-week區間仍需觀察。")
        self.assertEqual(card["section_status"]["market_text"], "VALID")

    def test_cross_company_symbol_is_rejected_locally(self):
        self.assert_local_rejection("market_text", "1608.TW 股價高於均線。")
        self.assert_local_rejection("market_text", "股票代號1608，目前價格可供研究。")

    def test_global_identity_corruption_stops_before_generation(self):
        calls = []
        result = analyze_section_shortlist([self.row], stock_loader=lambda _: cached_stock("9999.TW"),
                    section_generator=lambda **kw: calls.append(kw), generated_at=NOW)
        self.assertEqual(calls, [])
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["provider_call_count"], 0)

    def test_duplicate_companies_cannot_trigger_multiple_generation_calls(self):
        calls = []
        with self.assertRaises(AIAnalystShortlistError):
            analyze_section_shortlist([self.row, self.row], stock_loader=cached_stock,
                                      section_generator=lambda **kw: calls.append(kw), generated_at=NOW)
        self.assertEqual(calls, [])

    def captured_card(self, symbol):
        item = REAL_ANALYST_CAPTURE[symbol]
        context = build_shortlist_selected_context(item["row"], stock=Stock(**item["stock"]), generated_at=NOW,
                                                   radar_evidence_resolver=lambda _: item["radar"])
        initial = item["responses"]["initial"]
        output = section_answer(context)
        # Exact captured prose; field routing is a test migration, not a new AI response.
        output.update(opportunity_text=initial["findings"][0]["statement"],
                      fundamental_text=initial["findings"][1]["statement"], priority_reason=initial["summary"])
        for patch_item in REAL_ANALYST_REPAIR_RECORDS[symbol]["response"]["patches"]:
            if patch_item["slot_id"] == ("findings:3" if symbol == "1216.TW" else "findings:2"):
                output["valuation_text"] = patch_item["rewritten_text"]
            elif symbol == "2027.TW" and patch_item["slot_id"] == "findings:3":
                output["market_text"] = patch_item["rewritten_text"]
        return assemble_section_analyst_card(output, context, item["row"]), context

    def test_REAL_CAPTURE_1216_numeric_valuation_rejected_but_card_usable(self):
        card, _ = self.captured_card("1216.TW")
        self.assertEqual(card["section_status"]["valuation_text"], "REJECTED")
        self.assertEqual(card["section_status"]["opportunity_text"], "VALID")
        self.assertNotIn("18.33倍", json.dumps(build_stage_two_cards([card]), ensure_ascii=False))

    def test_REAL_CAPTURE_1608_valuation_and_priority_overclaim_are_local(self):
        card, _ = self.captured_card("1608.TW")
        self.assertEqual(card["section_status"]["valuation_text"], "REJECTED")
        self.assertEqual(card["priority_reason"], "")
        self.assertEqual(card["section_status"]["fundamental_text"], "VALID")
        self.assertTrue(build_stage_two_cards([card]))

    def test_REAL_CAPTURE_2027_benchmark_and_reporting_periods_are_usable(self):
        card, context = self.captured_card("2027.TW")
        self.assertEqual(card["section_status"]["market_text"], "VALID")
        self.assertEqual(card["section_status"]["valuation_text"], "VALID")
        self.assertTrue(build_stage_two_cards([card]))
        sections = build_analyst_section_contexts(context)
        for item in REAL_ANALYST_REPAIR_RECORDS["2027.TW"]["response"]["patches"]:
            if item["slot_id"] in {"missing_information:0", "next_steps:0"}:
                self.assertFalse(any(token["role"] in {"FINANCIAL_VALUE", "UNCLASSIFIED_NUMBER"}
                                     for token in classify_analyst_numbers(item["rewritten_text"], context)))
                # Old missing-data tasks are no longer AI slots; absent revenue cannot be
                # laundered into fundamental evidence by a harmless reporting-period token.
                with self.assertRaises(AIGroundingError):
                    validate_analyst_section_text(item["rewritten_text"], sections["fundamental_text"])
        validate_analyst_section_text("近4季與12個月獲利序列仍需進一步查核。", sections["fundamental_text"])

    def test_refreshed_three_company_rich_evidence_is_preserved(self):
        for symbol in ("1216.TW", "1608.TW", "2027.TW"):
            with self.subTest(symbol=symbol):
                card, context = self.captured_card(symbol)
                self.assertEqual(set(build_analyst_section_contexts(context)), set(ANALYST_TEXT_SLOTS))
                self.assertEqual(card["verified_evidence"], build_verified_evidence(context))
                self.assertEqual(card["evidence_dates"], __import__("ai_analyst_shortlist")._evidence_dates(context))

    def test_provider_schema_and_call_count_are_single_generation(self):
        calls = []
        class Client:
            def create_grounded_answer(inner, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(output_text=json.dumps(section_answer(self.context), ensure_ascii=False))
        with patch("ai_analyst_shortlist.generate_analyst_repair_patch", side_effect=AssertionError("No repair")), patch(
            "ai_research_service.numeric_claim_metric", side_effect=AssertionError("No numeric metric inference")), patch(
            "ai_analyst_shortlist.OpenAIResearchClient", return_value=Client()), patch(
            "ai_analyst_shortlist.get_ai_research_config", return_value=AIResearchConfig("mock", 2400, "minimal", "low", 30)), patch(
            "ai_analyst_shortlist.generate_analyst_grounded_answer", side_effect=AssertionError("Retired full card")), patch(
            "ai_analyst_shortlist.build_analyst_repair_request", side_effect=AssertionError("No repair collector")), patch(
            "ai_analyst_shortlist.apply_analyst_repair_patch", side_effect=AssertionError("No repair merge")):
            result = analyze_section_shortlist([self.row], stock_loader=cached_stock, generated_at=NOW)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["provider_call_count"], 1)
        self.assertEqual(result["stage1_success_count"], 1)
        self.assertEqual(result["stage1_format_repair_count"], 0)
        self.assertEqual(result["stage1_policy_regeneration_count"], 0)
        self.assertEqual(calls[0]["response_format"], build_analyst_section_format(self.context))
        self.assertLessEqual(len(calls[0]["payload"]["question"]), MAX_RESEARCH_QUESTION_LENGTH)

    def test_stage_two_receives_only_validated_text_and_no_raw_evidence(self):
        stage1_calls, stage2_cards = [], []
        def generate(*, selected_context):
            stage1_calls.append(selected_context.symbol)
            response = section_answer(selected_context)
            response["valuation_text"] = "估值18.33倍，便宜可持有。"
            return response
        def synthesis(*, cards):
            stage2_cards.extend(cards)
            return valid_synthesis(cards)
        result = analyze_section_shortlist([self.row, shortlist_row("2454.TW")], stock_loader=cached_stock,
                    section_generator=generate, synthesis_generator=synthesis, generated_at=NOW)
        self.assertEqual(stage1_calls, ["2330.TW", "2454.TW"])
        self.assertEqual(result["provider_call_count"], 3)
        self.assertEqual(result["stage1_success_count"], 2)
        for card in stage2_cards:
            for key in ("valuation_context", "verified_evidence", "verified_evidence_summary", "evidence_refs", "section_evidence_refs"):
                self.assertNotIn(key, card)
        self.assertNotIn("18.33", json.dumps(stage2_cards, ensure_ascii=False))
        self.assertNotIn("持有", json.dumps(stage2_cards, ensure_ascii=False))

    def test_zero_valid_and_provider_failures_are_isolated_without_second_calls(self):
        calls, compared = [], []
        def generate(*, selected_context):
            calls.append(selected_context.symbol)
            if selected_context.symbol == "2454.TW":
                raise AIProviderError("private raw response with financial values")
            output = section_answer(selected_context)
            output.update({slot: "價格50元" for slot in build_analyst_section_contexts(selected_context)})
            return output
        result = analyze_section_shortlist([self.row, shortlist_row("2454.TW")], stock_loader=cached_stock,
                    section_generator=generate, synthesis_generator=lambda **kw: compared.append(kw), generated_at=NOW)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(compared, [])
        self.assertNotIn("private raw response", json.dumps(result))

    def test_final_card_invariants_reject_unsafely_replaced_fallback(self):
        card = self.card(valuation_text="便宜。")
        card["valuation_context"] = "可以持有。"
        with self.assertRaises(AIAnalystShortlistError):
            validate_analyst_card(card)


if __name__ == "__main__":
    unittest.main()
