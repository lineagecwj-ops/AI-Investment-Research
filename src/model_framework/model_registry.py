from dataclasses import dataclass

from model_framework.model_definition import ModelDefinition


class ModelRegistryError(Exception):
    """Raised when model registry operations are invalid."""


@dataclass(frozen=True)
class _RegistryKey:
    model_id: str
    version: str


class ModelRegistry:
    """In-memory registry for model definitions."""

    def __init__(self):
        self._definitions: dict[_RegistryKey, ModelDefinition] = {}

    def register(self, definition: ModelDefinition) -> None:
        key = _RegistryKey(definition.model_id, definition.version)
        if key in self._definitions:
            raise ModelRegistryError(f"Model already registered: {definition.model_id} version {definition.version}")
        self._definitions[key] = definition

    def get_model(self, model_id: str, version: str) -> ModelDefinition:
        key = _RegistryKey(model_id, version)
        try:
            return self._definitions[key]
        except KeyError as exc:
            raise ModelRegistryError(f"Model not registered: {model_id} version {version}") from exc

    def list_models(self) -> tuple[str, ...]:
        return tuple(
            f"{key.model_id}:{key.version}"
            for key in sorted(self._definitions.keys(), key=lambda item: (item.model_id, item.version))
        )
