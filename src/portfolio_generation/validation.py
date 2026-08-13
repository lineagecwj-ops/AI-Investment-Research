class PortfolioGenerationValidationError(ValueError):
    """Raised when portfolio generation contract validation fails closed."""


class PositionAdapterError(PortfolioGenerationValidationError):
    """Raised when a portfolio state position cannot be adapted for risk input."""


class RiskContextBuilderError(PortfolioGenerationValidationError):
    """Raised when a deterministic RiskContext cannot be built."""


class MonitoringContextBuilderError(PortfolioGenerationValidationError):
    """Raised when a deterministic RiskMonitoringContext cannot be built."""


class PolicyResolverError(PortfolioGenerationValidationError):
    """Raised when exact-version policy resolution fails."""
