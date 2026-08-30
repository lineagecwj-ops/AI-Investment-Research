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
from external_source import ExternalSourceError
from external_source import RawWebSearchSource
from external_source import RelatedCompanyIdentity
from external_source import ResearchWindowStatus
from external_source import SourceStatus
from external_source import SourceTier
from external_source import TargetCompanyIdentity
from external_source import canonicalize_url
from external_source import classify_company_association
from external_source import classify_source_tier
from external_source import deduplicate_sources
from external_source import extract_temporal_evidence
from external_source import is_primary_factual_evidence
from external_source import normalize_external_source
from external_source import parse_structured_source_date
from external_source import validate_research_window


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)
TARGET = TargetCompanyIdentity(
    symbol="1216.TW",
    canonical_name="統一",
    validated_english_name="Uni-President Enterprises Corp.",
    supported_aliases=("統一(1216)",),
)
RELATED = (
    RelatedCompanyIdentity(
        canonical_name="Uni-President China Holdings Ltd.",
        security_codes=("220",),
        aliases=("統一中國",),
    ),
)
DOMAIN_MAP = {
    "uni-president.com.tw": SourceTier.TIER_1_OFFICIAL,
    "twse.com.tw": SourceTier.TIER_1_OFFICIAL,
    "money.udn.com": SourceTier.TIER_2_ESTABLISHED_MEDIA,
    "reddit.com": SourceTier.TIER_4_SOCIAL_COMMUNITY,
}


class ExternalSourceTestCase(unittest.TestCase):
    def fixture_sources(self):
        payload = json.loads((PROJECT_ROOT / "tests/fixtures/catalyst_v1f_web_search_results.json").read_text(encoding="utf-8"))
        return {item["name"]: RawWebSearchSource(**{key: value for key, value in item.items() if key != "name"}) for item in payload["sources"]}

    def normalize(self, raw):
        return normalize_external_source(raw, target=TARGET, retrieved_at=NOW, domain_map=DOMAIN_MAP, related_entities=RELATED)

    def test_parses_unambiguous_date_patterns_and_rejects_relative_or_ambiguous_dates(self):
        self.assertEqual([item.value for item in extract_temporal_evidence("2026-08-06 / 2026/08/10")], [date(2026, 8, 6), date(2026, 8, 10)])
        self.assertEqual([item.value for item in extract_temporal_evidence("2026 年 08 月 10 日")], [date(2026, 8, 10)])
        self.assertEqual([item.value for item in extract_temporal_evidence("10 Aug 2026 and Aug 11, 2026")], [date(2026, 8, 10), date(2026, 8, 11)])
        self.assertEqual(extract_temporal_evidence("3 weeks ago and 08/06/2026"), ())

    def test_source_date_is_separate_from_event_dates_and_retrieved_at_is_never_substituted(self):
        source = self.normalize(self.fixture_sources()["multiple_events"])
        self.assertIsNone(source.source_published_at)
        self.assertEqual([item.value for item in source.temporal_evidence], [date(2026, 8, 6), date(2026, 8, 10)])
        self.assertNotIn(NOW.date(), [item.value for item in source.temporal_evidence])

    def test_structured_datetime_retains_datetime_precision(self):
        parsed = parse_structured_source_date("2026-08-10T09:30:00+08:00")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.precision.value, "DATETIME")
        self.assertEqual(parsed.value.isoformat(), "2026-08-10T09:30:00+08:00")

    def test_structured_date_only_retains_date_precision_without_a_fabricated_time(self):
        parsed = parse_structured_source_date("2026-08-10")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.precision.value, "DATE")
        self.assertEqual(type(parsed.value), date)
        self.assertEqual(parsed.value.isoformat(), "2026-08-10")

    def test_window_validation_is_explicit_and_fail_closed_for_unknown_date(self):
        source = self.normalize(self.fixture_sources()["direct_1216_official"])
        self.assertEqual(validate_research_window(source.temporal_evidence[0], start_date=date(2026, 8, 2), end_date=date(2026, 8, 31)), ResearchWindowStatus.IN_WINDOW)
        self.assertEqual(validate_research_window(source.temporal_evidence[0], start_date=date(2026, 8, 11), end_date=date(2026, 8, 31)), ResearchWindowStatus.OUT_OF_WINDOW)
        self.assertEqual(validate_research_window(None, start_date=date(2026, 8, 2), end_date=date(2026, 8, 31)), ResearchWindowStatus.UNKNOWN)

    def test_company_association_is_direct_for_target_and_related_company_stays_separate(self):
        direct = self.normalize(self.fixture_sources()["direct_1216_official"])
        related = self.normalize(self.fixture_sources()["related_220_media"])
        self.assertEqual(direct.company_association_status, CompanyAssociationStatus.DIRECT_EXACT)
        self.assertEqual(related.company_association_status, CompanyAssociationStatus.RELATED_ENTITY)
        self.assertEqual(classify_company_association(title="Uni-President overview", excerpt=None, target=TARGET, related_entities=RELATED), CompanyAssociationStatus.AMBIGUOUS)

    def test_suspicious_url_suffix_cannot_override_canonical_identity_evidence(self):
        source = self.normalize(self.fixture_sources()["multiple_events"])
        self.assertIn("1216.TWO", source.source_url)
        self.assertEqual(source.company_association_status, CompanyAssociationStatus.DIRECT_EXACT)

    def test_source_tier_mapping_is_program_owned_and_social_is_not_primary(self):
        self.assertEqual(classify_source_tier("sub.uni-president.com.tw", DOMAIN_MAP), SourceTier.TIER_1_OFFICIAL)
        self.assertEqual(classify_source_tier("money.udn.com", DOMAIN_MAP), SourceTier.TIER_2_ESTABLISHED_MEDIA)
        social = self.normalize(self.fixture_sources()["tier_4_social"])
        self.assertEqual(social.source_tier, SourceTier.TIER_4_SOCIAL_COMMUNITY)
        self.assertFalse(is_primary_factual_evidence(social))
        self.assertTrue(is_primary_factual_evidence(self.normalize(self.fixture_sources()["tier_2_media"])))
        self.assertEqual(classify_source_tier("unknown.example", DOMAIN_MAP), SourceTier.UNKNOWN)

    def test_url_canonicalization_removes_tracking_without_rewriting_meaningful_ticker_suffix(self):
        canonical = canonicalize_url("HTTPS://Example.test/news?b=2&utm_source=x&a=1#part")
        self.assertEqual(canonical, "https://example.test/news?a=1&b=2")
        self.assertEqual(canonicalize_url("https://tw.stock.yahoo.com/quote/1216.TWO/news"), "https://tw.stock.yahoo.com/quote/1216.TWO/news")

    def test_url_dedup_and_title_fallback_are_deterministic(self):
        first = self.normalize(self.fixture_sources()["direct_1216_official"])
        second = self.normalize(RawWebSearchSource(
            url="https://www.uni-president.com.tw/news/revenue?utm_medium=search",
            title="different title",
            snippet="2026-08-10",
        ))
        third = self.normalize(RawWebSearchSource(url="https://www.uni-president.com.tw/another", title="統一(1216) different article", snippet="2026-08-10"))
        self.assertEqual(len(deduplicate_sources((first, second, third))), 2)
        no_url_a = self.normalize(RawWebSearchSource(url=None, domain="example.test", title="Fallback title", snippet=None))
        no_url_b = self.normalize(RawWebSearchSource(url=None, domain="example.test", title=" fallback  title ", snippet=None))
        self.assertEqual(len(deduplicate_sources((no_url_a, no_url_b))), 1)

    def test_malformed_source_status_and_excerpt_truncation_are_explicit(self):
        malformed = self.normalize(self.fixture_sources()["malformed_missing_title"])
        self.assertEqual(malformed.source_status, SourceStatus.MISSING_TITLE)
        truncated = normalize_external_source(
            RawWebSearchSource(url="https://example.test/a", title="統一(1216)", snippet="x" * 12),
            target=TARGET,
            retrieved_at=NOW,
            max_excerpt_length=10,
        )
        self.assertTrue(truncated.source_excerpt_truncated)
        self.assertEqual(truncated.source_excerpt, "x" * 10)
        with self.assertRaisesRegex(ExternalSourceError, "positive"):
            normalize_external_source(RawWebSearchSource(url="https://example.test/a", title="x", snippet="x"), target=TARGET, retrieved_at=NOW, max_excerpt_length=0)


if __name__ == "__main__":
    unittest.main()
