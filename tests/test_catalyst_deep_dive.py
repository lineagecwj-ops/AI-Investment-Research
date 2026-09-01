import sys
import tempfile
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from catalyst_deep_dive import MAX_IMPACT_AI_CALLS
from catalyst_deep_dive import build_selected_catalyst_context
from catalyst_deep_dive import catalyst_card_display
from catalyst_deep_dive import catalyst_result_for_symbol
from catalyst_deep_dive import run_catalyst_deep_dive_refresh
from catalyst_impact import HypothesisStatus
from catalyst_impact import ImpactChannel
from catalyst_impact import ImpactHypothesis
from external_source import RawWebSearchSource
from external_source import SourceTier
from external_source import TargetCompanyIdentity
from models import Stock
from research_service import build_research_report
from web_search_retrieval import WebSearchRetrievalResponse
from web_search_retrieval import WebSearchRetrievalRequest


def catalyst_ui_fixture_app():
    from datetime import date
    import streamlit as st
    import app
    from catalyst_deep_dive import CatalystDeepDiveCard
    from catalyst_deep_dive import CatalystDeepDiveResult
    from catalyst_event import CatalystEventType
    from catalyst_event import EventConflictStatus
    from catalyst_event import EventTemporalStatus
    from catalyst_event import EventValidationStatus
    from catalyst_event import ValidatedCatalystEvent
    from external_source import CompanyAssociationStatus
    from external_source import SourceTemporalEvidence
    from external_source import TemporalEvidenceBasis
    from external_source import TemporalKind
    from external_source import TemporalPrecision
    from models import Stock
    from research_service import build_research_report
    from catalyst_impact import HypothesisStatus
    from catalyst_impact import ImpactChannel
    from catalyst_impact import ImpactHypothesis

    app.initialize_session_state()
    st.session_state.setdefault("fixture_catalyst_calls", 0)
    stock = Stock(symbol="1216.TW", company_name="統一")
    report = build_research_report(stock)
    event = ValidatedCatalystEvent(
        event_id="fixture_event",
        target_symbol="1216.TW",
        target_company_name="統一",
        event_type=CatalystEventType.REVENUE_UPDATE,
        event_fact="統一(1216) 公告 7 月合併營收。",
        event_temporal_evidence=SourceTemporalEvidence(
            value=date(2026, 8, 10),
            precision=TemporalPrecision.DATE,
            kind=TemporalKind.EVENT_ANNOUNCED_AT,
            basis=TemporalEvidenceBasis.SOURCE_SNIPPET_EXACT_DATE,
            raw_text="2026-08-10",
        ),
        event_temporal_status=EventTemporalStatus.TIME_CONFIRMED,
        source_ids=("fixture_source",),
        primary_source_id="fixture_source",
        support_count=1,
        event_key="fixture_event",
        candidate_ids=("fixture_candidate",),
        company_association_status=CompanyAssociationStatus.DIRECT_EXACT,
        validation_status=EventValidationStatus.VALIDATED,
        conflict_status=EventConflictStatus.NONE,
    )
    hypothesis = ImpactHypothesis(
        hypothesis_id="fixture_impact",
        event_id=event.event_id,
        target_symbol="1216.TW",
        target_company_name="統一",
        impact_channel=ImpactChannel.REVENUE,
        hypothesis_text="可能反映營運變化。",
        why_it_matters_text="需要後續資料確認。",
        hypothesis_status=HypothesisStatus.PLAUSIBLE,
        supporting_evidence_refs=(),
        contradictory_evidence_refs=(),
        missing_evidence=(),
        contradiction_or_limit_text="單一事件不足以確認持續影響。",
        uncertainty_text="後續公開資料尚未完整。",
        next_checks=("檢查後續公司公告。",),
    )

    def fake_refresh(**_kwargs):
        st.session_state["fixture_catalyst_calls"] = st.session_state.get("fixture_catalyst_calls", 0) + 1
        return CatalystDeepDiveResult(
            target_symbol="1216.TW",
            target_company_name="統一",
            state="COMPLETED",
            message="fixture complete",
            cards=(CatalystDeepDiveCard(event=event, impact_hypothesis=hypothesis, missing_evidence=()),),
            validated_event_count=1,
            retrieval_request_count=1,
            impact_call_count=1,
        )

    app.run_catalyst_deep_dive_refresh = fake_refresh
    app.render_catalyst_deep_dive(stock, report, {"Symbol": "1216.TW", "Company Name": "統一"})
    st.write(st.session_state.get("fixture_catalyst_calls", 0))
from web_search_retrieval import build_retrieval_artifact


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)
AS_OF = date(2026, 8, 31)


class FakeRetrievalService:
    def __init__(self, artifact=None, error=None):
        self.artifact = artifact
        self.error = error
        self.calls = []

    def retrieve_external_sources(self, request, *, retrieved_at):
        self.calls.append((request, retrieved_at))
        if self.error is not None:
            raise self.error
        return self.artifact


class FakeImpactGenerator:
    def __init__(self, failures=()):
        self.failures = set(failures)
        self.calls = []

    def __call__(self, context, **_kwargs):
        self.calls.append(context)
        if context.event.event_id in self.failures:
            raise RuntimeError("synthetic impact failure")
        return ImpactHypothesis(
            hypothesis_id=f"impact:{context.event.event_id}",
            event_id=context.event.event_id,
            target_symbol=context.event.target_symbol,
            target_company_name=context.event.target_company_name,
            impact_channel=ImpactChannel.REVENUE,
            hypothesis_text="此事件可能反映可後續驗證的營運變化。",
            why_it_matters_text="需要持續確認事件與後續公開資訊的關聯。",
            hypothesis_status=HypothesisStatus.PLAUSIBLE,
            supporting_evidence_refs=(),
            contradictory_evidence_refs=(),
            missing_evidence=context.missing_evidence_refs,
            contradiction_or_limit_text="單一事件不足以確認持續影響。",
            uncertainty_text="後續公開資料尚未完整。",
            next_checks=("檢查後續公司公告與財務資料。",),
        )


def selected_context(symbol="1216.TW", company_name="統一"):
    stock = Stock(symbol=symbol, company_name=company_name, sector="Consumer", industry="Food")
    return build_selected_catalyst_context(
        stock=stock,
        research_report=build_research_report(stock),
        display_name=company_name,
        generated_at=NOW,
    )


def artifact_for(context, sources):
    target = TargetCompanyIdentity(context.symbol, context.display_name)
    request = WebSearchRetrievalRequest(
        target=target,
        start_date=date(2026, 8, 1),
        end_date=AS_OF,
        query="fixture",
        retrieval_model="fixture",
        explicit_refresh=True,
    )
    response = WebSearchRetrievalResponse("completed", 1, tuple(sources))
    return build_retrieval_artifact(
        request,
        response,
        retrieved_at=NOW,
        domain_map={"official.test": SourceTier.TIER_1_OFFICIAL},
    )


def source(path, title, snippet):
    return RawWebSearchSource(
        url=f"https://official.test/{path}",
        title=title,
        snippet=snippet,
        source_type="fixture",
    )


class CatalystDeepDiveTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.provenance_directory = Path(self.temp_directory.name)

    def tearDown(self):
        self.temp_directory.cleanup()

    def refresh(self, context, sources, **kwargs):
        retrieval = FakeRetrievalService(artifact_for(context, sources))
        impact = kwargs.pop("impact", FakeImpactGenerator())
        result = run_catalyst_deep_dive_refresh(
            selected_context=context,
            explicit_refresh=True,
            as_of_date=AS_OF,
            retrieved_at=NOW,
            api_key_available=lambda: True,
            retrieval_service=retrieval,
            impact_generator=impact,
            provenance_directory=self.provenance_directory,
            **kwargs,
        )
        return result, retrieval, impact

    def test_page_load_path_does_not_refresh_and_consumes_no_calls(self):
        context = selected_context()
        retrieval = FakeRetrievalService()
        result = run_catalyst_deep_dive_refresh(
            selected_context=context,
            explicit_refresh=False,
            api_key_available=lambda: True,
            retrieval_service=retrieval,
            provenance_directory=self.provenance_directory,
        )
        self.assertEqual(result.state, "NOT_REFRESHED")
        self.assertEqual(retrieval.calls, [])

    def test_explicit_refresh_runs_one_retrieval_and_one_validated_event_card(self):
        context = selected_context()
        result, retrieval, impact = self.refresh(
            context,
            (source("revenue", "統一(1216) 營收", "日期：2026-08-10，統一(1216) 公告 7 月合併營收。"),),
        )
        self.assertEqual(result.state, "COMPLETED")
        self.assertEqual(len(retrieval.calls), 1)
        self.assertEqual(len(impact.calls), 1)
        self.assertEqual(len(result.cards), 1)
        self.assertIn("統一(1216) 公告 7 月合併營收", result.cards[0].event.event_fact)

    def test_display_rerun_uses_stored_result_without_another_provider_call(self):
        context = selected_context()
        result, retrieval, impact = self.refresh(
            context,
            (source("revenue", "統一(1216) 營收", "日期：2026-08-10，統一(1216) 公告 7 月合併營收。"),),
        )
        stored = catalyst_result_for_symbol({"1216.TW": result}, "1216.TW")
        self.assertIs(stored, result)
        self.assertEqual(len(retrieval.calls), 1)
        self.assertEqual(len(impact.calls), 1)

    def test_symbol_switch_never_reuses_another_company_result(self):
        result, _, _ = self.refresh(
            selected_context(),
            (source("revenue", "統一(1216) 營收", "日期：2026-08-10，統一(1216) 公告 7 月合併營收。"),),
        )
        self.assertIsNone(catalyst_result_for_symbol({"1216.TW": result}, "2027.TW"))

    def test_missing_api_key_makes_zero_provider_calls(self):
        context = selected_context()
        retrieval = FakeRetrievalService()
        result = run_catalyst_deep_dive_refresh(
            selected_context=context,
            explicit_refresh=True,
            api_key_available=lambda: False,
            retrieval_service=retrieval,
            provenance_directory=self.provenance_directory,
        )
        self.assertEqual(result.state, "API_KEY_MISSING")
        self.assertEqual(retrieval.calls, [])

    def test_retrieval_failure_prevents_impact_calls(self):
        context = selected_context()
        impact = FakeImpactGenerator()
        result = run_catalyst_deep_dive_refresh(
            selected_context=context,
            explicit_refresh=True,
            api_key_available=lambda: True,
            retrieval_service=FakeRetrievalService(error=RuntimeError("fixture")),
            impact_generator=impact,
            provenance_directory=self.provenance_directory,
        )
        self.assertEqual(result.state, "RETRIEVAL_FAILED")
        self.assertEqual(impact.calls, [])

    def test_partial_event_never_receives_impact(self):
        context = selected_context("1608.TW", "華榮")
        result, _, impact = self.refresh(
            context,
            (source("partial", "華榮(1608) 更新", "華榮近期公布營收。"),),
        )
        self.assertEqual(result.state, "NO_VALIDATED_EVENTS")
        self.assertEqual(impact.calls, [])

    def test_two_newest_validated_events_are_selected_deterministically(self):
        context = selected_context("2027.TW", "大成鋼")
        result, _, impact = self.refresh(
            context,
            (
                source("old", "大成鋼(2027) 營收", "日期：2026-08-08，大成鋼(2027) 公告 7 月合併營收。"),
                source("earnings", "大成鋼(2027) 財報", "日期：2026-08-10，大成鋼(2027) 董事會通過第二季財務報告。"),
                source("capacity", "大成鋼(2027) 產能", "日期：2026-08-12，大成鋼(2027) 公告擴建新廠並增加產能。"),
            ),
        )
        self.assertEqual(len(result.cards), MAX_IMPACT_AI_CALLS)
        self.assertEqual(len(impact.calls), MAX_IMPACT_AI_CALLS)
        self.assertEqual(result.omitted_validated_event_count, 1)
        self.assertGreaterEqual(
            result.cards[0].event.event_temporal_value,
            result.cards[1].event.event_temporal_value,
        )

    def test_one_impact_failure_preserves_the_other_event_card(self):
        context = selected_context("2027.TW", "大成鋼")
        result, _, impact = self.refresh(
            context,
            (
                source("one", "大成鋼(2027) 營收", "日期：2026-08-10，大成鋼(2027) 公告 7 月合併營收。"),
                source("two", "大成鋼(2027) 財報", "日期：2026-08-11，大成鋼(2027) 董事會通過第二季財務報告。"),
            ),
        )
        failed_id = result.cards[0].event.event_id
        retry_result, _, retry_impact = self.refresh(
            context,
            (
                source("one", "大成鋼(2027) 營收", "日期：2026-08-10，大成鋼(2027) 公告 7 月合併營收。"),
                source("two", "大成鋼(2027) 財報", "日期：2026-08-11，大成鋼(2027) 董事會通過第二季財務報告。"),
            ),
            impact=FakeImpactGenerator(failures=(failed_id,)),
        )
        self.assertEqual(len(impact.calls), 2)
        self.assertEqual(len(retry_impact.calls), 2)
        self.assertEqual(sum(card.impact_hypothesis is not None for card in retry_result.cards), 1)
        self.assertEqual(sum(card.impact_error is not None for card in retry_result.cards), 1)

    def test_card_display_keeps_event_fact_and_temporal_value_program_owned(self):
        context = selected_context()
        result, _, _ = self.refresh(
            context,
            (source("revenue", "統一(1216) 營收", "日期：2026-08-10，統一(1216) 公告 7 月合併營收。"),),
        )
        values = catalyst_card_display(result.cards[0])
        self.assertEqual(values["發生了什麼"], result.cards[0].event.event_fact)
        self.assertEqual(values["事件日期"], "2026-08-10")
        self.assertEqual(values["證據狀態"], "PLAUSIBLE")
        self.assertIn("仍缺少的證據", values)
        forbidden = {"recommendation", "price_target", "probability", "stock_price_direction", "research_priority"}
        self.assertFalse(forbidden & set(values))

    def test_mocked_streamlit_controller_requires_click_and_rerun_does_not_repeat(self):
        from streamlit.testing.v1 import AppTest

        app_test = AppTest.from_function(catalyst_ui_fixture_app)
        app_test.run()
        self.assertFalse(app_test.exception)
        self.assertEqual(app_test.session_state["fixture_catalyst_calls"], 0)

        app_test.button(key="catalyst_deep_dive_refresh_1216.TW").click().run()
        self.assertFalse(app_test.exception)
        self.assertEqual(app_test.session_state["fixture_catalyst_calls"], 1)
        content = "\n".join(item.value for item in app_test.markdown)
        for label in ("發生了什麼", "為什麼可能重要", "限制 / 反證", "不確定性", "下一步要查什麼"):
            self.assertIn(label, content)

        app_test.run()
        self.assertFalse(app_test.exception)
        self.assertEqual(app_test.session_state["fixture_catalyst_calls"], 1)


if __name__ == "__main__":
    unittest.main()
