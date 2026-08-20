from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from decimal import InvalidOperation
from decimal import localcontext
from enum import StrEnum
import hashlib
import json
from numbers import Real
from types import MappingProxyType
from typing import Mapping

from risk_oos.aligned_dataset import AlignedTechnicalRiskOOSRow
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetResult
from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.rule_candidates import ALLOWED_CANDIDATE_SEVERITIES_V1
from risk_oos.rule_candidates import FIXED_TECH_RISK_DECIMAL_CONTEXT
from risk_oos.rule_candidates import REQUIRED_THRESHOLD_DIMENSIONS_V1
from risk_oos.rule_candidates import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos.rule_candidates import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_oos.rule_candidates import TECH_RISK_NUMERIC_REPRESENTATION_V1
from risk_oos.rule_candidates import TechnicalRiskCandidateRule
from risk_oos.rule_candidates import TechnicalRiskCandidateSeverity
from risk_oos.rule_candidates import TechnicalRiskDerivedEvidence
from risk_oos.rule_candidates import TechnicalRiskPredicateId
from risk_oos.rule_candidates import TechnicalRiskPredicateState
from risk_oos.rule_candidates import TechnicalRiskReasonCode
from risk_oos.rule_candidates import TechnicalRiskRuleCandidateError
from risk_oos.rule_candidates import TechnicalRiskRuleCandidateSpec
from risk_oos.rule_candidates import TechnicalRiskThresholdDimensionId
from risk_oos.rule_candidates import TechnicalRiskThresholdOperator
from risk_oos.rule_candidates import TechnicalRiskThresholdSet
from risk_oos.rule_candidates import derive_technical_risk_evidence
from risk_oos.rule_candidates import evaluate_technical_risk_predicates


TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1 = "TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1"
TECH_RISK_CANDIDATE_EVALUATOR_V1 = "TECH_RISK_CANDIDATE_EVALUATOR_V1"
TECH_RISK_CONTINUOUS_MAE_METRIC_V1 = "TECH_RISK_CONTINUOUS_MAE_METRIC_V1"
TECH_RISK_QUANTILE_NEAREST_RANK_V1 = "TECH_RISK_QUANTILE_NEAREST_RANK_V1"
TECH_RISK_LOW_REASON_V1 = "NO_ELEVATED_TECHNICAL_DOWNSIDE_EVIDENCE"
_PREDICATE_ORDER = (
    TechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS,
    TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
    TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
    TechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,
)


class TechnicalRiskCandidateEvaluationError(Exception):
    """Raised when a Technical Risk candidate evaluation cannot be trusted."""


class TechnicalRiskMonotonicityStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    NOT_EVALUABLE = "NOT_EVALUABLE"


@dataclass(frozen=True)
class TechnicalRiskCandidateEvaluationInput:
    """Integrity echo for one frozen dataset, one candidate, and one threshold set."""

    evaluation_input_version: str
    dataset_id: str
    dataset_checksum: str
    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str
    threshold_set_id: str
    threshold_set_version: str
    threshold_set_checksum: str
    derived_evidence_version: str
    evaluator_version: str
    metric_version: str
    quantile_version: str
    numeric_context_version: str
    allowed_split_roles: tuple[TechnicalRiskOOSSplitRole, ...]

    def __post_init__(self):
        _require_version(self.evaluation_input_version, TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1, "evaluation_input_version")
        _require_text(self.dataset_id, "dataset_id")
        _require_text(self.dataset_checksum, "dataset_checksum")
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.candidate_version, "candidate_version")
        _require_text(self.candidate_structural_checksum, "candidate_structural_checksum")
        _require_text(self.threshold_set_id, "threshold_set_id")
        _require_text(self.threshold_set_version, "threshold_set_version")
        _require_text(self.threshold_set_checksum, "threshold_set_checksum")
        _require_version(self.derived_evidence_version, TECH_RISK_DERIVED_EVIDENCE_V1, "derived_evidence_version")
        _require_version(self.evaluator_version, TECH_RISK_CANDIDATE_EVALUATOR_V1, "evaluator_version")
        _require_version(self.metric_version, TECH_RISK_CONTINUOUS_MAE_METRIC_V1, "metric_version")
        _require_version(self.quantile_version, TECH_RISK_QUANTILE_NEAREST_RANK_V1, "quantile_version")
        _require_version(self.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1, "numeric_context_version")
        roles = _canonical_split_roles(self.allowed_split_roles)
        object.__setattr__(self, "allowed_split_roles", roles)


@dataclass(frozen=True)
class TechnicalRiskCandidateRowEvaluation:
    """Deterministic severity assignment and trace for one aligned OOS row."""

    row_id: str
    symbol: str
    evaluation_date: date
    split_id: str
    split_role: TechnicalRiskOOSSplitRole
    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str
    threshold_set_id: str
    threshold_set_version: str
    threshold_set_checksum: str
    derived_evidence_version: str
    close_vs_sma20: Decimal
    close_vs_sma60: Decimal
    relative_sma_spread: Decimal
    predicate_states: tuple[TechnicalRiskPredicateState, ...]
    severity: TechnicalRiskCandidateSeverity
    matched_rule_id: str | None
    reason_codes: tuple[str, ...]
    mae20_value: Decimal
    mae60_value: Decimal
    evaluation_version: str
    calculation_id: str

    def __post_init__(self):
        _require_text(self.row_id, "row_id")
        _require_text(self.symbol, "symbol")
        if not isinstance(self.evaluation_date, date):
            raise TechnicalRiskCandidateEvaluationError("evaluation_date must be a date.")
        _require_text(self.split_id, "split_id")
        if not isinstance(self.split_role, TechnicalRiskOOSSplitRole):
            object.__setattr__(self, "split_role", TechnicalRiskOOSSplitRole(self.split_role))
        if not isinstance(self.severity, TechnicalRiskCandidateSeverity):
            object.__setattr__(self, "severity", TechnicalRiskCandidateSeverity(self.severity))
        object.__setattr__(self, "close_vs_sma20", _canonical_decimal(self.close_vs_sma20))
        object.__setattr__(self, "close_vs_sma60", _canonical_decimal(self.close_vs_sma60))
        object.__setattr__(self, "relative_sma_spread", _canonical_decimal(self.relative_sma_spread))
        object.__setattr__(self, "mae20_value", _canonical_decimal(self.mae20_value))
        object.__setattr__(self, "mae60_value", _canonical_decimal(self.mae60_value))
        object.__setattr__(self, "predicate_states", tuple(self.predicate_states))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))


@dataclass(frozen=True)
class TechnicalRiskSeverityMAEMetrics:
    """Continuous MAE distribution metrics for one split and one severity bucket."""

    split_role: TechnicalRiskOOSSplitRole
    severity: TechnicalRiskCandidateSeverity
    sample_count: int
    coverage_ratio: Decimal
    mae20_mean: Decimal | None
    mae20_median: Decimal | None
    mae20_p25: Decimal | None
    mae20_p75: Decimal | None
    mae60_mean: Decimal | None
    mae60_median: Decimal | None
    mae60_p25: Decimal | None
    mae60_p75: Decimal | None

    def __post_init__(self):
        if not isinstance(self.split_role, TechnicalRiskOOSSplitRole):
            object.__setattr__(self, "split_role", TechnicalRiskOOSSplitRole(self.split_role))
        if not isinstance(self.severity, TechnicalRiskCandidateSeverity):
            object.__setattr__(self, "severity", TechnicalRiskCandidateSeverity(self.severity))
        if self.sample_count < 0:
            raise TechnicalRiskCandidateEvaluationError("sample_count cannot be negative.")
        object.__setattr__(self, "coverage_ratio", _canonical_decimal(self.coverage_ratio))
        for field_name in (
            "mae20_mean",
            "mae20_median",
            "mae20_p25",
            "mae20_p75",
            "mae60_mean",
            "mae60_median",
            "mae60_p25",
            "mae60_p75",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _canonical_decimal(value))


@dataclass(frozen=True)
class TechnicalRiskMonotonicityResult:
    """Median-based monotonicity result for one split and MAE horizon."""

    split_role: TechnicalRiskOOSSplitRole
    horizon: int
    status: TechnicalRiskMonotonicityStatus
    low_median: Decimal | None
    medium_median: Decimal | None
    high_median: Decimal | None
    reason_code: str | None = None

    def __post_init__(self):
        if not isinstance(self.split_role, TechnicalRiskOOSSplitRole):
            object.__setattr__(self, "split_role", TechnicalRiskOOSSplitRole(self.split_role))
        if self.horizon not in (20, 60):
            raise TechnicalRiskCandidateEvaluationError("Unsupported MAE horizon.")
        if not isinstance(self.status, TechnicalRiskMonotonicityStatus):
            object.__setattr__(self, "status", TechnicalRiskMonotonicityStatus(self.status))
        for field_name in ("low_median", "medium_median", "high_median"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _canonical_decimal(value))


@dataclass(frozen=True)
class TechnicalRiskCandidateEvaluationResult:
    """Frozen result for one candidate and one threshold set on selected split roles."""

    evaluation_id: str
    dataset_id: str
    dataset_checksum: str
    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str
    threshold_set_id: str
    threshold_set_version: str
    threshold_set_checksum: str
    derived_evidence_version: str
    evaluator_version: str
    metric_version: str
    quantile_version: str
    numeric_context_version: str
    evaluated_split_roles: tuple[TechnicalRiskOOSSplitRole, ...]
    row_evaluations: tuple[TechnicalRiskCandidateRowEvaluation, ...]
    aggregate_metrics: tuple[TechnicalRiskSeverityMAEMetrics, ...]
    monotonicity_results: tuple[TechnicalRiskMonotonicityResult, ...]
    evaluation_checksum: str
    evaluated_row_count: int | None = None


class TechnicalRiskCandidateEvaluator:
    """Evaluates one frozen Technical Risk rule candidate against one threshold set."""

    def __init__(self) -> None:
        self._row_runtime_cache: dict[tuple[object, ...], tuple[TechnicalRiskDerivedEvidence, Decimal]] = {}
        self._candidate_rule_mask_cache: dict[str, tuple[tuple[TechnicalRiskCandidateRule, int], ...]] = {}

    def evaluate(
        self,
        dataset: TechnicalRiskOOSDatasetResult,
        candidate_spec: TechnicalRiskRuleCandidateSpec,
        threshold_set: TechnicalRiskThresholdSet,
        evaluation_input: TechnicalRiskCandidateEvaluationInput,
    ) -> TechnicalRiskCandidateEvaluationResult:
        self._validate_integrity(dataset, candidate_spec, threshold_set, evaluation_input)
        split_roles = evaluation_input.allowed_split_roles
        rows = tuple(
            sorted(
                (row for row in dataset.included_rows if row.split_role in split_roles),
                key=_row_sort_key,
            )
        )
        row_evaluations = tuple(
            self._evaluate_row(row, candidate_spec, threshold_set, evaluation_input)
            for row in rows
        )
        aggregate_metrics = _aggregate_metrics(row_evaluations, split_roles)
        monotonicity_results = _monotonicity_results(aggregate_metrics, split_roles)
        evaluation_id = _evaluation_id(evaluation_input)
        checksum = _evaluation_checksum(
            evaluation_id,
            evaluation_input,
            row_evaluations,
            aggregate_metrics,
            monotonicity_results,
        )
        return TechnicalRiskCandidateEvaluationResult(
            evaluation_id=evaluation_id,
            dataset_id=evaluation_input.dataset_id,
            dataset_checksum=evaluation_input.dataset_checksum,
            candidate_id=evaluation_input.candidate_id,
            candidate_version=evaluation_input.candidate_version,
            candidate_structural_checksum=evaluation_input.candidate_structural_checksum,
            threshold_set_id=evaluation_input.threshold_set_id,
            threshold_set_version=evaluation_input.threshold_set_version,
            threshold_set_checksum=evaluation_input.threshold_set_checksum,
            derived_evidence_version=evaluation_input.derived_evidence_version,
            evaluator_version=evaluation_input.evaluator_version,
            metric_version=evaluation_input.metric_version,
            quantile_version=evaluation_input.quantile_version,
            numeric_context_version=evaluation_input.numeric_context_version,
            evaluated_split_roles=split_roles,
            row_evaluations=row_evaluations,
            aggregate_metrics=aggregate_metrics,
            monotonicity_results=monotonicity_results,
            evaluation_checksum=checksum,
            evaluated_row_count=len(row_evaluations),
        )

    def evaluate_compact(
        self,
        dataset: TechnicalRiskOOSDatasetResult,
        candidate_spec: TechnicalRiskRuleCandidateSpec,
        threshold_set: TechnicalRiskThresholdSet,
        evaluation_input: TechnicalRiskCandidateEvaluationInput,
    ) -> TechnicalRiskCandidateEvaluationResult:
        self._validate_integrity(dataset, candidate_spec, threshold_set, evaluation_input)
        split_roles = evaluation_input.allowed_split_roles
        rows = tuple(
            sorted(
                (row for row in dataset.included_rows if row.split_role in split_roles),
                key=_row_sort_key,
            )
        )
        threshold_values = threshold_set.bound_decimal_values
        bucket_values: dict[tuple[TechnicalRiskOOSSplitRole, TechnicalRiskCandidateSeverity], tuple[list[Decimal], list[Decimal]]] = {
            (split_role, severity): ([], [])
            for split_role in split_roles
            for severity in ALLOWED_CANDIDATE_SEVERITIES_V1
        }
        split_totals = {split_role: 0 for split_role in split_roles}
        row_payloads: list[dict[str, object]] = []
        for row in rows:
            try:
                evidence, rsi = self._row_runtime_values(row)
                predicate_states, predicate_mask = _evaluate_bound_predicates(evidence, rsi, threshold_values)
            except TechnicalRiskRuleCandidateError as exc:
                raise TechnicalRiskCandidateEvaluationError(str(exc)) from exc
            rule = self._matched_rule(candidate_spec, predicate_mask)
            severity = TechnicalRiskCandidateSeverity.LOW if rule is None else rule.severity
            reason_codes = _reason_codes(rule, predicate_states)
            calculation_id = _stable_id(
                "technical_risk_candidate_row_evaluation",
                {
                    "row_id": row.row_id,
                    "candidate_checksum": evaluation_input.candidate_structural_checksum,
                    "threshold_checksum": evaluation_input.threshold_set_checksum,
                    "evaluator_version": evaluation_input.evaluator_version,
                },
            )
            mae20_value = _canonical_decimal(row.mae20_value)
            mae60_value = _canonical_decimal(row.mae60_value)
            split_totals[row.split_role] += 1
            mae20_values, mae60_values = bucket_values[(row.split_role, severity)]
            mae20_values.append(mae20_value)
            mae60_values.append(mae60_value)
            row_payloads.append(
                {
                    "row_id": row.row_id,
                    "symbol": row.symbol,
                    "evaluation_date": row.evaluation_date.isoformat(),
                    "split_id": row.split_id,
                    "split_role": row.split_role.value,
                    "candidate_id": evaluation_input.candidate_id,
                    "candidate_version": evaluation_input.candidate_version,
                    "candidate_structural_checksum": evaluation_input.candidate_structural_checksum,
                    "threshold_set_id": evaluation_input.threshold_set_id,
                    "threshold_set_version": evaluation_input.threshold_set_version,
                    "threshold_set_checksum": evaluation_input.threshold_set_checksum,
                    "derived_evidence_version": evidence.derived_evidence_version,
                    "close_vs_sma20": evidence.close_vs_sma20,
                    "close_vs_sma60": evidence.close_vs_sma60,
                    "relative_sma_spread": evidence.relative_sma_spread,
                    "predicate_states": [
                        {"predicate_id": state.predicate_id.value, "is_triggered": state.is_triggered}
                        for state in predicate_states
                    ],
                    "severity": severity.value,
                    "matched_rule_id": None if rule is None else rule.rule_id,
                    "reason_codes": reason_codes,
                    "mae20_value": mae20_value,
                    "mae60_value": mae60_value,
                    "evaluation_version": evaluation_input.evaluator_version,
                    "calculation_id": calculation_id,
                }
            )
        aggregate_metrics = _aggregate_metrics_from_bucket_values(bucket_values, split_totals, split_roles)
        monotonicity_results = _monotonicity_results(aggregate_metrics, split_roles)
        evaluation_id = _evaluation_id(evaluation_input)
        checksum = _evaluation_checksum_from_payloads(
            evaluation_id,
            evaluation_input,
            row_payloads,
            aggregate_metrics,
            monotonicity_results,
        )
        return TechnicalRiskCandidateEvaluationResult(
            evaluation_id=evaluation_id,
            dataset_id=evaluation_input.dataset_id,
            dataset_checksum=evaluation_input.dataset_checksum,
            candidate_id=evaluation_input.candidate_id,
            candidate_version=evaluation_input.candidate_version,
            candidate_structural_checksum=evaluation_input.candidate_structural_checksum,
            threshold_set_id=evaluation_input.threshold_set_id,
            threshold_set_version=evaluation_input.threshold_set_version,
            threshold_set_checksum=evaluation_input.threshold_set_checksum,
            derived_evidence_version=evaluation_input.derived_evidence_version,
            evaluator_version=evaluation_input.evaluator_version,
            metric_version=evaluation_input.metric_version,
            quantile_version=evaluation_input.quantile_version,
            numeric_context_version=evaluation_input.numeric_context_version,
            evaluated_split_roles=split_roles,
            row_evaluations=(),
            aggregate_metrics=aggregate_metrics,
            monotonicity_results=monotonicity_results,
            evaluation_checksum=checksum,
            evaluated_row_count=len(rows),
        )

    def _validate_integrity(
        self,
        dataset: TechnicalRiskOOSDatasetResult,
        candidate_spec: TechnicalRiskRuleCandidateSpec,
        threshold_set: TechnicalRiskThresholdSet,
        evaluation_input: TechnicalRiskCandidateEvaluationInput,
    ) -> None:
        if evaluation_input.dataset_id != dataset.dataset_id:
            raise TechnicalRiskCandidateEvaluationError("dataset_id mismatch.")
        if evaluation_input.dataset_checksum != dataset.dataset_checksum:
            raise TechnicalRiskCandidateEvaluationError("dataset_checksum mismatch.")
        if evaluation_input.candidate_id != candidate_spec.policy_candidate_id:
            raise TechnicalRiskCandidateEvaluationError("candidate_id mismatch.")
        if evaluation_input.candidate_version != candidate_spec.candidate_version:
            raise TechnicalRiskCandidateEvaluationError("candidate_version mismatch.")
        if evaluation_input.candidate_structural_checksum != candidate_spec.candidate_structural_checksum:
            raise TechnicalRiskCandidateEvaluationError("candidate_structural_checksum mismatch.")
        if evaluation_input.threshold_set_id != threshold_set.threshold_set_id:
            raise TechnicalRiskCandidateEvaluationError("threshold_set_id mismatch.")
        if evaluation_input.threshold_set_version != threshold_set.threshold_set_version:
            raise TechnicalRiskCandidateEvaluationError("threshold_set_version mismatch.")
        if evaluation_input.threshold_set_checksum != threshold_set.threshold_set_checksum:
            raise TechnicalRiskCandidateEvaluationError("threshold_set_checksum mismatch.")
        if candidate_spec.derived_evidence_version != evaluation_input.derived_evidence_version:
            raise TechnicalRiskCandidateEvaluationError("derived evidence mismatch.")
        if tuple(candidate_spec.allowed_severities) != ALLOWED_CANDIDATE_SEVERITIES_V1:
            raise TechnicalRiskCandidateEvaluationError("Unsupported candidate severity contract.")
        if threshold_set.numeric_representation_version != TECH_RISK_NUMERIC_REPRESENTATION_V1:
            raise TechnicalRiskCandidateEvaluationError("Unsupported numeric representation.")
        if tuple(dimension.dimension_id for dimension in sorted(threshold_set.dimensions, key=lambda item: item.dimension_id.value)) != tuple(
            sorted(REQUIRED_THRESHOLD_DIMENSIONS_V1, key=lambda item: item.value)
        ):
            raise TechnicalRiskCandidateEvaluationError("Threshold dimensions mismatch.")
        if any(dimension.operator != TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL for dimension in threshold_set.dimensions):
            raise TechnicalRiskCandidateEvaluationError("Unsupported threshold operator.")
        if candidate_spec.candidate_family not in threshold_set.compatible_candidate_families:
            raise TechnicalRiskCandidateEvaluationError("Candidate family is incompatible with threshold set.")

    def _evaluate_row(
        self,
        row: AlignedTechnicalRiskOOSRow,
        candidate_spec: TechnicalRiskRuleCandidateSpec,
        threshold_set: TechnicalRiskThresholdSet,
        evaluation_input: TechnicalRiskCandidateEvaluationInput,
    ) -> TechnicalRiskCandidateRowEvaluation:
        try:
            evidence, rsi = self._row_runtime_values(row)
            predicate_states, predicate_mask = _evaluate_bound_predicates(evidence, rsi, threshold_set.bound_decimal_values)
        except TechnicalRiskRuleCandidateError as exc:
            raise TechnicalRiskCandidateEvaluationError(str(exc)) from exc
        rule = self._matched_rule(candidate_spec, predicate_mask)
        severity = TechnicalRiskCandidateSeverity.LOW if rule is None else rule.severity
        reason_codes = _reason_codes(rule, predicate_states)
        calculation_id = _stable_id(
            "technical_risk_candidate_row_evaluation",
            {
                "row_id": row.row_id,
                "candidate_checksum": evaluation_input.candidate_structural_checksum,
                "threshold_checksum": evaluation_input.threshold_set_checksum,
                "evaluator_version": evaluation_input.evaluator_version,
            },
        )
        return TechnicalRiskCandidateRowEvaluation(
            row_id=row.row_id,
            symbol=row.symbol,
            evaluation_date=row.evaluation_date,
            split_id=row.split_id,
            split_role=row.split_role,
            candidate_id=evaluation_input.candidate_id,
            candidate_version=evaluation_input.candidate_version,
            candidate_structural_checksum=evaluation_input.candidate_structural_checksum,
            threshold_set_id=evaluation_input.threshold_set_id,
            threshold_set_version=evaluation_input.threshold_set_version,
            threshold_set_checksum=evaluation_input.threshold_set_checksum,
            derived_evidence_version=evidence.derived_evidence_version,
            close_vs_sma20=evidence.close_vs_sma20,
            close_vs_sma60=evidence.close_vs_sma60,
            relative_sma_spread=evidence.relative_sma_spread,
            predicate_states=predicate_states,
            severity=severity,
            matched_rule_id=None if rule is None else rule.rule_id,
            reason_codes=reason_codes,
            mae20_value=row.mae20_value,
            mae60_value=row.mae60_value,
            evaluation_version=evaluation_input.evaluator_version,
            calculation_id=calculation_id,
        )

    def _row_runtime_values(self, row: AlignedTechnicalRiskOOSRow) -> tuple[TechnicalRiskDerivedEvidence, Decimal]:
        key = (
            row.row_id,
            row.observation_id,
            row.feature_observation_checksum,
            row.as_of_close,
            row.sma20,
            row.sma60,
            row.rsi14,
        )
        cached = self._row_runtime_cache.get(key)
        if cached is not None:
            return cached
        evidence = derive_technical_risk_evidence(row)
        values = (evidence, _canonical_decimal(row.rsi14))
        self._row_runtime_cache[key] = values
        return values

    def _matched_rule(self, candidate_spec: TechnicalRiskRuleCandidateSpec, predicate_mask: int) -> TechnicalRiskCandidateRule | None:
        rule_masks = self._candidate_rule_mask_cache.get(candidate_spec.candidate_structural_checksum)
        if rule_masks is None:
            rule_masks = tuple(
                (
                    rule,
                    _predicate_mask_for_ids(rule.required_predicates),
                )
                for rule in sorted(candidate_spec.rules, key=lambda item: (_severity_order(item.severity), item.rule_priority))
            )
            self._candidate_rule_mask_cache[candidate_spec.candidate_structural_checksum] = rule_masks
        for rule, required_mask in rule_masks:
            if predicate_mask & required_mask == required_mask:
                return rule
        return None


def _matched_rule(
    candidate_spec: TechnicalRiskRuleCandidateSpec,
    predicate_states: tuple[TechnicalRiskPredicateState, ...],
) -> TechnicalRiskCandidateRule | None:
    active = {state.predicate_id for state in predicate_states if state.is_triggered}
    matches = tuple(rule for rule in candidate_spec.rules if set(rule.required_predicates).issubset(active))
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda rule: (_severity_order(rule.severity), rule.rule_priority),
    )[0]


def _reason_codes(
    rule: TechnicalRiskCandidateRule | None,
    predicate_states: tuple[TechnicalRiskPredicateState, ...],
) -> tuple[str, ...]:
    if rule is None:
        return (TECH_RISK_LOW_REASON_V1,)
    reasons = [reason.value for reason in rule.reason_codes]
    active = {state.predicate_id for state in predicate_states if state.is_triggered}
    for predicate in rule.optional_confirmation_predicates:
        if predicate in active:
            reason = _optional_reason(predicate)
            if reason not in reasons:
                reasons.append(reason)
    return tuple(reasons)


def _optional_reason(predicate: TechnicalRiskPredicateId) -> str:
    return {
        TechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS: TechnicalRiskReasonCode.PRICE_POSITION_SHORT_TERM_WEAKNESS.value,
        TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS: TechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS.value,
        TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS: TechnicalRiskReasonCode.TREND_STRUCTURE_WEAKNESS.value,
        TechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION: TechnicalRiskReasonCode.MOMENTUM_WEAKNESS_CONFIRMATION.value,
    }[predicate]


def _evaluate_bound_predicates(
    evidence: TechnicalRiskDerivedEvidence,
    rsi14: Decimal,
    threshold_values: tuple[Decimal, Decimal, Decimal, Decimal],
) -> tuple[tuple[TechnicalRiskPredicateState, ...], int]:
    values = (
        evidence.close_vs_sma20 <= threshold_values[0],
        evidence.close_vs_sma60 <= threshold_values[1],
        evidence.relative_sma_spread <= threshold_values[2],
        rsi14 <= threshold_values[3],
    )
    predicate_mask = 0
    states: list[TechnicalRiskPredicateState] = []
    for index, is_triggered in enumerate(values):
        if is_triggered:
            predicate_mask |= 1 << index
        states.append(TechnicalRiskPredicateState(_PREDICATE_ORDER[index], is_triggered))
    return tuple(states), predicate_mask


def _predicate_mask_for_ids(predicate_ids: tuple[TechnicalRiskPredicateId, ...]) -> int:
    index = MappingProxyType({predicate_id: position for position, predicate_id in enumerate(_PREDICATE_ORDER)})
    mask = 0
    for predicate_id in predicate_ids:
        mask |= 1 << index[predicate_id]
    return mask


def _aggregate_metrics(
    row_evaluations: tuple[TechnicalRiskCandidateRowEvaluation, ...],
    split_roles: tuple[TechnicalRiskOOSSplitRole, ...],
) -> tuple[TechnicalRiskSeverityMAEMetrics, ...]:
    metrics: list[TechnicalRiskSeverityMAEMetrics] = []
    for split_role in split_roles:
        split_rows = tuple(row for row in row_evaluations if row.split_role == split_role)
        total = len(split_rows)
        for severity in ALLOWED_CANDIDATE_SEVERITIES_V1:
            bucket = tuple(row for row in split_rows if row.severity == severity)
            metrics.append(_severity_metrics(split_role, severity, bucket, total))
    return tuple(metrics)


def _aggregate_metrics_from_bucket_values(
    bucket_values: Mapping[tuple[TechnicalRiskOOSSplitRole, TechnicalRiskCandidateSeverity], tuple[list[Decimal], list[Decimal]]],
    split_totals: Mapping[TechnicalRiskOOSSplitRole, int],
    split_roles: tuple[TechnicalRiskOOSSplitRole, ...],
) -> tuple[TechnicalRiskSeverityMAEMetrics, ...]:
    metrics: list[TechnicalRiskSeverityMAEMetrics] = []
    for split_role in split_roles:
        total = split_totals[split_role]
        for severity in ALLOWED_CANDIDATE_SEVERITIES_V1:
            mae20_values, mae60_values = bucket_values[(split_role, severity)]
            metrics.append(_severity_metrics_from_values(split_role, severity, tuple(mae20_values), tuple(mae60_values), total))
    return tuple(metrics)


def _severity_metrics(
    split_role: TechnicalRiskOOSSplitRole,
    severity: TechnicalRiskCandidateSeverity,
    rows: tuple[TechnicalRiskCandidateRowEvaluation, ...],
    total_rows: int,
) -> TechnicalRiskSeverityMAEMetrics:
    if not rows:
        return TechnicalRiskSeverityMAEMetrics(
            split_role=split_role,
            severity=severity,
            sample_count=0,
            coverage_ratio=Decimal("0"),
            mae20_mean=None,
            mae20_median=None,
            mae20_p25=None,
            mae20_p75=None,
            mae60_mean=None,
            mae60_median=None,
            mae60_p25=None,
            mae60_p75=None,
        )
    mae20 = _distribution_stats(tuple(row.mae20_value for row in rows))
    mae60 = _distribution_stats(tuple(row.mae60_value for row in rows))
    return _severity_metrics_from_distributions(split_role, severity, len(rows), mae20, mae60, total_rows)


def _severity_metrics_from_values(
    split_role: TechnicalRiskOOSSplitRole,
    severity: TechnicalRiskCandidateSeverity,
    mae20_values: tuple[Decimal, ...],
    mae60_values: tuple[Decimal, ...],
    total_rows: int,
) -> TechnicalRiskSeverityMAEMetrics:
    if not mae20_values:
        return TechnicalRiskSeverityMAEMetrics(
            split_role=split_role,
            severity=severity,
            sample_count=0,
            coverage_ratio=Decimal("0"),
            mae20_mean=None,
            mae20_median=None,
            mae20_p25=None,
            mae20_p75=None,
            mae60_mean=None,
            mae60_median=None,
            mae60_p25=None,
            mae60_p75=None,
        )
    return _severity_metrics_from_distributions(
        split_role,
        severity,
        len(mae20_values),
        _distribution_stats(mae20_values),
        _distribution_stats(mae60_values),
        total_rows,
    )


def _severity_metrics_from_distributions(
    split_role: TechnicalRiskOOSSplitRole,
    severity: TechnicalRiskCandidateSeverity,
    sample_count: int,
    mae20: Mapping[str, Decimal],
    mae60: Mapping[str, Decimal],
    total_rows: int,
) -> TechnicalRiskSeverityMAEMetrics:
    with localcontext(FIXED_TECH_RISK_DECIMAL_CONTEXT):
        coverage = Decimal(sample_count) / Decimal(total_rows)
    return TechnicalRiskSeverityMAEMetrics(
        split_role=split_role,
        severity=severity,
        sample_count=sample_count,
        coverage_ratio=coverage,
        mae20_mean=mae20["mean"],
        mae20_median=mae20["median"],
        mae20_p25=mae20["p25"],
        mae20_p75=mae20["p75"],
        mae60_mean=mae60["mean"],
        mae60_median=mae60["median"],
        mae60_p25=mae60["p25"],
        mae60_p75=mae60["p75"],
    )


def _monotonicity_results(
    aggregate_metrics: tuple[TechnicalRiskSeverityMAEMetrics, ...],
    split_roles: tuple[TechnicalRiskOOSSplitRole, ...],
) -> tuple[TechnicalRiskMonotonicityResult, ...]:
    by_key = {(metric.split_role, metric.severity): metric for metric in aggregate_metrics}
    results: list[TechnicalRiskMonotonicityResult] = []
    for split_role in split_roles:
        for horizon in (20, 60):
            low = by_key[(split_role, TechnicalRiskCandidateSeverity.LOW)]
            medium = by_key[(split_role, TechnicalRiskCandidateSeverity.MEDIUM)]
            high = by_key[(split_role, TechnicalRiskCandidateSeverity.HIGH)]
            low_median = low.mae20_median if horizon == 20 else low.mae60_median
            medium_median = medium.mae20_median if horizon == 20 else medium.mae60_median
            high_median = high.mae20_median if horizon == 20 else high.mae60_median
            if low.sample_count == 0 or medium.sample_count == 0 or high.sample_count == 0:
                status = TechnicalRiskMonotonicityStatus.NOT_EVALUABLE
                reason_code = "EMPTY_SEVERITY_BUCKET"
            elif low_median >= medium_median >= high_median:
                status = TechnicalRiskMonotonicityStatus.PASS
                reason_code = None
            else:
                status = TechnicalRiskMonotonicityStatus.WARNING
                reason_code = "MEDIAN_MAE_MONOTONICITY_VIOLATION"
            results.append(
                TechnicalRiskMonotonicityResult(
                    split_role=split_role,
                    horizon=horizon,
                    status=status,
                    low_median=low_median,
                    medium_median=medium_median,
                    high_median=high_median,
                    reason_code=reason_code,
                )
            )
    return tuple(results)


def _mean(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        raise TechnicalRiskCandidateEvaluationError("mean requires at least one value.")
    with localcontext(FIXED_TECH_RISK_DECIMAL_CONTEXT):
        return _canonical_decimal(sum(values) / Decimal(len(values)))


def _distribution_stats(values: tuple[Decimal, ...]) -> Mapping[str, Decimal]:
    if not values:
        raise TechnicalRiskCandidateEvaluationError("distribution stats require at least one value.")
    canonical_values = tuple(_canonical_decimal(value) for value in values)
    ordered = tuple(sorted(canonical_values))
    with localcontext(FIXED_TECH_RISK_DECIMAL_CONTEXT):
        mean = _canonical_decimal(sum(canonical_values) / Decimal(len(canonical_values)))
    return {
        "mean": mean,
        "median": _median_from_ordered(ordered),
        "p25": ordered[_nearest_rank(Decimal("0.25"), len(ordered)) - 1],
        "p75": ordered[_nearest_rank(Decimal("0.75"), len(ordered)) - 1],
    }


def _median(values: tuple[Decimal, ...]) -> Decimal:
    ordered = tuple(sorted(_canonical_decimal(value) for value in values))
    if not ordered:
        raise TechnicalRiskCandidateEvaluationError("median requires at least one value.")
    return _median_from_ordered(ordered)


def _median_from_ordered(ordered: tuple[Decimal, ...]) -> Decimal:
    if not ordered:
        raise TechnicalRiskCandidateEvaluationError("median requires at least one value.")
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    with localcontext(FIXED_TECH_RISK_DECIMAL_CONTEXT):
        return _canonical_decimal((ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2"))


def _nearest_rank_quantile(values: tuple[Decimal, ...], p: Decimal) -> Decimal:
    ordered = tuple(sorted(_canonical_decimal(value) for value in values))
    if not ordered:
        raise TechnicalRiskCandidateEvaluationError("quantile requires at least one value.")
    rank = _nearest_rank(p, len(ordered))
    return ordered[rank - 1]


def _nearest_rank(p: Decimal, n: int) -> int:
    if p == Decimal("0.25"):
        numerator, denominator = 1, 4
    elif p == Decimal("0.75"):
        numerator, denominator = 3, 4
    else:
        raise TechnicalRiskCandidateEvaluationError("Unsupported quantile probability.")
    return (numerator * n + denominator - 1) // denominator


def _evaluation_id(evaluation_input: TechnicalRiskCandidateEvaluationInput) -> str:
    return _stable_id(
        "technical_risk_candidate_evaluation",
        {
            "dataset_checksum": evaluation_input.dataset_checksum,
            "candidate_structural_checksum": evaluation_input.candidate_structural_checksum,
            "threshold_set_checksum": evaluation_input.threshold_set_checksum,
            "derived_evidence_version": evaluation_input.derived_evidence_version,
            "evaluator_version": evaluation_input.evaluator_version,
            "metric_version": evaluation_input.metric_version,
            "quantile_version": evaluation_input.quantile_version,
            "numeric_context_version": evaluation_input.numeric_context_version,
            "evaluated_split_roles": [role.value for role in evaluation_input.allowed_split_roles],
        },
    )


def _evaluation_checksum(
    evaluation_id: str,
    evaluation_input: TechnicalRiskCandidateEvaluationInput,
    row_evaluations: tuple[TechnicalRiskCandidateRowEvaluation, ...],
    aggregate_metrics: tuple[TechnicalRiskSeverityMAEMetrics, ...],
    monotonicity_results: tuple[TechnicalRiskMonotonicityResult, ...],
) -> str:
    return _stable_hash(
        {
            "evaluation_id": evaluation_id,
            "evaluation_input_version": evaluation_input.evaluation_input_version,
            "dataset_id": evaluation_input.dataset_id,
            "dataset_checksum": evaluation_input.dataset_checksum,
            "candidate_id": evaluation_input.candidate_id,
            "candidate_version": evaluation_input.candidate_version,
            "candidate_structural_checksum": evaluation_input.candidate_structural_checksum,
            "threshold_set_id": evaluation_input.threshold_set_id,
            "threshold_set_version": evaluation_input.threshold_set_version,
            "threshold_set_checksum": evaluation_input.threshold_set_checksum,
            "derived_evidence_version": evaluation_input.derived_evidence_version,
            "evaluator_version": evaluation_input.evaluator_version,
            "metric_version": evaluation_input.metric_version,
            "quantile_version": evaluation_input.quantile_version,
            "numeric_context_version": evaluation_input.numeric_context_version,
            "evaluated_split_roles": [role.value for role in evaluation_input.allowed_split_roles],
            "row_evaluations": [_row_evaluation_payload(row) for row in row_evaluations],
            "aggregate_metrics": [_metric_payload(metric) for metric in aggregate_metrics],
            "monotonicity_results": [_monotonicity_payload(result) for result in monotonicity_results],
        }
    )


def _evaluation_checksum_from_payloads(
    evaluation_id: str,
    evaluation_input: TechnicalRiskCandidateEvaluationInput,
    row_payloads: list[dict[str, object]],
    aggregate_metrics: tuple[TechnicalRiskSeverityMAEMetrics, ...],
    monotonicity_results: tuple[TechnicalRiskMonotonicityResult, ...],
) -> str:
    return _stable_hash(
        {
            "evaluation_id": evaluation_id,
            "evaluation_input_version": evaluation_input.evaluation_input_version,
            "dataset_id": evaluation_input.dataset_id,
            "dataset_checksum": evaluation_input.dataset_checksum,
            "candidate_id": evaluation_input.candidate_id,
            "candidate_version": evaluation_input.candidate_version,
            "candidate_structural_checksum": evaluation_input.candidate_structural_checksum,
            "threshold_set_id": evaluation_input.threshold_set_id,
            "threshold_set_version": evaluation_input.threshold_set_version,
            "threshold_set_checksum": evaluation_input.threshold_set_checksum,
            "derived_evidence_version": evaluation_input.derived_evidence_version,
            "evaluator_version": evaluation_input.evaluator_version,
            "metric_version": evaluation_input.metric_version,
            "quantile_version": evaluation_input.quantile_version,
            "numeric_context_version": evaluation_input.numeric_context_version,
            "evaluated_split_roles": [role.value for role in evaluation_input.allowed_split_roles],
            "row_evaluations": row_payloads,
            "aggregate_metrics": [_metric_payload(metric) for metric in aggregate_metrics],
            "monotonicity_results": [_monotonicity_payload(result) for result in monotonicity_results],
        }
    )


def _row_evaluation_payload(row: TechnicalRiskCandidateRowEvaluation) -> dict[str, object]:
    return {
        "row_id": row.row_id,
        "symbol": row.symbol,
        "evaluation_date": row.evaluation_date.isoformat(),
        "split_id": row.split_id,
        "split_role": row.split_role.value,
        "candidate_id": row.candidate_id,
        "candidate_version": row.candidate_version,
        "candidate_structural_checksum": row.candidate_structural_checksum,
        "threshold_set_id": row.threshold_set_id,
        "threshold_set_version": row.threshold_set_version,
        "threshold_set_checksum": row.threshold_set_checksum,
        "derived_evidence_version": row.derived_evidence_version,
        "close_vs_sma20": row.close_vs_sma20,
        "close_vs_sma60": row.close_vs_sma60,
        "relative_sma_spread": row.relative_sma_spread,
        "predicate_states": [
            {"predicate_id": state.predicate_id.value, "is_triggered": state.is_triggered}
            for state in row.predicate_states
        ],
        "severity": row.severity.value,
        "matched_rule_id": row.matched_rule_id,
        "reason_codes": row.reason_codes,
        "mae20_value": row.mae20_value,
        "mae60_value": row.mae60_value,
        "evaluation_version": row.evaluation_version,
        "calculation_id": row.calculation_id,
    }


def _metric_payload(metric: TechnicalRiskSeverityMAEMetrics) -> dict[str, object]:
    return {
        "split_role": metric.split_role.value,
        "severity": metric.severity.value,
        "sample_count": metric.sample_count,
        "coverage_ratio": metric.coverage_ratio,
        "mae20_mean": metric.mae20_mean,
        "mae20_median": metric.mae20_median,
        "mae20_p25": metric.mae20_p25,
        "mae20_p75": metric.mae20_p75,
        "mae60_mean": metric.mae60_mean,
        "mae60_median": metric.mae60_median,
        "mae60_p25": metric.mae60_p25,
        "mae60_p75": metric.mae60_p75,
    }


def _monotonicity_payload(result: TechnicalRiskMonotonicityResult) -> dict[str, object]:
    return {
        "split_role": result.split_role.value,
        "horizon": result.horizon,
        "status": result.status.value,
        "low_median": result.low_median,
        "medium_median": result.medium_median,
        "high_median": result.high_median,
        "reason_code": result.reason_code,
    }


def _canonical_split_roles(values: tuple[TechnicalRiskOOSSplitRole, ...]) -> tuple[TechnicalRiskOOSSplitRole, ...]:
    roles = tuple(value if isinstance(value, TechnicalRiskOOSSplitRole) else TechnicalRiskOOSSplitRole(value) for value in values)
    if not roles:
        raise TechnicalRiskCandidateEvaluationError("allowed_split_roles must not be empty.")
    if len(set(roles)) != len(roles):
        raise TechnicalRiskCandidateEvaluationError("Duplicate split role.")
    return tuple(sorted(roles, key=_split_role_order))


def _row_sort_key(row: AlignedTechnicalRiskOOSRow) -> tuple[int, str, date, str]:
    return (_split_role_order(row.split_role), row.symbol, row.evaluation_date, row.row_id)


def _split_role_order(role: TechnicalRiskOOSSplitRole) -> int:
    return {
        TechnicalRiskOOSSplitRole.DEVELOPMENT: 0,
        TechnicalRiskOOSSplitRole.VALIDATION: 1,
        TechnicalRiskOOSSplitRole.HOLDOUT: 2,
    }[role]


def _severity_order(severity: TechnicalRiskCandidateSeverity) -> int:
    return {
        TechnicalRiskCandidateSeverity.HIGH: 0,
        TechnicalRiskCandidateSeverity.MEDIUM: 1,
        TechnicalRiskCandidateSeverity.LOW: 2,
    }[severity]


def _require_version(actual: object, expected: str, field_name: str) -> None:
    if actual != expected:
        raise TechnicalRiskCandidateEvaluationError(f"Unsupported {field_name}.")


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskCandidateEvaluationError(f"{field_name} must be a non-empty string.")


def _canonical_decimal(value: object) -> Decimal:
    decimal_value = _parse_decimal(value)
    if decimal_value == 0:
        return Decimal("0")
    formatted = format(decimal_value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    if formatted == "-0":
        return Decimal("0")
    return Decimal(formatted)


def _parse_decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise TechnicalRiskCandidateEvaluationError("Boolean is not a valid numeric value.")
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, Real):
        candidate = Decimal(str(value))
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise TechnicalRiskCandidateEvaluationError("Decimal string must not be empty.")
        try:
            candidate = Decimal(text)
        except InvalidOperation as exc:
            raise TechnicalRiskCandidateEvaluationError("Invalid Decimal representation.") from exc
    else:
        raise TechnicalRiskCandidateEvaluationError("Value must be numeric or a Decimal string.")
    if not candidate.is_finite():
        raise TechnicalRiskCandidateEvaluationError("Decimal value must be finite.")
    return candidate


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return _canonical_decimal_string(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _canonical_decimal_string(value: Decimal) -> str:
    decimal_value = _canonical_decimal(value)
    if decimal_value == 0:
        return "0"
    formatted = format(decimal_value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return "0" if formatted == "-0" else formatted
