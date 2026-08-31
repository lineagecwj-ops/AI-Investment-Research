import copy
import json
import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from external_source import CompanyAssociationStatus
from external_source import RelatedCompanyIdentity
from external_source import SourceTier
from external_source import TargetCompanyIdentity
from openai_web_search_client import OPENAI_WEB_SEARCH_DOMAIN_MAP
from openai_web_search_client import OPENAI_WEB_SEARCH_INCLUDE
from openai_web_search_client import OpenAIWebSearchRetrievalClient
from openai_web_search_client import OpenAIWebSearchRetrievalError
from openai_web_search_client import adapt_openai_web_search_response
from openai_web_search_client import build_company_research_query
from openai_web_search_client import build_openai_web_search_retrieval_service
from web_search_retrieval import ToolCallAccountingStatus
from web_search_retrieval import WebSearchRetrievalRequest


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)
TARGET = TargetCompanyIdentity("1216.TW", "統一", "Uni-President Enterprises Corp.", ("統一(1216)",))
RELATED = (RelatedCompanyIdentity("Uni-President China Holdings Ltd.", ("220",), ("統一中國",)),)
REQUEST = WebSearchRetrievalRequest(
    target=TARGET,
    start_date=date(2026, 8, 2),
    end_date=date(2026, 8, 31),
    query=build_company_research_query(target=TARGET, start_date=date(2026, 8, 2), end_date=date(2026, 8, 31)),
    explicit_refresh=True,
    related_entities=RELATED,
)


class FakeResponses:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeProvider:
    def __init__(self, responses):
        self.responses = responses


class ProviderError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


class OpenAIWebSearchClientTestCase(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads((PROJECT_ROOT / "tests/fixtures/catalyst_v1h_openai_web_search_response.json").read_text(encoding="utf-8"))
        self.responses = FakeResponses(self.payload)
        self.factory_calls = []

    def client(self, *, environ=None, responses=None):
        def factory(**kwargs):
            self.factory_calls.append(kwargs)
            return FakeProvider(responses or self.responses)

        return OpenAIWebSearchRetrievalClient(
            client_factory=factory,
            environ={"OPENAI_API_KEY": "test-secret"} if environ is None else environ,
        )

    def test_request_contract_is_explicit_and_single_request(self):
        response = self.client().retrieve(REQUEST)
        self.assertEqual(len(self.responses.calls), 1)
        call = self.responses.calls[0]
        self.assertFalse(call["store"])
        self.assertEqual(call["model"], "gpt-5.6-luna")
        self.assertEqual(call["include"], list(OPENAI_WEB_SEARCH_INCLUDE))
        self.assertEqual(call["tools"], [{"type": "web_search", "search_context_size": "low"}])
        self.assertEqual(call["tool_choice"], "required")
        self.assertEqual(call["max_tool_calls"], 1)
        self.assertEqual(response.observed_web_search_call_count, 2)

    def test_api_key_is_resolved_at_call_time_and_never_part_of_response(self):
        client = self.client(environ={})
        with self.assertRaisesRegex(OpenAIWebSearchRetrievalError, "OPENAI_API_KEY_MISSING"):
            client.retrieve(REQUEST)
        self.assertEqual(self.factory_calls, [])
        self.assertNotIn("test-secret", repr(client))

    def test_explicit_refresh_is_required_by_transport_and_blocks_provider_construction(self):
        blocked = WebSearchRetrievalRequest(TARGET, date(2026, 8, 2), date(2026, 8, 31), "query")
        with self.assertRaisesRegex(OpenAIWebSearchRetrievalError, "EXPLICIT_REFRESH_REQUIRED"):
            self.client().retrieve(blocked)
        self.assertEqual(self.factory_calls, [])

    def test_provider_errors_are_sanitized_without_retry(self):
        for status, code in ((401, "OPENAI_AUTH_FAILED"), (403, "OPENAI_ACCESS_DENIED"), (429, "OPENAI_RATE_OR_QUOTA_LIMIT"), (500, "OPENAI_REQUEST_FAILED")):
            with self.subTest(status=status):
                responses = FakeResponses(error=ProviderError(status))
                with self.assertRaisesRegex(OpenAIWebSearchRetrievalError, code):
                    self.client(responses=responses).retrieve(REQUEST)
                self.assertEqual(len(responses.calls), 1)

    def test_results_are_primary_and_inventory_cannot_erase_richer_metadata(self):
        response = self.client().retrieve(REQUEST)
        by_url = {source.url: source for source in response.sources}
        twse = by_url["https://www.twse.com.tw/company/1216?utm_source=result"]
        yahoo = by_url["https://tw.stock.yahoo.com/quote/1216.TW/news"]
        self.assertEqual(twse.title, "統一(1216) 重大訊息")
        self.assertEqual(twse.snippet, "2026年08月10日 統一(1216) 公告。")
        self.assertEqual(yahoo.title, "統一(1216) 營收新聞")
        self.assertEqual(yahoo.snippet, "2026-08-08 統一(1216) 公布營收。")

    def test_citation_is_fallback_and_generated_message_prose_is_excluded(self):
        response = self.client().retrieve(REQUEST)
        titles = {source.title for source in response.sources}
        self.assertIn("統一(1216) citation-only source", titles)
        self.assertNotIn("Generated prose must never become source evidence.", titles)
        self.assertTrue(all(source.snippet != "Generated prose must never become source evidence." for source in response.sources))

    def test_adapter_merge_is_deterministic_across_output_order(self):
        first = adapt_openai_web_search_response(self.payload)
        reordered = copy.deepcopy(self.payload)
        reordered["output"].reverse()
        second = adapt_openai_web_search_response(reordered)
        self.assertEqual(first.sources, second.sources)

    def test_v1f_service_reuses_temporal_company_and_tier_contracts(self):
        service = build_openai_web_search_retrieval_service(client=self.client())
        artifact = service.retrieve_external_sources(REQUEST, retrieved_at=NOW)
        by_url = {source.canonical_url: source for source in artifact.sources}
        twse = by_url["https://www.twse.com.tw/company/1216"]
        related = by_url["https://marketscreener.com/quote/220"]
        reddit = by_url["https://www.reddit.com/r/stocks/comments/1216"]
        ambiguous = by_url["https://unknown.example/1216"]
        self.assertEqual(twse.source_tier, SourceTier.TIER_1_OFFICIAL)
        self.assertEqual(twse.company_association_status, CompanyAssociationStatus.DIRECT_EXACT)
        self.assertEqual([item.value for item in twse.temporal_evidence], [date(2026, 8, 10)])
        self.assertEqual(related.company_association_status, CompanyAssociationStatus.RELATED_ENTITY)
        self.assertEqual(reddit.source_tier, SourceTier.TIER_4_SOCIAL_COMMUNITY)
        self.assertEqual(ambiguous.source_tier, SourceTier.UNKNOWN)
        self.assertEqual(ambiguous.temporal_evidence, ())

    def test_actual_tool_count_and_policy_warning_are_preserved_in_artifact(self):
        artifact = build_openai_web_search_retrieval_service(client=self.client()).retrieve_external_sources(REQUEST, retrieved_at=NOW)
        self.assertEqual(artifact.observed_web_search_call_count, 2)
        self.assertEqual(artifact.tool_call_accounting_status, ToolCallAccountingStatus.EXCEEDED_EXPECTED_POLICY)
        self.assertIn("OBSERVED_WEB_SEARCH_CALL_COUNT_EXCEEDS_EXPECTED_POLICY", artifact.normalization_warnings)
        self.assertEqual(artifact.responses_request_count, 1)

    def test_missing_web_search_call_fails_closed(self):
        payload = {"status": "completed", "output": [{"type": "message", "content": []}]}
        with self.assertRaisesRegex(OpenAIWebSearchRetrievalError, "WEB_SEARCH_NOT_EXECUTED"):
            adapt_openai_web_search_response(payload)

    def test_incomplete_response_with_partial_sources_fails_closed(self):
        payload = self.partial_payload(response_status="incomplete", tool_status="in_progress")
        with self.assertRaisesRegex(OpenAIWebSearchRetrievalError, "OPENAI_RESPONSE_NOT_COMPLETED"):
            adapt_openai_web_search_response(payload)

    def test_failed_response_with_partial_sources_fails_closed(self):
        payload = self.partial_payload(response_status="failed", tool_status="failed")
        with self.assertRaisesRegex(OpenAIWebSearchRetrievalError, "OPENAI_RESPONSE_NOT_COMPLETED"):
            adapt_openai_web_search_response(payload)

    def test_completed_response_ignores_non_completed_tool_call_evidence_but_keeps_accounting(self):
        payload = copy.deepcopy(self.payload)
        second_call = payload["output"][2]
        second_call["status"] = "searching"
        second_call["results"] = [{
            "type": "text_result",
            "url": "https://partial.example/1216",
            "title": "統一(1216) partial",
            "snippet": "2026-08-09 partial result.",
        }]
        second_call["action"]["sources"].append({"url": "https://partial.example/action"})

        artifact = build_openai_web_search_retrieval_service(client=self.client(responses=FakeResponses(payload))).retrieve_external_sources(REQUEST, retrieved_at=NOW)
        urls = {source.canonical_url for source in artifact.sources}
        self.assertNotIn("https://partial.example/1216", urls)
        self.assertNotIn("https://partial.example/action", urls)
        self.assertEqual(artifact.observed_web_search_call_count, 2)
        self.assertEqual(artifact.tool_call_accounting_status, ToolCallAccountingStatus.EXCEEDED_EXPECTED_POLICY)
        self.assertIn("OBSERVED_WEB_SEARCH_CALL_COUNT_EXCEEDS_EXPECTED_POLICY", artifact.normalization_warnings)

    def test_completed_response_with_only_non_completed_tool_calls_fails_closed(self):
        payload = self.partial_payload(response_status="completed", tool_status="searching")
        with self.assertRaisesRegex(OpenAIWebSearchRetrievalError, "WEB_SEARCH_NOT_COMPLETED"):
            adapt_openai_web_search_response(payload)

    def test_completed_search_without_sources_fails_closed(self):
        payload = {"status": "completed", "output": [{"type": "web_search_call", "status": "completed", "results": [], "action": {"sources": []}}]}
        with self.assertRaisesRegex(OpenAIWebSearchRetrievalError, "NO_CURRENT_EVENT_SOURCES"):
            adapt_openai_web_search_response(payload)

    def test_query_is_deterministic_and_has_no_investment_recommendation_request(self):
        query = build_company_research_query(target=TARGET, start_date=date(2026, 8, 2), end_date=date(2026, 8, 31))
        self.assertIn("1216", query)
        self.assertIn("2026-08-02", query)
        self.assertIn("2026-08-31", query)
        self.assertIn("Do not provide investment advice", query)
        self.assertNotIn("portfolio holdings", query)

    def test_domain_policy_has_only_the_v1g_minimum_mappings(self):
        self.assertEqual(OPENAI_WEB_SEARCH_DOMAIN_MAP["twse.com.tw"], SourceTier.TIER_1_OFFICIAL)
        self.assertEqual(OPENAI_WEB_SEARCH_DOMAIN_MAP["tw.stock.yahoo.com"], SourceTier.TIER_2_ESTABLISHED_MEDIA)
        self.assertEqual(OPENAI_WEB_SEARCH_DOMAIN_MAP["goodinfo.tw"], SourceTier.TIER_3_OTHER_ATTRIBUTABLE)
        self.assertEqual(OPENAI_WEB_SEARCH_DOMAIN_MAP["reddit.com"], SourceTier.TIER_4_SOCIAL_COMMUNITY)

    @staticmethod
    def partial_payload(*, response_status, tool_status):
        return {
            "status": response_status,
            "output": [{
                "type": "web_search_call",
                "status": tool_status,
                "results": [{
                    "url": "https://partial.example/1216",
                    "title": "統一(1216) partial",
                    "snippet": "2026-08-09 partial result.",
                }],
                "action": {"sources": [{"url": "https://partial.example/action"}]},
            }],
        }


if __name__ == "__main__":
    unittest.main()
