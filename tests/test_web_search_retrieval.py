import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from external_source import RawWebSearchSource
from external_source import SourceTier
from external_source import TargetCompanyIdentity
from web_search_retrieval import ToolCallAccountingStatus
from web_search_retrieval import WebSearchRetrievalError
from web_search_retrieval import WebSearchRetrievalRequest
from web_search_retrieval import WebSearchRetrievalResponse
from web_search_retrieval import WebSearchRetrievalService
from web_search_retrieval import build_retrieval_artifact


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)
TARGET = TargetCompanyIdentity("1216.TW", "統一", "Uni-President Enterprises Corp.", ("統一(1216)",))
REQUEST = WebSearchRetrievalRequest(
    target=TARGET,
    start_date=date(2026, 8, 2),
    end_date=date(2026, 8, 31),
    query="synthetic test query",
    explicit_refresh=True,
)


class FakeRetrievalClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def retrieve(self, request):
        self.calls.append(request)
        return self.response


class WebSearchRetrievalTestCase(unittest.TestCase):
    def response(self, *, calls=1, sources=()):
        return WebSearchRetrievalResponse("completed", calls, tuple(sources), {"input_tokens": 12, "output_tokens": 8})

    def source(self, *, url="https://twse.com.tw/company/1216?utm_source=test", title="統一(1216) 2026-08-10 公告"):
        return RawWebSearchSource(url=url, title=title, snippet="日 期：2026年08月10日，公司名稱：統一(1216)")

    def test_service_requires_explicit_refresh_before_injected_client_can_run(self):
        client = FakeRetrievalClient(self.response(sources=(self.source(),)))
        request = WebSearchRetrievalRequest(TARGET, date(2026, 8, 2), date(2026, 8, 31), "query")
        with self.assertRaisesRegex(WebSearchRetrievalError, "explicit_refresh"):
            WebSearchRetrievalService(client).retrieve_external_sources(request, retrieved_at=NOW)
        self.assertEqual(client.calls, [])

    def test_retrieval_model_is_explicit_and_synthesis_config_is_not_used(self):
        artifact = build_retrieval_artifact(REQUEST, self.response(sources=(self.source(),)), retrieved_at=NOW, domain_map={"twse.com.tw": SourceTier.TIER_1_OFFICIAL})
        self.assertEqual(artifact.model, "gpt-5.6-luna")
        self.assertEqual(artifact.sources[0].source_tier, SourceTier.TIER_1_OFFICIAL)

    def test_observed_tool_calls_are_audited_and_excess_is_a_warning(self):
        artifact = build_retrieval_artifact(REQUEST, self.response(calls=2, sources=(self.source(),)), retrieved_at=NOW)
        self.assertEqual(artifact.observed_web_search_call_count, 2)
        self.assertEqual(artifact.tool_call_accounting_status, ToolCallAccountingStatus.EXCEEDED_EXPECTED_POLICY)
        self.assertIn("OBSERVED_WEB_SEARCH_CALL_COUNT_EXCEEDS_EXPECTED_POLICY", artifact.normalization_warnings)

    def test_unobserved_tool_call_count_is_not_silently_assumed(self):
        artifact = build_retrieval_artifact(REQUEST, self.response(calls=None, sources=(self.source(),)), retrieved_at=NOW)
        self.assertEqual(artifact.tool_call_accounting_status, ToolCallAccountingStatus.UNOBSERVED)
        self.assertIn("OBSERVED_WEB_SEARCH_CALL_COUNT_UNAVAILABLE", artifact.normalization_warnings)

    def test_checksum_is_deterministic_for_equivalent_normalized_evidence_regardless_of_order_or_retrieval_time(self):
        first = self.source(url="https://twse.com.tw/a?utm_source=x", title="統一(1216) A")
        second = self.source(url="https://twse.com.tw/b?utm_source=x", title="統一(1216) B")
        left = build_retrieval_artifact(REQUEST, self.response(sources=(first, second)), retrieved_at=NOW)
        right = build_retrieval_artifact(REQUEST, self.response(sources=(second, first)), retrieved_at=datetime(2026, 8, 31, 9, 0, tzinfo=UTC))
        self.assertEqual(left.checksum, right.checksum)

    def test_duplicate_url_is_removed_without_collapsing_different_articles_from_same_domain(self):
        duplicate = self.source(url="https://twse.com.tw/a?utm_source=two", title="other title")
        other = self.source(url="https://twse.com.tw/b", title="統一(1216) B")
        artifact = build_retrieval_artifact(REQUEST, self.response(sources=(self.source(url="https://twse.com.tw/a"), duplicate, other)), retrieved_at=NOW)
        self.assertEqual(len(artifact.sources), 2)
        self.assertIn("DUPLICATE_SOURCES_REMOVED", artifact.normalization_warnings)


if __name__ == "__main__":
    unittest.main()
