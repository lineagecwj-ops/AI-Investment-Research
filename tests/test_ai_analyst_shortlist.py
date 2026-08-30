import json
import re
import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_analyst_shortlist import (
    AI_ANALYST_SHORTLIST_MAX_SIZE,
    AIAnalystCardFormatError,
    AIAnalystMissingRequiredEvidenceRefsError,
    AIAnalystShortlistError,
    AIAnalystStageTwoNumericError,
    AIAnalystStageTwoPolicyError,
    AIAnalystValuationComparatorOverclaimError,
    SYNTHESIS_INSTRUCTIONS,
    analyze_research_shortlist,
    ANALYST_MODEL_EVIDENCE_METRICS,
    build_analyst_model_context,
    build_analyst_format_repair_question,
    build_analyst_missing_evidence,
    build_analyst_policy_regeneration_question,
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
        GroundedFinding("Earnings Growth 為 362.20%。", ["current:earnings_growth"]),
        GroundedFinding(
            "Trailing P/E 為 9.70、P／B 為 1.51。",
            ["current:trailing_pe", "current:price_to_book"],
        ),
        GroundedFinding(
            "目前股價 TWD 48.4，50-day average TWD 44.08，200-day average TWD 39.55。",
            ["current:current_price", "current:fifty_day_average", "current:two_hundred_day_average"],
        ),
    ])


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

    def _run_adapter_findings(self, outputs, *, stock=None):
        """Exercise the real adapter's validate-before-return path without any network."""
        payloads, contexts = [], []
        class FakeClient:
            def create_grounded_answer(_self, **kwargs):
                payload = kwargs["payload"]
                payloads.append(payload)
                findings = outputs[len(payloads) - 1]
                data = {
                    "symbol": payload["symbol"], "question_type": payload["question_type"],
                    "summary": "研究優先度：值得觀察", "findings": findings,
                    "limitations": [], "missing_information": [], "next_steps": [],
                }
                return SimpleNamespace(output_text=json.dumps(data, ensure_ascii=False), id="mock")

        def generate(**kwargs):
            contexts.append(kwargs["selected_context"])
            return generate_grounded_research_answer(
                **kwargs, client=FakeClient(),
                config=AIResearchConfig("mock", 2400, "minimal", "low", 30), generated_at=NOW,
            )
        result = analyze_research_shortlist(
            [shortlist_row("1608.TW", yoy=.4267, mom=.1496, rel20=None, rel60=None)],
            stock_loader=lambda _: stock or Stock(symbol="1608.TW"),
            grounded_generator=generate, synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )
        if len(contexts) == 2:
            self.assertIs(contexts[0], contexts[1])
        return result, payloads

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
        self.assertIn("HOLD_ACTION / 持有", payloads[1]["question"])
        self.assertLessEqual(len(payloads[1]["question"]), 1500)
        self.assertEqual({k: v for k, v in payloads[0].items() if k != "question"},
                         {k: v for k, v in payloads[1].items() if k != "question"})
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
            {"statement": "Revenue YoY = 99%", "evidence_ids": ["radar:1608.TW:revenue_yoy"]},
            {"statement": "Current Price = USD 48.4", "evidence_ids": ["current:current_price"]},
            {"statement": "Current Price = TWD 50", "evidence_ids": ["current:current_price"]},
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
        error = AIForbiddenRecommendationError(grounded_answer(context), rule="HOLD_ACTION", term="持有", field="findings")
        self.assertEqual(MAX_RESEARCH_QUESTION_LENGTH, 1500)
        self.assertLessEqual(len(build_analyst_policy_regeneration_question(context, error)), 1500)

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

    def test_optional_ai_next_check_requires_available_reference_and_exact_number(self):
        row = shortlist_row("2027.TW")
        context = build_shortlist_selected_context(row, stock=cached_stock("2027.TW"), generated_at=NOW)
        answer = grounded_answer(context)
        baseline = normalize_analyst_card(replace(answer, next_steps=[]), context, row)
        ungrounded = normalize_analyst_card(replace(answer, next_steps=["任意新增研究論點。"]), context, row)
        self.assertEqual(baseline["next_checks"], ungrounded["next_checks"])
        for text in ("確認 Revenue YoY = 99%（radar:2027.TW:revenue_yoy）。",
                     "確認 current:invented_metric。"):
            with self.subTest(text=text), self.assertRaises(AIGroundingError):
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
        self.assertIs(contexts[0], contexts[1])
        self.assertIn("exact supplied CATALOG evidence_ids", questions[1])
        self.assertIn("radar:1216.TW:revenue_yoy", questions[1])
        self.assertIn("radar:1216.TW:revenue_mom", questions[1])
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
        self.assertIs(contexts[0], contexts[1])
        self.assertIn("no peer or historical comparator", questions[1])
        self.assertIn("current:trailing_pe", questions[1])
        self.assertIn("current:price_to_book", questions[1])
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
        question = build_analyst_format_repair_question(context, AIAnalystValuationComparatorOverclaimError())
        self.assertIn("no peer or historical comparator", question)
        self.assertLessEqual(len(question), MAX_RESEARCH_QUESTION_LENGTH)

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
            return grounded_answer_with_findings(selected_context, [GroundedFinding(
                f"Revenue YoY 為 {yoy:.2%}，Revenue MoM 為 {mom:.2%}。",
                [f"radar:{symbol}:revenue_yoy", f"radar:{symbol}:revenue_mom"],
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
        self.assertIn(f"Revenue YoY 為 {yoy:.2%}，Revenue MoM 為 {mom:.2%}。", card["opportunity_interpretation"])

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

    def test_2027_section_overlap_gets_one_bounded_format_repair(self):
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

        self.assertEqual(result["stage1_success_count"], 1)
        self.assertEqual(result["stage1_format_repair_count"], 1)
        self.assertEqual(result["provider_call_count"], 2)
        self.assertEqual(len(questions), 2)
        self.assertIn("FORMAT REPAIR ONLY", questions[1])
        self.assertIn("radar:2027.TW:revenue_yoy", questions[1])
        self.assertLessEqual(len(questions[1]), MAX_RESEARCH_QUESTION_LENGTH)
        self.assertIn("估值倍數", card["valuation_context"])
        self.assertIn("絕對價格趨勢", card["market_confirmation"])

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
                "Revenue YoY 為 18.85%。", ["radar:2027.TW:revenue_yoy"],
            )]),
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

    def test_exact_grounded_numeric_narrative_passes_but_wrong_value_fails_closed(self):
        row = shortlist_row("2027.TW", mom=0.0597)
        context = build_shortlist_selected_context(row, stock=cached_stock("2027.TW"), generated_at=NOW)
        answer = grounded_answer_with_findings(context, [GroundedFinding(
            "Revenue MoM 為 50%。",
            ["radar:2027.TW:revenue_mom"],
        )])

        result = analyze_research_shortlist(
            [row],
            stock_loader=lambda _symbol: cached_stock("2027.TW"),
            grounded_generator=lambda **_kwargs: answer,
            synthesis_generator=lambda *, cards: valid_synthesis(cards),
            generated_at=NOW,
        )

        self.assertEqual(result["stage1_success_count"], 0)
        self.assertEqual(result["cards"][0]["research_priority"], "證據不足")
        self.assertEqual(result["stage1_format_repair_count"], 0)

        supported_but_repeated = grounded_answer_with_findings(context, [GroundedFinding(
            "Revenue MoM 為 5.97%。",
            ["radar:2027.TW:revenue_mom"],
        )])
        validate_grounded_ai_answer(supported_but_repeated, context)
        card = normalize_analyst_card(supported_but_repeated, context, row)

        self.assertIn("Revenue MoM 為 5.97%。", card["opportunity_interpretation"])

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

    def test_one_company_numeric_grounding_failure_is_isolated(self):
        def generator(*, selected_context, **_kwargs):
            if selected_context.symbol == "2454.TW":
                return grounded_answer_with_findings(selected_context, [GroundedFinding(
                    "REL_RETURN_60D 為 99.99%。",
                    ["radar:2454.TW:rel_return_60d"],
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
        self.assertIn("unsupported_percentage_claim", failed["missing_evidence"][0])
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
            ("main_unresolved_risk", "Current Price 為 TWD 48.40。", "TWD 48.40", "NON_PERCENTAGE"),
            ("cross_company_observations", "50-day 平均線仍待確認。", None, None),
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


if __name__ == "__main__":
    unittest.main()
