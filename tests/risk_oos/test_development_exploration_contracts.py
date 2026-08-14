import inspect
import sys
import unittest
from datetime import datetime
from datetime import timezone
from dataclasses import fields
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk_oos import TECH_RISK_CANDIDATE_EVALUATOR_V1
from risk_oos import TECH_RISK_CANDIDATE_SET_CONTRACT_V1
from risk_oos import TECH_RISK_CONTINUOUS_MAE_METRIC_V1
from risk_oos import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos import TECH_RISK_DEVELOPMENT_EVALUATION_CONTEXT_V1
from risk_oos import TECH_RISK_NUMERIC_REPRESENTATION_V1
from risk_oos import TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1
from risk_oos import DevelopmentEvaluationContext
from risk_oos import TechnicalRiskCandidateFamily
from risk_oos import TechnicalRiskCandidateIdentity
from risk_oos import TechnicalRiskCandidateSet
from risk_oos import TechnicalRiskDevelopmentExplorationError
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskThresholdDimension
from risk_oos import TechnicalRiskThresholdDimensionId
from risk_oos import TechnicalRiskThresholdIdentity
from risk_oos import TechnicalRiskThresholdOperator
from risk_oos import TechnicalRiskThresholdSet
from risk_oos import ThresholdCandidateGenerationContract
from risk_oos import technical_risk_candidate_a_spec
from risk_oos import technical_risk_candidate_b_spec


class TechnicalRiskDevelopmentExplorationContractTestCase(unittest.TestCase):

    def threshold_dimension(self, dimension_id, value):
        return TechnicalRiskThresholdDimension(
            dimension_id=dimension_id,
            operator=TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            canonical_value=value,
        )

    def threshold_set(self, threshold_set_id="threshold_set_001", close_vs_sma20="-0.05", **overrides):
        values = {
            "threshold_set_id": threshold_set_id,
            "threshold_set_version": "v1",
            "numeric_representation_version": TECH_RISK_NUMERIC_REPRESENTATION_V1,
            "dimensions": (
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, close_vs_sma20),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.05"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, "-0.05"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "40"),
            ),
            "compatible_candidate_families": tuple(TechnicalRiskCandidateFamily),
        }
        values.update(overrides)
        return TechnicalRiskThresholdSet(**values)

    def threshold_generation(self, thresholds=None, **overrides):
        if thresholds is None:
            thresholds = (
                TechnicalRiskThresholdIdentity.from_threshold_set(self.threshold_set("threshold_set_001")),
                TechnicalRiskThresholdIdentity.from_threshold_set(self.threshold_set("threshold_set_002", close_vs_sma20="-0.06")),
            )
        threshold_ids = tuple(threshold.threshold_set_id for threshold in thresholds)
        threshold_checksums = tuple(threshold.threshold_set_checksum for threshold in thresholds)
        values = {
            "generation_id": None,
            "generation_version": TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1,
            "generation_method_id": "TECH_RISK_FIXED_GRID_CANDIDATES",
            "generation_method_version": "v1",
            "numeric_representation_version": TECH_RISK_NUMERIC_REPRESENTATION_V1,
            "numeric_context_version": TECH_RISK_DECIMAL_CONTEXT_V1,
            "candidate_family": TechnicalRiskCandidateFamily.MEDIUM_TERM_TREND_CENTRIC,
            "source_spec_version": "technical_risk_rule_candidate_generation_spec_v1",
            "generated_threshold_set_ids": threshold_ids,
            "generated_threshold_set_checksums": threshold_checksums,
        }
        values.update(overrides)
        return ThresholdCandidateGenerationContract(**values)

    def candidate_set(self, candidates=None, **overrides):
        if candidates is None:
            candidates = (
                TechnicalRiskCandidateIdentity.from_candidate_spec(technical_risk_candidate_a_spec()),
                TechnicalRiskCandidateIdentity.from_candidate_spec(technical_risk_candidate_b_spec()),
            )
        candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
        candidate_checksums = tuple(candidate.candidate_structural_checksum for candidate in candidates)
        values = {
            "candidate_set_id": None,
            "candidate_set_version": TECH_RISK_CANDIDATE_SET_CONTRACT_V1,
            "dataset_checksum": "dataset_checksum_001",
            "generation_id": self.threshold_generation().generation_id,
            "candidate_ids": candidate_ids,
            "candidate_structural_checksums": candidate_checksums,
        }
        values.update(overrides)
        return TechnicalRiskCandidateSet(**values)

    def development_context(self, **overrides):
        candidate_set = self.candidate_set()
        generation = self.threshold_generation()
        values = {
            "development_experiment_id": None,
            "dataset_id": "technical_risk_oos_dataset_001",
            "dataset_checksum": "dataset_checksum_001",
            "split_role": TechnicalRiskOOSSplitRole.DEVELOPMENT,
            "candidate_set_id": candidate_set.candidate_set_id,
            "threshold_candidate_set_id": generation.generation_id,
            "exploration_version": TECH_RISK_DEVELOPMENT_EVALUATION_CONTEXT_V1,
            "evaluator_version": TECH_RISK_CANDIDATE_EVALUATOR_V1,
            "metric_version": TECH_RISK_CONTINUOUS_MAE_METRIC_V1,
            "numeric_context_version": TECH_RISK_DECIMAL_CONTEXT_V1,
        }
        values.update(overrides)
        return DevelopmentEvaluationContext(**values)

    def test_development_context_deterministic(self):
        first = self.development_context()
        second = self.development_context()

        self.assertEqual(first.development_experiment_id, second.development_experiment_id)
        self.assertEqual(first.development_experiment_checksum, second.development_experiment_checksum)
        self.assertEqual(first.split_role, TechnicalRiskOOSSplitRole.DEVELOPMENT)

    def test_threshold_generation_contract_deterministic(self):
        first = self.threshold_generation()
        reversed_thresholds = tuple(
            TechnicalRiskThresholdIdentity(threshold_set_id, "v1", threshold_set_checksum)
            for threshold_set_id, threshold_set_checksum in reversed(
                tuple(zip(first.generated_threshold_set_ids, first.generated_threshold_set_checksums))
            )
        )
        second = self.threshold_generation(thresholds=reversed_thresholds)

        self.assertEqual(first.generation_id, second.generation_id)
        self.assertEqual(first.generation_checksum, second.generation_checksum)
        self.assertEqual(first.generated_threshold_set_ids, second.generated_threshold_set_ids)
        self.assertEqual(first.generated_threshold_set_checksums, second.generated_threshold_set_checksums)

    def test_candidate_set_deterministic(self):
        first = self.candidate_set()
        reversed_candidates = tuple(
            TechnicalRiskCandidateIdentity(candidate_id, "v1", candidate_structural_checksum)
            for candidate_id, candidate_structural_checksum in reversed(
                tuple(zip(first.candidate_ids, first.candidate_structural_checksums))
            )
        )
        second = self.candidate_set(candidates=reversed_candidates)

        self.assertEqual(first.candidate_set_id, second.candidate_set_id)
        self.assertEqual(first.candidate_set_checksum, second.candidate_set_checksum)
        self.assertEqual(first.candidate_ids, second.candidate_ids)
        self.assertEqual(first.candidate_structural_checksums, second.candidate_structural_checksums)

    def test_dataset_checksum_mutation_changes_identity(self):
        first = self.development_context(dataset_checksum="dataset_checksum_001")
        second = self.development_context(dataset_checksum="dataset_checksum_002")
        first_set = self.candidate_set(dataset_checksum="dataset_checksum_001")
        second_set = self.candidate_set(dataset_checksum="dataset_checksum_002")

        self.assertNotEqual(first.development_experiment_id, second.development_experiment_id)
        self.assertNotEqual(first.development_experiment_checksum, second.development_experiment_checksum)
        self.assertNotEqual(first_set.candidate_set_id, second_set.candidate_set_id)
        self.assertNotEqual(first_set.candidate_set_checksum, second_set.candidate_set_checksum)

    def test_generation_method_version_change_changes_checksum(self):
        first = self.threshold_generation(generation_method_version="v1")
        second = self.threshold_generation(generation_method_version="v2")

        self.assertNotEqual(first.generation_id, second.generation_id)
        self.assertNotEqual(first.generation_checksum, second.generation_checksum)

    def test_timestamp_metadata_does_not_affect_semantic_checksum(self):
        first = self.development_context(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        second = self.development_context(created_at=datetime(2026, 2, 1, tzinfo=timezone.utc))
        first_generation = self.threshold_generation(generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        second_generation = self.threshold_generation(generated_at=datetime(2026, 2, 1, tzinfo=timezone.utc))
        first_set = self.candidate_set(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        second_set = self.candidate_set(created_at=datetime(2026, 2, 1, tzinfo=timezone.utc))

        self.assertEqual(first.development_experiment_id, second.development_experiment_id)
        self.assertEqual(first.development_experiment_checksum, second.development_experiment_checksum)
        self.assertEqual(first_generation.generation_id, second_generation.generation_id)
        self.assertEqual(first_generation.generation_checksum, second_generation.generation_checksum)
        self.assertEqual(first_set.candidate_set_id, second_set.candidate_set_id)
        self.assertEqual(first_set.candidate_set_checksum, second_set.candidate_set_checksum)

    def test_holdout_rejected(self):
        with self.assertRaisesRegex(TechnicalRiskDevelopmentExplorationError, "DEVELOPMENT"):
            self.development_context(split_role=TechnicalRiskOOSSplitRole.HOLDOUT)

    def test_validation_rejected(self):
        with self.assertRaisesRegex(TechnicalRiskDevelopmentExplorationError, "DEVELOPMENT"):
            self.development_context(split_role=TechnicalRiskOOSSplitRole.VALIDATION)

    def test_no_winner_or_final_policy_fields(self):
        forbidden_fields = {
            "winner_candidate",
            "best_threshold",
            "selected_threshold",
            "final_policy",
            "holdout_result",
        }
        for contract in (DevelopmentEvaluationContext, ThresholdCandidateGenerationContract, TechnicalRiskCandidateSet):
            self.assertTrue(forbidden_fields.isdisjoint({field.name for field in fields(contract)}))

    def test_no_optimization_api(self):
        import risk_oos.development_exploration as development_exploration

        source = inspect.getsource(development_exploration)
        forbidden_tokens = (
            "def search",
            "def optimize",
            "def find_best",
            "def evaluate_best",
            "winner_candidate",
            "best_threshold",
            "selected_threshold",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_candidate_checksum_change_changes_candidate_set_identity(self):
        first = self.candidate_set()
        changed_candidate = TechnicalRiskCandidateIdentity(
            candidate_id=first.candidate_ids[0],
            candidate_version="v1",
            candidate_structural_checksum="changed_candidate_checksum",
        )
        unchanged_candidate = TechnicalRiskCandidateIdentity(
            candidate_id=first.candidate_ids[1],
            candidate_version="v1",
            candidate_structural_checksum=first.candidate_structural_checksums[1],
        )
        second = self.candidate_set(candidates=(changed_candidate, unchanged_candidate))

        self.assertNotEqual(first.candidate_set_id, second.candidate_set_id)
        self.assertNotEqual(first.candidate_set_checksum, second.candidate_set_checksum)

    def test_threshold_generation_contract_change_changes_context_identity(self):
        first_generation = self.threshold_generation(generation_method_version="v1")
        second_generation = self.threshold_generation(generation_method_version="v2")
        first = self.development_context(threshold_candidate_set_id=first_generation.generation_id)
        second = self.development_context(threshold_candidate_set_id=second_generation.generation_id)

        self.assertNotEqual(first.development_experiment_id, second.development_experiment_id)
        self.assertNotEqual(first.development_experiment_checksum, second.development_experiment_checksum)

    def test_public_api_exports_3ca_contracts(self):
        self.assertEqual(TECH_RISK_DEVELOPMENT_EVALUATION_CONTEXT_V1, "TECH_RISK_DEVELOPMENT_EVALUATION_CONTEXT_V1")
        self.assertEqual(TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1, "TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1")
        self.assertEqual(TECH_RISK_CANDIDATE_SET_CONTRACT_V1, "TECH_RISK_CANDIDATE_SET_CONTRACT_V1")

    def test_architecture_boundary(self):
        source = (PROJECT_ROOT / "src" / "risk_oos" / "development_exploration.py").read_text(encoding="utf-8")
        forbidden_tokens = (
            "sqlite",
            "LiveDataStore",
            "ResearchDataStore",
            "yfinance",
            "scanner",
            "PDF",
            "open(",
            "Path(",
            "TechnicalRiskSignalProducer",
            "RiskSignal",
            "RiskSeverity",
            "app.py",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
