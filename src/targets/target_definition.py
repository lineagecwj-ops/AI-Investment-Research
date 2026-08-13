from dataclasses import dataclass


@dataclass(frozen=True)
class TargetDefinition:
    """Versioned metadata describing a target calculation."""

    target_id: str
    target_name: str
    target_type: str
    version: str
    calculation_window: int
    formula_version: str
    description: str
    requires_window_lineage: bool = False

    def __post_init__(self):
        required = {
            "target_id": self.target_id,
            "target_name": self.target_name,
            "target_type": self.target_type,
            "version": self.version,
            "formula_version": self.formula_version,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"TargetDefinition missing required fields: {', '.join(missing)}")
        if self.calculation_window <= 0:
            raise ValueError("TargetDefinition calculation_window must be positive.")
