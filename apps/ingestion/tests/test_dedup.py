"""Observation de-duplication."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pokevend.forecast.features import build_features
from pokevend.models import EvidenceClass
from pokevend.models.observation import build_fingerprint, hash_text
from pokevend.normalizers.observation_normalizer import deduplicate
from pokevend.sources.community_source import parse_community_post
from tests.conftest import make_observation

WHEN = datetime(2026, 9, 20, 12, 37, tzinfo=timezone.utc)


def duplicate_pair(**overrides):
    first = make_observation(observation_id="a", when=WHEN, **overrides)
    second = make_observation(observation_id="a", when=WHEN, **overrides)
    return first, second


def test_identical_reports_collapse_to_one():
    first, second = duplicate_pair()
    assert first.fingerprint == second.fingerprint
    assert len(deduplicate([first, second])) == 1


def test_distinct_reports_are_both_kept():
    first = make_observation(observation_id="a", when=WHEN)
    second = make_observation(observation_id="b", when=WHEN + timedelta(hours=1))
    assert len(deduplicate([first, second])) == 2


def test_fingerprint_ignores_sub_minute_jitter():
    """Re-crawls often shift a timestamp by seconds; that is the same event."""
    text_hash = hash_text("pokemon vending machine in stock")
    first = build_fingerprint("REDDIT", "t3_abc", "rec1", "2026-09-20T12:37:11Z", text_hash)
    second = build_fingerprint("REDDIT", "t3_abc", "rec1", "2026-09-20T12:37:52Z", text_hash)
    assert first == second


def test_fingerprint_separates_different_machines():
    text_hash = hash_text("in stock")
    first = build_fingerprint("REDDIT", "t3_abc", "rec1", "2026-09-20T12:37:00Z", text_hash)
    second = build_fingerprint("REDDIT", "t3_abc", "rec2", "2026-09-20T12:37:00Z", text_hash)
    assert first != second


def test_the_strongest_copy_of_a_duplicate_survives():
    weak = make_observation(observation_id="a", when=WHEN, confidence=0.4,
                            evidence_class=EvidenceClass.COMMUNITY_GENERAL)
    strong = make_observation(observation_id="a", when=WHEN, confidence=1.0,
                              purchase=True, evidence_class=EvidenceClass.PURCHASE_CONFIRMED)

    survivors = deduplicate([weak, strong])
    assert len(survivors) == 1
    assert survivors[0].confidence == 1.0
    assert survivors[0].purchase_confirmed is True


def test_the_same_post_crossposted_is_counted_once():
    """Identical text and time from one source id is one event, not two."""
    post = {
        "id": "t3_abc",
        "title": "Kent Safeway pokemon vending machine restocked",
        "text": "bought a bundle",
        "created_at": "2026-09-20T13:37:00Z",
        "url": "https://example.test/a",
    }
    mirrored = dict(post, url="https://example.test/mirror")

    observations = [parse_community_post(post), parse_community_post(mirrored)]
    assert len({observation.fingerprint for observation in observations}) == 1
    assert len(deduplicate(observations)) == 1


def test_results_are_ordered_oldest_first():
    late = make_observation(observation_id="late", when=WHEN + timedelta(hours=2))
    early = make_observation(observation_id="early", when=WHEN)
    assert [obs.id for obs in deduplicate([late, early])] == ["early", "late"]


def test_observations_without_a_key_are_dropped():
    orphan = make_observation(observation_id="x")
    orphan.fingerprint = ""
    orphan.id = ""
    assert deduplicate([orphan]) == []


def test_duplicates_do_not_inflate_the_forecast_sample():
    """Double-counting would let one report clear the minimum-sample gate."""
    now = WHEN + timedelta(hours=1)
    observations = [make_observation(observation_id="a", when=WHEN) for _ in range(10)]

    deduped = deduplicate(observations)
    features = build_features("rec1", deduped, now=now, lambda_per_hour=0.0058)

    assert features.observation_count == 1
