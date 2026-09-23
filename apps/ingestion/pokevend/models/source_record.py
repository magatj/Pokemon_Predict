"""Source health records.

Every source reports a status on every run. Ingestion never fails silently: a
source that is off, blocked or broken says so in source-health.json and the
dashboard surfaces it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class SourceStatus:
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    ERROR = "ERROR"
    DISABLED = "DISABLED"
    RATE_LIMITED = "RATE_LIMITED"
    SKIPPED = "SKIPPED"

    ALL = (HEALTHY, STALE, ERROR, DISABLED, RATE_LIMITED, SKIPPED)


@dataclass
class SourceHealth:
    name: str
    status: str
    authority: str
    checked_at: str
    records: int = 0
    message: str = ""
    # Machine-readable skip reason, e.g. ROBOTS_DISALLOWED or NO_CREDENTIALS.
    reason: Optional[str] = None
    last_success_at: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SourceHealth:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})


def merge_health(existing: List[Dict[str, Any]], fresh: List[SourceHealth]) -> List[Dict[str, Any]]:
    """Merge a run's health reports into the stored set.

    ``last_success_at`` is carried forward so a source that fails today still
    shows when it last worked.
    """
    by_name = {entry.get("name"): dict(entry) for entry in existing}
    for report in fresh:
        previous = by_name.get(report.name, {})
        record = report.to_dict()
        if report.status == SourceStatus.HEALTHY:
            record["last_success_at"] = report.checked_at
        else:
            record["last_success_at"] = previous.get("last_success_at")
        by_name[report.name] = record
    return sorted(by_name.values(), key=lambda entry: entry.get("name") or "")
