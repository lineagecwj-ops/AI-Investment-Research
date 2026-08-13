from dataclasses import dataclass
from typing import Iterable

from targets.target_generator import TargetGenerator


class TargetRegistryError(Exception):
    """Raised when target registry operations are invalid."""


@dataclass(frozen=True)
class _RegistryKey:
    target_id: str
    version: str


class TargetRegistry:
    """In-memory registry for target generators."""

    def __init__(self):
        self._generators: dict[_RegistryKey, TargetGenerator] = {}

    def register(self, generator: TargetGenerator) -> None:
        definition = generator.get_definition()
        key = _RegistryKey(definition.target_id, definition.version)
        if key in self._generators:
            raise TargetRegistryError(
                f"Target generator already registered: {definition.target_id} version {definition.version}"
            )
        self._generators[key] = generator

    def get_generator(self, target_id: str, version: str) -> TargetGenerator:
        key = _RegistryKey(target_id, version)
        try:
            return self._generators[key]
        except KeyError as exc:
            raise TargetRegistryError(f"Target generator not registered: {target_id} version {version}") from exc

    def list_targets(self) -> tuple[str, ...]:
        return tuple(
            f"{key.target_id}:{key.version}"
            for key in sorted(self._generators.keys(), key=lambda item: (item.target_id, item.version))
        )

    def register_many(self, generators: Iterable[TargetGenerator]) -> None:
        for generator in generators:
            self.register(generator)
