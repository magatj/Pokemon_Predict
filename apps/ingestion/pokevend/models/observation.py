"""Availability observations.

An observation is one timestamped statement about whether a machine could
dispense product. It is the only input the forecast engine trusts.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


class Availability:
    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    RESTOCK = "RESTOCK"
    UNKNOWN = "UNKNOWN"

    ALL = (AVAILABLE, NOT_AVAILABLE, RESTOCK, UNKNOWN)

    #: Outcomes that count as "product could be bought around then".
    POSITIVE = (AVAILABLE, RESTOCK)


class ObservationSource:
    REDDIT = "REDDIT"
    PUBLIC_WEB = "PUBLIC_WEB"
    USER = "USER"

    ALL = (REDDIT, PUBLIC_WEB, USER)


class EvidenceClass:
    """Evidence tiers; weights live in forecast_config.yaml."""

    PURCHASE_CONFIRMED = "PURCHASE_CONFIRMED"
    USER_REPORT_WITH_PHOTO = "USER_REPORT_WITH_PHOTO"
    USER_AVAILABLE = "USER_AVAILABLE"
    USER_NOT_AVAILABLE = "USER_NOT_AVAILABLE"
    COMMUNITY_TIMESTAMPED = "COMMUNITY_TIMESTAMPED"
    COMMUNITY_GENERAL = "COMMUNITY_GENERAL"
    THIRD_PARTY_INFERRED = "THIRD_PARTY_INFERRED"


class Product:
    BOOSTER_BUNDLE = "BOOSTER_BUNDLE"
    BOOSTER_PACK = "BOOSTER_PACK"
    ELITE_TRAINER_BOX = "ELITE_TRAINER_BOX"
    TIN = "TIN"
    COLLECTION_BOX = "COLLECTION_BOX"
    OTHER = "OTHER"

    ALL = (
        BOOSTER_BUNDLE,
        BOOSTER_PACK,
        ELITE_TRAINER_BOX,
        TIN,
        COLLECTION_BOX,
        OTHER,
    )


@dataclass
class Observation:
    """A normalized availability observation.

    Only the minimum needed for forecasting is stored. Source text is reduced to
    ``raw_text_hash`` plus a ``source_url`` so nothing long or copyrighted is
    republished.
    """

    id: str
    source: str
    availability: str
    posted_at: str
    observed_at: Optional[str] = None
    source_url: Optional[str] = None
    machine_id: Optional[str] = None
    machine_match_confidence: float = 0.0
    retailer: Optional[str] = None
    location_text: Optional[str] = None
    product: Optional[str] = None
    purchase_confirmed: bool = False
    has_photo: bool = False
    evidence_class: str = EvidenceClass.COMMUNITY_GENERAL
    confidence: float = 0.4
    raw_text_hash: str = ""
    fingerprint: str = ""
    ingested_at: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Observation:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})

    @property
    def effective_at(self) -> str:
        """When the machine state was actually seen, falling back to post time."""
        return self.observed_at or self.posted_at

    def is_positive(self) -> bool:
        return self.availability in Availability.POSITIVE


def hash_text(text: str) -> str:
    """Stable hash of normalized source text, used for duplicate detection."""
    normalized = " ".join((text or "").split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:40]


def build_fingerprint(
    source: str,
    source_identifier: str,
    machine_id: Optional[str],
    timestamp: Optional[str],
    raw_text_hash: str,
) -> str:
    """Deterministic identity for an observation.

    The same report arriving twice (re-crawl, cross-post, mirrored feed)
    collapses to one fingerprint and is counted once.
    """
    parts = [
        (source or "").upper(),
        source_identifier or "",
        machine_id or "",
        (timestamp or "")[:16],  # minute resolution
        raw_text_hash or "",
    ]
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]
