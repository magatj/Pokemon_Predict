"""Job: discover and verify machines near the configured search area.

Run:  python -m pokevend.jobs.refresh_machines

1. Resolve the search ZIP to a centroid.
2. Query the official locator API over a tiled bounding box.
3. Filter to the radius with Haversine distance.
4. Optionally verify each machine against its retailer's public store page.
5. Persist machines and source health.
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import List

from pokevend.config import load_config
from pokevend.geocode import resolve_zip_centroid
from pokevend.http import SourceSkipped, session_from_config
from pokevend.models import SourceHealth, SourceStatus
from pokevend.models.source_record import merge_health
from pokevend.normalizers.machine_normalizer import apply_verification, normalize_machines
from pokevend.sources.pokemon_locator import PokemonLocatorSource
from pokevend.sources.retailer_source import build_retailer_sources
from pokevend.store import DataStore
from pokevend.timeutil import now_utc, to_iso8601

LOGGER = logging.getLogger(__name__)


def run(verify: bool = True, config_dir=None, data_dir=None) -> int:
    config = load_config(config_dir)
    store = DataStore(data_dir=data_dir)
    forecast_config = config.forecast
    reports: List[SourceHealth] = []

    locator_settings = config.sources.source("pokemon_locator")
    locator_session = session_from_config(locator_settings)

    centroid, provenance = resolve_zip_centroid(
        forecast_config.zip_code,
        session=locator_session,
        fallback=forecast_config.fallback_centroid,
    )
    LOGGER.info(
        "search centroid for ZIP %s: %.5f, %.5f (%s)",
        forecast_config.zip_code, centroid[0], centroid[1], provenance,
    )

    discovered = []
    if config.sources.is_enabled("pokemon_locator"):
        locator = PokemonLocatorSource(locator_settings, locator_session)
        try:
            payloads = locator.fetch(centroid[0], centroid[1], forecast_config.radius_miles)
            discovered = locator.normalize(payloads)
            reports.append(
                SourceHealth(
                    name=locator.name,
                    status=SourceStatus.HEALTHY,
                    authority=locator.authority,
                    checked_at=to_iso8601(now_utc()),
                    records=len(discovered),
                    message=f"{len(discovered)} machines discovered across {len(payloads)} tiles",
                )
            )
        except SourceSkipped as exc:
            LOGGER.error("SOURCE_SKIPPED %s (%s)", locator.name, exc.reason)
            reports.append(
                SourceHealth(
                    name=locator.name,
                    status=SourceStatus.SKIPPED,
                    authority=locator.authority,
                    checked_at=to_iso8601(now_utc()),
                    message=str(exc),
                    reason=exc.reason,
                )
            )
    else:
        reports.append(
            SourceHealth(
                name="pokemon_locator",
                status=SourceStatus.DISABLED,
                authority="OFFICIAL",
                checked_at=to_iso8601(now_utc()),
                message="disabled in sources.yaml",
                reason="DISABLED",
            )
        )

    machines = normalize_machines(
        discovered,
        origin=centroid,
        radius_miles=forecast_config.radius_miles,
        existing=store.load_machines() if not discovered else None,
    )
    LOGGER.info("%s machines within %.1f miles", len(machines), forecast_config.radius_miles)

    if verify and config.sources.is_enabled("retailer_pages"):
        retailer_settings = config.sources.source("retailer_pages")
        retailer_session = session_from_config(retailer_settings)
        for source in build_retailer_sources(retailer_settings, retailer_session):
            verified = 0
            if not source.enabled:
                reports.append(source.health_check())
                LOGGER.info("SOURCE_SKIPPED %s (DISABLED)", source.name)
                continue
            for machine in machines:
                if machine.retailer.lower() != source.retailer.lower():
                    continue
                try:
                    profile = source.fetch(machine)
                except SourceSkipped as exc:
                    LOGGER.warning("SOURCE_SKIPPED %s for %s (%s)",
                                   source.name, machine.id, exc.reason)
                    continue
                except Exception as exc:  # noqa: BLE001 - verification is best-effort
                    LOGGER.warning("verification error for %s: %s", machine.id, exc)
                    continue
                if profile:
                    apply_verification(machine, profile)
                    verified += 1
            health = source.health_check()
            health.records = verified
            health.message = f"{health.message}; verified {verified} machine(s)"
            reports.append(health)

    store.save_machines(
        machines,
        meta={
            "search": {
                "zipCode": forecast_config.zip_code,
                "radiusMiles": forecast_config.radius_miles,
                "centroid": {"latitude": centroid[0], "longitude": centroid[1]},
                "centroidSource": provenance,
            }
        },
    )
    store.save_source_health(merge_health(store.load_source_health(), reports))

    for report in reports:
        LOGGER.info("source %s: %s (%s records)", report.name, report.status, report.records)
    return len(machines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Refresh vending machine locations")
    parser.add_argument("--no-verify", action="store_true",
                        help="skip retailer store-page verification")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(levelname)s %(name)s: %(message)s")
    count = run(verify=not args.no_verify)
    print(f"machines within radius: {count}")
    return 0 if count else 1


if __name__ == "__main__":
    sys.exit(main())
