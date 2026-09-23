"""Observation normalization: machine matching and de-duplication."""
from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional, Tuple

from pokevend.models import Machine, Observation
from pokevend.timeutil import parse_iso8601

LOGGER = logging.getLogger(__name__)


class MachineMatcher:
    """Attributes free-text community reports to specific machines.

    Scoring is additive over the signals present in the text, capped at 1.0. A
    literal machine id is decisive; everything else is circumstantial and has to
    accumulate past ``min_confidence`` before the report may be used for
    machine-specific forecasting.
    """

    def __init__(self, machines: Iterable[Machine], matching_config: Optional[Dict] = None):
        self.machines = list(machines)
        config = matching_config or {}
        self.min_confidence = float(config.get("min_machine_match_confidence", 0.7))
        self.retailer_weight = float(config.get("retailer_weight", 0.35))
        self.city_weight = float(config.get("city_weight", 0.35))
        self.zip_weight = float(config.get("zip_weight", 0.20))
        self.alias_weight = float(config.get("alias_weight", 0.40))
        self.machine_id_weight = float(config.get("machine_id_weight", 1.0))
        self._by_id = {machine.id: machine for machine in self.machines}
        self._by_name = {
            (machine.name or "").upper(): machine for machine in self.machines if machine.name
        }

    def _score(self, machine: Machine, observation: Observation) -> float:
        haystack = " ".join(
            part for part in (observation.location_text, observation.retailer) if part
        ).lower()
        if not haystack:
            return 0.0

        score = 0.0
        retailer = (machine.retailer or "").lower()
        city = (machine.city or "").lower()
        zip_code = (machine.zip or "").strip()

        if retailer and retailer in haystack:
            score += self.retailer_weight
        if city and city in haystack:
            score += self.city_weight
        if zip_code and zip_code in haystack:
            score += self.zip_weight
        for alias in machine.aliases or []:
            if alias and alias in haystack:
                score += self.alias_weight
                break
        return min(score, 1.0)

    def match(self, observation: Observation) -> Tuple[Optional[str], float]:
        """Return the best (machine_id, confidence) for an observation.

        Confidence below ``min_confidence`` returns the machine id as None: the
        observation is still stored as area-level evidence, but it is not
        attributed to any single machine.
        """
        # A literal machine id or printed machine name is unambiguous.
        if observation.machine_id and observation.machine_id in self._by_id:
            return observation.machine_id, self.machine_id_weight
        if observation.machine_id and observation.machine_id.upper() in self._by_name:
            return self._by_name[observation.machine_id.upper()].id, self.machine_id_weight

        best_id, best_score = None, 0.0
        tied = False
        for machine in self.machines:
            score = self._score(machine, observation)
            if score > best_score:
                best_id, best_score, tied = machine.id, score, False
            elif score == best_score and score > 0 and machine.id != best_id:
                tied = True

        if tied:
            # Two machines fit equally well (e.g. two Safeways in one city).
            # Ambiguous evidence must not be attributed to either.
            LOGGER.debug("ambiguous machine match for observation %s", observation.id)
            return None, best_score * 0.5

        if best_score < self.min_confidence:
            return None, best_score
        return best_id, best_score


def deduplicate(observations: Iterable[Observation]) -> List[Observation]:
    """Collapse observations sharing a fingerprint.

    The same report reaches us more than once through re-crawls, cross-posts and
    mirrors. Keeping the strongest copy - and only one - stops a single event
    from being counted as several.
    """
    best: Dict[str, Observation] = {}
    for observation in observations:
        key = observation.fingerprint or observation.id
        if not key:
            continue
        incumbent = best.get(key)
        if incumbent is None:
            best[key] = observation
            continue
        # Prefer the copy with the strongest evidence, then the more precise
        # timestamp, then the higher machine-match confidence.
        candidate_rank = (
            observation.confidence,
            1 if observation.observed_at else 0,
            observation.machine_match_confidence,
        )
        incumbent_rank = (
            incumbent.confidence,
            1 if incumbent.observed_at else 0,
            incumbent.machine_match_confidence,
        )
        if candidate_rank > incumbent_rank:
            best[key] = observation

    ordered = sorted(best.values(), key=lambda obs: obs.effective_at or "")
    return ordered


def normalize_observations(
    observations: Iterable[Observation],
    machines: Iterable[Machine],
    matching_config: Optional[Dict] = None,
) -> List[Observation]:
    """Match observations to machines, then de-duplicate."""
    matcher = MachineMatcher(machines, matching_config)
    matched: List[Observation] = []

    for observation in observations:
        # First-party user reports already name their machine; trust them.
        if observation.source == "USER" and observation.machine_id:
            observation.machine_match_confidence = 1.0
            matched.append(observation)
            continue

        machine_id, confidence = matcher.match(observation)
        observation.machine_id = machine_id
        observation.machine_match_confidence = round(confidence, 3)
        matched.append(observation)

    return deduplicate(matched)


def observations_for_machine(
    observations: Iterable[Observation], machine_id: str, min_match_confidence: float = 0.7
) -> List[Observation]:
    """Observations confidently attributed to one machine, oldest first."""
    selected = [
        observation
        for observation in observations
        if observation.machine_id == machine_id
        and observation.machine_match_confidence >= min_match_confidence
    ]
    selected.sort(key=lambda obs: parse_iso8601(obs.effective_at) or parse_iso8601(obs.posted_at))
    return selected
