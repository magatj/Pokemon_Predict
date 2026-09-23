"""Per-machine feature extraction.

Everything the scoring model reads is computed here from observations, so the
engine itself stays a simple weighted sum over named, inspectable features.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Sequence

from pokevend.forecast.interval import detect_interval
from pokevend.forecast.minute_pattern import detect_minute_pattern
from pokevend.forecast.recency import weight_for
from pokevend.localtime import to_local
from pokevend.models import Availability, Observation
from pokevend.timeutil import hours_between, minutes_between, parse_iso8601


class MachineFeatures:
    """Feature bundle for one machine at one point in time."""

    def __init__(self, machine_id: str):
        self.machine_id = machine_id
        self.observation_count = 0
        self.positive_count = 0
        self.negative_count = 0
        self.purchase_count = 0
        self.total_weight = 0.0

        self.minutes_since_last_available: Optional[float] = None
        self.minutes_since_last_not_available: Optional[float] = None
        self.minutes_since_last_purchase: Optional[float] = None
        self.minutes_since_suspected_restock: Optional[float] = None
        self.minutes_since_last_positive: Optional[float] = None

        self.minute_pattern: Optional[Dict[str, object]] = None
        self.interval: Optional[Dict[str, object]] = None

        #: weighted positive rate keyed by local hour / weekday / (weekday, hour)
        self.hour_hit_rate: Dict[int, float] = {}
        self.weekday_hit_rate: Dict[int, float] = {}
        self.weekday_hour_hit_rate: Dict[str, float] = {}

        self.nearby: Optional[Dict[str, object]] = None
        self.mean_source_confidence = 0.0
        self.mean_match_confidence = 0.0
        self.last_observation_at: Optional[str] = None
        #: The most recent observation itself. Surfaced even when there is too
        #: little history to forecast, because "sold out, seen 4 months ago" is
        #: real information and a bare INSUFFICIENT_DATA is not.
        self.last_known_status: Optional[Dict[str, object]] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "machineId": self.machine_id,
            "observationCount": self.observation_count,
            "positiveCount": self.positive_count,
            "negativeCount": self.negative_count,
            "purchaseCount": self.purchase_count,
            "totalWeight": round(self.total_weight, 4),
            "minutesSinceLastAvailable": _round_opt(self.minutes_since_last_available),
            "minutesSinceLastNotAvailable": _round_opt(self.minutes_since_last_not_available),
            "minutesSinceLastPurchase": _round_opt(self.minutes_since_last_purchase),
            "minutesSinceSuspectedRestock": _round_opt(self.minutes_since_suspected_restock),
            "minutesSinceLastPositive": _round_opt(self.minutes_since_last_positive),
            "minutePattern": self.minute_pattern,
            "interval": self.interval,
            "hourHitRate": {str(k): round(v, 4) for k, v in self.hour_hit_rate.items()},
            "weekdayHitRate": {str(k): round(v, 4) for k, v in self.weekday_hit_rate.items()},
            "weekdayHourHitRate": {k: round(v, 4) for k, v in self.weekday_hour_hit_rate.items()},
            "nearby": self.nearby,
            "meanSourceConfidence": round(self.mean_source_confidence, 4),
            "meanMatchConfidence": round(self.mean_match_confidence, 4),
            "lastObservationAt": self.last_observation_at,
            "lastKnownStatus": self.last_known_status,
        }


def _round_opt(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 1)


def _weighted_rate(buckets: Dict[object, List[float]]) -> Dict[object, float]:
    """Positive weight over total weight, per bucket."""
    rates = {}
    for key, (positive, total) in buckets.items():
        rates[key] = (positive / total) if total > 0 else 0.0
    return rates


def build_features(
    machine_id: str,
    observations: Sequence[Observation],
    now: datetime,
    lambda_per_hour: float,
    timezone_name: str = "America/Los_Angeles",
    minute_tolerance: int = 3,
    minute_min_samples: int = 4,
    interval_candidates: Sequence[int] = (30, 60, 90, 120),
    interval_tolerance: float = 4.0,
    interval_min_samples: int = 4,
    interval_min_support: float = 0.5,
) -> MachineFeatures:
    """Compute every model input for one machine.

    Each observation contributes ``source confidence x match confidence x
    recency decay``, so a stale, weakly-matched community post moves the
    numbers far less than a fresh confirmed purchase.
    """
    features = MachineFeatures(machine_id)
    if not observations:
        return features

    hour_buckets: Dict[object, List[float]] = {}
    weekday_buckets: Dict[object, List[float]] = {}
    weekday_hour_buckets: Dict[object, List[float]] = {}

    positive_minutes: List[int] = []
    positive_weights: List[float] = []
    positive_times: List[datetime] = []

    confidences: List[float] = []
    match_confidences: List[float] = []
    latest: Optional[datetime] = None
    latest_observation: Optional[Observation] = None

    for observation in observations:
        timestamp = parse_iso8601(observation.effective_at)
        if timestamp is None:
            continue

        local = to_local(timestamp, timezone_name)
        decay = weight_for(timestamp, now, lambda_per_hour)
        weight = max(observation.confidence, 0.0) * max(
            observation.machine_match_confidence, 0.0
        ) * decay

        features.observation_count += 1
        features.total_weight += weight
        confidences.append(observation.confidence)
        match_confidences.append(observation.machine_match_confidence)

        if latest is None or timestamp > latest:
            latest = timestamp
            latest_observation = observation

        age_minutes = minutes_between(now, timestamp)
        positive = observation.is_positive()

        if positive:
            features.positive_count += 1
            positive_minutes.append(local.minute)
            positive_weights.append(weight)
            positive_times.append(timestamp)
            features.minutes_since_last_positive = _min_opt(
                features.minutes_since_last_positive, age_minutes
            )
            if observation.availability == Availability.AVAILABLE:
                features.minutes_since_last_available = _min_opt(
                    features.minutes_since_last_available, age_minutes
                )
            if observation.availability == Availability.RESTOCK:
                features.minutes_since_suspected_restock = _min_opt(
                    features.minutes_since_suspected_restock, age_minutes
                )
        else:
            features.negative_count += 1
            features.minutes_since_last_not_available = _min_opt(
                features.minutes_since_last_not_available, age_minutes
            )

        if observation.purchase_confirmed:
            features.purchase_count += 1
            features.minutes_since_last_purchase = _min_opt(
                features.minutes_since_last_purchase, age_minutes
            )

        for buckets, key in (
            (hour_buckets, local.hour),
            (weekday_buckets, local.weekday()),
            (weekday_hour_buckets, f"{local.weekday()}:{local.hour}"),
        ):
            entry = buckets.setdefault(key, [0.0, 0.0])
            entry[1] += weight
            if positive:
                entry[0] += weight

    features.minute_pattern = detect_minute_pattern(
        positive_minutes,
        tolerance=minute_tolerance,
        min_samples=minute_min_samples,
        weights=positive_weights,
    )
    features.interval = detect_interval(
        positive_times,
        candidates=interval_candidates,
        tolerance_minutes=interval_tolerance,
        min_samples=interval_min_samples,
        min_support=interval_min_support,
    )

    features.hour_hit_rate = _weighted_rate(hour_buckets)
    features.weekday_hit_rate = _weighted_rate(weekday_buckets)
    features.weekday_hour_hit_rate = _weighted_rate(weekday_hour_buckets)
    features.mean_source_confidence = (
        sum(confidences) / len(confidences) if confidences else 0.0
    )
    features.mean_match_confidence = (
        sum(match_confidences) / len(match_confidences) if match_confidences else 0.0
    )
    if latest is not None:
        from pokevend.timeutil import to_iso8601

        features.last_observation_at = to_iso8601(latest)

    if latest_observation is not None:
        features.last_known_status = {
            "availability": latest_observation.availability,
            "observedAt": features.last_observation_at,
            "source": latest_observation.source,
            "sourceUrl": latest_observation.source_url,
            "evidenceClass": latest_observation.evidence_class,
            "product": latest_observation.product,
            "purchaseConfirmed": latest_observation.purchase_confirmed,
            "ageHours": round(hours_between(now, latest), 1),
        }
    return features


def _min_opt(current: Optional[float], candidate: float) -> float:
    if candidate < 0:
        # Observation is in the future relative to `now`; treat as just-now.
        candidate = 0.0
    return candidate if current is None else min(current, candidate)
