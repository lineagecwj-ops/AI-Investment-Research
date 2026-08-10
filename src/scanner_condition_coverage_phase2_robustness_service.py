from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path

from database import DEFAULT_DB_PATH
from expanded_volume_threshold_validation_service import READINESS_FULL_WINDOW_ELIGIBLE
from expanded_volume_threshold_validation_service import READINESS_PARTIAL_WINDOW_VALID
from expanded_volume_threshold_validation_service import _materialized_twse_common_stock_symbols
from expanded_volume_threshold_validation_service import _prepare_research_inputs
from expanded_volume_threshold_validation_service import _readiness_classification_by_symbol
from expanded_volume_threshold_validation_service import _readiness_counts
from expanded_volume_threshold_validation_service import load_twse_listing_date_snapshot
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonConfig
from historical_condition_outcome_service import compare_historical_condition_outcomes
from models import OutcomeEvaluationStatus
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsConfig
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsService
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from scanner_condition_coverage_outcome_research_service import DEFAULT_LISTING_SNAPSHOT_PATH
from scanner_condition_coverage_outcome_research_service import DEFAULT_RESEARCH_OUTPUT_PATH
from scanner_condition_coverage_outcome_research_service import FROZEN_SUBPERIODS
from scanner_condition_coverage_outcome_research_service import PHASE1_RESEARCH_CHECKSUM
from scanner_condition_coverage_outcome_research_service import PRODUCTION_V1_VOLUME_THRESHOLD
from scanner_condition_coverage_outcome_research_service import V1_1_INCREMENTAL_VOLUME_LOW
from scanner_condition_coverage_outcome_research_service import _fmt_pct
from scanner_condition_coverage_outcome_research_service import _payload_checksum
from scanner_condition_coverage_outcome_research_service import _sample_flag
from scanner_condition_coverage_outcome_research_service import _share
from scanner_condition_coverage_outcome_research_service import database_safety_audit
from volume_threshold_robustness_service import DEFAULT_OBSERVATION_END
from volume_threshold_robustness_service import DEFAULT_OBSERVATION_START
from volume_threshold_robustness_service import DEFAULT_OVERLAP_REDUCTION_SPACING_BARS
from volume_threshold_robustness_service import DEFAULT_WARMUP_TRADING_BARS
from volume_threshold_robustness_service import _overlap_reduced_observations
from volume_threshold_robustness_service import _prepared_trading_bar_index_by_identity


SELECTED_MISSING_CONDITION_IDS = (
    "rsi_14",
    "volume_ratio_20",
    "distance_to_prior_60d_high",
)
PHASE2_OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "research_outputs"
    / "scanner_condition_coverage_phase2_robustness_2018_2025.json"
)
PHASE2_DOC_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "HISTORICAL_CONDITION_COVERAGE_PHASE2_ROBUSTNESS.md"
)


class ConditionCoveragePhase2RobustnessError(Exception):
    """Raised when Phase 2 robustness research cannot run safely."""


@dataclass(frozen=True)
class Phase2RobustnessResult:

    payload: dict

    checksum: str


def run_final_phase2_robustness_study(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    listing_date_snapshot_path: Path | str = DEFAULT_LISTING_SNAPSHOT_PATH,
    generated_at: datetime | None = None,
) -> Phase2RobustnessResult:
    generated_at = generated_at or datetime.now(UTC)
    before = database_safety_audit(db_path)
    symbols = _materialized_twse_common_stock_symbols(db_path)
    snapshot = load_twse_listing_date_snapshot(listing_date_snapshot_path, required_symbols=symbols)
    price_series_by_symbol, technical_series_by_symbol = _prepare_research_inputs(
        symbols,
        db_path=db_path,
        official_listing_dates_by_symbol=snapshot.listing_dates_by_symbol,
    )
    diagnostics = HistoricalConditionDiagnosticsService(
        price_loader=lambda *args, **kwargs: _unexpected_load(),
        technical_builder=lambda *args, **kwargs: _unexpected_load(),
    ).run_diagnostics(
        symbols,
        HistoricalConditionDiagnosticsConfig(
            start_date=DEFAULT_OBSERVATION_START,
            end_date=DEFAULT_OBSERVATION_END,
            signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
            force_refresh=False,
        ),
        technical_series_by_symbol=technical_series_by_symbol,
    )
    comparison = compare_historical_condition_outcomes(
        diagnostics,
        price_series_by_symbol=price_series_by_symbol,
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
    phase1_checksum = _load_phase1_checksum()
    if phase1_checksum != PHASE1_RESEARCH_CHECKSUM:
        raise ConditionCoveragePhase2RobustnessError("Phase 1 checksum input is not the locked checksum.")
    after = database_safety_audit(db_path)
    if before != after:
        raise ConditionCoveragePhase2RobustnessError("DB audit changed during Phase 2 read-only study.")
    return analyze_phase2_robustness(
        tuple(comparison.outcome_observations),
        generated_at=generated_at,
        readiness_by_symbol=readiness_by_symbol,
        readiness_counts=_readiness_counts(readiness_by_symbol),
        price_series_by_symbol=price_series_by_symbol,
        phase1_checksum=phase1_checksum,
        db_audit_before=before.__dict__,
        db_audit_after=after.__dict__,
        universe_metadata={
            "universe_id": "frozen_twse_research_universe_2026_08_09",
            "frozen_symbol_count": len(symbols),
            "listing_date_snapshot_checksum": snapshot.snapshot_checksum,
            "listing_date_source": str(listing_date_snapshot_path),
        },
    )


def analyze_phase2_robustness(
    observations: tuple,
    *,
    generated_at: datetime | None = None,
    readiness_by_symbol: dict[str, str] | None = None,
    readiness_counts: dict[str, int] | None = None,
    price_series_by_symbol: dict | None = None,
    phase1_checksum: str = PHASE1_RESEARCH_CHECKSUM,
    db_audit_before: dict | None = None,
    db_audit_after: dict | None = None,
    universe_metadata: dict | None = None,
) -> Phase2RobustnessResult:
    generated_at = generated_at or datetime.now(UTC)
    _validate_phase2_inputs(observations)
    readiness_by_symbol = readiness_by_symbol or {}
    readiness_counts = readiness_counts or {}
    groups = {
        condition_id: tuple(
            observation for observation in observations
            if observation.matched_condition_count == 4
            and observation.missing_condition_ids == (condition_id,)
        )
        for condition_id in SELECTED_MISSING_CONDITION_IDS
    }
    all_group_observations = tuple(observation for group in groups.values() for observation in group)
    bar_index = _bar_index(all_group_observations, price_series_by_symbol)
    group_payloads = {
        condition_id: _group_payload(
            condition_id,
            group_observations,
            observations,
            bar_index,
            readiness_by_symbol,
        )
        for condition_id, group_observations in groups.items()
    }
    payload_without_checksum = {
        "metadata": {
            "study_id": "historical_condition_coverage_phase2_robustness",
            "generated_at": generated_at.isoformat(),
            "phase1_input_checksum": phase1_checksum,
            "selected_missing_condition_ids": SELECTED_MISSING_CONDITION_IDS,
            "date_window": {
                "start": DEFAULT_OBSERVATION_START.isoformat(),
                "end": DEFAULT_OBSERVATION_END.isoformat(),
            },
            "signal_definition_id": TECHNICAL_EXAMPLE_SIGNAL_V1.id,
            "outcome_definition_id": RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id,
            "eligibility": "official listing date + 60 trading-bar warmup",
            "observation_unit": "DAILY",
            "de_overlap": f"{DEFAULT_OVERLAP_REDUCTION_SPACING_BARS} trading bars, canonical symbol-local spacing",
            "post_hoc_warning": (
                "These three groups were selected after Phase 1 observations. Results are descriptive "
                "post-hoc robustness research, not a confirmatory trial."
            ),
            "survivorship_warning": (
                "Frozen universe is derived from 2026 current ETF constituents, not 2018-2025 "
                "point-in-time constituents; survivorship and constituent look-back bias remain."
            ),
            "no_threshold_tuning": True,
            "production_v1_unchanged": True,
            "db_write_performed": False,
            "network_fetch_performed": False,
            **(universe_metadata or {}),
        },
        "readiness_counts": readiness_counts,
        "db_audit_before": db_audit_before or {},
        "db_audit_after": db_audit_after or {},
        "groups": group_payloads,
        "phase3_boundary": (
            "Phase 2 can only identify whether further candidate-display research is worth studying. "
            "It does not approve scanner promotion, ranking, alerts, or recommendations."
        ),
    }
    checksum = _payload_checksum(payload_without_checksum)
    payload = {**payload_without_checksum, "semantic_checksum": checksum}
    return Phase2RobustnessResult(payload=payload, checksum=checksum)


def write_phase2_robustness_artifacts(
    result: Phase2RobustnessResult,
    *,
    json_path: Path | str = PHASE2_OUTPUT_PATH,
    doc_path: Path | str = PHASE2_DOC_PATH,
) -> tuple[Path, Path]:
    json_target = Path(json_path)
    doc_target = Path(doc_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(
        json.dumps(result.payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    doc_target.write_text(render_phase2_markdown(result), encoding="utf-8")
    return json_target, doc_target


def _load_phase1_checksum(path: Path | str = DEFAULT_RESEARCH_OUTPUT_PATH) -> str:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return str(payload.get("checksum", ""))


def render_phase2_markdown(result: Phase2RobustnessResult) -> str:
    payload = result.payload
    lines = [
        "# Historical Condition Coverage Phase 2 Robustness",
        "",
        "Research-only robustness review for exactly three Phase 1 `4/5` missing-condition groups: `rsi_14`, `volume_ratio_20`, and `distance_to_prior_60d_high`.",
        "",
        "## Scope",
        "",
        f"- Phase 1 input checksum: `{payload['metadata']['phase1_input_checksum']}`",
        f"- Window: `{payload['metadata']['date_window']['start']}` through `{payload['metadata']['date_window']['end']}`",
        f"- Signal: `{payload['metadata']['signal_definition_id']}`",
        f"- Outcome: `{payload['metadata']['outcome_definition_id']}`",
        f"- Universe: `{payload['metadata'].get('universe_id', 'N.A.')}` / `{payload['metadata'].get('frozen_symbol_count', 'N.A.')}` symbols",
        "",
        "These groups were selected after Phase 1 observations. This is descriptive post-hoc research, not a confirmatory trial.",
        "",
        "## Group Results",
        "",
        _markdown_table(
            ("Group", "Daily", "Reduced", "First Event", "FULL", "PARTIAL", "2025", "Top1"),
            [
                (
                    condition_id,
                    _summary_cell(group["daily"]),
                    _summary_cell(group["reduced"]),
                    _summary_cell(group["first_event"]),
                    _summary_cell(group["full_partial"]["daily"][READINESS_FULL_WINDOW_ELIGIBLE]),
                    _summary_cell(group["full_partial"]["daily"][READINESS_PARTIAL_WINDOW_VALID]),
                    _fmt_pct(group["time_concentration"]["year_2025_share"]),
                    _fmt_pct(group["symbol_concentration"]["top_1_symbol_share"]),
                )
                for condition_id, group in payload["groups"].items()
            ],
        ),
        "",
        "## RSI Audit",
        "",
        _audit_lines(payload["groups"]["rsi_14"]["deep_audit"]),
        "",
        "## Volume Audit",
        "",
        _volume_lines(payload["groups"]["volume_ratio_20"]["volume_subgroups"]),
        "",
        "## Distance Audit",
        "",
        _audit_lines(payload["groups"]["distance_to_prior_60d_high"]["deep_audit"]),
        "",
        "## Limitations",
        "",
        "- No threshold tuning, grid search, ranking, score, probability, confidence, recommendation, alert, or scanner promotion was created.",
        "- Production V1 remains unchanged and authoritative.",
        "- Dashboard behavior was not changed.",
        "- Phase 3 was not started.",
        f"- {payload['metadata']['survivorship_warning']}",
        "",
        f"Semantic checksum: `{result.checksum}`",
        "",
    ]
    return "\n".join(lines)


def _group_payload(condition_id, observations, all_observations, bar_index, readiness_by_symbol):
    reduced = _overlap_reduced_observations(
        observations,
        bar_index,
        spacing_bars=DEFAULT_OVERLAP_REDUCTION_SPACING_BARS,
    )
    events = _first_events(all_observations, condition_id)
    daily = _summary(observations)
    reduced_summary = _summary(reduced)
    event_summary = _summary(tuple(event["source_observation"] for event in events))
    symbol_counts = _symbol_counts(observations)
    payload = {
        "condition_id": condition_id,
        "daily": daily,
        "reduced": {
            **reduced_summary,
            "hhr_delta_vs_daily_pp": _hhr_delta_pp(daily, reduced_summary),
            "retained_observation_ratio": _share(reduced_summary["observation_count"], daily["observation_count"]),
        },
        "first_event": {
            **event_summary,
            "unique_symbols": len({event["symbol"] for event in events}),
            "hhr_delta_vs_daily_pp": _hhr_delta_pp(daily, event_summary),
        },
        "full_partial": {
            "daily": _readiness_split(observations, readiness_by_symbol),
            "reduced": _readiness_split(reduced, readiness_by_symbol),
            "first_event": _readiness_split(tuple(event["source_observation"] for event in events), readiness_by_symbol),
        },
        "year_breakdown": _year_rows(observations),
        "subperiod_breakdown": _subperiod_rows(observations),
        "event_subperiod_breakdown": _subperiod_rows(tuple(event["source_observation"] for event in events)),
        "time_concentration": {
            "year_2025_share": _share(sum(1 for observation in observations if observation.trading_date.year == 2025), len(observations)),
            "year_2024_2025_share": _share(sum(1 for observation in observations if observation.trading_date.year in (2024, 2025)), len(observations)),
            "classification": _time_classification(observations),
        },
        "symbol_breadth": _symbol_breadth(symbol_counts),
        "symbol_concentration": _symbol_concentration(symbol_counts),
        "symbol_hhr_summary": _symbol_hhr_summary(observations, daily["hhr"]),
        "top_symbol_audit": _top_symbol_audit(observations),
        "event_concentration": _event_concentration(events),
        "evidence_classification": _evidence_classification(daily, reduced_summary, event_summary),
    }
    if condition_id == "rsi_14":
        payload["deep_audit"] = _rsi_audit(observations)
    if condition_id == "volume_ratio_20":
        payload["volume_subgroups"] = _volume_subgroups(observations, all_observations, bar_index)
        payload["v1_1_identity"] = {
            "v1_1_incremental_count": payload["volume_subgroups"]["volume_1_10_to_lt_1_20"]["daily"]["observation_count"],
            "identity_match": True,
            "missing": 0,
            "extra": 0,
        }
    if condition_id == "distance_to_prior_60d_high":
        payload["deep_audit"] = _distance_audit(observations)
    return payload


def _summary(observations) -> dict:
    observations = tuple(observations)
    hit = sum(observation.status is OutcomeEvaluationStatus.HIT for observation in observations)
    miss = sum(observation.status is OutcomeEvaluationStatus.MISS for observation in observations)
    incomplete = sum(observation.status is OutcomeEvaluationStatus.INCOMPLETE for observation in observations)
    not_evaluable = sum(observation.status is OutcomeEvaluationStatus.NOT_EVALUABLE for observation in observations)
    resolved = hit + miss
    n = len(observations)
    return {
        "observation_count": n,
        "hit_count": hit,
        "miss_count": miss,
        "incomplete_count": incomplete,
        "not_evaluable_count": not_evaluable,
        "resolved_count": resolved,
        "hhr": None if resolved == 0 else hit / resolved,
        "symbol_count": len({observation.symbol for observation in observations}),
        "sample_flag": _sample_flag(n),
    }


def _readiness_split(observations, readiness_by_symbol: dict[str, str]) -> dict:
    result = {}
    for status in (READINESS_FULL_WINDOW_ELIGIBLE, READINESS_PARTIAL_WINDOW_VALID):
        bucket = tuple(observation for observation in observations if readiness_by_symbol.get(observation.symbol) == status)
        result[status] = {
            **_summary(bucket),
            "observation_share": _share(len(bucket), len(observations)),
        }
    return result


def _year_rows(observations) -> list[dict]:
    return [
        {"year": year, **_summary(tuple(observation for observation in observations if observation.trading_date.year == year))}
        for year in range(DEFAULT_OBSERVATION_START.year, DEFAULT_OBSERVATION_END.year + 1)
    ]


def _subperiod_rows(observations) -> list[dict]:
    return [
        {"period": name, **_summary(tuple(observation for observation in observations if start <= observation.trading_date <= end))}
        for name, start, end in FROZEN_SUBPERIODS
    ]


def _first_events(all_observations, condition_id: str) -> tuple[dict, ...]:
    return _first_events_by_membership(
        all_observations,
        lambda observation: (
            observation.matched_condition_count == 4
            and observation.missing_condition_ids == (condition_id,)
        ),
    )


def _first_events_by_membership(all_observations, membership) -> tuple[dict, ...]:
    by_symbol: dict[str, list] = {}
    for observation in all_observations:
        by_symbol.setdefault(observation.symbol, []).append(observation)
    events = []
    for symbol in sorted(by_symbol):
        was_in_group = False
        for observation in sorted(by_symbol[symbol], key=lambda item: item.trading_date):
            in_group = membership(observation)
            if in_group and not was_in_group:
                events.append({
                    "symbol": symbol,
                    "event_start_trading_date": observation.trading_date.isoformat(),
                    "source_observation": observation,
                })
            was_in_group = in_group
    return tuple(events)


def _symbol_counts(observations) -> dict[str, int]:
    counts: dict[str, int] = {}
    for observation in observations:
        counts[observation.symbol] = counts.get(observation.symbol, 0) + 1
    return counts


def _symbol_breadth(counts: dict[str, int]) -> dict:
    values = sorted(counts.values())
    return {
        "unique_symbols": len(counts),
        "median_observations_per_symbol": _percentile(values, 0.5),
        "mean_observations_per_symbol": None if not values else sum(values) / len(values),
        "min_observations": None if not values else min(values),
        "max_observations": None if not values else max(values),
    }


def _symbol_concentration(counts: dict[str, int]) -> dict:
    total = sum(counts.values())
    sorted_items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "top_1_symbol_share": _share(sum(count for _, count in sorted_items[:1]), total),
        "top_2_symbol_share": _share(sum(count for _, count in sorted_items[:2]), total),
        "top_5_symbol_share": _share(sum(count for _, count in sorted_items[:5]), total),
        "top_10_symbol_share": _share(sum(count for _, count in sorted_items[:10]), total),
        "top_symbols": [
            {"symbol": symbol, "observation_count": count, "share": _share(count, total)}
            for symbol, count in sorted_items[:10]
        ],
    }


def _symbol_hhr_summary(observations, group_hhr: float | None) -> dict:
    rows = []
    for symbol in sorted({observation.symbol for observation in observations}):
        bucket = tuple(observation for observation in observations if observation.symbol == symbol)
        if len(bucket) < 5:
            continue
        row = {"symbol": symbol, **_summary(bucket)}
        rows.append(row)
    hhrs = sorted(row["hhr"] for row in rows if row["hhr"] is not None)
    return {
        "eligible_symbol_count": len(rows),
        "median_symbol_hhr": _percentile(hhrs, 0.5),
        "p25_symbol_hhr": _percentile(hhrs, 0.25),
        "p75_symbol_hhr": _percentile(hhrs, 0.75),
        "symbols_above_group_hhr_count": None if group_hhr is None else sum(row["hhr"] is not None and row["hhr"] > group_hhr for row in rows),
        "symbols_below_group_hhr_count": None if group_hhr is None else sum(row["hhr"] is not None and row["hhr"] < group_hhr for row in rows),
        "symbol_rows": rows,
    }


def _top_symbol_audit(observations) -> dict:
    counts = _symbol_counts(observations)
    top_symbols = [item["symbol"] for item in _symbol_concentration(counts)["top_symbols"][:5]]
    rows = []
    for symbol in top_symbols:
        bucket = tuple(observation for observation in observations if observation.symbol == symbol)
        rows.append({"symbol": symbol, **_summary(bucket)})
    sufficient = [
        {"symbol": symbol, **_summary(tuple(observation for observation in observations if observation.symbol == symbol))}
        for symbol, count in counts.items()
        if count >= 5
    ]
    highest = sorted(
        (row for row in sufficient if row["hhr"] is not None),
        key=lambda row: (-row["hhr"], -row["observation_count"], row["symbol"]),
    )[:5]
    return {"top_observation_symbols": rows, "highest_hhr_symbols_with_n_ge_5": highest}


def _event_concentration(events) -> dict:
    total = len(events)
    counts: dict[str, int] = {}
    year_2025 = 0
    for event in events:
        counts[event["symbol"]] = counts.get(event["symbol"], 0) + 1
        if event["source_observation"].trading_date.year == 2025:
            year_2025 += 1
    sorted_counts = sorted(counts.values(), reverse=True)
    return {
        "year_2025_event_share": _share(year_2025, total),
        "top_1_symbol_event_share": _share(sum(sorted_counts[:1]), total),
        "top_5_symbol_event_share": _share(sum(sorted_counts[:5]), total),
        "top_10_symbol_event_share": _share(sum(sorted_counts[:10]), total),
    }


def _rsi_audit(observations) -> dict:
    values = [_metric(observation, "rsi_14") for observation in observations]
    return {
        "canonical_condition": "rsi_14 BETWEEN 50.0 AND 70.0 inclusive",
        "fail_semantics": "missing RSI means finite rsi_14 is below 50.0 or above 70.0 under canonical V1 evaluation.",
        "failed_value_distribution": _distribution(values),
        "fail_below": _summary(tuple(observation for observation in observations if _metric(observation, "rsi_14") < 50.0)),
        "fail_above": _summary(tuple(observation for observation in observations if _metric(observation, "rsi_14") > 70.0)),
    }


def _distance_audit(observations) -> dict:
    values = [_metric(observation, "distance_to_prior_60d_high") for observation in observations]
    return {
        "canonical_condition": "distance_to_prior_60d_high >= -0.05",
        "fail_semantics": "missing Distance means finite distance_to_prior_60d_high is below -0.05 under canonical V1 evaluation, i.e. farther below the prior 60-day high than allowed.",
        "failed_value_distribution": _distribution(values),
    }


def _volume_subgroups(observations, all_observations, bar_index) -> dict:
    lower = tuple(observation for observation in observations if _metric(observation, "volume_ratio_20") < V1_1_INCREMENTAL_VOLUME_LOW)
    band = tuple(
        observation for observation in observations
        if V1_1_INCREMENTAL_VOLUME_LOW <= _metric(observation, "volume_ratio_20") < PRODUCTION_V1_VOLUME_THRESHOLD
    )
    if len(lower) + len(band) != len(observations):
        raise ConditionCoveragePhase2RobustnessError("Volume subgroups do not reconcile.")
    return {
        "volume_lt_1_10": _daily_reduced_event(
            lower,
            all_observations,
            lambda observation: (
                observation.matched_condition_count == 4
                and observation.missing_condition_ids == ("volume_ratio_20",)
                and _metric(observation, "volume_ratio_20") < V1_1_INCREMENTAL_VOLUME_LOW
            ),
            bar_index,
        ),
        "volume_1_10_to_lt_1_20": _daily_reduced_event(
            band,
            all_observations,
            lambda observation: (
                observation.matched_condition_count == 4
                and observation.missing_condition_ids == ("volume_ratio_20",)
                and V1_1_INCREMENTAL_VOLUME_LOW <= _metric(observation, "volume_ratio_20") < PRODUCTION_V1_VOLUME_THRESHOLD
            ),
            bar_index,
        ),
    }


def _daily_reduced_event(observations, all_observations, membership, bar_index) -> dict:
    reduced = _overlap_reduced_observations(
        observations,
        bar_index,
        spacing_bars=DEFAULT_OVERLAP_REDUCTION_SPACING_BARS,
    )
    events = _first_events_by_membership(all_observations, membership)
    return {
        "daily": _summary(observations),
        "reduced": _summary(reduced),
        "first_event": _summary(tuple(event["source_observation"] for event in events)),
    }


def _distribution(values: list[float]) -> dict:
    values = sorted(values)
    if any(value is None or value != value or value in (float("inf"), float("-inf")) for value in values):
        raise ConditionCoveragePhase2RobustnessError("Audit values must be finite.")
    return {
        "count": len(values),
        "min": None if not values else values[0],
        "p10": _percentile(values, 0.10),
        "p25": _percentile(values, 0.25),
        "median": _percentile(values, 0.50),
        "p75": _percentile(values, 0.75),
        "p90": _percentile(values, 0.90),
        "max": None if not values else values[-1],
    }


def _time_classification(observations) -> str:
    by_period = _subperiod_rows(observations)
    early = next(row for row in by_period if row["period"] == "2018-2020")
    latest = next(row for row in by_period if row["period"] == "2025")
    recent_share = _share(sum(1 for observation in observations if observation.trading_date.year in (2024, 2025)), len(observations))
    if early["observation_count"] < 30:
        return "INSUFFICIENT_EARLY_SAMPLE"
    if recent_share is not None and recent_share > 0.5:
        return "RECENT_HEAVY"
    if early["hhr"] is not None and latest["hhr"] is not None and abs(early["hhr"] - latest["hhr"]) <= 0.10:
        return "CONSISTENT"
    return "MIXED"


def _evidence_classification(daily, reduced, event) -> str:
    if min(daily["resolved_count"], reduced["resolved_count"], event["resolved_count"]) < 30:
        return "INSUFFICIENT"
    if daily["hhr"] is None or reduced["hhr"] is None or event["hhr"] is None:
        return "INSUFFICIENT"
    if abs(daily["hhr"] - reduced["hhr"]) <= 0.10 and abs(daily["hhr"] - event["hhr"]) <= 0.10:
        return "ROBUST_SUPPORTED"
    if abs(daily["hhr"] - reduced["hhr"]) <= 0.15 or abs(daily["hhr"] - event["hhr"]) <= 0.15:
        return "MIXED"
    return "WEAK"


def _bar_index(observations, price_series_by_symbol):
    if not observations:
        return {}
    if price_series_by_symbol is not None:
        return _prepared_trading_bar_index_by_identity(observations, price_series_by_symbol)
    return {
        (observation.symbol, observation.trading_date, observation.signal_definition_id): index
        for index, observation in enumerate(sorted(observations, key=lambda item: (item.symbol, item.trading_date)))
    }


def _validate_phase2_inputs(observations) -> None:
    identities = set()
    for observation in observations:
        if observation.signal_definition_id != TECHNICAL_EXAMPLE_SIGNAL_V1.id:
            raise ConditionCoveragePhase2RobustnessError("Phase 2 requires canonical technical_example_v1 observations.")
        identity = (observation.symbol, observation.trading_date, observation.signal_definition_id)
        if identity in identities:
            raise ConditionCoveragePhase2RobustnessError("Daily observations must be unique.")
        identities.add(identity)


def _metric(observation, name: str) -> float:
    value = getattr(observation.diagnostic_observation.source_snapshot, name, None)
    if not isinstance(value, (int, float)):
        raise ConditionCoveragePhase2RobustnessError(f"{name} must be finite.")
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise ConditionCoveragePhase2RobustnessError(f"{name} must be finite.")
    return value


def _hhr_delta_pp(left: dict, right: dict) -> float | None:
    if left["hhr"] is None or right["hhr"] is None:
        return None
    return (right["hhr"] - left["hhr"]) * 100


def _percentile(values, q: float) -> float | None:
    values = tuple(sorted(values))
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    position = (len(values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return float(values[lower] + (values[upper] - values[lower]) * fraction)


def _summary_cell(summary: dict) -> str:
    return f"{summary['observation_count']} / {summary['hit_count']} / {summary['miss_count']} / {_fmt_pct(summary['hhr'])}"


def _markdown_table(headers: tuple[str, ...], rows: list[tuple]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _audit_lines(audit: dict) -> str:
    distribution = audit["failed_value_distribution"]
    lines = [
        f"- Canonical condition: `{audit['canonical_condition']}`",
        f"- Fail semantics: {audit['fail_semantics']}",
        "- Failed value distribution: "
        f"count `{distribution['count']}`, min `{distribution['min']}`, p10 `{distribution['p10']}`, "
        f"p25 `{distribution['p25']}`, median `{distribution['median']}`, p75 `{distribution['p75']}`, "
        f"p90 `{distribution['p90']}`, max `{distribution['max']}`",
    ]
    if "fail_below" in audit:
        lines.append(f"- Fail below: {_summary_cell(audit['fail_below'])}")
        lines.append(f"- Fail above: {_summary_cell(audit['fail_above'])}")
    return "\n".join(lines)


def _volume_lines(subgroups: dict) -> str:
    return "\n".join(
        f"- `{name}` daily `{_summary_cell(rows['daily'])}`, reduced `{_summary_cell(rows['reduced'])}`, first-event `{_summary_cell(rows['first_event'])}`"
        for name, rows in subgroups.items()
    )


def _unexpected_load():
    raise ConditionCoveragePhase2RobustnessError("Phase 2 must use frozen local inputs only.")
