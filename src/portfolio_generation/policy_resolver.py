from dataclasses import dataclass

from risk import RiskDefinition
from risk import RiskRegistry
from risk import RiskRegistryError

from portfolio_generation.validation import PolicyResolverError


@dataclass(frozen=True)
class PolicyVersionResolution:
    """Exact-version policy metadata resolution."""

    version: str
    policy_type: str


class ExactVersionPolicyResolver:
    """Resolve known risk definitions and policy versions without latest/default fallback."""

    def __init__(
        self,
        *,
        risk_registry: RiskRegistry,
        allowed_risk_policy_versions: tuple[str, ...],
        allowed_monitoring_policy_versions: tuple[str, ...] = (),
    ):
        if not isinstance(risk_registry, RiskRegistry):
            raise PolicyResolverError("ExactVersionPolicyResolver requires RiskRegistry.")
        self.risk_registry = risk_registry
        self.allowed_risk_policy_versions = self._validate_versions(
            allowed_risk_policy_versions,
            "risk_policy",
        )
        self.allowed_monitoring_policy_versions = self._validate_versions(
            allowed_monitoring_policy_versions,
            "monitoring_policy",
            allow_empty=True,
        )

    def resolve_risk_definition(self, risk_id: str, version: str) -> RiskDefinition:
        if not risk_id or not version:
            raise PolicyResolverError("Risk definition resolution requires exact risk_id and version.")
        try:
            return self.risk_registry.get_risk(risk_id, version)
        except RiskRegistryError as exc:
            raise PolicyResolverError(str(exc)) from exc

    def resolve_risk_policy_version(self, version: str) -> PolicyVersionResolution:
        return self._resolve_allowed_version(version, self.allowed_risk_policy_versions, "risk_policy")

    def resolve_monitoring_policy_version(self, version: str) -> PolicyVersionResolution:
        return self._resolve_allowed_version(version, self.allowed_monitoring_policy_versions, "monitoring_policy")

    def _resolve_allowed_version(
        self,
        version: str,
        allowed_versions: tuple[str, ...],
        policy_type: str,
    ) -> PolicyVersionResolution:
        if not version:
            raise PolicyResolverError(f"{policy_type} version is required.")
        if version not in allowed_versions:
            raise PolicyResolverError(f"Unknown {policy_type} version: {version}")
        return PolicyVersionResolution(version=version, policy_type=policy_type)

    def _validate_versions(
        self,
        versions: tuple[str, ...],
        policy_type: str,
        *,
        allow_empty: bool = False,
    ) -> tuple[str, ...]:
        if not isinstance(versions, tuple):
            raise PolicyResolverError(f"{policy_type} versions must be a tuple.")
        if not allow_empty and not versions:
            raise PolicyResolverError(f"{policy_type} versions cannot be empty.")
        if any(not isinstance(version, str) or not version for version in versions):
            raise PolicyResolverError(f"{policy_type} versions must contain non-empty strings.")
        if len(set(versions)) != len(versions):
            raise PolicyResolverError(f"{policy_type} versions must be unique.")
        return tuple(versions)
