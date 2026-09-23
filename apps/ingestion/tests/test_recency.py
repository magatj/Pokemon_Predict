"""Exponential recency decay and freshness scoring."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from pokevend.forecast.features import build_features
from pokevend.forecast.recency import recency_score, recency_weight, weight_for
from pokevend.models import Availability
from tests.conftest import make_observation

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
LAMBDA = 0.0058


def test_weight_decays_with_age():
    fresh = recency_weight(0, LAMBDA)
    day = recency_weight(24, LAMBDA)
    week = recency_weight(24 * 7, LAMBDA)

    assert fresh == 1.0
    assert fresh > day > week > 0


def test_weight_matches_the_exponential_formula():
    assert recency_weight(100, LAMBDA) == pytest.approx(math.exp(-LAMBDA * 100))


def test_half_life_is_about_five_days():
    half_life_hours = math.log(2) / LAMBDA
    assert recency_weight(half_life_hours, LAMBDA) == pytest.approx(0.5, abs=1e-9)
    assert half_life_hours / 24 == pytest.approx(5.0, abs=0.3)


def test_future_timestamps_are_not_rewarded():
    """Clock skew between sources must not produce a weight above 1."""
    assert recency_weight(-50, LAMBDA) == 1.0


def test_zero_lambda_disables_decay():
    assert recency_weight(10_000, 0.0) == 1.0


def test_weight_for_uses_the_elapsed_time():
    older = NOW - timedelta(hours=48)
    newer = NOW - timedelta(hours=1)
    assert weight_for(newer, NOW, LAMBDA) > weight_for(older, NOW, LAMBDA)


# -- freshness score -----------------------------------------------------

def test_recency_score_falls_to_zero_across_the_reference_window():
    assert recency_score(0, 72) == 1.0
    assert recency_score(72 * 60, 72) == 0.0
    assert 0 < recency_score(36 * 60, 72) < 1


def test_recency_score_without_history_is_zero():
    assert recency_score(None, 72) == 0.0


# -- contradiction handling ----------------------------------------------

def test_new_observations_override_a_stale_pattern():
    """An old :37 rhythm must yield to fresh contradicting evidence.

    The machine used to dispense at :37; for the last day it has only been seen
    at :05. The fresh cluster has to win, or the forecast would keep predicting
    behaviour the machine has stopped exhibiting.
    """
    old = [
        make_observation(
            observation_id=f"old{index}",
            when=NOW - timedelta(days=20, hours=index) + timedelta(minutes=37),
            availability=Availability.AVAILABLE,
        )
        for index in range(12)
    ]
    recent = [
        make_observation(
            observation_id=f"new{index}",
            when=NOW - timedelta(hours=index) + timedelta(minutes=5),
            availability=Availability.AVAILABLE,
        )
        for index in range(12)
    ]

    features = build_features("rec1", old + recent, now=NOW, lambda_per_hour=LAMBDA,
                              timezone_name="UTC")

    assert features.minute_pattern is not None
    assert features.minute_pattern["patternMinute"] == 5


def test_without_decay_the_old_pattern_would_still_dominate():
    """Control for the test above: decay is what produces the switch."""
    old = [
        make_observation(
            observation_id=f"old{index}",
            when=NOW - timedelta(days=20, hours=index) + timedelta(minutes=37),
        )
        for index in range(20)
    ]
    recent = [
        make_observation(
            observation_id=f"new{index}",
            when=NOW - timedelta(hours=index) + timedelta(minutes=5),
        )
        for index in range(12)
    ]

    undecayed = build_features("rec1", old + recent, now=NOW, lambda_per_hour=0.0,
                               timezone_name="UTC")
    decayed = build_features("rec1", old + recent, now=NOW, lambda_per_hour=LAMBDA,
                             timezone_name="UTC")

    assert undecayed.minute_pattern["patternMinute"] == 37
    assert decayed.minute_pattern["patternMinute"] == 5
