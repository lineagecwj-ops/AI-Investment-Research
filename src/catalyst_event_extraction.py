"""Offline deterministic extraction of source-linked Catalyst event evidence."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from hashlib import sha256
import re

from catalyst_identity_catalog import TaiwanListedCompanyIdentityCatalog
from catalyst_identity_catalog import load_default_identity_catalog
from catalyst_event import CandidateStatus
from catalyst_event import CatalystEventType
from catalyst_event import EventCandidate
from catalyst_event import EventConflictStatus
from catalyst_event import EventTemporalStatus
from catalyst_event import EventValidationStatus
from catalyst_event import ExtractionBasis
from catalyst_event import ValidatedCatalystEvent
from external_source import CompanyAssociationStatus
from external_source import ExternalSourceRef
from external_source import ResearchWindowStatus
from external_source import SourceStatus
from external_source import SourceTemporalEvidence
from external_source import SourceTier
from external_source import TemporalKind
from external_source import validate_research_window


EventResearchWindow = tuple[date, date]

_DATE_BLOCK = re.compile(
    r"(?:(?:日\s*期|日期|事實發生日|董事會決議日期)\s*[：:]?\s*)?"
    r"(?P<year>20\d{2})\s*(?:年|[-/])\s*(?P<month>\d{1,2})\s*(?:月|[-/])\s*(?P<day>\d{1,2})\s*(?:日)?"
)
_EVENT_MARKERS = re.compile(
    r"財務報告|財報|季報|半年報|合併營收|月營收|法說會|投資人說明會|董事會|"
    r"綜合損益表|增資|投資|取得|股權|擴建|新廠|股利|配息|庫藏股|重大訊息",
    re.IGNORECASE,
)
_PAGE_CHROME_MARKERS = (
    "更新", "成交量", "本益比", "同業平均", "走勢圖", "技術分析", "成交彙整",
    "籌碼", "法人買賣", "主力進出", "資券變化", "股價", "開盤", "最高", "最低", "收盤",
)
_WHITESPACE = re.compile(r"\s+")
_NON_SUBJECT = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)
_MONTH_IN_TEXT = re.compile(
    r"(?<!\d)(?P<month>\d{1,2})\s*月|\b(?P<english_month>january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE,
)
_REPORTING_PERIOD = re.compile(
    r"\b(?P<quarter>q[1-4])\b|\b(?P<half>h[12])\b|(?P<chinese_quarter>第[一二三四1234]季)|(?P<chinese_half>上半年|下半年)",
    re.IGNORECASE,
)
_STRUCTURED_SUBJECT = re.compile(
    r"(?:(?:公告\s*)?主\s*旨|標題)\s*[：:]\s*(?P<subject>[^\n。；;]{1,240})",
    re.IGNORECASE,
)
_STRUCTURED_STOCK_CODE = re.compile(r"(?:股票代號|股票代碼)\s*[：:]\s*(?P<code>\d{4})(?!\d)")
_NAMED_STOCK_CODE = re.compile(
    r"(?P<name>[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z .&-]{0,40})\s*[（(]\s*(?P<code>\d{4})\s*[）)]"
)
_ENGLISH_MONTH_NUMBERS = {
    "january": "1", "february": "2", "march": "3", "april": "4", "may": "5", "june": "6",
    "july": "7", "august": "8", "september": "9", "october": "10", "november": "11", "december": "12",
}


class CatalystEventExtractionError(ValueError):
    """Raised when supplied source evidence cannot be safely extracted."""


def extract_event_candidates(
    sources: Iterable[ExternalSourceRef],
    *,
    target_symbol: str,
    target_company_name: str,
    validated_aliases: tuple[str, ...] = (),
    research_window: EventResearchWindow,
    identity_catalog: TaiwanListedCompanyIdentityCatalog | None = None,
) -> tuple[EventCandidate, ...]:
    """Create source-local candidates without network, AI, persistence, or mutation."""
    _validate_window(research_window)
    catalog = identity_catalog or load_default_identity_catalog()
    unique_sources = {source.source_id: source for source in sources}
    candidates: list[EventCandidate] = []
    for source in sorted(unique_sources.values(), key=lambda item: item.source_id):
        _validate_source_target(source, target_symbol, target_company_name)
        candidates.extend(_extract_source_candidates(source, validated_aliases, catalog))
    return tuple(sorted(candidates, key=lambda item: item.candidate_id))


def validate_event_candidate(
    candidate: EventCandidate,
    *,
    source: ExternalSourceRef,
    research_window: EventResearchWindow,
) -> EventValidationStatus:
    """Apply program-owned source, identity, tier, and temporal gates."""
    _validate_window(research_window)
    if candidate.source_id != source.source_id:
        raise CatalystEventExtractionError("Candidate source_id does not match supplied source.")
    if candidate.candidate_status is CandidateStatus.BACKGROUND_ONLY:
        return EventValidationStatus.BACKGROUND_ONLY
    if source.source_status is not SourceStatus.ACCEPTED:
        return EventValidationStatus.REJECTED
    if candidate.company_association_status in {
        CompanyAssociationStatus.AMBIGUOUS,
        CompanyAssociationStatus.UNRELATED,
        CompanyAssociationStatus.UNKNOWN,
    }:
        return EventValidationStatus.REJECTED
    if candidate.company_association_status is CompanyAssociationStatus.RELATED_ENTITY:
        return EventValidationStatus.PARTIALLY_VALIDATED
    if candidate.source_tier not in {SourceTier.TIER_1_OFFICIAL, SourceTier.TIER_2_ESTABLISHED_MEDIA}:
        return EventValidationStatus.PARTIALLY_VALIDATED
    evidence = _confirmed_event_time(candidate.temporal_evidence, research_window)
    return EventValidationStatus.VALIDATED if evidence is not None else EventValidationStatus.PARTIALLY_VALIDATED


def cluster_validated_events(
    candidates: Iterable[EventCandidate],
    *,
    sources: Iterable[ExternalSourceRef],
    research_window: EventResearchWindow,
) -> tuple[ValidatedCatalystEvent, ...]:
    """Cluster deterministic candidates; output statuses retain incomplete evidence explicitly."""
    _validate_window(research_window)
    source_by_id = {source.source_id: source for source in sources}
    groups: dict[tuple[str, str, str, str], list[EventCandidate]] = {}
    for candidate in candidates:
        if candidate.source_id not in source_by_id:
            raise CatalystEventExtractionError(f"Candidate references unavailable source: {candidate.source_id}")
        groups.setdefault(_cluster_identity(candidate), []).append(candidate)

    events = [
        _build_event(group, source_by_id, research_window)
        for _, group in sorted(groups.items(), key=lambda item: item[0])
    ]
    return tuple(sorted(events, key=lambda item: item.event_id))


def _extract_source_candidates(
    source: ExternalSourceRef,
    validated_aliases: tuple[str, ...],
    identity_catalog: TaiwanListedCompanyIdentityCatalog,
) -> list[EventCandidate]:
    text = _source_local_text(source)
    if not text:
        return []
    matches = list(_DATE_BLOCK.finditer(text))
    if matches:
        return [
            _candidate_from_date_span(
                source,
                text,
                match.start(),
                matches[index + 1].start() if index + 1 < len(matches) else len(text),
                ExtractionBasis.STRUCTURED_DATE_BLOCK,
                _matching_temporal_evidence(source, match.group(0)),
                validated_aliases,
                identity_catalog,
            )
            for index, match in enumerate(matches)
        ]
    if _EVENT_MARKERS.search(text):
        return [_candidate_from_span(
            source, text, 0, len(text), ExtractionBasis.TITLE_OR_EXCERPT_FALLBACK, (), validated_aliases, identity_catalog,
        )]
    return [_background_candidate(source, text, identity_catalog=identity_catalog)]


def _candidate_from_date_span(
    source: ExternalSourceRef,
    text: str,
    start: int,
    end: int,
    basis: ExtractionBasis,
    temporal_evidence: tuple[SourceTemporalEvidence, ...],
    validated_aliases: tuple[str, ...],
    identity_catalog: TaiwanListedCompanyIdentityCatalog,
) -> EventCandidate:
    """Reject page chrome as a date source before it reaches event validation."""
    if _is_page_chrome_span(text, start, end):
        return _background_candidate(
            source,
            text,
            start=start,
            end=end,
            validated_aliases=validated_aliases,
            identity_catalog=identity_catalog,
        )
    return _candidate_from_span(source, text, start, end, basis, temporal_evidence, validated_aliases, identity_catalog)


def _candidate_from_span(
    source: ExternalSourceRef,
    text: str,
    start: int,
    end: int,
    basis: ExtractionBasis,
    temporal_evidence: tuple[SourceTemporalEvidence, ...],
    validated_aliases: tuple[str, ...],
    identity_catalog: TaiwanListedCompanyIdentityCatalog,
) -> EventCandidate:
    anchor, local_start, local_end = _bounded_anchor(text, start, end)
    association = _candidate_association(source, anchor, validated_aliases, identity_catalog)
    event_type = _classify_event_type(anchor)
    candidate_key = _candidate_key(source.source_id, local_start, local_end, event_type, anchor)
    return EventCandidate(
        candidate_id="catalyst_candidate_" + _digest(candidate_key),
        source_id=source.source_id,
        target_symbol=source.target_symbol,
        target_company_name=source.target_company_name,
        candidate_anchor=anchor,
        candidate_start=local_start,
        candidate_end=local_end,
        candidate_type=event_type,
        temporal_evidence=temporal_evidence,
        company_association_status=association,
        source_tier=source.source_tier,
        candidate_status=CandidateStatus.EVENT_LIKE,
        extraction_basis=basis,
        candidate_key=candidate_key,
    )


def _background_candidate(
    source: ExternalSourceRef,
    text: str,
    *,
    start: int = 0,
    end: int | None = None,
    validated_aliases: tuple[str, ...] = (),
    identity_catalog: TaiwanListedCompanyIdentityCatalog | None = None,
) -> EventCandidate:
    anchor, start, end = _bounded_anchor(text, start, len(text) if end is None else end)
    association = _candidate_association(
        source,
        anchor,
        validated_aliases,
        identity_catalog or load_default_identity_catalog(),
    )
    candidate_key = _candidate_key(source.source_id, start, end, CatalystEventType.OTHER, anchor)
    return EventCandidate(
        candidate_id="catalyst_candidate_" + _digest(candidate_key),
        source_id=source.source_id,
        target_symbol=source.target_symbol,
        target_company_name=source.target_company_name,
        candidate_anchor=anchor,
        candidate_start=start,
        candidate_end=end,
        candidate_type=CatalystEventType.OTHER,
        temporal_evidence=(),
        company_association_status=association,
        source_tier=source.source_tier,
        candidate_status=CandidateStatus.BACKGROUND_ONLY,
        extraction_basis=ExtractionBasis.TITLE_OR_EXCERPT_FALLBACK,
        candidate_key=candidate_key,
    )


def _build_event(
    candidates: list[EventCandidate],
    source_by_id: dict[str, ExternalSourceRef],
    research_window: EventResearchWindow,
) -> ValidatedCatalystEvent:
    ordered = tuple(sorted(candidates, key=lambda item: item.candidate_id))
    source_ids = tuple(sorted({item.source_id for item in ordered}))
    sources = [source_by_id[item] for item in source_ids]
    statuses = [validate_event_candidate(item, source=source_by_id[item.source_id], research_window=research_window) for item in ordered]
    conflict = _conflict_status(ordered, research_window)
    temporal = _cluster_temporal_evidence(ordered, research_window)
    validation = _cluster_validation_status(ordered, statuses, temporal, conflict)
    primary_source_id = _primary_source_id(sources)
    event_type = ordered[0].candidate_type
    subject = _subject_key(ordered[0].candidate_anchor, event_type)
    temporal_key = temporal.value.isoformat() if temporal else "TIME_UNKNOWN"
    if conflict is EventConflictStatus.SOURCE_DATE:
        temporal_key = "CONFLICT_SOURCE_DATE"
    event_key = "|".join((ordered[0].target_symbol, event_type.value, temporal_key, subject))
    return ValidatedCatalystEvent(
        event_id="catalyst_event_" + _digest(event_key),
        target_symbol=ordered[0].target_symbol,
        target_company_name=ordered[0].target_company_name,
        event_type=event_type,
        event_fact=_event_fact(ordered, primary_source_id),
        event_temporal_evidence=temporal,
        event_temporal_status=_temporal_status(temporal, ordered),
        source_ids=source_ids,
        primary_source_id=primary_source_id,
        support_count=len(source_ids),
        event_key=event_key,
        candidate_ids=tuple(item.candidate_id for item in ordered),
        company_association_status=ordered[0].company_association_status,
        validation_status=validation,
        conflict_status=conflict,
    )


def _cluster_validation_status(
    candidates: tuple[EventCandidate, ...],
    statuses: list[EventValidationStatus],
    temporal: SourceTemporalEvidence | None,
    conflict: EventConflictStatus,
) -> EventValidationStatus:
    if all(item.candidate_status is CandidateStatus.BACKGROUND_ONLY for item in candidates):
        return EventValidationStatus.BACKGROUND_ONLY
    if conflict is not EventConflictStatus.NONE:
        return EventValidationStatus.REJECTED
    if EventValidationStatus.VALIDATED in statuses and temporal is not None:
        return EventValidationStatus.VALIDATED
    if EventValidationStatus.REJECTED in statuses and len(set(statuses)) == 1:
        return EventValidationStatus.REJECTED
    return EventValidationStatus.PARTIALLY_VALIDATED


def _conflict_status(candidates: tuple[EventCandidate, ...], research_window: EventResearchWindow) -> EventConflictStatus:
    associations = {item.company_association_status for item in candidates}
    if len(associations) > 1:
        return EventConflictStatus.IDENTITY
    dates = {
        evidence.value.isoformat()
        for item in candidates
        for evidence in (_confirmed_event_time(item.temporal_evidence, research_window),)
        if evidence is not None
    }
    if len(dates) > 1:
        return EventConflictStatus.SOURCE_DATE
    return EventConflictStatus.NONE


def _cluster_temporal_evidence(
    candidates: tuple[EventCandidate, ...], research_window: EventResearchWindow
) -> SourceTemporalEvidence | None:
    exact = [
        evidence
        for item in candidates
        for evidence in (_confirmed_event_time(item.temporal_evidence, research_window),)
        if evidence is not None
    ]
    return sorted(exact, key=lambda item: item.value.isoformat())[0] if exact else None


def _temporal_status(
    temporal: SourceTemporalEvidence | None, candidates: tuple[EventCandidate, ...]
) -> EventTemporalStatus:
    if temporal is not None:
        return EventTemporalStatus.TIME_CONFIRMED
    if any(item.temporal_evidence for item in candidates):
        return EventTemporalStatus.TIME_PARTIAL
    return EventTemporalStatus.TIME_UNKNOWN


def _primary_source_id(sources: list[ExternalSourceRef]) -> str | None:
    eligible = [
        source
        for source in sources
        if source.company_association_status in {CompanyAssociationStatus.DIRECT_EXACT, CompanyAssociationStatus.DIRECT_SUPPORTED}
        and source.source_status is SourceStatus.ACCEPTED
        and source.source_tier in {SourceTier.TIER_1_OFFICIAL, SourceTier.TIER_2_ESTABLISHED_MEDIA, SourceTier.TIER_3_OTHER_ATTRIBUTABLE}
    ]
    if not eligible:
        return None
    rank = {
        SourceTier.TIER_1_OFFICIAL: 1,
        SourceTier.TIER_2_ESTABLISHED_MEDIA: 2,
        SourceTier.TIER_3_OTHER_ATTRIBUTABLE: 3,
    }
    return sorted(eligible, key=lambda item: (rank[item.source_tier], item.source_id))[0].source_id


def _cluster_identity(candidate: EventCandidate) -> tuple[str, str, str, str]:
    relationship = "DIRECT" if candidate.company_association_status in {
        CompanyAssociationStatus.DIRECT_EXACT,
        CompanyAssociationStatus.DIRECT_SUPPORTED,
    } else candidate.company_association_status.value
    return candidate.target_symbol, candidate.candidate_type.value, _subject_key(candidate.candidate_anchor, candidate.candidate_type), relationship


def _subject_key(anchor: str, event_type: CatalystEventType) -> str:
    if event_type is CatalystEventType.REVENUE_UPDATE:
        month = _MONTH_IN_TEXT.search(anchor)
        if month and month.group("month"):
            month_key = month.group("month")
        elif month and month.group("english_month"):
            month_key = _ENGLISH_MONTH_NUMBERS[month.group("english_month").casefold()]
        else:
            month_key = "unspecified:" + _subject_fingerprint(anchor)
        return "monthly_revenue:" + month_key
    if event_type is CatalystEventType.EARNINGS_RESULT:
        period = _reporting_period(anchor)
        return "financial_report:" + (period or _subject_fingerprint(anchor))
    if event_type is CatalystEventType.MANAGEMENT_GOVERNANCE:
        return "management_governance:" + _subject_fingerprint(anchor)
    if event_type is CatalystEventType.CAPEX_CAPACITY:
        return "capex_capacity:" + _subject_fingerprint(anchor)
    if event_type is CatalystEventType.DIVIDEND_CAPITAL_RETURN:
        return "capital_return:" + _subject_fingerprint(anchor)
    return _subject_fingerprint(anchor)


def _classify_event_type(anchor: str) -> CatalystEventType:
    core_subject = _core_event_subject(anchor)
    classified = _specific_event_type(core_subject)
    if classified is not None:
        return classified
    if _is_acquisition_core(core_subject):
        return CatalystEventType.OTHER
    classified = _specific_event_type(anchor)
    if classified is not None:
        return classified
    return CatalystEventType.OTHER


def _core_event_subject(anchor: str) -> str:
    """Prefer a structured subject, then the first factual sentence."""
    structured = _STRUCTURED_SUBJECT.search(anchor)
    if structured:
        return structured.group("subject")
    return re.split(r"[\n。；;]", anchor, maxsplit=1)[0] or anchor


def _specific_event_type(text: str) -> CatalystEventType | None:
    normalized = _normalized(text)
    if any(token in normalized for token in ("投資人說明會", "投資者說明會", "法人說明會", "法說會")):
        return CatalystEventType.MANAGEMENT_GOVERNANCE
    if any(token in normalized for token in ("財務報告", "財報", "季報", "半年報", "綜合損益表", "earnings", "eps")):
        return CatalystEventType.EARNINGS_RESULT
    if any(token in normalized for token in ("合併營收", "月營收", "revenue")):
        return CatalystEventType.REVENUE_UPDATE
    if any(token in normalized for token in ("股利", "配息", "庫藏股")):
        return CatalystEventType.DIVIDEND_CAPITAL_RETURN
    if any(token in normalized for token in ("擴建", "新廠", "產能", "設備投資", "資本支出", "廠房", "生產線", "capex", "capacityexpansion", "plantexpansion")):
        return CatalystEventType.CAPEX_CAPACITY
    return None


def _is_acquisition_core(text: str) -> bool:
    normalized = _normalized(text)
    return bool(re.search(
        r"(?:取得|購入).{0,80}(?:股權|有價證券)|投資取得子公司|"
        r"acquisition|equitypurchase|shareacquisition",
        normalized,
    ))


def _candidate_association(
    source: ExternalSourceRef,
    anchor: str,
    validated_aliases: tuple[str, ...],
    identity_catalog: TaiwanListedCompanyIdentityCatalog,
) -> CompanyAssociationStatus:
    """A page-level direct match never substitutes for candidate-local identity."""
    if source.company_association_status not in {
        CompanyAssociationStatus.DIRECT_EXACT,
        CompanyAssociationStatus.DIRECT_SUPPORTED,
    }:
        return source.company_association_status
    target_code = source.target_symbol.split(".", maxsplit=1)[0]
    exact_names = (source.target_company_name, *validated_aliases)
    has_code = bool(re.search(rf"(?<!\d){re.escape(target_code)}(?!\d)", anchor))
    has_name = any(name and name in anchor for name in exact_names)
    if _has_conflicting_listed_company_identity(anchor, target_code):
        return CompanyAssociationStatus.AMBIGUOUS
    if identity_catalog.find_explicit_non_target_identities(anchor, source.target_symbol):
        return CompanyAssociationStatus.AMBIGUOUS
    return source.company_association_status if has_code or has_name else CompanyAssociationStatus.AMBIGUOUS


def _has_conflicting_listed_company_identity(anchor: str, target_code: str) -> bool:
    """Fail closed only for explicit non-target listed-company identity forms."""
    explicit_codes = {
        match.group("code")
        for match in _STRUCTURED_STOCK_CODE.finditer(anchor)
    }
    explicit_codes.update(
        match.group("code")
        for match in _NAMED_STOCK_CODE.finditer(anchor)
    )
    return any(code != target_code for code in explicit_codes)


def _is_page_chrome_span(text: str, start: int, end: int) -> bool:
    """Conservatively identify quote/page framing that cannot supply event time."""
    prefix = text[start:min(end, start + 240)]
    return "更新" in prefix and any(marker in prefix for marker in _PAGE_CHROME_MARKERS if marker != "更新")


def _reporting_period(anchor: str) -> str | None:
    match = _REPORTING_PERIOD.search(anchor)
    if not match:
        return None
    if match.group("quarter"):
        return match.group("quarter").casefold()
    if match.group("half"):
        return match.group("half").casefold()
    chinese_quarter = match.group("chinese_quarter")
    if chinese_quarter:
        return {"第一季": "q1", "第1季": "q1", "第二季": "q2", "第2季": "q2", "第三季": "q3", "第3季": "q3", "第四季": "q4", "第4季": "q4"}[chinese_quarter]
    return {"上半年": "h1", "下半年": "h2"}[match.group("chinese_half")]


def _subject_fingerprint(anchor: str) -> str:
    without_dates = _DATE_BLOCK.sub("", anchor)
    return _normalized(without_dates)[:96] or "other"


def _matching_temporal_evidence(source: ExternalSourceRef, matched_text: str) -> tuple[SourceTemporalEvidence, ...]:
    match_values = _date_values(matched_text)
    return tuple(
        evidence
        for evidence in source.temporal_evidence
        if evidence.kind in {TemporalKind.EVENT_ANNOUNCED_AT, TemporalKind.EVENT_OCCURRED_AT}
        and evidence.value.isoformat().split("T", maxsplit=1)[0] in match_values
    )


def _confirmed_event_time(
    evidence: tuple[SourceTemporalEvidence, ...], research_window: EventResearchWindow
) -> SourceTemporalEvidence | None:
    accepted = [
        item
        for item in evidence
        if item.kind in {TemporalKind.EVENT_ANNOUNCED_AT, TemporalKind.EVENT_OCCURRED_AT}
        and validate_research_window(item, start_date=research_window[0], end_date=research_window[1]) is ResearchWindowStatus.IN_WINDOW
    ]
    return sorted(accepted, key=lambda item: item.value.isoformat())[0] if accepted else None


def _date_values(text: str) -> set[str]:
    values: set[str] = set()
    for match in _DATE_BLOCK.finditer(text):
        try:
            values.add(date(int(match.group("year")), int(match.group("month")), int(match.group("day"))).isoformat())
        except ValueError:
            pass
    return values


def _source_local_text(source: ExternalSourceRef) -> str:
    return source.source_excerpt or source.title or ""


def _bounded_anchor(text: str, start: int, end: int) -> tuple[str, int, int]:
    raw = text[start:end].strip(" \t\n,，;；。")
    if not raw:
        raw = text[start:end].strip() or "source evidence"
    bounded = raw[:360].strip()
    offset = text.find(bounded, start, end) if bounded else start
    return _WHITESPACE.sub(" ", bounded), offset, offset + len(bounded)


def _event_fact(candidates: tuple[EventCandidate, ...], primary_source_id: str | None) -> str:
    selected = next((item for item in candidates if item.source_id == primary_source_id), candidates[0])
    return selected.candidate_anchor[:360]


def _candidate_key(source_id: str, start: int, end: int, event_type: CatalystEventType, anchor: str) -> str:
    return "|".join((source_id, str(start), str(end), event_type.value, _normalized(anchor)))


def _normalized(value: str) -> str:
    return _NON_SUBJECT.sub("", _WHITESPACE.sub(" ", value).casefold())


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:16]


def _validate_window(research_window: EventResearchWindow) -> None:
    if len(research_window) != 2 or research_window[0] > research_window[1]:
        raise CatalystEventExtractionError("research_window must be an ordered start/end date pair.")


def _validate_source_target(source: ExternalSourceRef, target_symbol: str, target_company_name: str) -> None:
    if source.target_symbol != target_symbol or source.target_company_name != target_company_name:
        raise CatalystEventExtractionError("All sources must match the supplied target identity.")
