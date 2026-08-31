import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from catalyst_event import CandidateStatus
from catalyst_event import CatalystEventError
from catalyst_event import CatalystEventType
from catalyst_event import EventConflictStatus
from catalyst_event import EventTemporalStatus
from catalyst_event import EventValidationStatus
from catalyst_event import ExtractionBasis
from catalyst_event import EventCandidate
from catalyst_event import ValidatedCatalystEvent
from external_source import CompanyAssociationStatus
from external_source import SourceTemporalEvidence
from external_source import SourceTier
from external_source import TemporalEvidenceBasis
from external_source import TemporalKind
from external_source import TemporalPrecision


TIME = SourceTemporalEvidence(
    value=date(2026, 8, 10),
    precision=TemporalPrecision.DATE,
    kind=TemporalKind.EVENT_ANNOUNCED_AT,
    basis=TemporalEvidenceBasis.SOURCE_SNIPPET_EXACT_DATE,
    raw_text="2026-08-10",
)


def candidate():
    return EventCandidate(
        candidate_id="candidate_1",
        source_id="source_1",
        target_symbol="1216.TW",
        target_company_name="統一",
        candidate_anchor="2026-08-10 統一(1216) 公告 7 月營收。",
        candidate_start=0,
        candidate_end=30,
        candidate_type=CatalystEventType.REVENUE_UPDATE,
        temporal_evidence=(TIME,),
        company_association_status=CompanyAssociationStatus.DIRECT_EXACT,
        source_tier=SourceTier.TIER_1_OFFICIAL,
        candidate_status=CandidateStatus.EVENT_LIKE,
        extraction_basis=ExtractionBasis.STRUCTURED_DATE_BLOCK,
        candidate_key="candidate-key",
    )


class CatalystEventModelTestCase(unittest.TestCase):
    def test_candidate_requires_bounded_non_empty_source_local_anchor(self):
        item = candidate()
        self.assertEqual(item.candidate_status, CandidateStatus.EVENT_LIKE)
        with self.assertRaises(CatalystEventError):
            EventCandidate(**{**item.__dict__, "candidate_anchor": "", "candidate_end": 1})

    def test_validated_event_requires_sorted_traceable_sources_and_confirmed_time(self):
        item = candidate()
        event = ValidatedCatalystEvent(
            event_id="event_1",
            target_symbol=item.target_symbol,
            target_company_name=item.target_company_name,
            event_type=item.candidate_type,
            event_fact=item.candidate_anchor,
            event_temporal_evidence=TIME,
            event_temporal_status=EventTemporalStatus.TIME_CONFIRMED,
            source_ids=("source_1",),
            primary_source_id="source_1",
            support_count=1,
            event_key="event-key",
            candidate_ids=(item.candidate_id,),
            company_association_status=CompanyAssociationStatus.DIRECT_EXACT,
            validation_status=EventValidationStatus.VALIDATED,
            conflict_status=EventConflictStatus.NONE,
        )
        self.assertEqual(event.event_temporal_value, date(2026, 8, 10))
        with self.assertRaises(CatalystEventError):
            ValidatedCatalystEvent(**{**event.__dict__, "primary_source_id": "other"})

    def test_validated_event_cannot_hide_conflict_or_missing_direct_evidence(self):
        item = candidate()
        with self.assertRaises(CatalystEventError):
            ValidatedCatalystEvent(
                event_id="event_bad",
                target_symbol=item.target_symbol,
                target_company_name=item.target_company_name,
                event_type=item.candidate_type,
                event_fact=item.candidate_anchor,
                event_temporal_evidence=TIME,
                event_temporal_status=EventTemporalStatus.TIME_CONFIRMED,
                source_ids=("source_1",),
                primary_source_id="source_1",
                support_count=1,
                event_key="event-key",
                candidate_ids=(item.candidate_id,),
                company_association_status=CompanyAssociationStatus.RELATED_ENTITY,
                validation_status=EventValidationStatus.VALIDATED,
                conflict_status=EventConflictStatus.IDENTITY,
            )


if __name__ == "__main__":
    unittest.main()
