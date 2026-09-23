"""Persistence, publishing, configuration validation and local time."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from pokevend.config import ConfigError, ForecastConfig, load_config
from pokevend.geocode import local_lookup, resolve_zip_centroid
from pokevend.localtime import to_local, us_dst_bounds
from pokevend.models import SourceHealth, SourceStatus
from pokevend.models.source_record import merge_health
from pokevend.store import DataStore
from pokevend.timeutil import parse_iso8601, to_iso8601
from tests.conftest import make_machine, make_observation, minimal_forecast_config

# -- configuration -------------------------------------------------------


def test_repository_configuration_loads_and_validates():
    config = load_config()
    assert config.forecast.zip_code == "98092"
    assert config.forecast.radius_miles == 10.0
    assert config.forecast.window_minutes == 5


def test_scoring_weights_must_sum_to_one():
    raw = minimal_forecast_config().raw
    raw["scoring_weights"]["minute_pattern"] = 0.9
    with pytest.raises(ConfigError, match="sum to 1.0"):
        ForecastConfig(raw)


def test_observation_weights_must_be_probabilities():
    raw = minimal_forecast_config().raw
    raw["observation_weights"]["PURCHASE_CONFIRMED"] = 1.5
    with pytest.raises(ConfigError, match="out of range"):
        ForecastConfig(raw)


def test_minimum_observations_must_be_positive():
    raw = minimal_forecast_config().raw
    raw["forecast"]["minimum_observations"] = 0
    with pytest.raises(ConfigError):
        ForecastConfig(raw)


def test_unknown_evidence_class_falls_back_to_the_weakest_weight():
    config = minimal_forecast_config()
    assert config.observation_weight("SOMETHING_NEW") == 0.25
    assert config.observation_weight("PURCHASE_CONFIRMED") == 1.0


def test_source_settings_merge_over_defaults():
    config = load_config()
    locator = config.sources.source("pokemon_locator")
    assert locator["user_agent"]           # from defaults
    assert locator["rate_limit_seconds"] == 1.0   # overridden per source


def test_reddit_and_third_party_defaults_reflect_the_compliance_stance():
    config = load_config()
    # Reddit is enabled but gated on credentials; directories stay off.
    assert config.sources.is_enabled("reddit") is True
    assert config.sources.is_enabled("third_party_directories") is False


# -- geocoding -----------------------------------------------------------

def test_default_zip_resolves_without_network():
    centroid, provenance = resolve_zip_centroid("98092", session=None)
    assert provenance == "local_table"
    assert centroid == local_lookup("98092")


def test_unknown_zip_falls_back_to_configured_centroid():
    centroid, provenance = resolve_zip_centroid("99999", session=None, fallback=(1.0, 2.0))
    assert centroid == (1.0, 2.0)
    assert provenance == "config_fallback"


def test_unresolvable_zip_raises():
    with pytest.raises(ValueError):
        resolve_zip_centroid("99999", session=None, fallback=None)


# -- local time ----------------------------------------------------------

def test_pacific_summer_and_winter_offsets():
    summer = to_local(datetime(2026, 7, 1, 19, 0, tzinfo=timezone.utc), "America/Los_Angeles")
    winter = to_local(datetime(2026, 1, 1, 20, 0, tzinfo=timezone.utc), "America/Los_Angeles")
    assert summer.hour == 12   # UTC-7
    assert winter.hour == 12   # UTC-8


def test_dst_bounds_follow_the_us_rules():
    start, end = us_dst_bounds(2026)
    assert (start.month, start.weekday()) == (3, 6)
    assert (end.month, end.weekday()) == (11, 6)
    assert 8 <= start.day <= 14
    assert 1 <= end.day <= 7


def test_minute_of_hour_is_preserved_across_zones():
    """Offsets are whole hours here, so the pattern minute must not shift."""
    utc = datetime(2026, 9, 20, 19, 37, tzinfo=timezone.utc)
    assert to_local(utc, "America/Los_Angeles").minute == 37


# -- timestamps ----------------------------------------------------------

@pytest.mark.parametrize(
    "value",
    ["2026-09-20T12:37:00Z", "2026-09-20T12:37:00+00:00", "2026-09-20T12:37:00+0000"],
)
def test_iso_variants_parse_to_the_same_instant(value):
    assert parse_iso8601(value) == datetime(2026, 9, 20, 12, 37, tzinfo=timezone.utc)


@pytest.mark.parametrize("value", [None, "", "not-a-date", [], {}, "2026-13-45T99:99:99Z"])
def test_unparseable_timestamps_return_none_instead_of_raising(value):
    assert parse_iso8601(value) is None


def test_epoch_seconds_are_accepted():
    assert parse_iso8601(1789000000).tzinfo is not None


# -- store ---------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    return DataStore(data_dir=tmp_path / "data", publish_dir=tmp_path / "public")


def test_machines_round_trip(store):
    machines = [make_machine(machine_id="rec1"), make_machine(machine_id="rec2")]
    store.save_machines(machines)
    assert [m.id for m in store.load_machines()] == ["rec1", "rec2"]


def test_observations_round_trip(store):
    observations = [make_observation(observation_id="a"), make_observation(observation_id="b")]
    assert store.save_observations(observations) == 2
    assert [o.id for o in store.load_observations()] == ["a", "b"]


def test_a_corrupt_observation_line_costs_only_that_line(store):
    store.save_observations([make_observation(observation_id="a")])
    path = store.data_dir / "observations.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{not json}\n")
        handle.write(json.dumps(make_observation(observation_id="c").to_dict()) + "\n")

    assert [o.id for o in store.load_observations()] == ["a", "c"]


def test_missing_files_load_as_empty(store):
    assert store.load_machines() == []
    assert store.load_observations() == []
    assert store.load_forecasts() == []
    assert store.load_source_health() == []


def test_publish_writes_every_dashboard_file(store):
    store.save_machines([make_machine()])
    store.save_observations([make_observation()])
    store.save_forecasts([{"machineId": "rec1", "status": "INSUFFICIENT_DATA"}])
    store.save_source_health([{"name": "pokemon_locator", "status": "HEALTHY"}])

    counts = store.publish(search_meta={"zipCode": "98092", "radiusMiles": 10})

    expected = {"machines.json", "observations.json", "forecasts.json",
                "source-health.json", "generated-at.json"}
    assert {path.name for path in store.publish_dir.iterdir()} == expected
    assert counts["machines"] == 1

    published = json.loads((store.publish_dir / "machines.json").read_text(encoding="utf-8"))
    assert published["search"]["zipCode"] == "98092"
    assert parse_iso8601(published["generatedAt"]) is not None


def test_published_observations_omit_raw_text(store):
    store.save_observations([make_observation()])
    store.publish()

    payload = json.loads((store.publish_dir / "observations.json").read_text(encoding="utf-8"))
    record = payload["observations"][0]
    assert "rawTextHash" not in record
    assert "raw_text_hash" not in record
    assert set(record) >= {"machineId", "availability", "observedAt", "confidence"}


# -- source health -------------------------------------------------------

def test_health_merge_carries_forward_the_last_success():
    checked = to_iso8601(datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc))
    existing = [{"name": "reddit", "status": "HEALTHY", "last_success_at": "2026-09-22T10:00:00Z"}]
    failure = SourceHealth(name="reddit", status=SourceStatus.SKIPPED, authority="COMMUNITY",
                           checked_at=checked, reason="NO_CREDENTIALS")

    merged = {entry["name"]: entry for entry in merge_health(existing, [failure])}

    assert merged["reddit"]["status"] == "SKIPPED"
    assert merged["reddit"]["reason"] == "NO_CREDENTIALS"
    assert merged["reddit"]["last_success_at"] == "2026-09-22T10:00:00Z"


def test_health_merge_records_a_new_success():
    checked = to_iso8601(datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc))
    report = SourceHealth(name="pokemon_locator", status=SourceStatus.HEALTHY,
                          authority="OFFICIAL", checked_at=checked, records=16)
    merged = merge_health([], [report])[0]
    assert merged["last_success_at"] == checked
