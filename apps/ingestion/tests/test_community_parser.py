"""Community text parsing: relevance, classification and extraction."""
from __future__ import annotations

import pytest

from pokevend.models import Availability, EvidenceClass, ObservationSource, Product
from pokevend.sources.community_source import (
    CommunityObservationSource,
    classify_availability,
    classify_product,
    extract_machine_id,
    extract_retailer,
    extract_zip,
    is_relevant,
    parse_community_post,
)
from pokevend.sources.reddit_source import RedditSource, parse_listing
from tests.conftest import load_json_fixture

POSTED = "2026-09-20T13:37:00Z"


def post(text: str, **overrides):
    payload = {"id": "p1", "title": "", "text": text, "created_at": POSTED,
               "url": "https://example.test/p1"}
    payload.update(overrides)
    return payload


# -- relevance -----------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("pokemon vending machine restocked", True),
        ("Pokémon kiosk is empty", True),
        ("pulled a great pokemon card today", False),   # no machine
        ("the vending machine in the lobby", False),    # no pokemon
        ("", False),
    ],
)
def test_is_relevant(text, expected):
    assert is_relevant(text) is expected


# -- availability classification ----------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("machine is in stock right now", Availability.AVAILABLE),
        ("it has packs again", Availability.AVAILABLE),
        ("sold out", Availability.NOT_AVAILABLE),
        ("completely empty", Availability.NOT_AVAILABLE),
        ("they just restocked it", Availability.RESTOCK),
        ("someone refilled the machine", Availability.RESTOCK),
        ("anyone know where this machine is", Availability.UNKNOWN),
        ("", Availability.UNKNOWN),
    ],
)
def test_classify_availability(text, expected):
    assert classify_availability(text) == expected


def test_restocked_but_already_sold_out_is_negative():
    """The more specific negative claim wins over restock language."""
    assert classify_availability("restocked this morning but sold out already") == (
        Availability.NOT_AVAILABLE
    )


# -- field extraction ----------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("grabbed a booster bundle", Product.BOOSTER_BUNDLE),
        ("got an elite trainer box", Product.ELITE_TRAINER_BOX),
        ("ETB in stock", Product.ELITE_TRAINER_BOX),
        ("just tins left", Product.TIN),
        ("collection box available", Product.COLLECTION_BOX),
        ("nothing identifiable", None),
    ],
)
def test_classify_product(text, expected):
    assert classify_product(text) == expected


def test_extract_machine_id():
    assert extract_machine_id("machine Q01094 is empty") == "Q01094"
    assert extract_machine_id("machine 1094 is empty") is None


def test_extract_zip_and_retailer():
    assert extract_zip("near 98042 today") == "98042"
    assert extract_retailer("the covington fred meyer one") == "Fred Meyer"
    assert extract_retailer("no retailer named here") is None


# -- post parsing --------------------------------------------------------

def test_parses_a_usable_post_into_an_observation():
    observation = parse_community_post(
        post("Kent Safeway pokemon vending machine restocked, bought a booster bundle")
    )
    assert observation is not None
    assert observation.availability == Availability.RESTOCK
    assert observation.product == Product.BOOSTER_BUNDLE
    assert observation.purchase_confirmed is True
    assert observation.retailer == "Safeway"
    assert observation.source_url == "https://example.test/p1"


def test_irrelevant_and_unclassifiable_posts_are_skipped():
    assert parse_community_post(post("I love pokemon cards")) is None
    assert parse_community_post(post("where is the pokemon vending machine")) is None


def test_post_without_a_timestamp_is_skipped():
    """An observation with no time cannot contribute to a timing forecast."""
    assert parse_community_post(post("pokemon vending machine in stock",
                                     created_at=None)) is None


@pytest.mark.parametrize("bad", [None, "string", 42, []])
def test_unusable_post_shapes_return_none(bad):
    assert parse_community_post(bad) is None


def test_only_minimal_normalized_data_is_retained():
    """Long post bodies must not be republished - only a hash and a link."""
    body = "pokemon vending machine in stock. " + ("long copyrighted text " * 50)
    observation = parse_community_post(post(body))

    stored = observation.to_dict()
    assert "long copyrighted text" not in str(stored)
    assert len(observation.raw_text_hash) == 40
    assert observation.source_url


def test_machine_id_in_text_gives_full_match_confidence():
    observation = parse_community_post(post("Q01094 pokemon vending machine sold out"))
    assert observation.machine_id == "Q01094"
    assert observation.machine_match_confidence == 1.0


def test_evidence_class_reflects_timestamp_precision():
    with_observed = parse_community_post(
        post("pokemon vending machine in stock", observed_at=POSTED)
    )
    without = parse_community_post(post("pokemon vending machine in stock"))

    assert with_observed.evidence_class == EvidenceClass.COMMUNITY_TIMESTAMPED
    assert without.evidence_class == EvidenceClass.COMMUNITY_GENERAL


def test_weight_lookup_sets_confidence():
    observation = parse_community_post(
        post("pokemon vending machine in stock"), weight_lookup=lambda _: 0.65
    )
    assert observation.confidence == 0.65


# -- reddit listing ------------------------------------------------------

def test_parse_reddit_listing_flattens_posts():
    posts = parse_listing(load_json_fixture("reddit_listing.json"))
    assert [item["id"] for item in posts] == [
        "t3_aaa111", "t3_bbb222", "t3_ccc333", "t3_ddd444", "t3_eee555"
    ]
    assert posts[0]["url"].startswith("https://www.reddit.com/r/PokeInvesting/")
    assert posts[0]["has_photo"] is True


@pytest.mark.parametrize("payload", [None, {}, {"data": {}}, {"data": {"children": "x"}}, []])
def test_parse_reddit_listing_tolerates_bad_payloads(payload):
    assert parse_listing(payload) == []


def test_reddit_normalize_keeps_only_usable_observations():
    source = RedditSource({}, weight_lookup=lambda _: 0.65)
    posts = parse_listing(load_json_fixture("reddit_listing.json"))
    observations = source.normalize(posts)

    # Two usable: the Covington restock and the Kent sold-out report.
    # Dropped: off-topic, no availability signal, and an unparseable timestamp.
    assert len(observations) == 2
    assert {obs.availability for obs in observations} == {
        Availability.RESTOCK, Availability.NOT_AVAILABLE
    }
    assert all(obs.source == ObservationSource.REDDIT for obs in observations)


def test_one_broken_post_does_not_stop_the_batch():
    class Exploding(CommunityObservationSource):
        pass

    source = Exploding({})
    posts = [post("pokemon vending machine in stock"), {"id": object()}, None]
    assert len(source.normalize(posts)) == 1
