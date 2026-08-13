from datetime import date
from datetime import datetime
from decimal import Decimal
from numbers import Real
from typing import Any

from risk import RiskCategory


class RiskEvaluationContractError(ValueError):
    """Raised when a production risk evaluation contract is invalid."""


class RiskFeatureInputError(RiskEvaluationContractError):
    """Raised when a frozen risk feature input is invalid."""


class RiskSignalProductionInputError(RiskEvaluationContractError):
    """Raised when a per-position signal production input is invalid."""


class RiskEvaluationPolicyError(RiskEvaluationContractError):
    """Raised when a risk evaluation policy contract is invalid."""


class RiskSignalProducerError(RiskEvaluationContractError):
    """Raised when a produced risk signal contract is invalid."""


def require_non_empty_text(value: str, field_name: str, error_type: type[RiskEvaluationContractError]) -> None:
    if not isinstance(value, str) or not value:
        raise error_type(f"{field_name} is required.")


def require_date(value: date, field_name: str, error_type: type[RiskEvaluationContractError]) -> None:
    if not isinstance(value, date):
        raise error_type(f"{field_name} must be a date.")


def require_timezone_aware_datetime(
    value: datetime,
    field_name: str,
    error_type: type[RiskEvaluationContractError],
) -> None:
    if not isinstance(value, datetime):
        raise error_type(f"{field_name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise error_type(f"{field_name} must be timezone-aware.")


def require_numeric_value(value: Decimal | int | float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (Decimal, Real)):
        raise RiskFeatureInputError(f"{field_name} must be a Decimal-compatible numeric value.")


def normalize_text_tuple(values: tuple[str, ...], field_name: str, error_type: type[RiskEvaluationContractError]) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise error_type(f"{field_name} must be a tuple.")
    if any(not isinstance(value, str) or not value for value in values):
        raise error_type(f"{field_name} must contain non-empty strings.")
    if len(set(values)) != len(values):
        raise error_type(f"{field_name} must not contain duplicates.")
    return tuple(sorted(values))


def normalize_categories(
    categories: tuple[RiskCategory | str, ...],
    field_name: str,
) -> tuple[RiskCategory, ...]:
    if not isinstance(categories, tuple):
        raise RiskEvaluationPolicyError(f"{field_name} must be a tuple.")
    if not categories:
        raise RiskEvaluationPolicyError(f"{field_name} cannot be empty.")
    normalized: list[RiskCategory] = []
    for category in categories:
        try:
            normalized.append(RiskCategory(category))
        except ValueError as exc:
            raise RiskEvaluationPolicyError(f"Unknown risk category: {category}") from exc
    if len(set(normalized)) != len(normalized):
        raise RiskEvaluationPolicyError(f"{field_name} must not contain duplicates.")
    return tuple(sorted(normalized, key=lambda item: item.value))


def normalize_string_mapping(
    values: dict[Any, Any] | None,
    field_name: str,
    *,
    allow_empty: bool = True,
) -> dict[str, str]:
    if values is None:
        if allow_empty:
            return {}
        raise RiskEvaluationPolicyError(f"{field_name} is required.")
    if not isinstance(values, dict):
        raise RiskEvaluationPolicyError(f"{field_name} must be a dict.")
    normalized = {str(key): str(value) for key, value in sorted(values.items(), key=lambda item: str(item[0]))}
    if not allow_empty and not normalized:
        raise RiskEvaluationPolicyError(f"{field_name} cannot be empty.")
    if any(not key or not value for key, value in normalized.items()):
        raise RiskEvaluationPolicyError(f"{field_name} must contain non-empty keys and values.")
    return normalized
