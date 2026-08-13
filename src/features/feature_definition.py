from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureDefinition:
    """Versioned metadata that defines a feature without calculating it."""

    feature_id: str
    feature_name: str
    category: str
    version: str
    description: str
    formula_version: str
    dependencies: tuple[str, ...] = ()
    input_fields: tuple[str, ...] = ()

    def __post_init__(self):
        required = {
            "feature_id": self.feature_id,
            "feature_name": self.feature_name,
            "category": self.category,
            "version": self.version,
            "formula_version": self.formula_version,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"FeatureDefinition missing required fields: {', '.join(missing)}")
