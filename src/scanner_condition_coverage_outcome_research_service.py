from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path

from database import DEFAULT_DB_PATH
from expanded_volume_threshold_validation_service import READINESS_DATA_QUALITY_BLOCKED
from expanded_volume_threshold_validation_service import READINESS_FULL_WINDOW_ELIGIBLE
from expanded_volume_threshold_validation_service import READINESS_PARTIAL_WINDOW_VALID
from expanded_volume_threshold_validation_service import _materialized_twse_common_stock_symbols
from expanded_volume_threshold_validation_service import _prepare_research_inputs
from expanded_volume_threshold_validation_service import _readiness_classification_by_symbol
from expanded_volume_threshold_validation_service import _readiness_counts
from expanded_volume_threshold_validation_service import load_twse_listing_date_snapshot
from historical_condition_outcome_service import ConditionOutcomeObservation
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonConfig
from historical_condition_outcome_service import compare_historical_condition_outcomes
from models import OutcomeEvaluationStatus
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsConfig
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsService
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from volume_threshold_robustness_service import DEFAULT_OBSERVATION_END
from volume_threshold_robustness_service import DEFAULT_OBSERVATION_START
from volume_threshold_robustness_service import DEFAULT_OUTCOME_HORIZON_BARS
from volume_threshold_robustness_service import DEFAULT_OVERLAP_REDUCTION_SPACING_BARS
from volume_threshold_robustness_service import DEFAULT_WARMUP_TRADING_BARS
from volume_threshold_robustness_service import VolumeThresholdRobustnessConfig
from volume_threshold_robustness_service import _overlap_reduced_observations
from volume_threshold_robustness_service import _prepared_trading_bar_index_by_identity
from volume_threshold_sensitivity_service import VOLUME_CONDITION_ID


CANONICAL_CONDITION_IDS = (
    "analysis_close_vs_sma_20",
    "sma_20_vs_sma_60",
    "volume_ratio_20",
    "rsi_14",
    "distance_to_prior_60d_high",
)
PRIMARY_COVERAGE_COUNTS = (5, 4, 3)
V1_DAILY_BASELINE_N = 1821
V1_DAILY_BASELINE_HIT = 1567
V1_DAILY_BASELINE_MISS = 254
V1_DAILY_BASELINE_HHR = 1567 / (1567 + 254)
V1_1_INCREMENTAL_VOLUME_LOW = 1.10
PRODUCTION_V1_VOLUME_THRESHOLD = 1.20
DEFAULT_LISTING_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "research_inputs"
    / "twse_listing_dates_2026_08_09.json"
)
DEFAULT_RESEARCH_OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "research_outputs"
    / "scanner_condition_coverage_outcomes_2018_2025.json"
)
DEFAULT_RESEARCH_DOC_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "HISTORICAL_CONDITION_COVERAGE_OUTCOME_STUDY.md"
)
FROZEN_SUBPERIODS = (
    ("2018-2020", date(2018, 1, 1), date(2020, 12, 31)),
    ("2021-2023", date(2021, 1, 1), date(2023, 12, 31)),
    ("2024", date(2024, 1, 1), date(2024, 12, 31)),
    ("2025", date(2025, 1, 1), date(2025, 12, 31)),
)


class ConditionCoverageOutcomeStudyError(Exception):
    """Raised when the research-only condition coverage study cannot continue."""


@dataclass(frozen=True)
class CoverageOutcomeRow:

    coverage_count: int

    missing_signature: str

    observation_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    hhr: float | None

    symbol_count: int

    sample_flag: str

    share: float | None = None

    period: str | None = None


@dataclass(frozen=True)
class CoverageConcentrationRow:

    coverage_count: int

    observation_count: int

    unique_symbols: int

    median_observations_per_symbol: float | None

    top_1_symbol_share: float | None

    top_5_symbol_share: float | None

    top_10_symbol_share: float | None

    year_2025_share: float | None

    year_2024_2025_share: float | None


@dataclass(frozen=True)
class V11IncrementalConsistency:

    missing_volume_1_10_to_lt_1_20_count: int

    v1_1_incremental_identity_count: int

    identity_match: bool

    missing_from_v1_1_count: int

    extra_in_v1_1_count: int


@dataclass(frozen=True)
class DatabaseSafetyAudit:

    db_path: str

    row_count: int

    symbol_count: int

    duplicate_count: int

    integrity_check: str

    sha256: str


@dataclass(frozen=True)
class ConditionCoverageOutcomeStudyResult:

    metadata: dict

    db_audit_before: DatabaseSafetyAudit

    db_audit_after: DatabaseSafetyAudit

    readiness_counts: dict[str, int]

    overall: tuple[CoverageOutcomeRow, ...]

    missing_condition_4_of_5: tuple[CoverageOutcomeRow, ...]

    volume_subgroups_4_of_5: tuple[CoverageOutcomeRow, ...]

    v1_1_incremental_consistency: V11IncrementalConsistency

    missing_pairs_3_of_5: tuple[CoverageOutcomeRow, ...]

    year_breakdown: tuple[CoverageOutcomeRow, ...]

    subperiod_breakdown: tuple[CoverageOutcomeRow, ...]

    missing_condition_4_of_5_by_subperiod: tuple[CoverageOutcomeRow, ...]

    concentration: tuple[CoverageConcentrationRow, ...]

    overlap_reduced: tuple[CoverageOutcomeRow, ...]

    evidence_classification: dict[str, str]

    checksum: str


def run_final_condition_coverage_outcome_study(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    listing_date_snapshot_path: Path | str = DEFAULT_LISTING_SNAPSHOT_PATH,
    generated_at: datetime | None = None,
) -> ConditionCoverageOutcomeStudyResult:
    generated_at = generated_at or datetime.now(UTC)
    before = database_safety_audit(db_path)
    symbols = _materialized_twse_common_stock_symbols(db_path)
    snapshot = load_twse_listing_date_snapshot(
        listing_date_snapshot_path,
        required_symbols=symbols,
    )
    if len(symbols) != 218:
        raise ConditionCoverageOutcomeStudyError(
            f"Frozen TWSE research universe must contain 218 symbols; got {len(symbols)}."
        )
    comparison_price_series, technical_series = _prepare_research_inputs(
        symbols,
        db_path=db_path,
        official_listing_dates_by_symbol=snapshot.listing_dates_by_symbol,
    )
    diagnostics = HistoricalConditionDiagnosticsService(
        price_loader=lambda *args, **kwargs: _unexpected_mutating_or_network_load(),
        technical_builder=lambda *args, **kwargs: _unexpected_mutating_or_network_load(),
    ).run_diagnostics(
        symbols,
        HistoricalConditionDiagnosticsConfig(
            start_date=DEFAULT_OBSERVATION_START,
            end_date=DEFAULT_OBSERVATION_END,
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
            warmup_trading_bars=DEFAULT_WARMUP_TRADING_BARS,
            observation_unit="DAILY",
            overlap_possible=True,
        ),
        generated_at=generated_at,
    )
    readiness_by_symbol = _readiness_classification_by_symbol(
        symbols,
        comparison.outcome_observations,
        official_listing_dates_by_symbol=snapshot.listing_dates_by_symbol,
        research_start=DEFAULT_OBSERVATION_START,
    )
    result = analyze_condition_coverage_outcomes(
        tuple(comparison.outcome_observations),
        generated_at=generated_at,
        symbols=symbols,
        price_series_by_symbol=comparison_price_series,
        db_audit_before=before,
        db_audit_after=database_safety_audit(db_path),
        readiness_counts=_readiness_counts(readiness_by_symbol),
        universe_metadata={
            "universe_id": "frozen_twse_research_universe_2026_08_09",
            "frozen_symbol_count": len(symbols),
            "listing_date_source": str(listing_date_snapshot_path),
            "listing_date_snapshot_checksum": snapshot.snapshot_checksum,
        },
    )
    if result.db_audit_before != result.db_audit_after:
        raise ConditionCoverageOutcomeStudyError("DB safety audit changed during read-only study.")
    return result


def analyze_condition_coverage_outcomes(
    observations: tuple[ConditionOutcomeObservation, ...],
    *,
    generated_at: datetime | None = None,
    symbols: tuple[str, ...] | None = None,
    price_series_by_symbol: dict | None = None,
    db_audit_before: DatabaseSafetyAudit | None = None,
    db_audit_after: DatabaseSafetyAudit | None = None,
    readiness_counts: dict[str, int] | None = None,
    universe_metadata: dict | None = None,
) -> ConditionCoverageOutcomeStudyResult:
    generated_at = generated_at or datetime.now(UTC)
    _validate_observations(observations)
    symbols = symbols or tuple(sorted({observation.symbol for observation in observations}))
    grouped = {
        coverage: tuple(
            observation for observation in observations
            if observation.matched_condition_count == coverage
        )
        for coverage in PRIMARY_COVERAGE_COUNTS
    }
    overall = tuple(
        _coverage_row(coverage, "ALL", grouped[coverage])
        for coverage in PRIMARY_COVERAGE_COUNTS
    )
    four_of_five = grouped[4]
    three_of_five = grouped[3]
    missing_4 = tuple(
        _coverage_row(
            4,
            f"MISSING_{condition_id}",
            tuple(observation for observation in four_of_five if observation.missing_condition_ids == (condition_id,)),
            share_denominator=len(four_of_five),
        )
        for condition_id in CANONICAL_CONDITION_IDS
    )
    volume_subgroups = _volume_subgroup_rows(four_of_five)
    missing_pairs = _missing_pair_rows(three_of_five)
    year_breakdown = tuple(
        _coverage_row(
            coverage,
            "ALL",
            tuple(observation for observation in grouped[coverage] if observation.trading_date.year == year),
            period=str(year),
        )
        for year in range(DEFAULT_OBSERVATION_START.year, DEFAULT_OBSERVATION_END.year + 1)
        for coverage in PRIMARY_COVERAGE_COUNTS
    )
    subperiod_breakdown = tuple(
        _coverage_row(
            coverage,
            "ALL",
            _filter_period(grouped[coverage], start, end),
            period=name,
        )
        for name, start, end in FROZEN_SUBPERIODS
        for coverage in PRIMARY_COVERAGE_COUNTS
    )
    missing_by_period = tuple(
        _coverage_row(
            4,
            f"MISSING_{condition_id}",
            _filter_period(
                tuple(observation for observation in four_of_five if observation.missing_condition_ids == (condition_id,)),
                start,
                end,
            ),
            period=name,
        )
        for name, start, end in FROZEN_SUBPERIODS
        for condition_id in CANONICAL_CONDITION_IDS
    )
    concentration = tuple(
        _concentration_row(coverage, grouped[coverage])
        for coverage in PRIMARY_COVERAGE_COUNTS
    )
    overlap_reduced = _overlap_reduced_rows(grouped, price_series_by_symbol)
    v11_consistency = _v1_1_incremental_consistency(four_of_five, observations)
    evidence = {
        "4/5": _classify_evidence(_row_by_coverage(overall, 4), _row_by_coverage(overall, 5), _concentration_by_coverage(concentration, 4)),
        "3/5": _classify_evidence(_row_by_coverage(overall, 3), _row_by_coverage(overall, 5), _concentration_by_coverage(concentration, 3)),
    }
    metadata = {
        "study_id": "historical_condition_coverage_outcome_study_phase_1",
        "generated_at": generated_at.isoformat(),
        "date_window": {
            "start": DEFAULT_OBSERVATION_START.isoformat(),
            "end": DEFAULT_OBSERVATION_END.isoformat(),
        },
        "observation_unit": "DAILY",
        "signal_definition_id": TECHNICAL_EXAMPLE_SIGNAL_V1.id,
        "canonical_condition_ids": CANONICAL_CONDITION_IDS,
        "outcome_definition_id": RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id,
        "outcome_horizon_bars": DEFAULT_OUTCOME_HORIZON_BARS,
        "warmup_trading_bars": DEFAULT_WARMUP_TRADING_BARS,
        "overlap_reduction_spacing_bars": DEFAULT_OVERLAP_REDUCTION_SPACING_BARS,
        "production_v1_unchanged": True,
        "db_write_performed": False,
        "network_fetch_performed": False,
        "survivorship_warning": (
            "Frozen universe is derived from 2026 current ETF constituents, not 2018-2025 "
            "point-in-time constituents; survivorship and constituent look-back bias remain."
        ),
        **(universe_metadata or {}),
    }
    before = db_audit_before or DatabaseSafetyAudit("", 0, 0, 0, "", "")
    after = db_audit_after or before
    readiness = readiness_counts or {
        READINESS_FULL_WINDOW_ELIGIBLE: 0,
        READINESS_PARTIAL_WINDOW_VALID: 0,
        READINESS_DATA_QUALITY_BLOCKED: 0,
    }
    result_without_checksum = {
        "metadata": metadata,
        "db_audit_before": asdict(before),
        "db_audit_after": asdict(after),
        "readiness_counts": readiness,
        "overall": [asdict(row) for row in overall],
        "missing_condition_4_of_5": [asdict(row) for row in missing_4],
        "volume_subgroups_4_of_5": [asdict(row) for row in volume_subgroups],
        "v1_1_incremental_consistency": asdict(v11_consistency),
        "missing_pairs_3_of_5": [asdict(row) for row in missing_pairs],
        "year_breakdown": [asdict(row) for row in year_breakdown],
        "subperiod_breakdown": [asdict(row) for row in subperiod_breakdown],
        "missing_condition_4_of_5_by_subperiod": [asdict(row) for row in missing_by_period],
        "concentration": [asdict(row) for row in concentration],
        "overlap_reduced": [asdict(row) for row in overlap_reduced],
        "evidence_classification": evidence,
    }
    checksum = _payload_checksum(result_without_checksum)
    return ConditionCoverageOutcomeStudyResult(
        metadata=metadata,
        db_audit_before=before,
        db_audit_after=after,
        readiness_counts=readiness,
        overall=overall,
        missing_condition_4_of_5=missing_4,
        volume_subgroups_4_of_5=volume_subgroups,
        v1_1_incremental_consistency=v11_consistency,
        missing_pairs_3_of_5=missing_pairs,
        year_breakdown=year_breakdown,
        subperiod_breakdown=subperiod_breakdown,
        missing_condition_4_of_5_by_subperiod=missing_by_period,
        concentration=concentration,
        overlap_reduced=overlap_reduced,
        evidence_classification=evidence,
        checksum=checksum,
    )


def write_condition_coverage_research_artifacts(
    result: ConditionCoverageOutcomeStudyResult,
    *,
    json_path: Path | str = DEFAULT_RESEARCH_OUTPUT_PATH,
    doc_path: Path | str = DEFAULT_RESEARCH_DOC_PATH,
) -> tuple[Path, Path]:
    json_target = Path(json_path)
    doc_target = Path(doc_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(
        json.dumps(result_to_dict(result), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    doc_target.write_text(render_markdown_report(result), encoding="utf-8")
    return json_target, doc_target


def result_to_dict(result: ConditionCoverageOutcomeStudyResult) -> dict:
    payload = {
        "metadata": result.metadata,
        "db_audit_before": asdict(result.db_audit_before),
        "db_audit_after": asdict(result.db_audit_after),
        "readiness_counts": result.readiness_counts,
        "overall": [asdict(row) for row in result.overall],
        "missing_condition_4_of_5": [asdict(row) for row in result.missing_condition_4_of_5],
        "volume_subgroups_4_of_5": [asdict(row) for row in result.volume_subgroups_4_of_5],
        "v1_1_incremental_consistency": asdict(result.v1_1_incremental_consistency),
        "missing_pairs_3_of_5": [asdict(row) for row in result.missing_pairs_3_of_5],
        "year_breakdown": [asdict(row) for row in result.year_breakdown],
        "subperiod_breakdown": [asdict(row) for row in result.subperiod_breakdown],
        "missing_condition_4_of_5_by_subperiod": [
            asdict(row) for row in result.missing_condition_4_of_5_by_subperiod
        ],
        "concentration": [asdict(row) for row in result.concentration],
        "overlap_reduced": [asdict(row) for row in result.overlap_reduced],
        "evidence_classification": result.evidence_classification,
        "checksum": result.checksum,
    }
    return payload


def render_markdown_report(result: ConditionCoverageOutcomeStudyResult) -> str:
    lines = [
        "# Historical Condition Coverage Outcome Study",
        "",
        "Phase 1 research-only study for canonical `technical_example_v1` condition coverage.",
        "",
        "## Research Question",
        "",
        "Compare daily historical outcomes for exactly `5/5`, `4/5`, and `3/5` condition coverage, including missing-condition and missing-pair splits.",
        "",
        "## Dataset / Universe",
        "",
        f"- Date window: `{result.metadata['date_window']['start']}` through `{result.metadata['date_window']['end']}`",
        f"- Universe: `{result.metadata.get('universe_id', 'frozen_twse_research_universe')}`",
        f"- Frozen symbol count: `{result.metadata.get('frozen_symbol_count', 'N.A.')}`",
        f"- FULL_WINDOW_ELIGIBLE: `{result.readiness_counts.get(READINESS_FULL_WINDOW_ELIGIBLE, 0)}`",
        f"- PARTIAL_WINDOW_VALID: `{result.readiness_counts.get(READINESS_PARTIAL_WINDOW_VALID, 0)}`",
        f"- DATA_QUALITY_BLOCKED: `{result.readiness_counts.get(READINESS_DATA_QUALITY_BLOCKED, 0)}`",
        "",
        "Eligibility uses official listing date plus 60 trading-bar warm-up. Not-yet-listed symbols are not treated as zero-observation failures.",
        "",
        "Outcome semantics reuse the attached canonical historical outcome `raw_high_breakout_60d_within_20d_v1`; this report does not create a second HIT/MISS definition.",
        "",
        "## Overall",
        "",
        _markdown_table(("Coverage", "n", "HIT", "MISS", "HHR", "Sample"), [
            (f"{row.coverage_count}/5", row.observation_count, row.hit_count, row.miss_count, _fmt_pct(row.hhr), row.sample_flag)
            for row in result.overall
        ]),
        "",
        f"- 4/5 minus 5/5 HHR delta: `{_fmt_pp(_hhr_delta(result, 4, 5))}`",
        f"- 3/5 minus 5/5 HHR delta: `{_fmt_pp(_hhr_delta(result, 3, 5))}`",
        f"- 5/5 control baseline reconciled: `{_control_reconciled(result)}`",
        "",
        "## 4/5 Missing Condition",
        "",
        _markdown_table(("Missing condition", "n", "HIT", "MISS", "HHR", "Share", "Sample"), [
            (row.missing_signature.removeprefix("MISSING_"), row.observation_count, row.hit_count, row.miss_count, _fmt_pct(row.hhr), _fmt_pct(row.share), row.sample_flag)
            for row in result.missing_condition_4_of_5
        ]),
        "",
        "## 4/5 Missing Volume Subgroups",
        "",
        _markdown_table(("Subgroup", "n", "HIT", "MISS", "HHR", "Sample"), [
            (row.missing_signature, row.observation_count, row.hit_count, row.miss_count, _fmt_pct(row.hhr), row.sample_flag)
            for row in result.volume_subgroups_4_of_5
        ]),
        "",
        f"V1.1 incremental identity consistency: `{result.v1_1_incremental_consistency.identity_match}`.",
        "",
        "## 3/5 Missing Pairs",
        "",
        _markdown_table(("Missing pair", "n", "HIT", "MISS", "HHR", "Share", "Sample"), [
            (row.missing_signature, row.observation_count, row.hit_count, row.miss_count, _fmt_pct(row.hhr), _fmt_pct(row.share), row.sample_flag)
            for row in result.missing_pairs_3_of_5
        ]),
        "",
        "## Year Robustness",
        "",
        _markdown_table(("Year", "5/5 n/HHR", "4/5 n/HHR", "3/5 n/HHR"), _period_rows(result.year_breakdown)),
        "",
        "## Subperiod Robustness",
        "",
        _markdown_table(("Period", "5/5 n/HHR", "4/5 n/HHR", "3/5 n/HHR"), _period_rows(result.subperiod_breakdown)),
        "",
        "## Concentration",
        "",
        _markdown_table(("Coverage", "Symbols", "Median obs/symbol", "Top1", "Top5", "Top10", "2025", "2024+2025"), [
            (
                f"{row.coverage_count}/5",
                row.unique_symbols,
                "N.A." if row.median_observations_per_symbol is None else f"{row.median_observations_per_symbol:.2f}",
                _fmt_pct(row.top_1_symbol_share),
                _fmt_pct(row.top_5_symbol_share),
                _fmt_pct(row.top_10_symbol_share),
                _fmt_pct(row.year_2025_share),
                _fmt_pct(row.year_2024_2025_share),
            )
            for row in result.concentration
        ]),
        "",
        "## Evidence Classification",
        "",
        f"- 4/5 overall: `{result.evidence_classification['4/5']}`",
        f"- 3/5 overall: `{result.evidence_classification['3/5']}`",
        "",
        "These classifications describe research evidence only. They are not production promotion, ranking, score, probability, confidence, alert, or recommendation.",
        "",
        "## Safety Boundary",
        "",
        "- Production V1 remains unchanged and authoritative.",
        "- No Dashboard behavior was modified.",
        "- No database write was performed.",
        "- No network fetch was performed.",
        "- No ranking, score, probability, confidence, recommendation, alert, or scanner promotion was created.",
        "",
        "## Survivorship / Look-back Warning",
        "",
        result.metadata["survivorship_warning"],
        "",
        f"Checksum: `{result.checksum}`",
        "",
    ]
    return "\n".join(lines)


def database_safety_audit(db_path: Path | str = DEFAULT_DB_PATH) -> DatabaseSafetyAudit:
    path = Path(db_path)
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        row_count = connection.execute("SELECT COUNT(*) FROM historical_prices").fetchone()[0]
        symbol_count = connection.execute("SELECT COUNT(DISTINCT symbol) FROM historical_prices").fetchone()[0]
        duplicate_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT symbol, trading_date
                FROM historical_prices
                GROUP BY symbol, trading_date
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    return DatabaseSafetyAudit(
        db_path=str(path),
        row_count=row_count,
        symbol_count=symbol_count,
        duplicate_count=duplicate_count,
        integrity_check=integrity,
        sha256=_file_sha256(path),
    )


def _validate_observations(observations: tuple[ConditionOutcomeObservation, ...]) -> None:
    seen = set()
    for observation in observations:
        if observation.signal_definition_id != TECHNICAL_EXAMPLE_SIGNAL_V1.id:
            raise ConditionCoverageOutcomeStudyError("Study requires canonical technical_example_v1 observations.")
        if observation.total_condition_count != len(CANONICAL_CONDITION_IDS):
            raise ConditionCoverageOutcomeStudyError("Study requires five canonical V1 conditions.")
        if tuple(sorted(observation.passed_condition_ids, key=_condition_order)) != observation.passed_condition_ids:
            raise ConditionCoverageOutcomeStudyError("Passed condition IDs must use canonical ordering.")
        if tuple(sorted(observation.missing_condition_ids, key=_condition_order)) != observation.missing_condition_ids:
            raise ConditionCoverageOutcomeStudyError("Missing condition IDs must use canonical ordering.")
        if len(observation.passed_condition_ids) != observation.matched_condition_count:
            raise ConditionCoverageOutcomeStudyError("Matched count must equal passed condition ID count.")
        if len(observation.missing_condition_ids) != observation.total_condition_count - observation.matched_condition_count:
            raise ConditionCoverageOutcomeStudyError("Missing condition count is inconsistent with coverage.")
        identity = _identity(observation)
        if identity in seen:
            raise ConditionCoverageOutcomeStudyError("Daily observations must be unique by symbol/date/signal.")
        seen.add(identity)


def _coverage_row(
    coverage_count: int,
    missing_signature: str,
    observations: tuple[ConditionOutcomeObservation, ...],
    *,
    share_denominator: int | None = None,
    period: str | None = None,
) -> CoverageOutcomeRow:
    hit_count = _count_status(observations, OutcomeEvaluationStatus.HIT)
    miss_count = _count_status(observations, OutcomeEvaluationStatus.MISS)
    incomplete_count = _count_status(observations, OutcomeEvaluationStatus.INCOMPLETE)
    not_evaluable_count = _count_status(observations, OutcomeEvaluationStatus.NOT_EVALUABLE)
    resolved = hit_count + miss_count
    n = len(observations)
    return CoverageOutcomeRow(
        coverage_count=coverage_count,
        missing_signature=missing_signature,
        observation_count=n,
        hit_count=hit_count,
        miss_count=miss_count,
        incomplete_count=incomplete_count,
        not_evaluable_count=not_evaluable_count,
        resolved_count=resolved,
        hhr=None if resolved == 0 else hit_count / resolved,
        symbol_count=len({observation.symbol for observation in observations}),
        sample_flag=_sample_flag(n),
        share=None if share_denominator in (None, 0) else n / share_denominator,
        period=period,
    )


def _volume_subgroup_rows(
    four_of_five: tuple[ConditionOutcomeObservation, ...],
) -> tuple[CoverageOutcomeRow, ...]:
    missing_volume = tuple(
        observation for observation in four_of_five
        if observation.missing_condition_ids == (VOLUME_CONDITION_ID,)
    )
    lower = tuple(observation for observation in missing_volume if _volume_value(observation) < V1_1_INCREMENTAL_VOLUME_LOW)
    v11_only = tuple(
        observation for observation in missing_volume
        if V1_1_INCREMENTAL_VOLUME_LOW <= _volume_value(observation) < PRODUCTION_V1_VOLUME_THRESHOLD
    )
    inconsistent = tuple(observation for observation in missing_volume if _volume_value(observation) >= PRODUCTION_V1_VOLUME_THRESHOLD)
    if inconsistent:
        raise ConditionCoverageOutcomeStudyError(
            "Missing-volume 4/5 observations cannot have volume_ratio_20 >= 1.20."
        )
    if len(lower) + len(v11_only) != len(missing_volume):
        raise ConditionCoverageOutcomeStudyError("Missing-volume subgroup counts do not reconcile.")
    return (
        _coverage_row(4, "MISSING_volume_ratio_20__volume_lt_1_10", lower),
        _coverage_row(4, "MISSING_volume_ratio_20__volume_1_10_to_lt_1_20", v11_only),
    )


def _missing_pair_rows(
    three_of_five: tuple[ConditionOutcomeObservation, ...],
) -> tuple[CoverageOutcomeRow, ...]:
    rows = []
    for pair in sorted({observation.missing_condition_ids for observation in three_of_five}):
        if len(pair) != 2:
            raise ConditionCoverageOutcomeStudyError("3/5 observations must have exactly two missing IDs.")
        rows.append(
            _coverage_row(
                3,
                "MISSING_" + "+".join(pair),
                tuple(observation for observation in three_of_five if observation.missing_condition_ids == pair),
                share_denominator=len(three_of_five),
            )
        )
    return tuple(sorted(rows, key=lambda row: (-row.observation_count, row.missing_signature)))


def _v1_1_incremental_consistency(
    four_of_five: tuple[ConditionOutcomeObservation, ...],
    observations: tuple[ConditionOutcomeObservation, ...],
) -> V11IncrementalConsistency:
    missing_volume_v11 = {
        _identity(observation)
        for observation in four_of_five
        if observation.missing_condition_ids == (VOLUME_CONDITION_ID,)
        and V1_1_INCREMENTAL_VOLUME_LOW <= _volume_value(observation) < PRODUCTION_V1_VOLUME_THRESHOLD
    }
    v11_incremental = {
        _identity(observation)
        for observation in observations
        if observation.missing_condition_ids == (VOLUME_CONDITION_ID,)
        and observation.matched_condition_count == 4
        and V1_1_INCREMENTAL_VOLUME_LOW <= _volume_value(observation) < PRODUCTION_V1_VOLUME_THRESHOLD
    }
    return V11IncrementalConsistency(
        missing_volume_1_10_to_lt_1_20_count=len(missing_volume_v11),
        v1_1_incremental_identity_count=len(v11_incremental),
        identity_match=missing_volume_v11 == v11_incremental,
        missing_from_v1_1_count=len(missing_volume_v11 - v11_incremental),
        extra_in_v1_1_count=len(v11_incremental - missing_volume_v11),
    )


def _concentration_row(
    coverage_count: int,
    observations: tuple[ConditionOutcomeObservation, ...],
) -> CoverageConcentrationRow:
    by_symbol: dict[str, int] = {}
    by_year: dict[int, int] = {}
    for observation in observations:
        by_symbol[observation.symbol] = by_symbol.get(observation.symbol, 0) + 1
        by_year[observation.trading_date.year] = by_year.get(observation.trading_date.year, 0) + 1
    counts = sorted(by_symbol.values(), reverse=True)
    total = len(observations)
    return CoverageConcentrationRow(
        coverage_count=coverage_count,
        observation_count=total,
        unique_symbols=len(by_symbol),
        median_observations_per_symbol=_median(tuple(sorted(counts))),
        top_1_symbol_share=_share(sum(counts[:1]), total),
        top_5_symbol_share=_share(sum(counts[:5]), total),
        top_10_symbol_share=_share(sum(counts[:10]), total),
        year_2025_share=_share(by_year.get(2025, 0), total),
        year_2024_2025_share=_share(by_year.get(2024, 0) + by_year.get(2025, 0), total),
    )


def _overlap_reduced_rows(
    grouped: dict[int, tuple[ConditionOutcomeObservation, ...]],
    price_series_by_symbol: dict | None,
) -> tuple[CoverageOutcomeRow, ...]:
    all_primary = tuple(observation for coverage in PRIMARY_COVERAGE_COUNTS for observation in grouped[coverage])
    if not all_primary:
        return tuple(_coverage_row(coverage, "OVERLAP_REDUCED_20_BARS", tuple()) for coverage in PRIMARY_COVERAGE_COUNTS)
    if price_series_by_symbol is not None:
        index = _prepared_trading_bar_index_by_identity(all_primary, price_series_by_symbol)
    else:
        index = {
            _identity(observation): position
            for position, observation in enumerate(sorted(all_primary, key=lambda item: (item.symbol, item.trading_date)))
        }
    return tuple(
        _coverage_row(
            coverage,
            "OVERLAP_REDUCED_20_BARS",
            _overlap_reduced_observations(
                grouped[coverage],
                index,
                spacing_bars=VolumeThresholdRobustnessConfig().overlap_reduction_spacing_bars,
            ),
        )
        for coverage in PRIMARY_COVERAGE_COUNTS
    )


def _filter_period(
    observations: tuple[ConditionOutcomeObservation, ...],
    start: date,
    end: date,
) -> tuple[ConditionOutcomeObservation, ...]:
    return tuple(observation for observation in observations if start <= observation.trading_date <= end)


def _sample_flag(observation_count: int) -> str:
    if observation_count < 10:
        return "VERY_SMALL_SAMPLE"
    if observation_count < 30:
        return "SMALL_SAMPLE"
    return "ADEQUATE"


def _classify_evidence(
    row: CoverageOutcomeRow,
    baseline: CoverageOutcomeRow,
    concentration: CoverageConcentrationRow,
) -> str:
    if row.observation_count < 30 or row.resolved_count < 30:
        return "INSUFFICIENT_SAMPLE"
    if concentration.year_2025_share is not None and concentration.year_2025_share >= 0.65:
        return "WEAK"
    if row.hhr is None or baseline.hhr is None:
        return "INSUFFICIENT_SAMPLE"
    if abs(row.hhr - baseline.hhr) < 0.02:
        return "MIXED"
    return "SUPPORTED"


def _period_rows(rows: tuple[CoverageOutcomeRow, ...]) -> list[tuple]:
    periods = tuple(dict.fromkeys(row.period for row in rows if row.period is not None))
    output = []
    for period in periods:
        values = []
        for coverage in PRIMARY_COVERAGE_COUNTS:
            row = next(item for item in rows if item.period == period and item.coverage_count == coverage)
            values.append(f"{row.observation_count} / {_fmt_pct(row.hhr)}")
        output.append((period, *values))
    return output


def _row_by_coverage(rows: tuple[CoverageOutcomeRow, ...], coverage: int) -> CoverageOutcomeRow:
    return next(row for row in rows if row.coverage_count == coverage)


def _concentration_by_coverage(rows: tuple[CoverageConcentrationRow, ...], coverage: int) -> CoverageConcentrationRow:
    return next(row for row in rows if row.coverage_count == coverage)


def _hhr_delta(result: ConditionCoverageOutcomeStudyResult, coverage: int, baseline: int) -> float | None:
    row = _row_by_coverage(result.overall, coverage)
    base = _row_by_coverage(result.overall, baseline)
    if row.hhr is None or base.hhr is None:
        return None
    return (row.hhr - base.hhr) * 100


def _control_reconciled(result: ConditionCoverageOutcomeStudyResult) -> bool:
    row = _row_by_coverage(result.overall, 5)
    return (
        row.observation_count == V1_DAILY_BASELINE_N
        and row.hit_count == V1_DAILY_BASELINE_HIT
        and row.miss_count == V1_DAILY_BASELINE_MISS
        and row.hhr is not None
        and round(row.hhr, 4) == round(V1_DAILY_BASELINE_HHR, 4)
    )


def _markdown_table(headers: tuple[str, ...], rows: list[tuple]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N.A."
    return f"{value * 100:.2f}%"


def _fmt_pp(value: float | None) -> str:
    if value is None:
        return "N.A."
    return f"{value:+.2f} pp"


def _volume_value(observation: ConditionOutcomeObservation) -> float:
    value = getattr(observation.diagnostic_observation.source_snapshot, VOLUME_CONDITION_ID, None)
    if not isinstance(value, (int, float)):
        return float("-inf")
    return float(value)


def _condition_order(condition_id: str) -> int:
    try:
        return CANONICAL_CONDITION_IDS.index(condition_id)
    except ValueError as exc:
        raise ConditionCoverageOutcomeStudyError(f"Unknown canonical condition id: {condition_id}") from exc


def _identity(observation: ConditionOutcomeObservation) -> tuple[str, object, str]:
    return (observation.symbol, observation.trading_date, observation.signal_definition_id)


def _count_status(observations, status: OutcomeEvaluationStatus) -> int:
    return sum(observation.status is status for observation in observations)


def _share(count: int, total: int) -> float | None:
    if total == 0:
        return None
    return count / total


def _median(values: tuple[int, ...]) -> float | None:
    if not values:
        return None
    midpoint = len(values) // 2
    if len(values) % 2:
        return float(values[midpoint])
    return (values[midpoint - 1] + values[midpoint]) / 2


def _payload_checksum(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unexpected_mutating_or_network_load():
    raise ConditionCoverageOutcomeStudyError("Research study must use frozen local inputs only.")

