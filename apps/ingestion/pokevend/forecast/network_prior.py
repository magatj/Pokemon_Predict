"""Network-level availability prior.

Most machines will never accumulate enough reports of their own to support a
machine-specific forecast. Showing nothing in that case wastes evidence that
does exist: across the wider region, community reports do carry a real
time-of-day and day-of-week signal.

So the engine backs off to the population pattern - ordinary shrinkage toward a
prior. The result is always reported as a *network* pattern, never as something
specific to the machine, and it is capped well below what genuine machine
history can earn.

Every report is used, including ones that could not be attributed to any
machine in the search radius: for a population-level rate, an unattributed
report from a neighbouring county is still a real observation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Sequence, Tuple

from pokevend.forecast.recency import weight_for
from pokevend.geo import haversine_miles
from pokevend.models import Observation
from pokevend.timeutil import parse_iso8601

LOGGER = logging.getLogger(__name__)

SCOPE_REGIONAL = "REGIONAL"
SCOPE_NETWORK = "NETWORK"


def approximate_local_time(moment: datetime, longitude: Optional[float]) -> datetime:
    """Approximate local time from longitude.

    Reports come from machines spread across several time zones, and a
    population rate over *local* hours is the only meaningful one. Without a
    coordinate-to-timezone database, longitude/15 is accurate to within an hour
    across the contiguous US, which is the resolution this prior works at.
    """
    if longitude is None:
        return moment
    offset_hours = int(round(longitude / 15.0))
    return moment.astimezone(timezone.utc) + timedelta(hours=offset_hours)


def _coordinates(observation: Observation) -> Tuple[Optional[float], Optional[float]]:
    extra = observation.extra or {}
    latitude = extra.get("latitude")
    longitude = extra.get("longitude")
    if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
        return float(latitude), float(longitude)
    return None, None


def build_network_prior(
    observations: Sequence[Observation],
    origin: Tuple[float, float],
    now: datetime,
    lambda_per_hour: float,
    regional_radius_miles: float = 250.0,
    min_regional_reports: int = 40,
    min_reports: int = 25,
    min_hour_samples: int = 8,
) -> Optional[Dict[str, Any]]:
    """Empirical in-stock rate by local hour and weekday.

    Prefers reports near the search area, falling back to every available
    report when the regional sample is too thin. Returns None when there is not
    enough evidence to say anything, in which case no prior is offered.
    """
    usable = []
    for observation in observations:
        moment = parse_iso8601(observation.effective_at)
        if moment is None:
            continue
        latitude, longitude = _coordinates(observation)
        distance = (
            haversine_miles(origin[0], origin[1], latitude, longitude)
            if latitude is not None
            else None
        )
        usable.append((observation, moment, longitude, distance))

    if not usable:
        return None

    regional = [row for row in usable if row[3] is not None and row[3] <= regional_radius_miles]
    if len(regional) >= min_regional_reports:
        selected, scope = regional, SCOPE_REGIONAL
    else:
        selected, scope = usable, SCOPE_NETWORK

    if len(selected) < min_reports:
        LOGGER.info(
            "network prior not offered: %s report(s) is below the %s minimum",
            len(selected), min_reports,
        )
        return None

    hour_buckets: Dict[int, list] = {}
    weekday_buckets: Dict[int, list] = {}
    positive_weight = 0.0
    total_weight = 0.0

    for observation, moment, longitude, _distance in selected:
        local = approximate_local_time(moment, longitude)
        weight = weight_for(moment, now, lambda_per_hour)
        # A population rate must not be dominated by whichever month had the
        # most reporting, so decay is floored rather than allowed to vanish.
        weight = max(weight, 0.05)
        positive = observation.is_positive()

        for buckets, key in ((hour_buckets, local.hour), (weekday_buckets, local.weekday())):
            entry = buckets.setdefault(key, [0.0, 0.0, 0])
            entry[1] += weight
            entry[2] += 1
            if positive:
                entry[0] += weight

        total_weight += weight
        if positive:
            positive_weight += weight

    base_rate = (positive_weight / total_weight) if total_weight else 0.0

    hour_rate = {}
    for hour, (positive, total, count) in hour_buckets.items():
        if count < min_hour_samples:
            continue  # too few reports in this hour to claim a rate
        hour_rate[hour] = positive / total if total else 0.0

    weekday_rate = {
        day: (positive / total if total else 0.0)
        for day, (positive, total, count) in weekday_buckets.items()
        if count >= max(min_hour_samples // 2, 3)
    }

    if not hour_rate and not weekday_rate:
        return None

    best_hour = max(hour_rate, key=lambda h: hour_rate[h]) if hour_rate else None

    return {
        "scope": scope,
        "sampleCount": len(selected),
        "machineCount": len(
            {o.machine_id or (o.extra or {}).get("latitude") for o, _, _, _ in selected}
        ),
        "positiveCount": sum(1 for o, _, _, _ in selected if o.is_positive()),
        "baseRate": round(base_rate, 4),
        "hourRate": {str(k): round(v, 4) for k, v in sorted(hour_rate.items())},
        "weekdayRate": {str(k): round(v, 4) for k, v in sorted(weekday_rate.items())},
        "bestHour": best_hour,
        "bestHourRate": round(hour_rate[best_hour], 4) if best_hour is not None else None,
        "regionalRadiusMiles": int(regional_radius_miles),
    }


def network_score(
    prior: Optional[Dict[str, Any]],
    local_hour: int,
    local_weekday: int,
    hour_weight: float = 0.7,
    weekday_weight: float = 0.3,
) -> float:
    """Blended population rate for a given local hour and weekday."""
    if not prior:
        return 0.0
    hour_rate = prior.get("hourRate", {}).get(str(local_hour))
    weekday_rate = prior.get("weekdayRate", {}).get(str(local_weekday))
    base = float(prior.get("baseRate", 0.0))

    hour_component = float(hour_rate) if hour_rate is not None else base
    weekday_component = float(weekday_rate) if weekday_rate is not None else base

    total = hour_weight + weekday_weight
    if total <= 0:
        return 0.0
    return (hour_component * hour_weight + weekday_component * weekday_weight) / total
