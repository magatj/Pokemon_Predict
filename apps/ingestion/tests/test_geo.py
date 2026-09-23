"""Geographic primitives."""
from __future__ import annotations

import pytest

from pokevend.geo import (
    bounding_box,
    destination_point,
    haversine_miles,
    parse_coordinate,
    tile_bounding_box,
    within_radius,
)
from tests.conftest import ORIGIN


def test_haversine_known_distance():
    """Seattle to Portland is about 145 miles."""
    distance = haversine_miles(47.6062, -122.3321, 45.5152, -122.6784)
    assert distance == pytest.approx(145, abs=3)


def test_haversine_is_symmetric_and_zero_at_identity():
    assert haversine_miles(*ORIGIN, *ORIGIN) == pytest.approx(0.0)
    assert haversine_miles(47.0, -122.0, 47.5, -122.5) == pytest.approx(
        haversine_miles(47.5, -122.5, 47.0, -122.0)
    )


def test_destination_point_round_trips():
    for bearing in (0, 45, 120, 200, 359):
        latitude, longitude = destination_point(ORIGIN[0], ORIGIN[1], bearing, 8.0)
        assert haversine_miles(ORIGIN[0], ORIGIN[1], latitude, longitude) == pytest.approx(
            8.0, abs=0.01
        )


def test_bounding_box_contains_the_whole_circle():
    """Every point on the radius circle must fall inside the box."""
    box = bounding_box(ORIGIN[0], ORIGIN[1], 10.0)
    for bearing in range(0, 360, 15):
        latitude, longitude = destination_point(ORIGIN[0], ORIGIN[1], bearing, 10.0)
        assert box.sw_lat <= latitude <= box.ne_lat
        assert box.sw_lng <= longitude <= box.ne_lng


def test_bounding_box_corner_is_further_than_the_radius():
    """The box over-covers, which is why a Haversine filter is still required."""
    box = bounding_box(ORIGIN[0], ORIGIN[1], 10.0)
    corner = haversine_miles(ORIGIN[0], ORIGIN[1], box.ne_lat, box.ne_lng)
    assert corner > 10.0


def test_tiling_covers_the_box_without_gaps():
    box = bounding_box(ORIGIN[0], ORIGIN[1], 10.0)
    tiles = tile_bounding_box(box, 4)

    assert len(tiles) == 16
    assert min(tile.sw_lat for tile in tiles) == pytest.approx(box.sw_lat)
    assert max(tile.ne_lat for tile in tiles) == pytest.approx(box.ne_lat)
    assert min(tile.sw_lng for tile in tiles) == pytest.approx(box.sw_lng)
    assert max(tile.ne_lng for tile in tiles) == pytest.approx(box.ne_lng)

    total_area = sum(
        (tile.ne_lat - tile.sw_lat) * (tile.ne_lng - tile.sw_lng) for tile in tiles
    )
    box_area = (box.ne_lat - box.sw_lat) * (box.ne_lng - box.sw_lng)
    assert total_area == pytest.approx(box_area)


def test_tiling_rejects_invalid_grid():
    box = bounding_box(ORIGIN[0], ORIGIN[1], 10.0)
    with pytest.raises(ValueError):
        tile_bounding_box(box, 0)


def test_within_radius_includes_the_boundary():
    edge = destination_point(ORIGIN[0], ORIGIN[1], 90, 10.0)
    assert within_radius(ORIGIN, edge, 10.0)


@pytest.mark.parametrize(
    "value,expected",
    [(47.5, 47.5), ("47.5", 47.5), (None, None), ("abc", None), (True, None), (float("nan"), None)],
)
def test_parse_coordinate(value, expected):
    assert parse_coordinate(value) == expected
