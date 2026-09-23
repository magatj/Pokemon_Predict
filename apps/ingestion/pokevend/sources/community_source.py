"""Community observation parsing.

Official sources publish where machines are, not when they can dispense. That
timing signal only exists in community reports and first-party user reports, so
this module turns free text into structured, minimal observations.

Only normalized fields plus a source URL are kept. Post bodies are reduced to a
hash and never republished.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from pokevend.models import Availability, EvidenceClass, ObservationSource, Product
from pokevend.models.observation import Observation, build_fingerprint, hash_text
from pokevend.sources.base import BaseSource
from pokevend.timeutil import now_utc, parse_iso8601, to_iso8601

LOGGER = logging.getLogger(__name__)

# A post must mention a machine AND Pokemon to be considered at all.
_POKEMON_HINT = re.compile(r"pok[eé]mon|pokemon", re.IGNORECASE)
_MACHINE_HINT = re.compile(r"vending|machine|kiosk", re.IGNORECASE)

# Machine ids are printed on the machine itself, e.g. Q00164.
_MACHINE_ID_PATTERN = re.compile(r"\b(Q\d{5})\b", re.IGNORECASE)
_ZIP_PATTERN = re.compile(r"\b(9\d{4})\b")

_RESTOCK_PATTERN = re.compile(
    r"\brestock(ed|ing)?\b|\brefill(ed|ing)?\b|\bdrop(ped|ping)?\b|\bloaded\b",
    re.IGNORECASE,
)
_NOT_AVAILABLE_PATTERN = re.compile(
    r"\bsold\s*out\b|\bempty\b|\bout\s*of\s*stock\b|\bnothing\s+(left|in\s+it)\b"
    r"|\bno\s+stock\b|\bcleaned\s*out\b|\bwiped\b|\bnot\s+available\b|\bdidn'?t\s+have\b",
    re.IGNORECASE,
)
_AVAILABLE_PATTERN = re.compile(
    r"\bin\s*stock\b|\bavailable\b|\bstocked\b|\bhas\s+(packs?|bundles?|etbs?)\b"
    r"|\bdispens(ed|ing)\b|\bfull\b|\bloaded\s+up\b",
    re.IGNORECASE,
)
_PURCHASE_PATTERN = re.compile(
    r"\b(bought|purchased|grabbed|picked\s+up|copped|snagged)\b", re.IGNORECASE
)
_PHOTO_PATTERN = re.compile(r"\b(photo|pic|picture|image)\b|i\.redd\.it|imgur\.com", re.IGNORECASE)

_PRODUCT_PATTERNS = (
    (Product.BOOSTER_BUNDLE, re.compile(r"\bbooster\s+bundle|\bbundle\b", re.IGNORECASE)),
    (Product.ELITE_TRAINER_BOX, re.compile(r"\belite\s+trainer\s+box\b|\betb\b", re.IGNORECASE)),
    (Product.COLLECTION_BOX, re.compile(r"\bcollection\s+box\b|\bcollection\b", re.IGNORECASE)),
    (Product.BOOSTER_PACK, re.compile(r"\bbooster\s+pack|\bpacks?\b", re.IGNORECASE)),
    (Product.TIN, re.compile(r"\btins?\b", re.IGNORECASE)),
)

#: Cities in and around the default search area, used to extract location text.
DEFAULT_LOCATION_TERMS = (
    "auburn", "kent", "covington", "maple valley", "federal way", "sumner",
    "bonney lake", "puyallup", "milton", "renton", "black diamond", "enumclaw",
)

DEFAULT_RETAILER_TERMS = (
    "safeway", "fred meyer", "fredmeyer", "qfc", "winco", "h mart", "albertsons",
    "target", "walmart", "kroger",
)


def is_relevant(text: str) -> bool:
    """Cheap pre-filter: does this text plausibly concern a Pokemon machine?"""
    if not text:
        return False
    return bool(_POKEMON_HINT.search(text) and _MACHINE_HINT.search(text))


def classify_availability(text: str) -> str:
    """Classify a report into an availability state.

    Order matters. "restocked but sold out already" is a negative report, so
    explicit negatives are checked before restock language.
    """
    if not text:
        return Availability.UNKNOWN
    negative = bool(_NOT_AVAILABLE_PATTERN.search(text))
    positive = bool(_AVAILABLE_PATTERN.search(text))
    restock = bool(_RESTOCK_PATTERN.search(text))

    if negative and not positive:
        return Availability.NOT_AVAILABLE
    if restock and not negative:
        return Availability.RESTOCK
    if positive and not negative:
        return Availability.AVAILABLE
    if positive and negative:
        # Mixed signals: trust the negative, it is the more specific claim.
        return Availability.NOT_AVAILABLE
    return Availability.UNKNOWN


def classify_product(text: str) -> Optional[str]:
    for product, pattern in _PRODUCT_PATTERNS:
        if pattern.search(text or ""):
            return product
    return None


def extract_machine_id(text: str) -> Optional[str]:
    match = _MACHINE_ID_PATTERN.search(text or "")
    return match.group(1).upper() if match else None


def extract_zip(text: str) -> Optional[str]:
    match = _ZIP_PATTERN.search(text or "")
    return match.group(1) if match else None


def extract_retailer(text: str, retailers=DEFAULT_RETAILER_TERMS) -> Optional[str]:
    lowered = (text or "").lower()
    for retailer in retailers:
        if retailer in lowered:
            return retailer.title().replace("Fredmeyer", "Fred Meyer")
    return None


def extract_location_text(text: str, terms=DEFAULT_LOCATION_TERMS) -> Optional[str]:
    lowered = (text or "").lower()
    found = [term for term in terms if term in lowered]
    return ", ".join(sorted(found)).title() if found else None


def evidence_class_for(availability: str, has_timestamp: bool, purchase: bool) -> str:
    """Pick the evidence tier for a community report."""
    if purchase:
        return EvidenceClass.COMMUNITY_TIMESTAMPED if has_timestamp \
            else EvidenceClass.COMMUNITY_GENERAL
    if has_timestamp and availability != Availability.UNKNOWN:
        return EvidenceClass.COMMUNITY_TIMESTAMPED
    return EvidenceClass.COMMUNITY_GENERAL


def parse_community_post(
    post: Dict[str, Any],
    source: str = ObservationSource.PUBLIC_WEB,
    weight_lookup=None,
) -> Optional[Observation]:
    """Turn one public post into an Observation, or None if it is not usable.

    ``post`` is a source-agnostic dict: ``id``, ``text``, ``created_at``,
    ``url``. Returning None (rather than raising) is how irrelevant and
    malformed rows are dropped without stopping the run.
    """
    if not isinstance(post, dict):
        return None

    text = " ".join(str(part) for part in (post.get("title"), post.get("text")) if part).strip()
    if not is_relevant(text):
        return None

    availability = classify_availability(text)
    if availability == Availability.UNKNOWN:
        # No availability signal means nothing to forecast from.
        return None

    posted_at = parse_iso8601(post.get("created_at"))
    if posted_at is None:
        return None

    observed_at = parse_iso8601(post.get("observed_at"))
    purchase = bool(_PURCHASE_PATTERN.search(text))
    has_photo = bool(_PHOTO_PATTERN.search(text)) or bool(post.get("has_photo"))

    evidence = evidence_class_for(availability, observed_at is not None, purchase)
    raw_hash = hash_text(text)
    source_identifier = str(post.get("id") or post.get("url") or raw_hash)
    machine_id = extract_machine_id(text)

    fingerprint = build_fingerprint(
        source=source,
        source_identifier=source_identifier,
        machine_id=machine_id,
        timestamp=to_iso8601(observed_at or posted_at),
        raw_text_hash=raw_hash,
    )

    confidence = weight_lookup(evidence) if weight_lookup else 0.4

    return Observation(
        id=fingerprint,
        source=source,
        availability=availability,
        posted_at=to_iso8601(posted_at),
        observed_at=to_iso8601(observed_at) if observed_at else None,
        source_url=post.get("url"),
        machine_id=machine_id,
        machine_match_confidence=1.0 if machine_id else 0.0,
        retailer=extract_retailer(text),
        location_text=extract_location_text(text) or extract_zip(text),
        product=classify_product(text),
        purchase_confirmed=purchase,
        has_photo=has_photo,
        evidence_class=evidence,
        confidence=confidence,
        raw_text_hash=raw_hash,
        fingerprint=fingerprint,
        ingested_at=to_iso8601(now_utc()),
    )


class CommunityObservationSource(BaseSource):
    """Base for adapters that yield source-agnostic post dicts."""

    name = "community"
    authority = "COMMUNITY"
    observation_source = ObservationSource.PUBLIC_WEB

    def __init__(self, settings, enabled: bool = True, weight_lookup=None):
        super().__init__(settings, enabled=enabled)
        self.weight_lookup = weight_lookup

    def fetch(self) -> List[Dict[str, Any]]:  # pragma: no cover - overridden
        raise NotImplementedError

    def normalize(self, raw: List[Dict[str, Any]]) -> List[Observation]:
        """Parse posts, skipping anything unusable. Never raises on bad input."""
        observations: List[Observation] = []
        for post in raw or []:
            try:
                observation = parse_community_post(
                    post, source=self.observation_source, weight_lookup=self.weight_lookup
                )
            except Exception as exc:  # noqa: BLE001 - one bad post must not stop the run
                LOGGER.warning("failed to parse post %r: %s", (post or {}).get("id"), exc)
                continue
            if observation is not None:
                observations.append(observation)
        return observations
