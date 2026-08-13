from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path

from database import DEFAULT_DB_PATH
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonConfig
from historical_condition_outcome_service import compare_historical_condition_outcomes
from historical_condition_outcome_service import prepare_diagnostic_research_series
from models import HistoricalPriceSeries
from research_data_store import ResearchDataStore
from research_data_store import ResearchDataStoreError
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
LISTING_DATE_SOURCE_OFFICIAL_SNAPSHOT = "OFFICIAL_SNAPSHOT"
LISTING_DATE_SOURCE_FALLBACK = "UNAVAILABLE_CURRENT_RUN_DB_FIRST_DATE_FALLBACK"
READINESS_FULL_WINDOW_ELIGIBLE = "FULL_WINDOW_ELIGIBLE"
READINESS_PARTIAL_WINDOW_VALID = "PARTIAL_WINDOW_VALID"
READINESS_DATA_QUALITY_BLOCKED = "DATA_QUALITY_BLOCKED"
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
class TWSEListingDateSnapshot:

    source_authority: str

    source_url: str

    source_report_date: date

    source_report_date_raw: str

    retrieved_at: datetime

    source_checksum: str

    snapshot_checksum: str

    records: tuple[dict[str, str], ...]

    listing_dates_by_symbol: dict[str, date]


@dataclass(frozen=True)
class ExpandedSymbolUniverseConfig:

    symbols: tuple[str, ...]

    frozen_total_count: int

    twse_count: int

    tpex_count: int

    unknown_exchange_count: int

    full_window_eligible_count: int | None

    partial_window_valid_count: int | None

    data_quality_blocked_count: int | None

    listing_date_source: str

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

    exchange: str

    official_listing_date: date | None

    earliest_raw_price_date: date | None

    latest_raw_price_date: date | None

    total_rows: int

    observation_window_rows: int

    warmup_available_bars: int

    post_window_available_bars: int

    duplicate_date_count: int

    invalid_ohlcv_rows: int

    included: bool

    readiness_status: str | None

    exclusion_reason: str | None

    exclusion_detail: str | None


@dataclass(frozen=True)
class ExpandedThresholdSymbolSummary:

    symbol: str

    threshold: float

    eligible_observation_date_count: int

    observation_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    historical_hit_rate: float | None

    delta_hit_rate_vs_1_20_pp: float | None

    observation_count_delta_vs_1_20: int

    observation_count_change_rate_vs_1_20: float | None


@dataclass(frozen=True)
class ExpandedThresholdYearSummary:

    year: int

    threshold: float

    eligible_symbol_count: int

    observation_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    historical_hit_rate: float | None

    delta_hit_rate_vs_1_20_pp: float | None

    observation_count_delta_vs_1_20: int


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

    candidate_added_sample_symbols: tuple[str, ...]

    baseline_resolved_sample_sizes: tuple[int, ...]

    candidate_resolved_sample_sizes: tuple[int, ...]


@dataclass(frozen=True)
class ThresholdConcentrationMetric:

    threshold: float

    observation_count: int

    year_2025_share: float | None

    latest_year: int | None

    latest_year_share: float | None

    largest_year: int | None

    largest_year_share: float | None

    top_1_symbol_share: float | None

    top_2_symbol_share: float | None

    top_5_symbol_share: float | None

    top_10_symbol_share: float | None


@dataclass(frozen=True)
class UniverseSubsetThresholdSummary:

    subset_name: str

    threshold: float

    symbol_count: int

    observation_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    historical_hit_rate: float | None


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

    year_consistency: str

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

    full_window_summaries: tuple[UniverseSubsetThresholdSummary, ...]

    partial_window_summaries: tuple[UniverseSubsetThresholdSummary, ...]

    year_consistency_by_threshold: dict[float, dict[str, int]]

    effective_years_by_threshold: dict[float, int]

    generated_at: datetime


def run_expanded_volume_threshold_validation(
    *,
    db_path: Path | str | None = None,
    official_listing_dates_by_symbol: dict[str, date] | None = None,
    generated_at: datetime | None = None,
) -> ExpandedVolumeThresholdValidationResult:
    generated_at = generated_at or datetime.now(UTC)
    official_listing_dates_by_symbol = official_listing_dates_by_symbol or {}
    audits = audit_expanded_symbol_universe(
        db_path=db_path,
        official_listing_dates_by_symbol=official_listing_dates_by_symbol,
    )
    included = tuple(audit.symbol for audit in audits if audit.included)
    if len(included) != 218:
        raise ExpandedVolumeThresholdValidationError(
            f"Expanded TWSE validation requires exactly 218 materialized TWSE common stocks; got {len(included)}."
        )

    universe_config = ExpandedSymbolUniverseConfig(
        symbols=included,
        frozen_total_count=224,
        twse_count=218,
        tpex_count=6,
        unknown_exchange_count=0,
        full_window_eligible_count=None,
        partial_window_valid_count=None,
        data_quality_blocked_count=None,
        listing_date_source=(
            LISTING_DATE_SOURCE_OFFICIAL_SNAPSHOT
            if official_listing_dates_by_symbol
            else LISTING_DATE_SOURCE_FALLBACK
        ),
        selection_rule=(
            "Materialized frozen TWSE common-stock universe in data/stocks.db: four-digit .TW "
            "symbols excluding ETF 0050.TW and non-Taiwan symbols; no threshold outcome, hit "
            "rate, scanner result, or profitability data is used."
        ),
        minimum_coverage_requirement=(
            "All 218 materialized TWSE symbols are retained. Observation eligibility is applied "
            "per symbol and per date after official listing date, 60 trading-bar warm-up, "
            "technical indicator evaluability, and 20-bar outcome support."
        ),
        generated_at=generated_at,
    )
    comparison_price_series, technical_series = _prepare_research_inputs(
        included,
        db_path=db_path,
        official_listing_dates_by_symbol=official_listing_dates_by_symbol,
    )
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
    per_year = _expanded_year_summaries_with_eligible_symbols(
        robustness.per_year_summaries,
        _eligible_symbol_count_by_year(included, comparison.outcome_observations),
    )
    overlap = _aggregate_overlap_summaries(robustness)
    per_symbol_overlap = _per_symbol_overlap_summaries(robustness)
    breadth = _symbol_breadth_summaries(robustness)
    concentration = _concentration_metrics(robustness)
    effective_years = _effective_years_by_threshold(robustness.per_year_summaries)
    readiness_by_symbol = _readiness_classification_by_symbol(
        included,
        comparison.outcome_observations,
        official_listing_dates_by_symbol=official_listing_dates_by_symbol,
        research_start=universe_config.research_start,
    )
    readiness = _readiness_counts(readiness_by_symbol)
    year_consistency = _year_consistency_by_threshold(robustness.per_year_summaries)
    universe_config = ExpandedSymbolUniverseConfig(
        symbols=universe_config.symbols,
        frozen_total_count=universe_config.frozen_total_count,
        twse_count=universe_config.twse_count,
        tpex_count=universe_config.tpex_count,
        unknown_exchange_count=universe_config.unknown_exchange_count,
        full_window_eligible_count=readiness[READINESS_FULL_WINDOW_ELIGIBLE],
        partial_window_valid_count=readiness[READINESS_PARTIAL_WINDOW_VALID],
        data_quality_blocked_count=readiness[READINESS_DATA_QUALITY_BLOCKED],
        listing_date_source=universe_config.listing_date_source,
        selection_rule=universe_config.selection_rule,
        minimum_coverage_requirement=universe_config.minimum_coverage_requirement,
        research_start=universe_config.research_start,
        research_end=universe_config.research_end,
        warmup_trading_bars=universe_config.warmup_trading_bars,
        outcome_horizon_bars=universe_config.outcome_horizon_bars,
        source_version=universe_config.source_version,
        generated_at=universe_config.generated_at,
    )

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
            year_consistency,
        ),
        full_window_summaries=_subset_summaries(
            READINESS_FULL_WINDOW_ELIGIBLE,
            tuple(
                symbol
                for symbol, status in readiness_by_symbol.items()
                if status == READINESS_FULL_WINDOW_ELIGIBLE
            ),
            robustness,
        ),
        partial_window_summaries=_subset_summaries(
            READINESS_PARTIAL_WINDOW_VALID,
            tuple(
                symbol
                for symbol, status in readiness_by_symbol.items()
                if status == READINESS_PARTIAL_WINDOW_VALID
            ),
            robustness,
        ),
        year_consistency_by_threshold=year_consistency,
        effective_years_by_threshold=effective_years,
        generated_at=generated_at,
    )


def run_final_expanded_volume_threshold_validation(
    *,
    listing_date_snapshot_path: Path | str,
    db_path: Path | str | None = None,
    generated_at: datetime | None = None,
) -> ExpandedVolumeThresholdValidationResult:
    symbols = _materialized_twse_common_stock_symbols(db_path)
    snapshot = load_twse_listing_date_snapshot(
        listing_date_snapshot_path,
        required_symbols=symbols,
    )
    return run_expanded_volume_threshold_validation(
        db_path=db_path,
        official_listing_dates_by_symbol=snapshot.listing_dates_by_symbol,
        generated_at=generated_at,
    )


def is_final_listing_date_source(listing_date_source: str) -> bool:
    return listing_date_source == LISTING_DATE_SOURCE_OFFICIAL_SNAPSHOT


def load_twse_listing_date_snapshot(
    snapshot_path: Path | str,
    *,
    required_symbols: tuple[str, ...] | None = None,
) -> TWSEListingDateSnapshot:
    path = Path(snapshot_path)
    payload = json.loads(path.read_text())
    _validate_snapshot_checksum(payload)
    records = tuple(payload["records"])
    listing_dates_by_symbol: dict[str, date] = {}
    seen_codes: set[str] = set()
    duplicate_codes = []
    invalid_dates = []
    for record in records:
        code = str(record.get("stock_code", "")).strip()
        listing_date_text = str(record.get("listing_date", "")).strip()
        if code in seen_codes:
            duplicate_codes.append(code)
        seen_codes.add(code)
        if len(listing_date_text) != 10 or listing_date_text[4] != "-" or listing_date_text[7] != "-":
            invalid_dates.append((code, listing_date_text))
            continue
        try:
            listing_date = date.fromisoformat(listing_date_text)
        except ValueError:
            invalid_dates.append((code, listing_date_text))
            continue
        listing_dates_by_symbol[f"{code}.TW"] = listing_date
    if duplicate_codes:
        raise ExpandedVolumeThresholdValidationError(
            f"TWSE listing-date snapshot has duplicate stock codes: {tuple(sorted(duplicate_codes))}."
        )
    if invalid_dates:
        raise ExpandedVolumeThresholdValidationError(
            f"TWSE listing-date snapshot has invalid listing dates: {tuple(invalid_dates)}."
        )
    if required_symbols is not None:
        missing = tuple(symbol for symbol in required_symbols if symbol not in listing_dates_by_symbol)
        if missing:
            raise ExpandedVolumeThresholdValidationError(
                f"Official TWSE listing-date snapshot is missing {len(missing)} required symbols: {missing}."
            )
    return TWSEListingDateSnapshot(
        source_authority=str(payload["source_authority"]),
        source_url=str(payload["source_url"]),
        source_report_date=date.fromisoformat(str(payload["source_report_date"])),
        source_report_date_raw=str(payload["source_report_date_raw"]),
        retrieved_at=_parse_snapshot_retrieved_at(str(payload["retrieved_at"])),
        source_checksum=str(payload["source_checksum"]),
        snapshot_checksum=str(payload["snapshot_checksum"]),
        records=records,
        listing_dates_by_symbol=listing_dates_by_symbol,
    )


def _validate_snapshot_checksum(payload: dict) -> None:
    expected = str(payload.get("snapshot_checksum", ""))
    stable = {key: value for key, value in payload.items() if key not in {"retrieved_at", "snapshot_checksum"}}
    actual = hashlib.sha256(
        json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if actual != expected:
        raise ExpandedVolumeThresholdValidationError(
            f"TWSE listing-date snapshot checksum mismatch: expected {expected}, got {actual}."
        )


def _parse_snapshot_retrieved_at(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def audit_expanded_symbol_universe(
    *,
    db_path: Path | str | None = None,
    official_listing_dates_by_symbol: dict[str, date] | None = None,
    start_date: date = DEFAULT_OBSERVATION_START,
    end_date: date = DEFAULT_OBSERVATION_END,
    warmup_trading_bars: int = DEFAULT_WARMUP_TRADING_BARS,
    outcome_horizon_bars: int = DEFAULT_OUTCOME_HORIZON_BARS,
) -> tuple[SymbolCoverageAudit, ...]:
    official_listing_dates_by_symbol = official_listing_dates_by_symbol or {}
    rows = _coverage_rows(db_path, start_date=start_date, end_date=end_date)
    audits = []
    for row in rows:
        symbol = row["symbol"]
        exclusion_reason = None
        exclusion_detail = None
        if not _is_materialized_twse_common_stock(symbol):
            exclusion_reason = EXCLUDED_NOT_TAIWAN_UNIVERSE
            exclusion_detail = "Symbol is not a materialized four-digit TWSE common stock."
        else:
            coverage_issues = []
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
                exchange="TWSE" if _is_materialized_twse_common_stock(symbol) else "UNKNOWN",
                official_listing_date=official_listing_dates_by_symbol.get(symbol),
                earliest_raw_price_date=row["earliest"],
                latest_raw_price_date=row["latest"],
                total_rows=row["total_rows"],
                observation_window_rows=row["window_rows"],
                warmup_available_bars=row["pre_rows"],
                post_window_available_bars=row["post_rows"],
                duplicate_date_count=row["duplicate_dates"],
                invalid_ohlcv_rows=row["invalid_ohlcv_rows"],
                included=exclusion_reason is None,
                readiness_status=None,
                exclusion_reason=exclusion_reason,
                exclusion_detail=exclusion_detail,
            )
        )
    return tuple(audits)


def load_historical_price_series_read_only(
    symbol: str,
    *,
    db_path: Path | str | None = None,
    research_store: ResearchDataStore | None = None,
) -> HistoricalPriceSeries:
    store = research_store or (ResearchDataStore() if db_path is None else ResearchDataStore(db_path=db_path))
    try:
        return store.load_historical_price_series(symbol)
    except ResearchDataStoreError as exc:
        raise ExpandedVolumeThresholdValidationError(str(exc)) from exc


def _prepare_research_inputs(
    symbols: tuple[str, ...],
    *,
    db_path: Path | str | None,
    official_listing_dates_by_symbol: dict[str, date] | None = None,
    research_store: ResearchDataStore | None = None,
) -> tuple[dict[str, HistoricalPriceSeries], dict[str, object]]:
    official_listing_dates_by_symbol = official_listing_dates_by_symbol or {}
    store = research_store or (ResearchDataStore() if db_path is None else ResearchDataStore(db_path=db_path))
    resolved_db_path = store.resolved_db_path
    price_series_by_symbol = {}
    technical_series_by_symbol = {}
    for symbol in symbols:
        raw = load_historical_price_series_read_only(symbol, db_path=resolved_db_path, research_store=store)
        raw = _trim_before_official_listing(raw, official_listing_dates_by_symbol.get(symbol))
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


def _coverage_rows(db_path: Path | str | None, *, start_date: date, end_date: date) -> tuple[sqlite3.Row, ...]:
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


def _materialized_twse_common_stock_symbols(db_path: Path | str | None) -> tuple[str, ...]:
    store = ResearchDataStore() if db_path is None else ResearchDataStore(db_path=db_path)
    return store.materialized_twse_common_stock_symbols()


def _connect_read_only(db_path: Path | str | None):
    store = ResearchDataStore() if db_path is None else ResearchDataStore(db_path=db_path)
    return store.connect_read_only()


def _is_taiwan_symbol(symbol: str) -> bool:
    return symbol.endswith(".TW") or symbol.endswith(".TWO")


def _is_materialized_twse_common_stock(symbol: str) -> bool:
    code, _, suffix = symbol.partition(".")
    return code.isdigit() and len(code) == 4 and suffix == "TW" and symbol != "0050.TW"


def _trim_before_official_listing(
    price_series: HistoricalPriceSeries,
    official_listing_date: date | None,
) -> HistoricalPriceSeries:
    if official_listing_date is None:
        return price_series
    return HistoricalPriceSeries(
        symbol=price_series.symbol,
        currency=price_series.currency,
        bars=tuple(bar for bar in price_series.bars if bar.trading_date >= official_listing_date),
        fetched_at=price_series.fetched_at,
        is_stale=price_series.is_stale,
        source=price_series.source,
    )


def _expanded_symbol_summaries(
    rows: tuple[ThresholdSymbolRobustnessSummary, ...],
) -> tuple[ExpandedThresholdSymbolSummary, ...]:
    return tuple(
        ExpandedThresholdSymbolSummary(
            symbol=row.symbol,
            threshold=row.threshold,
            eligible_observation_date_count=row.observation_count,
            observation_count=row.observation_count,
            hit_count=row.hit_count,
            miss_count=row.miss_count,
            incomplete_count=row.incomplete_count,
            not_evaluable_count=row.not_evaluable_count,
            resolved_count=row.resolved_count,
            historical_hit_rate=row.historical_hit_rate,
            delta_hit_rate_vs_1_20_pp=row.delta_hit_rate_vs_1_20_pp,
            observation_count_delta_vs_1_20=row.observation_count_delta_vs_1_20,
            observation_count_change_rate_vs_1_20=row.observation_count_change_rate_vs_1_20,
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
            eligible_symbol_count=0,
            observation_count=row.observation_count,
            hit_count=row.hit_count,
            miss_count=row.miss_count,
            incomplete_count=row.incomplete_count,
            not_evaluable_count=row.not_evaluable_count,
            resolved_count=row.resolved_count,
            historical_hit_rate=row.historical_hit_rate,
            delta_hit_rate_vs_1_20_pp=row.delta_hit_rate_vs_1_20_pp,
            observation_count_delta_vs_1_20=row.observation_count_delta_vs_1_20,
        )
        for row in rows
    )


def _expanded_year_summaries_with_eligible_symbols(
    rows: tuple[ThresholdYearRobustnessSummary, ...],
    eligible_symbol_count_by_year: dict[int, int],
) -> tuple[ExpandedThresholdYearSummary, ...]:
    return tuple(
        ExpandedThresholdYearSummary(
            year=row.year,
            threshold=row.threshold,
            eligible_symbol_count=eligible_symbol_count_by_year.get(row.year, 0),
            observation_count=row.observation_count,
            hit_count=row.hit_count,
            miss_count=row.miss_count,
            incomplete_count=row.incomplete_count,
            not_evaluable_count=row.not_evaluable_count,
            resolved_count=row.resolved_count,
            historical_hit_rate=row.historical_hit_rate,
            delta_hit_rate_vs_1_20_pp=row.delta_hit_rate_vs_1_20_pp,
            observation_count_delta_vs_1_20=row.observation_count_delta_vs_1_20,
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
        added = []
        baseline_sizes = []
        candidate_sizes = []
        for symbol in robustness.symbols:
            baseline = rows[(symbol, robustness.baseline_threshold)]
            candidate = rows[(symbol, threshold)]
            if baseline.resolved_count > 0:
                baseline_resolved += 1
                baseline_sizes.append(baseline.resolved_count)
            if candidate.resolved_count > 0:
                candidate_sizes.append(candidate.resolved_count)
            if baseline.observation_count == 0 and candidate.observation_count > 0:
                added.append(symbol)
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
                candidate_added_sample_symbols=tuple(added),
                baseline_resolved_sample_sizes=tuple(sorted(baseline_sizes)),
                candidate_resolved_sample_sizes=tuple(sorted(candidate_sizes)),
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
        largest_year_row = max(years, key=lambda row: (row.observation_count, -row.year), default=None)
        year_2025_count = next((row.observation_count for row in years if row.year == 2025), 0)
        rows.append(
            ThresholdConcentrationMetric(
                threshold=threshold,
                observation_count=total,
                year_2025_share=None if total == 0 else year_2025_count / total,
                latest_year=latest_year,
                latest_year_share=None if total == 0 else latest_year_count / total,
                largest_year=None if largest_year_row is None else largest_year_row.year,
                largest_year_share=None if total == 0 or largest_year_row is None else largest_year_row.observation_count / total,
                top_1_symbol_share=None if total == 0 else sum(top_counts[:1]) / total,
                top_2_symbol_share=None if total == 0 else sum(top_counts[:2]) / total,
                top_5_symbol_share=None if total == 0 else sum(top_counts[:5]) / total,
                top_10_symbol_share=None if total == 0 else sum(top_counts[:10]) / total,
            )
        )
    return tuple(rows)


def _eligible_years_by_symbol(symbols, observations) -> dict[str, set[int]]:
    years_by_symbol = {symbol: set() for symbol in symbols}
    for observation in observations:
        if observation.status.name == "NOT_EVALUABLE":
            continue
        years_by_symbol.setdefault(observation.symbol, set()).add(observation.trading_date.year)
    return years_by_symbol


def _eligible_symbol_count_by_year(symbols, observations) -> dict[int, int]:
    by_year: dict[int, set[str]] = {year: set() for year in range(2018, 2026)}
    for observation in observations:
        if observation.status.name == "NOT_EVALUABLE":
            continue
        if observation.symbol in symbols and observation.trading_date.year in by_year:
            by_year[observation.trading_date.year].add(observation.symbol)
    return {year: len(symbols_for_year) for year, symbols_for_year in by_year.items()}


def _readiness_classification_by_symbol(
    symbols,
    observations,
    *,
    official_listing_dates_by_symbol: dict[str, date] | None,
    research_start: date,
) -> dict[str, str]:
    full_years = set(range(2018, 2026))
    by_symbol = _eligible_years_by_symbol(symbols, observations)
    listing_dates = official_listing_dates_by_symbol or {}
    classifications = {}
    for symbol in symbols:
        years = by_symbol.get(symbol, set())
        listing_date = listing_dates.get(symbol)
        listed_after_research_start = listing_date is not None and listing_date > research_start
        if listed_after_research_start:
            classifications[symbol] = READINESS_PARTIAL_WINDOW_VALID
        elif full_years.issubset(years):
            classifications[symbol] = READINESS_FULL_WINDOW_ELIGIBLE
        elif years:
            classifications[symbol] = READINESS_PARTIAL_WINDOW_VALID
        else:
            classifications[symbol] = READINESS_DATA_QUALITY_BLOCKED
    return classifications


def _readiness_counts(readiness_by_symbol: dict[str, str]) -> dict[str, int]:
    return {
        READINESS_FULL_WINDOW_ELIGIBLE: sum(
            status == READINESS_FULL_WINDOW_ELIGIBLE for status in readiness_by_symbol.values()
        ),
        READINESS_PARTIAL_WINDOW_VALID: sum(
            status == READINESS_PARTIAL_WINDOW_VALID for status in readiness_by_symbol.values()
        ),
        READINESS_DATA_QUALITY_BLOCKED: sum(
            status == READINESS_DATA_QUALITY_BLOCKED for status in readiness_by_symbol.values()
        ),
    }


def _subset_summaries(
    subset_name: str,
    symbols: tuple[str, ...],
    robustness: VolumeThresholdRobustnessResult,
) -> tuple[UniverseSubsetThresholdSummary, ...]:
    symbol_set = set(symbols)
    rows = []
    for threshold in robustness.candidate_thresholds:
        per_symbol = [
            row
            for row in robustness.per_symbol_summaries
            if row.threshold == threshold and row.symbol in symbol_set
        ]
        observation_count = sum(row.observation_count for row in per_symbol)
        hit_count = sum(row.hit_count for row in per_symbol)
        miss_count = sum(row.miss_count for row in per_symbol)
        incomplete_count = sum(row.incomplete_count for row in per_symbol)
        not_evaluable_count = sum(row.not_evaluable_count for row in per_symbol)
        resolved_count = hit_count + miss_count
        rows.append(
            UniverseSubsetThresholdSummary(
                subset_name=subset_name,
                threshold=threshold,
                symbol_count=len(symbols),
                observation_count=observation_count,
                hit_count=hit_count,
                miss_count=miss_count,
                incomplete_count=incomplete_count,
                not_evaluable_count=not_evaluable_count,
                resolved_count=resolved_count,
                historical_hit_rate=None if resolved_count == 0 else hit_count / resolved_count,
            )
        )
    return tuple(rows)


def _year_consistency_by_threshold(
    rows: tuple[ThresholdYearRobustnessSummary, ...],
) -> dict[float, dict[str, int]]:
    by_threshold_year = {(row.threshold, row.year): row for row in rows}
    result = {}
    for threshold in (1.00, 1.10):
        positive = negative = same = unavailable = 0
        for year in range(2018, 2026):
            candidate = by_threshold_year[(threshold, year)]
            baseline = by_threshold_year[(1.20, year)]
            if candidate.historical_hit_rate is None or baseline.historical_hit_rate is None:
                unavailable += 1
            elif candidate.historical_hit_rate > baseline.historical_hit_rate:
                positive += 1
            elif candidate.historical_hit_rate < baseline.historical_hit_rate:
                negative += 1
            else:
                same += 1
        result[threshold] = {
            "positive_years": positive,
            "negative_years": negative,
            "same_years": same,
            "unavailable_years": unavailable,
        }
    return result


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
    year_consistency: dict[float, dict[str, int]],
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
                year_consistency=_classify_year_consistency(year_consistency[threshold]),
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


def _classify_year_consistency(row: dict[str, int]) -> str:
    available = row["positive_years"] + row["negative_years"] + row["same_years"]
    if available == 0:
        return "UNAVAILABLE"
    if row["negative_years"] == 0:
        return "SUPPORTED"
    if row["positive_years"] > 0 or row["same_years"] > 0:
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
