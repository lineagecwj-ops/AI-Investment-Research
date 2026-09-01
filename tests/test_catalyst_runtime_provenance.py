import json
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from catalyst_deep_dive import build_selected_catalyst_context
from catalyst_deep_dive import run_catalyst_deep_dive_refresh
from catalyst_impact import HypothesisStatus
from catalyst_impact import ImpactChannel
from catalyst_impact import ImpactHypothesis
from catalyst_runtime_provenance import CatalystRuntimeProvenanceError
from catalyst_runtime_provenance import CatalystRuntimeProvenanceRun
from catalyst_impact_service import build_event_impact_context
from external_source import RawWebSearchSource
from external_source import SourceTier
from external_source import TargetCompanyIdentity
from models import Stock
from research_service import build_research_report
from web_search_retrieval import WebSearchRetrievalRequest
from web_search_retrieval import WebSearchRetrievalResponse
from web_search_retrieval import build_retrieval_artifact


NOW = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
AS_OF = date(2026, 9, 1)


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
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def __call__(self, context, **_kwargs):
        self.calls.append(context)
        if self.error is not None:
            raise self.error
        event = context.event
        return ImpactHypothesis(
            hypothesis_id=f"impact:{event.event_id}",
            event_id=event.event_id,
            target_symbol=event.target_symbol,
            target_company_name=event.target_company_name,
            impact_channel=ImpactChannel.REVENUE,
            hypothesis_text="可能反映可後續驗證的營運變化。",
            why_it_matters_text="需要持續確認事件與後續公開資訊的關聯。",
            hypothesis_status=HypothesisStatus.PLAUSIBLE,
            supporting_evidence_refs=(),
            contradictory_evidence_refs=(),
            missing_evidence=context.missing_evidence_refs,
            contradiction_or_limit_text="單一事件不足以確認持續影響。",
            uncertainty_text="後續公開資料尚未完整。",
            next_checks=("檢查後續公司公告與財務資料。",),
        )


class FailingProvenanceRun(CatalystRuntimeProvenanceRun):
    def finalize_and_persist(self, *, run_status, completed_at=None):
        raise CatalystRuntimeProvenanceError("fixture persistence failure")


def selected_context(symbol="1216.TW", company_name="統一"):
    stock = Stock(symbol=symbol, company_name=company_name, sector="Consumer", industry="Food")
    return build_selected_catalyst_context(
        stock=stock,
        research_report=build_research_report(stock),
        display_name=company_name,
        generated_at=NOW,
    )


def artifact_for(context, sources):
    request = WebSearchRetrievalRequest(
        target=TargetCompanyIdentity(context.symbol, context.display_name),
        start_date=date(2026, 8, 1),
        end_date=AS_OF,
        query="fixture",
        retrieval_model="fixture-model",
        explicit_refresh=True,
    )
    return build_retrieval_artifact(
        request,
        WebSearchRetrievalResponse("completed", 1, tuple(sources)),
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


class CatalystRuntimeProvenanceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.provenance_directory = Path(self.temp_directory.name)

    def tearDown(self):
        self.temp_directory.cleanup()

    def run_refresh(self, context, sources, *, impact=None, provenance_factory=CatalystRuntimeProvenanceRun):
        retrieval = FakeRetrievalService(artifact_for(context, sources))
        impact = impact or FakeImpactGenerator()
        result = run_catalyst_deep_dive_refresh(
            selected_context=context,
            explicit_refresh=True,
            as_of_date=AS_OF,
            retrieved_at=NOW,
            api_key_available=lambda: True,
            retrieval_service=retrieval,
            impact_generator=impact,
            provenance_directory=self.provenance_directory,
            provenance_factory=provenance_factory,
        )
        return result, retrieval, impact

    def load_artifact(self, result):
        path = self.provenance_directory / f"{result.provenance_run_id}.json"
        self.assertTrue(path.is_file())
        return json.loads(path.read_text(encoding="utf-8"))

    def test_passive_render_creates_no_run_and_explicit_refresh_creates_one(self):
        context = selected_context()
        retrieval = FakeRetrievalService()
        result = run_catalyst_deep_dive_refresh(
            selected_context=context,
            explicit_refresh=False,
            api_key_available=lambda: True,
            retrieval_service=retrieval,
            provenance_directory=self.provenance_directory,
        )
        self.assertEqual(result.provenance_status, "NOT_TRIGGERED")
        self.assertEqual(list(self.provenance_directory.glob("*.json")), [])
        result, retrieval, _ = self.run_refresh(
            context,
            (source("revenue", "統一(1216) 營收", "日期：2026-08-10，統一(1216) 公告 7 月合併營收。"),),
        )
        self.assertEqual(result.provenance_status, "PROVENANCE_SAVED")
        self.assertEqual(len(retrieval.calls), 1)
        self.assertEqual(len(list(self.provenance_directory.glob("*.json"))), 1)

    def test_success_artifact_captures_source_event_impact_and_call_accounting(self):
        result, _, impact = self.run_refresh(
            selected_context(),
            (source("revenue", "統一(1216) 營收", "日期：2026-08-10，統一(1216) 公告 7 月合併營收。"),),
        )
        payload = self.load_artifact(result)
        self.assertEqual(payload["schema_version"], "CATALYST_RUNTIME_PROVENANCE_V1")
        self.assertEqual(payload["run_status"], "COMPLETED")
        self.assertEqual(payload["symbol"], "1216.TW")
        self.assertEqual(payload["retrieval"]["request_count"], 1)
        self.assertEqual(payload["retrieval"]["source_count"], 1)
        self.assertEqual(len(payload["event_pipeline"]["candidates"]), 1)
        self.assertEqual(payload["event_pipeline"]["events"][0]["validation_status"], "VALIDATED")
        self.assertEqual(payload["impact_attempts"][0]["impact_status"], "SUCCESS")
        self.assertEqual(payload["call_accounting"], {
            "retrieval_call_count": 1,
            "impact_call_count": 1,
            "total_external_call_count": 2,
        })
        self.assertEqual(len(impact.calls), 1)

    def test_zero_validated_events_is_fail_closed_without_impact_failure(self):
        result, _, impact = self.run_refresh(
            selected_context("1608.TW", "華榮"),
            (source("partial", "華榮(1608) 更新", "華榮近期公布營收。"),),
        )
        payload = self.load_artifact(result)
        self.assertEqual(result.state, "NO_VALIDATED_EVENTS")
        self.assertEqual(payload["run_status"], "NO_VALIDATED_EVENTS")
        self.assertEqual(payload["call_accounting"]["impact_call_count"], 0)
        self.assertEqual(payload["impact_attempts"], [])
        self.assertEqual(payload["failures"], [])
        self.assertEqual(impact.calls, [])

    def test_impact_failure_is_recorded_once_with_redacted_safe_error(self):
        secret = "sk-fixture-secret-token-123456789"
        result, _, impact = self.run_refresh(
            selected_context(),
            (source("revenue", "統一(1216) 營收", "日期：2026-08-10，統一(1216) 公告 7 月合併營收。"),),
            impact=FakeImpactGenerator(RuntimeError(f"Bearer {secret}; api_key={secret}")),
        )
        payload = self.load_artifact(result)
        self.assertEqual(len(impact.calls), 1)
        self.assertEqual(payload["run_status"], "COMPLETED_WITH_EVENT_FAILURES")
        self.assertEqual(payload["impact_attempts"][0]["impact_status"], "FAILED")
        self.assertTrue(payload["impact_attempts"][0]["impact_attempted"])
        self.assertEqual(payload["impact_attempts"][0]["impact_call_index"], 1)
        self.assertEqual(payload["call_accounting"]["impact_call_count"], 1)
        failure = payload["failures"][0]
        self.assertEqual(failure["error_stage"], "IMPACT_PROVIDER")
        self.assertEqual(failure["exception_class"], "RuntimeError")
        self.assertNotIn(secret, json.dumps(payload, ensure_ascii=False))
        self.assertIn("[REDACTED", failure["sanitized_error_message"])

    def test_context_failure_is_not_a_provider_attempt_and_preserves_actual_call_counts(self):
        secret = "sk-context-secret-token-123456789"
        impact = FakeImpactGenerator()
        with patch(
            "catalyst_deep_dive.build_event_impact_context",
            side_effect=RuntimeError(f"OPENAI_API_KEY={secret}"),
        ):
            result, retrieval, impact = self.run_refresh(
                selected_context(),
                (source("revenue", "統一(1216) 營收", "日期：2026-08-10，統一(1216) 公告 7 月合併營收。"),),
                impact=impact,
            )
        payload = self.load_artifact(result)
        self.assertEqual(len(retrieval.calls), 1)
        self.assertEqual(impact.calls, [])
        attempt = payload["impact_attempts"][0]
        self.assertFalse(attempt["impact_attempted"])
        self.assertIsNone(attempt["impact_call_index"])
        self.assertEqual(attempt["impact_status"], "CONTEXT_FAILED")
        self.assertEqual(payload["call_accounting"], {
            "retrieval_call_count": 1,
            "impact_call_count": 0,
            "total_external_call_count": 1,
        })
        failure = payload["failures"][0]
        self.assertEqual(failure["error_stage"], "IMPACT_CONTEXT")
        self.assertEqual(failure["exception_class"], "RuntimeError")
        self.assertNotIn(secret, json.dumps(payload, ensure_ascii=False))

    def test_context_failure_and_provider_success_keep_two_event_accounting_separate(self):
        calls = 0

        def context_or_failure(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("fixture context failure")
            return build_event_impact_context(*args, **kwargs)

        with patch("catalyst_deep_dive.build_event_impact_context", side_effect=context_or_failure):
            result, _, impact = self.run_refresh(
                selected_context("2027.TW", "大成鋼"),
                (
                    source("revenue", "大成鋼(2027) 營收", "日期：2026-08-10，大成鋼(2027) 公告 7 月合併營收。"),
                    source("earnings", "大成鋼(2027) 財報", "日期：2026-08-11，大成鋼(2027) 董事會通過第二季財務報告。"),
                ),
            )
        payload = self.load_artifact(result)
        self.assertEqual(len(impact.calls), 1)
        self.assertEqual(payload["call_accounting"], {
            "retrieval_call_count": 1,
            "impact_call_count": 1,
            "total_external_call_count": 2,
        })
        self.assertEqual(
            {item["impact_status"] for item in payload["impact_attempts"]},
            {"CONTEXT_FAILED", "SUCCESS"},
        )

    def test_persistence_failure_preserves_result_without_another_call(self):
        result, retrieval, impact = self.run_refresh(
            selected_context(),
            (source("revenue", "統一(1216) 營收", "日期：2026-08-10，統一(1216) 公告 7 月合併營收。"),),
            provenance_factory=FailingProvenanceRun,
        )
        self.assertEqual(result.state, "COMPLETED")
        self.assertEqual(result.provenance_status, "PROVENANCE_PERSIST_FAILED")
        self.assertIsNotNone(result.provenance_warning)
        self.assertEqual(len(retrieval.calls), 1)
        self.assertEqual(len(impact.calls), 1)
        self.assertEqual(list(self.provenance_directory.glob("*.json")), [])

    def test_two_symbols_create_distinct_artifacts_without_cross_symbol_reuse(self):
        first, _, _ = self.run_refresh(
            selected_context(),
            (source("revenue", "統一(1216) 營收", "日期：2026-08-10，統一(1216) 公告 7 月合併營收。"),),
        )
        second, _, _ = self.run_refresh(
            selected_context("2027.TW", "大成鋼"),
            (source("revenue", "大成鋼(2027) 營收", "日期：2026-08-10，大成鋼(2027) 公告 7 月合併營收。"),),
        )
        self.assertNotEqual(first.provenance_run_id, second.provenance_run_id)
        self.assertEqual(self.load_artifact(first)["symbol"], "1216.TW")
        self.assertEqual(self.load_artifact(second)["symbol"], "2027.TW")


if __name__ == "__main__":
    unittest.main()
