"""Shared test fixtures and builders."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pokevend.config import ForecastConfig
from pokevend.models import Availability, EvidenceClass, Machine, Observation, SourceAuthority
from pokevend.models.observation import build_fingerprint, hash_text
from pokevend.timeutil import to_iso8601

FIXTURES = Path(__file__).parent / "fixtures"

#: Centroid of ZIP 98092, the default search area.
ORIGIN = (47.2884, -122.098)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_json_fixture(name: str):
    return json.loads(load_fixture(name))


def make_machine(
    machine_id: str = "rec1",
    latitude: float = 47.2884,
    longitude: float = -122.098,
    retailer: str = "Safeway",
    city: str = "Auburn",
    zip_code: str = "98092",
    address: str = "4010 A St SE",
    name: str = "Q00001",
    aliases=None,
) -> Machine:
    return Machine(
        id=machine_id,
        retailer=retailer,
        name=name,
        address=address,
        city=city,
        state="WA",
        zip=zip_code,
        latitude=latitude,
        longitude=longitude,
        source="pokemon_locator",
        source_authority=SourceAuthority.OFFICIAL,
        aliases=aliases if aliases is not None else [],
    )


def make_observation(
    observation_id: str = "obs1",
    machine_id: str = "rec1",
    when: datetime = None,
    availability: str = Availability.AVAILABLE,
    confidence: float = 1.0,
    match_confidence: float = 1.0,
    purchase: bool = False,
    source: str = "USER",
    text: str = "available",
    evidence_class: str = EvidenceClass.USER_AVAILABLE,
) -> Observation:
    when = when or datetime(2026, 9, 20, 12, 37, tzinfo=timezone.utc)
    raw_hash = hash_text(text)
    fingerprint = build_fingerprint(source, observation_id, machine_id,
                                    to_iso8601(when), raw_hash)
    return Observation(
        id=observation_id,
        source=source,
        availability=availability,
        posted_at=to_iso8601(when),
        observed_at=to_iso8601(when),
        machine_id=machine_id,
        machine_match_confidence=match_confidence,
        purchase_confirmed=purchase,
        evidence_class=evidence_class,
        confidence=confidence,
        raw_text_hash=raw_hash,
        fingerprint=fingerprint,
    )


def minimal_forecast_config(**overrides) -> ForecastConfig:
    """A valid ForecastConfig with test-friendly thresholds."""
    raw = {
        "location": {
            "zip_code": "98092",
            "radius_miles": 10.0,
            "timezone": "America/Los_Angeles",
            "fallback_centroid": {"latitude": ORIGIN[0], "longitude": ORIGIN[1]},
        },
        "forecast": {
            "window_minutes": 5,
            "horizon_hours": 3,
            "max_windows_per_machine": 5,
            "minimum_observations": 8,
            "high_confidence_observations": 30,
            "minute_tolerance": 3,
            "minute_pattern_min_samples": 4,
            "interval_candidates_minutes": [30, 60, 90, 120],
            "interval_tolerance_minutes": 4,
            "interval_min_samples": 4,
            "interval_min_support": 0.5,
            "recency_lambda_per_hour": 0.0058,
            "recency_reference_hours": 72,
            "nearby_radii_miles": [3, 5, 10],
            "nearby_window_minutes": 90,
        },
        "scoring_weights": {
            "minute_pattern": 0.30,
            "interval": 0.20,
            "historical_hit_rate": 0.20,
            "recency": 0.15,
            "weekday_hour": 0.10,
            "nearby_activity": 0.05,
        },
        "confidence": {
            "full_confidence_observations": 30,
            "sample_scale_floor": 0.35,
            "bands": {"high": 0.70, "medium": 0.40},
        },
        "observation_weights": {
            "PURCHASE_CONFIRMED": 1.00,
            "USER_REPORT_WITH_PHOTO": 0.95,
            "USER_AVAILABLE": 0.85,
            "USER_NOT_AVAILABLE": 0.75,
            "COMMUNITY_TIMESTAMPED": 0.65,
            "COMMUNITY_GENERAL": 0.40,
            "THIRD_PARTY_INFERRED": 0.25,
        },
        "matching": {"min_machine_match_confidence": 0.70},
    }
    for section, values in overrides.items():
        raw.setdefault(section, {}).update(values)
    return ForecastConfig(raw)


def hourly_positives(
    count: int,
    minute: int = 37,
    start: datetime = None,
    machine_id: str = "rec1",
    jitter=(0, 1, -1),
):
    """Observations one hour apart, clustered near ``minute`` past the hour.

    ``jitter`` reproduces the real pattern of reports landing on :36/:37/:38
    rather than an implausibly exact minute.
    """
    start = start or datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc)
    observations = []
    for index in range(count):
        offset = jitter[index % len(jitter)]
        when = start + timedelta(hours=index, minutes=minute + offset)
        observations.append(
            make_observation(
                observation_id=f"obs{index}",
                machine_id=machine_id,
                when=when,
            )
        )
    return observations
