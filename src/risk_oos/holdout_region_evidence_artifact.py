from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
import hashlib
import json
from typing import Any
from typing import Mapping

from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_CHECKSUM
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_ID
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionConfirmationStatus
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionEvidenceHorizon
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionSeparationEvidence
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionSeverityEvidence
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionSummary
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionThresholdResult
from risk_oos.holdout_region_evaluation import TECH_RISK_HOLDOUT_REGION_EVALUATION_RESULT_V1
from risk_oos.holdout_region_evaluation import TECH_RISK_HOLDOUT_REGION_EVALUATOR_V1
from risk_oos.holdout_region_evaluation import TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1
from risk_oos.holdout_region_evaluation import TechnicalRiskHoldoutRegionEvaluationResult
from risk_oos.holdout_region_evaluation import TechnicalRiskHoldoutRegionThresholdEvaluationRecord
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1


TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_SCHEMA_V1 = (
    "TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_V1"
)
TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_CODEC_V1 = (
    "TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_CODEC_V1"
)
DEFAULT_TECH_RISK_HOLDOUT_REGION_EVIDENCE_DIR = Path(
    "data/research/technical_risk_holdout_region_evidence"
)

_ENVELOPE_FIELDS = frozenset({"schema_version", "codec_version", "artifact", "serialization_checksum"})
_ARTIFACT_FIELDS = frozenset(
    {
        "artifact_id",
        "artifact_schema_version",
        "artifact_checksum",
        "validation_evidence_artifact_id",
        "validation_evidence_artifact_checksum",
        "validation_selection_methodology_version",
        "validation_selection_decision_package_id",
        "validation_selection_decision_package_checksum",
        "holdout_evaluation_result",
    }
)
_RESULT_FIELDS = frozenset(
    {
        "result_id",
        "result_version",
        "result_checksum",
        "evaluator_version",
        "contract_id",
        "contract_version",
        "split_role",
        "split_id",
        "holdout_start_date",
        "holdout_end_date",
        "dataset_id",
        "dataset_checksum",
        "holdout_row_count",
        "source_snapshot_id",
        "source_snapshot_checksum",
        "candidate_id",
        "candidate_version",
        "candidate_structural_checksum",
        "region_id",
        "threshold_count",
        "evaluation_count",
        "dataset_materialization_count",
        "threshold_identities",
        "threshold_records",
        "region_summary",
    }
)
_RECORD_FIELDS = frozenset(
    {
        "evaluation_id",
        "evaluation_checksum",
        "evaluated_row_count",
        "threshold_set_id",
        "threshold_checksum",
        "candidate_id",
        "region_id",
        "severity_evidence",
        "mae20_monotonicity_status",
        "mae20_monotonicity_reason_code",
        "mae60_monotonicity_status",
        "mae60_monotonicity_reason_code",
        "mae20_separation_evidence",
        "mae60_separation_evidence",
        "confirmation_status",
        "warning_codes",
    }
)
_SEVERITY_FIELDS = frozenset(
    {
        "severity",
        "sample_count",
        "coverage_ratio",
        "mae20_mean",
        "mae20_median",
        "mae20_p25",
        "mae20_p75",
        "mae60_mean",
        "mae60_median",
        "mae60_p25",
        "mae60_p75",
    }
)
_SEPARATION_FIELDS = frozenset(
    {"horizon", "high_minus_low", "high_minus_medium", "medium_minus_low"}
)
_SUMMARY_FIELDS = frozenset(
    {
        "region_id",
        "candidate_id",
        "total_threshold_count",
        "confirmed_threshold_count",
        "not_confirmed_threshold_count",
        "review_required_threshold_count",
        "monotonicity_stability_summary",
        "separation_stability_summary",
        "coverage_stability_summary",
    }
)


class TechnicalRiskHoldoutRegionEvidenceArtifactError(ValueError):
    """Raised when Holdout region evidence artifacts fail closed."""


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionEvidenceArtifactSaveResult:
    artifact_id: str
    artifact_checksum: str
    path: Path
    status: str

    def __post_init__(self) -> None:
        _require_text(self.artifact_id, "artifact_id")
        _require_text(self.artifact_checksum, "artifact_checksum")
        object.__setattr__(self, "path", Path(self.path))
        if self.status not in {"INSERTED", "IDEMPOTENT"}:
            raise TechnicalRiskHoldoutRegionEvidenceArtifactError("Unsupported save status.")


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionEvidenceArtifact:
    """Research-owned immutable evidence snapshot for frozen region Holdout results."""

    artifact_id: str | None
    artifact_schema_version: str
    artifact_checksum: str | None
    validation_evidence_artifact_id: str
    validation_evidence_artifact_checksum: str
    validation_selection_methodology_version: str
    validation_selection_decision_package_id: str
    validation_selection_decision_package_checksum: str
    holdout_evaluation_result: TechnicalRiskHoldoutRegionEvaluationResult

    def __post_init__(self) -> None:
        _require_version(
            self.artifact_schema_version,
            TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_SCHEMA_V1,
            "artifact_schema_version",
        )
        _require_version(
            self.validation_evidence_artifact_id,
            TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID,
            "validation_evidence_artifact_id",
        )
        _require_version(
            self.validation_evidence_artifact_checksum,
            TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM,
            "validation_evidence_artifact_checksum",
        )
        _require_version(
            self.validation_selection_methodology_version,
            TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1,
            "validation_selection_methodology_version",
        )
        _require_version(
            self.validation_selection_decision_package_id,
            TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_ID,
            "validation_selection_decision_package_id",
        )
        _require_version(
            self.validation_selection_decision_package_checksum,
            TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_CHECKSUM,
            "validation_selection_decision_package_checksum",
        )
        if not isinstance(self.holdout_evaluation_result, TechnicalRiskHoldoutRegionEvaluationResult):
            raise TechnicalRiskHoldoutRegionEvidenceArtifactError("holdout_evaluation_result type mismatch.")
        _validate_result(self.holdout_evaluation_result)
        checksum = _artifact_checksum(self)
        artifact_id = _stable_id("technical_risk_holdout_region_evidence", {"artifact_checksum": checksum})
        if self.artifact_id is not None and self.artifact_id != artifact_id:
            raise TechnicalRiskHoldoutRegionEvidenceArtifactError("artifact_id mismatch.")
        if self.artifact_checksum is not None and self.artifact_checksum != checksum:
            raise TechnicalRiskHoldoutRegionEvidenceArtifactError("artifact_checksum mismatch.")
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_checksum", checksum)

    @classmethod
    def from_holdout_result(
        cls,
        holdout_result: TechnicalRiskHoldoutRegionEvaluationResult,
    ) -> "TechnicalRiskHoldoutRegionEvidenceArtifact":
        return cls(
            artifact_id=None,
            artifact_schema_version=TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_SCHEMA_V1,
            artifact_checksum=None,
            validation_evidence_artifact_id=TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID,
            validation_evidence_artifact_checksum=TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM,
            validation_selection_methodology_version=TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1,
            validation_selection_decision_package_id=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_ID,
            validation_selection_decision_package_checksum=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_CHECKSUM,
            holdout_evaluation_result=holdout_result,
        )


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionEvidenceArtifactCodec:
    """Strict canonical JSON codec for region-aware Holdout evidence."""

    def encode(self, artifact: TechnicalRiskHoldoutRegionEvidenceArtifact) -> str:
        if not isinstance(artifact, TechnicalRiskHoldoutRegionEvidenceArtifact):
            raise TechnicalRiskHoldoutRegionEvidenceArtifactError("encode requires Holdout region evidence artifact.")
        envelope: dict[str, Any] = {
            "schema_version": TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_SCHEMA_V1,
            "codec_version": TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_CODEC_V1,
            "artifact": _artifact_payload(artifact),
        }
        envelope["serialization_checksum"] = serialization_checksum(envelope)
        return canonical_json_dumps(envelope)

    def decode(self, payload: str) -> TechnicalRiskHoldoutRegionEvidenceArtifact:
        if not isinstance(payload, str):
            raise TechnicalRiskHoldoutRegionEvidenceArtifactError("decode requires JSON string payload.")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise TechnicalRiskHoldoutRegionEvidenceArtifactError("Artifact payload must be valid JSON.") from exc
        envelope = _require_exact_mapping(decoded, _ENVELOPE_FIELDS, "artifact envelope")
        _require_version(envelope["schema_version"], TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_SCHEMA_V1, "schema_version")
        _require_version(envelope["codec_version"], TECH_RISK_HOLDOUT_REGION_EVIDENCE_ARTIFACT_CODEC_V1, "codec_version")
        _verify_serialization_checksum(envelope)
        artifact_payload = _require_exact_mapping(envelope["artifact"], _ARTIFACT_FIELDS, "artifact payload")
        return TechnicalRiskHoldoutRegionEvidenceArtifact(
            artifact_id=_require_text(artifact_payload["artifact_id"], "artifact_id"),
            artifact_schema_version=_require_text(artifact_payload["artifact_schema_version"], "artifact_schema_version"),
            artifact_checksum=_require_text(artifact_payload["artifact_checksum"], "artifact_checksum"),
            validation_evidence_artifact_id=_require_text(artifact_payload["validation_evidence_artifact_id"], "validation_evidence_artifact_id"),
            validation_evidence_artifact_checksum=_require_text(artifact_payload["validation_evidence_artifact_checksum"], "validation_evidence_artifact_checksum"),
            validation_selection_methodology_version=_require_text(artifact_payload["validation_selection_methodology_version"], "validation_selection_methodology_version"),
            validation_selection_decision_package_id=_require_text(artifact_payload["validation_selection_decision_package_id"], "validation_selection_decision_package_id"),
            validation_selection_decision_package_checksum=_require_text(artifact_payload["validation_selection_decision_package_checksum"], "validation_selection_decision_package_checksum"),
            holdout_evaluation_result=_decode_result(artifact_payload["holdout_evaluation_result"]),
        )


def save_holdout_region_evidence_artifact(
    artifact: TechnicalRiskHoldoutRegionEvidenceArtifact,
    directory: Path | str = DEFAULT_TECH_RISK_HOLDOUT_REGION_EVIDENCE_DIR,
    *,
    codec: TechnicalRiskHoldoutRegionEvidenceArtifactCodec | None = None,
) -> TechnicalRiskHoldoutRegionEvidenceArtifactSaveResult:
    if not isinstance(artifact, TechnicalRiskHoldoutRegionEvidenceArtifact):
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("save requires Holdout region evidence artifact.")
    directory_path = Path(directory)
    if any(part == "production" for part in directory_path.parts):
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("Holdout evidence cannot be saved under production path.")
    codec = codec or TechnicalRiskHoldoutRegionEvidenceArtifactCodec()
    directory_path.mkdir(parents=True, exist_ok=True)
    path = holdout_region_evidence_artifact_path(directory_path, artifact)
    payload = codec.encode(artifact)
    if path.exists():
        existing = codec.decode(path.read_text(encoding="utf-8"))
        if existing.artifact_id == artifact.artifact_id and existing.artifact_checksum == artifact.artifact_checksum:
            if path.read_text(encoding="utf-8") != payload:
                raise TechnicalRiskHoldoutRegionEvidenceArtifactError("Existing artifact payload differs from canonical payload.")
            return TechnicalRiskHoldoutRegionEvidenceArtifactSaveResult(
                artifact_id=artifact.artifact_id,
                artifact_checksum=artifact.artifact_checksum,
                path=path,
                status="IDEMPOTENT",
            )
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("Conflicting Holdout evidence artifact exists.")
    path.write_text(payload, encoding="utf-8")
    return TechnicalRiskHoldoutRegionEvidenceArtifactSaveResult(
        artifact_id=artifact.artifact_id,
        artifact_checksum=artifact.artifact_checksum,
        path=path,
        status="INSERTED",
    )


def load_holdout_region_evidence_artifact(
    path: Path | str,
    *,
    codec: TechnicalRiskHoldoutRegionEvidenceArtifactCodec | None = None,
) -> TechnicalRiskHoldoutRegionEvidenceArtifact:
    return (codec or TechnicalRiskHoldoutRegionEvidenceArtifactCodec()).decode(Path(path).read_text(encoding="utf-8"))


def holdout_region_evidence_artifact_path(
    directory: Path | str,
    artifact: TechnicalRiskHoldoutRegionEvidenceArtifact,
) -> Path:
    return Path(directory) / f"{artifact.artifact_id}.json"


def canonical_json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def serialization_checksum(envelope: Mapping[str, Any]) -> str:
    checksum_payload = {key: envelope[key] for key in sorted(envelope) if key != "serialization_checksum"}
    return hashlib.sha256(canonical_json_dumps(checksum_payload).encode("utf-8")).hexdigest()


def _artifact_payload(artifact: TechnicalRiskHoldoutRegionEvidenceArtifact) -> Mapping[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "artifact_schema_version": artifact.artifact_schema_version,
        "artifact_checksum": artifact.artifact_checksum,
        "validation_evidence_artifact_id": artifact.validation_evidence_artifact_id,
        "validation_evidence_artifact_checksum": artifact.validation_evidence_artifact_checksum,
        "validation_selection_methodology_version": artifact.validation_selection_methodology_version,
        "validation_selection_decision_package_id": artifact.validation_selection_decision_package_id,
        "validation_selection_decision_package_checksum": artifact.validation_selection_decision_package_checksum,
        "holdout_evaluation_result": _result_payload(artifact.holdout_evaluation_result),
    }


def _result_payload(result: TechnicalRiskHoldoutRegionEvaluationResult) -> Mapping[str, Any]:
    return {
        "result_id": result.result_id,
        "result_version": result.result_version,
        "result_checksum": result.result_checksum,
        "evaluator_version": result.evaluator_version,
        "contract_id": result.contract_id,
        "contract_version": result.contract_version,
        "split_role": result.split_role.value,
        "split_id": result.split_id,
        "holdout_start_date": result.holdout_start_date.isoformat(),
        "holdout_end_date": result.holdout_end_date.isoformat(),
        "dataset_id": result.dataset_id,
        "dataset_checksum": result.dataset_checksum,
        "holdout_row_count": result.holdout_row_count,
        "source_snapshot_id": result.source_snapshot_id,
        "source_snapshot_checksum": result.source_snapshot_checksum,
        "candidate_id": result.candidate_id,
        "candidate_version": result.candidate_version,
        "candidate_structural_checksum": result.candidate_structural_checksum,
        "region_id": result.region_id,
        "threshold_count": result.threshold_count,
        "evaluation_count": result.evaluation_count,
        "dataset_materialization_count": result.dataset_materialization_count,
        "threshold_identities": [list(identity) for identity in result.threshold_identities],
        "threshold_records": [_record_payload(record) for record in result.threshold_records],
        "region_summary": _summary_payload(result.region_summary),
    }


def _record_payload(record: TechnicalRiskHoldoutRegionThresholdEvaluationRecord) -> Mapping[str, Any]:
    threshold_result = record.threshold_result
    return {
        "evaluation_id": record.evaluation_id,
        "evaluation_checksum": record.evaluation_checksum,
        "evaluated_row_count": record.evaluated_row_count,
        "threshold_set_id": threshold_result.threshold_set_id,
        "threshold_checksum": threshold_result.threshold_checksum,
        "candidate_id": threshold_result.candidate_id,
        "region_id": threshold_result.region_id,
        "severity_evidence": [_severity_payload(item) for item in threshold_result.severity_evidence],
        "mae20_monotonicity_status": threshold_result.mae20_monotonicity_status,
        "mae20_monotonicity_reason_code": None,
        "mae60_monotonicity_status": threshold_result.mae60_monotonicity_status,
        "mae60_monotonicity_reason_code": None,
        "mae20_separation_evidence": _separation_payload(threshold_result.mae20_separation_evidence),
        "mae60_separation_evidence": _separation_payload(threshold_result.mae60_separation_evidence),
        "confirmation_status": threshold_result.confirmation_status.value,
        "warning_codes": list(record.warning_codes),
    }


def _severity_payload(evidence: TechnicalRiskHoldoutRegionSeverityEvidence) -> Mapping[str, Any]:
    return {
        "severity": evidence.severity.value,
        "sample_count": evidence.sample_count,
        "coverage_ratio": _decimal_payload(evidence.coverage_ratio),
        "mae20_mean": _optional_decimal_payload(evidence.mae20_mean),
        "mae20_median": _optional_decimal_payload(evidence.mae20_median),
        "mae20_p25": _optional_decimal_payload(evidence.mae20_p25),
        "mae20_p75": _optional_decimal_payload(evidence.mae20_p75),
        "mae60_mean": _optional_decimal_payload(evidence.mae60_mean),
        "mae60_median": _optional_decimal_payload(evidence.mae60_median),
        "mae60_p25": _optional_decimal_payload(evidence.mae60_p25),
        "mae60_p75": _optional_decimal_payload(evidence.mae60_p75),
    }


def _separation_payload(evidence: TechnicalRiskHoldoutRegionSeparationEvidence) -> Mapping[str, Any]:
    return {
        "horizon": evidence.horizon.value,
        "high_minus_low": _optional_decimal_payload(evidence.high_minus_low),
        "high_minus_medium": _optional_decimal_payload(evidence.high_minus_medium),
        "medium_minus_low": _optional_decimal_payload(evidence.medium_minus_low),
    }


def _summary_payload(summary: TechnicalRiskHoldoutRegionSummary) -> Mapping[str, Any]:
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


def _decode_result(payload: Any) -> TechnicalRiskHoldoutRegionEvaluationResult:
    value = _require_exact_mapping(payload, _RESULT_FIELDS, "Holdout result payload")
    return TechnicalRiskHoldoutRegionEvaluationResult(
        result_id=_require_text(value["result_id"], "result_id"),
        result_version=_require_text(value["result_version"], "result_version"),
        result_checksum=_require_text(value["result_checksum"], "result_checksum"),
        evaluator_version=_require_text(value["evaluator_version"], "evaluator_version"),
        contract_id=_require_text(value["contract_id"], "contract_id"),
        contract_version=_require_text(value["contract_version"], "contract_version"),
        split_role=TechnicalRiskOOSSplitRole(_require_text(value["split_role"], "split_role")),
        split_id=_require_text(value["split_id"], "split_id"),
        holdout_start_date=_parse_date(value["holdout_start_date"], "holdout_start_date"),
        holdout_end_date=_parse_date(value["holdout_end_date"], "holdout_end_date"),
        dataset_id=_require_text(value["dataset_id"], "dataset_id"),
        dataset_checksum=_require_text(value["dataset_checksum"], "dataset_checksum"),
        holdout_row_count=_require_int(value["holdout_row_count"], "holdout_row_count"),
        source_snapshot_id=_require_text(value["source_snapshot_id"], "source_snapshot_id"),
        source_snapshot_checksum=_require_text(value["source_snapshot_checksum"], "source_snapshot_checksum"),
        candidate_id=_require_text(value["candidate_id"], "candidate_id"),
        candidate_version=_require_text(value["candidate_version"], "candidate_version"),
        candidate_structural_checksum=_require_text(value["candidate_structural_checksum"], "candidate_structural_checksum"),
        region_id=_require_text(value["region_id"], "region_id"),
        threshold_count=_require_int(value["threshold_count"], "threshold_count"),
        evaluation_count=_require_int(value["evaluation_count"], "evaluation_count"),
        dataset_materialization_count=_require_int(value["dataset_materialization_count"], "dataset_materialization_count"),
        threshold_identities=_decode_identity_pairs(value["threshold_identities"], "threshold_identities"),
        threshold_records=tuple(_decode_record(item) for item in _require_list(value["threshold_records"], "threshold_records")),
        region_summary=_decode_summary(value["region_summary"]),
    )


def _decode_record(payload: Any) -> TechnicalRiskHoldoutRegionThresholdEvaluationRecord:
    value = _require_exact_mapping(payload, _RECORD_FIELDS, "threshold record payload")
    threshold_result = TechnicalRiskHoldoutRegionThresholdResult(
        threshold_set_id=_require_text(value["threshold_set_id"], "threshold_set_id"),
        threshold_checksum=_require_text(value["threshold_checksum"], "threshold_checksum"),
        candidate_id=_require_text(value["candidate_id"], "candidate_id"),
        region_id=_require_text(value["region_id"], "region_id"),
        severity_evidence=tuple(_decode_severity(item) for item in _require_list(value["severity_evidence"], "severity_evidence")),
        mae20_monotonicity_status=_require_text(value["mae20_monotonicity_status"], "mae20_monotonicity_status"),
        mae60_monotonicity_status=_require_text(value["mae60_monotonicity_status"], "mae60_monotonicity_status"),
        mae20_separation_evidence=_decode_separation(value["mae20_separation_evidence"]),
        mae60_separation_evidence=_decode_separation(value["mae60_separation_evidence"]),
        confirmation_status=TechnicalRiskHoldoutRegionConfirmationStatus(_require_text(value["confirmation_status"], "confirmation_status")),
    )
    if value["mae20_monotonicity_reason_code"] is not None:
        _require_text(value["mae20_monotonicity_reason_code"], "mae20_monotonicity_reason_code")
    if value["mae60_monotonicity_reason_code"] is not None:
        _require_text(value["mae60_monotonicity_reason_code"], "mae60_monotonicity_reason_code")
    return TechnicalRiskHoldoutRegionThresholdEvaluationRecord(
        evaluation_id=_require_text(value["evaluation_id"], "evaluation_id"),
        evaluation_checksum=_require_text(value["evaluation_checksum"], "evaluation_checksum"),
        evaluated_row_count=_require_int(value["evaluated_row_count"], "evaluated_row_count"),
        threshold_result=threshold_result,
        warning_codes=tuple(_require_text(item, "warning_code") for item in _require_list(value["warning_codes"], "warning_codes")),
    )


def _decode_severity(payload: Any) -> TechnicalRiskHoldoutRegionSeverityEvidence:
    value = _require_exact_mapping(payload, _SEVERITY_FIELDS, "severity evidence payload")
    return TechnicalRiskHoldoutRegionSeverityEvidence(
        severity=_require_text(value["severity"], "severity"),
        sample_count=_require_int(value["sample_count"], "sample_count"),
        coverage_ratio=_parse_decimal(value["coverage_ratio"], "coverage_ratio"),
        mae20_mean=_parse_optional_decimal(value["mae20_mean"], "mae20_mean"),
        mae20_median=_parse_optional_decimal(value["mae20_median"], "mae20_median"),
        mae20_p25=_parse_optional_decimal(value["mae20_p25"], "mae20_p25"),
        mae20_p75=_parse_optional_decimal(value["mae20_p75"], "mae20_p75"),
        mae60_mean=_parse_optional_decimal(value["mae60_mean"], "mae60_mean"),
        mae60_median=_parse_optional_decimal(value["mae60_median"], "mae60_median"),
        mae60_p25=_parse_optional_decimal(value["mae60_p25"], "mae60_p25"),
        mae60_p75=_parse_optional_decimal(value["mae60_p75"], "mae60_p75"),
    )


def _decode_separation(payload: Any) -> TechnicalRiskHoldoutRegionSeparationEvidence:
    value = _require_exact_mapping(payload, _SEPARATION_FIELDS, "separation evidence payload")
    return TechnicalRiskHoldoutRegionSeparationEvidence(
        horizon=TechnicalRiskHoldoutRegionEvidenceHorizon(_require_text(value["horizon"], "horizon")),
        high_minus_low=_parse_optional_decimal(value["high_minus_low"], "high_minus_low"),
        high_minus_medium=_parse_optional_decimal(value["high_minus_medium"], "high_minus_medium"),
        medium_minus_low=_parse_optional_decimal(value["medium_minus_low"], "medium_minus_low"),
    )


def _decode_summary(payload: Any) -> TechnicalRiskHoldoutRegionSummary:
    value = _require_exact_mapping(payload, _SUMMARY_FIELDS, "region summary payload")
    return TechnicalRiskHoldoutRegionSummary(
        region_id=_require_text(value["region_id"], "summary.region_id"),
        candidate_id=_require_text(value["candidate_id"], "summary.candidate_id"),
        total_threshold_count=_require_int(value["total_threshold_count"], "summary.total_threshold_count"),
        confirmed_threshold_count=_require_int(value["confirmed_threshold_count"], "summary.confirmed_threshold_count"),
        not_confirmed_threshold_count=_require_int(value["not_confirmed_threshold_count"], "summary.not_confirmed_threshold_count"),
        review_required_threshold_count=_require_int(value["review_required_threshold_count"], "summary.review_required_threshold_count"),
        monotonicity_stability_summary=_decode_int_mapping(value["monotonicity_stability_summary"], "monotonicity_stability_summary"),
        separation_stability_summary=_decode_int_mapping(value["separation_stability_summary"], "separation_stability_summary"),
        coverage_stability_summary=_decode_int_mapping(value["coverage_stability_summary"], "coverage_stability_summary"),
    )


def _validate_result(result: TechnicalRiskHoldoutRegionEvaluationResult) -> None:
    _require_version(result.result_version, TECH_RISK_HOLDOUT_REGION_EVALUATION_RESULT_V1, "result_version")
    _require_version(result.evaluator_version, TECH_RISK_HOLDOUT_REGION_EVALUATOR_V1, "evaluator_version")
    _require_version(result.contract_version, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1, "contract_version")
    if result.split_role != TechnicalRiskOOSSplitRole.HOLDOUT:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("Holdout artifact requires HOLDOUT result.")
    if result.holdout_start_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("holdout_start_date mismatch.")
    if result.holdout_end_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("holdout_end_date mismatch.")
    _require_version(result.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID, "candidate_id")
    _require_version(result.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID, "region_id")
    if result.threshold_count != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("threshold_count mismatch.")
    if result.evaluation_count != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("evaluation_count mismatch.")
    if tuple(identity[0] for identity in result.threshold_identities) != TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("threshold identity mismatch.")
    if len(set(result.threshold_identities)) != len(result.threshold_identities):
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("duplicate threshold identity.")
    record_keys = tuple(
        (
            record.threshold_result.threshold_set_id,
            record.threshold_result.threshold_checksum,
            record.evaluation_id,
            record.evaluation_checksum,
        )
        for record in result.threshold_records
    )
    if len(set(record_keys)) != len(record_keys):
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("duplicate threshold or evaluation identity.")
    if any(record.threshold_result.confirmation_status != TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED for record in result.threshold_records):
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("Holdout evidence must remain REVIEW_REQUIRED.")


def _artifact_checksum(artifact: TechnicalRiskHoldoutRegionEvidenceArtifact) -> str:
    return _stable_hash(
        {
            "artifact_schema_version": artifact.artifact_schema_version,
            "validation_evidence_artifact_id": artifact.validation_evidence_artifact_id,
            "validation_evidence_artifact_checksum": artifact.validation_evidence_artifact_checksum,
            "validation_selection_methodology_version": artifact.validation_selection_methodology_version,
            "validation_selection_decision_package_id": artifact.validation_selection_decision_package_id,
            "validation_selection_decision_package_checksum": artifact.validation_selection_decision_package_checksum,
            "holdout_evaluation_result": _result_payload(artifact.holdout_evaluation_result),
        }
    )


def _decimal_payload(value: Decimal) -> str:
    return format(value, "f")


def _optional_decimal_payload(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return _decimal_payload(value)


def _parse_decimal(value: Any, field_name: str) -> Decimal:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError(f"{field_name} must be a decimal string.")
    try:
        return Decimal(value)
    except Exception as exc:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError(f"{field_name} must be a decimal string.") from exc


def _parse_optional_decimal(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return _parse_decimal(value, field_name)


def _parse_date(value: Any, field_name: str) -> date:
    if not isinstance(value, str):
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError(f"{field_name} must be a date string.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError(f"{field_name} must be a date string.") from exc


def _decode_identity_pairs(value: Any, field_name: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (_require_text(item[0], field_name), _require_text(item[1], field_name))
        for item in _require_list(value, field_name)
        if _require_pair(item, field_name)
    )


def _decode_int_mapping(value: Any, field_name: str) -> Mapping[str, int]:
    mapping = _require_mapping(value, field_name)
    return {
        _require_text(key, field_name): _require_int(item, field_name)
        for key, item in mapping.items()
    }


def _verify_serialization_checksum(envelope: Mapping[str, Any]) -> None:
    expected = _require_text(envelope["serialization_checksum"], "serialization_checksum")
    actual = serialization_checksum(envelope)
    if actual != expected:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError("serialization_checksum mismatch.")


def _require_exact_mapping(value: Any, expected_fields: frozenset[str], field_name: str) -> Mapping[str, Any]:
    mapping = _require_mapping(value, field_name)
    if set(mapping) != expected_fields:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError(f"{field_name} fields mismatch.")
    return mapping


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError(f"{field_name} must be an object.")
    return value


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError(f"{field_name} must be a list.")
    return value


def _require_pair(value: Any, field_name: str) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError(f"{field_name} pair mismatch.")
    return True


def _require_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError(f"{field_name} must be an integer.")
    return value


def _require_version(actual: object, expected: str, field_name: str) -> None:
    if actual != expected:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError(f"{field_name} mismatch.")


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskHoldoutRegionEvidenceArtifactError(f"{field_name} must be a non-empty string.")
    return value


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_dumps(payload).encode("utf-8")).hexdigest()
