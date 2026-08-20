import inspect
import sys
import unittest
from dataclasses import fields
from datetime import date
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_oos
import risk_oos.holdout_region_confirmation as contract_module
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONFIRMED_NOT_APPROVAL
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_CHECKSUM
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_ID
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_POST_VALIDATION_METHOD_DECISION
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_LEVEL_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE
from risk_oos import TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1
from risk_oos import TechnicalRiskCandidateSeverity
from risk_oos import TechnicalRiskHoldoutConfirmationArtifact
from risk_oos import TechnicalRiskHoldoutRegionConfirmationContract
from risk_oos import TechnicalRiskHoldoutRegionConfirmationError
from risk_oos import TechnicalRiskHoldoutRegionConfirmationStatus
from risk_oos import TechnicalRiskHoldoutRegionEvidenceHorizon
from risk_oos import TechnicalRiskHoldoutRegionSeparationEvidence
from risk_oos import TechnicalRiskHoldoutRegionSeverityEvidence
from risk_oos import TechnicalRiskHoldoutRegionSummary
from risk_oos import TechnicalRiskHoldoutRegionThresholdResult
from risk_oos import build_technical_risk_v1_holdout_region_confirmation_contract


class TechnicalRiskHoldoutRegionConfirmationContractTestCase(unittest.TestCase):
    def setUp(self):
        self.contract = build_technical_risk_v1_holdout_region_confirmation_contract()

    def test_exact_contract_version_and_scope(self):
        self.assertEqual(self.contract.contract_version, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1)
        self.assertEqual(self.contract.contract_scope, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_LEVEL_V1)
        self.assertTrue(self.contract.region_confirmation_required)
        self.assertFalse(self.contract.single_threshold_confirmation_allowed)

    def test_frozen_validation_lineage_is_preserved(self):
        self.assertEqual(self.contract.validation_evidence_artifact_id, TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID)
        self.assertEqual(
            self.contract.validation_evidence_artifact_checksum,
            TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM,
        )
        self.assertEqual(
            self.contract.validation_selection_methodology_version,
            TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1,
        )
        self.assertEqual(
            self.contract.validation_selection_decision_package_id,
            TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_ID,
        )
        self.assertEqual(
            self.contract.validation_selection_decision_package_checksum,
            TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_CHECKSUM,
        )

    def test_candidate_and_region_identity_are_frozen(self):
        self.assertEqual(self.contract.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID)
        self.assertEqual(self.contract.candidate_id, "TECH_POLICY_CANDIDATE_C")
        self.assertEqual(self.contract.robust_region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID)
        self.assertEqual(
            self.contract.robust_region_id,
            "technical_risk_validation_robust_region_3df35aa1395ead5d",
        )
        self.assertEqual(
            self.contract.robust_region_threshold_count,
            TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT,
        )
        self.assertEqual(self.contract.robust_region_threshold_count, 69)

    def test_holdout_period_is_preserved_and_sealed(self):
        self.assertEqual(self.contract.holdout_start_date, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE)
        self.assertEqual(self.contract.holdout_end_date, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE)
        self.assertEqual(self.contract.holdout_start_date, date(2024, 1, 1))
        self.assertEqual(self.contract.holdout_end_date, date(2025, 12, 31))
        self.assertTrue(self.contract.holdout_period_sealed_before_evaluation)

    def test_decision_states_are_limited_and_do_not_approve_policy(self):
        self.assertEqual(
            self.contract.confirmation_statuses,
            (
                TechnicalRiskHoldoutRegionConfirmationStatus.CONFIRMED,
                TechnicalRiskHoldoutRegionConfirmationStatus.NOT_CONFIRMED,
                TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED,
            ),
        )
        self.assertEqual(
            self.contract.confirmed_status_policy,
            TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONFIRMED_NOT_APPROVAL,
        )

    def test_numeric_criteria_remain_post_validation_method_decision(self):
        self.assertEqual(
            self.contract.numeric_acceptance_floor_policy,
            TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1,
        )
        self.assertEqual(
            self.contract.future_numeric_criteria_decision,
            TECH_RISK_HOLDOUT_REGION_CONFIRMATION_POST_VALIDATION_METHOD_DECISION,
        )
        source = inspect.getsource(contract_module)
        self.assertNotIn("minimum_", source)
        self.assertNotIn("max_allowed", source)
        self.assertNotIn("numeric_cutoff", source)

    def test_threshold_result_shape_preserves_required_future_holdout_evidence(self):
        field_names = {field.name for field in fields(TechnicalRiskHoldoutRegionThresholdResult)}
        self.assertEqual(
            field_names,
            {
                "threshold_set_id",
                "threshold_checksum",
                "candidate_id",
                "region_id",
                "severity_evidence",
                "mae20_monotonicity_status",
                "mae60_monotonicity_status",
                "mae20_separation_evidence",
                "mae60_separation_evidence",
                "confirmation_status",
            },
        )

    def test_threshold_result_requires_candidate_region_and_all_severities(self):
        result = _threshold_result()
        self.assertEqual(result.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID)
        self.assertEqual(result.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID)
        self.assertEqual({item.severity for item in result.severity_evidence}, set(TechnicalRiskCandidateSeverity))
        self.assertEqual(result.mae20_separation_evidence.horizon, TechnicalRiskHoldoutRegionEvidenceHorizon.MAE20)
        self.assertEqual(result.mae60_separation_evidence.horizon, TechnicalRiskHoldoutRegionEvidenceHorizon.MAE60)

    def test_threshold_result_rejects_candidate_or_region_mutation(self):
        with self.assertRaisesRegex(TechnicalRiskHoldoutRegionConfirmationError, "candidate_id mismatch"):
            _threshold_result(candidate_id="TECH_POLICY_CANDIDATE_A")
        with self.assertRaisesRegex(TechnicalRiskHoldoutRegionConfirmationError, "region_id mismatch"):
            _threshold_result(region_id="other_region")

    def test_region_summary_preserves_counts_without_threshold_preference(self):
        summary = TechnicalRiskHoldoutRegionSummary(
            region_id=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID,
            candidate_id=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID,
            total_threshold_count=69,
            confirmed_threshold_count=60,
            not_confirmed_threshold_count=3,
            review_required_threshold_count=6,
            monotonicity_stability_summary={"MAE20": 69, "MAE60": 69},
            separation_stability_summary={"MAE20": 69, "MAE60": 69},
            coverage_stability_summary={"LOW": 69, "MEDIUM": 69, "HIGH": 69},
        )
        self.assertEqual(summary.total_threshold_count, 69)
        field_names = {field.name for field in fields(TechnicalRiskHoldoutRegionSummary)}
        self.assertTrue(
            field_names.isdisjoint({
                "winner",
                "selected_threshold",
                "selected_threshold_set_id",
                "score",
                "weighted_score",
            })
        )

    def test_contract_identity_and_checksum_are_deterministic(self):
        first = build_technical_risk_v1_holdout_region_confirmation_contract()
        second = build_technical_risk_v1_holdout_region_confirmation_contract()
        self.assertEqual(first.contract_id, second.contract_id)
        self.assertEqual(first.contract_checksum, second.contract_checksum)
        self.assertRegex(first.contract_id, r"^technical_risk_holdout_region_confirmation_contract_[0-9a-f]{16}$")
        self.assertRegex(first.contract_checksum, r"^[0-9a-f]{64}$")

    def test_contract_rejects_lineage_candidate_region_and_period_mutation(self):
        with self.assertRaisesRegex(TechnicalRiskHoldoutRegionConfirmationError, "candidate_id mismatch"):
            _contract(candidate_id="TECH_POLICY_CANDIDATE_D")
        with self.assertRaisesRegex(TechnicalRiskHoldoutRegionConfirmationError, "robust_region_id mismatch"):
            _contract(robust_region_id="technical_risk_validation_robust_region_other")
        with self.assertRaisesRegex(TechnicalRiskHoldoutRegionConfirmationError, "holdout_start_date mismatch"):
            _contract(holdout_start_date=date(2023, 1, 1))
        with self.assertRaisesRegex(TechnicalRiskHoldoutRegionConfirmationError, "holdout_end_date mismatch"):
            _contract(holdout_end_date=date(2026, 1, 1))

    def test_no_execution_selection_or_production_dependency(self):
        source = inspect.getsource(contract_module)
        forbidden_tokens = (
            "TechnicalRiskCandidateEvaluator",
            "TechnicalRiskRealOOSDatasetMaterializer",
            "load_validation_evidence_artifact",
            "sqlite3",
            "yfinance",
            "requests",
            "data/production",
            "production_runtime",
            "selected_candidate",
            "selected_threshold",
            "weighted_score",
            "holdout_dataset_id =",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_public_api_exports_contract_without_executor(self):
        self.assertIn("TechnicalRiskHoldoutRegionConfirmationContract", risk_oos.__all__)
        self.assertIn("build_technical_risk_v1_holdout_region_confirmation_contract", risk_oos.__all__)
        self.assertNotIn("TechnicalRiskHoldoutRegionConfirmationEvaluator", risk_oos.__all__)
        self.assertNotIn("TechnicalRiskHoldoutRegionConfirmationArtifact", risk_oos.__all__)

    def test_existing_artifact_is_single_threshold_oriented(self):
        field_names = {field.name for field in fields(TechnicalRiskHoldoutConfirmationArtifact)}
        self.assertIn("selected_threshold_set_id", field_names)
        self.assertNotIn("robust_region_id", field_names)
        self.assertNotIn("threshold_results", field_names)


def _contract(**overrides):
    payload = {
        "contract_id": None,
        "contract_version": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1,
        "contract_scope": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_LEVEL_V1,
        "validation_evidence_artifact_id": TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID,
        "validation_evidence_artifact_checksum": TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM,
        "validation_selection_methodology_version": TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1,
        "validation_selection_decision_package_id": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_ID,
        "validation_selection_decision_package_checksum": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_CHECKSUM,
        "candidate_id": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID,
        "robust_region_id": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID,
        "robust_region_threshold_count": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT,
        "holdout_start_date": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE,
        "holdout_end_date": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE,
        "holdout_period_sealed_before_evaluation": True,
        "region_confirmation_required": True,
        "single_threshold_confirmation_allowed": False,
        "numeric_acceptance_floor_policy": TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1,
        "future_numeric_criteria_decision": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_POST_VALIDATION_METHOD_DECISION,
        "confirmation_statuses": tuple(TechnicalRiskHoldoutRegionConfirmationStatus),
        "confirmed_status_policy": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONFIRMED_NOT_APPROVAL,
    }
    payload.update(overrides)
    return TechnicalRiskHoldoutRegionConfirmationContract(**payload)


def _threshold_result(**overrides):
    payload = {
        "threshold_set_id": "threshold_set_001",
        "threshold_checksum": "threshold_checksum_001",
        "candidate_id": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID,
        "region_id": TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID,
        "severity_evidence": (
            _severity_evidence("LOW"),
            _severity_evidence("MEDIUM"),
            _severity_evidence("HIGH"),
        ),
        "mae20_monotonicity_status": "PASS",
        "mae60_monotonicity_status": "PASS",
        "mae20_separation_evidence": TechnicalRiskHoldoutRegionSeparationEvidence(
            horizon="MAE20",
            high_minus_low=Decimal("0.10"),
            high_minus_medium=Decimal("0.05"),
            medium_minus_low=Decimal("0.05"),
        ),
        "mae60_separation_evidence": TechnicalRiskHoldoutRegionSeparationEvidence(
            horizon="MAE60",
            high_minus_low=Decimal("0.20"),
            high_minus_medium=Decimal("0.10"),
            medium_minus_low=Decimal("0.10"),
        ),
        "confirmation_status": TechnicalRiskHoldoutRegionConfirmationStatus.CONFIRMED,
    }
    payload.update(overrides)
    return TechnicalRiskHoldoutRegionThresholdResult(**payload)


def _severity_evidence(severity):
    return TechnicalRiskHoldoutRegionSeverityEvidence(
        severity=severity,
        coverage_ratio=Decimal("0.3333333333333333333333333333"),
        sample_count=10,
        mae20_mean=Decimal("0.10"),
        mae20_median=Decimal("0.09"),
        mae20_p25=Decimal("0.08"),
        mae20_p75=Decimal("0.11"),
        mae60_mean=Decimal("0.20"),
        mae60_median=Decimal("0.19"),
        mae60_p25=Decimal("0.18"),
        mae60_p75=Decimal("0.21"),
    )


if __name__ == "__main__":
    unittest.main()
