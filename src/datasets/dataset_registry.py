from dataclasses import dataclass

from datasets.dataset_definition import DatasetDefinition


class DatasetRegistryError(Exception):
    """Raised when dataset registry operations are invalid."""


@dataclass(frozen=True)
class _RegistryKey:
    dataset_id: str
    dataset_version: str


class DatasetRegistry:
    """In-memory registry for dataset definitions."""

    def __init__(self):
        self._definitions: dict[_RegistryKey, DatasetDefinition] = {}

    def register(self, definition: DatasetDefinition) -> None:
        key = _RegistryKey(definition.dataset_id, definition.dataset_version)
        if key in self._definitions:
            raise DatasetRegistryError(
                f"Dataset definition already registered: {definition.dataset_id} version {definition.dataset_version}"
            )
        self._definitions[key] = definition

    def get_definition(self, dataset_id: str, dataset_version: str) -> DatasetDefinition:
        key = _RegistryKey(dataset_id, dataset_version)
        try:
            return self._definitions[key]
        except KeyError as exc:
            raise DatasetRegistryError(f"Dataset definition not registered: {dataset_id} version {dataset_version}") from exc

    def list_datasets(self) -> tuple[str, ...]:
        return tuple(
            f"{key.dataset_id}:{key.dataset_version}"
            for key in sorted(self._definitions.keys(), key=lambda item: (item.dataset_id, item.dataset_version))
        )
