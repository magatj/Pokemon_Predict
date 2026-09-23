"""Network-level prior: the fallback for machines without their own history."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pokevend.forecast.engine import (
    STATUS_INSUFFICIENT_DATA,
    STATUS_NETWORK_PATTERN,
    STATUS_OK,
    ForecastEngine,
    forecast_all,
)
from pokevend.forecast.network_prior import (
    approximate_local_time,
    build_network_prior,
    network_score,
)
from pokevend.models import Availability
from tests.conftest import (
    ORIGIN,
    hourly_positives,
    make_machine,
    make_observation,
    minimal_forecast_config,
)

NOW = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)
LAMBDA = 0.0058


def regional_observation(index, hour, positive, lat=47.3, lng=-122.2, days_ago=10):
    """A report from a machine near the search area at a given local hour."""
    # ORIGIN sits at roughly UTC-8, so shift the local hour back into UTC.
    when = (NOW - timedelta(days=days_ago)).replace(
        hour=(hour + 8) % 24, minute=0, second=0, microsecond=0
    )
    observation = make_observation(
        observation_id=f"net{index}",
        machine_id=None,
        when=when,
        availability=Availability.AVAILABLE if positive else Availability.NOT_AVAILABLE,
        source="PUBLIC_WEB",
    )
    observation.extra = {"latitude": lat, "longitude": lng}
    return observation


def sample(positives_at_hour=13, count=60):
    """A population where one hour is clearly better than the rest."""
    observations = []
    for index in range(count):
        hour = positives_at_hour if index % 3 == 0 else (index % 24)
        positive = index % 3 == 0
        observations.append(regional_observation(index, hour, positive))
    return observations


# -- prior construction --------------------------------------------------

def test_prior_is_built_from_enough_regional_reports():
    prior = build_network_prior(sample(), ORIGIN, NOW, LAMBDA, min_regional_reports=40)

    assert prior is not None
    assert prior["scope"] == "REGIONAL"
    assert prior["sampleCount"] == 60


def test_prior_finds_the_hour_with_the_highest_in_stock_rate():
    prior = build_network_prior(sample(positives_at_hour=13), ORIGIN, NOW, LAMBDA)
    assert prior["bestHour"] == 13
    assert prior["bestHourRate"] > prior["baseRate"]


def test_too_few_reports_yields_no_prior():
    few = sample(count=10)
    assert build_network_prior(few, ORIGIN, NOW, LAMBDA, min_reports=25) is None


def test_hours_below_the_sample_floor_are_not_given_a_rate():
    prior = build_network_prior(sample(), ORIGIN, NOW, LAMBDA, min_hour_samples=100)
    assert prior is None or prior["hourRate"] == {}


def test_distant_reports_fall_back_to_network_scope():
    """With too few nearby reports, the wider sample is used and labelled so."""
    far = [
        regional_observation(index, 13, index % 3 == 0, lat=40.7, lng=-74.0)
        for index in range(60)
    ]
    prior = build_network_prior(far, ORIGIN, NOW, LAMBDA, min_regional_reports=40)

    assert prior["scope"] == "NETWORK"


def test_unattributed_reports_still_count():
    """A report we could not tie to a machine is still a real observation."""
    observations = sample()
    assert all(o.machine_id is None for o in observations)
    assert build_network_prior(observations, ORIGIN, NOW, LAMBDA) is not None


def test_observations_without_coordinates_do_not_crash_the_prior():
    observations = sample()
    for observation in observations[:10]:
        observation.extra = {}
    assert build_network_prior(observations, ORIGIN, NOW, LAMBDA) is not None


@pytest.mark.parametrize("longitude,expected_offset", [(-122.0, -8), (-74.0, -5), (None, 0)])
def test_approximate_local_time_uses_longitude(longitude, expected_offset):
    moment = datetime(2026, 9, 23, 20, 0, tzinfo=timezone.utc)
    local = approximate_local_time(moment, longitude)
    assert local.hour == (20 + expected_offset) % 24


# -- scoring -------------------------------------------------------------

def test_score_prefers_the_best_hour():
    prior = build_network_prior(sample(positives_at_hour=13), ORIGIN, NOW, LAMBDA)
    best = network_score(prior, 13, 2)
    other = network_score(prior, 3, 2)
    assert best > other


def test_score_without_a_prior_is_zero():
    assert network_score(None, 13, 2) == 0.0


def test_unknown_hour_falls_back_to_the_base_rate():
    prior = build_network_prior(sample(), ORIGIN, NOW, LAMBDA)
    assert network_score(prior, 3, 2) > 0


# -- engine integration --------------------------------------------------

def test_machine_without_history_gets_a_network_pattern():
    config = minimal_forecast_config()
    machine = make_machine()
    engine = ForecastEngine(
        config, network_prior=build_network_prior(sample(), ORIGIN, NOW, LAMBDA)
    )

    result = engine.forecast_machine(machine, [], [machine], [], now=NOW)

    assert result["status"] == STATUS_NETWORK_PATTERN
    assert result["windows"]
    assert result["confidence"] == "LOW"


def test_network_windows_are_hour_resolution():
    """The prior resolves to the hour, so windows must not imply minutes."""
    from pokevend.timeutil import parse_iso8601

    config = minimal_forecast_config()
    machine = make_machine()
    engine = ForecastEngine(
        config, network_prior=build_network_prior(sample(), ORIGIN, NOW, LAMBDA)
    )
    result = engine.forecast_machine(machine, [], [machine], [], now=NOW)

    for window in result["windows"]:
        span = parse_iso8601(window["windowEnd"]) - parse_iso8601(window["windowStart"])
        assert span == timedelta(hours=1)
        assert window["localTime"].endswith(":00")


def test_network_probability_is_capped():
    config = minimal_forecast_config(network_prior={"max_probability": 0.2})
    machine = make_machine()
    # A population where every report is positive would otherwise score 1.0.
    always = [regional_observation(i, 13, True) for i in range(60)]
    engine = ForecastEngine(
        config, network_prior=build_network_prior(always, ORIGIN, NOW, LAMBDA)
    )

    result = engine.forecast_machine(machine, [], [machine], [], now=NOW)
    assert all(window["probability"] <= 0.2 for window in result["windows"])


def test_network_windows_are_marked_as_network_basis():
    config = minimal_forecast_config()
    machine = make_machine()
    engine = ForecastEngine(
        config, network_prior=build_network_prior(sample(), ORIGIN, NOW, LAMBDA)
    )
    result = engine.forecast_machine(machine, [], [machine], [], now=NOW)

    assert all(window["basis"] == "NETWORK" for window in result["windows"])
    assert result["explanation"]["signals"]["basis"] == "Network pattern"


def test_explanation_states_it_is_not_machine_specific():
    config = minimal_forecast_config()
    machine = make_machine()
    engine = ForecastEngine(
        config, network_prior=build_network_prior(sample(), ORIGIN, NOW, LAMBDA)
    )
    result = engine.forecast_machine(machine, [], [machine], [], now=NOW)

    joined = " ".join(result["explanation"]["reasons"]).lower()
    assert "not enough for a machine-specific forecast" in joined
    assert "community report" in joined


def test_machine_with_real_history_still_wins_over_the_prior():
    """A machine with its own data must not be downgraded to the population rate."""
    config = minimal_forecast_config()
    machine = make_machine()
    engine = ForecastEngine(
        config, network_prior=build_network_prior(sample(), ORIGIN, NOW, LAMBDA)
    )
    own = hourly_positives(12, minute=37, start=NOW - timedelta(hours=12))

    result = engine.forecast_machine(machine, own, [machine], [], now=NOW)

    assert result["status"] == STATUS_OK
    assert all(window.get("basis") != "NETWORK" for window in result["windows"])


def test_insufficient_data_is_still_used_when_no_prior_exists():
    config = minimal_forecast_config()
    machine = make_machine()
    result = ForecastEngine(config, network_prior=None).forecast_machine(
        machine, [], [machine], [], now=NOW
    )
    assert result["status"] == STATUS_INSUFFICIENT_DATA


def test_prior_can_be_disabled_in_config():
    config = minimal_forecast_config(network_prior={"enabled": False})
    machine = make_machine()
    results = forecast_all(config, [machine], sample(), now=NOW, origin=ORIGIN)
    assert results[0]["status"] == STATUS_INSUFFICIENT_DATA


def test_forecast_all_builds_the_prior_once_and_applies_it():
    config = minimal_forecast_config()
    machines = [make_machine(machine_id="rec1"), make_machine(machine_id="rec2")]

    results = forecast_all(config, machines, sample(), now=NOW, origin=ORIGIN)

    assert all(result["status"] == STATUS_NETWORK_PATTERN for result in results)
    assert results[0]["networkPrior"]["sampleCount"] == 60
