"""The 10-mile radius filter is geometric, never name-based."""
from __future__ import annotations

import pytest

from pokevend.geo import destination_point, haversine_miles
from pokevend.normalizers.machine_normalizer import filter_by_radius
from tests.conftest import ORIGIN, make_machine

RADIUS = 10.0


def machine_at_distance(distance_miles: float, machine_id: str, bearing: float = 45.0, **kwargs):
    """A machine placed exactly ``distance_miles`` from the search centroid."""
    latitude, longitude = destination_point(ORIGIN[0], ORIGIN[1], bearing, distance_miles)
    return make_machine(machine_id=machine_id, latitude=latitude, longitude=longitude, **kwargs)


@pytest.mark.parametrize(
    "distance,expected",
    [
        (0.0, True),
        (5.0, True),
        (9.9, True),
        (10.0, True),    # exactly on the boundary is included
        (10.1, False),
        (25.0, False),
    ],
)
def test_radius_boundaries(distance, expected):
    machine = machine_at_distance(distance, f"rec-{distance}")
    kept = filter_by_radius([machine], ORIGIN, RADIUS)
    assert bool(kept) is expected


def test_distance_is_computed_not_taken_from_source():
    machine = machine_at_distance(7.5, "rec-7")
    machine.distance_miles = 999.0  # a source claiming nonsense
    kept = filter_by_radius([machine], ORIGIN, RADIUS)
    assert kept[0].distance_miles == pytest.approx(7.5, abs=0.01)


def test_city_name_does_not_decide_inclusion():
    """A Covington machine inside the radius stays; an Auburn one outside goes."""
    covington_inside = machine_at_distance(6.0, "rec-covington", city="Covington",
                                           zip_code="98042")
    auburn_outside = machine_at_distance(14.0, "rec-auburn-far", city="Auburn",
                                         zip_code="98092")

    kept = filter_by_radius([covington_inside, auburn_outside], ORIGIN, RADIUS)
    kept_ids = [machine.id for machine in kept]

    assert "rec-covington" in kept_ids
    assert "rec-auburn-far" not in kept_ids


def test_results_are_sorted_nearest_first():
    machines = [
        machine_at_distance(8.0, "far"),
        machine_at_distance(2.0, "near"),
        machine_at_distance(5.0, "mid"),
    ]
    kept = filter_by_radius(machines, ORIGIN, RADIUS)
    assert [machine.id for machine in kept] == ["near", "mid", "far"]


def test_radius_is_direction_independent():
    """Distance is measured on the sphere, so bearing must not matter."""
    for bearing in (0, 90, 180, 270, 315):
        machine = machine_at_distance(9.5, "rec", bearing=bearing)
        assert filter_by_radius([machine], ORIGIN, RADIUS), f"failed at bearing {bearing}"
        outside = machine_at_distance(10.5, "rec", bearing=bearing)
        assert not filter_by_radius([outside], ORIGIN, RADIUS)


def test_real_discovered_machines_are_all_inside_the_radius(fixtures_dir):
    """Every machine the locator fixture yields inside 10 miles really is."""
    from pokevend.sources.pokemon_locator import parse_machines_payload
    from tests.conftest import load_json_fixture

    machines = parse_machines_payload(load_json_fixture("pokemon_locator_bbox.json"))
    kept = filter_by_radius(machines, ORIGIN, RADIUS)

    assert kept, "fixture should contain machines inside the radius"
    assert len(kept) < len(machines), "the bounding box is wider than the circle"
    for machine in kept:
        actual = haversine_miles(ORIGIN[0], ORIGIN[1], machine.latitude, machine.longitude)
        assert actual <= RADIUS + 1e-6
