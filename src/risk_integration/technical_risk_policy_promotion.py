from risk import RiskSeverity
from risk_evaluation import PRODUCTION_TECHNICAL_RISK_POLICY_V1
from risk_evaluation import TECH_RISK_REASON_MAPPING_V1
from risk_evaluation import TECH_RISK_REQUIRED_FEATURE_IDS_V1
from risk_evaluation import TECH_RISK_SEVERITY_MAPPING_V1
from risk_evaluation import ProductionTechnicalRiskPolicy
from risk_evaluation import ProductionTechnicalRiskPredicateId
from risk_evaluation import ProductionTechnicalRiskReasonCode
from risk_evaluation import ProductionTechnicalRiskRule
from risk_evaluation import ProductionTechnicalRiskThresholdDimension
from risk_evaluation import ProductionTechnicalRiskThresholdDimensionId
from risk_evaluation import ProductionTechnicalRiskThresholdOperator
from risk_evaluation import RiskEvaluationPolicyError
from risk_oos import TechnicalRiskPolicyFreezeArtifact
from risk_oos import TechnicalRiskPolicyFreezeReasonCode
from risk_oos import TechnicalRiskPolicyFreezeStatus
from risk_oos import TechnicalRiskRuleCandidateSpec
from risk_oos import TechnicalRiskThresholdSet


class TechnicalRiskPolicyPromotionError(ValueError):
    """Raised when a research freeze cannot be promoted to a production policy."""


def promote_research_freeze_to_production_policy(
    *,
    research_freeze: TechnicalRiskPolicyFreezeArtifact,
    candidate: TechnicalRiskRuleCandidateSpec,
    threshold_set: TechnicalRiskThresholdSet,
    policy_version: str = PRODUCTION_TECHNICAL_RISK_POLICY_V1,
) -> ProductionTechnicalRiskPolicy:
    """Convert one frozen research methodology into one immutable production policy."""

    _validate_inputs(research_freeze, candidate, threshold_set)
    _validate_freeze(research_freeze)
    _validate_candidate_match(research_freeze, candidate)
    _validate_threshold_match(research_freeze, threshold_set)
    try:
        return ProductionTechnicalRiskPolicy(
            policy_id=None,
            policy_version=policy_version,
            policy_checksum=None,
            technical_policy_version=research_freeze.technical_policy_version,
            source_research_freeze_id=research_freeze.freeze_id,
            source_research_freeze_checksum=research_freeze.freeze_checksum,
            candidate_id=candidate.policy_candidate_id,
            candidate_version=candidate.candidate_version,
            candidate_structural_checksum=candidate.candidate_structural_checksum,
            rules=tuple(_promote_rule(rule) for rule in candidate.rules),
            threshold_set_id=threshold_set.threshold_set_id,
            threshold_set_version=threshold_set.threshold_set_version,
            threshold_set_checksum=threshold_set.threshold_set_checksum,
            threshold_dimensions=tuple(_promote_threshold_dimension(dimension) for dimension in threshold_set.dimensions),
            required_feature_ids=TECH_RISK_REQUIRED_FEATURE_IDS_V1,
            derived_evidence_version=research_freeze.derived_evidence_version,
            numeric_context_version=research_freeze.numeric_context_version,
            severity_mapping_version=TECH_RISK_SEVERITY_MAPPING_V1,
            reason_mapping_version=TECH_RISK_REASON_MAPPING_V1,
        )
    except RiskEvaluationPolicyError as exc:
        raise TechnicalRiskPolicyPromotionError(str(exc)) from exc


def _validate_inputs(
    research_freeze: TechnicalRiskPolicyFreezeArtifact,
    candidate: TechnicalRiskRuleCandidateSpec,
    threshold_set: TechnicalRiskThresholdSet,
) -> None:
    if not isinstance(research_freeze, TechnicalRiskPolicyFreezeArtifact):
        raise TechnicalRiskPolicyPromotionError("Promotion requires a TechnicalRiskPolicyFreezeArtifact.")
    if not isinstance(candidate, TechnicalRiskRuleCandidateSpec):
        raise TechnicalRiskPolicyPromotionError("Promotion requires a TechnicalRiskRuleCandidateSpec.")
    if not isinstance(threshold_set, TechnicalRiskThresholdSet):
        raise TechnicalRiskPolicyPromotionError("Promotion requires a TechnicalRiskThresholdSet.")


def _validate_freeze(research_freeze: TechnicalRiskPolicyFreezeArtifact) -> None:
    if research_freeze.freeze_status != TechnicalRiskPolicyFreezeStatus.FROZEN:
        raise TechnicalRiskPolicyPromotionError("Production promotion requires a FROZEN research policy freeze.")
    if TechnicalRiskPolicyFreezeReasonCode.RESEARCH_POLICY_FROZEN not in research_freeze.structured_freeze_reason_codes:
        raise TechnicalRiskPolicyPromotionError("Production promotion requires RESEARCH_POLICY_FROZEN reason.")
    if not research_freeze.freeze_id or not research_freeze.freeze_checksum:
        raise TechnicalRiskPolicyPromotionError("Production promotion requires freeze id and checksum.")


def _validate_candidate_match(
    research_freeze: TechnicalRiskPolicyFreezeArtifact,
    candidate: TechnicalRiskRuleCandidateSpec,
) -> None:
    if candidate.policy_candidate_id != research_freeze.candidate_id:
        raise TechnicalRiskPolicyPromotionError("candidate id mismatch.")
    if candidate.candidate_version != research_freeze.candidate_version:
        raise TechnicalRiskPolicyPromotionError("candidate version mismatch.")
    if candidate.candidate_structural_checksum != research_freeze.candidate_structural_checksum:
        raise TechnicalRiskPolicyPromotionError("candidate structural checksum mismatch.")
    if candidate.derived_evidence_version != research_freeze.derived_evidence_version:
        raise TechnicalRiskPolicyPromotionError("candidate derived_evidence_version mismatch.")
    if tuple(sorted(candidate.required_feature_ids)) != TECH_RISK_REQUIRED_FEATURE_IDS_V1:
        raise TechnicalRiskPolicyPromotionError("candidate required feature set mismatch.")


def _validate_threshold_match(
    research_freeze: TechnicalRiskPolicyFreezeArtifact,
    threshold_set: TechnicalRiskThresholdSet,
) -> None:
    if threshold_set.threshold_set_id != research_freeze.threshold_set_id:
        raise TechnicalRiskPolicyPromotionError("threshold id mismatch.")
    if threshold_set.threshold_set_version != research_freeze.threshold_set_version:
        raise TechnicalRiskPolicyPromotionError("threshold version mismatch.")
    if threshold_set.threshold_set_checksum != research_freeze.threshold_set_checksum:
        raise TechnicalRiskPolicyPromotionError("threshold checksum mismatch.")


def _promote_rule(rule) -> ProductionTechnicalRiskRule:
    return ProductionTechnicalRiskRule(
        rule_id=rule.rule_id,
        rule_priority=rule.rule_priority,
        severity=_map_severity(rule.severity),
        required_predicates=tuple(_map_predicate(predicate) for predicate in rule.required_predicates),
        optional_confirmation_predicates=tuple(_map_predicate(predicate) for predicate in rule.optional_confirmation_predicates),
        reason_codes=tuple(_map_reason(reason) for reason in rule.reason_codes),
    )


def _promote_threshold_dimension(dimension) -> ProductionTechnicalRiskThresholdDimension:
    return ProductionTechnicalRiskThresholdDimension(
        dimension_id=_map_dimension(dimension.dimension_id),
        operator=_map_operator(dimension.operator),
        canonical_value=dimension.canonical_value,
    )


def _map_severity(value) -> RiskSeverity:
    try:
        severity = RiskSeverity(value.value)
    except (AttributeError, ValueError) as exc:
        raise TechnicalRiskPolicyPromotionError("Unsupported Technical Risk candidate severity.") from exc
    if severity == RiskSeverity.CRITICAL:
        raise TechnicalRiskPolicyPromotionError("Technical Risk v1 cannot promote CRITICAL severity.")
    return severity


def _map_predicate(value) -> ProductionTechnicalRiskPredicateId:
    try:
        return ProductionTechnicalRiskPredicateId(value.value)
    except (AttributeError, ValueError) as exc:
        raise TechnicalRiskPolicyPromotionError("Unsupported Technical Risk predicate.") from exc


def _map_reason(value) -> ProductionTechnicalRiskReasonCode:
    try:
        return ProductionTechnicalRiskReasonCode(value.value)
    except (AttributeError, ValueError) as exc:
        raise TechnicalRiskPolicyPromotionError("Unsupported Technical Risk reason code.") from exc


def _map_dimension(value) -> ProductionTechnicalRiskThresholdDimensionId:
    try:
        return ProductionTechnicalRiskThresholdDimensionId(value.value)
    except (AttributeError, ValueError) as exc:
        raise TechnicalRiskPolicyPromotionError("Unsupported Technical Risk threshold dimension.") from exc


def _map_operator(value) -> ProductionTechnicalRiskThresholdOperator:
    try:
        return ProductionTechnicalRiskThresholdOperator(value.value)
    except (AttributeError, ValueError) as exc:
        raise TechnicalRiskPolicyPromotionError("Unsupported Technical Risk threshold operator.") from exc
