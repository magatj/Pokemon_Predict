"""Official locator payload parsing.

The fixture is a real, unmodified response from the public locator API for a
bounding box around ZIP 98092.
"""
from __future__ import annotations

import pytest

from pokevend.models import SourceAuthority
from pokevend.sources.pokemon_locator import PokemonLocatorSource, parse_machines_payload
from tests.conftest import load_json_fixture


@pytest.fixture
def payload():
    return load_json_fixture("pokemon_locator_bbox.json")


def test_parses_every_well_formed_row(payload):
    machines = parse_machines_payload(payload)
    assert len(machines) == len(payload["machines"])


def test_extracts_machine_identity_fields(payload):
    machines = {machine.id: machine for machine in parse_machines_payload(payload)}
    machine = machines["recDRDzItBxXkjJTy"]

    assert machine.name == "Q00164"
    assert machine.retailer == "Fred Meyer"
    assert machine.address == "801 Auburn Wy N"
    assert machine.city == "Auburn"
    assert machine.state == "WA"
    assert machine.zip == "98002"
    assert machine.latitude == pytest.approx(47.3156721)
    assert machine.longitude == pytest.approx(-122.2266363)


def test_records_official_authority_and_provenance(payload):
    machine = parse_machines_payload(payload)[0]
    assert machine.source == "pokemon_locator"
    assert machine.source_authority == SourceAuthority.OFFICIAL
    assert machine.source_url
    assert machine.discovered_at and machine.last_verified_at


def test_source_supplied_distance_is_not_trusted(payload):
    """The API reports its own distance; we must compute ours instead."""
    assert "distance" in payload["machines"][0]
    machine = parse_machines_payload(payload)[0]
    assert machine.distance_miles is None


def test_malformed_rows_are_dropped_not_raised():
    """A row is usable only with an id and parseable coordinates.

    ``recNOFIELDS`` has both, so it survives with default retailer/address;
    every other bad row is dropped without raising.
    """
    machines = parse_machines_payload(load_json_fixture("pokemon_locator_malformed.json"))
    assert [machine.id for machine in machines] == ["recGOOD0000000001", "recNOFIELDS"]


def test_missing_optional_fields_get_safe_defaults():
    payload = {"machines": [{"id": "recX", "lat": 47.3, "lng": -122.2}]}
    machine = parse_machines_payload(payload)[0]

    assert machine.retailer == "Unknown retailer"
    assert machine.name == "recX"
    assert machine.address == ""
    assert machine.city == ""


@pytest.mark.parametrize(
    "payload", [None, {}, [], "text", 42, {"machines": None}, {"machines": "nope"}]
)
def test_unusable_payload_shapes_return_empty(payload):
    assert parse_machines_payload(payload) == []


def test_normalize_merges_tiles_and_deduplicates(payload):
    """Tiles overlap at their edges, so the same machine arrives more than once."""
    source = PokemonLocatorSource({}, session=None)
    merged = source.normalize([payload, payload, {"machines": []}])

    assert len(merged) == len(payload["machines"])
    assert len({machine.id for machine in merged}) == len(merged)
