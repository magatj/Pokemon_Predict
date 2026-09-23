"""Geographic maths: Haversine distance, bounding boxes and bbox tiling.

Distance filtering is always Haversine from the search centroid. City names are
never used to include or exclude a machine.
"""
from __future__ import annotations

import math
from typing import List, NamedTuple, Optional, Tuple

EARTH_RADIUS_MILES = 3958.7613

#: Fractional slack added to a bounding box so it strictly contains its circle.
BOX_PADDING_RATIO = 1e-9


class BoundingBox(NamedTuple):
    sw_lat: float
    sw_lng: float
    ne_lat: float
    ne_lng: float


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in statute miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat: float, lng: float, radius_miles: float) -> BoundingBox:
    """Smallest lat/lng box fully containing the radius circle."""
    lat_delta = math.degrees(radius_miles / EARTH_RADIUS_MILES)
    cos_lat = math.cos(math.radians(lat))
    # Guard against the poles, where longitude degrees collapse.
    cos_lat = max(cos_lat, 1e-6)
    lng_delta = math.degrees(radius_miles / (EARTH_RADIUS_MILES * cos_lat))
    # A mathematically exact box is tangent to the circle, so rounding can put a
    # point that is exactly on the radius a fraction outside it. The pad keeps
    # the box a strict superset; the Haversine filter still decides inclusion.
    lat_delta *= 1 + BOX_PADDING_RATIO
    lng_delta *= 1 + BOX_PADDING_RATIO
    return BoundingBox(lat - lat_delta, lng - lng_delta, lat + lat_delta, lng + lng_delta)


def tile_bounding_box(box: BoundingBox, grid: int) -> List[BoundingBox]:
    """Split a box into ``grid * grid`` sub-boxes.

    The locator API returns at most N machines per query, so a dense area is
    silently truncated. Tiling keeps each individual query under that cap;
    callers merge and de-duplicate the results by machine id.
    """
    if grid < 1:
        raise ValueError("grid must be >= 1")
    lat_step = (box.ne_lat - box.sw_lat) / grid
    lng_step = (box.ne_lng - box.sw_lng) / grid
    tiles = []
    for row in range(grid):
        for col in range(grid):
            tiles.append(
                BoundingBox(
                    box.sw_lat + row * lat_step,
                    box.sw_lng + col * lng_step,
                    box.sw_lat + (row + 1) * lat_step,
                    box.sw_lng + (col + 1) * lng_step,
                )
            )
    return tiles


def within_radius(
    origin: Tuple[float, float], point: Tuple[float, float], radius_miles: float,
    tolerance_miles: float = 1e-9,
) -> bool:
    """Inclusive radius test - a machine exactly on the boundary is included."""
    distance = haversine_miles(origin[0], origin[1], point[0], point[1])
    return distance <= radius_miles + tolerance_miles


def destination_point(lat: float, lng: float, bearing_degrees: float, distance_miles: float):
    """Point at a given bearing/distance. Used to build exact-distance tests."""
    angular = distance_miles / EARTH_RADIUS_MILES
    bearing = math.radians(bearing_degrees)
    phi1, lambda1 = math.radians(lat), math.radians(lng)
    phi2 = math.asin(
        math.sin(phi1) * math.cos(angular) + math.cos(phi1) * math.sin(angular) * math.cos(bearing)
    )
    lambda2 = lambda1 + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(phi1),
        math.cos(angular) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), math.degrees(lambda2)


def parse_coordinate(value) -> Optional[float]:
    """Coerce a source-supplied coordinate to float, or None if unusable."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(result) or math.isinf(result) else result
