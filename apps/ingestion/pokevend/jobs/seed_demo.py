"""Job: generate a DEMONSTRATION dataset so the forecast UI can be exercised.

Run:  python -m pokevend.jobs.seed_demo --output data-demo

The production pipeline only ever forecasts from real observations, and with no
community source available it correctly reports INSUFFICIENT_DATA for every
machine. That is the honest result, but it makes the scored views impossible to
look at during development.

This job writes SYNTHETIC observations into a SEPARATE directory. It refuses to
touch the real store, and every file it produces carries ``"demoData": true``
so the dashboard can label it loudly. Nothing it writes is ever deployed by the
`pages` job.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from datetime import timedelta
from pathlib import Path
from typing import List

from pokevend.config import load_config
from pokevend.forecast.engine import forecast_all
from pokevend.models import Availability, EvidenceClass, Machine, Observation
from pokevend.models.observation import build_fingerprint, hash_text
from pokevend.store import DEFAULT_DATA_DIR, DataStore
from pokevend.timeutil import now_utc, to_iso8601

LOGGER = logging.getLogger(__name__)

#: How each simulated machine behaves. Deliberately varied so the dashboard
#: shows scored, marginal and insufficient-data machines side by side.
PROFILES = [
    {"minute": 37, "interval_minutes": 60, "count": 44, "purchase_rate": 0.35},
    {"minute": 12, "interval_minutes": 30, "count": 30, "purchase_rate": 0.25},
    {"minute": 5, "interval_minutes": 120, "count": 14, "purchase_rate": 0.15},
    {"minute": 48, "interval_minutes": 90, "count": 9, "purchase_rate": 0.1},
    {"minute": 21, "interval_minutes": 60, "count": 4, "purchase_rate": 0.0},
]


def _observation(
    machine: Machine, when, availability: str, purchase: bool, index: int
) -> Observation:
    text = f"demo observation {machine.id} {index}"
    raw_hash = hash_text(text)
    identifier = f"demo-{machine.id}-{index}"
    fingerprint = build_fingerprint("USER", identifier, machine.id, to_iso8601(when), raw_hash)

    if purchase:
        evidence = EvidenceClass.PURCHASE_CONFIRMED
        confidence = 1.0
    elif availability == Availability.AVAILABLE:
        evidence = EvidenceClass.USER_AVAILABLE
        confidence = 0.85
    else:
        evidence = EvidenceClass.USER_NOT_AVAILABLE
        confidence = 0.75

    return Observation(
        id=fingerprint,
        source="USER",
        availability=availability,
        posted_at=to_iso8601(when),
        observed_at=to_iso8601(when),
        machine_id=machine.id,
        machine_match_confidence=1.0,
        purchase_confirmed=purchase,
        evidence_class=evidence,
        confidence=confidence,
        raw_text_hash=raw_hash,
        fingerprint=fingerprint,
        ingested_at=to_iso8601(now_utc()),
        extra={"demoData": True},
    )


def build_demo_observations(machines: List[Machine], seed: int = 20260923) -> List[Observation]:
    """Synthesise a plausible observation history for the first few machines."""
    rng = random.Random(seed)
    now = now_utc()
    observations: List[Observation] = []

    for machine, profile in zip(machines, PROFILES):
        interval = int(profile["interval_minutes"])
        # Anchor on the profile's minute, then step backwards at its cadence.
        # The minute is only pinned once, so a 30- or 90-minute cadence produces
        # the alternating minutes it actually would in the field.
        anchor = now.replace(minute=int(profile["minute"]), second=0, microsecond=0)
        if anchor > now:
            anchor -= timedelta(hours=1)

        for index in range(int(profile["count"])):
            # A couple of minutes of jitter so minute-clustering has real work.
            jitter = timedelta(minutes=rng.choice([-2, -1, 0, 1, 2]))
            when = anchor - timedelta(minutes=interval * (index + 1)) + jitter

            # Most reports are positive; a minority are sold-out sightings.
            positive = rng.random() > 0.25
            availability = Availability.AVAILABLE if positive else Availability.NOT_AVAILABLE
            purchase = positive and rng.random() < float(profile["purchase_rate"])
            observations.append(_observation(machine, when, availability, purchase, index))

    return observations


def run(output_dir: Path, config_dir=None, seed: int = 20260923) -> dict:
    output_dir = Path(output_dir).resolve()
    if output_dir == DEFAULT_DATA_DIR.resolve():
        raise SystemExit(
            f"refusing to write demonstration data into the real store at {DEFAULT_DATA_DIR}"
        )

    config = load_config(config_dir)
    source = DataStore()
    machines = source.load_machines()
    if not machines:
        raise SystemExit(
            "no machines found; run `python -m pokevend.jobs.refresh_machines` first"
        )

    demo_store = DataStore(data_dir=output_dir, publish_dir=output_dir / "public")
    demo_store.save_machines(machines, meta={"demoData": True})

    observations = build_demo_observations(machines, seed=seed)
    demo_store.save_observations(observations)

    forecasts = forecast_all(config.forecast, machines, observations)
    demo_store.save_forecasts(forecasts)
    demo_store.save_source_health(
        [
            {
                "name": "demo_seed",
                "status": "DISABLED",
                "authority": "SUPPLEMENTAL",
                "checked_at": to_iso8601(now_utc()),
                "records": len(observations),
                "message": "SYNTHETIC demonstration data - not a real source",
                "reason": "DEMO_DATA",
                "last_success_at": None,
                "details": {},
            }
        ]
    )
    demo_store.publish(
        search_meta={
            "zipCode": config.forecast.zip_code,
            "radiusMiles": config.forecast.radius_miles,
            "demoData": True,
        }
    )

    # Stamp every published file so the UI cannot mistake this for real data.
    for path in (demo_store.publish_dir).glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["demoData"] = True
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    scored = sum(1 for f in forecasts if f.get("status") == "OK")
    return {
        "machines": len(machines),
        "observations": len(observations),
        "scored": scored,
        "insufficient": len(forecasts) - scored,
        "output": str(demo_store.publish_dir),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate SYNTHETIC demonstration data (never the real store)"
    )
    parser.add_argument("--output", default="data-demo", help="directory to write into")
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(levelname)s %(name)s: %(message)s")

    counts = run(Path(args.output), seed=args.seed)
    print("DEMONSTRATION DATA (synthetic - do not deploy)")
    for key, value in sorted(counts.items()):
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
