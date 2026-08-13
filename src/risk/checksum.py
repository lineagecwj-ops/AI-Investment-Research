import hashlib
import json
from datetime import date
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from risk.risk_artifact import RiskArtifact
from risk.risk_context import RiskContext


class RiskChecksumMismatchError(Exception):
    """Raised when reproduced risk checksum differs from expected value."""


class RiskChecksumGenerator:
    """Deterministic checksum generator for risk artifacts."""

    def generate(self, artifact: RiskArtifact, context: RiskContext) -> str:
        payload = {
            "artifact_id": artifact.artifact_id,
            "position_identity": artifact.position_identity,
            "portfolio_id": context.portfolio_id,
            "symbol": context.symbol,
            "analysis_date": context.analysis_date,
            "feature_version": context.feature_version,
            "model_version": context.model_version,
            "calculation_id": context.calculation_id,
            "assessment": {
                "overall_risk_level": artifact.risk_assessment.overall_risk_level,
                "assessment_date": artifact.risk_assessment.assessment_date,
            },
            "signals": tuple(
                {
                    "risk_id": signal.risk_id,
                    "symbol": signal.symbol,
                    "category": signal.category,
                    "severity": signal.severity,
                    "trigger_reason": signal.trigger_reason,
                    "created_at": signal.created_at,
                }
                for signal in sorted(
                    artifact.signals,
                    key=lambda item: (item.symbol, item.risk_id, item.severity.value, item.created_at.isoformat()),
                )
            ),
            "feature_lineage": artifact.feature_lineage,
            "calculation_metadata": artifact.calculation_metadata,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=self._json_default)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def verify(self, artifact: RiskArtifact, context: RiskContext, expected: str) -> None:
        actual = self.generate(artifact, context)
        if actual != expected:
            raise RiskChecksumMismatchError(f"Risk checksum mismatch: expected {expected}, got {actual}.")

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, StrEnum):
            return value.value
        return value
