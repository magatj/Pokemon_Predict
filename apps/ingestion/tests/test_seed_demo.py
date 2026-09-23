"""The demonstration seeder must stay isolated from real data."""
from __future__ import annotations

import pytest

from pokevend.jobs import seed_demo
from pokevend.models import Availability
from pokevend.store import DEFAULT_DATA_DIR
from tests.conftest import make_machine


def test_refuses_to_write_into_the_real_store():
    with pytest.raises(SystemExit, match="refusing"):
        seed_demo.run(DEFAULT_DATA_DIR)


def test_generated_observations_are_marked_as_demo_data():
    machines = [make_machine(machine_id=f"rec{index}") for index in range(3)]
    observations = seed_demo.build_demo_observations(machines)

    assert observations
    assert all(observation.extra.get("demoData") is True for observation in observations)


def test_generated_observations_are_deterministic():
    machines = [make_machine(machine_id="rec0")]
    first = seed_demo.build_demo_observations(machines, seed=1)
    second = seed_demo.build_demo_observations(machines, seed=1)
    assert [o.fingerprint for o in first] == [o.fingerprint for o in second]


def test_profiles_produce_detectable_patterns():
    """The seeded cadence must actually be recoverable, or the demo proves nothing."""
    from pokevend.forecast.interval import detect_interval
    from pokevend.forecast.minute_pattern import detect_minute_pattern
    from pokevend.timeutil import parse_iso8601

    machines = [make_machine(machine_id="rec0")]
    observations = seed_demo.build_demo_observations(machines, seed=7)
    positives = [
        parse_iso8601(o.effective_at)
        for o in observations
        if o.availability in Availability.POSITIVE
    ]

    pattern = detect_minute_pattern([t.minute for t in positives], tolerance=3, min_samples=4)
    interval = detect_interval(positives, tolerance_minutes=4)

    assert pattern is not None
    assert abs(pattern["patternMinute"] - seed_demo.PROFILES[0]["minute"]) <= 3
    assert interval is not None


def test_only_profiled_machines_receive_observations():
    machines = [make_machine(machine_id=f"rec{index}") for index in range(10)]
    observations = seed_demo.build_demo_observations(machines)
    seeded = {observation.machine_id for observation in observations}

    assert len(seeded) == len(seed_demo.PROFILES)
    assert "rec9" not in seeded
