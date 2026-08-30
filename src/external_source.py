"""Deterministic external-source evidence models for future catalyst retrieval."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from enum import StrEnum
import hashlib
import json
import re
from typing import Iterable
from urllib.parse import parse_qsl
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.parse import urlunsplit


EXTERNAL_SOURCE_REF_VERSION = "EXTERNAL_SOURCE_REF_V1"
MAX_SOURCE_EXCERPT_LENGTH = 1_000


class ExternalSourceError(ValueError):
    """Raised when external-source evidence cannot be normalized safely."""


class SourceTier(StrEnum):
    TIER_1_OFFICIAL = "TIER_1_OFFICIAL"
    TIER_2_ESTABLISHED_MEDIA = "TIER_2_ESTABLISHED_MEDIA"
    TIER_3_OTHER_ATTRIBUTABLE = "TIER_3_OTHER_ATTRIBUTABLE"
    TIER_4_SOCIAL_COMMUNITY = "TIER_4_SOCIAL_COMMUNITY"
    UNKNOWN = "UNKNOWN"


class CompanyAssociationStatus(StrEnum):
    DIRECT_EXACT = "DIRECT_EXACT"
    DIRECT_SUPPORTED = "DIRECT_SUPPORTED"
    RELATED_ENTITY = "RELATED_ENTITY"
    AMBIGUOUS = "AMBIGUOUS"
    UNRELATED = "UNRELATED"
    UNKNOWN = "UNKNOWN"


class SourceStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    MISSING_URL = "MISSING_URL"
    MISSING_TITLE = "MISSING_TITLE"
    MISSING_IDENTITY = "MISSING_IDENTITY"


class TemporalKind(StrEnum):
    SOURCE_PUBLISHED_AT = "SOURCE_PUBLISHED_AT"
    EVENT_ANNOUNCED_AT = "EVENT_ANNOUNCED_AT"
    EVENT_OCCURRED_AT = "EVENT_OCCURRED_AT"
    UNKNOWN = "UNKNOWN"


class TemporalPrecision(StrEnum):
    DATE = "DATE"
    DATETIME = "DATETIME"


class TemporalEvidenceBasis(StrEnum):
    STRUCTURED_PROVIDER_METADATA = "STRUCTURED_PROVIDER_METADATA"
    SOURCE_SNIPPET_EXACT_DATE = "SOURCE_SNIPPET_EXACT_DATE"
    SOURCE_SNIPPET_EXACT_DATETIME = "SOURCE_SNIPPET_EXACT_DATETIME"


class TemporalConfidenceStatus(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    UNKNOWN = "UNKNOWN"


class ResearchWindowStatus(StrEnum):
    IN_WINDOW = "IN_WINDOW"
    OUT_OF_WINDOW = "OUT_OF_WINDOW"
    UNKNOWN = "UNKNOWN"


_TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}

_MONTH_NUMBERS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_YEAR_FIRST_DATE_PATTERN = re.compile(r"(?<!\d)(?P<year>20\d{2})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})(?!\d)")
_CHINESE_DATE_PATTERN = re.compile(r"(?<!\d)(?P<year>20\d{2})\s*年\s*(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日")
_DAY_MONTH_YEAR_PATTERN = re.compile(r"(?<!\d)(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+)\.?\s*,?\s+(?P<year>20\d{2})(?!\d)", re.IGNORECASE)
_MONTH_DAY_YEAR_PATTERN = re.compile(r"(?<![A-Za-z])(?P<month>[A-Za-z]+)\.?\s+(?P<day>\d{1,2}),\s*(?P<year>20\d{2})(?!\d)", re.IGNORECASE)


@dataclass(frozen=True)
class TargetCompanyIdentity:
    symbol: str
    canonical_name: str
    validated_english_name: str | None = None
    supported_aliases: tuple[str, ...] = ()

    @property
    def security_code(self) -> str:
        return self.symbol.split(".", maxsplit=1)[0]


@dataclass(frozen=True)
class RelatedCompanyIdentity:
    canonical_name: str
    security_codes: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class RawWebSearchSource:
    url: str | None
    title: str | None
    snippet: str | None
    source_type: str = "web_search_result"
    source_published_at: str | None = None
    domain: str | None = None


@dataclass(frozen=True)
class SourceTemporalEvidence:
    value: date | datetime
    precision: TemporalPrecision
    kind: TemporalKind
    basis: TemporalEvidenceBasis
    raw_text: str
    confidence_status: TemporalConfidenceStatus = TemporalConfidenceStatus.DETERMINISTIC


@dataclass(frozen=True)
class ExternalSourceRef:
    source_id: str
    source_type: str
    source_tier: SourceTier
    source_url: str | None
    canonical_url: str | None
    domain: str | None
    title: str | None
    target_symbol: str
    target_company_name: str
    retrieved_at: datetime
    source_published_at: date | datetime | None
    source_published_at_precision: TemporalPrecision | None
    source_published_at_basis: TemporalEvidenceBasis | None
    source_excerpt: str | None
    source_excerpt_truncated: bool
    temporal_evidence: tuple[SourceTemporalEvidence, ...]
    content_hash: str
    company_association_status: CompanyAssociationStatus
    source_status: SourceStatus

    def identity_payload(self) -> dict[str, object]:
        return {
            "version": EXTERNAL_SOURCE_REF_VERSION,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_tier": self.source_tier.value,
            "source_url": self.source_url,
            "canonical_url": self.canonical_url,
            "domain": self.domain,
            "title": self.title,
            "target_symbol": self.target_symbol,
            "target_company_name": self.target_company_name,
            "source_published_at": self.source_published_at.isoformat() if self.source_published_at else None,
            "source_published_at_precision": self.source_published_at_precision.value if self.source_published_at_precision else None,
            "source_published_at_basis": self.source_published_at_basis.value if self.source_published_at_basis else None,
            "source_excerpt": self.source_excerpt,
            "source_excerpt_truncated": self.source_excerpt_truncated,
            "temporal_evidence": [
                {
                    "value": evidence.value.isoformat(),
                    "precision": evidence.precision.value,
                    "kind": evidence.kind.value,
                    "basis": evidence.basis.value,
                    "raw_text": evidence.raw_text,
                    "confidence_status": evidence.confidence_status.value,
                }
                for evidence in self.temporal_evidence
            ],
            "company_association_status": self.company_association_status.value,
            "source_status": self.source_status.value,
        }


def canonicalize_url(url: str | None) -> str | None:
    if url is None:
        return None
    stripped = url.strip()
    if not stripped:
        return None
    parsed = urlsplit(stripped)
    if not parsed.scheme or not parsed.netloc:
        raise ExternalSourceError("External source URL must include a scheme and host.")
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMETERS and not key.lower().startswith("utm_")
    ]
    return urlunsplit((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path or "/",
        urlencode(sorted(query_items)),
        "",
    ))


def source_domain(canonical_url: str | None, fallback_domain: str | None = None) -> str | None:
    if canonical_url:
        return urlsplit(canonical_url).netloc.lower().removeprefix("www.")
    if fallback_domain:
        return fallback_domain.strip().lower().removeprefix("www.") or None
    return None


def classify_source_tier(domain: str | None, domain_map: dict[str, SourceTier] | None = None) -> SourceTier:
    if not domain:
        return SourceTier.UNKNOWN
    normalized = domain.lower().removeprefix("www.")
    for mapped_domain, tier in (domain_map or {}).items():
        candidate = mapped_domain.lower().removeprefix("www.")
        if normalized == candidate or normalized.endswith("." + candidate):
            return tier
    return SourceTier.UNKNOWN


def extract_temporal_evidence(
    text: str | None,
    *,
    kind: TemporalKind = TemporalKind.EVENT_ANNOUNCED_AT,
    basis: TemporalEvidenceBasis = TemporalEvidenceBasis.SOURCE_SNIPPET_EXACT_DATE,
) -> tuple[SourceTemporalEvidence, ...]:
    if not text:
        return ()
    matches: list[tuple[int, date, str]] = []
    for pattern in (_YEAR_FIRST_DATE_PATTERN, _CHINESE_DATE_PATTERN):
        for match in pattern.finditer(text):
            parsed = _build_date(match.group("year"), match.group("month"), match.group("day"))
            if parsed:
                matches.append((match.start(), parsed, match.group(0)))
    for pattern, month_first in ((_DAY_MONTH_YEAR_PATTERN, False), (_MONTH_DAY_YEAR_PATTERN, True)):
        for match in pattern.finditer(text):
            month = _MONTH_NUMBERS.get(match.group("month").lower().rstrip("."))
            if not month:
                continue
            parsed = _build_date(match.group("year"), str(month), match.group("day"))
            if parsed:
                matches.append((match.start(), parsed, match.group(0)))
    evidence: list[SourceTemporalEvidence] = []
    seen: set[tuple[date, str]] = set()
    for _, parsed, raw_text in sorted(matches, key=lambda item: item[0]):
        key = (parsed, raw_text)
        if key not in seen:
            evidence.append(SourceTemporalEvidence(parsed, TemporalPrecision.DATE, kind, basis, raw_text))
            seen.add(key)
    return tuple(evidence)


def parse_structured_source_date(value: str | None) -> SourceTemporalEvidence | None:
    if value and "T" in value:
        try:
            parsed_datetime = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            parsed_datetime = None
        if parsed_datetime is not None:
            return SourceTemporalEvidence(
                parsed_datetime,
                TemporalPrecision.DATETIME,
                TemporalKind.SOURCE_PUBLISHED_AT,
                TemporalEvidenceBasis.STRUCTURED_PROVIDER_METADATA,
                value.strip(),
            )
    evidence = extract_temporal_evidence(
        value,
        kind=TemporalKind.SOURCE_PUBLISHED_AT,
        basis=TemporalEvidenceBasis.STRUCTURED_PROVIDER_METADATA,
    )
    if len(evidence) != 1:
        return None
    candidate = evidence[0]
    if value is None or candidate.raw_text.strip() != value.strip():
        return None
    return candidate


def validate_research_window(
    evidence: SourceTemporalEvidence | None,
    *,
    start_date: date,
    end_date: date,
) -> ResearchWindowStatus:
    if evidence is None:
        return ResearchWindowStatus.UNKNOWN
    if start_date > end_date:
        raise ExternalSourceError("Research window start_date must not be after end_date.")
    evidence_date = evidence.value.date() if isinstance(evidence.value, datetime) else evidence.value
    if start_date <= evidence_date <= end_date:
        return ResearchWindowStatus.IN_WINDOW
    return ResearchWindowStatus.OUT_OF_WINDOW


def classify_company_association(
    *,
    title: str | None,
    excerpt: str | None,
    target: TargetCompanyIdentity,
    related_entities: Iterable[RelatedCompanyIdentity] = (),
) -> CompanyAssociationStatus:
    text = _normalized_text(" ".join(filter(None, (title, excerpt))))
    if not text:
        return CompanyAssociationStatus.UNKNOWN
    if _contains_direct_identity(text, target):
        return CompanyAssociationStatus.DIRECT_EXACT
    if _contains_related_identity(text, related_entities):
        return CompanyAssociationStatus.RELATED_ENTITY
    if _contains_any(text, (target.canonical_name, target.validated_english_name, *target.supported_aliases)):
        return CompanyAssociationStatus.AMBIGUOUS
    if _contains_target_name_stem(text, target.validated_english_name):
        return CompanyAssociationStatus.AMBIGUOUS
    return CompanyAssociationStatus.UNRELATED


def normalize_external_source(
    raw: RawWebSearchSource,
    *,
    target: TargetCompanyIdentity,
    retrieved_at: datetime,
    domain_map: dict[str, SourceTier] | None = None,
    related_entities: Iterable[RelatedCompanyIdentity] = (),
    max_excerpt_length: int = MAX_SOURCE_EXCERPT_LENGTH,
) -> ExternalSourceRef:
    if max_excerpt_length <= 0:
        raise ExternalSourceError("max_excerpt_length must be positive.")
    canonical_url = canonicalize_url(raw.url)
    domain = source_domain(canonical_url, raw.domain)
    excerpt = raw.snippet.strip() if raw.snippet else None
    excerpt_truncated = bool(excerpt and len(excerpt) > max_excerpt_length)
    if excerpt_truncated:
        excerpt = excerpt[:max_excerpt_length]
    title = raw.title.strip() if raw.title else None
    association = classify_company_association(
        title=title,
        excerpt=excerpt,
        target=target,
        related_entities=related_entities,
    )
    structured_date = parse_structured_source_date(raw.source_published_at)
    temporal_evidence = extract_temporal_evidence("\n".join(part for part in (title, excerpt) if part))
    source_id = _source_id(canonical_url=canonical_url, domain=domain, title=title)
    status = _source_status(canonical_url=canonical_url, title=title, source_id=source_id)
    payload = {
        "source_id": source_id,
        "source_type": raw.source_type,
        "source_tier": classify_source_tier(domain, domain_map).value,
        "canonical_url": canonical_url,
        "domain": domain,
        "title": title,
        "target_symbol": target.symbol,
        "target_company_name": target.canonical_name,
        "source_published_at": structured_date.value.isoformat() if structured_date else None,
        "source_excerpt": excerpt,
        "source_excerpt_truncated": excerpt_truncated,
        "temporal_evidence": [
            (item.value.isoformat(), item.precision.value, item.kind.value, item.basis.value, item.raw_text)
            for item in temporal_evidence
        ],
        "company_association_status": association.value,
        "source_status": status.value,
    }
    return ExternalSourceRef(
        source_id=source_id,
        source_type=raw.source_type,
        source_tier=classify_source_tier(domain, domain_map),
        source_url=raw.url.strip() if raw.url else None,
        canonical_url=canonical_url,
        domain=domain,
        title=title,
        target_symbol=target.symbol,
        target_company_name=target.canonical_name,
        retrieved_at=retrieved_at,
        source_published_at=structured_date.value if structured_date else None,
        source_published_at_precision=structured_date.precision if structured_date else None,
        source_published_at_basis=structured_date.basis if structured_date else None,
        source_excerpt=excerpt,
        source_excerpt_truncated=excerpt_truncated,
        temporal_evidence=temporal_evidence,
        content_hash=_canonical_hash(payload),
        company_association_status=association,
        source_status=status,
    )


def deduplicate_sources(sources: Iterable[ExternalSourceRef]) -> tuple[ExternalSourceRef, ...]:
    unique: dict[str, ExternalSourceRef] = {}
    for source in sources:
        key = source.canonical_url or _fallback_key(source.domain, source.title)
        if key is None:
            key = source.source_id
        unique.setdefault(key, source)
    return tuple(sorted(unique.values(), key=lambda source: source.source_id))


def is_primary_factual_evidence(source: ExternalSourceRef) -> bool:
    """Tier 4 and unknown sources can remain in artifacts but never become primary evidence."""
    return (
        source.source_status is SourceStatus.ACCEPTED
        and source.company_association_status in {
            CompanyAssociationStatus.DIRECT_EXACT,
            CompanyAssociationStatus.DIRECT_SUPPORTED,
        }
        and source.source_tier in {SourceTier.TIER_1_OFFICIAL, SourceTier.TIER_2_ESTABLISHED_MEDIA}
    )


def _build_date(year: str, month: str, day: str) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _contains_any(text: str, values: Iterable[str | None]) -> bool:
    return any(_normalized_text(value) in text for value in values if value and _normalized_text(value))


def _contains_direct_identity(text: str, target: TargetCompanyIdentity) -> bool:
    canonical_markers = (target.validated_english_name, target.symbol)
    if _contains_any(text, canonical_markers):
        return True
    code_pattern = re.compile(rf"(?<!\d){re.escape(target.security_code)}(?!\d)")
    return bool(code_pattern.search(text) and _contains_any(text, (target.canonical_name, *target.supported_aliases)))


def _contains_target_name_stem(text: str, validated_english_name: str | None) -> bool:
    if not validated_english_name:
        return False
    words = _normalized_text(validated_english_name).split()
    if not words:
        return False
    return words[0] in text


def _contains_related_identity(text: str, related_entities: Iterable[RelatedCompanyIdentity]) -> bool:
    for entity in related_entities:
        if _contains_any(text, (entity.canonical_name, *entity.aliases)):
            return True
        for code in entity.security_codes:
            if re.search(rf"(?<!\d){re.escape(code)}(?!\d)", text):
                return True
    return False


def _source_id(*, canonical_url: str | None, domain: str | None, title: str | None) -> str:
    material = canonical_url or _fallback_key(domain, title)
    if material is None:
        return "external_source_unknown_" + hashlib.sha256(b"missing").hexdigest()[:20]
    return "external_source_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def _fallback_key(domain: str | None, title: str | None) -> str | None:
    if not domain or not title:
        return None
    return f"{domain}|{_normalized_text(title)}"


def _source_status(*, canonical_url: str | None, title: str | None, source_id: str) -> SourceStatus:
    if source_id.endswith(hashlib.sha256(b"missing").hexdigest()[:20]):
        return SourceStatus.MISSING_IDENTITY
    if canonical_url is None:
        return SourceStatus.MISSING_URL
    if title is None:
        return SourceStatus.MISSING_TITLE
    return SourceStatus.ACCEPTED


def _canonical_hash(payload: object) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
