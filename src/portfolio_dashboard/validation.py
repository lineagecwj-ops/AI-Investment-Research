from risk_monitoring.monitoring_artifact import RiskMonitoringArtifact

from portfolio_dashboard.formatter import FORBIDDEN_DISPLAY_TERMS


class PortfolioDashboardValidationError(ValueError):
    """Raised when monitoring artifacts cannot be projected safely."""


REQUIRED_ARTIFACT_FIELDS = (
    "artifact_id",
    "portfolio_id",
    "symbol",
    "monitoring_state",
    "overall_risk_level",
    "source_risk_artifact_id",
    "source_risk_checksum",
    "events",
    "alert_candidates",
    "policy_version",
    "lineage",
    "calculation_metadata",
    "created_at",
    "checksum",
)


class PortfolioDashboardValidator:
    """Validate artifact-only dashboard inputs."""

    def validate_artifacts(self, artifacts: tuple[RiskMonitoringArtifact, ...]) -> None:
        if not isinstance(artifacts, tuple):
            raise PortfolioDashboardValidationError("Portfolio dashboard input must be a tuple.")
        artifact_ids = tuple(getattr(artifact, "artifact_id", None) for artifact in artifacts)
        duplicates = sorted(
            artifact_id
            for artifact_id in set(artifact_ids)
            if artifact_id is not None and artifact_ids.count(artifact_id) > 1
        )
        if duplicates:
            raise PortfolioDashboardValidationError(
                f"Portfolio dashboard input contains duplicate artifact_id values: {', '.join(duplicates)}"
            )
        for artifact in artifacts:
            self.validate_artifact(artifact)

    def validate_artifact(self, artifact: RiskMonitoringArtifact) -> None:
        self._validate_artifact_compatibility(artifact)
        if not isinstance(artifact, RiskMonitoringArtifact):
            raise PortfolioDashboardValidationError("Expected RiskMonitoringArtifact input.")
        self._validate_required_text_fields(artifact)
        if artifact.calculation_metadata.get("event_count") != len(artifact.events):
            raise PortfolioDashboardValidationError("Monitoring artifact event_count mismatch.")
        if artifact.calculation_metadata.get("alert_candidate_count") != len(artifact.alert_candidates):
            raise PortfolioDashboardValidationError("Monitoring artifact alert_candidate_count mismatch.")
        self._validate_events(artifact)
        self._validate_alert_candidates(artifact)
        self._validate_lineage(artifact)
        self._validate_checksum(artifact)
        self._validate_no_trading_semantics(artifact)

    def _validate_artifact_compatibility(self, artifact) -> None:
        missing = [field for field in REQUIRED_ARTIFACT_FIELDS if not hasattr(artifact, field)]
        if missing:
            raise PortfolioDashboardValidationError(
                "RiskMonitoringArtifact missing required dashboard fields: "
                + ", ".join(missing)
            )

    def _validate_required_text_fields(self, artifact: RiskMonitoringArtifact) -> None:
        required = {
            "artifact_id": artifact.artifact_id,
            "portfolio_id": artifact.portfolio_id,
            "symbol": artifact.symbol,
            "overall_risk_level": artifact.overall_risk_level,
            "source_risk_artifact_id": artifact.source_risk_artifact_id,
            "source_risk_checksum": artifact.source_risk_checksum,
            "policy_version": artifact.policy_version,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise PortfolioDashboardValidationError(
                "RiskMonitoringArtifact missing required values: "
                + ", ".join(missing)
            )

    def _validate_events(self, artifact: RiskMonitoringArtifact) -> None:
        if not isinstance(artifact.events, tuple):
            raise PortfolioDashboardValidationError("Monitoring events must be a tuple.")
        event_ids = tuple(event.event_id for event in artifact.events)
        if len(set(event_ids)) != len(event_ids):
            raise PortfolioDashboardValidationError("Monitoring events must have unique event_id values.")
        for event in artifact.events:
            if event.portfolio_id != artifact.portfolio_id:
                raise PortfolioDashboardValidationError("Monitoring event portfolio_id mismatch.")
            if event.symbol != artifact.symbol:
                raise PortfolioDashboardValidationError("Monitoring event symbol mismatch.")

    def _validate_alert_candidates(self, artifact: RiskMonitoringArtifact) -> None:
        if not isinstance(artifact.alert_candidates, tuple):
            raise PortfolioDashboardValidationError("Alert candidates must be a tuple.")
        event_ids = {event.event_id for event in artifact.events}
        alert_ids = tuple(alert.alert_id for alert in artifact.alert_candidates)
        if len(set(alert_ids)) != len(alert_ids):
            raise PortfolioDashboardValidationError("Alert candidates must have unique alert_id values.")
        for alert in artifact.alert_candidates:
            if alert.portfolio_id != artifact.portfolio_id:
                raise PortfolioDashboardValidationError("Alert candidate portfolio_id mismatch.")
            if alert.symbol != artifact.symbol:
                raise PortfolioDashboardValidationError("Alert candidate symbol mismatch.")
            if not set(alert.source_event_ids).issubset(event_ids):
                raise PortfolioDashboardValidationError("Alert candidate references unknown monitoring event.")

    def _validate_lineage(self, artifact: RiskMonitoringArtifact) -> None:
        if not isinstance(artifact.lineage, dict):
            raise PortfolioDashboardValidationError("Monitoring artifact lineage must be a dict.")
        required_lineage = (
            "risk_artifact_id",
            "risk_artifact_checksum",
            "risk_assessment_date",
            "risk_engine_feature_version",
            "risk_engine_model_version",
            "risk_overall_level",
        )
        missing = [field for field in required_lineage if not artifact.lineage.get(field)]
        if missing:
            raise PortfolioDashboardValidationError(
                "Monitoring artifact lineage missing required fields: "
                + ", ".join(missing)
            )
        if artifact.lineage.get("risk_artifact_id") != artifact.source_risk_artifact_id:
            raise PortfolioDashboardValidationError("Monitoring artifact lineage risk artifact mismatch.")
        if artifact.lineage.get("risk_artifact_checksum") != artifact.source_risk_checksum:
            raise PortfolioDashboardValidationError("Monitoring artifact lineage checksum mismatch.")

    def _validate_checksum(self, artifact: RiskMonitoringArtifact) -> None:
        if not artifact.source_risk_checksum:
            raise PortfolioDashboardValidationError("Monitoring artifact source risk checksum is required.")
        if artifact.checksum is not None and not isinstance(artifact.checksum, str):
            raise PortfolioDashboardValidationError("Monitoring artifact checksum must be a string when provided.")
        if artifact.checksum == "":
            raise PortfolioDashboardValidationError("Monitoring artifact checksum cannot be empty when provided.")

    def _validate_no_trading_semantics(self, artifact: RiskMonitoringArtifact) -> None:
        text_parts = [
            artifact.artifact_id,
            artifact.portfolio_id,
            artifact.symbol,
            str(artifact.monitoring_state),
            artifact.overall_risk_level,
            artifact.policy_version,
        ]
        text_parts.extend(event.reason for event in artifact.events)
        text_parts.extend(alert.reason for alert in artifact.alert_candidates)
        text = " ".join(text_parts).lower()
        for term in FORBIDDEN_DISPLAY_TERMS:
            if term.lower() in text:
                raise PortfolioDashboardValidationError(
                    f"Portfolio dashboard input contains forbidden term: {term}"
                )
