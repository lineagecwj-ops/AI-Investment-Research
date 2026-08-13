from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from risk import RiskCategory
from risk_evaluation.evaluation_input import RiskSignalProductionInput
from risk_evaluation.validation import RiskEvaluationPolicyError
from risk_evaluation.validation import normalize_categories
from risk_evaluation.validation import normalize_string_mapping
from risk_evaluation.validation import normalize_text_tuple
from risk_evaluation.validation import require_non_empty_text


class MissingDataPolicy(StrEnum):
    """Supported missing-data behavior for production risk evaluation."""

    FAIL_EVALUATION = "FAIL_EVALUATION"


@dataclass(frozen=True)
class RiskEvaluationPolicy:
    """First-class immutable policy contract for risk signal production."""

    policy_id: str
    version: str
    enabled_categories: tuple[RiskCategory | str, ...]
    required_feature_ids: tuple[str, ...]
    category_producer_versions: Mapping[RiskCategory | str, str]
    severity_rules: Mapping[str, str]
    missing_data_policy: MissingDataPolicy | str
    calculation_metadata: Mapping[str, str] | None = None

    def __post_init__(self):
        require_non_empty_text(self.policy_id, "policy_id", RiskEvaluationPolicyError)
        require_non_empty_text(self.version, "version", RiskEvaluationPolicyError)
        enabled_categories = normalize_categories(self.enabled_categories, "enabled_categories")
        required_feature_ids = normalize_text_tuple(
            self.required_feature_ids,
            "required_feature_ids",
            RiskEvaluationPolicyError,
        )
        producer_versions = self._normalize_category_producer_versions(enabled_categories)
        severity_rules = normalize_string_mapping(dict(self.severity_rules), "severity_rules", allow_empty=True)
        calculation_metadata = normalize_string_mapping(
            dict(self.calculation_metadata or {}),
            "calculation_metadata",
            allow_empty=True,
        )
        try:
            missing_data_policy = MissingDataPolicy(self.missing_data_policy)
        except ValueError as exc:
            raise RiskEvaluationPolicyError(f"Unsupported missing_data_policy: {self.missing_data_policy}") from exc

        object.__setattr__(self, "enabled_categories", enabled_categories)
        object.__setattr__(self, "required_feature_ids", required_feature_ids)
        object.__setattr__(self, "category_producer_versions", MappingProxyType(producer_versions))
        object.__setattr__(self, "severity_rules", MappingProxyType(severity_rules))
        object.__setattr__(self, "missing_data_policy", missing_data_policy)
        object.__setattr__(self, "calculation_metadata", MappingProxyType(calculation_metadata))

    @property
    def identity(self) -> tuple[str, str]:
        return self.policy_id, self.version

    def validate_required_features(self, input: RiskSignalProductionInput) -> None:
        if not isinstance(input, RiskSignalProductionInput):
            raise RiskEvaluationPolicyError("RiskEvaluationPolicy requires RiskSignalProductionInput.")
        missing = tuple(feature_id for feature_id in self.required_feature_ids if feature_id not in input.feature_ids)
        if missing and self.missing_data_policy == MissingDataPolicy.FAIL_EVALUATION:
            raise RiskEvaluationPolicyError(f"Required feature missing: {', '.join(missing)}")

    def _normalize_category_producer_versions(self, enabled_categories: tuple[RiskCategory, ...]) -> dict[RiskCategory, str]:
        if not isinstance(self.category_producer_versions, Mapping):
            raise RiskEvaluationPolicyError("category_producer_versions must be a mapping.")
        normalized: dict[RiskCategory, str] = {}
        for key, value in self.category_producer_versions.items():
            try:
                category = RiskCategory(key)
            except ValueError as exc:
                raise RiskEvaluationPolicyError(f"Unknown risk category: {key}") from exc
            if category not in enabled_categories:
                raise RiskEvaluationPolicyError("category_producer_versions includes a disabled category.")
            if not isinstance(value, str) or not value:
                raise RiskEvaluationPolicyError("category_producer_versions values must be non-empty strings.")
            normalized[category] = value
        missing_categories = tuple(category.value for category in enabled_categories if category not in normalized)
        if missing_categories:
            raise RiskEvaluationPolicyError(f"Missing producer version for category: {', '.join(missing_categories)}")
        return dict(sorted(normalized.items(), key=lambda item: item[0].value))


class RiskEvaluationPolicyRegistry:
    """Minimal exact-version policy registry with fail-closed lookup."""

    def __init__(self, policies: tuple[RiskEvaluationPolicy, ...] = ()):
        self._policies: dict[tuple[str, str], RiskEvaluationPolicy] = {}
        for policy in policies:
            self.register(policy)

    def register(self, policy: RiskEvaluationPolicy) -> None:
        if not isinstance(policy, RiskEvaluationPolicy):
            raise RiskEvaluationPolicyError("RiskEvaluationPolicyRegistry requires RiskEvaluationPolicy.")
        if policy.identity in self._policies:
            raise RiskEvaluationPolicyError(f"RiskEvaluationPolicy already registered: {policy.policy_id}:{policy.version}")
        self._policies[policy.identity] = policy

    def resolve(self, policy_id: str, version: str) -> RiskEvaluationPolicy:
        require_non_empty_text(policy_id, "policy_id", RiskEvaluationPolicyError)
        require_non_empty_text(version, "version", RiskEvaluationPolicyError)
        identity = (policy_id, version)
        if identity not in self._policies:
            raise RiskEvaluationPolicyError(f"Unknown risk evaluation policy version: {policy_id}:{version}")
        return self._policies[identity]
