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

from risk_oos import TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE
from risk_oos import TECH_RISK_POST_HOLDOUT_AI_EXPOSURE_COHORT_MAPPING_SPEC_V1
from risk_oos import TechnicalRiskAIExposureCategory
from risk_oos import TechnicalRiskAIExposureCohortMappingRecord
from risk_oos import TechnicalRiskAIExposureMappingReviewStatus


ARTIFACT_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "post_holdout_ai_regime_diagnostic"
    / "technical_risk_ai_exposure_batch05_computer_peripheral_v1.json"
)
PHASE1_MAPPING_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "post_holdout_ai_regime_diagnostic"
    / "technical_risk_official_broad_industry_mapping_218_twse_v1.json"
)

EXPECTED_SYMBOLS = (
    "2301.TW",
    "2305.TW",
    "2324.TW",
    "2353.TW",
    "2356.TW",
    "2357.TW",
    "2376.TW",
    "2377.TW",
    "2382.TW",
    "2395.TW",
    "2425.TW",
    "3005.TW",
    "3017.TW",
    "3060.TW",
    "3231.TW",
    "3706.TW",
    "4938.TW",
    "6669.TW",
    "8210.TW",
)
EXPECTED_AI_HIGH_SYMBOLS = {
    "2301.TW",
    "2356.TW",
    "2357.TW",
    "2376.TW",
    "2377.TW",
    "2382.TW",
    "3706.TW",
    "6669.TW",
    "8210.TW",
}
EXPECTED_AI_ADJACENT_SYMBOLS = {
    "2353.TW",
    "2395.TW",
    "3231.TW",
    "4938.TW",
}
EXPECTED_UNKNOWN_SYMBOLS = {
    "2305.TW",
    "2324.TW",
    "2425.TW",
    "3005.TW",
    "3017.TW",
    "3060.TW",
}
ALLOWED_CATEGORIES = {
    TechnicalRiskAIExposureCategory.AI_HIGH.value,
    TechnicalRiskAIExposureCategory.AI_ADJACENT.value,
    TechnicalRiskAIExposureCategory.NON_AI_TECH_CONTROL.value,
    TechnicalRiskAIExposureCategory.UNKNOWN.value,
}


class TechnicalRiskAIExposureBatch05ComputerPeripheralTestCase(unittest.TestCase):
    def setUp(self):
        self.artifact = _load_json(ARTIFACT_PATH)
        self.records = self.artifact["records"]

    def test_artifact_contains_exact_batch_membership(self):
        self.assertEqual(self.artifact["batch_id"], "COMPUTER_PERIPHERAL_BATCH_05")
        self.assertEqual(tuple(record["symbol"] for record in self.records), EXPECTED_SYMBOLS)
        self.assertEqual(len(self.records), 19)
        self.assertEqual(len({record["symbol"] for record in self.records}), 19)

    def test_batch_symbols_are_in_committed_current_computer_peripheral_universe(self):
        phase1 = _load_json(PHASE1_MAPPING_PATH)
        phase1_records = {record["symbol"]: record for record in phase1["records"]}
        self.assertEqual(
            self.artifact["phase1_official_broad_industry_mapping_artifact_id"],
            phase1["artifact_id"],
        )
        self.assertEqual(
            self.artifact["phase1_official_broad_industry_mapping_artifact_checksum"],
            phase1["artifact_checksum"],
        )
        for record in self.records:
            phase1_record = phase1_records[record["symbol"]]
            self.assertEqual(phase1_record["broad_industry"], "電腦及週邊設備業")
            self.assertTrue(phase1_record["technology_related_preview"])
            self.assertEqual(record["current_official_broad_industry"], "電腦及週邊設備業")
            self.assertEqual(record["broad_industry"], "電腦及週邊設備業")

    def test_records_conform_to_committed_mapping_record_contract(self):
        for record in self.records:
            TechnicalRiskAIExposureCohortMappingRecord(
                symbol=record["symbol"],
                company_name=record["company_name"],
                broad_industry=record["broad_industry"],
                industry_source=record["industry_source"],
                industry_source_version=record["industry_source_version"],
                ai_exposure_category=record["ai_exposure_category"],
                classification_as_of_date=date.fromisoformat(record["classification_as_of_date"]),
                evidence_source_type=record["evidence_source_type"],
                evidence_source_reference=record["evidence_source_reference"],
                evidence_publication_date=date.fromisoformat(record["evidence_publication_date"]),
                classification_reason=record["classification_reason"],
                review_status=record["review_status"],
                mapping_methodology_version=record["mapping_methodology_version"],
                source_checksum=record["source_checksum"],
            )

    def test_evidence_dates_are_pre_2024_and_lineage_is_present(self):
        self.assertEqual(self.artifact["evidence_cutoff_date"], "2023-12-31")
        self.assertEqual(
            self.artifact["mapping_methodology_version"],
            TECH_RISK_POST_HOLDOUT_AI_EXPOSURE_COHORT_MAPPING_SPEC_V1,
        )
        self.assertEqual(
            self.artifact["historical_source_coverage_semantics"],
            "SYSTEMATIC_FIRST_PASS_HISTORICAL_SOURCE_COVERAGE",
        )
        for record in self.records:
            self.assertLessEqual(
                date.fromisoformat(record["classification_as_of_date"]),
                TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE,
            )
            self.assertLessEqual(
                date.fromisoformat(record["evidence_publication_date"]),
                TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE,
            )
            self.assertRegex(record["source_checksum"], r"^[0-9a-f]{64}$")

    def test_categories_are_allowed_and_counts_are_fixed(self):
        categories = [record["ai_exposure_category"] for record in self.records]
        self.assertEqual(set(categories) - ALLOWED_CATEGORIES, set())
        self.assertNotIn(TechnicalRiskAIExposureCategory.NON_TECH_CONTROL.value, categories)
        self.assertEqual(
            self.artifact["classification_counts"],
            {
                "AI_ADJACENT": 4,
                "AI_HIGH": 9,
                "NON_AI_TECH_CONTROL": 0,
                "UNKNOWN": 6,
            },
        )

    def test_expected_symbol_classification_sets_are_fixed(self):
        by_category = {
            category: {
                record["symbol"]
                for record in self.records
                if record["ai_exposure_category"] == category
            }
            for category in ALLOWED_CATEGORIES
        }
        self.assertEqual(by_category[TechnicalRiskAIExposureCategory.AI_HIGH.value], EXPECTED_AI_HIGH_SYMBOLS)
        self.assertEqual(
            by_category[TechnicalRiskAIExposureCategory.AI_ADJACENT.value],
            EXPECTED_AI_ADJACENT_SYMBOLS,
        )
        self.assertEqual(by_category[TechnicalRiskAIExposureCategory.UNKNOWN.value], EXPECTED_UNKNOWN_SYMBOLS)
        self.assertEqual(by_category[TechnicalRiskAIExposureCategory.NON_AI_TECH_CONTROL.value], set())

    def test_unknown_audit_statuses_are_explicit_and_fail_closed(self):
        for record in self.records:
            if record["ai_exposure_category"] == TechnicalRiskAIExposureCategory.UNKNOWN.value:
                self.assertIn(
                    record["source_audit_status"],
                    {"INSUFFICIENT_ELIGIBLE_EVIDENCE", "PUBLICATION_DATE_UNVERIFIED"},
                )
                self.assertFalse(record["direct_company_specific_evidence"])
                self.assertNotEqual(record["business_coverage_quality"], "BROAD")

    def test_synthetic_cutoff_publication_dates_are_rejected_by_audit(self):
        for record in self.records:
            self.assertNotEqual(record["evidence_publication_date"], "2023-12-31")
            self.assertFalse(_is_eligible_primary_evidence({**record, "evidence_publication_date": "0001-01-01"}))
            if record["publication_date_audit_status"] == "PUBLICATION_DATE_UNVERIFIED":
                self.assertFalse(record["evidence_publication_date_verified"])
                self.assertEqual(record["ai_exposure_category"], TechnicalRiskAIExposureCategory.UNKNOWN.value)
                self.assertFalse(_is_eligible_primary_evidence(record))
            else:
                self.assertTrue(record["evidence_publication_date_verified"])
                self.assertEqual(record["publication_date_audit_status"], "PUBLICATION_DATE_VERIFIED")
                self.assertTrue(_is_eligible_primary_evidence(record))

    def test_unverified_publication_date_is_never_eligible_by_date_value_only(self):
        for record in self.records:
            date_only_would_pass_cutoff = (
                date.fromisoformat(record["evidence_publication_date"])
                <= TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE
            )
            self.assertTrue(date_only_would_pass_cutoff)
            if not record["evidence_publication_date_verified"]:
                self.assertFalse(_is_eligible_primary_evidence(record))
                self.assertEqual(record["ai_exposure_category"], TechnicalRiskAIExposureCategory.UNKNOWN.value)

    def test_verified_primary_evidence_cannot_use_missing_date_sentinel(self):
        for record in self.records:
            if record["evidence_publication_date"] == "0001-01-01":
                self.assertFalse(record["evidence_publication_date_verified"])
                self.assertEqual(record["publication_date_audit_status"], "PUBLICATION_DATE_UNVERIFIED")
                self.assertFalse(_is_eligible_primary_evidence(record))

    def test_non_unknown_records_require_verified_direct_evidence(self):
        for record in self.records:
            if record["ai_exposure_category"] != TechnicalRiskAIExposureCategory.UNKNOWN.value:
                self.assertTrue(record["evidence_publication_date_verified"])
                self.assertTrue(record["direct_company_specific_evidence"])
                self.assertEqual(record["source_audit_status"], "FOUND_ELIGIBLE_PRIMARY_EVIDENCE")
                self.assertIn(record["business_coverage_quality"], {"BROAD"})
                self.assertIn(
                    record["ai_hpc_evidence_status"],
                    {"EXPLICIT_DIRECT", "EXPLICIT_ADJACENT"},
                )

    def test_artifact_is_descriptive_post_holdout_diagnostic_only(self):
        self.assertEqual(self.artifact["diagnostic_scope"], "POST_HOLDOUT_DIAGNOSTIC_EVIDENCE")
        self.assertEqual(
            self.artifact["post_holdout_governance"],
            "DIAGNOSTIC_ONLY_NO_RETUNE_NO_PRODUCTION_APPROVAL",
        )
        self.assertEqual(
            self.artifact["current_industry_semantics"],
            "CURRENT_OFFICIAL_INDUSTRY_CLASSIFICATION",
        )
        artifact_text = ARTIFACT_PATH.read_text(encoding="utf-8")
        forbidden_tokens = (
            "Candidate C",
            "Holdout results",
            "Holdout performance",
            "2024-2025 stock return",
            "Yahoo",
            "yfinance",
            "selected_threshold",
            "production_policy",
            "risk separation",
            "threshold performance",
            "MAE",
            "retune",
            "Production approval",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, artifact_text)

    def test_review_status_and_source_audit_are_complete_without_full_mapping_claim(self):
        self.assertEqual(self.artifact["artifact_schema_version"], "TECH_RISK_AI_EXPOSURE_BATCH_MAPPING_V1")
        self.assertNotIn("records_total", self.artifact)
        for record in self.records:
            self.assertEqual(record["review_status"], TechnicalRiskAIExposureMappingReviewStatus.REVIEWED.value)
            self.assertIn(
                record["source_audit_status"],
                {
                    "FOUND_ELIGIBLE_PRIMARY_EVIDENCE",
                    "INSUFFICIENT_ELIGIBLE_EVIDENCE",
                    "PUBLICATION_DATE_UNVERIFIED",
                },
            )

    def test_artifact_checksum_and_id_are_deterministic(self):
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
            f"technical_risk_ai_exposure_batch05_computer_peripheral_{checksum[:16]}",
        )


def _load_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _is_eligible_primary_evidence(record):
    return (
        record["evidence_publication_date_verified"]
        and record["evidence_publication_date"] != "0001-01-01"
        and date.fromisoformat(record["evidence_publication_date"])
        <= TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE
    )


if __name__ == "__main__":
    unittest.main()
