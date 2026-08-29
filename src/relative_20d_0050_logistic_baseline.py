from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path

import sklearn

from database_config import PROJECT_ROOT
from evaluation.oos_splitter import OOSSplitter
from frozen_twse_research_universe_service import load_frozen_twse_research_universe
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from research_data_store import ResearchDataStore
from upside_20d_logistic_baseline import EVALUATED_SPLITS
from upside_20d_logistic_baseline import FEATURE_ORDER
from upside_20d_logistic_baseline import SPLITS
from upside_20d_logistic_baseline import TARGET_HORIZON
from upside_20d_logistic_baseline import TRAIN
from upside_20d_logistic_baseline import VALIDATION
from upside_20d_logistic_baseline import WORKFLOW_FROZEN_OOS
from upside_20d_logistic_baseline import build_symbol_dataset_rows
from upside_20d_logistic_baseline import fit_logistic_baseline
from upside_20d_logistic_baseline import research_price


MODEL_ID = "RELATIVE_20D_0050_LOGISTIC_BASELINE_V0"
ARTIFACT_SCHEMA_VERSION = "relative_20d_0050_logistic_baseline_artifact_v1"
PRICE_SEMANTICS = "RELATIVE_20D_ADJUSTED_CLOSE_FIRST_V1"
TARGET_ID = "RELATIVE_OUTPERFORM_20D_0050_V0"
BENCHMARK_SYMBOL = "0050.TW"
BENCHMARK_ROLE = "TAIWAN_LARGE_CAP_ETF_MARKET_PROXY"
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "upside_20d_probability"
    / "relative_20d_0050_logistic_baseline_v0.json"
)


@dataclass(frozen=True)
class Relative20DTargetResult:
    outperform_20d: int | None
    target_date: date | None
    exclusion_reason: str | None = None


@dataclass(frozen=True)
class Relative20DDatasetRow:
    symbol: str
    as_of_date: date
    features: tuple[float, ...]
    outperform_20d: int
    target_date: date
    split: str


@dataclass(frozen=True)
class Relative20DDataset:
    rows: tuple[Relative20DDatasetRow, ...]
    requested_symbols: tuple[str, ...]
    usable_symbols: tuple[str, ...]
    excluded_symbols: tuple[str, ...]
    symbol_exclusion_reasons: dict[str, str]
    exclusion_counts: dict[str, int]

    def rows_for(self, split: str) -> tuple[Relative20DDatasetRow, ...]:
        return tuple(row for row in self.rows if row.split == split)


def build_benchmark_price_lookup(series: HistoricalPriceSeries) -> dict[date, float]:
    lookup: dict[date, float] = {}
    for bar in sorted(series.bars, key=lambda item: item.trading_date):
        if bar.trading_date in lookup:
            raise ValueError(f"Duplicate benchmark trading date: {bar.trading_date.isoformat()}.")
        price = research_price(bar)
        if _is_positive_finite(price):
            lookup[bar.trading_date] = float(price)
    return lookup


def relative_outperform_20d_target(
    bars: tuple[HistoricalPriceBar, ...],
    reference_index: int,
    benchmark_prices: dict[date, float],
) -> Relative20DTargetResult:
    target_index = reference_index + TARGET_HORIZON
    if reference_index < 0 or target_index >= len(bars):
        return Relative20DTargetResult(None, None, "INSUFFICIENT_FUTURE_20_BARS")

    reference_bar = bars[reference_index]
    target_bar = bars[target_index]
    stock_start = research_price(reference_bar)
    stock_end = research_price(target_bar)
    if not _is_positive_finite(stock_start) or not _is_positive_finite(stock_end):
        return Relative20DTargetResult(
            None,
            target_bar.trading_date,
            "MISSING_OR_INVALID_RESEARCH_PRICE",
        )

    benchmark_start = benchmark_prices.get(reference_bar.trading_date)
    benchmark_end = benchmark_prices.get(target_bar.trading_date)
    if not _is_positive_finite(benchmark_start) or not _is_positive_finite(benchmark_end):
        return Relative20DTargetResult(
            None,
            target_bar.trading_date,
            "BENCHMARK_EXACT_DATE_ALIGNMENT_MISSING",
        )

    stock_return = float(stock_end) / float(stock_start) - 1.0
    benchmark_return = float(benchmark_end) / float(benchmark_start) - 1.0
    return Relative20DTargetResult(
        int(stock_return > benchmark_return),
        target_bar.trading_date,
    )


def assemble_relative_20d_dataset(
    *,
    research_store: ResearchDataStore | None = None,
) -> tuple[Relative20DDataset, dict[str, object]]:
    OOSSplitter().validate_ordering(
        tuple(value.isoformat() for value in SPLITS[TRAIN]),
        tuple(value.isoformat() for value in SPLITS[VALIDATION]),
        tuple(value.isoformat() for value in SPLITS[WORKFLOW_FROZEN_OOS]),
    )
    store = research_store or ResearchDataStore()
    runtime_identity = store.verify_runtime_identity(verify_db_sha=False)
    benchmark_series = store.load_historical_price_series(BENCHMARK_SYMBOL)
    evaluation_benchmark_series = HistoricalPriceSeries(
        symbol=benchmark_series.symbol,
        currency=benchmark_series.currency,
        bars=tuple(
            bar
            for bar in benchmark_series.bars
            if SPLITS[TRAIN][0] <= bar.trading_date <= SPLITS[VALIDATION][1]
        ),
        fetched_at=benchmark_series.fetched_at,
        is_stale=benchmark_series.is_stale,
        source=benchmark_series.source,
    )
    benchmark_prices = build_benchmark_price_lookup(evaluation_benchmark_series)
    universe = load_frozen_twse_research_universe(research_store=store)

    def resolve_target(bars, reference_index, _target_index):
        result = relative_outperform_20d_target(bars, reference_index, benchmark_prices)
        return result.outperform_20d, result.exclusion_reason

    def build_row(symbol, as_of_date, features, target_value, target_date, split):
        return Relative20DDatasetRow(
            symbol=symbol,
            as_of_date=as_of_date,
            features=features,
            outperform_20d=target_value,
            target_date=target_date,
            split=split,
        )

    rows: list[Relative20DDatasetRow] = []
    exclusions: Counter[str] = Counter()
    usable_symbols = []
    symbol_exclusion_reasons: dict[str, str] = {}
    for symbol in universe.symbols:
        try:
            series = store.load_historical_price_series(symbol)
            symbol_rows, symbol_exclusions = build_symbol_dataset_rows(
                series,
                target_value_resolver=resolve_target,
                row_factory=build_row,
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

    ordered_rows = tuple(sorted(rows, key=lambda row: (row.symbol, row.as_of_date)))
    usable = tuple(usable_symbols)
    usable_set = set(usable)
    excluded = tuple(symbol for symbol in universe.symbols if symbol not in usable_set)
    exclusions.setdefault("BENCHMARK_EXACT_DATE_ALIGNMENT_MISSING", 0)
    benchmark_bars = tuple(
        bar
        for bar in sorted(benchmark_series.bars, key=lambda item: item.trading_date)
        if SPLITS[TRAIN][0] <= bar.trading_date <= SPLITS[WORKFLOW_FROZEN_OOS][1]
    )
    return (
        Relative20DDataset(
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
                "coverage_start": benchmark_bars[0].trading_date.isoformat(),
                "coverage_end": benchmark_bars[-1].trading_date.isoformat(),
                "bar_count": len(benchmark_bars),
                "valid_research_price_count": sum(
                    1 for bar in benchmark_bars if _is_positive_finite(research_price(bar))
                ),
                "adjusted_close_available_count": sum(
                    1 for bar in benchmark_bars if _is_positive_finite(bar.adjusted_close)
                ),
            },
        },
    )


def fit_relative_logistic_baseline(dataset: Relative20DDataset) -> dict[str, object]:
    return fit_logistic_baseline(
        dataset,
        target_getter=lambda row: row.outperform_20d,
    )


def build_result_artifact(
    dataset: Relative20DDataset,
    source_identity: dict[str, object],
    model_result: dict[str, object],
    *,
    generated_at: datetime,
) -> dict[str, object]:
    validation = dict(model_result["validation_metrics"])
    validation["observed_outperform_rate"] = validation.pop("observed_up_rate")
    calibration = [
        {
            **{key: value for key, value in row.items() if key != "actual_up_rate"},
            "actual_outperform_rate": row["actual_up_rate"],
        }
        for row in model_result["calibration_bands"]
    ]
    deciles = [
        {
            **{key: value for key, value in row.items() if key != "actual_up_rate"},
            "actual_outperform_rate": row["actual_up_rate"],
        }
        for row in model_result["probability_deciles"]
    ]
    annual = {}
    for year, row in model_result["annual_validation_metrics"].items():
        annual[year] = dict(row)
        annual[year]["observed_outperform_rate"] = annual[year].pop("observed_up_rate")

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
            "requested_candidate_symbols": len(dataset.requested_symbols),
            "usable_candidate_symbols": len(dataset.usable_symbols),
            "excluded_symbols": list(dataset.excluded_symbols),
            "symbol_exclusion_reasons": dataset.symbol_exclusion_reasons,
            "benchmark_is_candidate": False,
        },
        "benchmark": {
            **source_identity["benchmark"],
            "data_lineage": source_identity["runtime_identity"]["active_research_snapshot_id"],
            "exact_date_alignment_required": True,
            "forward_fill": False,
        },
        "price_semantics": {
            "version": PRICE_SEMANTICS,
            "definition": "adjusted_close when present and finite, otherwise raw close, for stock and benchmark",
        },
        "feature_set": {
            "feature_set_id": "RELATIVE_20D_FIXED_8_FEATURES_V0",
            "ordered_features": list(FEATURE_ORDER),
            "benchmark_relative_features": False,
            "timing_rule": "Each feature uses stock observations available on or before as_of_date.",
        },
        "target": {
            "target_id": TARGET_ID,
            "horizon_stock_trading_bars": TARGET_HORIZON,
            "definition": "1 when stock return exceeds 0050.TW return over identical stock start and target dates, otherwise 0",
            "equal_return_target": 0,
        },
        "temporal_workflow": {
            "splits": {
                name: {"start": period[0].isoformat(), "end": period[1].isoformat()}
                for name, period in SPLITS.items()
            },
            "evaluated_splits": list(EVALUATED_SPLITS),
            "workflow_frozen_oos_evaluated": False,
            "data_from_2026_used": False,
            "purge_rule": "stock as_of_date and stock target_date must be in the same split; benchmark endpoints must exist exactly",
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
            "train_outperform_rate": model_result["train_up_rate"],
            "validation_outperform_rate": model_result["validation_up_rate"],
            "validation": validation,
            "constant_baseline": model_result["constant_baseline"],
            "calibration_bands": calibration,
            "probability_deciles": deciles,
            "high_minus_low_decile_outperform_rate": (
                deciles[-1]["actual_outperform_rate"] - deciles[0]["actual_outperform_rate"]
            ),
            "annual_validation": annual,
        },
        "limitations": [
            "SURVIVORSHIP_BIAS_HANDLING=NOT_IMPLEMENTED / UNKNOWN.",
            "BENCHMARK_LIMITATION=0050 is a large-cap ETF proxy, not the full Taiwan equity market.",
            "Adjusted historical prices may reflect subsequently known corporate-action adjustments.",
            "The evaluation population is the Frozen TWSE research universe, not a historical point-in-time universe.",
            "Model coefficients are associations only, not causal effects.",
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
    dataset, source_identity = assemble_relative_20d_dataset()
    model_result = fit_relative_logistic_baseline(dataset)
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


def _is_positive_finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) > 0.0
    )


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
