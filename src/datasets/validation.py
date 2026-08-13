from datasets.dataset_context import DatasetContext


class DatasetValidationError(Exception):
    """Raised when dataset validation fails."""


class DatasetValidator:
    """Validation for metadata-only dataset build results."""

    def validate(self, dataset, context: DatasetContext) -> None:
        self.validate_feature_completeness(dataset)
        self.validate_target_completeness(dataset)
        self.validate_duplicate_rows(dataset)
        self.validate_feature_target_alignment(dataset)
        self.validate_leakage(dataset)
        self.validate_checksum(dataset)
        if dataset.artifact.snapshot_id != context.snapshot_id:
            raise DatasetValidationError("Dataset artifact snapshot_id mismatch.")

    def validate_feature_completeness(self, dataset) -> None:
        for row in dataset.rows:
            if not row.features:
                raise DatasetValidationError(f"Missing features for {row.symbol} {row.reference_date}.")
            if any(checksum is None for checksum in row.metadata.get("feature_checksums", ())):
                raise DatasetValidationError(f"Missing feature checksum for {row.symbol} {row.reference_date}.")

    def validate_target_completeness(self, dataset) -> None:
        for row in dataset.rows:
            if not row.target:
                raise DatasetValidationError(f"Missing target for {row.symbol} {row.reference_date}.")
            if row.metadata.get("target_checksum") is None:
                raise DatasetValidationError(f"Missing target checksum for {row.symbol} {row.reference_date}.")

    def validate_duplicate_rows(self, dataset) -> None:
        seen = set()
        for row in dataset.rows:
            key = (row.symbol, row.reference_date, row.target)
            if key in seen:
                raise DatasetValidationError(f"Duplicate dataset row: {row.symbol} {row.reference_date} {row.target}.")
            seen.add(key)

    def validate_feature_target_alignment(self, dataset) -> None:
        for row in dataset.rows:
            if row.metadata.get("snapshot_id") != dataset.artifact.snapshot_id:
                raise DatasetValidationError(f"Feature/target snapshot mismatch for {row.symbol} {row.reference_date}.")

    def validate_leakage(self, dataset) -> None:
        for row in dataset.rows:
            feature_reference_date = row.metadata.get("feature_reference_date", row.reference_date)
            if feature_reference_date != row.reference_date:
                raise DatasetValidationError(f"Feature/target date alignment failed for {row.symbol}.")

    def validate_checksum(self, dataset) -> None:
        if not dataset.artifact.checksum:
            raise DatasetValidationError("Dataset checksum is missing.")
