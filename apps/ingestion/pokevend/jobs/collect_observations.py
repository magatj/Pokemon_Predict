"""Job: collect and normalize public community observations.

Run:  python -m pokevend.jobs.collect_observations

Each enabled community source is fetched independently. A source that is
disabled, blocked by robots.txt or missing credentials is logged as
SOURCE_SKIPPED and recorded in source health - it never fails the run and never
falls back to a prohibited access method.

Observations are matched to machines, merged with the stored history and
de-duplicated by fingerprint before being written back. Sources such as
pokemonmap expose only a machine's *current* status, so repeated runs are what
accumulate a usable history; the fingerprint keeps an unchanged status from
being counted twice.
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Dict, List, Tuple

from pokevend.config import load_config
from pokevend.geocode import resolve_zip_centroid
from pokevend.http import SourceSkipped, session_from_config
from pokevend.models import Observation, SourceHealth, SourceStatus
from pokevend.models.source_record import merge_health
from pokevend.normalizers.observation_normalizer import normalize_observations
from pokevend.sources.pokemonmap_source import PokemonMapSource
from pokevend.sources.reddit_source import RedditSource
from pokevend.store import DataStore
from pokevend.timeutil import now_utc, to_iso8601

LOGGER = logging.getLogger(__name__)


def build_community_sources(config, centroid=None) -> List[Tuple[Any, Dict[str, Any]]]:
    """Instantiate every configured community source.

    Returns (source, fetch_kwargs) pairs, because geo-scoped sources need the
    search area while feed-style sources do not.
    """
    sources: List[Tuple[Any, Dict[str, Any]]] = []

    if "pokemonmap" in config.sources.names:
        settings = config.sources.source("pokemonmap")
        source = PokemonMapSource(
            settings,
            session=session_from_config(settings),
            enabled=config.sources.is_enabled("pokemonmap"),
            weight_lookup=config.forecast.observation_weight,
        )
        kwargs: Dict[str, Any] = {}
        if centroid is not None:
            kwargs = {
                "latitude": centroid[0],
                "longitude": centroid[1],
                "radius_miles": config.forecast.radius_miles,
            }
        sources.append((source, kwargs))

    if "reddit" in config.sources.names:
        settings = config.sources.source("reddit")
        sources.append(
            (
                RedditSource(
                    settings,
                    enabled=config.sources.is_enabled("reddit"),
                    weight_lookup=config.forecast.observation_weight,
                ),
                {},
            )
        )

    return sources


def run(config_dir=None, data_dir=None) -> int:
    config = load_config(config_dir)
    store = DataStore(data_dir=data_dir)
    machines = store.load_machines()
    existing = store.load_observations()

    centroid, _ = resolve_zip_centroid(
        config.forecast.zip_code,
        session=None,
        fallback=config.forecast.fallback_centroid,
    )

    collected: List[Observation] = []
    reports: List[SourceHealth] = []

    for source, fetch_kwargs in build_community_sources(config, centroid):
        checked_at = to_iso8601(now_utc())
        if not source.enabled:
            LOGGER.info("SOURCE_SKIPPED %s (DISABLED)", source.name)
            reports.append(source.health_check())
            continue
        try:
            raw = source.fetch(**fetch_kwargs)
        except SourceSkipped as exc:
            LOGGER.warning("SOURCE_SKIPPED %s (%s): %s", source.name, exc.reason, exc.detail)
            status = (
                SourceStatus.RATE_LIMITED
                if exc.reason == "RATE_LIMITED"
                else SourceStatus.SKIPPED
            )
            reports.append(
                SourceHealth(
                    name=source.name,
                    status=status,
                    authority=source.authority,
                    checked_at=checked_at,
                    message=str(exc),
                    reason=exc.reason,
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001 - one broken source must not stop the run
            LOGGER.exception("source %s failed", source.name)
            reports.append(
                SourceHealth(
                    name=source.name,
                    status=SourceStatus.ERROR,
                    authority=source.authority,
                    checked_at=checked_at,
                    message=str(exc),
                    reason="UNEXPECTED_ERROR",
                )
            )
            continue

        observations = source.normalize(raw)
        collected.extend(observations)
        reports.append(
            SourceHealth(
                name=source.name,
                status=SourceStatus.HEALTHY,
                authority=source.authority,
                checked_at=checked_at,
                records=len(observations),
                message=(
                    f"{len(raw or [])} record(s) fetched, "
                    f"{len(observations)} usable observation(s)"
                ),
            )
        )

    before = len(existing)
    merged = normalize_observations(
        list(existing) + collected, machines, config.forecast.matching
    )
    written = store.save_observations(merged)
    store.save_source_health(merge_health(store.load_source_health(), reports))

    LOGGER.info(
        "fetched %s observation(s); %s stored after de-duplication (%s new)",
        len(collected), written, max(written - before, 0),
    )
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Collect public community observations")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(levelname)s %(name)s: %(message)s")
    total = run()
    print(f"observations stored: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
