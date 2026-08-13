from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import time

from features.feature_artifact import FeatureArtifact
from targets.target_artifact import TargetArtifact

from datasets.checksum import DatasetChecksumGenerator
from datasets.dataset_artifact import DatasetArtifact
from datasets.dataset_context import DatasetContext
from datasets.validation import DatasetValidationError
from datasets.validation import DatasetValidator


@dataclass(frozen=True)
class DatasetRow:
    symbol: str
    reference_date: object
    features: tuple[str, ...]
    target: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class DatasetBuildResult:
    dataset_id: str
    rows: tuple[DatasetRow, ...]
    artifact: DatasetArtifact


class DatasetBuilder:
    """Builds metadata-only dataset rows from feature and target artifacts."""

    def __init__(
        self,
        context: DatasetContext,
        validator: DatasetValidator | None = None,
        checksum_generator: DatasetChecksumGenerator | None = None,
    ):
        self.context = context
        self.validator = validator or DatasetValidator()
        self.checksum_generator = checksum_generator or DatasetChecksumGenerator()

    def build(
        self,
        feature_artifacts: tuple[FeatureArtifact, ...],
        target_artifacts: tuple[TargetArtifact, ...],
    ) -> DatasetBuildResult:
        rows = tuple(self._row_for_target(feature_artifacts, target) for target in target_artifacts)
        checksum = self.checksum_generator.generate(self.context, rows)
        artifact = DatasetArtifact(
            dataset_id=self.context.dataset_id,
            dataset_version=self.context.feature_set_version,
            snapshot_id=self.context.snapshot_id,
            feature_versions=tuple(artifact.feature_version for artifact in feature_artifacts),
            target_version=self.context.target_version,
            row_count=len(rows),
            created_at=self._created_at(target_artifacts),
            checksum=checksum,
            validation_status="PENDING",
        )
        result = DatasetBuildResult(dataset_id=self.context.dataset_id, rows=rows, artifact=artifact)
        self.validate(result)
        return DatasetBuildResult(
            dataset_id=result.dataset_id,
            rows=result.rows,
            artifact=DatasetArtifact(
                dataset_id=artifact.dataset_id,
                dataset_version=artifact.dataset_version,
                snapshot_id=artifact.snapshot_id,
                feature_versions=artifact.feature_versions,
                target_version=artifact.target_version,
                row_count=artifact.row_count,
                created_at=artifact.created_at,
                checksum=artifact.checksum,
                validation_status="PASS",
            ),
        )

    def validate(self, dataset: DatasetBuildResult) -> None:
        try:
            self.validator.validate(dataset, self.context)
        except DatasetValidationError:
            raise

    def generate_artifact(self, dataset: DatasetBuildResult) -> DatasetArtifact:
        self.validate(dataset)
        return dataset.artifact

    def _row_for_target(
        self,
        feature_artifacts: tuple[FeatureArtifact, ...],
        target_artifact: TargetArtifact,
    ) -> DatasetRow:
        return DatasetRow(
            symbol=target_artifact.symbol,
            reference_date=target_artifact.reference_date,
            features=tuple(artifact.feature_id for artifact in feature_artifacts),
            target=target_artifact.target_id,
            metadata={
                "feature_artifact_ids": tuple(artifact.calculation_id for artifact in feature_artifacts),
                "feature_checksums": tuple(artifact.checksum for artifact in feature_artifacts),
                "target_calculation_id": target_artifact.calculation_id,
                "target_checksum": target_artifact.checksum,
                "target_value": target_artifact.target_value,
                "snapshot_id": self.context.snapshot_id,
                "universe_id": self.context.universe_id,
                "universe_version": self.context.universe_version,
                "split_policy": self.context.split_policy,
            },
        )

    def _created_at(self, target_artifacts: tuple[TargetArtifact, ...]) -> datetime:
        if target_artifacts:
            return datetime.combine(target_artifacts[0].reference_date, time.min, tzinfo=UTC)
        return datetime.fromtimestamp(0, tz=UTC)
