"""Source adapters. Each one is independently replaceable."""

from pokevend.sources.base import BaseSource, DataSource
from pokevend.sources.community_source import CommunityObservationSource, parse_community_post
from pokevend.sources.pokemon_locator import PokemonLocatorSource, parse_machines_payload
from pokevend.sources.pokemonmap_source import PokemonMapSource, parse_status_payload
from pokevend.sources.reddit_source import RedditSource, parse_listing
from pokevend.sources.retailer_source import (
    RetailerSource,
    build_retailer_sources,
    parse_retailer_store_page,
)

__all__ = [
    "BaseSource",
    "CommunityObservationSource",
    "DataSource",
    "PokemonLocatorSource",
    "PokemonMapSource",
    "RedditSource",
    "RetailerSource",
    "build_retailer_sources",
    "parse_community_post",
    "parse_listing",
    "parse_machines_payload",
    "parse_status_payload",
    "parse_retailer_store_page",
]
