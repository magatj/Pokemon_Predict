"""Attributing free-text community reports to specific machines."""
from __future__ import annotations

from pokevend.normalizers.machine_normalizer import build_aliases
from pokevend.normalizers.observation_normalizer import (
    MachineMatcher,
    normalize_observations,
    observations_for_machine,
)
from tests.conftest import make_machine, make_observation

MATCHING = {
    "min_machine_match_confidence": 0.70,
    "retailer_weight": 0.35,
    "city_weight": 0.35,
    "zip_weight": 0.20,
    "alias_weight": 0.40,
    "machine_id_weight": 1.00,
}


def covington_fred_meyer():
    machine = make_machine(
        machine_id="rec-cov", retailer="Fred Meyer", city="Covington", zip_code="98042",
        name="Q01401",
    )
    machine.aliases = build_aliases(machine)
    return machine


def kent_safeway():
    machine = make_machine(
        machine_id="rec-kent", retailer="Safeway", city="Kent", zip_code="98030", name="Q01094",
    )
    machine.aliases = build_aliases(machine)
    return machine


def test_retailer_plus_city_matches_confidently():
    """"Covington Fred Meyer" should resolve to that machine."""
    machines = [covington_fred_meyer(), kent_safeway()]
    observation = make_observation(machine_id=None, source="REDDIT")
    observation.location_text = "Covington"
    observation.retailer = "Fred Meyer"

    machine_id, confidence = MachineMatcher(machines, MATCHING).match(observation)

    assert machine_id == "rec-cov"
    assert confidence >= 0.70


def test_a_printed_machine_id_is_decisive():
    machines = [covington_fred_meyer(), kent_safeway()]
    observation = make_observation(machine_id="rec-kent", source="REDDIT")

    machine_id, confidence = MachineMatcher(machines, MATCHING).match(observation)

    assert machine_id == "rec-kent"
    assert confidence == 1.0


def test_machine_name_on_the_cabinet_resolves_to_the_record():
    machines = [covington_fred_meyer(), kent_safeway()]
    observation = make_observation(machine_id="Q01094", source="REDDIT")

    machine_id, _ = MachineMatcher(machines, MATCHING).match(observation)
    assert machine_id == "rec-kent"


def test_vague_city_only_report_is_not_attributed():
    """City alone is below threshold, so it must not pick a machine."""
    machines = [covington_fred_meyer(), kent_safeway()]
    observation = make_observation(machine_id=None, source="REDDIT")
    observation.location_text = "Kent"

    machine_id, confidence = MachineMatcher(machines, MATCHING).match(observation)

    assert machine_id is None
    assert confidence < 0.70


def test_ambiguous_report_between_two_identical_stores_is_rejected():
    """Two Safeways in one city cannot be told apart by "Kent Safeway"."""
    first = make_machine(machine_id="rec-a", retailer="Safeway", city="Kent", zip_code="98030",
                         name="Q1")
    second = make_machine(machine_id="rec-b", retailer="Safeway", city="Kent", zip_code="98030",
                          name="Q2")
    first.aliases, second.aliases = build_aliases(first), build_aliases(second)

    observation = make_observation(machine_id=None, source="REDDIT")
    observation.location_text = "kent safeway"
    observation.retailer = "Safeway"

    machine_id, _ = MachineMatcher([first, second], MATCHING).match(observation)
    assert machine_id is None


def test_report_with_no_location_signal_matches_nothing():
    observation = make_observation(machine_id=None, source="REDDIT")
    observation.location_text = None
    observation.retailer = None

    machine_id, confidence = MachineMatcher([kent_safeway()], MATCHING).match(observation)
    assert machine_id is None
    assert confidence == 0.0


def test_first_party_user_reports_keep_their_machine():
    """A user tapping a button on a machine page is not a guess."""
    machines = [kent_safeway()]
    observation = make_observation(machine_id="rec-kent", source="USER")

    normalized = normalize_observations([observation], machines, MATCHING)

    assert normalized[0].machine_id == "rec-kent"
    assert normalized[0].machine_match_confidence == 1.0


def test_low_confidence_observations_are_excluded_from_machine_forecasting():
    """Ambiguous evidence is retained, but never used for one machine."""
    machines = [covington_fred_meyer(), kent_safeway()]
    vague = make_observation(observation_id="vague", machine_id=None, source="REDDIT")
    vague.location_text = "Kent"
    precise = make_observation(observation_id="precise", machine_id="rec-kent", source="USER")

    normalized = normalize_observations([vague, precise], machines, MATCHING)
    used = observations_for_machine(normalized, "rec-kent", 0.70)

    assert len(normalized) == 2
    assert [observation.id for observation in used] == ["precise"]


def test_aliases_cover_both_word_orders():
    aliases = build_aliases(covington_fred_meyer())
    assert "covington fred meyer" in aliases
    assert "fred meyer covington" in aliases
