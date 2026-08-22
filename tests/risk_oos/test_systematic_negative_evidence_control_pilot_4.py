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
from risk_oos import SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_V1
from risk_oos import SystematicNegativeEvidenceControlInput
from risk_oos import SystematicNegativeEvidenceSourceReview
from risk_oos import assess_systematic_negative_evidence_control


ARTIFACT_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "post_holdout_ai_regime_diagnostic"
    / "systematic_negative_evidence_control_pilot_4_v1.json"
)
EXPECTED_SYMBOLS = ("2379.TW", "2408.TW", "5269.TW", "2467.TW")
EXPECTED_SOURCE_CLASSES = {
    "REGULATORY_MOPS",
    "COMPREHENSIVE_BUSINESS_REPORT",
    "INVESTOR_MATERIAL",
    "OFFICIAL_COMPANY_DISCLOSURE",
    "APPROVED_OFFICIAL_ECOSYSTEM_SOURCE",
}


class SystematicNegativeEvidenceControlPilot4Test(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact = _load_json(ARTIFACT_PATH)
        self.records = self.artifact["records"]

    def test_artifact_identity_and_protocol_are_draft(self) -> None:
        self.assertEqual(
            self.artifact["artifact_schema_version"],
            "SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_PILOT_ARTIFACT_V1",
        )
        self.assertEqual(self.artifact["pilot_id"], "SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_PILOT_4_V1")
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

    def test_exact_four_company_membership_without_duplicates(self) -> None:
        self.assertEqual(tuple(record["symbol"] for record in self.records), EXPECTED_SYMBOLS)
        self.assertEqual(self.artifact["frozen_membership"], list(EXPECTED_SYMBOLS))
        self.assertEqual(len(self.records), 4)
        self.assertEqual(len({record["symbol"] for record in self.records}), 4)

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

    def test_pilot_does_not_reclassify_existing_cohorts_or_create_production_artifact(self) -> None:
        self.assertFalse(self.artifact["original_cohort_labels_modified"])
        self.assertFalse(self.artifact["batch_artifacts_modified"])
        self.assertFalse(self.artifact["production_artifact_created"])
        for record in self.records:
            self.assertEqual(record["existing_cohort_label_preserved"], "UNKNOWN")
            self.assertNotIn("ai_exposure_category", record)
            self.assertTrue(record["pilot_finding"].startswith("PILOT_"))

    def test_pilot_is_independent_of_candidate_holdout_returns_and_network_runtime(self) -> None:
        self.assertEqual(self.artifact["candidate_c_dependency"], "NONE")
        self.assertEqual(self.artifact["holdout_performance_dependency"], "NONE")
        artifact_text = ARTIFACT_PATH.read_text(encoding="utf-8")
        forbidden_tokens = (
            "Candidate C",
            "Holdout performance",
            "2024-2025 stock return",
            "Yahoo",
            "yfinance",
            "selected_threshold",
            "production_policy",
            "risk separation",
            "return_dependency",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, artifact_text)

    def test_pilot_counts_explain_all_four_companies_without_final_cohort_counts(self) -> None:
        counts = self.artifact["pilot_outcome_counts"]
        self.assertEqual(counts["PILOT_CONTROL_ELIGIBLE"], 0)
        self.assertEqual(counts["PILOT_AI_EVIDENCE_FOUND"], 1)
        self.assertNotIn("PILOT_REVIEW_INCOMPLETE", counts)
        self.assertEqual(counts["PILOT_CONTROL_REVIEW_INCOMPLETE"], 3)
        self.assertEqual(counts["PILOT_SOURCE_CLASS_REVIEW_INCOMPLETE"], 0)
        self.assertEqual(counts["PILOT_CONFLICT"], 0)
        self.assertEqual(counts["PILOT_FAIL_CLOSED"], 4)
        self.assertEqual(counts["PILOT_CONTROL_ELIGIBLE"] + counts["PILOT_FAIL_CLOSED"], 4)
        self.assertNotIn("classification_counts", self.artifact)

    def test_search_not_found_does_not_create_control_eligibility_by_itself(self) -> None:
        for record in self.records:
            only_search_not_found = all(
                source["review_state"] == "SEARCHED_NOT_FOUND"
                for source in record["source_class_reviews"]
            )
            if only_search_not_found:
                self.assertFalse(record["contract_assessment"]["control_eligibility"])

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
            f"systematic_negative_evidence_control_pilot_4_v1_{checksum[:16]}",
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
