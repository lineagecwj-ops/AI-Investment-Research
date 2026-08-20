from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from research_data_store import ResearchDataStore
from risk_oos.aligned_dataset import TECHNICAL_RISK_V1_FEATURE_SET_ID
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetResult
from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.candidate_evaluator import TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1
from risk_oos.candidate_evaluator import TECH_RISK_CANDIDATE_EVALUATOR_V1
from risk_oos.candidate_evaluator import TECH_RISK_CONTINUOUS_MAE_METRIC_V1
from risk_oos.candidate_evaluator import TECH_RISK_QUANTILE_NEAREST_RANK_V1
from risk_oos.candidate_evaluator import TechnicalRiskCandidateEvaluationInput
from risk_oos.candidate_evaluator import TechnicalRiskCandidateEvaluationResult
from risk_oos.candidate_evaluator import TechnicalRiskCandidateEvaluator
from risk_oos.candidate_evaluator import TechnicalRiskMonotonicityResult
from risk_oos.candidate_evaluator import TechnicalRiskMonotonicityStatus
from risk_oos.candidate_evaluator import TechnicalRiskSeverityMAEMetrics
from risk_oos.real_oos_materialization import TechnicalRiskRealOOSDatasetMaterializationRequest
from risk_oos.real_oos_materialization import TechnicalRiskRealOOSDatasetMaterializationResult
from risk_oos.real_oos_materialization import TechnicalRiskRealOOSDatasetMaterializer
from risk_oos.rule_candidates import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos.rule_candidates import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_oos.rule_candidates import TechnicalRiskRuleCandidateSpec
from risk_oos.rule_candidates import technical_risk_candidate_a_spec
from risk_oos.rule_candidates import technical_risk_candidate_b_spec
from risk_oos.rule_candidates import technical_risk_candidate_c_spec
from risk_oos.rule_candidates import technical_risk_candidate_d_spec
from risk_oos.temporal_split_methodology import TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1
from risk_oos.temporal_split_methodology import build_technical_risk_v1_temporal_split_methodology
from risk_oos.threshold_axis_set import TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1
from risk_oos.threshold_axis_set import TechnicalRiskV1ThresholdAxisSet
from risk_oos.threshold_axis_set import build_technical_risk_v1_threshold_axis_set
from risk_oos.threshold_axis_set import materialize_technical_risk_v1_threshold_grid
from risk_oos.threshold_grid import TechnicalRiskThresholdGridResult


TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_REQUEST_V1 = "TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_REQUEST_V1"
TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_RESULT_V1 = "TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_RESULT_V1"
TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_ORCHESTRATOR_V1 = "TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_ORCHESTRATOR_V1"
TECH_RISK_VALIDATION_DATASET_SPEC_ID_V1 = "technical_risk_v1_validation_candidate_evaluation_dataset"
TECH_RISK_VALIDATION_DATASET_SPEC_VERSION_V1 = "v1"

TECH_RISK_VALIDATION_CANDIDATE_IDS_V1 = (
    "TECH_POLICY_CANDIDATE_A",
    "TECH_POLICY_CANDIDATE_B",
    "TECH_POLICY_CANDIDATE_C",
    "TECH_POLICY_CANDIDATE_D",
)


class TechnicalRiskValidationCandidateEvaluationError(Exception):
    """Raised when VALIDATION-only candidate evaluation orchestration is invalid."""


@dataclass(frozen=True)
class TechnicalRiskValidationCandidateEvaluationRequest:
    """Explicit request for Technical Risk v1 VALIDATION-only candidate evidence."""

    request_version: str
    research_db_path: Path | str
    research_manifest_path: Path | str
    source_snapshot_id: str
    source_snapshot_checksum: str
    symbols: tuple[str, ...]
    methodology_version: str
    axis_set_version: str
    candidate_ids: tuple[str, ...]
    validation_start_date: date
    validation_end_date: date
    dataset_spec_id: str = TECH_RISK_VALIDATION_DATASET_SPEC_ID_V1
    dataset_spec_version: str = TECH_RISK_VALIDATION_DATASET_SPEC_VERSION_V1
    feature_set_id: str = TECHNICAL_RISK_V1_FEATURE_SET_ID
    orchestrator_version: str = TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_ORCHESTRATOR_V1

    def __post_init__(self) -> None:
        _require_version(self.request_version, TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_REQUEST_V1, "request_version")
        object.__setattr__(self, "research_db_path", Path(self.research_db_path))
        object.__setattr__(self, "research_manifest_path", Path(self.research_manifest_path))
        _require_text(self.source_snapshot_id, "source_snapshot_id")
        _require_text(self.source_snapshot_checksum, "source_snapshot_checksum")
        object.__setattr__(self, "symbols", _normalize_symbols(self.symbols))
        _require_version(self.methodology_version, TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1, "methodology_version")
        _require_version(self.axis_set_version, TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1, "axis_set_version")
        if tuple(self.candidate_ids) != TECH_RISK_VALIDATION_CANDIDATE_IDS_V1:
            raise TechnicalRiskValidationCandidateEvaluationError("candidate_ids must be exact Technical Risk v1 candidates.")
        if self.validation_start_date != date(2022, 1, 1) or self.validation_end_date != date(2023, 12, 31):
            raise TechnicalRiskValidationCandidateEvaluationError("Unsupported VALIDATION window.")
        _require_text(self.dataset_spec_id, "dataset_spec_id")
        _require_text(self.dataset_spec_version, "dataset_spec_version")
        _require_version(self.feature_set_id, TECHNICAL_RISK_V1_FEATURE_SET_ID, "feature_set_id")
        _require_version(
            self.orchestrator_version,
            TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_ORCHESTRATOR_V1,
            "orchestrator_version",
        )


@dataclass(frozen=True)
class TechnicalRiskValidationCandidateEvaluationRecord:
    """Compact evidence record for one candidate and one threshold set."""

    evaluation_id: str
    evaluation_checksum: str
    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str
    threshold_set_id: str
    threshold_set_version: str
    threshold_set_checksum: str
    evaluated_row_count: int
    aggregate_metrics: tuple[TechnicalRiskSeverityMAEMetrics, ...]
    monotonicity_results: tuple[TechnicalRiskMonotonicityResult, ...]

    def __post_init__(self) -> None:
        _require_text(self.evaluation_id, "evaluation_id")
        _require_text(self.evaluation_checksum, "evaluation_checksum")
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.candidate_version, "candidate_version")
        _require_text(self.candidate_structural_checksum, "candidate_structural_checksum")
        _require_text(self.threshold_set_id, "threshold_set_id")
        _require_text(self.threshold_set_version, "threshold_set_version")
        _require_text(self.threshold_set_checksum, "threshold_set_checksum")
        if self.evaluated_row_count < 0:
            raise TechnicalRiskValidationCandidateEvaluationError("evaluated_row_count cannot be negative.")
        object.__setattr__(self, "aggregate_metrics", tuple(self.aggregate_metrics))
        object.__setattr__(self, "monotonicity_results", tuple(self.monotonicity_results))


@dataclass(frozen=True)
class TechnicalRiskValidationCandidateSummary:
    """Candidate-level aggregate counts without ranking or selection semantics."""

    candidate_id: str
    evaluation_count: int
    monotonicity_status_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        if self.evaluation_count < 0:
            raise TechnicalRiskValidationCandidateEvaluationError("evaluation_count cannot be negative.")
        object.__setattr__(self, "monotonicity_status_counts", MappingProxyType(dict(self.monotonicity_status_counts)))


@dataclass(frozen=True)
class TechnicalRiskValidationCandidateEvaluationResult:
    """Deterministic VALIDATION-only evidence matrix for all approved candidates and thresholds."""

    result_id: str
    result_version: str
    result_checksum: str
    orchestrator_version: str
    methodology_version: str
    split_role: TechnicalRiskOOSSplitRole
    split_id: str
    validation_start_date: date
    validation_end_date: date
    dataset_id: str
    dataset_checksum: str
    validation_row_count: int
    source_snapshot_id: str
    source_snapshot_checksum: str
    axis_set_id: str
    axis_set_checksum: str
    threshold_grid_result_id: str
    threshold_grid_result_checksum: str
    candidate_count: int
    threshold_set_count: int
    evaluation_count: int
    dataset_materialization_count: int
    candidate_identities: tuple[tuple[str, str, str], ...]
    threshold_identities: tuple[tuple[str, str], ...]
    evaluation_records: tuple[TechnicalRiskValidationCandidateEvaluationRecord, ...]
    candidate_summaries: tuple[TechnicalRiskValidationCandidateSummary, ...]

    def __post_init__(self) -> None:
        _require_text(self.result_id, "result_id")
        _require_version(self.result_version, TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_RESULT_V1, "result_version")
        _require_text(self.result_checksum, "result_checksum")
        if self.split_role != TechnicalRiskOOSSplitRole.VALIDATION:
            raise TechnicalRiskValidationCandidateEvaluationError("Result split_role must be VALIDATION.")
        if self.validation_start_date != date(2022, 1, 1) or self.validation_end_date != date(2023, 12, 31):
            raise TechnicalRiskValidationCandidateEvaluationError("Result VALIDATION window mismatch.")
        if self.candidate_count != len(self.candidate_identities):
            raise TechnicalRiskValidationCandidateEvaluationError("candidate_count mismatch.")
        if self.threshold_set_count != len(self.threshold_identities):
            raise TechnicalRiskValidationCandidateEvaluationError("threshold_set_count mismatch.")
        if self.evaluation_count != len(self.evaluation_records):
            raise TechnicalRiskValidationCandidateEvaluationError("evaluation_count mismatch.")
        if self.dataset_materialization_count != 1:
            raise TechnicalRiskValidationCandidateEvaluationError("dataset must be materialized exactly once.")
        if self.evaluation_count != self.candidate_count * self.threshold_set_count:
            raise TechnicalRiskValidationCandidateEvaluationError("evaluation matrix is incomplete.")
        object.__setattr__(self, "evaluation_records", tuple(self.evaluation_records))
        object.__setattr__(self, "candidate_summaries", tuple(self.candidate_summaries))


class TechnicalRiskValidationCandidateEvaluationOrchestrator:
    """Builds VALIDATION-only evidence for all Technical Risk v1 candidates and approved thresholds."""

    def __init__(
        self,
        *,
        dataset_materializer: TechnicalRiskRealOOSDatasetMaterializer | None = None,
        candidate_evaluator: TechnicalRiskCandidateEvaluator | None = None,
    ) -> None:
        self._dataset_materializer = dataset_materializer or TechnicalRiskRealOOSDatasetMaterializer()
        self._candidate_evaluator = candidate_evaluator or TechnicalRiskCandidateEvaluator()

    def evaluate(
        self,
        request: TechnicalRiskValidationCandidateEvaluationRequest,
    ) -> TechnicalRiskValidationCandidateEvaluationResult:
        methodology = build_technical_risk_v1_temporal_split_methodology()
        axis_set = build_technical_risk_v1_threshold_axis_set()
        grid_result = materialize_technical_risk_v1_threshold_grid()
        candidates = _canonical_candidates(_candidate_specs())
        _validate_request_against_contracts(request, methodology.methodology_version, axis_set, candidates)
        materialization_result = self._materialize_validation_dataset(request, methodology.split_specs)
        dataset = materialization_result.oos_dataset_result
        _validate_validation_dataset(dataset)
        records = tuple(
            record
            for candidate in candidates
            for record in self._evaluate_candidate_thresholds(dataset, candidate, grid_result)
        )
        summaries = _candidate_summaries(records)
        return _build_result(
            request,
            dataset,
            axis_set,
            grid_result,
            candidates,
            records,
            summaries,
            materialization_result,
        )

    def _materialize_validation_dataset(
        self,
        request: TechnicalRiskValidationCandidateEvaluationRequest,
        split_specs,
    ) -> TechnicalRiskRealOOSDatasetMaterializationResult:
        materialization_request = TechnicalRiskRealOOSDatasetMaterializationRequest(
            research_db_path=request.research_db_path,
            research_manifest_path=request.research_manifest_path,
            source_snapshot_id=request.source_snapshot_id,
            source_snapshot_checksum=request.source_snapshot_checksum,
            symbols=request.symbols,
            analysis_start_date=request.validation_start_date,
            analysis_end_date=request.validation_end_date,
            split_specs=split_specs,
            dataset_spec_id=request.dataset_spec_id,
            dataset_spec_version=request.dataset_spec_version,
            feature_set_id=request.feature_set_id,
            required_output_split_roles=(TechnicalRiskOOSSplitRole.VALIDATION,),
        )
        return self._dataset_materializer.materialize(materialization_request)

    def _evaluate_candidate_thresholds(
        self,
        dataset: TechnicalRiskOOSDatasetResult,
        candidate: TechnicalRiskRuleCandidateSpec,
        grid_result: TechnicalRiskThresholdGridResult,
    ) -> tuple[TechnicalRiskValidationCandidateEvaluationRecord, ...]:
        records = []
        for threshold_set in grid_result.threshold_sets:
            evaluation_input = TechnicalRiskCandidateEvaluationInput(
                evaluation_input_version=TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1,
                dataset_id=dataset.dataset_id,
                dataset_checksum=dataset.dataset_checksum,
                candidate_id=candidate.policy_candidate_id,
                candidate_version=candidate.candidate_version,
                candidate_structural_checksum=candidate.candidate_structural_checksum,
                threshold_set_id=threshold_set.threshold_set_id,
                threshold_set_version=threshold_set.threshold_set_version,
                threshold_set_checksum=threshold_set.threshold_set_checksum,
                derived_evidence_version=TECH_RISK_DERIVED_EVIDENCE_V1,
                evaluator_version=TECH_RISK_CANDIDATE_EVALUATOR_V1,
                metric_version=TECH_RISK_CONTINUOUS_MAE_METRIC_V1,
                quantile_version=TECH_RISK_QUANTILE_NEAREST_RANK_V1,
                numeric_context_version=TECH_RISK_DECIMAL_CONTEXT_V1,
                allowed_split_roles=(TechnicalRiskOOSSplitRole.VALIDATION,),
            )
            evaluate = getattr(self._candidate_evaluator, "evaluate_compact", self._candidate_evaluator.evaluate)
            evaluation = evaluate(dataset, candidate, threshold_set, evaluation_input)
            records.append(_record_from_evaluation(evaluation))
        return tuple(records)


def build_technical_risk_v1_validation_candidate_evaluation_request(
    *,
    research_db_path: Path | str,
    research_manifest_path: Path | str,
    source_snapshot_id: str,
    source_snapshot_checksum: str,
    symbols: tuple[str, ...],
) -> TechnicalRiskValidationCandidateEvaluationRequest:
    """Build the explicit canonical request for Technical Risk v1 VALIDATION evaluation."""

    return TechnicalRiskValidationCandidateEvaluationRequest(
        request_version=TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_REQUEST_V1,
        research_db_path=research_db_path,
        research_manifest_path=research_manifest_path,
        source_snapshot_id=source_snapshot_id,
        source_snapshot_checksum=source_snapshot_checksum,
        symbols=symbols,
        methodology_version=TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1,
        axis_set_version=TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1,
        candidate_ids=TECH_RISK_VALIDATION_CANDIDATE_IDS_V1,
        validation_start_date=date(2022, 1, 1),
        validation_end_date=date(2023, 12, 31),
    )


def build_default_research_validation_candidate_evaluation_request() -> TechnicalRiskValidationCandidateEvaluationRequest:
    """Build the explicit request from the current released research snapshot configuration."""

    store = ResearchDataStore(verify_default_runtime=False)
    return build_technical_risk_v1_validation_candidate_evaluation_request(
        research_db_path=store.resolved_db_path,
        research_manifest_path=store.resolved_manifest_path,
        source_snapshot_id=store.resolved_research_snapshot_id,
        source_snapshot_checksum=store.resolved_semantic_checksum,
        symbols=store.materialized_twse_common_stock_symbols(),
    )


def _candidate_specs() -> tuple[TechnicalRiskRuleCandidateSpec, ...]:
    return (
        technical_risk_candidate_a_spec(),
        technical_risk_candidate_b_spec(),
        technical_risk_candidate_c_spec(),
        technical_risk_candidate_d_spec(),
    )


def _canonical_candidates(candidates: tuple[TechnicalRiskRuleCandidateSpec, ...]) -> tuple[TechnicalRiskRuleCandidateSpec, ...]:
    ordered = tuple(sorted(candidates, key=lambda item: item.policy_candidate_id))
    if tuple(candidate.policy_candidate_id for candidate in ordered) != TECH_RISK_VALIDATION_CANDIDATE_IDS_V1:
        raise TechnicalRiskValidationCandidateEvaluationError("Candidate inventory mismatch.")
    return ordered


def _validate_request_against_contracts(
    request: TechnicalRiskValidationCandidateEvaluationRequest,
    methodology_version: str,
    axis_set: TechnicalRiskV1ThresholdAxisSet,
    candidates: tuple[TechnicalRiskRuleCandidateSpec, ...],
) -> None:
    if request.methodology_version != methodology_version:
        raise TechnicalRiskValidationCandidateEvaluationError("methodology_version mismatch.")
    if request.axis_set_version != axis_set.axis_set_version:
        raise TechnicalRiskValidationCandidateEvaluationError("axis_set_version mismatch.")
    if request.candidate_ids != tuple(candidate.policy_candidate_id for candidate in candidates):
        raise TechnicalRiskValidationCandidateEvaluationError("candidate_ids mismatch.")


def _validate_validation_dataset(dataset: TechnicalRiskOOSDatasetResult) -> None:
    rows = tuple(dataset.included_rows)
    if not rows:
        raise TechnicalRiskValidationCandidateEvaluationError("VALIDATION dataset must not be empty.")
    roles = {row.split_role for row in rows}
    if roles != {TechnicalRiskOOSSplitRole.VALIDATION}:
        raise TechnicalRiskValidationCandidateEvaluationError("Dataset must contain VALIDATION rows only.")
    if any(row.evaluation_date < date(2022, 1, 1) or row.evaluation_date > date(2023, 12, 31) for row in rows):
        raise TechnicalRiskValidationCandidateEvaluationError("Dataset contains non-VALIDATION dates.")


def _record_from_evaluation(
    evaluation: TechnicalRiskCandidateEvaluationResult,
) -> TechnicalRiskValidationCandidateEvaluationRecord:
    return TechnicalRiskValidationCandidateEvaluationRecord(
        evaluation_id=evaluation.evaluation_id,
        evaluation_checksum=evaluation.evaluation_checksum,
        candidate_id=evaluation.candidate_id,
        candidate_version=evaluation.candidate_version,
        candidate_structural_checksum=evaluation.candidate_structural_checksum,
        threshold_set_id=evaluation.threshold_set_id,
        threshold_set_version=evaluation.threshold_set_version,
        threshold_set_checksum=evaluation.threshold_set_checksum,
        evaluated_row_count=evaluation.evaluated_row_count
        if evaluation.evaluated_row_count is not None
        else len(evaluation.row_evaluations),
        aggregate_metrics=evaluation.aggregate_metrics,
        monotonicity_results=evaluation.monotonicity_results,
    )


def _candidate_summaries(
    records: tuple[TechnicalRiskValidationCandidateEvaluationRecord, ...],
) -> tuple[TechnicalRiskValidationCandidateSummary, ...]:
    candidate_ids = tuple(sorted({record.candidate_id for record in records}))
    summaries = []
    for candidate_id in candidate_ids:
        candidate_records = tuple(record for record in records if record.candidate_id == candidate_id)
        statuses = Counter(result.status.value for record in candidate_records for result in record.monotonicity_results)
        summaries.append(
            TechnicalRiskValidationCandidateSummary(
                candidate_id=candidate_id,
                evaluation_count=len(candidate_records),
                monotonicity_status_counts=dict(sorted(statuses.items())),
            )
        )
    return tuple(summaries)


def _build_result(
    request: TechnicalRiskValidationCandidateEvaluationRequest,
    dataset: TechnicalRiskOOSDatasetResult,
    axis_set: TechnicalRiskV1ThresholdAxisSet,
    grid_result: TechnicalRiskThresholdGridResult,
    candidates: tuple[TechnicalRiskRuleCandidateSpec, ...],
    records: tuple[TechnicalRiskValidationCandidateEvaluationRecord, ...],
    summaries: tuple[TechnicalRiskValidationCandidateSummary, ...],
    materialization_result: TechnicalRiskRealOOSDatasetMaterializationResult,
) -> TechnicalRiskValidationCandidateEvaluationResult:
    candidate_identities = tuple(
        (candidate.policy_candidate_id, candidate.candidate_version, candidate.candidate_structural_checksum)
        for candidate in candidates
    )
    threshold_identities = tuple(
        (threshold.threshold_set_id, threshold.threshold_set_checksum)
        for threshold in grid_result.threshold_sets
    )
    checksum_payload = {
        "result_version": TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_RESULT_V1,
        "orchestrator_version": request.orchestrator_version,
        "methodology_version": request.methodology_version,
        "split_role": TechnicalRiskOOSSplitRole.VALIDATION.value,
        "split_id": "technical_risk_v1_validation_2022_2023",
        "validation_start_date": request.validation_start_date.isoformat(),
        "validation_end_date": request.validation_end_date.isoformat(),
        "dataset_id": dataset.dataset_id,
        "dataset_checksum": dataset.dataset_checksum,
        "source_snapshot_id": request.source_snapshot_id,
        "source_snapshot_checksum": request.source_snapshot_checksum,
        "axis_set_id": axis_set.axis_set_id,
        "axis_set_checksum": axis_set.axis_set_checksum,
        "threshold_grid_result_id": grid_result.grid_result_id,
        "threshold_grid_result_checksum": grid_result.grid_result_checksum,
        "candidate_identities": candidate_identities,
        "threshold_identities": threshold_identities,
        "evaluation_records": [_record_payload(record) for record in records],
        "candidate_summaries": [_summary_payload(summary) for summary in summaries],
    }
    checksum = _stable_hash(checksum_payload)
    result_id = _stable_id("technical_risk_validation_candidate_evaluation", {"result_checksum": checksum})
    return TechnicalRiskValidationCandidateEvaluationResult(
        result_id=result_id,
        result_version=TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_RESULT_V1,
        result_checksum=checksum,
        orchestrator_version=request.orchestrator_version,
        methodology_version=request.methodology_version,
        split_role=TechnicalRiskOOSSplitRole.VALIDATION,
        split_id="technical_risk_v1_validation_2022_2023",
        validation_start_date=request.validation_start_date,
        validation_end_date=request.validation_end_date,
        dataset_id=dataset.dataset_id,
        dataset_checksum=dataset.dataset_checksum,
        validation_row_count=materialization_result.split_counts["validation"],
        source_snapshot_id=request.source_snapshot_id,
        source_snapshot_checksum=request.source_snapshot_checksum,
        axis_set_id=axis_set.axis_set_id,
        axis_set_checksum=axis_set.axis_set_checksum,
        threshold_grid_result_id=grid_result.grid_result_id,
        threshold_grid_result_checksum=grid_result.grid_result_checksum,
        candidate_count=len(candidates),
        threshold_set_count=len(grid_result.threshold_sets),
        evaluation_count=len(records),
        dataset_materialization_count=1,
        candidate_identities=candidate_identities,
        threshold_identities=threshold_identities,
        evaluation_records=records,
        candidate_summaries=summaries,
    )


def _record_payload(record: TechnicalRiskValidationCandidateEvaluationRecord) -> dict[str, object]:
    return {
        "evaluation_id": record.evaluation_id,
        "evaluation_checksum": record.evaluation_checksum,
        "candidate_id": record.candidate_id,
        "candidate_version": record.candidate_version,
        "candidate_structural_checksum": record.candidate_structural_checksum,
        "threshold_set_id": record.threshold_set_id,
        "threshold_set_version": record.threshold_set_version,
        "threshold_set_checksum": record.threshold_set_checksum,
        "evaluated_row_count": record.evaluated_row_count,
        "aggregate_metrics": [_metric_payload(metric) for metric in record.aggregate_metrics],
        "monotonicity_results": [_monotonicity_payload(result) for result in record.monotonicity_results],
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


def _summary_payload(summary: TechnicalRiskValidationCandidateSummary) -> dict[str, object]:
    return {
        "candidate_id": summary.candidate_id,
        "evaluation_count": summary.evaluation_count,
        "monotonicity_status_counts": dict(summary.monotonicity_status_counts),
    }


def _normalize_symbols(symbols: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(symbols)
    if not normalized:
        raise TechnicalRiskValidationCandidateEvaluationError("symbols must not be empty.")
    if len(set(normalized)) != len(normalized):
        raise TechnicalRiskValidationCandidateEvaluationError("Duplicate symbol.")
    for symbol in normalized:
        _require_text(symbol, "symbol")
    return tuple(sorted(normalized))


def _require_version(actual: object, expected: str, field_name: str) -> None:
    if actual != expected:
        raise TechnicalRiskValidationCandidateEvaluationError(f"Unsupported {field_name}.")


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskValidationCandidateEvaluationError(f"{field_name} must be a non-empty string.")


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(value: object) -> object:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
