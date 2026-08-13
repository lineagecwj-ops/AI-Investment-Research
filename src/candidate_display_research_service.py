from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import fields
from datetime import UTC
from datetime import datetime
from enum import Enum
import hashlib
import json
from pathlib import Path

from database import DEFAULT_DB_PATH
from expanded_volume_threshold_validation_service import _materialized_twse_common_stock_symbols
from expanded_volume_threshold_validation_service import load_historical_price_series_read_only
from models import OverlappingSignalPolicy
from models import SignalEvaluationStatus
from research_data_store import ResearchDataStore
from scanner_condition_coverage_outcome_research_service import database_safety_audit
from scanner_condition_coverage_service import ScannerConditionCoverageResult
from scanner_condition_coverage_service import ScannerConditionCoverageSummary
from signal_condition_diagnostics_service import condition_diagnostic_id
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from swing_scanner_service import SwingScannerConfig
from swing_scanner_service import SwingScannerResult
from swing_scanner_service import SwingScannerService


PHASE1_RESEARCH_CHECKSUM = "b58f00ebf9cac16c1ce5bed3720b3eb7036ff456bb2d28862ffccd66c8e02632"
PHASE2_ROBUSTNESS_CHECKSUM = "71c69eda6b743b195a531c67c9517b84b8a7b0fb19aa5263e97fec8ab891c704"

PHASE1_RESEARCH_OUTPUT_PATH = Path("docs/research_outputs/scanner_condition_coverage_outcomes_2018_2025.json")
PHASE2_RESEARCH_OUTPUT_PATH = Path("docs/research_outputs/scanner_condition_coverage_phase2_robustness_2018_2025.json")
DEFAULT_PHASE3_OUTPUT_PATH = Path("docs/research_outputs/candidate_display_phase3_research.json")


class CandidateDisplayClassification(Enum):

    FORMAL_V1 = "FORMAL_V1"
    RESEARCH_PRIORITY_A = "RESEARCH_PRIORITY_A"
    RESEARCH_PRIORITY_B = "RESEARCH_PRIORITY_B"
    RESEARCH_WATCH = "RESEARCH_WATCH"
    EXPLORATORY = "EXPLORATORY"
    BELOW_DISPLAY_SCOPE = "BELOW_DISPLAY_SCOPE"


class EvidenceClassification(Enum):

    DISPLAY_DESIGN_SUPPORTED = "DISPLAY_DESIGN_SUPPORTED"
    MIXED = "MIXED"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class CandidateDisplayEvidenceReference:

    phase1_checksum: str

    phase2_checksum: str | None

    group_id: str

    daily_hhr: float | None = None

    reduced_hhr: float | None = None

    first_event_hhr: float | None = None

    full_window_hhr: float | None = None

    partial_window_hhr: float | None = None

    source_note: str = "historical group HHR metadata only; not individual stock probability"


@dataclass(frozen=True)
class CandidateDisplayResearchResult:

    symbol: str

    as_of_date: object

    production_definition_id: str

    coverage_count: int

    missing_condition_ids: tuple[str, ...]

    display_classification: CandidateDisplayClassification

    formal_v1_qualified: bool

    v1_1_experimental_match: bool

    evidence_reference: CandidateDisplayEvidenceReference

    evidence_classification: EvidenceClassification

    display_reason_code: str


@dataclass(frozen=True)
class CandidateDisplayCountReconciliation:

    evaluated_symbol_count: int

    formal_v1_count: int

    research_priority_a_count: int

    research_priority_b_count: int

    research_watch_count: int

    other_4of5_exploratory_count: int

    three_of_five_exploratory_count: int

    below_display_scope_count: int

    reconciled: bool


@dataclass(frozen=True)
class CandidateDisplayResearchSummary:

    generated_at: datetime

    results: tuple[CandidateDisplayResearchResult, ...]

    count_reconciliation: CandidateDisplayCountReconciliation

    semantic_checksum: str


class CandidateDisplayResearchError(Exception):
    """Raised when Phase 3 candidate display projection violates its research-only contract."""


def build_candidate_display_research_summary(
    coverage_summary: ScannerConditionCoverageSummary,
    *,
    generated_at: datetime | None = None,
) -> CandidateDisplayResearchSummary:
    _validate_locked_evidence()
    _validate_formal_identity_from_coverage(coverage_summary)
    results = tuple(
        build_candidate_display_research_result(result)
        for result in coverage_summary.results
    )
    results = tuple(sorted(results, key=lambda item: _symbol_sort_key(item.symbol)))
    reconciliation = _count_reconciliation(results)
    payload = _summary_payload(
        generated_at=generated_at or datetime.now(UTC),
        results=results,
        count_reconciliation=reconciliation,
        semantic_checksum=None,
    )
    checksum = _payload_checksum(_semantic_payload(payload))
    return CandidateDisplayResearchSummary(
        generated_at=generated_at or datetime.now(UTC),
        results=results,
        count_reconciliation=reconciliation,
        semantic_checksum=checksum,
    )


def build_candidate_display_research_result(
    coverage_result: ScannerConditionCoverageResult,
) -> CandidateDisplayResearchResult:
    classification, reason_code = _classification_and_reason(coverage_result)
    formal_v1_qualified = classification is CandidateDisplayClassification.FORMAL_V1
    if formal_v1_qualified != coverage_result.formal_v1_qualified:
        raise CandidateDisplayResearchError("FORMAL_V1 must remain exactly equivalent to Production V1 5/5.")
    if classification is not CandidateDisplayClassification.FORMAL_V1 and coverage_result.formal_v1_qualified:
        raise CandidateDisplayResearchError("Non-formal Phase 3 classes must not promote Production V1 hits.")
    return CandidateDisplayResearchResult(
        symbol=coverage_result.symbol,
        as_of_date=coverage_result.as_of_date,
        production_definition_id=coverage_result.production_definition_id,
        coverage_count=coverage_result.matched_condition_count,
        missing_condition_ids=coverage_result.missing_condition_ids,
        display_classification=classification,
        formal_v1_qualified=formal_v1_qualified,
        v1_1_experimental_match=(
            classification is CandidateDisplayClassification.RESEARCH_PRIORITY_B
            and coverage_result.v1_1_experimental_match
        ),
        evidence_reference=_evidence_reference(classification, coverage_result.missing_condition_ids),
        evidence_classification=_evidence_classification(classification),
        display_reason_code=reason_code,
    )


def run_live_candidate_display_research_projection(
    *,
    db_path: Path | str | None = None,
    research_store: ResearchDataStore | None = None,
    generated_at: datetime | None = None,
) -> tuple[CandidateDisplayResearchSummary, SwingScannerResult]:
    store = research_store or (ResearchDataStore() if db_path is None else ResearchDataStore(db_path=db_path))
    resolved_db_path = store.resolved_db_path
    before = database_safety_audit(resolved_db_path, research_store=store)
    symbols = store.materialized_twse_common_stock_symbols()
    if len(symbols) != 218:
        raise CandidateDisplayResearchError(f"Frozen TWSE live projection requires 218 symbols; got {len(symbols)}.")
    service = SwingScannerService(
        price_loader=lambda symbol, **_kwargs: load_historical_price_series_read_only(
            symbol,
            db_path=resolved_db_path,
            research_store=store,
        ),
    )
    scanner_result = service.scan(
        symbols,
        SwingScannerConfig(
            signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
            outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
            overlap_policy=OverlappingSignalPolicy.ALLOW_ALL,
            minimum_resolved_samples=20,
            force_refresh=False,
        ),
    )
    if scanner_result.failed_symbols or scanner_result.not_evaluable_symbols:
        raise CandidateDisplayResearchError("Live projection requires all 218 symbols to be evaluable without failures.")
    from scanner_condition_coverage_service import build_scanner_condition_coverage_summary

    coverage_summary = build_scanner_condition_coverage_summary(
        scanner_result,
        production_signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
    )
    summary = build_candidate_display_research_summary(
        coverage_summary,
        generated_at=generated_at,
    )
    after = database_safety_audit(resolved_db_path, research_store=store)
    if asdict(before) != asdict(after):
        raise CandidateDisplayResearchError("Read-only live projection changed database safety audit values.")
    return summary, scanner_result


def build_candidate_display_phase3_payload(
    summary: CandidateDisplayResearchSummary,
    *,
    db_audit_before,
    db_audit_after,
    scanner_result: SwingScannerResult | None = None,
) -> dict:
    payload = _summary_payload(
        generated_at=summary.generated_at,
        results=summary.results,
        count_reconciliation=summary.count_reconciliation,
        semantic_checksum=summary.semantic_checksum,
    )
    payload["metadata"] = {
        "phase": "Candidate Display Research Phase 3",
        "purpose": "research-only candidate display classification",
        "production_definition_id": TECHNICAL_EXAMPLE_SIGNAL_V1.id,
        "phase1_checksum": PHASE1_RESEARCH_CHECKSUM,
        "phase2_checksum": PHASE2_ROBUSTNESS_CHECKSUM,
        "evidence_classification": EvidenceClassification.DISPLAY_DESIGN_SUPPORTED.value,
        "db_write_performed": False,
        "network_fetch_performed": False,
        "dashboard_changed": False,
        "scanner_changed": False,
        "ranking_created": False,
        "score_created": False,
        "recommendation_created": False,
        "survivorship_warning": (
            "Frozen 2026 current ETF constituent-derived universe is not a historical point-in-time universe; "
            "survivorship bias and constituent look-back bias remain."
        ),
        "post_hoc_warning": (
            "Priority A/B/Watch are post-hoc display categories selected from historical research; "
            "they are not prospectively validated ranking."
        ),
    }
    payload["classification_rules"] = classification_rules_payload()
    payload["db_audit_before"] = asdict(db_audit_before)
    payload["db_audit_after"] = asdict(db_audit_after)
    if scanner_result is not None:
        payload["scanner_control"] = {
            "production_hit_symbols": tuple(candidate.symbol for candidate in scanner_result.matched_candidates),
            "production_order_preserved": True,
            "scanner_default_changed": False,
        }
    return payload


def write_candidate_display_phase3_payload(
    payload: dict,
    *,
    output_path: Path | str = DEFAULT_PHASE3_OUTPUT_PATH,
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def classification_rules_payload() -> tuple[dict[str, object], ...]:
    return (
        {
            "display_classification": "FORMAL_V1",
            "rule": "coverage = 5/5",
            "reason_code": "FORMAL_V1_5_OF_5",
        },
        {
            "display_classification": "RESEARCH_PRIORITY_A",
            "rule": "coverage = exactly 4/5 and only missing rsi_14",
            "reason_code": "FOUR_OF_FIVE_MISSING_RSI",
        },
        {
            "display_classification": "RESEARCH_PRIORITY_B",
            "rule": "coverage = exactly 4/5 and only missing volume_ratio_20",
            "reason_code": "FOUR_OF_FIVE_MISSING_VOLUME",
        },
        {
            "display_classification": "RESEARCH_WATCH",
            "rule": "coverage = exactly 4/5 and only missing distance_to_prior_60d_high",
            "reason_code": "FOUR_OF_FIVE_MISSING_DISTANCE",
        },
        {
            "display_classification": "EXPLORATORY",
            "rule": "coverage = exactly 4/5 missing sma_20_vs_sma_60 or analysis_close_vs_sma_20, or coverage = 3/5",
            "reason_code": "FOUR_OF_FIVE_OTHER or THREE_OF_FIVE_EXPLORATORY",
        },
        {
            "display_classification": "BELOW_DISPLAY_SCOPE",
            "rule": "coverage = 0/5, 1/5, or 2/5",
            "reason_code": "BELOW_THREE_OF_FIVE",
        },
    )


def live_symbol_lists(summary: CandidateDisplayResearchSummary) -> dict[str, tuple[str, ...]]:
    return {
        "FORMAL_V1": _symbols_for(summary, CandidateDisplayClassification.FORMAL_V1),
        "RESEARCH_PRIORITY_A": _symbols_for(summary, CandidateDisplayClassification.RESEARCH_PRIORITY_A),
        "RESEARCH_PRIORITY_B": _symbols_for(summary, CandidateDisplayClassification.RESEARCH_PRIORITY_B),
        "RESEARCH_PRIORITY_B_V1_1_BADGE": tuple(
            result.symbol
            for result in summary.results
            if result.display_classification is CandidateDisplayClassification.RESEARCH_PRIORITY_B
            and result.v1_1_experimental_match
        ),
        "RESEARCH_WATCH": _symbols_for(summary, CandidateDisplayClassification.RESEARCH_WATCH),
        "OTHER_4OF5_EXPLORATORY": tuple(
            result.symbol
            for result in summary.results
            if result.display_classification is CandidateDisplayClassification.EXPLORATORY
            and result.coverage_count == 4
        ),
    }


def assert_no_forbidden_result_fields() -> None:
    forbidden_fragments = ("score", "rank", "probability", "confidence", "recommendation", "expected_return", "buy", "sell")
    field_names = {field.name for field in fields(CandidateDisplayResearchResult)}
    violations = sorted(
        name
        for name in field_names
        if any(fragment in name for fragment in forbidden_fragments)
    )
    if violations:
        raise CandidateDisplayResearchError("Forbidden Phase 3 result fields: " + ", ".join(violations))


def _classification_and_reason(
    coverage_result: ScannerConditionCoverageResult,
) -> tuple[CandidateDisplayClassification, str]:
    coverage = coverage_result.matched_condition_count
    missing = coverage_result.missing_condition_ids
    if coverage == 5:
        return CandidateDisplayClassification.FORMAL_V1, "FORMAL_V1_5_OF_5"
    if coverage == 4:
        if missing == ("rsi_14",):
            return CandidateDisplayClassification.RESEARCH_PRIORITY_A, "FOUR_OF_FIVE_MISSING_RSI"
        if missing == ("volume_ratio_20",):
            return CandidateDisplayClassification.RESEARCH_PRIORITY_B, "FOUR_OF_FIVE_MISSING_VOLUME"
        if missing == ("distance_to_prior_60d_high",):
            return CandidateDisplayClassification.RESEARCH_WATCH, "FOUR_OF_FIVE_MISSING_DISTANCE"
        return CandidateDisplayClassification.EXPLORATORY, "FOUR_OF_FIVE_OTHER"
    if coverage == 3:
        return CandidateDisplayClassification.EXPLORATORY, "THREE_OF_FIVE_EXPLORATORY"
    return CandidateDisplayClassification.BELOW_DISPLAY_SCOPE, "BELOW_THREE_OF_FIVE"


def _evidence_reference(
    classification: CandidateDisplayClassification,
    missing_condition_ids: tuple[str, ...],
) -> CandidateDisplayEvidenceReference:
    if classification is CandidateDisplayClassification.RESEARCH_PRIORITY_A:
        return CandidateDisplayEvidenceReference(
            phase1_checksum=PHASE1_RESEARCH_CHECKSUM,
            phase2_checksum=PHASE2_ROBUSTNESS_CHECKSUM,
            group_id="MISSING_rsi_14",
            daily_hhr=0.9713,
            reduced_hhr=0.9803,
            first_event_hhr=0.9755,
            full_window_hhr=0.9704,
            partial_window_hhr=0.9778,
        )
    if classification is CandidateDisplayClassification.RESEARCH_PRIORITY_B:
        return CandidateDisplayEvidenceReference(
            phase1_checksum=PHASE1_RESEARCH_CHECKSUM,
            phase2_checksum=PHASE2_ROBUSTNESS_CHECKSUM,
            group_id="MISSING_volume_ratio_20",
            daily_hhr=0.7551,
            reduced_hhr=0.7802,
            first_event_hhr=0.7692,
        )
    if classification is CandidateDisplayClassification.RESEARCH_WATCH:
        return CandidateDisplayEvidenceReference(
            phase1_checksum=PHASE1_RESEARCH_CHECKSUM,
            phase2_checksum=PHASE2_ROBUSTNESS_CHECKSUM,
            group_id="MISSING_distance_to_prior_60d_high",
            daily_hhr=0.6232,
            reduced_hhr=0.5809,
            first_event_hhr=0.6180,
        )
    group_id = "NONE" if not missing_condition_ids else "MISSING_" + "+".join(missing_condition_ids)
    return CandidateDisplayEvidenceReference(
        phase1_checksum=PHASE1_RESEARCH_CHECKSUM,
        phase2_checksum=PHASE2_ROBUSTNESS_CHECKSUM,
        group_id=group_id,
    )


def _evidence_classification(
    classification: CandidateDisplayClassification,
) -> EvidenceClassification:
    if classification in {
        CandidateDisplayClassification.FORMAL_V1,
        CandidateDisplayClassification.RESEARCH_PRIORITY_A,
        CandidateDisplayClassification.RESEARCH_PRIORITY_B,
        CandidateDisplayClassification.RESEARCH_WATCH,
    }:
        return EvidenceClassification.DISPLAY_DESIGN_SUPPORTED
    if classification is CandidateDisplayClassification.EXPLORATORY:
        return EvidenceClassification.MIXED
    return EvidenceClassification.INSUFFICIENT


def _count_reconciliation(
    results: tuple[CandidateDisplayResearchResult, ...],
) -> CandidateDisplayCountReconciliation:
    formal = _count(results, CandidateDisplayClassification.FORMAL_V1)
    priority_a = _count(results, CandidateDisplayClassification.RESEARCH_PRIORITY_A)
    priority_b = _count(results, CandidateDisplayClassification.RESEARCH_PRIORITY_B)
    watch = _count(results, CandidateDisplayClassification.RESEARCH_WATCH)
    other_4 = sum(
        result.display_classification is CandidateDisplayClassification.EXPLORATORY
        and result.coverage_count == 4
        for result in results
    )
    three = sum(
        result.display_classification is CandidateDisplayClassification.EXPLORATORY
        and result.coverage_count == 3
        for result in results
    )
    below = _count(results, CandidateDisplayClassification.BELOW_DISPLAY_SCOPE)
    total = formal + priority_a + priority_b + watch + other_4 + three + below
    return CandidateDisplayCountReconciliation(
        evaluated_symbol_count=len(results),
        formal_v1_count=formal,
        research_priority_a_count=priority_a,
        research_priority_b_count=priority_b,
        research_watch_count=watch,
        other_4of5_exploratory_count=other_4,
        three_of_five_exploratory_count=three,
        below_display_scope_count=below,
        reconciled=total == len(results),
    )


def _summary_payload(
    *,
    generated_at: datetime,
    results: tuple[CandidateDisplayResearchResult, ...],
    count_reconciliation: CandidateDisplayCountReconciliation,
    semantic_checksum: str | None,
) -> dict:
    return {
        "generated_at": generated_at.isoformat(),
        "semantic_checksum": semantic_checksum,
        "count_reconciliation": asdict(count_reconciliation),
        "live_local_projection": [_result_payload(result) for result in results],
        "evidence_references": _evidence_reference_payload(),
        "limitations": (
            "Research-only display projection; not Production V1 promotion.",
            "No ranking, score, confidence, recommendation, alert, buy/sell language, or expected return is created.",
            "Historical group HHR is explanatory metadata only and must not be shown as individual stock probability.",
            "Frozen 2026 current ETF constituent-derived universe is not a historical point-in-time universe.",
        ),
    }


def _result_payload(result: CandidateDisplayResearchResult) -> dict:
    payload = asdict(result)
    payload["as_of_date"] = result.as_of_date.isoformat() if hasattr(result.as_of_date, "isoformat") else result.as_of_date
    payload["display_classification"] = result.display_classification.value
    payload["evidence_classification"] = result.evidence_classification.value
    return payload


def _evidence_reference_payload() -> dict[str, dict[str, object]]:
    references = {}
    for classification in CandidateDisplayClassification:
        reference = _evidence_reference(classification, tuple())
        references[classification.value] = asdict(reference)
    return references


def _semantic_payload(payload: dict) -> dict:
    stable = dict(payload)
    stable.pop("generated_at", None)
    stable["semantic_checksum"] = None
    return stable


def _payload_checksum(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_locked_evidence() -> None:
    phase1 = _load_json(PHASE1_RESEARCH_OUTPUT_PATH)
    phase2 = _load_json(PHASE2_RESEARCH_OUTPUT_PATH)
    if phase1.get("checksum") != PHASE1_RESEARCH_CHECKSUM:
        raise CandidateDisplayResearchError("Phase 1 checksum input is not the locked checksum.")
    if phase2.get("semantic_checksum") != PHASE2_ROBUSTNESS_CHECKSUM:
        raise CandidateDisplayResearchError("Phase 2 checksum input is not the locked checksum.")


def _validate_formal_identity_from_coverage(
    coverage_summary: ScannerConditionCoverageSummary,
) -> None:
    formal = tuple(result.symbol for result in coverage_summary.results if result.formal_v1_qualified)
    if tuple(sorted(formal, key=_symbol_sort_key)) != coverage_summary.formal_v1_match_symbols:
        raise CandidateDisplayResearchError("FORMAL_V1 identity must equal Condition Coverage 5/5 symbols.")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _symbols_for(
    summary: CandidateDisplayResearchSummary,
    classification: CandidateDisplayClassification,
) -> tuple[str, ...]:
    return tuple(result.symbol for result in summary.results if result.display_classification is classification)


def _count(
    results: tuple[CandidateDisplayResearchResult, ...],
    classification: CandidateDisplayClassification,
) -> int:
    return sum(result.display_classification is classification for result in results)


def _symbol_sort_key(symbol: str) -> tuple[int, int | str, str]:
    code = symbol.split(".", 1)[0]
    if code.isdigit():
        return (0, int(code), symbol)
    return (1, code, symbol)
