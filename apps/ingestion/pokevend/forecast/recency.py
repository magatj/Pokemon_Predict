"""Exponential recency weighting.

A machine's behaviour can change - a retailer moves it, restocking staff change
shift. Old evidence must therefore fade, so that when new observations
contradict an established pattern the new ones win.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional, Sequence

from pokevend.timeutil import hours_between


def recency_weight(age_hours: float, lambda_per_hour: float) -> float:
    """``exp(-lambda * age)``, clamped to (0, 1].

    A negative age (clock skew between sources) is treated as fresh rather than
    rewarded with a weight above 1.
    """
    if age_hours <= 0:
        return 1.0
    if lambda_per_hour <= 0:
        return 1.0
    return math.exp(-lambda_per_hour * age_hours)


def weight_for(observation_time: datetime, now: datetime, lambda_per_hour: float) -> float:
    return recency_weight(hours_between(now, observation_time), lambda_per_hour)


def weighted_values(
    timestamps: Sequence[datetime], now: datetime, lambda_per_hour: float
) -> Sequence[float]:
    return [weight_for(timestamp, now, lambda_per_hour) for timestamp in timestamps]


def recency_score(
    minutes_since_last_positive: Optional[float],
    reference_hours: float,
) -> float:
    """Freshness of the machine's most recent positive report, in 0..1.

    Decays linearly to zero across ``reference_hours``. A machine nobody has
    confirmed in days scores zero here regardless of its historical pattern.
    """
    if minutes_since_last_positive is None:
        return 0.0
    reference_minutes = max(reference_hours * 60.0, 1.0)
    if minutes_since_last_positive <= 0:
        return 1.0
    if minutes_since_last_positive >= reference_minutes:
        return 0.0
    return round(1.0 - (minutes_since_last_positive / reference_minutes), 4)
