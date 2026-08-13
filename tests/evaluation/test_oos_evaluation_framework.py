import sys
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from evaluation import EvaluationArtifact
from evaluation import EvaluationChecksumGenerator
from evaluation import EvaluationContext
from evaluation import EvaluationDefinition
from evaluation import ModelEvaluatorExtension
from evaluation import OOSSplitError
from evaluation import OOSSplitter
from evaluation import PerformanceRecord
from evaluation import PerformanceTracker


class OOSEvaluationFrameworkTestCase(unittest.TestCase):

    def created_at(self):
        return datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

    def context(self):
        return EvaluationContext(
            model_id="BASELINE_CLASSIFIER_V1",
            model_version="v1",
            dataset_id="LTG_DATASET_V1",
            training_period=("2015-01-01", "2021-12-31"),
            validation_period=("2022-01-01", "2022-12-31"),
            oos_period=("2023-01-01", "2025-12-31"),
            experiment_id="exp_phase7j_oos",
        )

    def artifact(self):
        return EvaluationArtifact(
            evaluation_id="OOS_EVALUATION_V1",
            model_id="BASELINE_CLASSIFIER_V1",
            dataset_id="LTG_DATASET_V1",
            metrics={"accuracy": 0.75, "f1": 0.8},
            oos_period=("2023-01-01", "2025-12-31"),
            created_at=self.created_at(),
            validation_status="PASS",
        )

    def test_evaluation_definition_creation(self):
        definition = EvaluationDefinition(
            evaluation_id="OOS_EVALUATION_V1",
            evaluation_type="frozen_oos",
            metrics=("accuracy", "precision", "recall", "f1", "roc_auc"),
            dataset_version="v1",
            model_version="v1",
            created_at=self.created_at(),
        )

        self.assertEqual(definition.evaluation_id, "OOS_EVALUATION_V1")
        self.assertEqual(definition.evaluation_type, "frozen_oos")
        self.assertIn("accuracy", definition.metrics)

    def test_evaluation_context_creation(self):
        context = self.context()

        self.assertEqual(context.model_id, "BASELINE_CLASSIFIER_V1")
        self.assertEqual(context.dataset_id, "LTG_DATASET_V1")
        self.assertEqual(context.oos_period, ("2023-01-01", "2025-12-31"))

    def test_oos_split_ordering(self):
        split = OOSSplitter().split(self.context())

        self.assertEqual(split.training_period, ("2015-01-01", "2021-12-31"))
        self.assertEqual(split.validation_period, ("2022-01-01", "2022-12-31"))
        self.assertEqual(split.oos_period, ("2023-01-01", "2025-12-31"))

    def test_training_validation_oos_separation(self):
        splitter = OOSSplitter()

        with self.assertRaisesRegex(OOSSplitError, "without overlap"):
            splitter.validate_ordering(
                ("2015-01-01", "2022-06-30"),
                ("2022-01-01", "2022-12-31"),
                ("2023-01-01", "2025-12-31"),
            )

    def test_classification_metrics(self):
        result = ModelEvaluatorExtension().evaluate_classification(
            y_true=(1, 0, 1, 0),
            y_pred=(1, 0, 0, 0),
            scores=(0.9, 0.2, 0.4, 0.1),
        )

        self.assertEqual(result.metrics["accuracy"], 0.75)
        self.assertEqual(result.metrics["precision"], 1.0)
        self.assertEqual(result.metrics["recall"], 0.5)
        self.assertEqual(result.metrics["f1"], 2 / 3)
        self.assertEqual(result.metrics["roc_auc"], 1.0)

    def test_regression_metrics(self):
        result = ModelEvaluatorExtension().evaluate_regression(
            y_true=(1.0, 2.0, 3.0),
            y_pred=(1.0, 2.5, 2.5),
        )

        self.assertAlmostEqual(result.metrics["mae"], 1 / 3)
        self.assertAlmostEqual(result.metrics["rmse"], (0.5 / 3) ** 0.5)
        self.assertAlmostEqual(result.metrics["r2"], 0.75)

    def test_investment_specific_evaluation_framework(self):
        result = ModelEvaluatorExtension().evaluate_investment(
            model_scores=(0.9, 0.2, 0.7, 0.1),
            realized_returns=(0.10, -0.02, 0.05, -0.04),
            top_n=2,
        )

        self.assertGreater(result.metrics["return_correlation"], 0.0)
        self.assertGreater(result.metrics["rank_correlation"], 0.0)
        self.assertAlmostEqual(result.metrics["top_n_performance"], 0.075)
        self.assertEqual(result.metrics["drawdown"], -0.04)
        self.assertGreater(result.metrics["stability"], 0.0)

    def test_performance_tracking(self):
        tracker = PerformanceTracker()
        record = PerformanceRecord(
            model_id="BASELINE_CLASSIFIER_V1",
            dataset_id="LTG_DATASET_V1",
            evaluation_version="v1",
            metrics={"accuracy": 0.75},
            created_at=self.created_at(),
        )

        tracker.record(record)

        self.assertEqual(tracker.list_records(), (record,))

    def test_evaluation_artifact_creation(self):
        artifact = self.artifact()

        self.assertEqual(artifact.evaluation_id, "OOS_EVALUATION_V1")
        self.assertEqual(artifact.model_id, "BASELINE_CLASSIFIER_V1")
        self.assertEqual(artifact.dataset_id, "LTG_DATASET_V1")
        self.assertEqual(artifact.validation_status, "PASS")

    def test_checksum_reproducibility(self):
        generator = EvaluationChecksumGenerator()
        artifact = self.artifact()
        context = self.context()

        self.assertEqual(generator.generate(artifact, context), generator.generate(artifact, context))

    def test_oos_leakage_rejection(self):
        with self.assertRaisesRegex(OOSSplitError, "cannot be used for tuning"):
            OOSSplitter().reject_oos_contamination("oos")

    def test_model_framework_integration_metadata(self):
        artifact = self.artifact()
        context = self.context()

        self.assertEqual(artifact.model_id, context.model_id)
        self.assertEqual(artifact.dataset_id, context.dataset_id)
        self.assertEqual(artifact.oos_period, context.oos_period)

    def test_evaluation_modules_do_not_import_existing_runtime_boundaries(self):
        evaluation_source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "evaluation").glob("*.py"))
        )

        forbidden_imports = (
            "live_data_store",
            "swing_scanner_service",
            "swing_scanner_pdf_export_service",
            "yfinance",
            "sqlite3",
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, evaluation_source)


if __name__ == "__main__":
    unittest.main()
