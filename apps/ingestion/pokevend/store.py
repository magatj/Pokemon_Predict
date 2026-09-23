"""Persistence and publishing.

State lives in plain JSON/JSONL under ``data/`` at the repo root so a GitLab CI
runner can restore it from the repo (or cache), extend it, and commit it back.
Publishing copies the browser-facing view into ``apps/web/public/data/``.

The same interface is what the AWS migration replaces with DynamoDB: jobs never
touch the filesystem directly.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pokevend.models import Machine, Observation
from pokevend.timeutil import now_utc, to_iso8601

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DEFAULT_PUBLISH_DIR = REPO_ROOT / "apps" / "web" / "public" / "data"

MACHINES_FILE = "machines.json"
OBSERVATIONS_FILE = "observations.jsonl"
FORECASTS_FILE = "forecasts.json"
SOURCE_HEALTH_FILE = "source-health.json"
GENERATED_AT_FILE = "generated-at.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        LOGGER.warning("could not read %s (%s); starting from empty", path, exc)
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


class DataStore:
    """JSON-backed store for machines, observations, forecasts and health."""

    def __init__(self, data_dir: Optional[Path] = None, publish_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.publish_dir = Path(publish_dir) if publish_dir else DEFAULT_PUBLISH_DIR

    # -- machines ---------------------------------------------------------
    def load_machines(self) -> List[Machine]:
        raw = _read_json(self.data_dir / MACHINES_FILE, {"machines": []})
        rows = raw.get("machines", []) if isinstance(raw, dict) else raw
        machines = []
        for row in rows or []:
            try:
                machines.append(Machine.from_dict(row))
            except (TypeError, ValueError) as exc:
                LOGGER.warning("skipping malformed machine row: %s", exc)
        return machines

    def save_machines(self, machines: Iterable[Machine], meta: Optional[Dict] = None) -> None:
        payload = {
            "generatedAt": to_iso8601(now_utc()),
            "machines": [machine.to_dict() for machine in machines],
        }
        if meta:
            payload.update(meta)
        _write_json(self.data_dir / MACHINES_FILE, payload)

    # -- observations -----------------------------------------------------
    def load_observations(self) -> List[Observation]:
        """Read the append-only observation log.

        JSONL keeps appends cheap and makes a corrupt line cost one observation
        rather than the whole history.
        """
        path = self.data_dir / OBSERVATIONS_FILE
        if not path.exists():
            return []
        observations = []
        with path.open("r", encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    observations.append(Observation.from_dict(json.loads(line)))
                except (ValueError, TypeError) as exc:
                    LOGGER.warning("skipping malformed observation on line %s: %s", number, exc)
        return observations

    def save_observations(self, observations: Iterable[Observation]) -> int:
        """Rewrite the log with the de-duplicated set."""
        path = self.data_dir / OBSERVATIONS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with path.open("w", encoding="utf-8") as handle:
            for observation in observations:
                handle.write(json.dumps(observation.to_dict(), sort_keys=True,
                                        ensure_ascii=False) + "\n")
                count += 1
        return count

    # -- forecasts and health --------------------------------------------
    def save_forecasts(self, forecasts: List[Dict[str, Any]]) -> None:
        _write_json(
            self.data_dir / FORECASTS_FILE,
            {"generatedAt": to_iso8601(now_utc()), "forecasts": forecasts},
        )

    def load_forecasts(self) -> List[Dict[str, Any]]:
        raw = _read_json(self.data_dir / FORECASTS_FILE, {"forecasts": []})
        return raw.get("forecasts", []) if isinstance(raw, dict) else []

    def load_source_health(self) -> List[Dict[str, Any]]:
        raw = _read_json(self.data_dir / SOURCE_HEALTH_FILE, {"sources": []})
        return raw.get("sources", []) if isinstance(raw, dict) else []

    def save_source_health(self, sources: List[Dict[str, Any]]) -> None:
        _write_json(
            self.data_dir / SOURCE_HEALTH_FILE,
            {"checkedAt": to_iso8601(now_utc()), "sources": sources},
        )

    # -- publishing -------------------------------------------------------
    def publish(self, search_meta: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        """Write the browser-facing JSON bundle.

        Observations are published in a reduced form: no raw text, just the
        normalized fields the dashboard needs plus the source URL.
        """
        machines = self.load_machines()
        observations = self.load_observations()
        forecasts = self.load_forecasts()
        health = self.load_source_health()
        generated_at = to_iso8601(now_utc())

        _write_json(
            self.publish_dir / "machines.json",
            {
                "generatedAt": generated_at,
                "search": search_meta or {},
                "machines": [machine.to_dict() for machine in machines],
            },
        )
        _write_json(
            self.publish_dir / "observations.json",
            {
                "generatedAt": generated_at,
                "observations": [
                    {
                        "id": observation.id,
                        "source": observation.source,
                        "sourceUrl": observation.source_url,
                        "machineId": observation.machine_id,
                        "machineMatchConfidence": observation.machine_match_confidence,
                        "availability": observation.availability,
                        "product": observation.product,
                        "purchaseConfirmed": observation.purchase_confirmed,
                        "evidenceClass": observation.evidence_class,
                        "confidence": observation.confidence,
                        "observedAt": observation.observed_at,
                        "postedAt": observation.posted_at,
                        "retailer": observation.retailer,
                        "locationText": observation.location_text,
                    }
                    for observation in observations
                ],
            },
        )
        _write_json(
            self.publish_dir / "forecasts.json",
            {"generatedAt": generated_at, "forecasts": forecasts},
        )
        _write_json(
            self.publish_dir / "source-health.json",
            {"generatedAt": generated_at, "sources": health},
        )
        _write_json(self.publish_dir / "generated-at.json", {"generatedAt": generated_at})

        return {
            "machines": len(machines),
            "observations": len(observations),
            "forecasts": len(forecasts),
            "sources": len(health),
        }
