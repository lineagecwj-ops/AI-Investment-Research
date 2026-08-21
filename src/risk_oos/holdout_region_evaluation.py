from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
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
from risk_oos.candidate_evaluator import TechnicalRiskCandidateEvaluator
from risk_oos.candidate_evaluator import TechnicalRiskMonotonicityResult
from risk_oos.candidate_evaluator import TechnicalRiskSeverityMAEMetrics
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionConfirmationContract
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionConfirmationError
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionConfirmationStatus
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionEvidenceHorizon
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionSeparationEvidence
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionSeverityEvidence
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionSummary
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionThresholdResult
from risk_oos.holdout_region_confirmation import build_technical_risk_v1_holdout_region_confirmation_contract
from risk_oos.real_oos_materialization import TechnicalRiskRealOOSDatasetMaterializationRequest
from risk_oos.real_oos_materialization import TechnicalRiskRealOOSDatasetMaterializationResult
from risk_oos.real_oos_materialization import TechnicalRiskRealOOSDatasetMaterializer
from risk_oos.rule_candidates import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos.rule_candidates import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_oos.rule_candidates import TechnicalRiskCandidateSeverity
from risk_oos.rule_candidates import TechnicalRiskRuleCandidateSpec
from risk_oos.rule_candidates import TechnicalRiskThresholdSet
from risk_oos.rule_candidates import technical_risk_candidate_c_spec
from risk_oos.temporal_split_methodology import TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1
from risk_oos.temporal_split_methodology import build_technical_risk_v1_temporal_split_methodology
from risk_oos.threshold_axis_set import TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1
from risk_oos.threshold_axis_set import build_technical_risk_v1_threshold_axis_set
from risk_oos.threshold_axis_set import materialize_technical_risk_v1_threshold_grid


TECH_RISK_HOLDOUT_REGION_EVALUATION_REQUEST_V1 = "TECH_RISK_HOLDOUT_REGION_EVALUATION_REQUEST_V1"
TECH_RISK_HOLDOUT_REGION_EVALUATION_RESULT_V1 = "TECH_RISK_HOLDOUT_REGION_EVALUATION_RESULT_V1"
TECH_RISK_HOLDOUT_REGION_EVALUATOR_V1 = "TECH_RISK_HOLDOUT_REGION_EVALUATOR_V1"
TECH_RISK_HOLDOUT_REGION_DATASET_SPEC_ID_V1 = "technical_risk_v1_holdout_region_evaluation_dataset"
TECH_RISK_HOLDOUT_REGION_DATASET_SPEC_VERSION_V1 = "v1"

TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1 = (
    "technical_risk_threshold_set_8a5c8f1fb26eb80f",
    "technical_risk_threshold_set_4cd88bcbc8f3efc1",
    "technical_risk_threshold_set_10fa0d2aabde5743",
    "technical_risk_threshold_set_4c59c6e723d5628e",
    "technical_risk_threshold_set_d86eac8ad4255a6c",
    "technical_risk_threshold_set_1d88fe882dd0b589",
    "technical_risk_threshold_set_115fe63e0179ab90",
    "technical_risk_threshold_set_63510232941323ad",
    "technical_risk_threshold_set_c4ea7184755a000f",
    "technical_risk_threshold_set_dc1106864b012c24",
    "technical_risk_threshold_set_7c4236de0627001f",
    "technical_risk_threshold_set_854cd447f9aa828e",
    "technical_risk_threshold_set_56bb1bbeddba04b8",
    "technical_risk_threshold_set_70e1fec8fea244d5",
    "technical_risk_threshold_set_83e233a459515c5b",
    "technical_risk_threshold_set_337db20971075dd0",
    "technical_risk_threshold_set_0a8d0a32a15441ef",
    "technical_risk_threshold_set_5f6582ed6c24d942",
    "technical_risk_threshold_set_bebad70d8f57c79e",
    "technical_risk_threshold_set_354476dfe474f660",
    "technical_risk_threshold_set_eb39155baab6b217",
    "technical_risk_threshold_set_927341059e0909b6",
    "technical_risk_threshold_set_aec7eadbb9f8f6d1",
    "technical_risk_threshold_set_0f8be84a28cf54b9",
    "technical_risk_threshold_set_aa85c79c46f35895",
    "technical_risk_threshold_set_6761517925267b8f",
    "technical_risk_threshold_set_8bf9aff4820a3433",
    "technical_risk_threshold_set_7c4ce76b685a6c8d",
    "technical_risk_threshold_set_0d0ea3c7cdd25416",
    "technical_risk_threshold_set_29b452d797e5d645",
    "technical_risk_threshold_set_9e3f62aec09887fe",
    "technical_risk_threshold_set_342d20ff9cdf509a",
    "technical_risk_threshold_set_37f49bd798332c5d",
    "technical_risk_threshold_set_ef9913e907beb7b1",
    "technical_risk_threshold_set_b818b0f3e69120a2",
    "technical_risk_threshold_set_b88fa112454e7a1e",
    "technical_risk_threshold_set_5412184e3429975a",
    "technical_risk_threshold_set_e007d14f6fc9e7c3",
    "technical_risk_threshold_set_7cd202bc5662aee5",
    "technical_risk_threshold_set_de030a70b504d74c",
    "technical_risk_threshold_set_41faeb8c0d61e5c2",
    "technical_risk_threshold_set_2bd48857d2e54206",
    "technical_risk_threshold_set_cb9b1b57002621b9",
    "technical_risk_threshold_set_5234ab2a4b4b59a5",
    "technical_risk_threshold_set_c39c2a16bec86f88",
    "technical_risk_threshold_set_833944d89316cbba",
    "technical_risk_threshold_set_d5fba5e3bbb17b26",
    "technical_risk_threshold_set_e08b21051f7893a1",
    "technical_risk_threshold_set_93cce986bdb3ed84",
    "technical_risk_threshold_set_fe8c7848d5be1c0c",
    "technical_risk_threshold_set_5303b8acbd61353a",
    "technical_risk_threshold_set_41724c31422f5e4c",
    "technical_risk_threshold_set_1615c3df5b73c11f",
    "technical_risk_threshold_set_1a4111d8b03b8432",
    "technical_risk_threshold_set_eb286645caa97a12",
    "technical_risk_threshold_set_6f99ee72efbc5c2e",
    "technical_risk_threshold_set_2f21c2fd9f7078e4",
    "technical_risk_threshold_set_bd312c802f6771b1",
    "technical_risk_threshold_set_17c0305360e76c25",
    "technical_risk_threshold_set_68418ac92f5bf18c",
    "technical_risk_threshold_set_5fa55d18b5ad2154",
    "technical_risk_threshold_set_f02f44b3229023f9",
    "technical_risk_threshold_set_ef0ec04b2dbad6fc",
    "technical_risk_threshold_set_521557929c005b28",
    "technical_risk_threshold_set_29d87a0c65bafa44",
    "technical_risk_threshold_set_ef98a2d4308ec440",
    "technical_risk_threshold_set_94fdbbde9d3951bd",
    "technical_risk_threshold_set_3c45f3bd36f6a50f",
    "technical_risk_threshold_set_0eef124d07ca809d",
)


class TechnicalRiskHoldoutRegionEvaluationError(Exception):
    """Raised when Holdout region evaluation cannot safely continue."""


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionEvaluationRequest:
    """Explicit request for frozen Candidate C robust-region Holdout evaluation."""

    request_version: str
    research_db_path: Path | str
    research_manifest_path: Path | str
    source_snapshot_id: str
    source_snapshot_checksum: str
    symbols: tuple[str, ...]
    contract_id: str
    contract_version: str
    candidate_id: str
    region_id: str
    threshold_set_ids: tuple[str, ...]
    methodology_version: str
    axis_set_version: str
    holdout_start_date: date
    holdout_end_date: date
    dataset_spec_id: str = TECH_RISK_HOLDOUT_REGION_DATASET_SPEC_ID_V1
    dataset_spec_version: str = TECH_RISK_HOLDOUT_REGION_DATASET_SPEC_VERSION_V1
    feature_set_id: str = TECHNICAL_RISK_V1_FEATURE_SET_ID
    evaluator_version: str = TECH_RISK_HOLDOUT_REGION_EVALUATOR_V1

    def __post_init__(self) -> None:
        _require_version(self.request_version, TECH_RISK_HOLDOUT_REGION_EVALUATION_REQUEST_V1, "request_version")
        object.__setattr__(self, "research_db_path", Path(self.research_db_path))
        object.__setattr__(self, "research_manifest_path", Path(self.research_manifest_path))
        object.__setattr__(self, "symbols", _normalize_symbols(self.symbols))
        _require_text(self.source_snapshot_id, "source_snapshot_id")
        _require_text(self.source_snapshot_checksum, "source_snapshot_checksum")
        _require_text(self.contract_id, "contract_id")
        _require_version(self.contract_version, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1, "contract_version")
        _require_version(self.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID, "candidate_id")
        _require_version(self.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID, "region_id")
        if tuple(self.threshold_set_ids) != TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1:
            raise TechnicalRiskHoldoutRegionEvaluationError("threshold_set_ids must match the frozen robust region.")
        _require_version(self.methodology_version, TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1, "methodology_version")
        _require_version(self.axis_set_version, TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1, "axis_set_version")
        if self.holdout_start_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE:
            raise TechnicalRiskHoldoutRegionEvaluationError("holdout_start_date mismatch.")
        if self.holdout_end_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE:
            raise TechnicalRiskHoldoutRegionEvaluationError("holdout_end_date mismatch.")
        _require_text(self.dataset_spec_id, "dataset_spec_id")
        _require_text(self.dataset_spec_version, "dataset_spec_version")
        _require_version(self.feature_set_id, TECHNICAL_RISK_V1_FEATURE_SET_ID, "feature_set_id")
        _require_version(self.evaluator_version, TECH_RISK_HOLDOUT_REGION_EVALUATOR_V1, "evaluator_version")


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionThresholdEvaluationRecord:
    """One frozen threshold result for Candidate C on the Holdout split."""

    evaluation_id: str
    evaluation_checksum: str
    evaluated_row_count: int
    threshold_result: TechnicalRiskHoldoutRegionThresholdResult
    warning_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.evaluation_id, "evaluation_id")
        _require_text(self.evaluation_checksum, "evaluation_checksum")
        if self.evaluated_row_count < 0:
            raise TechnicalRiskHoldoutRegionEvaluationError("evaluated_row_count cannot be negative.")
        if not isinstance(self.threshold_result, TechnicalRiskHoldoutRegionThresholdResult):
            raise TechnicalRiskHoldoutRegionEvaluationError("threshold_result type mismatch.")
        object.__setattr__(self, "warning_codes", tuple(self.warning_codes))


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionEvaluationResult:
    """In-memory research-side Holdout evidence for one frozen robust region."""

    result_id: str
    result_version: str
    result_checksum: str
    evaluator_version: str
    contract_id: str
    contract_version: str
    split_role: TechnicalRiskOOSSplitRole
    split_id: str
    holdout_start_date: date
    holdout_end_date: date
    dataset_id: str
    dataset_checksum: str
    holdout_row_count: int
    source_snapshot_id: str
    source_snapshot_checksum: str
    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str
    region_id: str
    threshold_count: int
    evaluation_count: int
    dataset_materialization_count: int
    threshold_identities: tuple[tuple[str, str], ...]
    threshold_records: tuple[TechnicalRiskHoldoutRegionThresholdEvaluationRecord, ...]
    region_summary: TechnicalRiskHoldoutRegionSummary

    def __post_init__(self) -> None:
        _require_text(self.result_id, "result_id")
        _require_version(self.result_version, TECH_RISK_HOLDOUT_REGION_EVALUATION_RESULT_V1, "result_version")
        _require_text(self.result_checksum, "result_checksum")
        _require_version(self.evaluator_version, TECH_RISK_HOLDOUT_REGION_EVALUATOR_V1, "evaluator_version")
        _require_text(self.contract_id, "contract_id")
        _require_version(self.contract_version, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1, "contract_version")
        if self.split_role != TechnicalRiskOOSSplitRole.HOLDOUT:
            raise TechnicalRiskHoldoutRegionEvaluationError("split_role must be HOLDOUT.")
        if self.holdout_start_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE:
            raise TechnicalRiskHoldoutRegionEvaluationError("holdout_start_date mismatch.")
        if self.holdout_end_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE:
            raise TechnicalRiskHoldoutRegionEvaluationError("holdout_end_date mismatch.")
        _require_text(self.dataset_id, "dataset_id")
        _require_text(self.dataset_checksum, "dataset_checksum")
        _require_text(self.source_snapshot_id, "source_snapshot_id")
        _require_text(self.source_snapshot_checksum, "source_snapshot_checksum")
        _require_version(self.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID, "candidate_id")
        _require_version(self.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID, "region_id")
        if self.threshold_count != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
            raise TechnicalRiskHoldoutRegionEvaluationError("threshold_count mismatch.")
        records = tuple(self.threshold_records)
        if self.evaluation_count != len(records):
            raise TechnicalRiskHoldoutRegionEvaluationError("evaluation_count mismatch.")
        if self.evaluation_count != self.threshold_count:
            raise TechnicalRiskHoldoutRegionEvaluationError("Holdout region evaluation must cover every frozen threshold.")
        if self.dataset_materialization_count != 1:
            raise TechnicalRiskHoldoutRegionEvaluationError("dataset must be materialized exactly once.")
        if tuple(identity[0] for identity in self.threshold_identities) != TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1:
            raise TechnicalRiskHoldoutRegionEvaluationError("threshold identity ordering mismatch.")
        if self.region_summary.total_threshold_count != self.threshold_count:
            raise TechnicalRiskHoldoutRegionEvaluationError("region summary threshold count mismatch.")
        object.__setattr__(self, "threshold_records", records)
        object.__setattr__(self, "threshold_identities", tuple(self.threshold_identities))


class TechnicalRiskHoldoutRegionEvaluator:
    """Executes frozen Candidate C robust-region evaluation on the HOLDOUT split only."""

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
        request: TechnicalRiskHoldoutRegionEvaluationRequest,
        *,
        contract: TechnicalRiskHoldoutRegionConfirmationContract | None = None,
    ) -> TechnicalRiskHoldoutRegionEvaluationResult:
        contract = contract or build_technical_risk_v1_holdout_region_confirmation_contract()
        _validate_request_against_contract(request, contract)
        methodology = build_technical_risk_v1_temporal_split_methodology()
        axis_set = build_technical_risk_v1_threshold_axis_set()
        grid_result = materialize_technical_risk_v1_threshold_grid()
        candidate = technical_risk_candidate_c_spec()
        if candidate.policy_candidate_id != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID:
            raise TechnicalRiskHoldoutRegionEvaluationError("Candidate C contract mismatch.")
        if request.methodology_version != methodology.methodology_version:
            raise TechnicalRiskHoldoutRegionEvaluationError("methodology_version mismatch.")
        if request.axis_set_version != axis_set.axis_set_version:
            raise TechnicalRiskHoldoutRegionEvaluationError("axis_set_version mismatch.")
        thresholds = _frozen_region_thresholds(grid_result.threshold_sets)
        materialization_result = self._materialize_holdout_dataset(request, methodology.split_specs)
        dataset = materialization_result.oos_dataset_result
        _validate_holdout_dataset(dataset)
        records = tuple(
            self._evaluate_threshold(dataset, candidate, threshold)
            for threshold in thresholds
        )
        summary = _region_summary(records)
        return _build_result(request, contract, dataset, candidate, thresholds, records, summary, materialization_result)

    def _materialize_holdout_dataset(
        self,
        request: TechnicalRiskHoldoutRegionEvaluationRequest,
        split_specs,
    ) -> TechnicalRiskRealOOSDatasetMaterializationResult:
        materialization_request = TechnicalRiskRealOOSDatasetMaterializationRequest(
            research_db_path=request.research_db_path,
            research_manifest_path=request.research_manifest_path,
            source_snapshot_id=request.source_snapshot_id,
            source_snapshot_checksum=request.source_snapshot_checksum,
            symbols=request.symbols,
            analysis_start_date=request.holdout_start_date,
            analysis_end_date=request.holdout_end_date,
            split_specs=split_specs,
            dataset_spec_id=request.dataset_spec_id,
            dataset_spec_version=request.dataset_spec_version,
            feature_set_id=request.feature_set_id,
            required_output_split_roles=(TechnicalRiskOOSSplitRole.HOLDOUT,),
        )
        return self._dataset_materializer.materialize(materialization_request)

    def _evaluate_threshold(
        self,
        dataset: TechnicalRiskOOSDatasetResult,
        candidate: TechnicalRiskRuleCandidateSpec,
        threshold: TechnicalRiskThresholdSet,
    ) -> TechnicalRiskHoldoutRegionThresholdEvaluationRecord:
        evaluation_input = TechnicalRiskCandidateEvaluationInput(
            evaluation_input_version=TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1,
            dataset_id=dataset.dataset_id,
            dataset_checksum=dataset.dataset_checksum,
            candidate_id=candidate.policy_candidate_id,
            candidate_version=candidate.candidate_version,
            candidate_structural_checksum=candidate.candidate_structural_checksum,
            threshold_set_id=threshold.threshold_set_id,
            threshold_set_version=threshold.threshold_set_version,
            threshold_set_checksum=threshold.threshold_set_checksum,
            derived_evidence_version=TECH_RISK_DERIVED_EVIDENCE_V1,
            evaluator_version=TECH_RISK_CANDIDATE_EVALUATOR_V1,
            metric_version=TECH_RISK_CONTINUOUS_MAE_METRIC_V1,
            quantile_version=TECH_RISK_QUANTILE_NEAREST_RANK_V1,
            numeric_context_version=TECH_RISK_DECIMAL_CONTEXT_V1,
            allowed_split_roles=(TechnicalRiskOOSSplitRole.HOLDOUT,),
        )
        evaluate = getattr(self._candidate_evaluator, "evaluate_compact", self._candidate_evaluator.evaluate)
        evaluation = evaluate(dataset, candidate, threshold, evaluation_input)
        return _threshold_record_from_evaluation(evaluation)


def build_technical_risk_v1_holdout_region_evaluation_request(
    *,
    research_db_path: Path | str,
    research_manifest_path: Path | str,
    source_snapshot_id: str,
    source_snapshot_checksum: str,
    symbols: tuple[str, ...],
    contract: TechnicalRiskHoldoutRegionConfirmationContract | None = None,
) -> TechnicalRiskHoldoutRegionEvaluationRequest:
    contract = contract or build_technical_risk_v1_holdout_region_confirmation_contract()
    return TechnicalRiskHoldoutRegionEvaluationRequest(
        request_version=TECH_RISK_HOLDOUT_REGION_EVALUATION_REQUEST_V1,
        research_db_path=research_db_path,
        research_manifest_path=research_manifest_path,
        source_snapshot_id=source_snapshot_id,
        source_snapshot_checksum=source_snapshot_checksum,
        symbols=symbols,
        contract_id=contract.contract_id,
        contract_version=contract.contract_version,
        candidate_id=contract.candidate_id,
        region_id=contract.robust_region_id,
        threshold_set_ids=TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1,
        methodology_version=TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1,
        axis_set_version=TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1,
        holdout_start_date=contract.holdout_start_date,
        holdout_end_date=contract.holdout_end_date,
    )


def build_default_research_holdout_region_evaluation_request() -> TechnicalRiskHoldoutRegionEvaluationRequest:
    store = ResearchDataStore(verify_default_runtime=False)
    return build_technical_risk_v1_holdout_region_evaluation_request(
        research_db_path=store.resolved_db_path,
        research_manifest_path=store.resolved_manifest_path,
        source_snapshot_id=store.resolved_research_snapshot_id,
        source_snapshot_checksum=store.resolved_semantic_checksum,
        symbols=store.materialized_twse_common_stock_symbols(),
    )


def _validate_request_against_contract(
    request: TechnicalRiskHoldoutRegionEvaluationRequest,
    contract: TechnicalRiskHoldoutRegionConfirmationContract,
) -> None:
    if request.contract_id != contract.contract_id:
        raise TechnicalRiskHoldoutRegionEvaluationError("contract_id mismatch.")
    if request.contract_version != contract.contract_version:
        raise TechnicalRiskHoldoutRegionEvaluationError("contract_version mismatch.")
    if request.candidate_id != contract.candidate_id:
        raise TechnicalRiskHoldoutRegionEvaluationError("candidate_id mismatch.")
    if request.region_id != contract.robust_region_id:
        raise TechnicalRiskHoldoutRegionEvaluationError("region_id mismatch.")
    if request.holdout_start_date != contract.holdout_start_date:
        raise TechnicalRiskHoldoutRegionEvaluationError("holdout_start_date mismatch.")
    if request.holdout_end_date != contract.holdout_end_date:
        raise TechnicalRiskHoldoutRegionEvaluationError("holdout_end_date mismatch.")


def _frozen_region_thresholds(
    threshold_sets: tuple[TechnicalRiskThresholdSet, ...],
) -> tuple[TechnicalRiskThresholdSet, ...]:
    by_id = {threshold.threshold_set_id: threshold for threshold in threshold_sets}
    try:
        thresholds = tuple(by_id[threshold_id] for threshold_id in TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1)
    except KeyError as exc:
        raise TechnicalRiskHoldoutRegionEvaluationError("Frozen region threshold set missing from grid.") from exc
    if len(thresholds) != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
        raise TechnicalRiskHoldoutRegionEvaluationError("Frozen region threshold count mismatch.")
    return thresholds


def _validate_holdout_dataset(dataset: TechnicalRiskOOSDatasetResult) -> None:
    rows = tuple(dataset.included_rows)
    if not rows:
        raise TechnicalRiskHoldoutRegionEvaluationError("HOLDOUT dataset must not be empty.")
    roles = {row.split_role for row in rows}
    if roles != {TechnicalRiskOOSSplitRole.HOLDOUT}:
        raise TechnicalRiskHoldoutRegionEvaluationError("Dataset must contain HOLDOUT rows only.")
    if any(
        row.evaluation_date < TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE
        or row.evaluation_date > TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE
        for row in rows
    ):
        raise TechnicalRiskHoldoutRegionEvaluationError("Dataset contains non-HOLDOUT dates.")


def _threshold_record_from_evaluation(evaluation) -> TechnicalRiskHoldoutRegionThresholdEvaluationRecord:
    severity_evidence = tuple(_severity_evidence(metric) for metric in evaluation.aggregate_metrics)
    monotonicity_by_horizon = {result.horizon: result for result in evaluation.monotonicity_results}
    mae20 = monotonicity_by_horizon[20]
    mae60 = monotonicity_by_horizon[60]
    threshold_result = TechnicalRiskHoldoutRegionThresholdResult(
        threshold_set_id=evaluation.threshold_set_id,
        threshold_checksum=evaluation.threshold_set_checksum,
        candidate_id=evaluation.candidate_id,
        region_id=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID,
        severity_evidence=severity_evidence,
        mae20_monotonicity_status=mae20.status.value,
        mae60_monotonicity_status=mae60.status.value,
        mae20_separation_evidence=_separation_evidence(TechnicalRiskHoldoutRegionEvidenceHorizon.MAE20, mae20),
        mae60_separation_evidence=_separation_evidence(TechnicalRiskHoldoutRegionEvidenceHorizon.MAE60, mae60),
        confirmation_status=TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED,
    )
    return TechnicalRiskHoldoutRegionThresholdEvaluationRecord(
        evaluation_id=evaluation.evaluation_id,
        evaluation_checksum=evaluation.evaluation_checksum,
        evaluated_row_count=evaluation.evaluated_row_count,
        threshold_result=threshold_result,
        warning_codes=_warning_codes(evaluation.aggregate_metrics),
    )


def _severity_evidence(metric: TechnicalRiskSeverityMAEMetrics) -> TechnicalRiskHoldoutRegionSeverityEvidence:
    return TechnicalRiskHoldoutRegionSeverityEvidence(
        severity=metric.severity,
        coverage_ratio=metric.coverage_ratio,
        sample_count=metric.sample_count,
        mae20_mean=metric.mae20_mean,
        mae20_median=metric.mae20_median,
        mae20_p25=metric.mae20_p25,
        mae20_p75=metric.mae20_p75,
        mae60_mean=metric.mae60_mean,
        mae60_median=metric.mae60_median,
        mae60_p25=metric.mae60_p25,
        mae60_p75=metric.mae60_p75,
    )


def _separation_evidence(
    horizon: TechnicalRiskHoldoutRegionEvidenceHorizon,
    monotonicity: TechnicalRiskMonotonicityResult,
) -> TechnicalRiskHoldoutRegionSeparationEvidence:
    return TechnicalRiskHoldoutRegionSeparationEvidence(
        horizon=horizon,
        high_minus_low=_optional_difference(monotonicity.high_median, monotonicity.low_median),
        high_minus_medium=_optional_difference(monotonicity.high_median, monotonicity.medium_median),
        medium_minus_low=_optional_difference(monotonicity.medium_median, monotonicity.low_median),
    )


def _optional_difference(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None or right is None:
        return None
    return left - right


def _warning_codes(metrics: tuple[TechnicalRiskSeverityMAEMetrics, ...]) -> tuple[str, ...]:
    warnings = []
    if any(metric.sample_count == 0 for metric in metrics):
        warnings.append("EMPTY_BUCKET")
    if any(metric.mae20_median is None or metric.mae60_median is None for metric in metrics):
        warnings.append("INSUFFICIENT_EVIDENCE")
    return tuple(warnings)


def _region_summary(
    records: tuple[TechnicalRiskHoldoutRegionThresholdEvaluationRecord, ...],
) -> TechnicalRiskHoldoutRegionSummary:
    statuses = Counter(record.threshold_result.confirmation_status.value for record in records)
    return TechnicalRiskHoldoutRegionSummary(
        region_id=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID,
        candidate_id=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID,
        total_threshold_count=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT,
        confirmed_threshold_count=statuses.get(TechnicalRiskHoldoutRegionConfirmationStatus.CONFIRMED.value, 0),
        not_confirmed_threshold_count=statuses.get(TechnicalRiskHoldoutRegionConfirmationStatus.NOT_CONFIRMED.value, 0),
        review_required_threshold_count=statuses.get(TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED.value, 0),
        monotonicity_stability_summary=_monotonicity_stability(records),
        separation_stability_summary=_separation_stability(records),
        coverage_stability_summary=_coverage_stability(records),
    )


def _monotonicity_stability(records: tuple[TechnicalRiskHoldoutRegionThresholdEvaluationRecord, ...]) -> Mapping[str, int]:
    counter = Counter()
    for record in records:
        counter[f"MAE20_{record.threshold_result.mae20_monotonicity_status}"] += 1
        counter[f"MAE60_{record.threshold_result.mae60_monotonicity_status}"] += 1
    return dict(sorted(counter.items()))


def _separation_stability(records: tuple[TechnicalRiskHoldoutRegionThresholdEvaluationRecord, ...]) -> Mapping[str, int]:
    counter = Counter()
    for record in records:
        if record.threshold_result.mae20_separation_evidence.high_minus_low is not None:
            counter["MAE20_HIGH_MINUS_LOW_AVAILABLE"] += 1
        if record.threshold_result.mae60_separation_evidence.high_minus_low is not None:
            counter["MAE60_HIGH_MINUS_LOW_AVAILABLE"] += 1
    return dict(sorted(counter.items()))


def _coverage_stability(records: tuple[TechnicalRiskHoldoutRegionThresholdEvaluationRecord, ...]) -> Mapping[str, int]:
    counter = Counter()
    for record in records:
        for evidence in record.threshold_result.severity_evidence:
            key = f"{evidence.severity.value}_NON_EMPTY" if evidence.sample_count > 0 else f"{evidence.severity.value}_EMPTY"
            counter[key] += 1
    return dict(sorted(counter.items()))


def _build_result(
    request: TechnicalRiskHoldoutRegionEvaluationRequest,
    contract: TechnicalRiskHoldoutRegionConfirmationContract,
    dataset: TechnicalRiskOOSDatasetResult,
    candidate: TechnicalRiskRuleCandidateSpec,
    thresholds: tuple[TechnicalRiskThresholdSet, ...],
    records: tuple[TechnicalRiskHoldoutRegionThresholdEvaluationRecord, ...],
    summary: TechnicalRiskHoldoutRegionSummary,
    materialization_result: TechnicalRiskRealOOSDatasetMaterializationResult,
) -> TechnicalRiskHoldoutRegionEvaluationResult:
    threshold_identities = tuple((threshold.threshold_set_id, threshold.threshold_set_checksum) for threshold in thresholds)
    payload = {
        "result_version": TECH_RISK_HOLDOUT_REGION_EVALUATION_RESULT_V1,
        "evaluator_version": request.evaluator_version,
        "contract_id": contract.contract_id,
        "contract_version": contract.contract_version,
        "split_role": TechnicalRiskOOSSplitRole.HOLDOUT.value,
        "split_id": "technical_risk_v1_holdout_2024_2025",
        "holdout_start_date": request.holdout_start_date.isoformat(),
        "holdout_end_date": request.holdout_end_date.isoformat(),
        "dataset_id": dataset.dataset_id,
        "dataset_checksum": dataset.dataset_checksum,
        "source_snapshot_id": request.source_snapshot_id,
        "source_snapshot_checksum": request.source_snapshot_checksum,
        "candidate_id": candidate.policy_candidate_id,
        "candidate_version": candidate.candidate_version,
        "candidate_structural_checksum": candidate.candidate_structural_checksum,
        "region_id": request.region_id,
        "threshold_identities": threshold_identities,
        "threshold_records": [_record_payload(record) for record in records],
        "region_summary": _summary_payload(summary),
    }
    checksum = _stable_hash(payload)
    result_id = _stable_id("technical_risk_holdout_region_evaluation", {"result_checksum": checksum})
    return TechnicalRiskHoldoutRegionEvaluationResult(
        result_id=result_id,
        result_version=TECH_RISK_HOLDOUT_REGION_EVALUATION_RESULT_V1,
        result_checksum=checksum,
        evaluator_version=request.evaluator_version,
        contract_id=contract.contract_id,
        contract_version=contract.contract_version,
        split_role=TechnicalRiskOOSSplitRole.HOLDOUT,
        split_id="technical_risk_v1_holdout_2024_2025",
        holdout_start_date=request.holdout_start_date,
        holdout_end_date=request.holdout_end_date,
        dataset_id=dataset.dataset_id,
        dataset_checksum=dataset.dataset_checksum,
        holdout_row_count=materialization_result.split_counts["holdout"],
        source_snapshot_id=request.source_snapshot_id,
        source_snapshot_checksum=request.source_snapshot_checksum,
        candidate_id=candidate.policy_candidate_id,
        candidate_version=candidate.candidate_version,
        candidate_structural_checksum=candidate.candidate_structural_checksum,
        region_id=request.region_id,
        threshold_count=len(thresholds),
        evaluation_count=len(records),
        dataset_materialization_count=1,
        threshold_identities=threshold_identities,
        threshold_records=records,
        region_summary=summary,
    )


def _record_payload(record: TechnicalRiskHoldoutRegionThresholdEvaluationRecord) -> Mapping[str, object]:
    result = record.threshold_result
    return {
        "evaluation_id": record.evaluation_id,
        "evaluation_checksum": record.evaluation_checksum,
        "evaluated_row_count": record.evaluated_row_count,
        "threshold_set_id": result.threshold_set_id,
        "threshold_checksum": result.threshold_checksum,
        "candidate_id": result.candidate_id,
        "region_id": result.region_id,
        "severity_evidence": [_severity_payload(item) for item in result.severity_evidence],
        "mae20_monotonicity_status": result.mae20_monotonicity_status,
        "mae60_monotonicity_status": result.mae60_monotonicity_status,
        "mae20_separation_evidence": _separation_payload(result.mae20_separation_evidence),
        "mae60_separation_evidence": _separation_payload(result.mae60_separation_evidence),
        "confirmation_status": result.confirmation_status.value,
        "warning_codes": record.warning_codes,
    }


def _severity_payload(evidence: TechnicalRiskHoldoutRegionSeverityEvidence) -> Mapping[str, object]:
    return {
        "severity": evidence.severity.value,
        "coverage_ratio": evidence.coverage_ratio,
        "sample_count": evidence.sample_count,
        "mae20_mean": evidence.mae20_mean,
        "mae20_median": evidence.mae20_median,
        "mae20_p25": evidence.mae20_p25,
        "mae20_p75": evidence.mae20_p75,
        "mae60_mean": evidence.mae60_mean,
        "mae60_median": evidence.mae60_median,
        "mae60_p25": evidence.mae60_p25,
        "mae60_p75": evidence.mae60_p75,
    }


def _separation_payload(evidence: TechnicalRiskHoldoutRegionSeparationEvidence) -> Mapping[str, object]:
    return {
        "horizon": evidence.horizon.value,
        "high_minus_low": evidence.high_minus_low,
        "high_minus_medium": evidence.high_minus_medium,
        "medium_minus_low": evidence.medium_minus_low,
    }


def _summary_payload(summary: TechnicalRiskHoldoutRegionSummary) -> Mapping[str, object]:
    return {
        "region_id": summary.region_id,
        "candidate_id": summary.candidate_id,
        "total_threshold_count": summary.total_threshold_count,
        "confirmed_threshold_count": summary.confirmed_threshold_count,
        "not_confirmed_threshold_count": summary.not_confirmed_threshold_count,
        "review_required_threshold_count": summary.review_required_threshold_count,
        "monotonicity_stability_summary": dict(summary.monotonicity_stability_summary),
        "separation_stability_summary": dict(summary.separation_stability_summary),
        "coverage_stability_summary": dict(summary.coverage_stability_summary),
    }


def _normalize_symbols(symbols: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(symbols)
    if not normalized:
        raise TechnicalRiskHoldoutRegionEvaluationError("symbols must not be empty.")
    if len(set(normalized)) != len(normalized):
        raise TechnicalRiskHoldoutRegionEvaluationError("Duplicate symbol.")
    for symbol in normalized:
        _require_text(symbol, "symbol")
    return tuple(sorted(normalized))


def _require_version(actual: object, expected: str, field_name: str) -> None:
    if actual != expected:
        raise TechnicalRiskHoldoutRegionEvaluationError(f"{field_name} mismatch.")


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskHoldoutRegionEvaluationError(f"{field_name} must be a non-empty string.")


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
