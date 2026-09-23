"""PokeVend Tracker (pokemonmap.com) status parsing.

The fixture is a real, unmodified /api/machines response for the bounding box
around ZIP 98092, trimmed to the rows that carry a status plus a few that do
not.
"""
from __future__ import annotations

import pytest

from pokevend.models import Availability, EvidenceClass, ObservationSource
from pokevend.normalizers.observation_normalizer import deduplicate
from pokevend.sources.pokemonmap_source import (
    STATUS_MAP,
    PokemonMapSource,
    parse_status_payload,
)
from tests.conftest import load_json_fixture


@pytest.fixture
def payload():
    return load_json_fixture("pokemonmap_status.json")


def test_parses_only_rows_that_carry_a_status_and_timestamp(payload):
    with_status = [row for row in payload if row.get("status") and row.get("lastUpdated")]
    observations = parse_status_payload(payload)

    assert len(observations) == len(with_status)
    assert observations, "fixture should contain usable rows"


def test_status_values_map_to_availability(payload):
    observations = {obs.machine_id: obs for obs in parse_status_payload(payload)}
    by_id = {
        row["Machine_ID"]: row for row in payload if row.get("status") and row.get("lastUpdated")
    }

    for machine_id, row in by_id.items():
        expected = STATUS_MAP[row["status"].upper()]
        assert observations[machine_id].availability == expected


def test_maintenance_counts_as_not_available():
    """A machine under maintenance could not dispense, which is what we forecast."""
    payload = [
        {
            "Machine_ID": "Q00804",
            "status": "MAINTENANCE",
            "lastUpdated": "2026-02-06T00:35:37.430Z",
            "Address": "4010 A St SE, Auburn, WA",
            "Retailer": "Safeway",
        }
    ]
    assert parse_status_payload(payload)[0].availability == Availability.NOT_AVAILABLE


def test_machine_id_is_the_printed_q_number(payload):
    observations = parse_status_payload(payload)
    for observation in observations:
        assert observation.machine_id.startswith("Q")
        # Exact identifier, so this is not a fuzzy text match.
        assert observation.machine_match_confidence == 1.0


def test_observation_time_comes_from_last_updated(payload):
    row = next(r for r in payload if r.get("status") and r.get("lastUpdated"))
    observation = next(
        o for o in parse_status_payload(payload) if o.machine_id == row["Machine_ID"]
    )
    assert observation.observed_at.startswith(row["lastUpdated"][:16])
    assert observation.posted_at == observation.observed_at


def test_evidence_class_and_weight(payload):
    observation = parse_status_payload(payload, weight_lookup=lambda _: 0.65)[0]
    assert observation.evidence_class == EvidenceClass.COMMUNITY_TIMESTAMPED
    assert observation.confidence == 0.65
    assert observation.source == ObservationSource.PUBLIC_WEB


def test_rows_without_status_or_timestamp_are_skipped():
    """An undated status cannot be dated 'now' without inventing evidence."""
    payload = [
        {"Machine_ID": "Q1", "status": None, "lastUpdated": None},
        {"Machine_ID": "Q2", "status": "INSTOCK", "lastUpdated": None},
        {"Machine_ID": "Q3", "status": None, "lastUpdated": "2026-05-18T00:24:50.781Z"},
        {"Machine_ID": None, "status": "INSTOCK", "lastUpdated": "2026-05-18T00:24:50.781Z"},
    ]
    assert parse_status_payload(payload) == []


def test_unknown_status_values_are_skipped_not_guessed():
    payload = [
        {"Machine_ID": "Q1", "status": "SOMETHING_NEW", "lastUpdated": "2026-05-18T00:24:50Z"}
    ]
    assert parse_status_payload(payload) == []


@pytest.mark.parametrize("bad", [None, {}, "text", 42, [None, "x", 7]])
def test_unusable_payload_shapes_return_empty(bad):
    assert parse_status_payload(bad) == []


# -- polling behaviour ---------------------------------------------------

def test_repeated_polls_of_an_unchanged_status_collapse_to_one(payload):
    """The API exposes only current state, so every run re-reads the same rows."""
    first = parse_status_payload(payload)
    second = parse_status_payload(payload)

    assert [o.fingerprint for o in first] == [o.fingerprint for o in second]
    assert len(deduplicate(first + second)) == len(first)


def test_a_status_change_creates_a_new_observation():
    """A genuine change must not be swallowed by de-duplication."""
    before = [
        {"Machine_ID": "Q1", "status": "OUT_OF_STOCK", "lastUpdated": "2026-09-20T10:00:00Z"}
    ]
    after = [
        {"Machine_ID": "Q1", "status": "INSTOCK", "lastUpdated": "2026-09-23T14:37:00Z"}
    ]

    combined = deduplicate(parse_status_payload(before) + parse_status_payload(after))

    assert len(combined) == 2
    assert {o.availability for o in combined} == {
        Availability.NOT_AVAILABLE,
        Availability.AVAILABLE,
    }


def test_same_status_reported_again_later_is_a_distinct_observation():
    """A machine going out of stock, restocked, then out of stock again."""
    early = [
        {"Machine_ID": "Q1", "status": "OUT_OF_STOCK", "lastUpdated": "2026-09-20T10:00:00Z"}
    ]
    later = [
        {"Machine_ID": "Q1", "status": "OUT_OF_STOCK", "lastUpdated": "2026-09-22T10:00:00Z"}
    ]
    assert len(deduplicate(parse_status_payload(early) + parse_status_payload(later))) == 2


# -- adapter -------------------------------------------------------------

def test_normalize_never_raises_on_bad_input():
    source = PokemonMapSource({}, session=None)
    assert source.normalize(object()) == []


def test_disabled_source_reports_disabled_health():
    source = PokemonMapSource({}, session=None, enabled=False)
    health = source.health_check()
    assert health.status == "DISABLED"
    assert health.reason == "DISABLED"


def test_only_minimal_data_is_retained(payload):
    """No scraped prose is stored - just normalized fields and a source link."""
    observation = parse_status_payload(payload)[0]
    assert observation.source_url == "https://pokemonmap.com/"
    assert observation.raw_text_hash
    assert observation.extra.get("communityStatus")
