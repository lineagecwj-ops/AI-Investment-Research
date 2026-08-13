from dataclasses import dataclass

from risk.risk_definition import RiskDefinition


class RiskRegistryError(Exception):
    """Raised when risk registry operations are invalid."""


@dataclass(frozen=True)
class _RegistryKey:
    risk_id: str
    version: str


class RiskRegistry:
    """In-memory registry for deterministic risk definitions."""

    def __init__(self):
        self._definitions: dict[_RegistryKey, RiskDefinition] = {}

    def register(self, definition: RiskDefinition) -> None:
        key = _RegistryKey(definition.risk_id, definition.version)
        if key in self._definitions:
            raise RiskRegistryError(f"Risk already registered: {definition.risk_id} version {definition.version}")
        self._definitions[key] = definition

    def get_risk(self, risk_id: str, version: str) -> RiskDefinition:
        key = _RegistryKey(risk_id, version)
        try:
            return self._definitions[key]
        except KeyError as exc:
            raise RiskRegistryError(f"Risk definition missing: {risk_id} version {version}") from exc

    def list_risks(self) -> tuple[str, ...]:
        return tuple(
            f"{key.risk_id}:{key.version}"
            for key in sorted(self._definitions.keys(), key=lambda item: (item.risk_id, item.version))
        )
