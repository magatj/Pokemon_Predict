"""Recurring-interval detection.

Given the times a machine was seen dispensing, decide whether those events
repeat on a fixed cadence (30 / 60 / 90 / 120 minutes). An interval is only
reported once it clears both a sample-count and a support threshold - an
apparent rhythm in three data points is not a schedule.
"""
from __future__ import annotations

import statistics
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from pokevend.timeutil import minutes_between


def consecutive_gaps_minutes(timestamps: Sequence[datetime]) -> List[float]:
    """Gaps between consecutive positive events, in minutes."""
    ordered = sorted(timestamps)
    return [
        minutes_between(ordered[index], ordered[index - 1])
        for index in range(1, len(ordered))
    ]


def _matches_interval(gap: float, interval: int, tolerance: float) -> bool:
    """True when a gap is a near-multiple of the candidate interval.

    Multiples matter: if a machine runs hourly but nobody reported the 3pm
    event, the observed gap is 120 minutes and still supports a 60-minute
    cadence.
    """
    if interval <= 0 or gap < interval - tolerance:
        return False
    remainder = gap % interval
    return min(remainder, interval - remainder) <= tolerance


def detect_interval(
    timestamps: Sequence[datetime],
    candidates: Sequence[int] = (30, 60, 90, 120),
    tolerance_minutes: float = 4.0,
    min_samples: int = 4,
    min_support: float = 0.5,
) -> Optional[Dict[str, object]]:
    """Find the recurring interval that best explains the observed gaps.

    Returns None when no candidate clears ``min_support``, or when there are
    fewer than ``min_samples`` events to judge from.
    """
    if len(timestamps) < min_samples:
        return None
    gaps = consecutive_gaps_minutes(timestamps)
    if not gaps:
        return None

    median_gap = statistics.median(gaps)
    best: Optional[Dict[str, object]] = None

    for interval in candidates:
        matches = [gap for gap in gaps if _matches_interval(gap, interval, tolerance_minutes)]
        support = len(matches) / float(len(gaps))
        if support < min_support:
            continue
        candidate = {
            "intervalMinutes": int(interval),
            "support": round(support, 4),
            "sampleCount": len(timestamps),
            "matchedGaps": len(matches),
            "totalGaps": len(gaps),
            "medianGapMinutes": round(median_gap, 2),
        }
        if best is None:
            best = candidate
            continue
        # Equal support is common because longer gaps are multiples of shorter
        # candidates. Prefer the interval closest to the typical observed gap.
        better_support = candidate["support"] > best["support"]
        same_support = abs(candidate["support"] - best["support"]) < 1e-9
        closer = abs(interval - median_gap) < abs(int(best["intervalMinutes"]) - median_gap)
        if better_support or (same_support and closer):
            best = candidate

    return best


def interval_score(
    interval: Optional[Dict[str, object]],
    minutes_since_last_positive: Optional[float],
    tolerance_minutes: float = 4.0,
) -> float:
    """Score a candidate window against the detected cadence, in 0..1.

    Highest when the window lands where the next event is due.
    """
    if not interval or minutes_since_last_positive is None:
        return 0.0
    length = int(interval.get("intervalMinutes", 0))
    if length <= 0:
        return 0.0
    remainder = minutes_since_last_positive % length
    distance = min(remainder, length - remainder)
    if distance > tolerance_minutes:
        return 0.0
    proximity = 1.0 - (distance / float(tolerance_minutes + 1))
    return round(float(interval.get("support", 0.0)) * proximity, 4)
