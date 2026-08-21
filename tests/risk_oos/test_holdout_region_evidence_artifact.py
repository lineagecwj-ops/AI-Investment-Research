import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_oos
from risk_oos import AlignedTechnicalRiskOOSRow
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID
from risk_oos import TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_CODEC_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_SCHEMA_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1
from risk_oos import TechnicalRiskCandidateEvaluator
from risk_oos import TechnicalRiskHoldoutRegionEvidenceArtifact
from risk_oos import TechnicalRiskHoldoutRegionEvidenceArtifactCodec
from risk_oos import TechnicalRiskHoldoutRegionEvidenceArtifactError
from risk_oos import TechnicalRiskHoldoutRegionEvaluator
from risk_oos import TechnicalRiskOOSDatasetResult
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskRealOOSDatasetMaterializationResult
from risk_oos import build_technical_risk_holdout_region_evidence_review_package_from_artifact
from risk_oos import build_technical_risk_v1_holdout_region_confirmation_contract
from risk_oos import build_technical_risk_v1_holdout_region_evaluation_request
from risk_oos import load_holdout_region_evidence_artifact
from risk_oos import load_official_validation_evidence_artifact
from risk_oos import save_holdout_region_evidence_artifact


class FakeHoldoutDatasetMaterializer:
    def __init__(self, dataset):
        self.dataset = dataset

    def materialize(self, request):
        return TechnicalRiskRealOOSDatasetMaterializationResult(
            oos_dataset_result=self.dataset,
            feature_observation_count=len(self.dataset.included_rows),
            feature_exclusion_count=0,
            mae20_artifact_count=len(self.dataset.included_rows),
            mae60_artifact_count=len(self.dataset.included_rows),
            aligned_row_count=len(self.dataset.included_rows),
            split_counts={
                "development": 0,
                "validation": 0,
                "holdout": len(self.dataset.included_rows),
            },
            excluded_insufficient_feature_history_count=0,
            excluded_incomplete_mae20_count=0,
            excluded_incomplete_mae60_count=0,
            excluded_split_leakage_count=0,
        )


class CompactOnlyCandidateEvaluator:
    def __init__(self):
        self.delegate = TechnicalRiskCandidateEvaluator()

    def evaluate(self, dataset, candidate, threshold_set, evaluation_input):
        raise AssertionError("compact evaluation should be used")

    def evaluate_compact(self, dataset, candidate, threshold_set, evaluation_input):
        return self.delegate.evaluate_compact(dataset, candidate, threshold_set, evaluation_input)


class TechnicalRiskHoldoutRegionEvidenceArtifactTestCase(unittest.TestCase):
    def row(self, row_id, *, as_of_close, sma20, sma60, rsi14, mae20_value, mae60_value):
        return AlignedTechnicalRiskOOSRow(
            row_id=row_id,
            observation_id=f"obs_{row_id}",
            symbol="2330.TW",
            evaluation_date=date(2024, 6, 3),
            as_of_close=as_of_close,
            sma20=sma20,
            sma60=sma60,
            rsi14=rsi14,
            feature_observation_checksum=f"feature_checksum_{row_id}",
            mae20_value=mae20_value,
            mae20_target_checksum=f"mae20_checksum_{row_id}",
            mae20_calculation_id=f"mae20_calc_{row_id}",
            mae20_target_start_date=date(2024, 6, 4),
            mae20_target_end_date=date(2024, 7, 1),
            mae60_value=mae60_value,
            mae60_target_checksum=f"mae60_checksum_{row_id}",
            mae60_calculation_id=f"mae60_calc_{row_id}",
            mae60_target_start_date=date(2024, 6, 4),
            mae60_target_end_date=date(2024, 8, 30),
            split_id="holdout_split",
            split_role=TechnicalRiskOOSSplitRole.HOLDOUT,
            dataset_spec_id="technical_risk_holdout_region_dataset_fixture",
            dataset_spec_version="v1",
        )

    def dataset(self):
        return TechnicalRiskOOSDatasetResult(
            included_rows=(
                self.row("high", as_of_close=80, sma20=100, sma60=110, rsi14=25, mae20_value=-0.22, mae60_value=-0.32),
                self.row("medium", as_of_close=96, sma20=100, sma60=105, rsi14=45, mae20_value=-0.11, mae60_value=-0.20),
                self.row("low", as_of_close=110, sma20=100, sma60=95, rsi14=55, mae20_value=-0.02, mae60_value=-0.04),
            ),
            excluded_records=(),
            dataset_id="technical_risk_holdout_region_dataset_fixture",
            dataset_checksum="dataset_checksum_holdout_fixture",
            summary_counts={"included_rows": 3, "holdout_included": 3},
        )

    def holdout_result(self):
        contract = build_technical_risk_v1_holdout_region_confirmation_contract()
        request = build_technical_risk_v1_holdout_region_evaluation_request(
            research_db_path="/tmp/research.db",
            research_manifest_path="/tmp/research_manifest.json",
            source_snapshot_id="research_snapshot_v1",
            source_snapshot_checksum="research_snapshot_checksum_v1",
            symbols=("2330.TW",),
            contract=contract,
        )
        return TechnicalRiskHoldoutRegionEvaluator(
            dataset_materializer=FakeHoldoutDatasetMaterializer(self.dataset()),
            candidate_evaluator=CompactOnlyCandidateEvaluator(),
        ).evaluate(request, contract=contract)

    def artifact(self):
        return TechnicalRiskHoldoutRegionEvidenceArtifact.from_holdout_result(self.holdout_result())

    def test_artifact_creation_preserves_frozen_lineage_and_69_entries(self):
        artifact = self.artifact()
        result = artifact.holdout_evaluation_result

        self.assertEqual(artifact.artifact_schema_version, TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_SCHEMA_V1)
        self.assertEqual(result.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID)
        self.assertEqual(result.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID)
        self.assertEqual(result.threshold_count, 69)
        self.assertEqual(result.evaluation_count, 69)
        self.assertEqual(tuple(identity[0] for identity in result.threshold_identities), TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1)
        self.assertEqual(len(result.threshold_records), 69)

    def test_codec_round_trip_preserves_decimal_and_identity(self):
        artifact = self.artifact()
        codec = TechnicalRiskHoldoutRegionEvidenceArtifactCodec()
        decoded = codec.decode(codec.encode(artifact))

        self.assertEqual(decoded.artifact_id, artifact.artifact_id)
        self.assertEqual(decoded.artifact_checksum, artifact.artifact_checksum)
        self.assertEqual(decoded.holdout_evaluation_result.result_id, artifact.holdout_evaluation_result.result_id)
        self.assertEqual(decoded.holdout_evaluation_result.result_checksum, artifact.holdout_evaluation_result.result_checksum)
        self.assertEqual(
            decoded.holdout_evaluation_result.threshold_records[0].threshold_result.severity_evidence[0].coverage_ratio,
            artifact.holdout_evaluation_result.threshold_records[0].threshold_result.severity_evidence[0].coverage_ratio,
        )

    def test_strict_decode_rejects_unknown_fields_and_tamper(self):
        artifact = self.artifact()
        codec = TechnicalRiskHoldoutRegionEvidenceArtifactCodec()
        payload = json.loads(codec.encode(artifact))
        payload["extra"] = "forbidden"
        with self.assertRaisesRegex(TechnicalRiskHoldoutRegionEvidenceArtifactError, "fields mismatch"):
            codec.decode(json.dumps(payload, sort_keys=True))

        payload = json.loads(codec.encode(artifact))
        payload["artifact"]["holdout_evaluation_result"]["candidate_id"] = "TECH_POLICY_CANDIDATE_A"
        with self.assertRaisesRegex(TechnicalRiskHoldoutRegionEvidenceArtifactError, "serialization_checksum"):
            codec.decode(json.dumps(payload, sort_keys=True))

    def test_duplicate_threshold_or_evaluation_identity_rejected(self):
        result = self.holdout_result()
        duplicated = replace(
            result,
            threshold_records=result.threshold_records[:1] + result.threshold_records[:1] + result.threshold_records[2:],
        )
        with self.assertRaisesRegex(TechnicalRiskHoldoutRegionEvidenceArtifactError, "duplicate"):
            TechnicalRiskHoldoutRegionEvidenceArtifact.from_holdout_result(duplicated)

    def test_save_is_idempotent_and_conflict_fails_closed(self):
        artifact = self.artifact()
        with tempfile.TemporaryDirectory() as tmpdir:
            first = save_holdout_region_evidence_artifact(artifact, tmpdir)
            second = save_holdout_region_evidence_artifact(artifact, tmpdir)

            self.assertEqual(first.status, "INSERTED")
            self.assertEqual(second.status, "IDEMPOTENT")
            payload = json.loads(first.path.read_text(encoding="utf-8"))
            payload["artifact"]["holdout_evaluation_result"]["result_id"] = "tampered"
            first.path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            with self.assertRaises(TechnicalRiskHoldoutRegionEvidenceArtifactError):
                save_holdout_region_evidence_artifact(artifact, tmpdir)

    def test_review_can_consume_persisted_artifact_without_evaluation(self):
        artifact = self.artifact()
        validation_artifact = load_official_validation_evidence_artifact()
        with tempfile.TemporaryDirectory() as tmpdir:
            save_result = save_holdout_region_evidence_artifact(artifact, tmpdir)
            loaded = load_holdout_region_evidence_artifact(save_result.path)
            review = build_technical_risk_holdout_region_evidence_review_package_from_artifact(
                loaded,
                validation_artifact=validation_artifact,
            )

        self.assertEqual(review.holdout_evaluation_result_id, artifact.holdout_evaluation_result.result_id)
        self.assertEqual(review.holdout_summary.evaluation_count, 69)
        self.assertFalse(review.production_policy_created)

    def test_public_api_exports_artifact_contract(self):
        self.assertIs(risk_oos.TechnicalRiskHoldoutRegionEvidenceArtifact, TechnicalRiskHoldoutRegionEvidenceArtifact)
        self.assertIs(risk_oos.TechnicalRiskHoldoutRegionEvidenceArtifactCodec, TechnicalRiskHoldoutRegionEvidenceArtifactCodec)
        self.assertEqual(risk_oos.TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_CODEC_V1, TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_CODEC_V1)


if __name__ == "__main__":
    unittest.main()
