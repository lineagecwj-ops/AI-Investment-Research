from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path

from database import DEFAULT_DB_PATH
from database import historical_price_bar_from_row
from database import parse_cache_datetime
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonConfig
from historical_condition_outcome_service import compare_historical_condition_outcomes
from historical_condition_outcome_service import prepare_diagnostic_research_series
from models import HistoricalPriceSeries
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsConfig
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsService
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from technical_indicator_service import build_technical_indicator_series
from volume_threshold_robustness_service import DEFAULT_OBSERVATION_END
from volume_threshold_robustness_service import DEFAULT_OBSERVATION_START
from volume_threshold_robustness_service import DEFAULT_OUTCOME_HORIZON_BARS
from volume_threshold_robustness_service import DEFAULT_OVERLAP_REDUCTION_SPACING_BARS
from volume_threshold_robustness_service import DEFAULT_ROBUSTNESS_THRESHOLDS
from volume_threshold_robustness_service import DEFAULT_WARMUP_TRADING_BARS
from volume_threshold_robustness_service import ThresholdDailyRobustnessSummary
from volume_threshold_robustness_service import ThresholdSymbolRobustnessSummary
from volume_threshold_robustness_service import ThresholdYearRobustnessSummary
from volume_threshold_robustness_service import VolumeThresholdRobustnessConfig
from volume_threshold_robustness_service import VolumeThresholdRobustnessResult
from volume_threshold_robustness_service import analyze_volume_threshold_robustness


ORIGINAL_FIVE_SYMBOLS = ("2330.TW", "0050.TW", "2337.TW", "2404.TW", "2454.TW")
EXCLUDED_DATA_COVERAGE = "EXCLUDED_DATA_COVERAGE"
EXCLUDED_NOT_TAIWAN_UNIVERSE = "EXCLUDED_NOT_TAIWAN_UNIVERSE"
OLD_FIVE_DAILY_BENCHMARK = {
    1.00: (114, 92.11),
    1.10: (96, 91.67),
    1.20: (73, 90.41),
}
OLD_FIVE_REDUCED_BENCHMARK = {
    1.00: (36, 88.89),
    1.10: (35, 88.57),
    1.20: (32, 84.38),
}


class ExpandedVolumeThresholdValidationError(Exception):
    """Raised when expanded symbol validation cannot run safely."""


@dataclass(frozen=True)
class ExpandedSymbolUniverseConfig:

    symbols: tuple[str, ...]

    selection_rule: str

    minimum_coverage_requirement: str

    research_start: date = DEFAULT_OBSERVATION_START

    research_end: date = DEFAULT_OBSERVATION_END

    warmup_trading_bars: int = DEFAULT_WARMUP_TRADING_BARS

    outcome_horizon_bars: int = DEFAULT_OUTCOME_HORIZON_BARS

    source_version: str = "data/stocks.db historical_prices via SQLite mode=ro"

    generated_at: datetime | None = None


@dataclass(frozen=True)
class SymbolCoverageAudit:

    symbol: str

    earliest_raw_price_date: date | None

    latest_raw_price_date: date | None

    total_rows: int

    observation_window_rows: int

    warmup_available_bars: int

    post_window_available_bars: int

    duplicate_date_count: int

    invalid_ohlcv_rows: int

    included: bool

    exclusion_reason: str | None

    exclusion_detail: str | None


@dataclass(frozen=True)
class ExpandedThresholdSymbolSummary:

    symbol: str

    threshold: float

    observation_count: int

    hit_count: int

    miss_count: int

    resolved_count: int

    historical_hit_rate: float | None

    delta_hit_rate_vs_1_20_pp: float | None


@dataclass(frozen=True)
class ExpandedThresholdYearSummary:

    year: int

    threshold: float

    observation_count: int

    hit_count: int

    miss_count: int

    resolved_count: int

    historical_hit_rate: float | None

    delta_hit_rate_vs_1_20_pp: float | None


@dataclass(frozen=True)
class ExpandedThresholdOverlapSummary:

    symbol: str | None

    threshold: float

    daily_observation_count: int

    overlap_reduced_observation_count: int

    hit_count: int

    miss_count: int

    resolved_count: int

    historical_hit_rate: float | None

    delta_hit_rate_vs_1_20_pp: float | None


@dataclass(frozen=True)
class SymbolBreadthSummary:

    candidate_threshold: float

    baseline_threshold: float

    symbols_with_resolved_baseline: int

    candidate_positive_delta_symbols: int

    candidate_negative_delta_symbols: int

    candidate_same_delta_symbols: int

    candidate_unavailable_symbols: int


@dataclass(frozen=True)
class ThresholdConcentrationMetric:

    threshold: float

    latest_year: int | None

    latest_year_share: float | None

    top_2_symbol_share: float | None

    top_5_symbol_share: float | None


@dataclass(frozen=True)
class OldFiveBenchmarkComparison:

    threshold: float

    expanded_observation_count: int

    old_five_observation_count: int

    observation_count_difference: int

    expanded_hhr_percent: float | None

    old_five_hhr_percent: float

    hhr_difference_pp: float | None


@dataclass(frozen=True)
class CandidateRobustnessClassification:

    threshold: float

    aggregate: str

    symbol_breadth: str

    year_coverage: str

    overlap_reduced: str

    concentration: str


@dataclass(frozen=True)
class ExpandedVolumeThresholdValidationResult:

    universe_config: ExpandedSymbolUniverseConfig

    coverage_audits: tuple[SymbolCoverageAudit, ...]

    included_symbols: tuple[str, ...]

    excluded_symbols: tuple[SymbolCoverageAudit, ...]

    robustness_result: VolumeThresholdRobustnessResult

    aggregate_summaries: tuple[ThresholdDailyRobustnessSummary, ...]

    per_symbol_summaries: tuple[ExpandedThresholdSymbolSummary, ...]

    per_year_summaries: tuple[ExpandedThresholdYearSummary, ...]

    symbol_breadth_summaries: tuple[SymbolBreadthSummary, ...]

    overlap_summaries: tuple[ExpandedThresholdOverlapSummary, ...]

    per_symbol_overlap_summaries: tuple[ExpandedThresholdOverlapSummary, ...]

    concentration_metrics: tuple[ThresholdConcentrationMetric, ...]

    old_five_daily_comparison: tuple[OldFiveBenchmarkComparison, ...]

    old_five_reduced_comparison: tuple[OldFiveBenchmarkComparison, ...]

    candidate_classifications: tuple[CandidateRobustnessClassification, ...]

    effective_years_by_threshold: dict[float, int]

    generated_at: datetime


def run_expanded_volume_threshold_validation(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    generated_at: datetime | None = None,
) -> ExpandedVolumeThresholdValidationResult:
    generated_at = generated_at or datetime.now(UTC)
    audits = audit_expanded_symbol_universe(db_path=db_path)
    included = tuple(audit.symbol for audit in audits if audit.included)
    if not included:
        raise ExpandedVolumeThresholdValidationError("No local Taiwan symbols satisfy the frozen coverage rule.")

    universe_config = ExpandedSymbolUniverseConfig(
        symbols=included,
        selection_rule=(
            "Deterministic local Taiwan universe: symbols already present in data/stocks.db "
            "historical_prices whose symbol ends with .TW or .TWO; no threshold outcome, "
            "hit rate, scanner result, or profitability data is used."
        ),
        minimum_coverage_requirement=(
            "At least 60 pre-window trading bars before 2018-01-01, at least one raw row "
            "inside 2018-01-01 through 2025-12-31, at least 20 post-window trading bars "
            "after 2025-12-31, no duplicate trading dates, and usable OHLCV rows."
        ),
        generated_at=generated_at,
    )
    comparison_price_series, technical_series = _prepare_research_inputs(included, db_path=db_path)
    diagnostics = HistoricalConditionDiagnosticsService(
        price_loader=lambda *args, **kwargs: _unexpected_price_load(),
        technical_builder=lambda *args, **kwargs: _unexpected_technical_build(),
    ).run_diagnostics(
        included,
        HistoricalConditionDiagnosticsConfig(
            start_date=universe_config.research_start,
            end_date=universe_config.research_end,
            signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
            force_refresh=False,
        ),
        technical_series_by_symbol=technical_series,
    )
    comparison = compare_historical_condition_outcomes(
        diagnostics,
        price_series_by_symbol=comparison_price_series,
        config=HistoricalConditionOutcomeComparisonConfig(
            outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
            warmup_trading_bars=universe_config.warmup_trading_bars,
            observation_unit="DAILY",
            overlap_possible=True,
        ),
        generated_at=generated_at,
    )
    robustness = analyze_volume_threshold_robustness(
        comparison,
        config=VolumeThresholdRobustnessConfig(
            symbols=included,
            start_date=universe_config.research_start,
            end_date=universe_config.research_end,
            warmup_trading_bars=universe_config.warmup_trading_bars,
            outcome_horizon_bars=universe_config.outcome_horizon_bars,
            overlap_reduction_spacing_bars=DEFAULT_OVERLAP_REDUCTION_SPACING_BARS,
        ),
        price_series_by_symbol=comparison_price_series,
        generated_at=generated_at,
    )

    per_symbol = _expanded_symbol_summaries(robustness.per_symbol_summaries)
    per_year = _expanded_year_summaries(robustness.per_year_summaries)
    overlap = _aggregate_overlap_summaries(robustness)
    per_symbol_overlap = _per_symbol_overlap_summaries(robustness)
    breadth = _symbol_breadth_summaries(robustness)
    concentration = _concentration_metrics(robustness)
    effective_years = _effective_years_by_threshold(robustness.per_year_summaries)

    return ExpandedVolumeThresholdValidationResult(
        universe_config=universe_config,
        coverage_audits=audits,
        included_symbols=included,
        excluded_symbols=tuple(audit for audit in audits if not audit.included),
        robustness_result=robustness,
        aggregate_summaries=robustness.daily_summaries,
        per_symbol_summaries=per_symbol,
        per_year_summaries=per_year,
        symbol_breadth_summaries=breadth,
        overlap_summaries=overlap,
        per_symbol_overlap_summaries=per_symbol_overlap,
        concentration_metrics=concentration,
        old_five_daily_comparison=_old_five_daily_comparison(robustness.daily_summaries),
        old_five_reduced_comparison=_old_five_reduced_comparison(overlap),
        candidate_classifications=_candidate_classifications(
            robustness,
            breadth,
            overlap,
            concentration,
            effective_years,
        ),
        effective_years_by_threshold=effective_years,
        generated_at=generated_at,
    )


def audit_expanded_symbol_universe(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    start_date: date = DEFAULT_OBSERVATION_START,
    end_date: date = DEFAULT_OBSERVATION_END,
    warmup_trading_bars: int = DEFAULT_WARMUP_TRADING_BARS,
    outcome_horizon_bars: int = DEFAULT_OUTCOME_HORIZON_BARS,
) -> tuple[SymbolCoverageAudit, ...]:
    rows = _coverage_rows(db_path, start_date=start_date, end_date=end_date)
    audits = []
    for row in rows:
        symbol = row["symbol"]
        exclusion_reason = None
        exclusion_detail = None
        if not _is_taiwan_symbol(symbol):
            exclusion_reason = EXCLUDED_NOT_TAIWAN_UNIVERSE
            exclusion_detail = "Symbol does not end with .TW or .TWO."
        else:
            coverage_issues = []
            if row["pre_rows"] < warmup_trading_bars:
                coverage_issues.append(f"warmup bars {row['pre_rows']} < {warmup_trading_bars}")
            if row["window_rows"] <= 0:
                coverage_issues.append("no rows in observation window")
            if row["post_rows"] < outcome_horizon_bars:
                coverage_issues.append(f"post-window bars {row['post_rows']} < {outcome_horizon_bars}")
            if row["duplicate_dates"] > 0:
                coverage_issues.append(f"duplicate dates {row['duplicate_dates']}")
            if row["invalid_ohlcv_rows"] > 0:
                coverage_issues.append(f"invalid OHLCV rows {row['invalid_ohlcv_rows']}")
            if coverage_issues:
                exclusion_reason = EXCLUDED_DATA_COVERAGE
                exclusion_detail = "; ".join(coverage_issues)
        audits.append(
            SymbolCoverageAudit(
                symbol=symbol,
                earliest_raw_price_date=row["earliest"],
                latest_raw_price_date=row["latest"],
                total_rows=row["total_rows"],
                observation_window_rows=row["window_rows"],
                warmup_available_bars=row["pre_rows"],
                post_window_available_bars=row["post_rows"],
                duplicate_date_count=row["duplicate_dates"],
                invalid_ohlcv_rows=row["invalid_ohlcv_rows"],
                included=exclusion_reason is None,
                exclusion_reason=exclusion_reason,
                exclusion_detail=exclusion_detail,
            )
        )
    return tuple(audits)


def load_historical_price_series_read_only(
    symbol: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> HistoricalPriceSeries:
    connection = _connect_read_only(db_path)
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT symbol, trading_date, open, high, low, close, adjusted_close,
                   volume, dividends, stock_splits, currency, fetched_at
            FROM historical_prices
            WHERE symbol = ?
            ORDER BY trading_date ASC
            """,
            (symbol,),
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        raise ExpandedVolumeThresholdValidationError(f"No historical prices found for {symbol}.")
    fetched_at_values = tuple(parse_cache_datetime(row["fetched_at"]) for row in rows if row["fetched_at"])
    fetched_at = min(fetched_at_values) if fetched_at_values else datetime.now(UTC)
    currency = next((row["currency"] for row in rows if row["currency"]), None)
    return HistoricalPriceSeries(
        symbol=symbol,
        currency=currency,
        bars=tuple(historical_price_bar_from_row(row) for row in rows),
        fetched_at=fetched_at,
        is_stale=False,
    )


def _prepare_research_inputs(
    symbols: tuple[str, ...],
    *,
    db_path: Path | str,
) -> tuple[dict[str, HistoricalPriceSeries], dict[str, object]]:
    price_series_by_symbol = {}
    technical_series_by_symbol = {}
    for symbol in symbols:
        raw = load_historical_price_series_read_only(symbol, db_path=db_path)
        prepared = prepare_diagnostic_research_series(
            raw,
            observation_start=DEFAULT_OBSERVATION_START,
            observation_end=DEFAULT_OBSERVATION_END,
            warmup_trading_bars=DEFAULT_WARMUP_TRADING_BARS,
            outcome_horizon_bars=DEFAULT_OUTCOME_HORIZON_BARS,
        )
        price_series_by_symbol[symbol] = prepared
        technical_series_by_symbol[symbol] = build_technical_indicator_series(prepared)
    return price_series_by_symbol, technical_series_by_symbol


def _coverage_rows(db_path: Path | str, *, start_date: date, end_date: date) -> tuple[sqlite3.Row, ...]:
    connection = _connect_read_only(db_path)
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                symbol,
                MIN(trading_date) AS earliest,
                MAX(trading_date) AS latest,
                COUNT(*) AS total_rows,
                COUNT(DISTINCT trading_date) AS distinct_dates,
                SUM(CASE WHEN trading_date < ? THEN 1 ELSE 0 END) AS pre_rows,
                SUM(CASE WHEN trading_date BETWEEN ? AND ? THEN 1 ELSE 0 END) AS window_rows,
                SUM(CASE WHEN trading_date > ? THEN 1 ELSE 0 END) AS post_rows,
                SUM(
                    CASE
                        WHEN high IS NULL OR low IS NULL OR close IS NULL
                          OR high <= 0 OR low <= 0 OR close <= 0
                          OR high < low OR high < close OR low > close
                          OR (open IS NOT NULL AND open <= 0)
                          OR (adjusted_close IS NOT NULL AND adjusted_close <= 0)
                          OR (volume IS NOT NULL AND volume < 0)
                        THEN 1 ELSE 0
                    END
                ) AS invalid_ohlcv_rows
            FROM historical_prices
            GROUP BY symbol
            ORDER BY symbol ASC
            """,
            (
                start_date.isoformat(),
                start_date.isoformat(),
                end_date.isoformat(),
                end_date.isoformat(),
            ),
        ).fetchall()
    finally:
        connection.close()
    hydrated = []
    for row in rows:
        values = dict(row)
        values["earliest"] = date.fromisoformat(values["earliest"]) if values["earliest"] else None
        values["latest"] = date.fromisoformat(values["latest"]) if values["latest"] else None
        values["duplicate_dates"] = values["total_rows"] - values["distinct_dates"]
        hydrated.append(values)
    return tuple(hydrated)


def _connect_read_only(db_path: Path | str) -> sqlite3.Connection:
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _is_taiwan_symbol(symbol: str) -> bool:
    return symbol.endswith(".TW") or symbol.endswith(".TWO")


def _expanded_symbol_summaries(
    rows: tuple[ThresholdSymbolRobustnessSummary, ...],
) -> tuple[ExpandedThresholdSymbolSummary, ...]:
    return tuple(
        ExpandedThresholdSymbolSummary(
            symbol=row.symbol,
            threshold=row.threshold,
            observation_count=row.observation_count,
            hit_count=row.hit_count,
            miss_count=row.miss_count,
            resolved_count=row.resolved_count,
            historical_hit_rate=row.historical_hit_rate,
            delta_hit_rate_vs_1_20_pp=row.delta_hit_rate_vs_1_20_pp,
        )
        for row in rows
    )


def _expanded_year_summaries(
    rows: tuple[ThresholdYearRobustnessSummary, ...],
) -> tuple[ExpandedThresholdYearSummary, ...]:
    return tuple(
        ExpandedThresholdYearSummary(
            year=row.year,
            threshold=row.threshold,
            observation_count=row.observation_count,
            hit_count=row.hit_count,
            miss_count=row.miss_count,
            resolved_count=row.resolved_count,
            historical_hit_rate=row.historical_hit_rate,
            delta_hit_rate_vs_1_20_pp=row.delta_hit_rate_vs_1_20_pp,
        )
        for row in rows
    )


def _symbol_breadth_summaries(
    robustness: VolumeThresholdRobustnessResult,
) -> tuple[SymbolBreadthSummary, ...]:
    rows = {(row.symbol, row.threshold): row for row in robustness.per_symbol_summaries}
    summaries = []
    for threshold in (1.00, 1.10):
        positive = negative = same = unavailable = baseline_resolved = 0
        for symbol in robustness.symbols:
            baseline = rows[(symbol, robustness.baseline_threshold)]
            candidate = rows[(symbol, threshold)]
            if baseline.resolved_count > 0:
                baseline_resolved += 1
            if baseline.historical_hit_rate is None or candidate.historical_hit_rate is None:
                unavailable += 1
            elif candidate.historical_hit_rate > baseline.historical_hit_rate:
                positive += 1
            elif candidate.historical_hit_rate < baseline.historical_hit_rate:
                negative += 1
            else:
                same += 1
        summaries.append(
            SymbolBreadthSummary(
                candidate_threshold=threshold,
                baseline_threshold=robustness.baseline_threshold,
                symbols_with_resolved_baseline=baseline_resolved,
                candidate_positive_delta_symbols=positive,
                candidate_negative_delta_symbols=negative,
                candidate_same_delta_symbols=same,
                candidate_unavailable_symbols=unavailable,
            )
        )
    return tuple(summaries)


def _aggregate_overlap_summaries(
    robustness: VolumeThresholdRobustnessResult,
) -> tuple[ExpandedThresholdOverlapSummary, ...]:
    return tuple(
        ExpandedThresholdOverlapSummary(
            symbol=None,
            threshold=row.threshold,
            daily_observation_count=row.daily_observation_count,
            overlap_reduced_observation_count=row.overlap_reduced_observation_count,
            hit_count=row.overlap_reduced_hit_count,
            miss_count=row.overlap_reduced_miss_count,
            resolved_count=row.overlap_reduced_resolved_count,
            historical_hit_rate=row.overlap_reduced_hit_rate,
            delta_hit_rate_vs_1_20_pp=row.overlap_reduced_hit_rate_delta_vs_1_20_pp,
        )
        for row in robustness.overlap_reduced_summaries
    )


def _per_symbol_overlap_summaries(
    robustness: VolumeThresholdRobustnessResult,
) -> tuple[ExpandedThresholdOverlapSummary, ...]:
    baseline_by_symbol = {}
    selected_by_threshold = {
        row.threshold: row.selected_observations
        for row in robustness.overlap_reduced_summaries
    }
    summaries = []
    for symbol in robustness.symbols:
        baseline_selected = tuple(
            item
            for item in selected_by_threshold[robustness.baseline_threshold]
            if item.symbol == symbol
        )
        baseline_rate = _rate_for_selected(baseline_selected)
        baseline_by_symbol[symbol] = baseline_rate
        for threshold in robustness.candidate_thresholds:
            selected = tuple(
                item
                for item in selected_by_threshold[threshold]
                if item.symbol == symbol
            )
            hit = sum(observation.outcome_status.name == "HIT" for observation in selected)
            miss = sum(observation.outcome_status.name == "MISS" for observation in selected)
            resolved = hit + miss
            rate = None if resolved == 0 else hit / resolved
            summaries.append(
                ExpandedThresholdOverlapSummary(
                    symbol=symbol,
                    threshold=threshold,
                    daily_observation_count=_daily_count(robustness, symbol, threshold),
                    overlap_reduced_observation_count=len(selected),
                    hit_count=hit,
                    miss_count=miss,
                    resolved_count=resolved,
                    historical_hit_rate=rate,
                    delta_hit_rate_vs_1_20_pp=_delta_pp(baseline_by_symbol[symbol], rate),
                )
            )
    return tuple(summaries)


def _daily_count(robustness: VolumeThresholdRobustnessResult, symbol: str, threshold: float) -> int:
    row = next(item for item in robustness.per_symbol_summaries if item.symbol == symbol and item.threshold == threshold)
    return row.observation_count


def _rate_for_selected(observations) -> float | None:
    hit = sum(observation.outcome_status.name == "HIT" for observation in observations)
    miss = sum(observation.outcome_status.name == "MISS" for observation in observations)
    resolved = hit + miss
    return None if resolved == 0 else hit / resolved


def _concentration_metrics(
    robustness: VolumeThresholdRobustnessResult,
) -> tuple[ThresholdConcentrationMetric, ...]:
    rows = []
    for threshold in robustness.candidate_thresholds:
        symbol_rows = [row for row in robustness.per_symbol_summaries if row.threshold == threshold]
        total = sum(row.observation_count for row in symbol_rows)
        top_counts = sorted((row.observation_count for row in symbol_rows), reverse=True)
        years = [row for row in robustness.per_year_summaries if row.threshold == threshold and row.observation_count > 0]
        latest_year = max((row.year for row in years), default=None)
        latest_year_count = next((row.observation_count for row in years if row.year == latest_year), 0)
        rows.append(
            ThresholdConcentrationMetric(
                threshold=threshold,
                latest_year=latest_year,
                latest_year_share=None if total == 0 else latest_year_count / total,
                top_2_symbol_share=None if total == 0 else sum(top_counts[:2]) / total,
                top_5_symbol_share=None if total == 0 else sum(top_counts[:5]) / total,
            )
        )
    return tuple(rows)


def _effective_years_by_threshold(
    rows: tuple[ThresholdYearRobustnessSummary, ...],
) -> dict[float, int]:
    return {
        threshold: sum(
            row.resolved_count > 0
            for row in rows
            if row.threshold == threshold
        )
        for threshold in DEFAULT_ROBUSTNESS_THRESHOLDS
    }


def _old_five_daily_comparison(
    rows: tuple[ThresholdDailyRobustnessSummary, ...],
) -> tuple[OldFiveBenchmarkComparison, ...]:
    return tuple(
        _old_five_comparison(
            row.threshold,
            row.observation_count,
            row.historical_hit_rate,
            OLD_FIVE_DAILY_BENCHMARK,
        )
        for row in rows
    )


def _old_five_reduced_comparison(
    rows: tuple[ExpandedThresholdOverlapSummary, ...],
) -> tuple[OldFiveBenchmarkComparison, ...]:
    return tuple(
        _old_five_comparison(
            row.threshold,
            row.overlap_reduced_observation_count,
            row.historical_hit_rate,
            OLD_FIVE_REDUCED_BENCHMARK,
        )
        for row in rows
    )


def _old_five_comparison(
    threshold: float,
    expanded_count: int,
    expanded_rate: float | None,
    benchmark: dict[float, tuple[int, float]],
) -> OldFiveBenchmarkComparison:
    old_count, old_rate_percent = benchmark[threshold]
    expanded_percent = None if expanded_rate is None else expanded_rate * 100
    return OldFiveBenchmarkComparison(
        threshold=threshold,
        expanded_observation_count=expanded_count,
        old_five_observation_count=old_count,
        observation_count_difference=expanded_count - old_count,
        expanded_hhr_percent=expanded_percent,
        old_five_hhr_percent=old_rate_percent,
        hhr_difference_pp=None if expanded_percent is None else expanded_percent - old_rate_percent,
    )


def _candidate_classifications(
    robustness: VolumeThresholdRobustnessResult,
    breadth: tuple[SymbolBreadthSummary, ...],
    overlap: tuple[ExpandedThresholdOverlapSummary, ...],
    concentration: tuple[ThresholdConcentrationMetric, ...],
    effective_years: dict[float, int],
) -> tuple[CandidateRobustnessClassification, ...]:
    aggregate = {row.threshold: row for row in robustness.daily_summaries}
    overlap_rows = {row.threshold: row for row in overlap}
    concentration_rows = {row.threshold: row for row in concentration}
    breadth_rows = {row.candidate_threshold: row for row in breadth}
    rows = []
    for threshold in (1.00, 1.10):
        rows.append(
            CandidateRobustnessClassification(
                threshold=threshold,
                aggregate=_classify_delta(aggregate[threshold].delta_hit_rate_vs_1_20_pp),
                symbol_breadth=_classify_breadth(breadth_rows[threshold]),
                year_coverage=_classify_year_coverage(
                    effective_years[threshold],
                    effective_years[1.20],
                ),
                overlap_reduced=_classify_delta(overlap_rows[threshold].delta_hit_rate_vs_1_20_pp),
                concentration=_classify_concentration(concentration_rows[threshold]),
            )
        )
    return tuple(rows)


def _classify_delta(delta_pp: float | None) -> str:
    if delta_pp is None:
        return "UNAVAILABLE"
    if delta_pp >= 0:
        return "SUPPORTED"
    return "WEAK"


def _classify_breadth(row: SymbolBreadthSummary) -> str:
    if row.candidate_unavailable_symbols == row.symbols_with_resolved_baseline:
        return "UNAVAILABLE"
    if row.candidate_positive_delta_symbols > row.candidate_negative_delta_symbols:
        return "SUPPORTED"
    if row.candidate_positive_delta_symbols == row.candidate_negative_delta_symbols:
        return "MIXED"
    return "WEAK"


def _classify_year_coverage(candidate_years: int, baseline_years: int) -> str:
    if candidate_years == 0:
        return "UNAVAILABLE"
    if candidate_years > baseline_years:
        return "SUPPORTED"
    if candidate_years == baseline_years:
        return "MIXED"
    return "WEAK"


def _classify_concentration(row: ThresholdConcentrationMetric) -> str:
    if row.top_2_symbol_share is None or row.latest_year_share is None:
        return "UNAVAILABLE"
    if row.top_2_symbol_share <= 0.60 and row.latest_year_share <= 0.50:
        return "SUPPORTED"
    if row.top_2_symbol_share <= 0.75:
        return "MIXED"
    return "WEAK"


def _delta_pp(baseline_rate: float | None, rate: float | None) -> float | None:
    if baseline_rate is None or rate is None:
        return None
    return (rate - baseline_rate) * 100


def _unexpected_price_load():
    raise ExpandedVolumeThresholdValidationError("Expanded validation must use preloaded read-only price series.")


def _unexpected_technical_build():
    raise ExpandedVolumeThresholdValidationError("Expanded validation must use one prebuilt technical series per symbol.")
