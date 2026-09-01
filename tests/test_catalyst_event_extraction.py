import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from catalyst_event import CandidateStatus
from catalyst_event import CatalystEventType
from catalyst_event import EventConflictStatus
from catalyst_event import EventValidationStatus
from catalyst_identity_catalog import ApprovedAlias
from catalyst_identity_catalog import ListedCompanyIdentity
from catalyst_identity_catalog import TaiwanListedCompanyIdentityCatalog
from catalyst_event_extraction import cluster_validated_events
from catalyst_event_extraction import extract_event_candidates
from catalyst_event_extraction import validate_event_candidate
from external_source import CompanyAssociationStatus
from external_source import RawWebSearchSource
from external_source import RelatedCompanyIdentity
from external_source import SourceTier
from external_source import TargetCompanyIdentity
from external_source import normalize_external_source


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)
WINDOW = (date(2026, 8, 1), date(2026, 8, 31))
TARGET = TargetCompanyIdentity("1216.TW", "統一", "Uni-President Enterprises Corp.", ("統一(1216)",))
TARGET_5866 = TargetCompanyIdentity("5866.TW", "統一期", None, ("統一期(5866)",))
RELATED = (RelatedCompanyIdentity("Uni-President China Holdings Ltd.", ("220",), ("統一中國",)),)
DOMAIN_MAP = {
    "official.test": SourceTier.TIER_1_OFFICIAL,
    "media.test": SourceTier.TIER_2_ESTABLISHED_MEDIA,
    "other.test": SourceTier.TIER_3_OTHER_ATTRIBUTABLE,
    "social.test": SourceTier.TIER_4_SOCIAL_COMMUNITY,
}


def source(url, title, snippet, *, target=TARGET):
    return normalize_external_source(
        RawWebSearchSource(url=url, title=title, snippet=snippet),
        target=target,
        retrieved_at=NOW,
        domain_map=DOMAIN_MAP,
        related_entities=RELATED,
    )


def candidates(*sources, target=TARGET, identity_catalog=None):
    return extract_event_candidates(
        sources,
        target_symbol=target.symbol,
        target_company_name=target.canonical_name,
        validated_aliases=target.supported_aliases,
        research_window=WINDOW,
        identity_catalog=identity_catalog,
    )


class CatalystEventExtractionTestCase(unittest.TestCase):
    def test_single_structured_earnings_event_is_validated(self):
        item = source("https://official.test/earnings", "統一(1216) 重大訊息", "日 期：2026年08月06日，統一(1216)董事會通過第二季財務報告。")
        extracted = candidates(item)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0].candidate_type, CatalystEventType.EARNINGS_RESULT)
        events = cluster_validated_events(extracted, sources=(item,), research_window=WINDOW)
        self.assertEqual(events[0].validation_status, EventValidationStatus.VALIDATED)

    def test_monthly_revenue_is_deterministically_classified(self):
        item = source("https://official.test/revenue", "統一(1216) 營收公告", "日期：2026-08-10，統一(1216) 公告 7 月合併營收。")
        extracted = candidates(item)
        self.assertEqual(extracted[0].candidate_type, CatalystEventType.REVENUE_UPDATE)
        self.assertEqual(validate_event_candidate(extracted[0], source=item, research_window=WINDOW), EventValidationStatus.VALIDATED)

    def test_investor_conference_precedes_generic_investment_and_true_capex_remains_capex(self):
        conference = source("https://official.test/conference", "統一(1216) 公告", "2026-08-10 統一(1216) 召開投資人說明會。")
        capex = source("https://official.test/capex", "統一(1216) 公告", "2026-08-10 統一(1216) 公告擴建新廠並增加產能。")
        generic_investment = source("https://official.test/generic-investment", "統一(1216) 公告", "2026-08-10 統一(1216) 投資人關注公司發展。")
        self.assertEqual(candidates(conference)[0].candidate_type, CatalystEventType.MANAGEMENT_GOVERNANCE)
        self.assertEqual(candidates(capex)[0].candidate_type, CatalystEventType.CAPEX_CAPACITY)
        self.assertEqual(candidates(generic_investment)[0].candidate_type, CatalystEventType.OTHER)

    def test_one_source_produces_three_distinct_candidates(self):
        item = source(
            "https://official.test/multi",
            "統一(1216) 重大訊息",
            "日期：2026-08-06，董事會通過第二季財報。日期：2026-08-10，公告 7 月合併營收。日期：2026-08-10，召開法說會。",
        )
        extracted = candidates(item)
        self.assertEqual(len(extracted), 3)
        self.assertEqual({item.candidate_type for item in extracted}, {
            CatalystEventType.EARNINGS_RESULT, CatalystEventType.REVENUE_UPDATE, CatalystEventType.MANAGEMENT_GOVERNANCE,
        })
        self.assertTrue(all(item.candidate_anchor and len(item.candidate_anchor) <= 360 for item in extracted))

    def test_official_and_yahoo_same_event_cluster_with_tier_one_primary(self):
        official = source("https://official.test/july", "統一(1216) 營收", "2026-08-10 統一(1216) 公告 7 月合併營收。")
        yahoo = source("https://media.test/july", "統一(1216) monthly revenue", "2026-08-10 統一(1216) announced July revenue.")
        extracted = candidates(official, yahoo)
        events = cluster_validated_events(extracted, sources=(official, yahoo), research_window=WINDOW)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].support_count, 2)
        self.assertEqual(events[0].primary_source_id, official.source_id)
        self.assertEqual(events[0].validation_status, EventValidationStatus.VALIDATED)

    def test_tier_two_is_an_acceptable_primary_without_tier_one(self):
        media = source("https://media.test/july", "統一(1216) 營收", "2026-08-10 統一(1216) 公告 7 月合併營收。")
        event = cluster_validated_events(candidates(media), sources=(media,), research_window=WINDOW)[0]
        self.assertEqual(event.primary_source_id, media.source_id)
        self.assertEqual(event.validation_status, EventValidationStatus.VALIDATED)

    def test_same_day_different_events_remain_separate(self):
        item = source("https://official.test/same-day", "統一(1216) 公告", "2026-08-10 公告 7 月合併營收。2026-08-10 召開法說會。")
        events = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)
        self.assertEqual(len(events), 2)
        self.assertEqual({event.event_type for event in events}, {CatalystEventType.REVENUE_UPDATE, CatalystEventType.MANAGEMENT_GOVERNANCE})

    def test_same_day_same_type_different_reporting_subjects_remain_separate(self):
        item = source(
            "https://official.test/report-subjects",
            "統一(1216) 公告",
            "2026-08-10 董事會通過第二季財務報告。2026-08-10 董事會通過上半年財務報告。",
        )
        events = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)
        self.assertEqual(len(events), 2)
        self.assertEqual({event.event_type for event in events}, {CatalystEventType.EARNINGS_RESULT})
        self.assertEqual(len({event.event_key for event in events}), 2)
        self.assertEqual(len({event.event_id for event in events}), 2)

    def test_related_entity_remains_partial_and_separate(self):
        related = source("https://media.test/220", "Uni-President China Holdings Ltd. (220)", "2026-08-10 Uni-President China announced July revenue.")
        extracted = candidates(related)
        events = cluster_validated_events(extracted, sources=(related,), research_window=WINDOW)
        self.assertEqual(extracted[0].company_association_status, CompanyAssociationStatus.RELATED_ENTITY)
        self.assertEqual(events[0].validation_status, EventValidationStatus.PARTIALLY_VALIDATED)

    def test_ambiguous_company_and_missing_title_fail_closed(self):
        ambiguous = source("https://media.test/ambiguous", "Uni-President update", "2026-08-10 announced monthly revenue.")
        missing_title = source("https://official.test/missing-title", None, "2026-08-10 統一(1216) 公告月營收。")
        for item in (ambiguous, missing_title):
            event = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)[0]
            self.assertEqual(event.validation_status, EventValidationStatus.REJECTED)

    def test_relative_and_ambiguous_dates_never_validate(self):
        for url, snippet in (
            ("https://official.test/relative", "統一(1216) 3 weeks ago 公告月營收。"),
            ("https://official.test/ambiguous-date", "統一(1216) 08/06/2026 公告月營收。"),
        ):
            item = source(url, "統一(1216) 營收", snippet)
            event = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)[0]
            self.assertEqual(event.validation_status, EventValidationStatus.PARTIALLY_VALIDATED)

    def test_tier_three_alone_does_not_validate_and_tier_four_cannot_be_primary(self):
        tier_three = source("https://other.test/revenue", "統一(1216) 營收", "2026-08-10 統一(1216) 公告 7 月營收。")
        tier_four = source("https://social.test/revenue", "統一(1216) 營收", "2026-08-10 統一(1216) 公告 7 月營收。")
        tier_three_event = cluster_validated_events(candidates(tier_three), sources=(tier_three,), research_window=WINDOW)[0]
        self.assertEqual(tier_three_event.validation_status, EventValidationStatus.PARTIALLY_VALIDATED)
        self.assertEqual(tier_three_event.primary_source_id, tier_three.source_id)
        tier_four_event = cluster_validated_events(candidates(tier_four), sources=(tier_four,), research_window=WINDOW)[0]
        self.assertEqual(tier_four_event.validation_status, EventValidationStatus.PARTIALLY_VALIDATED)
        self.assertIsNone(tier_four_event.primary_source_id)

    def test_conflicting_dates_do_not_silently_merge(self):
        first = source("https://official.test/july-one", "統一(1216) 營收", "2026-08-09 統一(1216) 公告 7 月營收。")
        second = source("https://media.test/july-two", "統一(1216) 營收", "2026-08-10 統一(1216) 公告 July revenue.")
        event = cluster_validated_events(candidates(first, second), sources=(first, second), research_window=WINDOW)[0]
        self.assertEqual(event.conflict_status, EventConflictStatus.SOURCE_DATE)
        self.assertEqual(event.validation_status, EventValidationStatus.REJECTED)

    def test_background_only_and_duplicate_url_are_explicit_and_deterministic(self):
        profile = source("https://official.test/profile", "統一(1216) 公司介紹", "Company profile without an event.")
        duplicate_a = source("https://official.test/revenue?utm_source=x", "統一(1216) 營收", "2026-08-10 統一(1216) 公告 7 月營收。")
        duplicate_b = source("https://official.test/revenue?utm_source=y", "統一(1216) 不同標題", "2026-08-10 統一(1216) 公告 7 月營收。")
        background = candidates(profile)[0]
        self.assertEqual(background.candidate_status, CandidateStatus.BACKGROUND_ONLY)
        self.assertEqual(cluster_validated_events((background,), sources=(profile,), research_window=WINDOW)[0].validation_status, EventValidationStatus.BACKGROUND_ONLY)
        first = cluster_validated_events(candidates(duplicate_a, duplicate_b), sources=(duplicate_a, duplicate_b), research_window=WINDOW)
        second = cluster_validated_events(candidates(duplicate_b, duplicate_a), sources=(duplicate_b, duplicate_a), research_window=WINDOW)
        self.assertEqual(first, second)
        self.assertEqual(first[0].support_count, 1)

    def test_candidate_local_identity_blocks_other_company_on_target_calendar_page(self):
        item = source(
            "https://media.test/calendar",
            "Uni-President Enterprises Corp. financial calendar | 1216",
            "2026-08-31 | PRESIDENT BAKERY | Ex-dividend date - 0.25 THB | 12:00 am",
        )
        extracted = candidates(item)
        self.assertEqual(extracted[0].company_association_status, CompanyAssociationStatus.AMBIGUOUS)
        event = cluster_validated_events(extracted, sources=(item,), research_window=WINDOW)[0]
        self.assertEqual(event.validation_status, EventValidationStatus.REJECTED)

    def test_mixed_named_listed_company_identity_fails_closed_for_target(self):
        item = source(
            "https://media.test/mixed-company",
            "統一(1216) 公告",
            "日期：2026年08月10日 統一期(5866)公布7月合併營收；"
            "統一(1216)受邀參加麥格理證券舉辦之投資人說明會。",
        )
        extracted = candidates(item)
        self.assertEqual(extracted[0].company_association_status, CompanyAssociationStatus.AMBIGUOUS)
        event = cluster_validated_events(extracted, sources=(item,), research_window=WINDOW)[0]
        self.assertEqual(event.validation_status, EventValidationStatus.REJECTED)

    def test_alias_only_mixed_identity_fails_closed_for_real_retest_shape(self):
        item = source(
            "https://media.test/alias-only-mixed-company",
            "統一(1216) 營收公告",
            "日期：2026年08月10日 統一企業(1216)公布7月營收；展望8月，統一超表示台灣7-ELEVEN將持續展店。",
        )
        event = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)[0]
        self.assertEqual(event.company_association_status, CompanyAssociationStatus.AMBIGUOUS)
        self.assertEqual(event.validation_status, EventValidationStatus.REJECTED)

    def test_alias_only_mixed_candidate_remains_isolated_from_clean_candidate(self):
        clean = source(
            "https://official.test/clean-alias-isolation",
            "統一(1216) 公告",
            "日期：2026年08月10日 統一企業(1216)公告7月合併營收。",
        )
        mixed = source(
            "https://media.test/mixed-alias-isolation",
            "統一(1216) 公告",
            "日期：2026年08月10日 統一企業(1216)公告7月合併營收；統一超表示台灣7-ELEVEN將持續展店。",
        )
        events = cluster_validated_events(candidates(clean, mixed), sources=(clean, mixed), research_window=WINDOW)
        validated = next(event for event in events if event.validation_status is EventValidationStatus.VALIDATED)
        rejected = next(event for event in events if event.validation_status is EventValidationStatus.REJECTED)
        self.assertEqual(len(events), 2)
        self.assertEqual(validated.source_ids, (clean.source_id,))
        self.assertEqual(rejected.source_ids, (mixed.source_id,))
        self.assertEqual(validated.event_fact, candidates(clean)[0].candidate_anchor)
        self.assertNotIn("統一超", validated.event_fact)

    def test_generic_unique_alias_attribution_fails_closed_without_substring_matching(self):
        catalog = TaiwanListedCompanyIdentityCatalog(
            version="TEST",
            checksum="a" * 64,
            records=(
                ListedCompanyIdentity("1000.TW", "甲公司股份有限公司", "甲公司", (ApprovedAlias("甲公司", "OFFICIAL_SHORT_NAME"),), "TWSE"),
                ListedCompanyIdentity("2000.TWO", "乙公司股份有限公司", "乙公司", (ApprovedAlias("乙公司", "OFFICIAL_SHORT_NAME"),), "TPEx"),
            ),
            resolvable_alias_count=2,
            ambiguous_alias_count=0,
        )
        target = TargetCompanyIdentity("1000.TW", "甲公司", None, ("甲公司(1000)",))
        item = source(
            "https://media.test/generic-alias",
            "甲公司(1000) 營收公告",
            "日期：2026年08月10日 甲公司(1000)公布7月營收；乙公司表示將擴充產能。",
            target=target,
        )
        event = cluster_validated_events(
            candidates(item, target=target, identity_catalog=catalog),
            sources=(item,),
            research_window=WINDOW,
        )[0]
        self.assertEqual(event.validation_status, EventValidationStatus.REJECTED)
        self.assertEqual(catalog.find_explicit_non_target_identities("非乙公司表示", "1000.TW"), ())

    def test_mixed_and_clean_candidates_with_same_revenue_subject_remain_isolated(self):
        clean = source(
            "https://official.test/clean-cluster-isolation",
            "統一(1216) 公告",
            "日期：2026年08月10日 統一(1216)公告 7 月合併營收。",
        )
        mixed = source(
            "https://media.test/mixed-cluster-isolation",
            "統一(1216) 公告",
            "日期：2026年08月10日 統一(1216)公告 7 月合併營收；統一期(5866)亦公布 7 月合併營收。",
        )
        extracted = candidates(clean, mixed)
        events = cluster_validated_events(extracted, sources=(clean, mixed), research_window=WINDOW)
        validated = next(event for event in events if event.validation_status is EventValidationStatus.VALIDATED)
        rejected = next(event for event in events if event.validation_status is EventValidationStatus.REJECTED)

        self.assertEqual(len(events), 2)
        self.assertEqual(validated.source_ids, (clean.source_id,))
        self.assertEqual(rejected.source_ids, (mixed.source_id,))
        self.assertEqual(validated.company_association_status, CompanyAssociationStatus.DIRECT_EXACT)
        self.assertEqual(rejected.company_association_status, CompanyAssociationStatus.AMBIGUOUS)
        self.assertEqual(validated.support_count, 1)
        self.assertEqual(rejected.support_count, 1)

    def test_mixed_candidate_cannot_become_primary_fact_for_clean_validated_event(self):
        clean = source(
            "https://official.test/clean-primary-isolation",
            "統一(1216) 公告",
            "日期：2026年08月10日 統一(1216)公告 7 月合併營收。",
        )
        mixed = source(
            "https://media.test/mixed-primary-isolation",
            "統一(1216) 公告",
            "日期：2026年08月10日 統一(1216)公告 7 月合併營收；統一期(5866)亦公布 7 月合併營收。",
        )
        extracted = candidates(clean, mixed)
        events = cluster_validated_events(extracted, sources=(clean, mixed), research_window=WINDOW)
        validated = next(event for event in events if event.validation_status is EventValidationStatus.VALIDATED)
        clean_candidate = next(candidate for candidate in extracted if candidate.source_id == clean.source_id)
        mixed_candidate = next(candidate for candidate in extracted if candidate.source_id == mixed.source_id)

        self.assertEqual(validated.primary_source_id, clean.source_id)
        self.assertEqual(validated.event_fact, clean_candidate.candidate_anchor)
        self.assertNotEqual(validated.event_fact, mixed_candidate.candidate_anchor)
        self.assertNotIn("5866", validated.event_fact)
        self.assertNotIn("統一期", validated.event_fact)

    def test_mixed_named_listed_company_identity_fails_closed_for_reverse_target(self):
        item = source(
            "https://media.test/mixed-company-reverse",
            "統一期(5866) 公告",
            "日期：2026年08月10日 統一期(5866)公布7月合併營收；"
            "統一(1216)受邀參加投資人說明會。",
            target=TARGET_5866,
        )
        extracted = candidates(item, target=TARGET_5866)
        self.assertEqual(extracted[0].company_association_status, CompanyAssociationStatus.AMBIGUOUS)
        event = cluster_validated_events(extracted, sources=(item,), research_window=WINDOW)[0]
        self.assertEqual(event.validation_status, EventValidationStatus.REJECTED)

    def test_structured_company_name_and_stock_code_conflicts_fail_closed(self):
        item = source(
            "https://media.test/structured-company-conflict",
            "統一(1216) 公告",
            "日期：2026年08月10日 公司名稱：統一(1216) 主旨：投資人說明會；"
            "公司名稱：統一期(5866) 公布7月合併營收。",
        )
        event = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)[0]
        self.assertEqual(event.company_association_status, CompanyAssociationStatus.AMBIGUOUS)
        self.assertEqual(event.validation_status, EventValidationStatus.REJECTED)

    def test_structured_stock_code_conflict_fails_closed(self):
        item = source(
            "https://media.test/structured-code-conflict",
            "統一(1216) 公告",
            "日期：2026年08月10日 股票代號：1216 主旨：投資人說明會；"
            "股票代碼：5866 公布7月合併營收。",
        )
        event = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)[0]
        self.assertEqual(event.company_association_status, CompanyAssociationStatus.AMBIGUOUS)
        self.assertEqual(event.validation_status, EventValidationStatus.REJECTED)

    def test_financial_numbers_do_not_become_conflicting_company_identity(self):
        item = source(
            "https://official.test/financial-values",
            "統一(1216) 營收公告",
            "日期：2026年08月10日 統一(1216)公布7月營收621.69，6.63、8.85、4121.47與5866為財務數值。",
        )
        extracted = candidates(item)
        self.assertEqual(extracted[0].company_association_status, CompanyAssociationStatus.DIRECT_EXACT)
        self.assertEqual(validate_event_candidate(extracted[0], source=item, research_window=WINDOW), EventValidationStatus.VALIDATED)

    def test_related_listed_company_in_unsplit_candidate_fails_closed(self):
        item = source(
            "https://official.test/related-listed-company",
            "統一(1216) 財報公告",
            "日期：2026年08月10日 統一企業(1216)財報內容提及統一超商(2912)。",
        )
        event = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)[0]
        self.assertEqual(event.company_association_status, CompanyAssociationStatus.AMBIGUOUS)
        self.assertEqual(event.validation_status, EventValidationStatus.REJECTED)

    def test_page_chrome_timestamp_is_background_and_event_local_date_validates(self):
        item = source(
            "https://media.test/page-header",
            "統一(1216) 個股公告",
            "2026/08/21 14:30 更新 成交量 2,044 本益比 15.07。"
            "日期：2026年08月10日 統一(1216)公告 7 月合併營收。",
        )
        events = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)
        validated = [event for event in events if event.validation_status is EventValidationStatus.VALIDATED]
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0].event_type, CatalystEventType.REVENUE_UPDATE)
        self.assertEqual(validated[0].event_temporal_value, date(2026, 8, 10))
        self.assertTrue(all("更新" not in event.event_fact for event in validated))

    def test_investor_conference_precedes_neighboring_revenue_text(self):
        item = source(
            "https://official.test/conference-mixed",
            "統一(1216) 公告",
            "日期：2026年08月10日 統一(1216)受邀參加投資人說明會；頁面另列 7 月合併營收新聞。",
        )
        extracted = candidates(item)
        self.assertEqual(extracted[0].candidate_type, CatalystEventType.MANAGEMENT_GOVERNANCE)
        self.assertEqual(extracted[0].company_association_status, CompanyAssociationStatus.DIRECT_EXACT)
        self.assertEqual(validate_event_candidate(extracted[0], source=item, research_window=WINDOW), EventValidationStatus.VALIDATED)

    def test_page_header_acquisition_does_not_duplicate_event_local_disclosure(self):
        item = source(
            "https://media.test/acquisition-page",
            "統一(1216) 個股公告",
            "2026/08/28 14:30 更新 成交量 10,296 本益比 9.55。"
            "日期：2026年08月12日 統一(1216)取得統一子公司股權。",
        )
        events = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)
        validated = [event for event in events if event.validation_status is EventValidationStatus.VALIDATED]
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0].event_type, CatalystEventType.OTHER)
        self.assertEqual(validated[0].event_temporal_value, date(2026, 8, 12))

    def test_same_source_duplicate_q2_income_statement_collapses_to_one_earnings_event(self):
        item = source(
            "https://media.test/q2",
            "統一(1216) 第二季財報",
            "2026/08/13 統一(1216)第2季綜合損益表，每股盈餘 1.93 元。"
            "2026/08/13 統一(1216)第2季綜合損益表，營業收入 100 元。",
        )
        events = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, CatalystEventType.EARNINGS_RESULT)
        self.assertEqual(events[0].validation_status, EventValidationStatus.VALIDATED)
        self.assertEqual(events[0].support_count, 1)

    def test_structured_earnings_subject_precedes_incidental_acquisition(self):
        item = source(
            "https://official.test/earnings-acquisition",
            "統一(1216) 公告",
            "日期：2026年08月13日 主旨：公告本公司115年第2季合併財務報告。說明：本期另取得子公司股權。",
        )
        self.assertEqual(candidates(item)[0].candidate_type, CatalystEventType.EARNINGS_RESULT)

    def test_structured_conference_subject_precedes_incidental_order_acquisition(self):
        item = source(
            "https://official.test/conference-acquisition",
            "統一(1216) 公告",
            "日期：2026年08月10日 主旨：本公司受邀參加法人說明會。說明：將討論取得訂單、營收與投資計畫。",
        )
        self.assertEqual(candidates(item)[0].candidate_type, CatalystEventType.MANAGEMENT_GOVERNANCE)

    def test_acquisition_subject_remains_other_with_board_date(self):
        item = source(
            "https://official.test/acquisition-core",
            "統一(1216) 公告",
            "日期：2026年08月12日 主旨：本公司取得○○公司股權。董事會通過日期：2026年08月11日。",
        )
        extracted = candidates(item)
        self.assertEqual(extracted[0].candidate_type, CatalystEventType.OTHER)
        self.assertEqual(extracted[1].candidate_type, CatalystEventType.OTHER)

    def test_revenue_and_capex_subjects_precede_incidental_acquisition(self):
        revenue = source(
            "https://official.test/revenue-acquisition",
            "統一(1216) 公告",
            "日期：2026年08月10日 主旨：公告7月合併營收。說明：另取得子公司股權。",
        )
        capex = source(
            "https://official.test/capex-acquisition",
            "統一(1216) 公告",
            "日期：2026年08月10日 主旨：擴建新廠增加產能。說明：另取得設備使用權。",
        )
        self.assertEqual(candidates(revenue)[0].candidate_type, CatalystEventType.REVENUE_UPDATE)
        self.assertEqual(candidates(capex)[0].candidate_type, CatalystEventType.CAPEX_CAPACITY)

    def test_price_table_row_never_becomes_validated_event(self):
        item = source(
            "https://media.test/quote",
            "統一(1216) 個股資訊",
            "2026/08/21 14:30 更新 成交量 2,044 本益比 15.07 收盤 35.85。",
        )
        events = cluster_validated_events(candidates(item), sources=(item,), research_window=WINDOW)
        self.assertEqual(events[0].validation_status, EventValidationStatus.BACKGROUND_ONLY)

    def test_extraction_is_offline_and_does_not_import_ai_or_transport(self):
        implementation = (SRC_PATH / "catalyst_event_extraction.py").read_text(encoding="utf-8")
        self.assertNotIn("openai", implementation.casefold())
        self.assertNotIn("requests", implementation.casefold())
        self.assertNotIn("sqlite", implementation.casefold())


if __name__ == "__main__":
    unittest.main()
