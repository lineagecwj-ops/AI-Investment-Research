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
from risk_oos.candidate_evaluator import TechnicalRiskMonotonicityResult
from risk_oos.candidate_evaluator import TechnicalRiskMonotonicityStatus
from risk_oos.candidate_evaluator import TechnicalRiskSeverityMAEMetrics
from risk_oos.rule_candidates import TechnicalRiskCandidateSeverity
from risk_oos.validation_candidate_evaluation import TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_RESULT_V1
from risk_oos.validation_candidate_evaluation import TechnicalRiskValidationCandidateEvaluationRecord
from risk_oos.validation_candidate_evaluation import TechnicalRiskValidationCandidateEvaluationResult
from risk_oos.validation_candidate_evaluation import TechnicalRiskValidationCandidateSummary


TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_SCHEMA_V1 = "TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_V1"
TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_CODEC_V1 = "TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_CODEC_V1"
DEFAULT_TECH_RISK_VALIDATION_EVIDENCE_DIR = Path("data/research/technical_risk_validation_evidence")

_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "codec_version",
        "artifact",
        "serialization_checksum",
    }
)

_ARTIFACT_FIELDS = frozenset(
    {
        "artifact_id",
        "artifact_schema_version",
        "artifact_checksum",
        "validation_result",
    }
)

_RESULT_FIELDS = frozenset(
    {
        "result_id",
        "result_version",
        "result_checksum",
        "orchestrator_version",
        "methodology_version",
        "split_role",
        "split_id",
        "validation_start_date",
        "validation_end_date",
        "dataset_id",
        "dataset_checksum",
        "validation_row_count",
        "source_snapshot_id",
        "source_snapshot_checksum",
        "axis_set_id",
        "axis_set_checksum",
        "threshold_grid_result_id",
        "threshold_grid_result_checksum",
        "candidate_count",
        "threshold_set_count",
        "evaluation_count",
        "dataset_materialization_count",
        "candidate_identities",
        "threshold_identities",
        "evaluation_records",
        "candidate_summaries",
    }
)

_RECORD_FIELDS = frozenset(
    {
        "evaluation_id",
        "evaluation_checksum",
        "candidate_id",
        "candidate_version",
        "candidate_structural_checksum",
        "threshold_set_id",
        "threshold_set_version",
        "threshold_set_checksum",
        "evaluated_row_count",
        "aggregate_metrics",
        "monotonicity_results",
    }
)

_METRIC_FIELDS = frozenset(
    {
        "split_role",
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

_MONOTONICITY_FIELDS = frozenset(
    {
        "split_role",
        "horizon",
        "status",
        "low_median",
        "medium_median",
        "high_median",
        "reason_code",
    }
)

_SUMMARY_FIELDS = frozenset(
    {
        "candidate_id",
        "evaluation_count",
        "monotonicity_status_counts",
    }
)


class TechnicalRiskValidationEvidenceArtifactError(ValueError):
    """Raised when Technical Risk Validation evidence artifacts fail closed."""


@dataclass(frozen=True)
class TechnicalRiskValidationEvidenceArtifactSaveResult:
    """Immutable save result for one research evidence artifact."""

    artifact_id: str
    artifact_checksum: str
    path: Path
    status: str

    def __post_init__(self) -> None:
        _require_text(self.artifact_id, "artifact_id")
        _require_text(self.artifact_checksum, "artifact_checksum")
        object.__setattr__(self, "path", Path(self.path))
        if self.status not in {"INSERTED", "IDEMPOTENT"}:
            raise TechnicalRiskValidationEvidenceArtifactError("Unsupported save status.")


@dataclass(frozen=True)
class TechnicalRiskValidationEvidenceArtifact:
    """Research-owned durable evidence snapshot for the VALIDATION-only matrix."""

    artifact_id: str | None
    artifact_schema_version: str
    artifact_checksum: str | None
    validation_result: TechnicalRiskValidationCandidateEvaluationResult

    def __post_init__(self) -> None:
        _require_version(
            self.artifact_schema_version,
            TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_SCHEMA_V1,
            "artifact_schema_version",
        )
        if not isinstance(self.validation_result, TechnicalRiskValidationCandidateEvaluationResult):
            raise TechnicalRiskValidationEvidenceArtifactError("validation_result must be a TechnicalRiskValidationCandidateEvaluationResult.")
        if self.validation_result.split_role != TechnicalRiskOOSSplitRole.VALIDATION:
            raise TechnicalRiskValidationEvidenceArtifactError("Validation evidence artifact requires VALIDATION result.")
        checksum = _artifact_checksum(self.validation_result, self.artifact_schema_version)
        artifact_id = _stable_id("technical_risk_validation_evidence", {"artifact_checksum": checksum})
        if self.artifact_id is not None and self.artifact_id != artifact_id:
            raise TechnicalRiskValidationEvidenceArtifactError("artifact_id mismatch.")
        if self.artifact_checksum is not None and self.artifact_checksum != checksum:
            raise TechnicalRiskValidationEvidenceArtifactError("artifact_checksum mismatch.")
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_checksum", checksum)

    @classmethod
    def from_validation_result(
        cls,
        validation_result: TechnicalRiskValidationCandidateEvaluationResult,
    ) -> "TechnicalRiskValidationEvidenceArtifact":
        return cls(
            artifact_id=None,
            artifact_schema_version=TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_SCHEMA_V1,
            artifact_checksum=None,
            validation_result=validation_result,
        )


@dataclass(frozen=True)
class TechnicalRiskValidationEvidenceArtifactCodec:
    """Strict versioned JSON codec for Technical Risk Validation evidence."""

    def encode(self, artifact: TechnicalRiskValidationEvidenceArtifact) -> str:
        if not isinstance(artifact, TechnicalRiskValidationEvidenceArtifact):
            raise TechnicalRiskValidationEvidenceArtifactError("encode requires TechnicalRiskValidationEvidenceArtifact.")
        envelope: dict[str, Any] = {
            "schema_version": TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_SCHEMA_V1,
            "codec_version": TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_CODEC_V1,
            "artifact": _artifact_payload(artifact),
        }
        envelope["serialization_checksum"] = serialization_checksum(envelope)
        return canonical_json_dumps(envelope)

    def decode(self, payload: str) -> TechnicalRiskValidationEvidenceArtifact:
        if not isinstance(payload, str):
            raise TechnicalRiskValidationEvidenceArtifactError("decode requires JSON string payload.")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise TechnicalRiskValidationEvidenceArtifactError("Evidence artifact payload must be valid JSON.") from exc
        envelope = _require_exact_mapping(decoded, _ENVELOPE_FIELDS, "Evidence artifact envelope")
        _require_version(envelope["schema_version"], TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_SCHEMA_V1, "schema_version")
        _require_version(envelope["codec_version"], TECH_RISK_VALIDATION_EVIDENCE_ARTIFACT_CODEC_V1, "codec_version")
        _verify_serialization_checksum(envelope)
        artifact_payload = _require_exact_mapping(envelope["artifact"], _ARTIFACT_FIELDS, "Evidence artifact payload")
        result = _decode_result(artifact_payload["validation_result"])
        return TechnicalRiskValidationEvidenceArtifact(
            artifact_id=_require_text(artifact_payload["artifact_id"], "artifact_id"),
            artifact_schema_version=_require_text(artifact_payload["artifact_schema_version"], "artifact_schema_version"),
            artifact_checksum=_require_text(artifact_payload["artifact_checksum"], "artifact_checksum"),
            validation_result=result,
        )


def save_validation_evidence_artifact(
    artifact: TechnicalRiskValidationEvidenceArtifact,
    directory: Path | str = DEFAULT_TECH_RISK_VALIDATION_EVIDENCE_DIR,
    *,
    codec: TechnicalRiskValidationEvidenceArtifactCodec | None = None,
) -> TechnicalRiskValidationEvidenceArtifactSaveResult:
    if not isinstance(artifact, TechnicalRiskValidationEvidenceArtifact):
        raise TechnicalRiskValidationEvidenceArtifactError("save requires TechnicalRiskValidationEvidenceArtifact.")
    codec = codec or TechnicalRiskValidationEvidenceArtifactCodec()
    directory_path = Path(directory)
    if any(part == "production" for part in directory_path.parts):
        raise TechnicalRiskValidationEvidenceArtifactError("Validation evidence artifact cannot be saved under production path.")
    directory_path.mkdir(parents=True, exist_ok=True)
    path = validation_evidence_artifact_path(directory_path, artifact)
    payload = codec.encode(artifact)
    if path.exists():
        existing = codec.decode(path.read_text(encoding="utf-8"))
        if existing.artifact_id == artifact.artifact_id and existing.artifact_checksum == artifact.artifact_checksum:
            if path.read_text(encoding="utf-8") != payload:
                raise TechnicalRiskValidationEvidenceArtifactError("Existing artifact payload differs from canonical payload.")
            return TechnicalRiskValidationEvidenceArtifactSaveResult(
                artifact_id=artifact.artifact_id,
                artifact_checksum=artifact.artifact_checksum,
                path=path,
                status="IDEMPOTENT",
            )
        raise TechnicalRiskValidationEvidenceArtifactError("Conflicting Validation evidence artifact exists.")
    path.write_text(payload, encoding="utf-8")
    return TechnicalRiskValidationEvidenceArtifactSaveResult(
        artifact_id=artifact.artifact_id,
        artifact_checksum=artifact.artifact_checksum,
        path=path,
        status="INSERTED",
    )


def load_validation_evidence_artifact(
    path: Path | str,
    *,
    codec: TechnicalRiskValidationEvidenceArtifactCodec | None = None,
) -> TechnicalRiskValidationEvidenceArtifact:
    return (codec or TechnicalRiskValidationEvidenceArtifactCodec()).decode(Path(path).read_text(encoding="utf-8"))


def validation_evidence_artifact_path(
    directory: Path | str,
    artifact: TechnicalRiskValidationEvidenceArtifact,
) -> Path:
    return Path(directory) / f"{artifact.artifact_id}.json"


def canonical_json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def serialization_checksum(envelope: Mapping[str, Any]) -> str:
    checksum_payload = {key: envelope[key] for key in sorted(envelope) if key != "serialization_checksum"}
    return hashlib.sha256(canonical_json_dumps(checksum_payload).encode("utf-8")).hexdigest()


def _artifact_payload(artifact: TechnicalRiskValidationEvidenceArtifact) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "artifact_schema_version": artifact.artifact_schema_version,
        "artifact_checksum": artifact.artifact_checksum,
        "validation_result": _result_payload(artifact.validation_result),
    }


def _result_payload(result: TechnicalRiskValidationCandidateEvaluationResult) -> dict[str, Any]:
    return {
        "result_id": result.result_id,
        "result_version": result.result_version,
        "result_checksum": result.result_checksum,
        "orchestrator_version": result.orchestrator_version,
        "methodology_version": result.methodology_version,
        "split_role": result.split_role.value,
        "split_id": result.split_id,
        "validation_start_date": result.validation_start_date.isoformat(),
        "validation_end_date": result.validation_end_date.isoformat(),
        "dataset_id": result.dataset_id,
        "dataset_checksum": result.dataset_checksum,
        "validation_row_count": result.validation_row_count,
        "source_snapshot_id": result.source_snapshot_id,
        "source_snapshot_checksum": result.source_snapshot_checksum,
        "axis_set_id": result.axis_set_id,
        "axis_set_checksum": result.axis_set_checksum,
        "threshold_grid_result_id": result.threshold_grid_result_id,
        "threshold_grid_result_checksum": result.threshold_grid_result_checksum,
        "candidate_count": result.candidate_count,
        "threshold_set_count": result.threshold_set_count,
        "evaluation_count": result.evaluation_count,
        "dataset_materialization_count": result.dataset_materialization_count,
        "candidate_identities": [list(item) for item in result.candidate_identities],
        "threshold_identities": [list(item) for item in result.threshold_identities],
        "evaluation_records": [_record_payload(record) for record in result.evaluation_records],
        "candidate_summaries": [_summary_payload(summary) for summary in result.candidate_summaries],
    }


def _record_payload(record: TechnicalRiskValidationCandidateEvaluationRecord) -> dict[str, Any]:
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


def _metric_payload(metric: TechnicalRiskSeverityMAEMetrics) -> dict[str, Any]:
    return {
        "split_role": metric.split_role.value,
        "severity": metric.severity.value,
        "sample_count": metric.sample_count,
        "coverage_ratio": _decimal_payload(metric.coverage_ratio),
        "mae20_mean": _optional_decimal_payload(metric.mae20_mean),
        "mae20_median": _optional_decimal_payload(metric.mae20_median),
        "mae20_p25": _optional_decimal_payload(metric.mae20_p25),
        "mae20_p75": _optional_decimal_payload(metric.mae20_p75),
        "mae60_mean": _optional_decimal_payload(metric.mae60_mean),
        "mae60_median": _optional_decimal_payload(metric.mae60_median),
        "mae60_p25": _optional_decimal_payload(metric.mae60_p25),
        "mae60_p75": _optional_decimal_payload(metric.mae60_p75),
    }


def _monotonicity_payload(result: TechnicalRiskMonotonicityResult) -> dict[str, Any]:
    return {
        "split_role": result.split_role.value,
        "horizon": result.horizon,
        "status": result.status.value,
        "low_median": _optional_decimal_payload(result.low_median),
        "medium_median": _optional_decimal_payload(result.medium_median),
        "high_median": _optional_decimal_payload(result.high_median),
        "reason_code": result.reason_code,
    }


def _summary_payload(summary: TechnicalRiskValidationCandidateSummary) -> dict[str, Any]:
    return {
        "candidate_id": summary.candidate_id,
        "evaluation_count": summary.evaluation_count,
        "monotonicity_status_counts": dict(summary.monotonicity_status_counts),
    }


def _decode_result(payload: Any) -> TechnicalRiskValidationCandidateEvaluationResult:
    value = _require_exact_mapping(payload, _RESULT_FIELDS, "Validation result payload")
    return TechnicalRiskValidationCandidateEvaluationResult(
        result_id=_require_text(value["result_id"], "result_id"),
        result_version=_require_text(value["result_version"], "result_version"),
        result_checksum=_require_text(value["result_checksum"], "result_checksum"),
        orchestrator_version=_require_text(value["orchestrator_version"], "orchestrator_version"),
        methodology_version=_require_text(value["methodology_version"], "methodology_version"),
        split_role=TechnicalRiskOOSSplitRole(_require_text(value["split_role"], "split_role")),
        split_id=_require_text(value["split_id"], "split_id"),
        validation_start_date=_parse_date(value["validation_start_date"], "validation_start_date"),
        validation_end_date=_parse_date(value["validation_end_date"], "validation_end_date"),
        dataset_id=_require_text(value["dataset_id"], "dataset_id"),
        dataset_checksum=_require_text(value["dataset_checksum"], "dataset_checksum"),
        validation_row_count=_require_int(value["validation_row_count"], "validation_row_count"),
        source_snapshot_id=_require_text(value["source_snapshot_id"], "source_snapshot_id"),
        source_snapshot_checksum=_require_text(value["source_snapshot_checksum"], "source_snapshot_checksum"),
        axis_set_id=_require_text(value["axis_set_id"], "axis_set_id"),
        axis_set_checksum=_require_text(value["axis_set_checksum"], "axis_set_checksum"),
        threshold_grid_result_id=_require_text(value["threshold_grid_result_id"], "threshold_grid_result_id"),
        threshold_grid_result_checksum=_require_text(value["threshold_grid_result_checksum"], "threshold_grid_result_checksum"),
        candidate_count=_require_int(value["candidate_count"], "candidate_count"),
        threshold_set_count=_require_int(value["threshold_set_count"], "threshold_set_count"),
        evaluation_count=_require_int(value["evaluation_count"], "evaluation_count"),
        dataset_materialization_count=_require_int(value["dataset_materialization_count"], "dataset_materialization_count"),
        candidate_identities=_decode_identity_triplets(value["candidate_identities"], "candidate_identities"),
        threshold_identities=_decode_identity_pairs(value["threshold_identities"], "threshold_identities"),
        evaluation_records=tuple(_decode_record(item) for item in _require_list(value["evaluation_records"], "evaluation_records")),
        candidate_summaries=tuple(_decode_summary(item) for item in _require_list(value["candidate_summaries"], "candidate_summaries")),
    )


def _decode_record(payload: Any) -> TechnicalRiskValidationCandidateEvaluationRecord:
    value = _require_exact_mapping(payload, _RECORD_FIELDS, "Evaluation record payload")
    return TechnicalRiskValidationCandidateEvaluationRecord(
        evaluation_id=_require_text(value["evaluation_id"], "evaluation_id"),
        evaluation_checksum=_require_text(value["evaluation_checksum"], "evaluation_checksum"),
        candidate_id=_require_text(value["candidate_id"], "candidate_id"),
        candidate_version=_require_text(value["candidate_version"], "candidate_version"),
        candidate_structural_checksum=_require_text(value["candidate_structural_checksum"], "candidate_structural_checksum"),
        threshold_set_id=_require_text(value["threshold_set_id"], "threshold_set_id"),
        threshold_set_version=_require_text(value["threshold_set_version"], "threshold_set_version"),
        threshold_set_checksum=_require_text(value["threshold_set_checksum"], "threshold_set_checksum"),
        evaluated_row_count=_require_int(value["evaluated_row_count"], "evaluated_row_count"),
        aggregate_metrics=tuple(_decode_metric(item) for item in _require_list(value["aggregate_metrics"], "aggregate_metrics")),
        monotonicity_results=tuple(_decode_monotonicity(item) for item in _require_list(value["monotonicity_results"], "monotonicity_results")),
    )


def _decode_metric(payload: Any) -> TechnicalRiskSeverityMAEMetrics:
    value = _require_exact_mapping(payload, _METRIC_FIELDS, "Metric payload")
    return TechnicalRiskSeverityMAEMetrics(
        split_role=TechnicalRiskOOSSplitRole(_require_text(value["split_role"], "metric.split_role")),
        severity=TechnicalRiskCandidateSeverity(_require_text(value["severity"], "metric.severity")),
        sample_count=_require_int(value["sample_count"], "metric.sample_count"),
        coverage_ratio=_parse_decimal(value["coverage_ratio"], "metric.coverage_ratio"),
        mae20_mean=_parse_optional_decimal(value["mae20_mean"], "metric.mae20_mean"),
        mae20_median=_parse_optional_decimal(value["mae20_median"], "metric.mae20_median"),
        mae20_p25=_parse_optional_decimal(value["mae20_p25"], "metric.mae20_p25"),
        mae20_p75=_parse_optional_decimal(value["mae20_p75"], "metric.mae20_p75"),
        mae60_mean=_parse_optional_decimal(value["mae60_mean"], "metric.mae60_mean"),
        mae60_median=_parse_optional_decimal(value["mae60_median"], "metric.mae60_median"),
        mae60_p25=_parse_optional_decimal(value["mae60_p25"], "metric.mae60_p25"),
        mae60_p75=_parse_optional_decimal(value["mae60_p75"], "metric.mae60_p75"),
    )


def _decode_monotonicity(payload: Any) -> TechnicalRiskMonotonicityResult:
    value = _require_exact_mapping(payload, _MONOTONICITY_FIELDS, "Monotonicity payload")
    return TechnicalRiskMonotonicityResult(
        split_role=TechnicalRiskOOSSplitRole(_require_text(value["split_role"], "monotonicity.split_role")),
        horizon=_require_int(value["horizon"], "monotonicity.horizon"),
        status=TechnicalRiskMonotonicityStatus(_require_text(value["status"], "monotonicity.status")),
        low_median=_parse_optional_decimal(value["low_median"], "monotonicity.low_median"),
        medium_median=_parse_optional_decimal(value["medium_median"], "monotonicity.medium_median"),
        high_median=_parse_optional_decimal(value["high_median"], "monotonicity.high_median"),
        reason_code=_optional_text(value["reason_code"], "monotonicity.reason_code"),
    )


def _decode_summary(payload: Any) -> TechnicalRiskValidationCandidateSummary:
    value = _require_exact_mapping(payload, _SUMMARY_FIELDS, "Candidate summary payload")
    counts = _require_mapping(value["monotonicity_status_counts"], "monotonicity_status_counts")
    return TechnicalRiskValidationCandidateSummary(
        candidate_id=_require_text(value["candidate_id"], "summary.candidate_id"),
        evaluation_count=_require_int(value["evaluation_count"], "summary.evaluation_count"),
        monotonicity_status_counts={_require_text(key, "status"): _require_int(item, "status_count") for key, item in counts.items()},
    )


def _artifact_checksum(result: TechnicalRiskValidationCandidateEvaluationResult, artifact_schema_version: str) -> str:
    return _stable_hash(
        {
            "artifact_schema_version": artifact_schema_version,
            "validation_result": _result_payload(result),
        }
    )


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_dumps(payload).encode("utf-8")).hexdigest()


def _verify_serialization_checksum(envelope: Mapping[str, Any]) -> None:
    expected = _require_text(envelope["serialization_checksum"], "serialization_checksum")
    actual = serialization_checksum(envelope)
    if actual != expected:
        raise TechnicalRiskValidationEvidenceArtifactError("serialization_checksum mismatch.")


def _require_exact_mapping(value: Any, expected_fields: frozenset[str], field_name: str) -> Mapping[str, Any]:
    mapping = _require_mapping(value, field_name)
    actual_fields = set(mapping)
    if actual_fields != expected_fields:
        raise TechnicalRiskValidationEvidenceArtifactError(f"{field_name} fields mismatch.")
    return mapping


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TechnicalRiskValidationEvidenceArtifactError(f"{field_name} must be an object.")
    return value


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise TechnicalRiskValidationEvidenceArtifactError(f"{field_name} must be a list.")
    return value


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskValidationEvidenceArtifactError(f"{field_name} must be a non-empty string.")
    return value


def _optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field_name)


def _require_version(actual: Any, expected: str, field_name: str) -> None:
    if actual != expected:
        raise TechnicalRiskValidationEvidenceArtifactError(f"Unsupported {field_name}.")


def _require_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TechnicalRiskValidationEvidenceArtifactError(f"{field_name} must be an integer.")
    return value


def _parse_date(value: Any, field_name: str) -> date:
    text = _require_text(value, field_name)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise TechnicalRiskValidationEvidenceArtifactError(f"{field_name} must be an ISO date.") from exc


def _parse_decimal(value: Any, field_name: str) -> Decimal:
    text = _require_text(value, field_name)
    return Decimal(text)


def _parse_optional_decimal(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return _parse_decimal(value, field_name)


def _decimal_payload(value: Decimal) -> str:
    return str(value)


def _optional_decimal_payload(value: Decimal | None) -> str | None:
    return None if value is None else _decimal_payload(value)


def _decode_identity_triplets(value: Any, field_name: str) -> tuple[tuple[str, str, str], ...]:
    return tuple(_decode_string_tuple(item, 3, field_name) for item in _require_list(value, field_name))


def _decode_identity_pairs(value: Any, field_name: str) -> tuple[tuple[str, str], ...]:
    return tuple(_decode_string_tuple(item, 2, field_name) for item in _require_list(value, field_name))


def _decode_string_tuple(value: Any, length: int, field_name: str) -> tuple[str, ...]:
    items = _require_list(value, field_name)
    if len(items) != length:
        raise TechnicalRiskValidationEvidenceArtifactError(f"{field_name} tuple length mismatch.")
    return tuple(_require_text(item, field_name) for item in items)
