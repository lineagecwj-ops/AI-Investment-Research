import sys
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ai_dashboard import build_request_fingerprint
from ai_dashboard import evidence_lookup
from ai_dashboard import format_evidence_period
from ai_dashboard import format_evidence_value
from ai_dashboard import is_openai_api_configured
from ai_dashboard import normalize_question_type
from ai_dashboard import question_type_help
from ai_dashboard import question_type_label
from ai_dashboard import question_type_options
from ai_dashboard import resolve_evidence_lineage
from ai_dashboard import safe_error_details
from ai_dashboard import safe_error_message
from ai_dashboard import source_type_label
from ai_research_service import AIConfigurationError
from ai_research_service import AIIncompleteResponseError
from ai_research_service import AIProviderError
from ai_research_service import AIRefusalError
from ai_research_service import AIGroundingError
from ai_research_service import AINumericGroundingError
from ai_research_service import AIStructuredOutputError
from research_context import EvidenceItem
from research_context import MissingDataItem
from research_context import ResearchLimitation
from research_context_selector import ResearchQuestionType
from research_context_selector import SelectedResearchContext


GENERATED_AT = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


class AIDashboardTestCase(unittest.TestCase):

    def selected_context(self, *, question_type=ResearchQuestionType.GROWTH, evidence=None):
        return SelectedResearchContext(
            symbol="2454.TW",
            display_name="聯發科",
            question_type=question_type,
            selected_evidence=evidence if evidence is not None else self.sample_evidence(),
            selected_observation_links=[],
            selected_observations=[],
            selected_missing_data=[
                MissingDataItem(
                    id="missing:historical:eps:2025-12-31",
                    area="historical",
                    metric="eps",
                    period_end=date(2025, 12, 31),
                    period_year=2025,
                    reason="Yahoo Finance annual statement value unavailable",
                    impact="EPS YoY cannot be calculated.",
                    source="Yahoo Finance annual financial statement",
                )
            ],
            selected_limitations=[
                ResearchLimitation(
                    id="global:annual_historical_data_only",
                    category="data_scope",
                    message="Historical financial context uses annual financial statement periods only.",
                    scope="global",
                )
            ],
            selection_notes=[],
            generated_at=GENERATED_AT,
            source_context_generated_at=GENERATED_AT,
            source_evidence_count=12,
        )

    def sample_evidence(self):
        return [
            EvidenceItem(
                id="current:revenue_growth",
                category="current_snapshot",
                metric="revenue_growth",
                value=0.1232,
                unit="ratio",
                currency=None,
                period_end=None,
                period_year=None,
                source="Yahoo Finance current snapshot",
                source_type="source",
            ),
            EvidenceItem(
                id="historical:revenue:2024-12-31",
                category="historical_financials",
                metric="revenue",
                value=95_123_456_789.12345,
                unit="currency_amount",
                currency="TWD",
                period_end=date(2024, 12, 31),
                period_year=2024,
                source="Yahoo Finance annual financial statement",
                source_type="source",
            ),
            EvidenceItem(
                id="historical:revenue:2025-12-31",
                category="historical_financials",
                metric="revenue",
                value=110_000_000_000,
                unit="currency",
                currency="TWD",
                period_end=date(2025, 12, 31),
                period_year=2025,
                source="Yahoo Finance annual financial statement",
                source_type="source",
            ),
            EvidenceItem(
                id="derived:revenue_yoy:2025-12-31",
                category="historical_derived",
                metric="revenue_yoy",
                value=0.1579,
                unit="ratio",
                currency=None,
                period_end=date(2025, 12, 31),
                period_year=2025,
                source="research_metrics.calculate_yoy_growth",
                source_type="derived",
                derived_from=(
                    "historical:revenue:2024-12-31",
                    "historical:revenue:2025-12-31",
                ),
            ),
        ]

    def test_question_type_labels_and_help_cover_all_enums(self):
        self.assertEqual(set(question_type_options()), set(ResearchQuestionType))

        for question_type in ResearchQuestionType:
            label = question_type_label(question_type)
            help_text = question_type_help(question_type)
            self.assertIn("（", label)
            self.assertIn("）", label)
            self.assertTrue(help_text)

    def test_question_type_helpers_accept_value_and_enum_like_values_after_rerun(self):
        self.assertEqual(normalize_question_type("growth"), ResearchQuestionType.GROWTH)
        self.assertEqual(
            question_type_label(SimpleNamespace(value="growth")),
            "Growth（成長）",
        )
        self.assertIn("Revenue", question_type_help(SimpleNamespace(value="growth")))

    def test_request_fingerprint_is_stable_and_changes_for_inputs(self):
        selected = self.selected_context()
        baseline = build_request_fingerprint(
            symbol="2454.TW",
            question_type=ResearchQuestionType.GROWTH,
            question="請說明成長變化。",
            selected_context=selected,
        )

        self.assertEqual(
            baseline,
            build_request_fingerprint(
                symbol="2454.TW",
                question_type=ResearchQuestionType.GROWTH,
                question="請說明成長變化。",
                selected_context=selected,
            ),
        )
        self.assertNotEqual(
            baseline,
            build_request_fingerprint(
                symbol="2454.TW",
                question_type=ResearchQuestionType.GROWTH,
                question="請說明估值變化。",
                selected_context=selected,
            ),
        )
        self.assertNotEqual(
            baseline,
            build_request_fingerprint(
                symbol="2454.TW",
                question_type=ResearchQuestionType.VALUATION,
                question="請說明成長變化。",
                selected_context=self.selected_context(question_type=ResearchQuestionType.VALUATION),
            ),
        )

    def test_request_fingerprint_changes_for_evidence_ids_and_ignores_api_key(self):
        selected = self.selected_context()
        alternate_evidence = [
            item if item.id != "current:revenue_growth" else EvidenceItem(
                id="current:earnings_growth",
                category=item.category,
                metric="earnings_growth",
                value=item.value,
                unit=item.unit,
                currency=item.currency,
                period_end=item.period_end,
                period_year=item.period_year,
                source=item.source,
                source_type=item.source_type,
            )
            for item in self.sample_evidence()
        ]
        alternate = self.selected_context(evidence=alternate_evidence)

        first = build_request_fingerprint(
            symbol="2454.TW",
            question_type=ResearchQuestionType.GROWTH,
            question="請說明成長變化。",
            selected_context=selected,
        )
        second = build_request_fingerprint(
            symbol="2454.TW",
            question_type=ResearchQuestionType.GROWTH,
            question="請說明成長變化。",
            selected_context=alternate,
        )

        self.assertNotEqual(first, second)
        self.assertEqual(len(first), 64)
        self.assertTrue(all(character in "0123456789abcdef" for character in first))

    def test_evidence_formatting(self):
        revenue_growth = self.sample_evidence()[0]
        revenue = self.sample_evidence()[1]
        negative_ratio = EvidenceItem(
            id="derived:revenue_yoy:2023-12-31",
            category="historical_derived",
            metric="revenue_yoy",
            value=-0.34878012345,
            unit="ratio",
            currency=None,
            period_end=date(2023, 12, 31),
            period_year=2023,
            source="research_metrics.calculate_yoy_growth",
            source_type="derived",
        )
        price = EvidenceItem(
            id="current:current_price",
            category="current_snapshot",
            metric="current_price",
            value=1250,
            unit="price",
            currency="TWD",
            period_end=None,
            period_year=None,
            source="Yahoo Finance current snapshot",
            source_type="source",
        )
        eps = EvidenceItem(
            id="historical:eps:2025-12-31",
            category="historical_financials",
            metric="eps",
            value=12.3456789,
            unit="per_share",
            currency=None,
            period_end=date(2025, 12, 31),
            period_year=2025,
            source="Yahoo Finance annual financial statement",
            source_type="source",
        )
        multiple = EvidenceItem(
            id="current:trailing_pe",
            category="current_snapshot",
            metric="trailing_pe",
            value=25.345,
            unit="multiple",
            currency=None,
            period_end=None,
            period_year=None,
            source="Yahoo Finance current snapshot",
            source_type="source",
        )
        decimal = EvidenceItem(
            id="current:trailing_pe",
            category="current_snapshot",
            metric="trailing_pe",
            value=25.345,
            unit=None,
            currency=None,
            period_end=None,
            period_year=None,
            source="Yahoo Finance current snapshot",
            source_type="source",
        )
        missing = EvidenceItem(
            id="test:missing",
            category="test",
            metric="test",
            value=None,
            unit=None,
            currency=None,
            period_end=None,
            period_year=None,
            source="test",
            source_type="source",
        )

        self.assertEqual(format_evidence_value(revenue_growth), "12.32%")
        self.assertEqual(format_evidence_value(negative_ratio), "-34.88%")
        self.assertEqual(format_evidence_value(revenue), "TWD 95.12B")
        self.assertEqual(format_evidence_value(price), "TWD 1,250.00")
        self.assertEqual(format_evidence_value(eps), "12.35")
        self.assertEqual(format_evidence_value(multiple), "25.34")
        self.assertEqual(format_evidence_value(decimal), "25.34")
        self.assertEqual(format_evidence_value(missing), "N/A")
        self.assertEqual(format_evidence_period(date(2025, 12, 31)), "FY ending 2025-12-31")
        self.assertEqual(source_type_label("derived"), "衍生計算")
        self.assertEqual(source_type_label("source"), "原始資料")
        self.assertEqual(revenue_growth.value, 0.1232)
        self.assertEqual(negative_ratio.value, -0.34878012345)
        self.assertEqual(revenue.value, 95_123_456_789.12345)
        self.assertEqual(eps.value, 12.3456789)

    def test_evidence_lineage_resolves_sources_and_missing_safely(self):
        selected = self.selected_context()
        lookup = evidence_lookup(selected)

        lineage = resolve_evidence_lineage("derived:revenue_yoy:2025-12-31", lookup)
        self.assertEqual(
            [item.id for item in lineage if isinstance(item, EvidenceItem)],
            ["historical:revenue:2024-12-31", "historical:revenue:2025-12-31"],
        )

        derived_with_missing_source = EvidenceItem(
            id="derived:test",
            category="test",
            metric="test",
            value=1,
            unit=None,
            currency=None,
            period_end=None,
            period_year=None,
            source="test",
            source_type="derived",
            derived_from=("missing:source",),
        )
        self.assertEqual(
            resolve_evidence_lineage("derived:test", {"derived:test": derived_with_missing_source}),
            ["missing:source"],
        )

    def test_safe_error_messages_do_not_leak_tracebacks(self):
        errors = [
            AIConfigurationError("secret token should not leak"),
            AIProviderError("provider failed"),
            AIIncompleteResponseError(
                response_id="resp_123",
                reason="max_output_tokens",
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                reasoning_tokens=5,
                cached_input_tokens=2,
            ),
            AIRefusalError("refusal"),
            AIStructuredOutputError("bad json"),
            AIGroundingError("unknown evidence"),
            AINumericGroundingError(
                statement="bad 99%",
                claims=[],
                cited_evidence_ids=[],
                candidates=[],
                reason="unsupported_percentage_claim",
            ),
        ]

        for error in errors:
            message = safe_error_message(error)
            self.assertNotIn("Traceback", message)
            self.assertNotIn("secret token", message)

        details = safe_error_details(errors[2])
        self.assertEqual(details["response_id"], "resp_123")
        self.assertEqual(details["incomplete_reason"], "max_output_tokens")

    def test_api_key_status_is_boolean_only(self):
        self.assertFalse(is_openai_api_configured({"OPENAI_API_KEY": ""}))
        self.assertTrue(is_openai_api_configured({"OPENAI_API_KEY": "configured-value"}))


if __name__ == "__main__":
    unittest.main()
