from __future__ import annotations

import hashlib
import json
import math
import warnings
from collections import Counter
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.metrics import brier_score_loss
from sklearn.metrics import confusion_matrix
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from database_config import PROJECT_ROOT
from evaluation.oos_splitter import OOSSplitter
from frozen_twse_research_universe_service import load_frozen_twse_research_universe
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from research_data_store import ResearchDataStore
from technical_indicator_service import build_technical_indicator_series


MODEL_ID = "UPSIDE_20D_LOGISTIC_BASELINE_V0"
ARTIFACT_SCHEMA_VERSION = "upside_20d_logistic_baseline_artifact_v1"
PRICE_SEMANTICS = "UPSIDE_20D_ADJUSTED_CLOSE_FIRST_V1"
FEATURE_SET_ID = "UPSIDE_20D_FIXED_8_FEATURES_V0"
FEATURE_ORDER = (
    "RETURN_5D",
    "RETURN_20D",
    "RETURN_60D",
    "CLOSE_VS_SMA20",
    "CLOSE_VS_SMA60",
    "RSI14",
    "VOLATILITY_20D",
    "VOLUME_RATIO20",
)
TRAIN = "TRAIN"
VALIDATION = "VALIDATION"
WORKFLOW_FROZEN_OOS = "WORKFLOW_FROZEN_OOS"
SPLITS = {
    TRAIN: (date(2018, 1, 1), date(2022, 12, 31)),
    VALIDATION: (date(2023, 1, 1), date(2024, 12, 31)),
    WORKFLOW_FROZEN_OOS: (date(2025, 1, 1), date(2025, 12, 31)),
}
EVALUATED_SPLITS = (TRAIN, VALIDATION)
TARGET_HORIZON = 20
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "upside_20d_probability"
    / "upside_20d_logistic_baseline_v0.json"
)


@dataclass(frozen=True)
class Upside20DDatasetRow:
    symbol: str
    as_of_date: date
    features: tuple[float, ...]
    up_20d: int
    target_date: date
    split: str


@dataclass(frozen=True)
class Upside20DDataset:
    rows: tuple[Upside20DDatasetRow, ...]
    requested_symbols: tuple[str, ...]
    usable_symbols: tuple[str, ...]
    excluded_symbols: tuple[str, ...]
    symbol_exclusion_reasons: dict[str, str]
    exclusion_counts: dict[str, int]

    def rows_for(self, split: str) -> tuple[Upside20DDatasetRow, ...]:
        return tuple(row for row in self.rows if row.split == split)


def research_price(bar: HistoricalPriceBar) -> float | None:
    if _is_finite_number(bar.adjusted_close):
        return float(bar.adjusted_close)
    if _is_finite_number(bar.close):
        return float(bar.close)
    return None


def up_20d_target(
    bars: tuple[HistoricalPriceBar, ...],
    reference_index: int,
) -> tuple[int, date] | None:
    target_index = reference_index + TARGET_HORIZON
    if reference_index < 0 or target_index >= len(bars):
        return None
    reference_price = research_price(bars[reference_index])
    future_price = research_price(bars[target_index])
    if not _is_positive_finite(reference_price) or not _is_positive_finite(future_price):
        return None
    return (int(future_price > reference_price), bars[target_index].trading_date)


def workflow_split(value: date) -> str | None:
    for split, (start, end) in SPLITS.items():
        if start <= value <= end:
            return split
    return None


def canonical_research_price_series(series: HistoricalPriceSeries) -> HistoricalPriceSeries:
    bars = []
    for bar in series.bars:
        price = research_price(bar)
        canonical_price = price if price is not None else float("nan")
        bars.append(
            HistoricalPriceBar(
                symbol=bar.symbol,
                trading_date=bar.trading_date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=canonical_price,
                adjusted_close=canonical_price,
                volume=bar.volume,
                dividends=bar.dividends,
                stock_splits=bar.stock_splits,
            )
        )
    return HistoricalPriceSeries(
        symbol=series.symbol,
        currency=series.currency,
        bars=tuple(bars),
        fetched_at=series.fetched_at,
        is_stale=series.is_stale,
        source=series.source,
    )


def build_symbol_dataset_rows(
    series: HistoricalPriceSeries,
) -> tuple[tuple[Upside20DDatasetRow, ...], Counter[str]]:
    bars = tuple(sorted(series.bars, key=lambda bar: bar.trading_date))
    if len({bar.trading_date for bar in bars}) != len(bars):
        return (), Counter({"DUPLICATE_TRADING_DATE": 1})

    feature_bars = tuple(bar for bar in bars if bar.trading_date <= SPLITS[VALIDATION][1])
    canonical_series = canonical_research_price_series(
        HistoricalPriceSeries(
            symbol=series.symbol,
            currency=series.currency,
            bars=feature_bars,
            fetched_at=series.fetched_at,
            is_stale=series.is_stale,
            source=series.source,
        )
    )
    snapshots = {
        snapshot.trading_date: snapshot
        for snapshot in build_technical_indicator_series(canonical_series).snapshots
    }

    rows = []
    exclusions: Counter[str] = Counter()
    for index, bar in enumerate(bars):
        split = workflow_split(bar.trading_date)
        if split not in EVALUATED_SPLITS:
            continue
        target_index = index + TARGET_HORIZON
        if target_index >= len(bars):
            exclusions["INSUFFICIENT_FUTURE_20_BARS"] += 1
            continue
        target_bar = bars[target_index]
        if workflow_split(target_bar.trading_date) != split:
            exclusions[f"{split}_TARGET_CROSSES_SPLIT"] += 1
            continue

        target = up_20d_target(bars, index)
        if target is None:
            exclusions["MISSING_OR_INVALID_RESEARCH_PRICE"] += 1
            continue
        snapshot = snapshots.get(bar.trading_date)
        if snapshot is None:
            exclusions["MISSING_TECHNICAL_SNAPSHOT"] += 1
            continue
        features = _feature_values(snapshot)
        if features is None:
            exclusions["INCOMPLETE_OR_NONFINITE_FEATURES"] += 1
            continue
        target_value, target_date = target
        rows.append(
            Upside20DDatasetRow(
                symbol=series.symbol,
                as_of_date=bar.trading_date,
                features=features,
                up_20d=target_value,
                target_date=target_date,
                split=split,
            )
        )
    return tuple(rows), exclusions


def assemble_upside_20d_dataset(
    *,
    research_store: ResearchDataStore | None = None,
) -> tuple[Upside20DDataset, dict[str, object]]:
    OOSSplitter().validate_ordering(
        tuple(value.isoformat() for value in SPLITS[TRAIN]),
        tuple(value.isoformat() for value in SPLITS[VALIDATION]),
        tuple(value.isoformat() for value in SPLITS[WORKFLOW_FROZEN_OOS]),
    )
    store = research_store or ResearchDataStore()
    runtime_identity = store.verify_runtime_identity(verify_db_sha=False)
    universe = load_frozen_twse_research_universe(research_store=store)
    rows = []
    exclusions: Counter[str] = Counter()
    usable_symbols = []
    symbol_exclusion_reasons: dict[str, str] = {}
    for symbol in universe.symbols:
        try:
            series = store.load_historical_price_series(symbol)
            symbol_rows, symbol_exclusions = build_symbol_dataset_rows(series)
        except Exception as exc:
            symbol_exclusion_reasons[symbol] = f"LOAD_FAILED:{type(exc).__name__}"
            exclusions["SYMBOL_LOAD_FAILED"] += 1
            continue
        exclusions.update(symbol_exclusions)
        if symbol_rows:
            usable_symbols.append(symbol)
            rows.extend(symbol_rows)
        else:
            symbol_exclusion_reasons[symbol] = "NO_USABLE_ROWS"
            exclusions["SYMBOL_NO_USABLE_ROWS"] += 1

    ordered_rows = tuple(sorted(rows, key=lambda row: (row.symbol, row.as_of_date)))
    usable = tuple(usable_symbols)
    excluded = tuple(symbol for symbol in universe.symbols if symbol not in set(usable))
    return (
        Upside20DDataset(
            rows=ordered_rows,
            requested_symbols=universe.symbols,
            usable_symbols=usable,
            excluded_symbols=excluded,
            symbol_exclusion_reasons=symbol_exclusion_reasons,
            exclusion_counts=dict(sorted(exclusions.items())),
        ),
        {
            "runtime_identity": runtime_identity,
            "universe_id": universe.universe_id,
            "universe_version": universe.universe_version,
        },
    )


def fit_logistic_baseline(dataset: Upside20DDataset) -> dict[str, object]:
    train_rows = dataset.rows_for(TRAIN)
    validation_rows = dataset.rows_for(VALIDATION)
    if not train_rows or not validation_rows:
        raise ValueError("TRAIN and VALIDATION rows are required.")

    x_train, y_train = _matrix(train_rows)
    x_validation, y_validation = _matrix(validation_rows)
    model = Pipeline(
        steps=(
            ("standard_scaler", StandardScaler()),
            (
                "logistic_regression",
                LogisticRegression(
                    penalty="l2",
                    solver="lbfgs",
                    class_weight=None,
                    C=1.0,
                    max_iter=1000,
                    random_state=None,
                ),
            ),
        )
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        model.fit(x_train, y_train)
    convergence_warnings = [str(item.message) for item in caught if issubclass(item.category, ConvergenceWarning)]

    probabilities = model.predict_proba(x_validation)[:, 1]
    if not np.all(np.isfinite(probabilities)) or not np.all((0.0 <= probabilities) & (probabilities <= 1.0)):
        raise ValueError("Validation probabilities must be finite and within [0, 1].")
    predictions = (probabilities >= 0.5).astype(int)
    train_rate = float(np.mean(y_train))
    validation_rate = float(np.mean(y_validation))
    validation_metrics = _classification_metrics(y_validation, probabilities, predictions)
    constant_probabilities = np.full_like(probabilities, train_rate, dtype=float)
    constant_brier = float(brier_score_loss(y_validation, constant_probabilities))
    scaler = model.named_steps["standard_scaler"]
    logistic = model.named_steps["logistic_regression"]
    coefficients = [
        {"feature": feature, "coefficient": float(value)}
        for feature, value in zip(FEATURE_ORDER, logistic.coef_[0], strict=True)
    ]
    coefficients.sort(key=lambda item: (-abs(item["coefficient"]), item["feature"]))

    return {
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "train_symbols": len({row.symbol for row in train_rows}),
        "validation_symbols": len({row.symbol for row in validation_rows}),
        "train_up_rate": train_rate,
        "validation_up_rate": validation_rate,
        "validation_probabilities": probabilities.tolist(),
        "validation_metrics": validation_metrics,
        "constant_baseline": {
            "probability": train_rate,
            "brier_score": constant_brier,
            "logistic_minus_constant_brier": validation_metrics["brier_score"] - constant_brier,
        },
        "calibration_bands": _calibration_bands(y_validation, probabilities),
        "probability_deciles": _probability_deciles(y_validation, probabilities),
        "annual_validation_metrics": _annual_metrics(validation_rows, y_validation, probabilities),
        "coefficients": coefficients,
        "intercept": float(logistic.intercept_[0]),
        "scaler_mean": [float(value) for value in scaler.mean_],
        "scaler_scale": [float(value) for value in scaler.scale_],
        "n_iter": int(logistic.n_iter_[0]),
        "converged": not convergence_warnings and int(logistic.n_iter_[0]) < logistic.max_iter,
        "convergence_warnings": convergence_warnings,
    }


def build_result_artifact(
    dataset: Upside20DDataset,
    source_identity: dict[str, object],
    model_result: dict[str, object],
    *,
    generated_at: datetime,
) -> dict[str, object]:
    deciles = model_result["probability_deciles"]
    artifact = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_id": MODEL_ID,
        "generated_at": generated_at.astimezone(UTC).isoformat(),
        "research_scope": "RESEARCH_EXPERIMENTAL_ONLY",
        "model_identity": MODEL_ID,
        "research_snapshot": source_identity["runtime_identity"],
        "universe": {
            "universe_id": source_identity["universe_id"],
            "universe_version": source_identity["universe_version"],
            "requested_symbols": len(dataset.requested_symbols),
            "usable_symbols": len(dataset.usable_symbols),
            "excluded_symbols": list(dataset.excluded_symbols),
            "symbol_exclusion_reasons": dataset.symbol_exclusion_reasons,
            "population_description": "Frozen TWSE research universe",
        },
        "price_semantics": {
            "version": PRICE_SEMANTICS,
            "definition": "adjusted_close when present and finite, otherwise raw close",
        },
        "feature_set": {
            "feature_set_id": FEATURE_SET_ID,
            "ordered_features": list(FEATURE_ORDER),
            "timing_rule": "Each feature uses observations available on or before as_of_date.",
        },
        "target": {
            "target_id": "UP_20D_V0",
            "horizon_trading_bars": TARGET_HORIZON,
            "definition": "1 when research_price[t+20] > research_price[t], otherwise 0",
            "equal_price_target": 0,
        },
        "temporal_workflow": {
            "splits": {
                name: {"start": period[0].isoformat(), "end": period[1].isoformat()}
                for name, period in SPLITS.items()
            },
            "evaluated_splits": list(EVALUATED_SPLITS),
            "workflow_frozen_oos_evaluated": False,
            "data_from_2026_used": False,
            "purge_rule": "as_of_date and target_date must be in the same split",
        },
        "dataset": {
            "ordering": "symbol,as_of_date",
            "total_usable_rows": len(dataset.rows),
            "train_rows": model_result["train_rows"],
            "validation_rows": model_result["validation_rows"],
            "train_symbols": model_result["train_symbols"],
            "validation_symbols": model_result["validation_symbols"],
            "exclusion_counts": dataset.exclusion_counts,
        },
        "dependency": {"scikit_learn_version": sklearn.__version__},
        "pipeline": {
            "steps": ["StandardScaler", "LogisticRegression"],
            "configuration": {
                "penalty": "l2",
                "solver": "lbfgs",
                "class_weight": None,
                "C": 1.0,
                "max_iter": 1000,
                "hyperparameter_tuning": False,
            },
            "converged": model_result["converged"],
            "n_iter": model_result["n_iter"],
            "convergence_warnings": model_result["convergence_warnings"],
        },
        "model_parameters": {
            "intercept": model_result["intercept"],
            "standardized_coefficients": model_result["coefficients"],
            "scaler_mean": model_result["scaler_mean"],
            "scaler_scale": model_result["scaler_scale"],
        },
        "metrics": {
            "train_up_rate": model_result["train_up_rate"],
            "validation_up_rate": model_result["validation_up_rate"],
            "validation": model_result["validation_metrics"],
            "constant_baseline": model_result["constant_baseline"],
            "calibration_bands": model_result["calibration_bands"],
            "probability_deciles": deciles,
            "high_minus_low_decile_actual_up_rate": deciles[-1]["actual_up_rate"] - deciles[0]["actual_up_rate"],
            "annual_validation": model_result["annual_validation_metrics"],
        },
        "limitations": [
            "Adjusted historical prices may reflect subsequently known corporate-action adjustments; perfect point-in-time corporate-action reconstruction is not claimed.",
            "SURVIVORSHIP_BIAS_HANDLING=NOT_IMPLEMENTED / UNKNOWN.",
            "The evaluation population is the Frozen TWSE research universe, not the complete historical Taiwan equity market.",
            "Model coefficients are descriptive associations, not causal effects.",
            "No 2025 WORKFLOW_FROZEN_OOS performance was inspected in Sprint 1.",
        ],
    }
    artifact["artifact_checksum"] = _stable_hash(artifact)
    return artifact


def run_research_baseline(
    *,
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    dataset, source_identity = assemble_upside_20d_dataset()
    model_result = fit_logistic_baseline(dataset)
    artifact = build_result_artifact(
        dataset,
        source_identity,
        model_result,
        generated_at=generated_at or datetime.now(UTC),
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _feature_values(snapshot) -> tuple[float, ...] | None:
    if not _is_positive_finite(snapshot.analysis_close):
        return None
    if not _is_positive_finite(snapshot.sma_20) or not _is_positive_finite(snapshot.sma_60):
        return None
    values = (
        snapshot.return_5d,
        snapshot.return_20d,
        snapshot.return_60d,
        snapshot.analysis_close / snapshot.sma_20 - 1.0,
        snapshot.analysis_close / snapshot.sma_60 - 1.0,
        snapshot.rsi_14,
        snapshot.return_volatility_20d,
        snapshot.volume_ratio_20,
    )
    if not all(_is_finite_number(value) for value in values):
        return None
    return tuple(float(value) for value in values)


def _matrix(rows: Iterable[Upside20DDatasetRow]) -> tuple[np.ndarray, np.ndarray]:
    materialized = tuple(rows)
    return (
        np.asarray([row.features for row in materialized], dtype=float),
        np.asarray([row.up_20d for row in materialized], dtype=int),
    )


def _classification_metrics(y_true, probabilities, predictions) -> dict[str, object]:
    tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    return {
        "row_count": int(len(y_true)),
        "observed_up_rate": float(np.mean(y_true)),
        "mean_predicted_probability": float(np.mean(probabilities)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "accuracy_at_0_50": float(accuracy_score(y_true, predictions)),
        "confusion_at_0_50": {"tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)},
    }


def _calibration_bands(y_true: np.ndarray, probabilities: np.ndarray) -> list[dict[str, object]]:
    indexes = np.minimum((probabilities * 10).astype(int), 9)
    rows = []
    for band_index in range(10):
        mask = indexes == band_index
        if not np.any(mask):
            continue
        mean_probability = float(np.mean(probabilities[mask]))
        actual_rate = float(np.mean(y_true[mask]))
        rows.append(
            {
                "band": f"[{band_index / 10:.1f},{(band_index + 1) / 10:.1f}{']' if band_index == 9 else ')'}",
                "count": int(np.sum(mask)),
                "mean_predicted_probability": mean_probability,
                "actual_up_rate": actual_rate,
                "actual_minus_predicted": actual_rate - mean_probability,
            }
        )
    return rows


def _probability_deciles(y_true: np.ndarray, probabilities: np.ndarray) -> list[dict[str, object]]:
    order = np.argsort(probabilities, kind="mergesort")
    rows = []
    for decile, indexes in enumerate(np.array_split(order, 10), start=1):
        rows.append(
            {
                "decile": decile,
                "count": int(len(indexes)),
                "mean_predicted_probability": float(np.mean(probabilities[indexes])),
                "actual_up_rate": float(np.mean(y_true[indexes])),
            }
        )
    return rows


def _annual_metrics(
    validation_rows: tuple[Upside20DDatasetRow, ...],
    y_true: np.ndarray,
    probabilities: np.ndarray,
) -> dict[str, dict[str, object]]:
    output = {}
    for year in (2023, 2024):
        indexes = np.asarray([index for index, row in enumerate(validation_rows) if row.as_of_date.year == year])
        year_truth = y_true[indexes]
        year_probabilities = probabilities[indexes]
        output[str(year)] = {
            "rows": int(len(indexes)),
            "symbols": len({validation_rows[index].symbol for index in indexes}),
            "observed_up_rate": float(np.mean(year_truth)),
            "mean_predicted_probability": float(np.mean(year_probabilities)),
            "roc_auc": float(roc_auc_score(year_truth, year_probabilities)),
            "brier_score": float(brier_score_loss(year_truth, year_probabilities)),
        }
    return output


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _is_positive_finite(value: object) -> bool:
    return _is_finite_number(value) and float(value) > 0.0


def _stable_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def main() -> None:
    artifact = run_research_baseline()
    summary = {
        "artifact_id": artifact["artifact_id"],
        "artifact_checksum": artifact["artifact_checksum"],
        "artifact_path": str(DEFAULT_OUTPUT_PATH),
        "dataset": artifact["dataset"],
        "metrics": artifact["metrics"],
        "pipeline": artifact["pipeline"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
