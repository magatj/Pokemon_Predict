"""Minute-of-hour pattern detection.

Machines that dispense on a repeating schedule rarely do so at an exact minute:
reports cluster around one, e.g. :36 / :37 / :38. This module finds that
cluster on the circle of minutes (so :59 and :01 are two minutes apart, not
fifty-eight) and reports how much of the evidence it accounts for.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

MINUTES_PER_HOUR = 60


def circular_distance(left: int, right: int, modulus: int = MINUTES_PER_HOUR) -> int:
    """Shortest distance between two points on a circle of ``modulus`` slots."""
    raw = abs(left - right) % modulus
    return min(raw, modulus - raw)


def circular_mean(minutes: Sequence[int], weights: Optional[Sequence[float]] = None) -> float:
    """Weighted mean minute, computed on the circle so clusters spanning :00 work."""
    if not minutes:
        return 0.0
    if weights is None:
        weights = [1.0] * len(minutes)
    sin_total = sum(
        weight * math.sin(2 * math.pi * minute / MINUTES_PER_HOUR)
        for minute, weight in zip(minutes, weights)
    )
    cos_total = sum(
        weight * math.cos(2 * math.pi * minute / MINUTES_PER_HOUR)
        for minute, weight in zip(minutes, weights)
    )
    if abs(sin_total) < 1e-12 and abs(cos_total) < 1e-12:
        return float(minutes[0])
    angle = math.atan2(sin_total, cos_total)
    mean = angle * MINUTES_PER_HOUR / (2 * math.pi)
    return mean % MINUTES_PER_HOUR


def detect_minute_pattern(
    minutes: Sequence[int],
    tolerance: int = 3,
    min_samples: int = 4,
    weights: Optional[Sequence[float]] = None,
) -> Optional[Dict[str, object]]:
    """Find the dominant minute-of-hour cluster.

    ``minutes`` are the minute-of-hour values of positive observations.
    Returns None when there is too little evidence to claim a pattern, which is
    what keeps a two-report machine from being given a confident schedule.

    ``support`` is the share of total observation weight inside the cluster.
    """
    if not minutes or len(minutes) < min_samples:
        return None
    if weights is None:
        weights = [1.0] * len(minutes)
    total_weight = float(sum(weights))
    if total_weight <= 0:
        return None

    best_center: Optional[int] = None
    best_weight = -1.0
    best_members: List[int] = []

    for center in range(MINUTES_PER_HOUR):
        members = [
            (minute, weight)
            for minute, weight in zip(minutes, weights)
            if circular_distance(minute, center) <= tolerance
        ]
        cluster_weight = float(sum(weight for _, weight in members))
        # Ties break toward the tighter cluster, so the centre sits on the peak
        # rather than drifting to the first qualifying minute.
        if cluster_weight > best_weight or (
            cluster_weight == best_weight
            and members
            and _spread(members, center) < _spread(
                [(m, w) for m, w in zip(minutes, weights)
                 if circular_distance(m, best_center or 0) <= tolerance],
                best_center or 0,
            )
        ):
            best_center = center
            best_weight = cluster_weight
            best_members = members

    if best_center is None or not best_members:
        return None
    if len(best_members) < min_samples:
        return None

    member_minutes = [minute for minute, _ in best_members]
    member_weights = [weight for _, weight in best_members]
    pattern_minute = int(round(circular_mean(member_minutes, member_weights))) % MINUTES_PER_HOUR

    return {
        "patternMinute": pattern_minute,
        "toleranceMinutes": int(tolerance),
        "support": round(best_weight / total_weight, 4),
        "sampleCount": len(best_members),
        "totalSamples": len(minutes),
    }


def _spread(members, center: int) -> float:
    if not members:
        return float("inf")
    return sum(circular_distance(minute, center) * weight for minute, weight in members)


def minute_pattern_score(pattern: Optional[Dict[str, object]], minute: int) -> float:
    """How well a candidate minute fits a detected pattern, in 0..1.

    Falls off linearly across the tolerance band and is zero outside it, so a
    window on the pattern scores full marks and one nearby scores partially.
    """
    if not pattern:
        return 0.0
    tolerance = int(pattern.get("toleranceMinutes", 3)) or 1
    distance = circular_distance(int(minute), int(pattern.get("patternMinute", 0)))
    if distance > tolerance:
        return 0.0
    proximity = 1.0 - (distance / float(tolerance + 1))
    return round(float(pattern.get("support", 0.0)) * proximity, 4)
