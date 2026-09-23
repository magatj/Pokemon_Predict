"""Forecast engine behaviour."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pokevend.forecast.engine import (
    STATUS_INSUFFICIENT_DATA,
    STATUS_OK,
    ForecastEngine,
    forecast_all,
)
from pokevend.models import Availability
from tests.conftest import hourly_positives, make_machine, make_observation, minimal_forecast_config

#: 09:00 local (America/Los_Angeles is UTC-7 in September).
NOW = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)


@pytest.fixture
def config():
    return minimal_forecast_config()


@pytest.fixture
def engine(config):
    return ForecastEngine(config)


def positives(count, minute=37, machine_id="rec1"):
    """Positives clustered near a minute, ending shortly before NOW."""
    start = NOW - timedelta(hours=count)
    return hourly_positives(count, minute=minute, start=start, machine_id=machine_id)


# -- insufficient data ---------------------------------------------------

def test_machine_below_the_minimum_reports_insufficient_data(engine, config):
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(3), [machine], [], now=NOW)

    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert result["windows"] == []
    assert result["next"] is None
    assert result["observationCount"] == 3
    assert result["minimumObservations"] == config.minimum_observations


def test_insufficient_data_states_the_shortfall_instead_of_a_number(engine):
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(3), [machine], [], now=NOW)

    reason = result["explanation"]["reasons"][0]
    assert "3 of 8 observations" in reason
    assert "%" not in reason


def test_a_machine_with_no_observations_is_insufficient(engine):
    machine = make_machine()
    result = engine.forecast_machine(machine, [], [machine], [], now=NOW)
    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert result["observationCount"] == 0


def test_no_probability_is_emitted_below_the_threshold(engine):
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(7), [machine], [], now=NOW)
    assert result["status"] == STATUS_INSUFFICIENT_DATA
    assert "probability" not in result


# -- scored forecasts ----------------------------------------------------

def test_sufficient_data_produces_ranked_windows(engine, config):
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(12), [machine], [], now=NOW)

    assert result["status"] == STATUS_OK
    assert result["windows"]
    assert len(result["windows"]) <= config.max_windows_per_machine

    probabilities = [window["probability"] for window in result["windows"]]
    assert probabilities == sorted(probabilities, reverse=True)
    assert all(0.0 <= value <= 1.0 for value in probabilities)


def test_the_top_window_lands_on_the_detected_pattern_minute(engine):
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(12, minute=37), [machine], [], now=NOW)

    minute = int(result["next"]["localTime"].split(":")[1])
    assert abs(minute - 37) <= config_tolerance()


def config_tolerance():
    return minimal_forecast_config().minute_tolerance + minimal_forecast_config().window_minutes


def test_window_length_matches_the_configuration(engine, config):
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(12), [machine], [], now=NOW)

    from pokevend.timeutil import parse_iso8601

    window = result["next"]
    length = parse_iso8601(window["windowEnd"]) - parse_iso8601(window["windowStart"])
    assert length == timedelta(minutes=config.window_minutes)


def test_all_candidate_windows_are_in_the_future(engine):
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(12), [machine], [], now=NOW)

    from pokevend.timeutil import parse_iso8601

    assert all(parse_iso8601(window["windowStart"]) > NOW for window in result["windows"])


def test_more_evidence_raises_the_score(engine):
    machine = make_machine()
    few = engine.forecast_machine(machine, positives(8), [machine], [], now=NOW)
    many = engine.forecast_machine(machine, positives(30), [machine], [], now=NOW)

    assert many["next"]["probability"] > few["next"]["probability"]


def test_confidence_band_rises_with_sample_size(engine):
    machine = make_machine()
    small = engine.forecast_machine(machine, positives(9), [machine], [], now=NOW)
    large = engine.forecast_machine(machine, positives(40), [machine], [], now=NOW)

    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    assert order[large["confidence"]] >= order[small["confidence"]]


# -- explanation ---------------------------------------------------------

def test_every_scored_window_is_explainable(engine):
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(12), [machine], [], now=NOW)

    for window in result["windows"]:
        explanation = window["explanation"]
        assert explanation["reasons"]
        assert set(explanation["signals"]) >= {
            "minutePattern", "interval", "historicalHits", "recentActivity",
            "nearbyActivity", "sampleConfidence",
        }
        assert explanation["reportsUsed"] == result["observationCount"]


def test_component_breakdown_is_exposed_for_every_weight(engine, config):
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(12), [machine], [], now=NOW)

    components = result["next"]["components"]
    assert set(components) == set(config.scoring_weights)


def test_explanation_cites_the_minute_pattern(engine):
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(12, minute=37), [machine], [], now=NOW)
    assert any(":37" in reason for reason in result["explanation"]["reasons"])


# -- nearby signal -------------------------------------------------------

def test_nearby_activity_is_recorded_but_stays_secondary(engine, config):
    from pokevend.geo import destination_point

    machine = make_machine(machine_id="rec1")
    latitude, longitude = destination_point(machine.latitude, machine.longitude, 0, 2.0)
    neighbour = make_machine(machine_id="rec2", latitude=latitude, longitude=longitude)

    neighbour_reports = [
        make_observation(observation_id="n1", machine_id="rec2",
                         when=NOW - timedelta(minutes=20))
    ]
    result = engine.forecast_machine(
        machine, positives(12), [machine, neighbour], neighbour_reports, now=NOW
    )

    assert result["features"]["nearby"]["activeMachineIds"] == ["rec2"]
    assert config.scoring_weights["nearby_activity"] == 0.05


def test_negative_reports_do_not_count_as_nearby_activity(engine):
    from pokevend.geo import destination_point

    machine = make_machine(machine_id="rec1")
    latitude, longitude = destination_point(machine.latitude, machine.longitude, 0, 2.0)
    neighbour = make_machine(machine_id="rec2", latitude=latitude, longitude=longitude)

    sold_out = [
        make_observation(observation_id="n1", machine_id="rec2",
                         when=NOW - timedelta(minutes=20),
                         availability=Availability.NOT_AVAILABLE)
    ]
    result = engine.forecast_machine(
        machine, positives(12), [machine, neighbour], sold_out, now=NOW
    )
    assert result["features"]["nearby"]["activeMachineIds"] == []


# -- batch ---------------------------------------------------------------

def test_forecast_all_covers_every_machine(config):
    machines = [make_machine(machine_id="rec1"), make_machine(machine_id="rec2")]
    observations = positives(12, machine_id="rec1")

    results = forecast_all(config, machines, observations, now=NOW)

    assert [result["machineId"] for result in results] == ["rec1", "rec2"]
    assert results[0]["status"] == STATUS_OK
    assert results[1]["status"] == STATUS_INSUFFICIENT_DATA


def test_forecast_all_ignores_weakly_matched_observations(config):
    """An unattributed community report must not feed a machine forecast."""
    machine = make_machine(machine_id="rec1")
    weak = positives(12, machine_id="rec1")
    for observation in weak:
        observation.machine_match_confidence = 0.2

    results = forecast_all(config, [machine], weak, now=NOW)
    assert results[0]["status"] == STATUS_INSUFFICIENT_DATA


# -- horizon decay -------------------------------------------------------

def test_later_windows_score_lower_than_equivalent_earlier_ones(engine):
    """Two windows on the same pattern minute differ only by how far off they are."""
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(30), [machine], [], now=NOW)

    by_minute = {}
    for window in result["windows"]:
        by_minute.setdefault(window["localTime"].split(":")[1], []).append(window)

    repeated = next(group for group in by_minute.values() if len(group) > 1)
    ordered = sorted(repeated, key=lambda window: window["minutesAhead"])
    assert ordered[0]["probability"] > ordered[-1]["probability"]


def test_horizon_scale_is_reported_for_every_window(engine):
    machine = make_machine()
    result = engine.forecast_machine(machine, positives(12), [machine], [], now=NOW)

    for window in result["windows"]:
        assert 0 < window["horizonScale"] <= 1.0
        assert window["minutesAhead"] > 0


def test_horizon_decay_can_be_switched_off():
    config = minimal_forecast_config(forecast={"horizon_decay_per_hour": 0.0})
    machine = make_machine()
    result = ForecastEngine(config).forecast_machine(
        machine, positives(30), [machine], [], now=NOW
    )
    assert all(window["horizonScale"] == 1.0 for window in result["windows"])
