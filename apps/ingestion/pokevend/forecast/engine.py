"""Explainable weighted-scoring forecast engine.

The question being answered is *"when can this machine next successfully
dispense a Pokemon product?"* - not "when was it physically restocked". Every
number below traces back to named features and to weights in
forecast_config.yaml.

A machine under the configured minimum observation count is reported as
INSUFFICIENT_DATA and given no probability at all. Inventing a plausible
percentage from three data points would be worse than saying nothing.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence

from pokevend.config import ForecastConfig
from pokevend.forecast.features import MachineFeatures, build_features
from pokevend.forecast.interval import interval_score
from pokevend.forecast.minute_pattern import minute_pattern_score
from pokevend.forecast.nearby import nearby_activity, nearby_score
from pokevend.forecast.network_prior import build_network_prior, network_score
from pokevend.forecast.recency import recency_score
from pokevend.localtime import to_local
from pokevend.models import Machine, Observation
from pokevend.normalizers.observation_normalizer import observations_for_machine
from pokevend.timeutil import floor_to_minute, now_utc, to_iso8601

STATUS_OK = "OK"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
#: Scored from the regional/network population rate, not this machine's own
#: history. Always presented as a network pattern and capped low.
STATUS_NETWORK_PATTERN = "NETWORK_PATTERN"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"

#: Human labels for feature strengths shown in the "why this prediction" panel.
_STRENGTH_BANDS = ((0.66, "Strong"), (0.33, "Moderate"), (0.0, "Weak"))


def _strength_label(value: float) -> str:
    for threshold, label in _STRENGTH_BANDS:
        if value >= threshold:
            return label
    return "None"


class ForecastEngine:
    def __init__(self, config: ForecastConfig, network_prior: Optional[Dict[str, object]] = None):
        self.config = config
        self.weights = config.scoring_weights
        self.network_prior = network_prior

    # -- candidate windows ------------------------------------------------
    def candidate_windows(self, now: datetime) -> List[datetime]:
        """Window start times across the forecast horizon.

        Starts are aligned to the window size so the same clock windows recur,
        which is what makes a minute-of-hour pattern legible.
        """
        size = self.config.window_minutes
        horizon = self.config.horizon_hours * 60
        start = floor_to_minute(now)
        aligned_minute = (start.minute // size) * size
        start = start.replace(minute=aligned_minute)
        if start <= now:
            start = start + timedelta(minutes=size)
        return [start + timedelta(minutes=offset) for offset in range(0, horizon, size)]

    # -- scoring ----------------------------------------------------------
    def score_window(
        self, features: MachineFeatures, window_start: datetime, now: datetime
    ) -> Dict[str, object]:
        """Score one candidate window, returning the component breakdown."""
        local = to_local(window_start, self.config.timezone_name)
        minutes_ahead = (window_start - now).total_seconds() / 60.0

        minute_component = minute_pattern_score(features.minute_pattern, local.minute)

        projected_since_positive = (
            None
            if features.minutes_since_last_positive is None
            else features.minutes_since_last_positive + minutes_ahead
        )
        interval_component = interval_score(
            features.interval,
            projected_since_positive,
            tolerance_minutes=self.config.interval_tolerance_minutes,
        )

        historical_component = features.hour_hit_rate.get(local.hour, 0.0)
        recency_component = recency_score(
            features.minutes_since_last_positive, self.config.recency_reference_hours
        )
        weekday_hour_component = features.weekday_hour_hit_rate.get(
            f"{local.weekday()}:{local.hour}", 0.0
        )
        nearby_component = nearby_score(features.nearby)

        components = {
            "minute_pattern": minute_component,
            "interval": interval_component,
            "historical_hit_rate": historical_component,
            "recency": recency_component,
            "weekday_hour": weekday_hour_component,
            "nearby_activity": nearby_component,
        }

        raw_score = sum(
            float(self.weights.get(name, 0.0)) * float(value)
            for name, value in components.items()
        )

        sample_scale = self._sample_scale(features.observation_count)
        source_scale = self._source_scale(features)
        horizon_scale = self._horizon_scale(minutes_ahead)
        score = raw_score * sample_scale * source_scale * horizon_scale

        return {
            "windowStart": to_iso8601(window_start),
            "windowEnd": to_iso8601(window_start + timedelta(
                minutes=self.config.window_minutes)),
            "localTime": local.strftime("%H:%M"),
            "probability": round(min(max(score, 0.0), 1.0), 4),
            "rawScore": round(raw_score, 4),
            "sampleScale": round(sample_scale, 4),
            "sourceScale": round(source_scale, 4),
            "horizonScale": round(horizon_scale, 4),
            "minutesAhead": round(minutes_ahead, 1),
            "components": {key: round(float(value), 4) for key, value in components.items()},
        }

    def network_windows(self, now: datetime) -> List[datetime]:
        """One window per upcoming local hour.

        The prior only resolves to the hour, so emitting five-minute windows
        would imply a precision it does not have.
        """
        start = floor_to_minute(now).replace(minute=0)
        return [
            start + timedelta(hours=offset)
            for offset in range(1, self.config.horizon_hours + 1)
        ]

    def score_network_window(self, window_start: datetime, now: datetime) -> Dict[str, object]:
        """Score a window from the population rate alone.

        No machine-specific feature contributes here, so the output is labelled
        NETWORK, spans a whole hour, and is capped at
        network_prior.max_probability.
        """
        local = to_local(window_start, self.config.timezone_name)
        minutes_ahead = (window_start - now).total_seconds() / 60.0

        rate = network_score(
            self.network_prior,
            local.hour,
            local.weekday(),
            hour_weight=self.config.network_hour_weight,
            weekday_weight=self.config.network_weekday_weight,
        )
        horizon_scale = self._horizon_scale(minutes_ahead)
        probability = min(rate * horizon_scale, self.config.network_max_probability)

        return {
            "windowStart": to_iso8601(window_start),
            # A whole hour, because that is the prior's resolution.
            "windowEnd": to_iso8601(window_start + timedelta(hours=1)),
            "localTime": local.strftime("%H:%M"),
            "probability": round(max(probability, 0.0), 4),
            "rawScore": round(rate, 4),
            "sampleScale": 0.0,
            "sourceScale": 0.0,
            "horizonScale": round(horizon_scale, 4),
            "minutesAhead": round(minutes_ahead, 1),
            "basis": "NETWORK",
            "components": {"network_rate": round(rate, 4)},
        }

    def _network_forecast(self, features: MachineFeatures, now: datetime) -> Dict[str, object]:
        """Build the network-pattern fallback for a machine without history."""
        prior = self.network_prior or {}
        scored = [
            self.score_network_window(start, now) for start in self.network_windows(now)
        ]
        ranked = sorted(
            [window for window in scored if window["probability"] > 0],
            key=lambda window: (-float(window["probability"]), window["windowStart"]),
        )[: self.config.max_windows_per_machine]

        if prior.get("scope") == "REGIONAL":
            scope = f"within {prior.get('regionalRadiusMiles')} miles"
        else:
            scope = "across the tracked network"

        reasons = [
            f"This machine has {features.observation_count} report(s) of its own"
            " - not enough for a machine-specific forecast.",
            f"Showing the pattern from {prior.get('sampleCount')} community"
            f" report(s) {scope}.",
        ]
        if prior.get("bestHour") is not None:
            reasons.append(
                "Product was most often found in stock around {:02d}:00 local "
                "time ({:.0%} of reports in that hour).".format(
                    int(prior["bestHour"]), float(prior.get("bestHourRate") or 0.0)
                )
            )

        explanation = {
            "reasons": reasons,
            "signals": {
                "basis": "Network pattern",
                "networkReports": str(prior.get("sampleCount", 0)),
                "machineReports": str(features.observation_count),
                "scope": str(prior.get("scope", "NETWORK")),
            },
            "reportsUsed": int(prior.get("sampleCount", 0)),
        }
        for window in ranked:
            window["explanation"] = explanation

        return {
            "status": STATUS_NETWORK_PATTERN,
            "confidence": CONFIDENCE_LOW,
            "windows": ranked,
            "next": ranked[0] if ranked else None,
            "networkPrior": prior,
            "explanation": explanation,
        }

    def _sample_scale(self, observation_count: int) -> float:
        """Shrink scores toward zero when the sample is small."""
        full = max(self.config.full_confidence_observations, 1)
        scale = observation_count / float(full)
        floor = self.config.sample_scale_floor
        return min(1.0, max(scale, floor)) if observation_count else 0.0

    def _horizon_scale(self, minutes_ahead: float) -> float:
        """Discount windows further into the future.

        The same pattern supports a window an hour out and one six hours out,
        but far more can change before the later one arrives, so it should not
        be presented with equal weight.
        """
        if minutes_ahead <= 0:
            return 1.0
        decay = self.config.horizon_decay_per_hour
        if decay <= 0:
            return 1.0
        return math.exp(-decay * (minutes_ahead / 60.0))

    def _source_scale(self, features: MachineFeatures) -> float:
        """Discount machines whose evidence is weak or loosely matched."""
        if features.observation_count == 0:
            return 0.0
        confidence = max(features.mean_source_confidence, 0.0)
        match = max(features.mean_match_confidence, 0.0)
        return min(1.0, 0.5 + 0.5 * (confidence * match))

    def confidence_band(self, features: MachineFeatures, probability: float) -> str:
        high, medium = self.config.confidence_bands
        ratio = features.observation_count / float(
            max(self.config.high_confidence_observations, 1)
        )
        combined = min(1.0, ratio) * 0.6 + probability * 0.4
        if combined >= high:
            return CONFIDENCE_HIGH
        if combined >= medium:
            return CONFIDENCE_MEDIUM
        return CONFIDENCE_LOW

    # -- explanation ------------------------------------------------------
    def explain(self, features: MachineFeatures, window: Dict[str, object]) -> Dict[str, object]:
        """Human-readable justification for one window."""
        components = window.get("components", {})
        reasons: List[str] = []

        pattern = features.minute_pattern
        if pattern:
            reasons.append(
                "{} of {} recent positive observations fell near :{:02d} past the hour.".format(
                    pattern.get("sampleCount"),
                    pattern.get("totalSamples"),
                    int(pattern.get("patternMinute", 0)),
                )
            )
        if features.interval:
            reasons.append(
                "Most common interval between positive reports: {} minutes "
                "(support {:.0%}).".format(
                    features.interval.get("intervalMinutes"),
                    float(features.interval.get("support", 0.0)),
                )
            )
        if features.minutes_since_last_purchase is not None:
            reasons.append(
                "Last confirmed purchase was "
                f"{features.minutes_since_last_purchase:.0f} minutes ago."
            )
        if features.nearby and features.nearby.get("activeMachineIds"):
            reasons.append(
                "{} nearby machine(s) reported product in the last {} minutes.".format(
                    len(features.nearby.get("activeMachineIds") or []),
                    features.nearby.get("windowMinutes"),
                )
            )
        if not reasons:
            reasons.append("Scored from overall observation history; no repeating pattern found.")

        return {
            "reasons": reasons,
            "signals": {
                "minutePattern": _strength_label(float(components.get("minute_pattern", 0.0))),
                "interval": _strength_label(float(components.get("interval", 0.0))),
                "historicalHits": f"{features.positive_count}/{features.observation_count}",
                "recentActivity": _strength_label(float(components.get("recency", 0.0))),
                "nearbyActivity": _strength_label(
                    float(components.get("nearby_activity", 0.0))
                ),
                "sampleConfidence": _strength_label(float(window.get("sampleScale", 0.0))),
            },
            "reportsUsed": features.observation_count,
        }

    # -- machine forecast -------------------------------------------------
    def forecast_machine(
        self,
        machine: Machine,
        observations: Sequence[Observation],
        machines: Sequence[Machine],
        all_observations: Sequence[Observation],
        now: Optional[datetime] = None,
    ) -> Dict[str, object]:
        now = now or now_utc()
        features = build_features(
            machine.id,
            observations,
            now=now,
            lambda_per_hour=self.config.recency_lambda_per_hour,
            timezone_name=self.config.timezone_name,
            minute_tolerance=self.config.minute_tolerance,
            minute_min_samples=self.config.minute_pattern_min_samples,
            interval_candidates=self.config.interval_candidates,
            interval_tolerance=self.config.interval_tolerance_minutes,
            interval_min_samples=self.config.interval_min_samples,
            interval_min_support=self.config.interval_min_support,
        )
        features.nearby = nearby_activity(
            machine,
            machines,
            all_observations,
            now=now,
            radii_miles=self.config.nearby_radii_miles,
            window_minutes=self.config.nearby_window_minutes,
        )

        base = {
            "machineId": machine.id,
            "generatedAt": to_iso8601(now),
            "windowMinutes": self.config.window_minutes,
            "observationCount": features.observation_count,
            "minimumObservations": self.config.minimum_observations,
            "features": features.to_dict(),
        }

        if features.observation_count < self.config.minimum_observations:
            if self.config.network_prior_enabled and self.network_prior:
                base.update(self._network_forecast(features, now))
                return base
            base.update(
                {
                    "status": STATUS_INSUFFICIENT_DATA,
                    "confidence": CONFIDENCE_LOW,
                    "windows": [],
                    "next": None,
                    "explanation": {
                        "reasons": [
                            f"{features.observation_count} of "
                            f"{self.config.minimum_observations} observations "
                            "collected. Forecasting starts once the minimum "
                            "sample is reached."
                        ],
                        "signals": {},
                        "reportsUsed": features.observation_count,
                    },
                }
            )
            return base

        scored = [
            self.score_window(features, window_start, now)
            for window_start in self.candidate_windows(now)
        ]
        # Rank by probability, then by how soon the window arrives.
        ranked = sorted(
            [window for window in scored if window["probability"] > 0],
            key=lambda window: (-float(window["probability"]), window["windowStart"]),
        )[: self.config.max_windows_per_machine]

        for window in ranked:
            window["explanation"] = self.explain(features, window)

        next_window = ranked[0] if ranked else None
        probability = float(next_window["probability"]) if next_window else 0.0

        base.update(
            {
                "status": STATUS_OK,
                "confidence": self.confidence_band(features, probability),
                "windows": ranked,
                "next": next_window,
                "explanation": self.explain(features, next_window or {"components": {}}),
            }
        )
        return base


def forecast_all(
    config: ForecastConfig,
    machines: Sequence[Machine],
    observations: Sequence[Observation],
    now: Optional[datetime] = None,
    origin: Optional[tuple] = None,
) -> List[Dict[str, object]]:
    """Forecast every machine, in the same order they were given.

    The network prior is computed once from every observation - including ones
    that could not be attributed to a machine in range, which are still real
    reports for a population-level rate.
    """
    now = now or now_utc()

    prior = None
    if config.network_prior_enabled:
        centre = origin or config.fallback_centroid
        prior = build_network_prior(
            observations,
            origin=centre,
            now=now,
            lambda_per_hour=config.recency_lambda_per_hour,
            regional_radius_miles=config.network_regional_radius_miles,
            min_regional_reports=config.network_min_regional_reports,
            min_reports=config.network_min_reports,
            min_hour_samples=config.network_min_hour_samples,
        )

    engine = ForecastEngine(config, network_prior=prior)
    results = []
    for machine in machines:
        machine_observations = observations_for_machine(
            observations, machine.id, config.min_machine_match_confidence
        )
        results.append(
            engine.forecast_machine(
                machine, machine_observations, machines, observations, now=now
            )
        )
    return results
