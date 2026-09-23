"""Job: build forecasts and publish the browser-facing JSON bundle.

Run:  python -m pokevend.jobs.build_forecasts

Machines below the configured minimum observation count are written out with
status INSUFFICIENT_DATA and no probability. That is intentional: the dashboard
shows how far off the threshold they are instead of a fabricated percentage.
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Dict

from pokevend.config import load_config
from pokevend.forecast.engine import (
    STATUS_INSUFFICIENT_DATA,
    STATUS_NETWORK_PATTERN,
    STATUS_OK,
    forecast_all,
)
from pokevend.geocode import resolve_zip_centroid
from pokevend.store import DataStore

LOGGER = logging.getLogger(__name__)


def run(config_dir=None, data_dir=None, publish_dir=None) -> Dict[str, int]:
    config = load_config(config_dir)
    store = DataStore(data_dir=data_dir, publish_dir=publish_dir)

    machines = store.load_machines()
    observations = store.load_observations()

    centroid, _ = resolve_zip_centroid(
        config.forecast.zip_code,
        session=None,
        fallback=config.forecast.fallback_centroid,
    )
    forecasts = forecast_all(config.forecast, machines, observations, origin=centroid)
    store.save_forecasts(forecasts)

    counts = {
        "machines": len(machines),
        "observations": len(observations),
        "forecast_ok": sum(1 for f in forecasts if f.get("status") == STATUS_OK),
        "insufficient_data": sum(
            1 for f in forecasts if f.get("status") == STATUS_INSUFFICIENT_DATA
        ),
        "network_pattern": sum(
            1 for f in forecasts if f.get("status") == STATUS_NETWORK_PATTERN
        ),
    }

    published = store.publish(
        search_meta={
            "zipCode": config.forecast.zip_code,
            "radiusMiles": config.forecast.radius_miles,
            "timezone": config.forecast.timezone_name,
            "windowMinutes": config.forecast.window_minutes,
            "minimumObservations": config.forecast.minimum_observations,
        }
    )
    counts.update({f"published_{k}": v for k, v in published.items()})

    LOGGER.info(
        "forecasts: %s scored, %s insufficient data, %s machines, %s observations",
        counts["forecast_ok"], counts["insufficient_data"],
        counts["machines"], counts["observations"],
    )
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build forecasts and publish JSON")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(levelname)s %(name)s: %(message)s")
    counts = run()
    for key, value in sorted(counts.items()):
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
