"""Research-scoped OOS contracts for technical risk methodology work."""

from risk_oos.aligned_dataset import AlignedTechnicalRiskOOSRow
from risk_oos.aligned_dataset import TARGET_MAE20
from risk_oos.aligned_dataset import TARGET_MAE60
from risk_oos.aligned_dataset import TECHNICAL_RISK_OOS_DATASET_BUILDER_VERSION
from risk_oos.aligned_dataset import TECHNICAL_RISK_OOS_DATASET_SCHEMA_VERSION
from risk_oos.aligned_dataset import TECHNICAL_RISK_V1_FEATURE_SET_ID
from risk_oos.aligned_dataset import TECHNICAL_RISK_V1_TARGET_IDENTITIES
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetBuilder
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetError
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetResult
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetSpec
from risk_oos.aligned_dataset import TechnicalRiskOOSExclusionReason
from risk_oos.aligned_dataset import TechnicalRiskOOSExclusionRecord
from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.aligned_dataset import TechnicalRiskOOSSplitSpec
from risk_oos.candidate_evaluator import TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1
from risk_oos.candidate_evaluator import TECH_RISK_CANDIDATE_EVALUATOR_V1
from risk_oos.candidate_evaluator import TECH_RISK_CONTINUOUS_MAE_METRIC_V1
from risk_oos.candidate_evaluator import TECH_RISK_LOW_REASON_V1
from risk_oos.candidate_evaluator import TECH_RISK_QUANTILE_NEAREST_RANK_V1
from risk_oos.candidate_evaluator import TechnicalRiskCandidateEvaluationError
from risk_oos.candidate_evaluator import TechnicalRiskCandidateEvaluationInput
from risk_oos.candidate_evaluator import TechnicalRiskCandidateEvaluationResult
from risk_oos.candidate_evaluator import TechnicalRiskCandidateEvaluator
from risk_oos.candidate_evaluator import TechnicalRiskCandidateRowEvaluation
from risk_oos.candidate_evaluator import TechnicalRiskMonotonicityResult
from risk_oos.candidate_evaluator import TechnicalRiskMonotonicityStatus
from risk_oos.candidate_evaluator import TechnicalRiskSeverityMAEMetrics
from risk_oos.historical_features import EXCLUSION_FEATURE_CALCULATION_FAILED
from risk_oos.historical_features import EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY
from risk_oos.historical_features import EXCLUSION_INVALID_PRICE
from risk_oos.historical_features import EXCLUSION_MISSING_AS_OF_CLOSE
from risk_oos.historical_features import HISTORICAL_RISK_FEATURE_SET_V1
from risk_oos.historical_features import HistoricalRiskFeatureExclusion
from risk_oos.historical_features import HistoricalRiskFeatureMaterializationContext
from risk_oos.historical_features import HistoricalRiskFeatureMaterializationError
from risk_oos.historical_features import HistoricalRiskFeatureMaterializationResult
from risk_oos.historical_features import HistoricalRiskFeatureMaterializer
from risk_oos.historical_features import HistoricalRiskFeatureObservation
from risk_oos.historical_features import HistoricalRiskFeatureStatus
from risk_oos.rule_candidates import ALLOWED_CANDIDATE_SEVERITIES_V1
from risk_oos.rule_candidates import ALLOWED_PREDICATES_V1
from risk_oos.rule_candidates import FIXED_TECH_RISK_DECIMAL_CONTEXT
from risk_oos.rule_candidates import REQUIRED_THRESHOLD_DIMENSIONS_V1
from risk_oos.rule_candidates import TECH_RISK_DECIMAL_CONTEXT_PRECISION_V1
from risk_oos.rule_candidates import TECH_RISK_DECIMAL_CONTEXT_ROUNDING_V1
from risk_oos.rule_candidates import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos.rule_candidates import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_oos.rule_candidates import TECH_RISK_EVIDENCE_VOCABULARY_V1
from risk_oos.rule_candidates import TECH_RISK_NUMERIC_REPRESENTATION_V1
from risk_oos.rule_candidates import TECH_RISK_TRIGGER_VOCABULARY_V1
from risk_oos.rule_candidates import TechnicalRiskCandidateFamily
from risk_oos.rule_candidates import TechnicalRiskCandidateRule
from risk_oos.rule_candidates import TechnicalRiskCandidateSeverity
from risk_oos.rule_candidates import TechnicalRiskDerivedEvidence
from risk_oos.rule_candidates import TechnicalRiskPredicateId
from risk_oos.rule_candidates import TechnicalRiskPredicateState
from risk_oos.rule_candidates import TechnicalRiskReasonCode
from risk_oos.rule_candidates import TechnicalRiskRuleCandidateError
from risk_oos.rule_candidates import TechnicalRiskRuleCandidateSpec
from risk_oos.rule_candidates import TechnicalRiskThresholdDimension
from risk_oos.rule_candidates import TechnicalRiskThresholdDimensionId
from risk_oos.rule_candidates import TechnicalRiskThresholdOperator
from risk_oos.rule_candidates import TechnicalRiskThresholdSet
from risk_oos.rule_candidates import derive_technical_risk_evidence
from risk_oos.rule_candidates import evaluate_technical_risk_predicates
from risk_oos.rule_candidates import technical_risk_candidate_a_spec
from risk_oos.rule_candidates import technical_risk_candidate_b_spec
from risk_oos.rule_candidates import technical_risk_candidate_c_spec
from risk_oos.rule_candidates import technical_risk_candidate_d_spec

__all__ = [
    "AlignedTechnicalRiskOOSRow",
    "ALLOWED_CANDIDATE_SEVERITIES_V1",
    "ALLOWED_PREDICATES_V1",
    "EXCLUSION_FEATURE_CALCULATION_FAILED",
    "EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY",
    "EXCLUSION_INVALID_PRICE",
    "EXCLUSION_MISSING_AS_OF_CLOSE",
    "FIXED_TECH_RISK_DECIMAL_CONTEXT",
    "HISTORICAL_RISK_FEATURE_SET_V1",
    "HistoricalRiskFeatureExclusion",
    "HistoricalRiskFeatureMaterializationContext",
    "HistoricalRiskFeatureMaterializationError",
    "HistoricalRiskFeatureMaterializationResult",
    "HistoricalRiskFeatureMaterializer",
    "HistoricalRiskFeatureObservation",
    "HistoricalRiskFeatureStatus",
    "REQUIRED_THRESHOLD_DIMENSIONS_V1",
    "TARGET_MAE20",
    "TARGET_MAE60",
    "TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1",
    "TECH_RISK_CANDIDATE_EVALUATOR_V1",
    "TECH_RISK_CONTINUOUS_MAE_METRIC_V1",
    "TECH_RISK_DECIMAL_CONTEXT_PRECISION_V1",
    "TECH_RISK_DECIMAL_CONTEXT_ROUNDING_V1",
    "TECH_RISK_DECIMAL_CONTEXT_V1",
    "TECHNICAL_RISK_OOS_DATASET_BUILDER_VERSION",
    "TECHNICAL_RISK_OOS_DATASET_SCHEMA_VERSION",
    "TECHNICAL_RISK_V1_FEATURE_SET_ID",
    "TECHNICAL_RISK_V1_TARGET_IDENTITIES",
    "TECH_RISK_DERIVED_EVIDENCE_V1",
    "TECH_RISK_EVIDENCE_VOCABULARY_V1",
    "TECH_RISK_LOW_REASON_V1",
    "TECH_RISK_NUMERIC_REPRESENTATION_V1",
    "TECH_RISK_QUANTILE_NEAREST_RANK_V1",
    "TECH_RISK_TRIGGER_VOCABULARY_V1",
    "TechnicalRiskCandidateFamily",
    "TechnicalRiskCandidateEvaluationError",
    "TechnicalRiskCandidateEvaluationInput",
    "TechnicalRiskCandidateEvaluationResult",
    "TechnicalRiskCandidateEvaluator",
    "TechnicalRiskCandidateRule",
    "TechnicalRiskCandidateRowEvaluation",
    "TechnicalRiskCandidateSeverity",
    "TechnicalRiskDerivedEvidence",
    "TechnicalRiskMonotonicityResult",
    "TechnicalRiskMonotonicityStatus",
    "TechnicalRiskOOSDatasetBuilder",
    "TechnicalRiskOOSDatasetError",
    "TechnicalRiskOOSDatasetResult",
    "TechnicalRiskOOSDatasetSpec",
    "TechnicalRiskOOSExclusionReason",
    "TechnicalRiskOOSExclusionRecord",
    "TechnicalRiskOOSSplitRole",
    "TechnicalRiskOOSSplitSpec",
    "TechnicalRiskPredicateId",
    "TechnicalRiskPredicateState",
    "TechnicalRiskReasonCode",
    "TechnicalRiskRuleCandidateError",
    "TechnicalRiskRuleCandidateSpec",
    "TechnicalRiskSeverityMAEMetrics",
    "TechnicalRiskThresholdDimension",
    "TechnicalRiskThresholdDimensionId",
    "TechnicalRiskThresholdOperator",
    "TechnicalRiskThresholdSet",
    "derive_technical_risk_evidence",
    "evaluate_technical_risk_predicates",
    "technical_risk_candidate_a_spec",
    "technical_risk_candidate_b_spec",
    "technical_risk_candidate_c_spec",
    "technical_risk_candidate_d_spec",
]
