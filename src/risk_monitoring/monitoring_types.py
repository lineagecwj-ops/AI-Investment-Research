from enum import StrEnum


class MonitoringState(StrEnum):
    """Neutral monitoring state, not trading intent."""

    NORMAL = "NORMAL"
    WATCH = "WATCH"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ESCALATED_REVIEW = "ESCALATED_REVIEW"


class AlertLevel(StrEnum):
    """Metadata alert level for monitoring review."""

    INFO = "INFO"
    NOTICE = "NOTICE"
    REVIEW = "REVIEW"
    ESCALATED = "ESCALATED"


class AlertType(StrEnum):
    """Metadata alert candidate type."""

    RISK_MONITORING = "RISK_MONITORING"
    RISK_REVIEW = "RISK_REVIEW"
    ESCALATED_RISK_REVIEW = "ESCALATED_RISK_REVIEW"
