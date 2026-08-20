import inspect
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_oos.validation_evidence_artifact as artifact_module
from risk_oos import TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_RESULT_V1
from risk_oos import TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_CODEC_V1
from risk_oos import TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_SCHEMA_V1
from risk_oos import TechnicalRiskCandidateSeverity
from risk_oos import TechnicalRiskValidationCandidateEvaluationError
from risk_oos import TechnicalRiskMonotonicityResult
from risk_oos import TechnicalRiskMonotonicityStatus
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskSeverityMAEMetrics
from risk_oos import TechnicalRiskValidationCandidateEvaluationRecord
from risk_oos import TechnicalRiskValidationCandidateEvaluationResult
from risk_oos import TechnicalRiskValidationCandidateSummary
from risk_oos import TechnicalRiskValidationEvidenceArtifact
from risk_oos import TechnicalRiskValidationEvidenceArtifactCodec
from risk_oos import TechnicalRiskValidationEvidenceArtifactError
from risk_oos import load_validation_evidence_artifact
from risk_oos import save_validation_evidence_artifact


class TechnicalRiskValidationEvidenceArtifactTestCase(unittest.TestCase):
    def result(self, *, candidate_count=4, threshold_count=81):
        candidate_ids = tuple(f"TECH_POLICY_CANDIDATE_{chr(ord('A') + index)}" for index in range(candidate_count))
        threshold_ids = tuple(f"technical_risk_threshold_set_{index:03d}" for index in range(1, threshold_count + 1))
        candidate_identities = tuple((candidate_id, "v1", f"{candidate_id}_checksum") for candidate_id in candidate_ids)
        threshold_identities = tuple((threshold_id, f"{threshold_id}_checksum") for threshold_id in threshold_ids)
        records = []
        for candidate_id, _, candidate_checksum in candidate_identities:
            for threshold_id, threshold_checksum in threshold_identities:
                records.append(self.record(candidate_id, candidate_checksum, threshold_id, threshold_checksum))
        summaries = tuple(
            TechnicalRiskValidationCandidateSummary(
                candidate_id=candidate_id,
                evaluation_count=threshold_count,
                monotonicity_status_counts={"PASS": threshold_count * 2},
            )
            for candidate_id in candidate_ids
        )
        return TechnicalRiskValidationCandidateEvaluationResult(
            result_id="technical_risk_validation_candidate_evaluation_fixture",
            result_version=TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_RESULT_V1,
            result_checksum="validation_result_checksum_fixture",
            orchestrator_version="TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_ORCHESTRATOR_V1",
            methodology_version="TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1",
            split_role=TechnicalRiskOOSSplitRole.VALIDATION,
            split_id="technical_risk_v1_validation_2022_2023",
            validation_start_date=date(2022, 1, 1),
            validation_end_date=date(2023, 12, 31),
            dataset_id="validation_dataset_fixture",
            dataset_checksum="validation_dataset_checksum_fixture",
            validation_row_count=90322,
            source_snapshot_id="research_snapshot_fixture",
            source_snapshot_checksum="research_snapshot_checksum_fixture",
            axis_set_id="technical_risk_v1_threshold_axis_set",
            axis_set_checksum="axis_set_checksum_fixture",
            threshold_grid_result_id="threshold_grid_result_fixture",
            threshold_grid_result_checksum="threshold_grid_result_checksum_fixture",
            candidate_count=candidate_count,
            threshold_set_count=threshold_count,
            evaluation_count=len(records),
            dataset_materialization_count=1,
            candidate_identities=candidate_identities,
            threshold_identities=threshold_identities,
            evaluation_records=tuple(records),
            candidate_summaries=summaries,
        )

    def record(self, candidate_id, candidate_checksum, threshold_id, threshold_checksum):
        return TechnicalRiskValidationCandidateEvaluationRecord(
            evaluation_id=f"eval_{candidate_id}_{threshold_id}",
            evaluation_checksum=f"eval_checksum_{candidate_id}_{threshold_id}",
            candidate_id=candidate_id,
            candidate_version="v1",
            candidate_structural_checksum=candidate_checksum,
            threshold_set_id=threshold_id,
            threshold_set_version="v1",
            threshold_set_checksum=threshold_checksum,
            evaluated_row_count=90322,
            aggregate_metrics=(
                self.metric(TechnicalRiskCandidateSeverity.LOW, 60000, "0.6643032718485015832255708498483171", "-0.030"),
                self.metric(TechnicalRiskCandidateSeverity.MEDIUM, 25000, "0.2767855056353822960089468656548704", "-0.050"),
                self.metric(TechnicalRiskCandidateSeverity.HIGH, 5322, "0.05891122251611612076548228449681296", "-0.080"),
            ),
            monotonicity_results=(
                self.monotonicity(20),
                self.monotonicity(60),
            ),
        )

    def metric(self, severity, sample_count, coverage, median):
        return TechnicalRiskSeverityMAEMetrics(
            split_role=TechnicalRiskOOSSplitRole.VALIDATION,
            severity=severity,
            sample_count=sample_count,
            coverage_ratio=Decimal(coverage),
            mae20_mean=Decimal(median) + Decimal("0.001"),
            mae20_median=Decimal(median),
            mae20_p25=Decimal(median) - Decimal("0.010"),
            mae20_p75=Decimal(median) + Decimal("0.010"),
            mae60_mean=Decimal(median) - Decimal("0.005"),
            mae60_median=Decimal(median) - Decimal("0.010"),
            mae60_p25=Decimal(median) - Decimal("0.020"),
            mae60_p75=Decimal(median),
        )

    def monotonicity(self, horizon):
        return TechnicalRiskMonotonicityResult(
            split_role=TechnicalRiskOOSSplitRole.VALIDATION,
            horizon=horizon,
            status=TechnicalRiskMonotonicityStatus.PASS,
            low_median=Decimal("-0.030") if horizon == 20 else Decimal("-0.040"),
            medium_median=Decimal("-0.050") if horizon == 20 else Decimal("-0.060"),
            high_median=Decimal("-0.080") if horizon == 20 else Decimal("-0.090"),
        )

    def artifact(self, result=None):
        return TechnicalRiskValidationEvidenceArtifact.from_validation_result(result or self.result())

    def payload(self, artifact=None):
        return json.loads(TechnicalRiskValidationEvidenceArtifactCodec().encode(artifact or self.artifact()))

    def encode_payload(self, payload):
        payload["serialization_checksum"] = artifact_module.serialization_checksum(payload)
        return artifact_module.canonical_json_dumps(payload)

    def test_immutable_evidence_artifact_schema_identity_and_checksum(self):
        artifact = self.artifact()
        same = self.artifact()

        self.assertEqual(artifact.artifact_schema_version, TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_SCHEMA_V1)
        self.assertTrue(artifact.artifact_id.startswith("technical_risk_validation_evidence_"))
        self.assertEqual(artifact.artifact_id, same.artifact_id)
        self.assertEqual(artifact.artifact_checksum, same.artifact_checksum)

    def test_schema_and_codec_versions_are_exact(self):
        payload = self.payload()

        self.assertEqual(payload["schema_version"], TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_SCHEMA_V1)
        self.assertEqual(payload["codec_version"], TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_CODEC_V1)

    def test_canonical_324_entry_ordering_with_synthetic_fixture(self):
        artifact = self.artifact()

        self.assertEqual(artifact.validation_result.evaluation_count, 324)
        self.assertEqual(len(artifact.validation_result.evaluation_records), 324)
        self.assertEqual(artifact.validation_result.candidate_count, 4)
        self.assertEqual(artifact.validation_result.threshold_set_count, 81)
        self.assertEqual(
            artifact.validation_result.evaluation_records[0].candidate_id,
            "TECH_POLICY_CANDIDATE_A",
        )
        self.assertEqual(
            artifact.validation_result.evaluation_records[-1].candidate_id,
            "TECH_POLICY_CANDIDATE_D",
        )

    def test_encode_decode_round_trip_preserves_domain_object(self):
        artifact = self.artifact()

        decoded = TechnicalRiskValidationEvidenceArtifactCodec().decode(
            TechnicalRiskValidationEvidenceArtifactCodec().encode(artifact)
        )

        self.assertEqual(decoded, artifact)
        self.assertIsInstance(decoded.validation_result, TechnicalRiskValidationCandidateEvaluationResult)

    def test_missing_field_rejected(self):
        payload = self.payload()
        del payload["artifact"]["validation_result"]["evaluation_records"]

        with self.assertRaisesRegex(TechnicalRiskValidationEvidenceArtifactError, "fields mismatch"):
            TechnicalRiskValidationEvidenceArtifactCodec().decode(self.encode_payload(payload))

    def test_unknown_field_rejected(self):
        payload = self.payload()
        payload["artifact"]["winner"] = "TECH_POLICY_CANDIDATE_A"

        with self.assertRaisesRegex(TechnicalRiskValidationEvidenceArtifactError, "fields mismatch"):
            TechnicalRiskValidationEvidenceArtifactCodec().decode(self.encode_payload(payload))

    def test_tamper_rejected(self):
        payload = self.payload()
        payload["artifact"]["validation_result"]["evaluation_records"][0]["evaluation_checksum"] = "tampered"

        with self.assertRaisesRegex(TechnicalRiskValidationEvidenceArtifactError, "serialization_checksum mismatch"):
            TechnicalRiskValidationEvidenceArtifactCodec().decode(json.dumps(payload, sort_keys=True))

    def test_checksum_mismatch_rejected(self):
        payload = self.payload()
        payload["artifact"]["artifact_checksum"] = "wrong_checksum"

        with self.assertRaisesRegex(TechnicalRiskValidationEvidenceArtifactError, "artifact_checksum mismatch"):
            TechnicalRiskValidationEvidenceArtifactCodec().decode(self.encode_payload(payload))

    def test_immutable_save_idempotency_and_conflict_rejected(self):
        artifact = self.artifact()
        with tempfile.TemporaryDirectory() as tmp:
            first = save_validation_evidence_artifact(artifact, tmp)
            second = save_validation_evidence_artifact(artifact, tmp)

            self.assertEqual(first.status, "INSERTED")
            self.assertEqual(second.status, "IDEMPOTENT")

            payload = json.loads(Path(first.path).read_text(encoding="utf-8"))
            payload["artifact"]["validation_result"]["dataset_checksum"] = "changed_dataset_checksum"
            payload["serialization_checksum"] = artifact_module.serialization_checksum(payload)
            Path(first.path).write_text(artifact_module.canonical_json_dumps(payload), encoding="utf-8")
            with self.assertRaises(TechnicalRiskValidationEvidenceArtifactError):
                save_validation_evidence_artifact(artifact, tmp)

    def test_official_loader_returns_exact_artifact(self):
        artifact = self.artifact()
        with tempfile.TemporaryDirectory() as tmp:
            saved = save_validation_evidence_artifact(artifact, tmp)

            loaded = load_validation_evidence_artifact(saved.path)

            self.assertEqual(loaded, artifact)

    def test_individual_coverage_and_sample_counts_are_preserved(self):
        decoded = TechnicalRiskValidationEvidenceArtifactCodec().decode(
            TechnicalRiskValidationEvidenceArtifactCodec().encode(self.artifact())
        )
        metrics = decoded.validation_result.evaluation_records[0].aggregate_metrics

        self.assertEqual(metrics[0].sample_count, 60000)
        self.assertEqual(metrics[1].coverage_ratio, Decimal("0.2767855056353822960089468656548704"))
        self.assertEqual(metrics[2].severity, TechnicalRiskCandidateSeverity.HIGH)

    def test_individual_mae20_and_mae60_metrics_are_preserved(self):
        decoded = TechnicalRiskValidationEvidenceArtifactCodec().decode(
            TechnicalRiskValidationEvidenceArtifactCodec().encode(self.artifact())
        )
        high_metric = decoded.validation_result.evaluation_records[0].aggregate_metrics[2]

        self.assertEqual(high_metric.mae20_median, Decimal("-0.080"))
        self.assertEqual(high_metric.mae20_p25, Decimal("-0.090"))
        self.assertEqual(high_metric.mae60_median, Decimal("-0.090"))
        self.assertEqual(high_metric.mae60_p75, Decimal("-0.080"))

    def test_monotonicity_and_candidate_threshold_linkage_are_preserved(self):
        decoded = TechnicalRiskValidationEvidenceArtifactCodec().decode(
            TechnicalRiskValidationEvidenceArtifactCodec().encode(self.artifact())
        )
        record = decoded.validation_result.evaluation_records[0]

        self.assertEqual(record.candidate_id, "TECH_POLICY_CANDIDATE_A")
        self.assertEqual(record.threshold_set_id, "technical_risk_threshold_set_001")
        self.assertEqual(record.monotonicity_results[0].status, TechnicalRiskMonotonicityStatus.PASS)
        self.assertEqual(record.monotonicity_results[1].horizon, 60)

    def test_no_winner_ranking_or_acceptance_criteria_fields(self):
        encoded = TechnicalRiskValidationEvidenceArtifactCodec().encode(self.artifact())
        forbidden_tokens = (
            "winner",
            "rank",
            "best_candidate",
            "best_threshold",
            "selected_candidate",
            "selected_threshold",
            "recommended_policy",
            "coverage_floor",
            "sample_floor",
            "separation_floor",
            "weighted_score",
        )

        for token in forbidden_tokens:
            self.assertNotIn(token, encoded)

    def test_rejects_holdout_result_and_has_no_holdout_dependency(self):
        with self.assertRaisesRegex(TechnicalRiskValidationCandidateEvaluationError, "VALIDATION"):
            replace(self.result(), split_role=TechnicalRiskOOSSplitRole.HOLDOUT)
        source = inspect.getsource(artifact_module)
        self.assertNotIn("TechnicalRiskHoldout", source)

    def test_rejects_production_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            production_path = Path(tmp) / "data" / "production" / "evidence"
            with self.assertRaisesRegex(TechnicalRiskValidationEvidenceArtifactError, "production path"):
                save_validation_evidence_artifact(self.artifact(), production_path)

    def test_source_has_no_network_db_or_selection_behavior(self):
        source = inspect.getsource(artifact_module)
        forbidden_tokens = (
            "sqlite3",
            "ResearchDataStore",
            "yfinance",
            "requests",
            "urllib",
            "def search",
            "def optimize",
            "find_best",
            "select_best",
            "TechnicalRiskSignalProducer",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
