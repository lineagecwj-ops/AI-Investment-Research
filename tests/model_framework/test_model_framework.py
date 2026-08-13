import sys
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from model_framework import CLASSIFICATION_ALGORITHMS
from model_framework import REGRESSION_ALGORITHMS
from model_framework import ExperimentRecord
from model_framework import ExperimentTracker
from model_framework import ModelArtifact
from model_framework import ModelChecksumGenerator
from model_framework import ModelContext
from model_framework import ModelDefinition
from model_framework import ModelEvaluator
from model_framework import ModelRegistry
from model_framework import ModelRegistryError


class ModelFrameworkTestCase(unittest.TestCase):

    def created_at(self):
        return datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

    def definition(self):
        return ModelDefinition(
            model_id="BASELINE_CLASSIFIER_V1",
            model_name="Baseline Classifier",
            model_type="classification",
            version="v1",
            algorithm="logistic_regression",
            feature_set_version="feature_set_v1",
            target_version="TARGET_RETURN_60D_CLASS_V1",
            created_at=self.created_at(),
        )

    def context(self):
        return ModelContext(
            model_id="BASELINE_CLASSIFIER_V1",
            dataset_id="LTG_DATASET_V1",
            feature_version="feature_set_v1",
            target_version="TARGET_RETURN_60D_CLASS_V1",
            training_period=("2015-01-01", "2021-12-31"),
            validation_period=("2022-01-01", "2022-12-31"),
            oos_period=("2023-01-01", "2025-12-31"),
            experiment_id="exp_phase7i_baseline",
        )

    def artifact(self):
        return ModelArtifact(
            model_id="BASELINE_CLASSIFIER_V1",
            version="v1",
            dataset_id="LTG_DATASET_V1",
            algorithm="logistic_regression",
            training_metadata={
                "research_snapshot": "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1",
                "feature_version": "feature_set_v1",
                "target_version": "TARGET_RETURN_60D_CLASS_V1",
                "algorithm_version": "logistic_regression_interface_v1",
            },
            evaluation_summary={"accuracy": 0.75, "f1": 0.8},
            created_at=self.created_at(),
        )

    def test_model_definition_creation(self):
        definition = self.definition()

        self.assertEqual(definition.model_id, "BASELINE_CLASSIFIER_V1")
        self.assertEqual(definition.model_type, "classification")
        self.assertEqual(definition.algorithm, "logistic_regression")

    def test_model_registry_registration(self):
        registry = ModelRegistry()
        definition = self.definition()

        registry.register(definition)

        self.assertIs(registry.get_model("BASELINE_CLASSIFIER_V1", "v1"), definition)
        self.assertEqual(registry.list_models(), ("BASELINE_CLASSIFIER_V1:v1",))

    def test_duplicate_model_rejection(self):
        registry = ModelRegistry()
        registry.register(self.definition())

        with self.assertRaisesRegex(ModelRegistryError, "already registered"):
            registry.register(self.definition())

    def test_model_context_creation(self):
        context = self.context()

        self.assertEqual(context.dataset_id, "LTG_DATASET_V1")
        self.assertEqual(context.oos_period, ("2023-01-01", "2025-12-31"))
        self.assertEqual(context.experiment_id, "exp_phase7i_baseline")

    def test_model_artifact_generation(self):
        artifact = self.artifact()

        self.assertEqual(artifact.model_id, "BASELINE_CLASSIFIER_V1")
        self.assertEqual(artifact.dataset_id, "LTG_DATASET_V1")
        self.assertEqual(artifact.evaluation_summary["accuracy"], 0.75)
        self.assertIsNone(artifact.checksum)

    def test_experiment_tracking(self):
        tracker = ExperimentTracker()
        record = ExperimentRecord(
            experiment_id="exp_phase7i_baseline",
            model_version="v1",
            dataset_version="v1",
            parameters={"algorithm": "logistic_regression"},
            metrics={"accuracy": 0.75},
            created_at=self.created_at(),
        )

        tracker.record(record)

        self.assertIs(tracker.get("exp_phase7i_baseline"), record)
        self.assertEqual(tracker.list_experiments(), ("exp_phase7i_baseline",))

    def test_evaluation_metrics_calculation(self):
        evaluator = ModelEvaluator()

        classification = evaluator.evaluate_classification(
            y_true=(1, 0, 1, 0),
            y_pred=(1, 0, 0, 0),
            scores=(0.9, 0.2, 0.4, 0.1),
        )
        regression = evaluator.evaluate_regression(y_true=(1.0, 2.0, 3.0), y_pred=(1.0, 2.5, 2.5))

        self.assertEqual(classification.metrics["accuracy"], 0.75)
        self.assertEqual(classification.metrics["precision"], 1.0)
        self.assertEqual(classification.metrics["recall"], 0.5)
        self.assertEqual(classification.metrics["f1"], 2 / 3)
        self.assertEqual(classification.metrics["roc_auc"], 1.0)
        self.assertAlmostEqual(regression.metrics["mae"], 1 / 3)
        self.assertAlmostEqual(regression.metrics["rmse"], (0.5 / 3) ** 0.5)
        self.assertAlmostEqual(regression.metrics["r2"], 0.75)

    def test_model_lineage_validation(self):
        artifact = self.artifact()
        context = self.context()

        self.assertEqual(artifact.training_metadata["research_snapshot"], "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1")
        self.assertEqual(artifact.training_metadata["feature_version"], context.feature_version)
        self.assertEqual(artifact.training_metadata["target_version"], context.target_version)
        self.assertEqual(artifact.dataset_id, context.dataset_id)

    def test_checksum_reproducibility(self):
        generator = ModelChecksumGenerator()
        artifact = self.artifact()
        context = self.context()

        self.assertEqual(generator.generate(artifact, context), generator.generate(artifact, context))

    def test_invalid_configuration_rejection(self):
        with self.assertRaisesRegex(ValueError, "Unsupported model_type"):
            ModelDefinition(
                model_id="BAD_MODEL",
                model_name="Bad Model",
                model_type="production_signal",
                version="v1",
                algorithm="auto_trade",
                feature_set_version="feature_set_v1",
                target_version="target_v1",
                created_at=self.created_at(),
            )

    def test_baseline_algorithm_interface(self):
        self.assertEqual(CLASSIFICATION_ALGORITHMS.algorithms, ("logistic_regression", "random_forest"))
        self.assertEqual(REGRESSION_ALGORITHMS.algorithms, ("linear_regression", "gradient_boosting"))

    def test_model_modules_do_not_import_existing_runtime_boundaries(self):
        model_source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "model_framework").glob("*.py"))
        )

        forbidden_imports = (
            "live_data_store",
            "swing_scanner_service",
            "swing_scanner_pdf_export_service",
            "yfinance",
            "sqlite3",
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, model_source)


if __name__ == "__main__":
    unittest.main()
