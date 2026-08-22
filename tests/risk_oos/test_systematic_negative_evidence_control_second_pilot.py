from __future__ import annotations

import hashlib
import json
import sys
import unittest
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk_oos import SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_CUTOFF_DATE
from risk_oos import SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_GOVERNANCE_POST_HOLDOUT
from risk_oos import SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_STATUS_DRAFT_FOR_METHOD_REVIEW
from risk_oos import SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_SENTINEL_DATE
from risk_oos import SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_V1
from risk_oos import SystematicNegativeEvidenceControlInput
from risk_oos import SystematicNegativeEvidenceSourceReview
from risk_oos import assess_systematic_negative_evidence_control


ARTIFACT_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "post_holdout_ai_regime_diagnostic"
    / "systematic_negative_evidence_control_second_validation_pilot_v1.json"
)
EXPECTED_CALIBRATION = ("2337.TW", "8261.TW")
EXPECTED_BLIND = ("2302.TW", "2449.TW", "2313.TW", "2316.TW", "2305.TW", "2324.TW")
EXPECTED_SOURCE_CLASSES = {
    "REGULATORY_MOPS",
    "COMPREHENSIVE_BUSINESS_REPORT",
    "INVESTOR_MATERIAL",
    "OFFICIAL_COMPANY_DISCLOSURE",
    "APPROVED_OFFICIAL_ECOSYSTEM_SOURCE",
}


class SystematicNegativeEvidenceControlSecondPilotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact = _load_json(ARTIFACT_PATH)
        self.records = self.artifact["records"]

    def test_artifact_identity_and_protocol_are_draft(self) -> None:
        self.assertEqual(
            self.artifact["artifact_schema_version"],
            "SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_SECOND_VALIDATION_PILOT_ARTIFACT_V1",
        )
        self.assertEqual(
            self.artifact["pilot_id"],
            "SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_SECOND_VALIDATION_PILOT_V1",
        )
        self.assertEqual(self.artifact["protocol_version"], SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_V1)
        self.assertEqual(
            self.artifact["protocol_status"],
            SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_STATUS_DRAFT_FOR_METHOD_REVIEW,
        )
        self.assertEqual(
            self.artifact["governance_scope"],
            SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_GOVERNANCE_POST_HOLDOUT,
        )
        self.assertEqual(
            self.artifact["evidence_cutoff_date"],
            SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_CUTOFF_DATE.isoformat(),
        )
        self.assertEqual(self.artifact["methodology_approval"], "NOT_APPROVED")

    def test_exact_membership_and_role_separation(self) -> None:
        self.assertEqual(tuple(self.artifact["calibration_membership"]), EXPECTED_CALIBRATION)
        self.assertEqual(tuple(self.artifact["blind_membership"]), EXPECTED_BLIND)
        self.assertEqual(len(self.records), 8)
        self.assertEqual(len({record["symbol"] for record in self.records}), 8)
        self.assertTrue(set(EXPECTED_CALIBRATION).isdisjoint(EXPECTED_BLIND))
        by_role = {
            role: tuple(record["symbol"] for record in self.records if record["pilot_role"] == role)
            for role in {"POSITIVE_CALIBRATION", "OUTCOME_BLIND_VALIDATION"}
        }
        self.assertEqual(by_role["POSITIVE_CALIBRATION"], EXPECTED_CALIBRATION)
        self.assertEqual(by_role["OUTCOME_BLIND_VALIDATION"], EXPECTED_BLIND)

    def test_each_record_has_all_source_classes_explicitly_represented(self) -> None:
        self.assertEqual(set(self.artifact["source_classes_required"]), EXPECTED_SOURCE_CLASSES)
        for record in self.records:
            source_classes = {source["source_class"] for source in record["source_class_reviews"]}
            self.assertEqual(source_classes, EXPECTED_SOURCE_CLASSES)
            self.assertEqual(len(record["source_class_reviews"]), 5)
            for source in record["source_class_reviews"]:
                if source["review_state"] in {"UNAVAILABLE_OR_UNRECOVERABLE", "NOT_APPLICABLE"}:
                    self.assertTrue(source["audit_reason"])

    def test_deterministic_replay_matches_persisted_assessments(self) -> None:
        for record in self.records:
            replayed = _serialize_assessment(
                assess_systematic_negative_evidence_control(_reconstruct_input(record))
            )
            self.assertEqual(replayed, record["contract_assessment"])

    def test_date_integrity_and_no_synthetic_eligible_dates(self) -> None:
        for record in self.records:
            for source in record["source_class_reviews"]:
                publication_date = source["publication_date"]
                self.assertFalse(source["publication_date_is_synthetic_fallback"])
                if source["review_state"] == "REVIEWED_ELIGIBLE":
                    self.assertTrue(source["publication_date_verified"])
                    self.assertIsNotNone(publication_date)
                    self.assertNotEqual(publication_date, SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_SENTINEL_DATE.isoformat())
                    self.assertLessEqual(
                        date.fromisoformat(publication_date),
                        SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_CUTOFF_DATE,
                    )
                else:
                    self.assertFalse(source["publication_date_verified"])

    def test_counters_keep_calibration_and_blind_results_separate(self) -> None:
        self.assertEqual(
            self.artifact["calibration_counters"],
            {
                "CALIBRATION_CASE_COUNT": 2,
                "CALIBRATION_CONTROL_ELIGIBLE": 0,
                "CALIBRATION_MISMATCH": 2,
            },
        )
        self.assertEqual(
            self.artifact["blind_counters"],
            {
                "BLIND_CASE_COUNT": 6,
                "BLIND_CONTROL_ELIGIBLE": 0,
                "BLIND_AI_EVIDENCE_FOUND": 0,
                "BLIND_CONTROL_REVIEW_INCOMPLETE": 6,
                "BLIND_SOURCE_CLASS_REVIEW_INCOMPLETE": 0,
                "BLIND_CONFLICT": 0,
            },
        )
        self.assertFalse(self.artifact["positive_path_flags"]["REAL_WORLD_POSITIVE_PATH_REPRODUCED"])
        self.assertFalse(
            self.artifact["positive_path_flags"]["BLIND_REAL_WORLD_CONTROL_ELIGIBLE_DEMONSTRATED"]
        )

    def test_existing_labels_and_research_boundaries_are_preserved(self) -> None:
        labels = {record["symbol"]: record["existing_cohort_label_preserved"] for record in self.records}
        self.assertEqual(labels["2337.TW"], "NON_AI_TECH_CONTROL")
        self.assertEqual(labels["8261.TW"], "NON_AI_TECH_CONTROL")
        for symbol in EXPECTED_BLIND:
            self.assertEqual(labels[symbol], "UNKNOWN")
        self.assertFalse(self.artifact["batch_artifacts_modified"])
        self.assertFalse(self.artifact["existing_cohort_labels_modified"])
        self.assertFalse(self.artifact["production_artifact_created"])

    def test_no_candidate_holdout_return_or_production_dependency(self) -> None:
        self.assertEqual(self.artifact["candidate_c_dependency"], "NONE")
        self.assertEqual(self.artifact["holdout_performance_dependency"], "NONE")
        self.assertEqual(self.artifact["return_dependency"], "NONE")
        artifact_text = ARTIFACT_PATH.read_text(encoding="utf-8")
        for token in (
            "Candidate C",
            "Holdout performance",
            "stock return",
            "Yahoo",
            "yfinance",
            "selected_threshold",
            "production_policy",
        ):
            self.assertNotIn(token, artifact_text)

    def test_artifact_checksum_and_id_are_deterministic(self) -> None:
        payload = {
            key: value
            for key, value in self.artifact.items()
            if key not in {"artifact_id", "artifact_checksum"}
        }
        checksum = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        self.assertEqual(self.artifact["artifact_checksum"], checksum)
        self.assertEqual(
            self.artifact["artifact_id"],
            f"systematic_negative_evidence_control_second_validation_pilot_v1_{checksum[:16]}",
        )


def _reconstruct_input(record: dict) -> SystematicNegativeEvidenceControlInput:
    reviews = []
    for source in record["source_class_reviews"]:
        reviews.append(
            SystematicNegativeEvidenceSourceReview(
                source_class=source["source_class"],
                review_state=source["review_state"],
                publication_date=(
                    date.fromisoformat(source["publication_date"])
                    if source["publication_date"] is not None
                    else None
                ),
                publication_date_verified=source["publication_date_verified"],
                publication_date_is_synthetic_fallback=source["publication_date_is_synthetic_fallback"],
                audit_reason=source["audit_reason"],
                supports_broad_business_coverage=source["supports_broad_business_coverage"],
                is_required=source["is_required"],
            )
        )
    return SystematicNegativeEvidenceControlInput(
        symbol=record["symbol"],
        source_class_reviews=tuple(reviews),
        historical_business_identity_supported=record["historical_business_identity_supported"],
        business_coverage_quality=record["business_coverage"],
        ai_high_evidence_status=record["ai_high_evidence_status"],
        ai_adjacent_evidence_status=record["ai_adjacent_evidence_status"],
        ecosystem_evidence_status=record["ecosystem_evidence_status"],
        conflict_status=record["conflict_status"],
        review_completeness=record["review_completeness"],
        reviewer_notes=record["reviewer_notes"],
    )


def _serialize_assessment(assessment) -> dict:
    return {
        "protocol_version": assessment.protocol_version,
        "protocol_status": assessment.protocol_status,
        "governance_scope": assessment.governance_scope,
        "evidence_cutoff_date": assessment.evidence_cutoff_date.isoformat(),
        "symbol": assessment.symbol,
        "control_review_state": assessment.control_review_state.value,
        "control_eligibility": assessment.control_eligibility,
        "unknown_reason": assessment.unknown_reason,
    }


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    unittest.main()
