from dataclasses import dataclass
from typing import Iterable

from features.feature_calculator import FeatureCalculator


class FeatureRegistryError(Exception):
    """Raised when feature registry operations are invalid."""


@dataclass(frozen=True)
class _RegistryKey:
    feature_id: str
    version: str


class FeatureRegistry:
    """In-memory registry for future feature calculators."""

    def __init__(self):
        self._calculators: dict[_RegistryKey, FeatureCalculator] = {}

    def register(self, calculator: FeatureCalculator) -> None:
        definition = calculator.get_definition()
        key = _RegistryKey(definition.feature_id, definition.version)
        if key in self._calculators:
            raise FeatureRegistryError(
                f"Feature calculator already registered: {definition.feature_id} version {definition.version}"
            )
        self._calculators[key] = calculator

    def get_calculator(self, feature_id: str, version: str) -> FeatureCalculator:
        key = _RegistryKey(feature_id, version)
        try:
            return self._calculators[key]
        except KeyError as exc:
            raise FeatureRegistryError(f"Feature calculator not registered: {feature_id} version {version}") from exc

    def list_features(self) -> tuple[str, ...]:
        return tuple(
            f"{key.feature_id}:{key.version}"
            for key in sorted(self._calculators.keys(), key=lambda item: (item.feature_id, item.version))
        )

    def register_many(self, calculators: Iterable[FeatureCalculator]) -> None:
        for calculator in calculators:
            self.register(calculator)
