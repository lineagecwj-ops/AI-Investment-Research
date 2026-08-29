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

import numpy as np
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from database_config import PROJECT_ROOT
from evaluation.oos_splitter import OOSSplitter
from frozen_twse_research_universe_service import load_frozen_twse_research_universe
from models import HistoricalPriceSeries
from relative_20d_0050_logistic_baseline import BENCHMARK_ROLE
from relative_20d_0050_logistic_baseline import BENCHMARK_SYMBOL
from relative_20d_0050_logistic_baseline import TARGET_ID
from relative_20d_0050_logistic_baseline import build_benchmark_price_lookup
from relative_20d_0050_logistic_baseline import relative_outperform_20d_target
from research_data_store import ResearchDataStore
from technical_indicator_service import build_technical_indicator_series
from upside_20d_logistic_baseline import SPLITS
from upside_20d_logistic_baseline import TARGET_HORIZON
from upside_20d_logistic_baseline import TRAIN
from upside_20d_logistic_baseline import VALIDATION
from upside_20d_logistic_baseline import WORKFLOW_FROZEN_OOS
from upside_20d_logistic_baseline import _annual_metrics
from upside_20d_logistic_baseline import _calibration_bands
from upside_20d_logistic_baseline import _classification_metrics
from upside_20d_logistic_baseline import _probability_deciles
from upside_20d_logistic_baseline import canonical_research_price_series


MODEL_ID = "RELATIVE_STRENGTH_20D_0050_LOGISTIC_V0"
ARTIFACT_SCHEMA_VERSION = "relative_strength_20d_0050_logistic_artifact_v1"
PRICE_SEMANTICS = "RELATIVE_20D_ADJUSTED_CLOSE_FIRST_V1"
FEATURE_SET_ID = "RELATIVE_STRENGTH_0050_FIXED_6_FEATURES_V0"
DEVELOPMENT_EVALUATION = "DEVELOPMENT_EVALUATION"
EVALUATED_SPLITS = (TRAIN, DEVELOPMENT_EVALUATION)
FEATURE_ORDER = (
    "REL_RETURN_5D",
    "REL_RETURN_20D",
    "REL_RETURN_60D",
    "REL_TREND_20",
    "REL_TREND_60",
    "REL_RSI14",
)
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "upside_20d_probability"
    / "relative_strength_20d_0050_logistic_v0.json"
)


@dataclass(frozen=True)
class RelativeStrength20DDatasetRow:
    symbol: str
    as_of_date: date
    features: tuple[float, ...]
    outperform_20d: int
    target_date: date
    split: str


@dataclass(frozen=True)
class RelativeStrength20DDataset:
    rows: tuple[RelativeStrength20DDatasetRow, ...]
    requested_symbols: tuple[str, ...]
    usable_symbols: tuple[str, ...]
    excluded_symbols: tuple[str, ...]
    symbol_exclusion_reasons: dict[str, str]
    exclusion_counts: dict[str, int]

    def rows_for(self, split: str) -> tuple[RelativeStrength20DDatasetRow, ...]:
        return tuple(row for row in self.rows if row.split == split)


def workflow_split(value: date) -> str | None:
    if SPLITS[TRAIN][0] <= value <= SPLITS[TRAIN][1]:
        return TRAIN
    if SPLITS[VALIDATION][0] <= value <= SPLITS[VALIDATION][1]:
        return DEVELOPMENT_EVALUATION
    if SPLITS[WORKFLOW_FROZEN_OOS][0] <= value <= SPLITS[WORKFLOW_FROZEN_OOS][1]:
        return WORKFLOW_FROZEN_OOS
    return None


def build_feature_snapshot_lookup(
    series: HistoricalPriceSeries,
    *,
    end_date: date,
) -> dict[date, object]:
    feature_series = HistoricalPriceSeries(
        symbol=series.symbol,
        currency=series.currency,
        bars=tuple(bar for bar in series.bars if bar.trading_date <= end_date),
        fetched_at=series.fetched_at,
        is_stale=series.is_stale,
        source=series.source,
    )
    canonical = canonical_research_price_series(feature_series)
    return {
        snapshot.trading_date: snapshot
        for snapshot in build_technical_indicator_series(canonical).snapshots
    }


def relative_strength_feature_values(stock_snapshot, benchmark_snapshot) -> tuple[float, ...] | None:
    if stock_snapshot.trading_date != benchmark_snapshot.trading_date:
        return None
    if not all(
        _is_positive_finite(value)
        for value in (
            stock_snapshot.analysis_close,
            stock_snapshot.sma_20,
            stock_snapshot.sma_60,
            benchmark_snapshot.analysis_close,
            benchmark_snapshot.sma_20,
            benchmark_snapshot.sma_60,
        )
    ):
        return None
    raw_values = (
        _difference(stock_snapshot.return_5d, benchmark_snapshot.return_5d),
        _difference(stock_snapshot.return_20d, benchmark_snapshot.return_20d),
        _difference(stock_snapshot.return_60d, benchmark_snapshot.return_60d),
        (
            stock_snapshot.analysis_close / stock_snapshot.sma_20
            - benchmark_snapshot.analysis_close / benchmark_snapshot.sma_20
        ),
        (
            stock_snapshot.analysis_close / stock_snapshot.sma_60
            - benchmark_snapshot.analysis_close / benchmark_snapshot.sma_60
        ),
        _difference(stock_snapshot.rsi_14, benchmark_snapshot.rsi_14),
    )
    if not all(_is_finite_number(value) for value in raw_values):
        return None
    return tuple(float(value) for value in raw_values)


def build_relative_strength_symbol_rows(
    series: HistoricalPriceSeries,
    *,
    benchmark_prices: dict[date, float],
    benchmark_snapshots: dict[date, object],
) -> tuple[tuple[RelativeStrength20DDatasetRow, ...], Counter[str]]:
    bars = tuple(sorted(series.bars, key=lambda bar: bar.trading_date))
    if len({bar.trading_date for bar in bars}) != len(bars):
        return (), Counter({"DUPLICATE_TRADING_DATE": 1})
    stock_snapshots = build_feature_snapshot_lookup(series, end_date=SPLITS[VALIDATION][1])

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

        target = relative_outperform_20d_target(bars, index, benchmark_prices)
        if target.exclusion_reason is not None:
            exclusions[target.exclusion_reason] += 1
            continue
        stock_snapshot = stock_snapshots.get(bar.trading_date)
        if stock_snapshot is None:
            exclusions["MISSING_STOCK_FEATURE_SNAPSHOT"] += 1
            continue
        benchmark_snapshot = benchmark_snapshots.get(bar.trading_date)
        if benchmark_snapshot is None:
            exclusions["BENCHMARK_FEATURE_EXACT_DATE_ALIGNMENT_MISSING"] += 1
            continue
        features = relative_strength_feature_values(stock_snapshot, benchmark_snapshot)
        if features is None:
            exclusions["INCOMPLETE_OR_NONFINITE_RELATIVE_FEATURES"] += 1
            continue
        rows.append(
            RelativeStrength20DDatasetRow(
                symbol=series.symbol,
                as_of_date=bar.trading_date,
                features=features,
                outperform_20d=target.outperform_20d,
                target_date=target.target_date,
                split=split,
            )
        )
    return tuple(rows), exclusions


def assemble_relative_strength_dataset(
    *,
    research_store: ResearchDataStore | None = None,
) -> tuple[RelativeStrength20DDataset, dict[str, object]]:
    OOSSplitter().validate_ordering(
        tuple(value.isoformat() for value in SPLITS[TRAIN]),
        tuple(value.isoformat() for value in SPLITS[VALIDATION]),
        tuple(value.isoformat() for value in SPLITS[WORKFLOW_FROZEN_OOS]),
    )
    store = research_store or ResearchDataStore()
    runtime_identity = store.verify_runtime_identity(verify_db_sha=False)
    benchmark_series = store.load_historical_price_series(BENCHMARK_SYMBOL)
    development_benchmark_series = HistoricalPriceSeries(
        symbol=benchmark_series.symbol,
        currency=benchmark_series.currency,
        bars=tuple(
            bar
            for bar in benchmark_series.bars
            if bar.trading_date <= SPLITS[VALIDATION][1]
        ),
        fetched_at=benchmark_series.fetched_at,
        is_stale=benchmark_series.is_stale,
        source=benchmark_series.source,
    )
    benchmark_prices = {
        trading_date: price
        for trading_date, price in build_benchmark_price_lookup(development_benchmark_series).items()
        if trading_date >= SPLITS[TRAIN][0]
    }
    benchmark_snapshots = build_feature_snapshot_lookup(
        development_benchmark_series,
        end_date=SPLITS[VALIDATION][1],
    )
    universe = load_frozen_twse_research_universe(research_store=store)

    rows: list[RelativeStrength20DDatasetRow] = []
    exclusions: Counter[str] = Counter()
    usable_symbols = []
    symbol_exclusion_reasons: dict[str, str] = {}
    for symbol in universe.symbols:
        try:
            series = store.load_historical_price_series(symbol)
            symbol_rows, symbol_exclusions = build_relative_strength_symbol_rows(
                series,
                benchmark_prices=benchmark_prices,
                benchmark_snapshots=benchmark_snapshots,
            )
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

    exclusions.setdefault("BENCHMARK_EXACT_DATE_ALIGNMENT_MISSING", 0)
    exclusions.setdefault("BENCHMARK_FEATURE_EXACT_DATE_ALIGNMENT_MISSING", 0)
    ordered_rows = tuple(sorted(rows, key=lambda row: (row.symbol, row.as_of_date)))
    usable = tuple(usable_symbols)
    usable_set = set(usable)
    excluded = tuple(symbol for symbol in universe.symbols if symbol not in usable_set)
    return (
        RelativeStrength20DDataset(
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
            "benchmark": {
                "symbol": BENCHMARK_SYMBOL,
                "role": BENCHMARK_ROLE,
                "development_price_count": len(benchmark_prices),
                "development_feature_snapshot_count": len(benchmark_snapshots),
            },
        },
    )


def fit_relative_strength_logistic(dataset: RelativeStrength20DDataset) -> dict[str, object]:
    train_rows = dataset.rows_for(TRAIN)
    development_rows = dataset.rows_for(DEVELOPMENT_EVALUATION)
    if not train_rows or not development_rows:
        raise ValueError("TRAIN and DEVELOPMENT_EVALUATION rows are required.")

    x_train, y_train = _matrix(train_rows)
    x_development, y_development = _matrix(development_rows)
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
    convergence_warnings = [
        str(item.message) for item in caught if issubclass(item.category, ConvergenceWarning)
    ]

    probabilities = model.predict_proba(x_development)[:, 1]
    if not np.all(np.isfinite(probabilities)) or not np.all((0 <= probabilities) & (probabilities <= 1)):
        raise ValueError("Development probabilities must be finite and within [0, 1].")
    predictions = (probabilities >= 0.5).astype(int)
    train_rate = float(np.mean(y_train))
    development_rate = float(np.mean(y_development))
    development_metrics = _classification_metrics(y_development, probabilities, predictions)
    constant_probabilities = np.full_like(probabilities, train_rate, dtype=float)
    constant_brier = float(brier_score_loss(y_development, constant_probabilities))
    scaler = model.named_steps["standard_scaler"]
    logistic = model.named_steps["logistic_regression"]
    coefficients = [
        {"feature": feature, "coefficient": float(value)}
        for feature, value in zip(FEATURE_ORDER, logistic.coef_[0], strict=True)
    ]
    coefficients.sort(key=lambda item: (-abs(item["coefficient"]), item["feature"]))
    return {
        "train_rows": len(train_rows),
        "development_rows": len(development_rows),
        "train_symbols": len({row.symbol for row in train_rows}),
        "development_symbols": len({row.symbol for row in development_rows}),
        "train_target_rate": train_rate,
        "development_target_rate": development_rate,
        "development_probabilities": probabilities.tolist(),
        "development_metrics": development_metrics,
        "constant_baseline": {
            "probability": train_rate,
            "brier_score": constant_brier,
            "logistic_minus_constant_brier": development_metrics["brier_score"] - constant_brier,
        },
        "calibration_bands": _calibration_bands(y_development, probabilities),
        "probability_deciles": _probability_deciles(y_development, probabilities),
        "annual_metrics": _annual_metrics(development_rows, y_development, probabilities),
        "coefficients": coefficients,
        "intercept": float(logistic.intercept_[0]),
        "scaler_mean": [float(value) for value in scaler.mean_],
        "scaler_scale": [float(value) for value in scaler.scale_],
        "n_iter": int(logistic.n_iter_[0]),
        "converged": not convergence_warnings and int(logistic.n_iter_[0]) < logistic.max_iter,
        "convergence_warnings": convergence_warnings,
    }


def build_result_artifact(
    dataset: RelativeStrength20DDataset,
    source_identity: dict[str, object],
    model_result: dict[str, object],
    *,
    generated_at: datetime,
) -> dict[str, object]:
    development = _rename_rate(model_result["development_metrics"])
    calibration = [_rename_rate(row) for row in model_result["calibration_bands"]]
    deciles = [_rename_rate(row) for row in model_result["probability_deciles"]]
    annual = {year: _rename_rate(row) for year, row in model_result["annual_metrics"].items()}
    artifact = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_id": MODEL_ID,
        "generated_at": generated_at.astimezone(UTC).isoformat(),
        "research_scope": "RESEARCH_EXPERIMENTAL_ONLY",
        "hypothesis": "Past relative technical strength versus 0050 may predict future 20-stock-bar outperformance versus 0050.",
        "research_snapshot": source_identity["runtime_identity"],
        "universe": {
            "universe_id": source_identity["universe_id"],
            "universe_version": source_identity["universe_version"],
            "requested_symbols": len(dataset.requested_symbols),
            "usable_symbols": len(dataset.usable_symbols),
            "excluded_symbols": list(dataset.excluded_symbols),
            "symbol_exclusion_reasons": dataset.symbol_exclusion_reasons,
        },
        "benchmark": {
            **source_identity["benchmark"],
            "benchmark_is_candidate": False,
            "exact_date_alignment_required": True,
            "forward_fill": False,
        },
        "price_semantics": {
            "version": PRICE_SEMANTICS,
            "definition": "adjusted_close when present and finite, otherwise raw close, for stock and 0050",
        },
        "target": {
            "target_id": TARGET_ID,
            "horizon_stock_trading_bars": TARGET_HORIZON,
            "definition": "1 when stock return exceeds 0050 return over identical stock start and target dates, otherwise 0",
            "equal_return_target": 0,
        },
        "feature_set": {
            "feature_set_id": FEATURE_SET_ID,
            "ordered_features": list(FEATURE_ORDER),
            "absolute_features_included": False,
            "definitions": {
                "REL_RETURN_5D": "stock RETURN_5D minus 0050 RETURN_5D",
                "REL_RETURN_20D": "stock RETURN_20D minus 0050 RETURN_20D",
                "REL_RETURN_60D": "stock RETURN_60D minus 0050 RETURN_60D",
                "REL_TREND_20": "stock close/SMA20 minus 0050 close/SMA20",
                "REL_TREND_60": "stock close/SMA60 minus 0050 close/SMA60",
                "REL_RSI14": "stock RSI14 minus 0050 RSI14",
            },
            "alignment_rule": "Stock and 0050 feature snapshots must have the exact same as_of_date.",
            "timing_rule": "All stock and benchmark feature inputs are available on or before as_of_date.",
        },
        "temporal_workflow": {
            "splits": {
                TRAIN: {"start": SPLITS[TRAIN][0].isoformat(), "end": SPLITS[TRAIN][1].isoformat()},
                DEVELOPMENT_EVALUATION: {
                    "start": SPLITS[VALIDATION][0].isoformat(),
                    "end": SPLITS[VALIDATION][1].isoformat(),
                },
                WORKFLOW_FROZEN_OOS: {
                    "start": SPLITS[WORKFLOW_FROZEN_OOS][0].isoformat(),
                    "end": SPLITS[WORKFLOW_FROZEN_OOS][1].isoformat(),
                },
            },
            "evaluated_splits": list(EVALUATED_SPLITS),
            "workflow_frozen_oos_evaluated": False,
            "data_from_2026_used": False,
            "purge_rule": "stock as_of_date and target_date must remain in the same split; 0050 endpoints must exist exactly",
        },
        "dataset": {
            "ordering": "symbol,as_of_date",
            "total_usable_rows": len(dataset.rows),
            "train_rows": model_result["train_rows"],
            "development_rows": model_result["development_rows"],
            "train_symbols": model_result["train_symbols"],
            "development_symbols": model_result["development_symbols"],
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
            "train_target_rate": model_result["train_target_rate"],
            "development_target_rate": model_result["development_target_rate"],
            "development": development,
            "constant_baseline": model_result["constant_baseline"],
            "calibration_bands": calibration,
            "probability_deciles": deciles,
            "high_minus_low_outperform_rate": (
                deciles[-1]["actual_outperform_rate"] - deciles[0]["actual_outperform_rate"]
            ),
            "annual_development": annual,
        },
        "limitations": [
            "SURVIVORSHIP_BIAS_HANDLING=NOT_IMPLEMENTED / UNKNOWN.",
            "BENCHMARK_LIMITATION=0050 is a large-cap ETF proxy, not the full Taiwan equity market.",
            "Adjusted historical prices may reflect subsequently known corporate-action adjustments.",
            "The Frozen TWSE universe is not a historical point-in-time universe.",
            "2023-2024 is DEVELOPMENT_EVALUATION, not pristine validation.",
            "Coefficients are associations only, not causal effects.",
            "No 2025 WORKFLOW_FROZEN_OOS performance was inspected.",
        ],
    }
    artifact["artifact_checksum"] = _stable_hash(artifact)
    return artifact


def run_research_baseline(
    *,
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    dataset, source_identity = assemble_relative_strength_dataset()
    model_result = fit_relative_strength_logistic(dataset)
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


def _matrix(rows):
    materialized = tuple(rows)
    return (
        np.asarray([row.features for row in materialized], dtype=float),
        np.asarray([row.outperform_20d for row in materialized], dtype=int),
    )


def _rename_rate(row):
    renamed = dict(row)
    if "observed_up_rate" in renamed:
        renamed["observed_outperform_rate"] = renamed.pop("observed_up_rate")
    if "actual_up_rate" in renamed:
        renamed["actual_outperform_rate"] = renamed.pop("actual_up_rate")
    return renamed


def _difference(left, right):
    if not _is_finite_number(left) or not _is_finite_number(right):
        return None
    return float(left) - float(right)


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
