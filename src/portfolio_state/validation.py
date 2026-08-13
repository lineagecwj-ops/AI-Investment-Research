class PortfolioStateValidationError(ValueError):
    """Raised when portfolio state contract validation fails closed."""


class PortfolioSnapshotChecksumMismatchError(PortfolioStateValidationError):
    """Raised when a supplied snapshot checksum does not match canonical content."""


class GenerationIdentityMismatchError(PortfolioStateValidationError):
    """Raised when supplied generation identity does not match canonical input."""
