from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from portfolio_generation import MonitoringEvaluator
from portfolio_generation import PortfolioPositionGenerationResult
from portfolio_generation import PortfolioRiskGenerationResult
from portfolio_generation import PortfolioRiskGenerationService
from portfolio_generation import PortfolioRiskGenerationStatus
from portfolio_generation import RiskEvaluator
from portfolio_generation import ExactVersionPolicyResolver
from portfolio_state import PortfolioSnapshot
from portfolio_state import RiskEvaluationInput
from risk import RiskArtifact
from risk_persistence.capturing_risk_evaluator import CapturingRiskEvaluator
from risk_persistence.contracts import RiskArtifactCorruptionError
from risk_persistence.contracts import RiskArtifactSaveResult
from risk_persistence.sqlite_portfolio_run_repository import _PreparedPortfolioRunRecordForPersistence
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunArtifactRef
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunIssue
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunMonitoringArtifactRef
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunRecord
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunSaveResult
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunWarning
from risk_persistence.sqlite_portfolio_run_repository import load_portfolio_run_record_in_connection
from risk_persistence.sqlite_portfolio_run_repository import prepare_portfolio_run_record_for_persistence
from risk_persistence.sqlite_portfolio_run_repository import persist_portfolio_run_record_in_connection
from risk_persistence.sqlite_schema import initialize_or_verify_schema
from risk_persistence.sqlite_storage import configure_sqlite_write_connection
from risk_persistence.sqlite_storage import load_core_artifact_row
from risk_persistence.sqlite_storage import validate_sqlite_db_path
from risk_persistence.sqlite_technical_artifact_persistence import persist_technical_artifact_in_connection
from risk_persistence.technical_query_contracts import TechnicalRiskArtifactIndexRecord


_DEFAULT_BUSY_TIMEOUT_MS = 5000


class TechnicalPortfolioRiskPersistenceError(ValueError):
    """Raised when Technical portfolio generation persistence fails."""


@dataclass(frozen=True)
class TechnicalPortfolioRiskPersistenceResult:
    """Coordinator result preserving generation output and durable save outcomes."""

    generation_result: PortfolioRiskGenerationResult
    run_record: PortfolioRiskGenerationRunRecord
    artifact_save_results: tuple[RiskArtifactSaveResult, ...]
    run_save_result: PortfolioRiskGenerationRunSaveResult

    def __post_init__(self) -> None:
        if not isinstance(self.generation_result, PortfolioRiskGenerationResult):
            raise TechnicalPortfolioRiskPersistenceError("generation_result must be PortfolioRiskGenerationResult.")
        if not isinstance(self.run_record, PortfolioRiskGenerationRunRecord):
            raise TechnicalPortfolioRiskPersistenceError("run_record must be PortfolioRiskGenerationRunRecord.")
        if not isinstance(self.artifact_save_results, tuple):
            raise TechnicalPortfolioRiskPersistenceError("artifact_save_results must be a tuple.")
        if not all(isinstance(item, RiskArtifactSaveResult) for item in self.artifact_save_results):
            raise TechnicalPortfolioRiskPersistenceError("artifact_save_results must contain RiskArtifactSaveResult.")
        if not isinstance(self.run_save_result, PortfolioRiskGenerationRunSaveResult):
            raise TechnicalPortfolioRiskPersistenceError("run_save_result must be PortfolioRiskGenerationRunSaveResult.")


@dataclass(frozen=True)
class SQLiteTechnicalPortfolioRiskPersistenceCoordinator:
    """SQLite-specific portfolio-level Technical Risk persistence coordinator."""

    db_path: str | Path
    risk_evaluator: RiskEvaluator
    monitoring_evaluator: MonitoringEvaluator
    policy_resolver: ExactVersionPolicyResolver
    risk_definition_ids: tuple[str, ...] = ()
    busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS

    def __post_init__(self) -> None:
        try:
            path = validate_sqlite_db_path(self.db_path)
        except Exception as exc:
            raise TechnicalPortfolioRiskPersistenceError(str(exc)) from exc
        if not hasattr(self.risk_evaluator, "evaluate"):
            raise TechnicalPortfolioRiskPersistenceError("risk_evaluator must implement evaluate.")
        if not hasattr(self.monitoring_evaluator, "evaluate"):
            raise TechnicalPortfolioRiskPersistenceError("monitoring_evaluator must implement evaluate.")
        if not hasattr(self.policy_resolver, "resolve_risk_policy_version"):
            raise TechnicalPortfolioRiskPersistenceError("policy_resolver is invalid.")
        if not isinstance(self.risk_definition_ids, tuple):
            raise TechnicalPortfolioRiskPersistenceError("risk_definition_ids must be a tuple.")
        if not isinstance(self.busy_timeout_ms, int) or self.busy_timeout_ms <= 0:
            raise TechnicalPortfolioRiskPersistenceError("busy_timeout_ms must be a positive integer.")
        object.__setattr__(self, "db_path", path)

    def generate_and_persist(
        self,
        snapshot: PortfolioSnapshot,
        evaluation_input: RiskEvaluationInput,
        *,
        created_at: datetime,
    ) -> TechnicalPortfolioRiskPersistenceResult:
        _require_timezone_aware_datetime(created_at, "created_at")
        capturing_evaluator = CapturingRiskEvaluator(self.risk_evaluator)
        service = PortfolioRiskGenerationService(
            risk_evaluator=capturing_evaluator,
            monitoring_evaluator=self.monitoring_evaluator,
            policy_resolver=self.policy_resolver,
            risk_definition_ids=self.risk_definition_ids,
        )
        generation_result = service.generate(snapshot, evaluation_input)
        captured_artifacts = capturing_evaluator.captured_artifacts
        try:
            run_record = _build_run_record(
                evaluation_input=evaluation_input,
                generation_result=generation_result,
                captured_artifacts=captured_artifacts,
                created_at=created_at,
            )
            prepared_run_record = prepare_portfolio_run_record_for_persistence(run_record)
        except TechnicalPortfolioRiskPersistenceError:
            raise
        except Exception as exc:
            raise TechnicalPortfolioRiskPersistenceError("Technical portfolio run record pre-validation failed.") from exc

        try:
            artifact_save_results, run_save_result = self._persist(captured_artifacts, prepared_run_record)
        except TechnicalPortfolioRiskPersistenceError:
            raise
        except Exception as exc:
            raise TechnicalPortfolioRiskPersistenceError("Technical portfolio risk persistence failed.") from exc
        return TechnicalPortfolioRiskPersistenceResult(
            generation_result=generation_result,
            run_record=run_record,
            artifact_save_results=artifact_save_results,
            run_save_result=run_save_result,
        )

    def _persist(
        self,
        captured_artifacts: tuple[RiskArtifact, ...],
        prepared_run_record: _PreparedPortfolioRunRecordForPersistence,
    ) -> tuple[tuple[RiskArtifactSaveResult, ...], PortfolioRiskGenerationRunSaveResult]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            configure_sqlite_write_connection(connection, self.busy_timeout_ms)
            initialize_or_verify_schema(connection)
            try:
                connection.execute("BEGIN IMMEDIATE")
                run_record = prepared_run_record.record
                _verify_existing_run_artifact_refs(connection, run_record)
                artifact_results = tuple(
                    persist_technical_artifact_in_connection(connection, artifact)
                    for artifact in captured_artifacts
                )
                run_result = persist_portfolio_run_record_in_connection(connection, prepared_run_record)
                connection.commit()
                return artifact_results, run_result
            except Exception:
                if connection.in_transaction:
                    connection.rollback()
                raise
        except TechnicalPortfolioRiskPersistenceError:
            raise
        except Exception as exc:
            raise TechnicalPortfolioRiskPersistenceError("SQLite Technical portfolio persistence failed.") from exc
        finally:
            connection.close()


def _build_run_record(
    *,
    evaluation_input: RiskEvaluationInput,
    generation_result: PortfolioRiskGenerationResult,
    captured_artifacts: tuple[RiskArtifact, ...],
    created_at: datetime,
) -> PortfolioRiskGenerationRunRecord:
    projections = tuple(TechnicalRiskArtifactIndexRecord.from_artifact(artifact) for artifact in captured_artifacts)
    captured_position_ids = tuple(record.position_id for record in projections)
    _validate_captured_positions(generation_result, captured_position_ids)
    risk_refs = tuple(
        PortfolioRiskGenerationRunArtifactRef(
            position_id=projection.position_id,
            artifact_id=artifact.artifact_id,
            artifact_checksum=artifact.checksum or "",
        )
        for artifact, projection in zip(captured_artifacts, projections)
    )
    monitoring_refs = _monitoring_refs(generation_result)
    return PortfolioRiskGenerationRunRecord(
        calculation_id=evaluation_input.calculation_id,
        generation_key=evaluation_input.generation_key,
        feature_set_checksum=evaluation_input.feature_set_checksum,
        portfolio_id=evaluation_input.portfolio_id,
        snapshot_id=evaluation_input.snapshot_id,
        snapshot_checksum=evaluation_input.snapshot_checksum,
        analysis_date=evaluation_input.as_of_date,
        valuation_date=evaluation_input.valuation_date,
        status=generation_result.status,
        attempted_position_ids=generation_result.attempted_position_ids,
        risk_evaluated_position_ids=captured_position_ids,
        succeeded_position_ids=generation_result.succeeded_position_ids,
        failed_position_ids=generation_result.failed_position_ids,
        risk_artifact_refs=risk_refs,
        monitoring_artifact_refs=monitoring_refs,
        issues=_issues(generation_result),
        warnings=_warnings(generation_result),
        created_at=created_at,
    )


def _validate_captured_positions(
    generation_result: PortfolioRiskGenerationResult,
    captured_position_ids: tuple[str, ...],
) -> None:
    attempted_prefix = generation_result.attempted_position_ids[: len(captured_position_ids)]
    if captured_position_ids != attempted_prefix:
        raise TechnicalPortfolioRiskPersistenceError("captured RiskArtifacts do not match attempted position order.")


def _monitoring_refs(
    generation_result: PortfolioRiskGenerationResult,
) -> tuple[PortfolioRiskGenerationRunMonitoringArtifactRef, ...]:
    result_by_position = _position_result_map(generation_result.position_results)
    refs: list[PortfolioRiskGenerationRunMonitoringArtifactRef] = []
    for position_id in generation_result.succeeded_position_ids:
        position_result = result_by_position.get(position_id)
        if position_result is None:
            raise TechnicalPortfolioRiskPersistenceError("succeeded position missing generation result.")
        if not isinstance(position_result.monitoring_artifact_id, str) or not position_result.monitoring_artifact_id:
            raise TechnicalPortfolioRiskPersistenceError("succeeded position missing monitoring_artifact_id.")
        refs.append(
            PortfolioRiskGenerationRunMonitoringArtifactRef(
                position_id=position_id,
                artifact_id=position_result.monitoring_artifact_id,
            )
        )
    return tuple(refs)


def _position_result_map(
    position_results: tuple[PortfolioPositionGenerationResult, ...],
) -> dict[str, PortfolioPositionGenerationResult]:
    result_by_position: dict[str, PortfolioPositionGenerationResult] = {}
    for result in position_results:
        if result.position_id in result_by_position:
            raise TechnicalPortfolioRiskPersistenceError("position_results must not duplicate position_id.")
        result_by_position[result.position_id] = result
    return result_by_position


def _issues(generation_result: PortfolioRiskGenerationResult) -> tuple[PortfolioRiskGenerationRunIssue, ...]:
    stage = _stage_for_status(generation_result.status)
    position_id = generation_result.failed_position_ids[0] if len(generation_result.failed_position_ids) == 1 else None
    messages: list[tuple[str, str | None]] = [(message, position_id) for message in generation_result.errors]
    seen_messages = {message for message, _position_id in messages}
    for position_result in generation_result.position_results:
        for message in position_result.diagnostics:
            if message not in seen_messages:
                messages.append((message, position_result.position_id))
                seen_messages.add(message)
    return tuple(
        PortfolioRiskGenerationRunIssue(
            stage=stage,
            message=message,
            position_id=item_position_id,
        )
        for message, item_position_id in messages
    )


def _warnings(generation_result: PortfolioRiskGenerationResult) -> tuple[PortfolioRiskGenerationRunWarning, ...]:
    messages: list[tuple[str, str | None]] = []
    seen_messages: set[str] = set()
    for position_result in generation_result.position_results:
        for message in position_result.warnings:
            if message not in seen_messages:
                messages.append((message, position_result.position_id))
                seen_messages.add(message)
    for message in generation_result.warnings:
        if message not in seen_messages:
            messages.append((message, None))
            seen_messages.add(message)
    return tuple(
        PortfolioRiskGenerationRunWarning(
            stage="GENERATION",
            message=message,
            position_id=position_id,
        )
        for message, position_id in messages
    )


def _stage_for_status(status: PortfolioRiskGenerationStatus) -> str:
    if status == PortfolioRiskGenerationStatus.VALIDATION_FAILED:
        return "VALIDATION"
    if status == PortfolioRiskGenerationStatus.RISK_EVALUATION_FAILED:
        return "RISK_EVALUATION"
    if status == PortfolioRiskGenerationStatus.MONITORING_FAILED:
        return "MONITORING"
    return "GENERATION"


def _verify_existing_run_artifact_refs(
    connection: sqlite3.Connection,
    incoming_record: PortfolioRiskGenerationRunRecord,
) -> None:
    existing = load_portfolio_run_record_in_connection(connection, incoming_record.calculation_id)
    if existing is None:
        return
    if existing.risk_artifact_refs != incoming_record.risk_artifact_refs and existing.record_checksum == incoming_record.record_checksum:
        raise TechnicalPortfolioRiskPersistenceError("existing run record risk refs mismatch.")
    for ref in existing.risk_artifact_refs:
        if load_core_artifact_row(connection, ref.artifact_id) is None:
            cause = RiskArtifactCorruptionError(ref.artifact_id)
            raise TechnicalPortfolioRiskPersistenceError(
                "existing run record references missing RiskArtifact."
            ) from cause


def _require_timezone_aware_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TechnicalPortfolioRiskPersistenceError(f"{field_name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise TechnicalPortfolioRiskPersistenceError(f"{field_name} must be timezone-aware.")
    return value
