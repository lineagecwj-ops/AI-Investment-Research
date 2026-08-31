import json
import sys
import unittest
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ai_config import AIResearchConfig
from ai_analyst_shortlist import AIAnalystFinancialNumericNarrativeError
from ai_research_service import AIGroundingError
from ai_research_service import AIProviderError
from ai_research_service import AIResearchError
from catalyst_event import CatalystEventType
from catalyst_event import EventConflictStatus
from catalyst_event import EventTemporalStatus
from catalyst_event import EventValidationStatus
from catalyst_event import ValidatedCatalystEvent
from catalyst_impact import HypothesisStatus
from catalyst_impact import ImpactChannel
from catalyst_impact_service import MAX_AI_CALLS_PER_COMPANY_RUN
from catalyst_impact_service import ApprovedSupportingEvidence
from catalyst_impact_service import CatalystImpactServiceError
from catalyst_impact_service import DuplicateEventContextConflictError
from catalyst_impact_service import build_event_impact_context
from catalyst_impact_service import build_event_impact_payload
from catalyst_impact_service import build_impact_hypothesis_id
from catalyst_impact_service import generate_company_event_impact_hypotheses
from catalyst_impact_service import generate_event_impact_hypothesis
from external_source import CompanyAssociationStatus
from external_source import SourceTemporalEvidence
from external_source import TemporalEvidenceBasis
from external_source import TemporalKind
from external_source import TemporalPrecision
from research_context import EvidenceItem
from research_context import MissingDataItem
from research_context_selector import ResearchQuestionType
from research_context_selector import SelectedResearchContext


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)
TIME = SourceTemporalEvidence(
    value=date(2026, 8, 11), precision=TemporalPrecision.DATE,
    kind=TemporalKind.EVENT_ANNOUNCED_AT, basis=TemporalEvidenceBasis.SOURCE_SNIPPET_EXACT_DATE,
    raw_text="2026-08-11",
)
CONFIG = AIResearchConfig("mock", 800, "minimal", "low", 30)


def event(event_id="event_1216_revenue", status=EventValidationStatus.VALIDATED, conflict=EventConflictStatus.NONE):
    return ValidatedCatalystEvent(
        event_id=event_id, target_symbol="1216.TW", target_company_name="統一",
        event_type=CatalystEventType.REVENUE_UPDATE,
        event_fact="統一(1216)於 2026-08-11 公告 7 月合併營收。",
        event_temporal_evidence=TIME, event_temporal_status=EventTemporalStatus.TIME_CONFIRMED,
        source_ids=("source:1216:revenue",), primary_source_id="source:1216:revenue",
        support_count=1, event_key=event_id, candidate_ids=(f"candidate:{event_id}",),
        company_association_status=CompanyAssociationStatus.DIRECT_EXACT,
        validation_status=status, conflict_status=conflict,
    )


def selected_context():
    evidence = [
        EvidenceItem("evidence:revenue", "current_snapshot", "revenue", "monthly revenue disclosed", None, None, date(2026, 7, 31), 2026, "fixture", "fixture"),
        EvidenceItem("evidence:earnings", "current_snapshot", "net_income", "financial result available", None, None, date(2026, 6, 30), 2026, "fixture", "fixture"),
        EvidenceItem("evidence:other", "current_snapshot", "operating_cash_flow", "cash flow context available", None, None, date(2026, 6, 30), 2026, "fixture", "fixture"),
        EvidenceItem("evidence:risk", "current_snapshot", "operating_margin", "margin context available", None, None, date(2026, 6, 30), 2026, "fixture", "fixture"),
    ]
    missing = [
        MissingDataItem("missing:margin", "profitability", "segment_margin", None, None, "not supplied", "limits confirmation"),
        MissingDataItem("missing:segment", "growth", "segment_contribution", None, None, "not supplied", "limits attribution"),
    ]
    return SelectedResearchContext("1216.TW", "統一", ResearchQuestionType.GENERAL_RESEARCH, evidence, [], [], missing, [], [], NOW, NOW, len(evidence))


def accepted_output(**changes):
    output = {
        "impact_channel": "REVENUE",
        "hypothesis_status": "PLAUSIBLE",
        "impact_hypothesis": "近期月營收事件可能反映目前營運動能變化，但尚不足以證明獲利改善可持續。",
        "why_it_matters": "營收動能可能影響近期可檢視的獲利基礎，其品質仍取決於事業組合與利潤率。",
        "contradiction_or_limit": "單一月份的營收觀察不足以確認持續的獲利改善。",
        "uncertainty": "事業組合貢獻與利潤率確認仍缺。",
        "next_check": "比較後續營收與財務或投資人說明會資料。",
    }
    output.update(changes)
    return output


class Client:
    def __init__(self, output=None, error=None):
        self.output = output or accepted_output()
        self.error = error
        self.calls = []

    def create_grounded_answer(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(output_text=json.dumps(self.output, ensure_ascii=False), usage=None, id="mock-response")


class CatalystImpactServiceTestCase(unittest.TestCase):
    def context(self, **kwargs):
        support_refs = kwargs.get("supporting_evidence_refs", ())
        kwargs.setdefault(
            "supporting_evidence_provenance",
            tuple(ApprovedSupportingEvidence(item, (_support_source_id(item),)) for item in support_refs),
        )
        return build_event_impact_context(event=event(), selected_context=selected_context(), **kwargs)

    def test_1216_offline_prototype_is_program_assembled_and_useful(self):
        context = self.context(supporting_evidence_refs=("evidence:earnings",), missing_evidence_refs=("missing:margin", "missing:segment"))
        client = Client()
        result = generate_event_impact_hypothesis(context, client=client, config=CONFIG, generated_at=NOW)
        self.assertEqual(result.target_symbol, "1216.TW")
        self.assertEqual(result.event_id, "event_1216_revenue")
        self.assertEqual(result.impact_channel, ImpactChannel.REVENUE)
        self.assertEqual(result.hypothesis_status, HypothesisStatus.PLAUSIBLE)
        self.assertEqual(result.supporting_evidence_refs, ("evidence:earnings",))
        self.assertEqual(result.missing_evidence, ("missing:margin", "missing:segment"))
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["response_format"]["schema"]["additionalProperties"], False)
        role_ids = [item["id"] for item in client.calls[0]["payload"]["evidence"]]
        self.assertTrue(any(item.startswith("event:") for item in role_ids))
        self.assertTrue(any(item.startswith("background:") for item in role_ids))
        self.assertTrue(any(item.startswith("supporting:") for item in role_ids))
        self.assertEqual(client.calls[0]["payload"]["allowed_missing_context_ids"], ["missing:missing:margin", "missing:missing:segment"])

    def test_only_validated_event_is_eligible_including_partial_rejected_and_conflicted(self):
        for status, conflict in (
            (EventValidationStatus.PARTIALLY_VALIDATED, EventConflictStatus.NONE),
            (EventValidationStatus.REJECTED, EventConflictStatus.NONE),
            (EventValidationStatus.REJECTED, EventConflictStatus.FACT),
        ):
            invalid = event(status=status, conflict=conflict)
            with self.subTest(status=status, conflict=conflict):
                with self.assertRaises(CatalystImpactServiceError):
                    build_event_impact_context(event=invalid, selected_context=selected_context())

    def test_partial_event_is_rejected_before_any_provider_call(self):
        client = Client()
        with self.assertRaises(CatalystImpactServiceError):
            build_event_impact_context(
                event=event(status=EventValidationStatus.PARTIALLY_VALIDATED), selected_context=selected_context(),
            )
        self.assertEqual(client.calls, [])

    def test_payload_keeps_all_evidence_roles_explicit(self):
        context = self.context(
            supporting_evidence_refs=("evidence:earnings",), contradictory_evidence_refs=("evidence:risk",),
            missing_evidence_refs=("missing:margin",),
        )
        payload = build_event_impact_payload(context)
        self.assertEqual(set(payload), {"CATALYST_EVENT_FACT", "COMPANY_BACKGROUND", "SUPPORTING_EVIDENCE", "CONTRADICTORY_EVIDENCE", "MISSING_EVIDENCE"})
        self.assertEqual(payload["SUPPORTING_EVIDENCE"], ["evidence:earnings"])
        self.assertEqual(payload["CONTRADICTORY_EVIDENCE"], ["evidence:risk"])
        self.assertEqual(payload["MISSING_EVIDENCE"], ["missing:margin"])
        self.assertNotIn("evidence:earnings", payload["COMPANY_BACKGROUND"])

    def test_status_rules_are_program_validated(self):
        for status, kwargs in (("SUPPORTED", {}), ("CONTRADICTED", {})):
            client = Client(accepted_output(hypothesis_status=status))
            with self.subTest(status=status):
                with self.assertRaises(CatalystImpactServiceError):
                    generate_event_impact_hypothesis(self.context(), client=client, config=CONFIG)
                self.assertEqual(len(client.calls), 1)
        supported = generate_event_impact_hypothesis(
            self.context(supporting_evidence_refs=("evidence:earnings",)),
            client=Client(accepted_output(hypothesis_status="SUPPORTED")), config=CONFIG,
        )
        contradicted = generate_event_impact_hypothesis(
            self.context(contradictory_evidence_refs=("evidence:risk",)),
            client=Client(accepted_output(hypothesis_status="CONTRADICTED")), config=CONFIG,
        )
        self.assertEqual(supported.hypothesis_status, HypothesisStatus.SUPPORTED)
        self.assertEqual(contradicted.hypothesis_status, HypothesisStatus.CONTRADICTED)

    def test_independent_support_requires_non_event_provenance(self):
        base = selected_context()
        same_event_source = EvidenceItem(
            "source:1216:revenue", "current_snapshot", "revenue", event().event_fact,
            None, None, None, None, "fixture", "fixture",
        )
        primary_alias = EvidenceItem(
            "evidence:primary-alias", "current_snapshot", "revenue", "monthly revenue disclosed",
            None, None, None, None, "fixture", "fixture",
        )
        fact_wrapper = EvidenceItem(
            "evidence:renamed-event", "current_snapshot", "revenue", event().event_fact,
            None, None, None, None, "fixture", "fixture",
        )
        unproven = EvidenceItem(
            "evidence:unproven", "current_snapshot", "revenue", "monthly revenue disclosed",
            None, None, None, None, "fixture", "fixture",
        )
        for item in (same_event_source, primary_alias, fact_wrapper, unproven):
            context = replace(base, selected_evidence=[item], source_evidence_count=1)
            with self.subTest(item=item.id):
                with self.assertRaises(CatalystImpactServiceError):
                    build_event_impact_context(
                        event=event(), selected_context=context, supporting_evidence_refs=(item.id,),
                        supporting_evidence_provenance=(
                            ApprovedSupportingEvidence(item.id, (_support_source_id(item.id),)),
                        ) if item is not unproven else (),
                    )
        with self.assertRaises(CatalystImpactServiceError):
            build_event_impact_context(
                event=event(), selected_context=selected_context(),
                supporting_evidence_refs=("evidence:earnings",),
                supporting_evidence_provenance=(
                    ApprovedSupportingEvidence(
                        "evidence:earnings", ("source:1216:earnings",), ("event_1216_revenue",),
                    ),
                ),
            )
        independent = self.context(supporting_evidence_refs=("evidence:earnings",))
        result = generate_event_impact_hypothesis(
            independent, client=Client(accepted_output(hypothesis_status="SUPPORTED")), config=CONFIG,
        )
        self.assertEqual(result.hypothesis_status, HypothesisStatus.SUPPORTED)
        self.assertEqual(result.supporting_evidence_refs, ("evidence:earnings",))

    def test_directly_constructed_context_cannot_bypass_independent_support_check(self):
        context = self.context(supporting_evidence_refs=("evidence:earnings",))
        bypassed = replace(
            context,
            supporting_evidence_provenance=(
                ApprovedSupportingEvidence(
                    "evidence:earnings", ("source:1216:revenue",),
                ),
            ),
        )
        client = Client(accepted_output(hypothesis_status="SUPPORTED"))
        with self.assertRaises(CatalystImpactServiceError):
            generate_event_impact_hypothesis(bypassed, client=client, config=CONFIG)
        self.assertEqual(len(client.calls), 0)

    def test_actual_provider_payload_keeps_all_five_evidence_roles(self):
        context = self.context(
            supporting_evidence_refs=("evidence:earnings",),
            contradictory_evidence_refs=("evidence:risk",),
            missing_evidence_refs=("missing:margin",),
        )
        client = Client()
        generate_event_impact_hypothesis(context, client=client, config=CONFIG)
        role_ids = {item["id"] for item in client.calls[0]["payload"]["evidence"]}
        self.assertTrue(any(item.startswith("event:") for item in role_ids))
        self.assertTrue(any(item.startswith("background:") for item in role_ids))
        self.assertTrue(any(item.startswith("supporting:") for item in role_ids))
        self.assertTrue(any(item.startswith("contradictory:") for item in role_ids))
        self.assertEqual(client.calls[0]["payload"]["allowed_missing_context_ids"], ["missing:missing:margin"])

    def test_unsupported_channel_extra_source_or_url_is_rejected_without_retry(self):
        for output in (
            accepted_output(impact_channel="DEMAND"),
            {**accepted_output(), "source_id": "invented"},
            accepted_output(impact_hypothesis="來源 https://example.test 的內容支持此假說。"),
        ):
            client = Client(output)
            with self.subTest(output=output):
                with self.assertRaises((CatalystImpactServiceError, AIGroundingError)):
                    generate_event_impact_hypothesis(self.context(), client=client, config=CONFIG)
                self.assertEqual(len(client.calls), 1)

    def test_financial_numbers_recommendations_and_price_targets_fail_closed(self):
        for text in ("營收成長 50%。", "建議買進。", "目標價為 100 元。"):
            client = Client(accepted_output(why_it_matters=text))
            with self.subTest(text=text):
                with self.assertRaises((AIResearchError, CatalystImpactServiceError, AIAnalystFinancialNumericNarrativeError)):
                    generate_event_impact_hypothesis(self.context(), client=client, config=CONFIG)
                self.assertEqual(len(client.calls), 1)

    def test_stock_price_direction_is_rejected_while_business_impact_is_allowed(self):
        rejected = (
            "股價將上漲。", "股價可能下跌。", "看多。", "stock price will rise.", "share price may fall.",
        )
        for text in rejected:
            client = Client(accepted_output(why_it_matters=text))
            with self.subTest(text=text):
                with self.assertRaises(AIResearchError):
                    generate_event_impact_hypothesis(self.context(), client=client, config=CONFIG)
                self.assertEqual(len(client.calls), 1)
        for text in ("營收動能可能改善。", "毛利率可能承壓。", "產能增加可能提高折舊壓力。"):
            with self.subTest(text=text):
                result = generate_event_impact_hypothesis(
                    self.context(), client=Client(accepted_output(why_it_matters=text)), config=CONFIG,
                )
                self.assertEqual(result.why_it_matters_text, text)

    def test_malformed_output_and_provider_failure_have_no_retry_or_repair(self):
        malformed = Client({"impact_channel": "REVENUE"})
        with self.assertRaises(CatalystImpactServiceError):
            generate_event_impact_hypothesis(self.context(), client=malformed, config=CONFIG)
        self.assertEqual(len(malformed.calls), 1)
        failed = Client(error=RuntimeError("provider failed"))
        with self.assertRaises(RuntimeError):
            generate_event_impact_hypothesis(self.context(), client=failed, config=CONFIG)
        self.assertEqual(len(failed.calls), 1)

    def test_company_budget_skips_third_event_and_failure_is_isolated(self):
        contexts = tuple(build_event_impact_context(
            event=event(event_id=f"event_{index}"), selected_context=selected_context(),
        ) for index in range(3))
        client = Client()
        results = generate_company_event_impact_hypotheses(contexts, client=client, config=CONFIG, generated_at=NOW)
        self.assertEqual(len(results), MAX_AI_CALLS_PER_COMPANY_RUN)
        self.assertEqual(len(client.calls), MAX_AI_CALLS_PER_COMPANY_RUN)
        failed = Client(error=AIProviderError("one event fails"))
        self.assertEqual(generate_company_event_impact_hypotheses(contexts, client=failed, config=CONFIG), ())
        self.assertEqual(len(failed.calls), MAX_AI_CALLS_PER_COMPANY_RUN)

    def test_first_provider_failure_still_consumes_one_of_two_company_slots(self):
        class SequenceClient(Client):
            def create_grounded_answer(self, **kwargs):
                self.calls.append(kwargs)
                if len(self.calls) == 1:
                    raise AIProviderError("first event fails")
                return SimpleNamespace(output_text=json.dumps(accepted_output(), ensure_ascii=False), usage=None, id="mock-response")
        contexts = tuple(build_event_impact_context(
            event=event(event_id=f"event_{index}"), selected_context=selected_context(),
        ) for index in range(3))
        client = SequenceClient()
        results = generate_company_event_impact_hypotheses(contexts, client=client, config=CONFIG)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(client.calls), MAX_AI_CALLS_PER_COMPANY_RUN)

    def test_company_run_deduplicates_event_identity_before_calling_ai(self):
        context = self.context()
        client = Client()
        results = generate_company_event_impact_hypotheses((context, context), client=client, config=CONFIG)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(client.calls), 1)

    def test_duplicate_contexts_are_order_independent_or_fail_closed_before_calls(self):
        exact = self.context(supporting_evidence_refs=("evidence:earnings",))
        first = generate_company_event_impact_hypotheses((exact, exact), client=Client(), config=CONFIG)
        second = generate_company_event_impact_hypotheses((exact, exact), client=Client(), config=CONFIG)
        self.assertEqual(first, second)

        alternate_support = self.context(supporting_evidence_refs=("evidence:other",))
        alternate_contradiction = self.context(contradictory_evidence_refs=("evidence:risk",))
        alternate_missing = self.context(missing_evidence_refs=("missing:margin",))
        for left, right in ((exact, alternate_support), (exact, alternate_contradiction), (exact, alternate_missing)):
            for contexts in ((left, right), (right, left)):
                client = Client()
                with self.subTest(contexts=contexts):
                    with self.assertRaises(DuplicateEventContextConflictError):
                        generate_company_event_impact_hypotheses(contexts, client=client, config=CONFIG)
                    self.assertEqual(client.calls, [])

    def test_equivalent_collection_orderings_collapse_to_one_provider_call(self):
        provenance = (
            ApprovedSupportingEvidence("evidence:earnings", ("source:1216:earnings",)),
            ApprovedSupportingEvidence("evidence:other", ("source:1216:cash-flow",)),
        )
        base = selected_context()
        reordered_background = replace(
            base, selected_evidence=list(reversed(base.selected_evidence)),
        )
        cases = (
            (
                build_event_impact_context(
                    event=event(), selected_context=base,
                    supporting_evidence_refs=("evidence:earnings",),
                    supporting_evidence_provenance=(provenance[0],),
                ),
                build_event_impact_context(
                    event=event(), selected_context=reordered_background,
                    supporting_evidence_refs=("evidence:earnings",),
                    supporting_evidence_provenance=(provenance[0],),
                ),
            ),
            (
                build_event_impact_context(
                    event=event(), selected_context=base,
                    supporting_evidence_refs=("evidence:earnings", "evidence:other"),
                    supporting_evidence_provenance=provenance,
                ),
                build_event_impact_context(
                    event=event(), selected_context=base,
                    supporting_evidence_refs=("evidence:other", "evidence:earnings"),
                    supporting_evidence_provenance=tuple(reversed(provenance)),
                ),
            ),
            (
                build_event_impact_context(
                    event=event(), selected_context=base,
                    contradictory_evidence_refs=("evidence:revenue", "evidence:risk"),
                ),
                build_event_impact_context(
                    event=event(), selected_context=base,
                    contradictory_evidence_refs=("evidence:risk", "evidence:revenue"),
                ),
            ),
            (
                build_event_impact_context(
                    event=event(), selected_context=base,
                    missing_evidence_refs=("missing:margin", "missing:segment"),
                ),
                build_event_impact_context(
                    event=event(), selected_context=base,
                    missing_evidence_refs=("missing:segment", "missing:margin"),
                ),
            ),
        )
        for left, right in cases:
            forward_client = Client()
            reverse_client = Client()
            forward = generate_company_event_impact_hypotheses(
                (left, right), client=forward_client, config=CONFIG,
            )
            reverse = generate_company_event_impact_hypotheses(
                (right, left), client=reverse_client, config=CONFIG,
            )
            with self.subTest(left=left, right=right):
                self.assertEqual(forward, reverse)
                self.assertEqual(len(forward), 1)
                self.assertEqual(len(forward_client.calls), 1)
                self.assertEqual(len(reverse_client.calls), 1)
                self.assertEqual(forward[0].hypothesis_id, build_impact_hypothesis_id("event_1216_revenue"))

    def test_material_company_background_difference_still_conflicts_before_provider_call(self):
        base = selected_context()
        changed_background = replace(
            base,
            selected_evidence=[
                *base.selected_evidence[:-1],
                replace(base.selected_evidence[-1], value="materially different margin context"),
            ],
        )
        left = build_event_impact_context(event=event(), selected_context=base)
        right = build_event_impact_context(event=event(), selected_context=changed_background)
        for contexts in ((left, right), (right, left)):
            client = Client()
            with self.subTest(contexts=contexts):
                with self.assertRaises(DuplicateEventContextConflictError):
                    generate_company_event_impact_hypotheses(contexts, client=client, config=CONFIG)
                self.assertEqual(client.calls, [])

    def test_identity_and_provenance_are_deterministic_and_program_owned(self):
        self.assertEqual(build_impact_hypothesis_id("event_1216_revenue"), build_impact_hypothesis_id("event_1216_revenue"))
        first = generate_event_impact_hypothesis(self.context(), client=Client(), config=CONFIG)
        second = generate_event_impact_hypothesis(
            self.context(), client=Client(accepted_output(impact_hypothesis="營收事件可能反映營運動能變化。")), config=CONFIG,
        )
        self.assertEqual(first.hypothesis_id, second.hypothesis_id)
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(first.target_company_name, "統一")

    def test_general_background_never_becomes_supporting_evidence(self):
        context = self.context()
        self.assertEqual(context.supporting_evidence_refs, ())
        self.assertTrue(context.company_background)
        result = generate_event_impact_hypothesis(context, client=Client(), config=CONFIG)
        self.assertEqual(result.supporting_evidence_refs, ())

    def test_slots_are_bounded(self):
        client = Client(accepted_output(uncertainty="x" * 421))
        with self.assertRaises(CatalystImpactServiceError):
            generate_event_impact_hypothesis(self.context(), client=client, config=CONFIG)
        self.assertEqual(len(client.calls), 1)


def _support_source_id(evidence_ref):
    return {
        "evidence:earnings": "source:1216:earnings",
        "evidence:other": "source:1216:cash-flow",
        "evidence:revenue": "source:1216:revenue",
        "evidence:risk": "source:1216:margin",
        "source:1216:revenue": "source:1216:revenue",
        "evidence:primary-alias": "source:1216:revenue",
        "evidence:renamed-event": "source:1216:other",
    }[evidence_ref]


if __name__ == "__main__":
    unittest.main()
