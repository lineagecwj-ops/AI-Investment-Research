import hashlib
import json
from datetime import date
from datetime import datetime
from enum import StrEnum
from typing import Any

from risk_monitoring.monitoring_artifact import RiskMonitoringArtifact
from risk_monitoring.monitoring_context import RiskMonitoringContext


class RiskMonitoringChecksumMismatchError(Exception):
    """Raised when reproduced monitoring checksum differs from expected value."""


class RiskMonitoringChecksumGenerator:
    """Deterministic checksum generator skeleton for risk monitoring artifacts."""

    def generate(self, artifact: RiskMonitoringArtifact, context: RiskMonitoringContext) -> str:
        payload = {
            "artifact_id": artifact.artifact_id,
            "portfolio_id": context.portfolio_id,
            "symbol": context.symbol,
            "monitoring_date": context.monitoring_date,
            "source_risk_artifact_id": context.source_risk_artifact_id,
            "risk_artifact_checksum": context.risk_artifact_checksum,
            "monitoring_policy_version": context.monitoring_policy_version,
            "calculation_id": context.calculation_id,
            "monitoring_state": artifact.monitoring_state,
            "overall_risk_level": artifact.overall_risk_level,
            "events": tuple(
                {
                    "event_id": event.event_id,
                    "source_risk_id": event.source_risk_id,
                    "risk_category": event.risk_category,
                    "risk_severity": event.risk_severity,
                    "monitoring_state": event.monitoring_state,
                    "reason": event.reason,
                    "created_at": event.created_at,
                }
                for event in sorted(artifact.events, key=lambda item: item.event_id)
            ),
            "alert_candidates": tuple(
                {
                    "alert_id": alert.alert_id,
                    "alert_level": alert.alert_level,
                    "alert_type": alert.alert_type,
                    "reason": alert.reason,
                    "source_event_ids": alert.source_event_ids,
                    "created_at": alert.created_at,
                }
                for alert in sorted(artifact.alert_candidates, key=lambda item: item.alert_id)
            ),
            "lineage": artifact.lineage,
            "calculation_metadata": artifact.calculation_metadata,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=self._json_default)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def verify(self, artifact: RiskMonitoringArtifact, context: RiskMonitoringContext, expected: str) -> None:
        actual = self.generate(artifact, context)
        if actual != expected:
            raise RiskMonitoringChecksumMismatchError(
                f"Risk monitoring checksum mismatch: expected {expected}, got {actual}."
            )

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, StrEnum):
            return value.value
        return value
