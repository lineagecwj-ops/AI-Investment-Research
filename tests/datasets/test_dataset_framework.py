import sys
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from datasets import DatasetBuilder
from datasets import DatasetChecksumGenerator
from datasets import DatasetContext
from datasets import DatasetDefinition
from datasets import DatasetRegistry
from datasets import DatasetRegistryError
from datasets import DatasetRow
from datasets import DatasetValidationError
from datasets import DatasetValidator
from features import FeatureArtifact
from targets import TargetArtifact


class DatasetFrameworkTestCase(unittest.TestCase):

    def created_at(self):
        return datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

    def definition(self):
        return DatasetDefinition(
            dataset_id="LTG_DATASET_V1",
            dataset_name="Long-Term Growth Dataset",
            dataset_version="v1",
            feature_versions=("feature_set_v1",),
            target_versions=("TARGET_RETURN_60D_REG_V1",),
            snapshot_id="research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1",
            universe_id="frozen_twse_218",
            created_at=self.created_at(),
        )

    def context(self):
        return DatasetContext(
            dataset_id="LTG_DATASET_V1",
            snapshot_id="research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1",
            feature_set_version="feature_set_v1",
            target_version="TARGET_RETURN_60D_REG_V1",
            universe_id="frozen_twse_218",
            calculation_id="dataset_calc_phase7h",
            universe_version="v1",
            split_policy="train_validation_oos_v1",
        )

    def feature_artifact(self, feature_id="TECH_SMA20_V1", checksum="feature_checksum_1"):
        return FeatureArtifact(
            feature_id=feature_id,
            feature_version="v1",
            snapshot_id=self.context().snapshot_id,
            calculation_id=f"{feature_id}_calc",
            created_at=self.created_at(),
            checksum=checksum,
            validation_status="PASS",
        )

    def target_artifact(self, symbol="2330.TW", reference_date=date(2026, 1, 1), checksum="target_checksum_1"):
        return TargetArtifact(
            target_id="TARGET_RETURN_60D_REG_V1",
            target_version="v1",
            symbol=symbol,
            reference_date=reference_date,
            target_value=0.12,
            calculation_id=f"{symbol}_target_calc",
            created_at=self.created_at(),
            checksum=checksum,
            validation_status="PASS",
        )

    def test_dataset_definition_creation(self):
        definition = self.definition()

        self.assertEqual(definition.dataset_id, "LTG_DATASET_V1")
        self.assertEqual(definition.dataset_version, "v1")
        self.assertEqual(definition.feature_versions, ("feature_set_v1",))
        self.assertEqual(definition.target_versions, ("TARGET_RETURN_60D_REG_V1",))

    def test_dataset_context_creation(self):
        context = self.context()

        self.assertEqual(context.snapshot_id, self.definition().snapshot_id)
        self.assertEqual(context.universe_id, "frozen_twse_218")
        self.assertEqual(context.split_policy, "train_validation_oos_v1")

    def test_dataset_registry_registration(self):
        registry = DatasetRegistry()
        definition = self.definition()

        registry.register(definition)

        self.assertIs(registry.get_definition("LTG_DATASET_V1", "v1"), definition)
        self.assertEqual(registry.list_datasets(), ("LTG_DATASET_V1:v1",))

    def test_duplicate_dataset_rejection(self):
        registry = DatasetRegistry()
        registry.register(self.definition())

        with self.assertRaisesRegex(DatasetRegistryError, "already registered"):
            registry.register(self.definition())

    def test_feature_target_join(self):
        result = DatasetBuilder(self.context()).build(
            (self.feature_artifact(),),
            (self.target_artifact(),),
        )

        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0].symbol, "2330.TW")
        self.assertEqual(result.rows[0].features, ("TECH_SMA20_V1",))
        self.assertEqual(result.rows[0].target, "TARGET_RETURN_60D_REG_V1")
        self.assertEqual(result.rows[0].metadata["target_value"], 0.12)

    def test_dataset_artifact_generation(self):
        result = DatasetBuilder(self.context()).build(
            (self.feature_artifact(),),
            (self.target_artifact(),),
        )

        self.assertEqual(result.artifact.dataset_id, "LTG_DATASET_V1")
        self.assertEqual(result.artifact.snapshot_id, self.context().snapshot_id)
        self.assertEqual(result.artifact.row_count, 1)
        self.assertEqual(result.artifact.validation_status, "PASS")
        self.assertTrue(result.artifact.checksum)

    def test_checksum_deterministic(self):
        builder = DatasetBuilder(self.context())
        first = builder.build((self.feature_artifact(),), (self.target_artifact(),))
        second = builder.build((self.feature_artifact(),), (self.target_artifact(),))

        self.assertEqual(first.artifact.checksum, second.artifact.checksum)

    def test_validation_pass(self):
        result = DatasetBuilder(self.context()).build(
            (self.feature_artifact(),),
            (self.target_artifact(),),
        )

        DatasetValidator().validate(result, self.context())

    def test_missing_feature_detection(self):
        row = DatasetRow(
            symbol="2330.TW",
            reference_date=date(2026, 1, 1),
            features=(),
            target="TARGET_RETURN_60D_REG_V1",
            metadata={"target_checksum": "target_checksum_1", "snapshot_id": self.context().snapshot_id},
        )
        artifact = DatasetBuilder(self.context()).build((self.feature_artifact(),), (self.target_artifact(),)).artifact
        dataset = type("DatasetStub", (), {"rows": (row,), "artifact": artifact})()

        with self.assertRaisesRegex(DatasetValidationError, "Missing features"):
            DatasetValidator().validate(dataset, self.context())

    def test_missing_target_detection(self):
        row = DatasetRow(
            symbol="2330.TW",
            reference_date=date(2026, 1, 1),
            features=("TECH_SMA20_V1",),
            target="",
            metadata={
                "feature_checksums": ("feature_checksum_1",),
                "target_checksum": "target_checksum_1",
                "snapshot_id": self.context().snapshot_id,
            },
        )
        artifact = DatasetBuilder(self.context()).build((self.feature_artifact(),), (self.target_artifact(),)).artifact
        dataset = type("DatasetStub", (), {"rows": (row,), "artifact": artifact})()

        with self.assertRaisesRegex(DatasetValidationError, "Missing target"):
            DatasetValidator().validate(dataset, self.context())

    def test_duplicate_row_detection(self):
        with self.assertRaisesRegex(DatasetValidationError, "Duplicate dataset row"):
            DatasetBuilder(self.context()).build(
                (self.feature_artifact(),),
                (
                    self.target_artifact(),
                    self.target_artifact(checksum="target_checksum_2"),
                ),
            )

    def test_leakage_detection(self):
        result = DatasetBuilder(self.context()).build((self.feature_artifact(),), (self.target_artifact(),))
        row = DatasetRow(
            symbol=result.rows[0].symbol,
            reference_date=result.rows[0].reference_date,
            features=result.rows[0].features,
            target=result.rows[0].target,
            metadata={**result.rows[0].metadata, "feature_reference_date": date(2026, 1, 2)},
        )
        dataset = type("DatasetStub", (), {"rows": (row,), "artifact": result.artifact})()

        with self.assertRaisesRegex(DatasetValidationError, "date alignment failed"):
            DatasetValidator().validate_leakage(dataset)

    def test_dataset_split_interface_metadata(self):
        result = DatasetBuilder(self.context()).build((self.feature_artifact(),), (self.target_artifact(),))

        self.assertEqual(result.rows[0].metadata["split_policy"], "train_validation_oos_v1")

    def test_universe_consistency_metadata(self):
        result = DatasetBuilder(self.context()).build((self.feature_artifact(),), (self.target_artifact(),))

        self.assertEqual(result.rows[0].metadata["universe_id"], "frozen_twse_218")
        self.assertEqual(result.rows[0].metadata["universe_version"], "v1")

    def test_different_row_content_changes_checksum(self):
        builder = DatasetBuilder(self.context())
        first = builder.build((self.feature_artifact(checksum="feature_checksum_1"),), (self.target_artifact(),))
        second = builder.build((self.feature_artifact(checksum="feature_checksum_2"),), (self.target_artifact(),))

        self.assertNotEqual(first.artifact.checksum, second.artifact.checksum)

    def test_dataset_modules_do_not_import_existing_runtime_boundaries(self):
        dataset_source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "datasets").glob("*.py"))
        )

        forbidden_imports = (
            "live_data_store",
            "swing_scanner_service",
            "swing_scanner_pdf_export_service",
            "yfinance",
            "sqlite3",
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, dataset_source)


if __name__ == "__main__":
    unittest.main()
