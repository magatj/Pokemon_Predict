"""Vending machine records."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class SourceAuthority:
    """Ordered confidence tiers for where a fact came from.

    A lower-authority source may add detail to a machine record but must never
    overwrite a field established by a higher-authority one.
    """

    OFFICIAL = "OFFICIAL"
    VERIFICATION = "VERIFICATION"
    SUPPLEMENTAL = "SUPPLEMENTAL"
    COMMUNITY = "COMMUNITY"

    RANK = {OFFICIAL: 4, VERIFICATION: 3, SUPPLEMENTAL: 2, COMMUNITY: 1}

    @classmethod
    def rank(cls, authority: str) -> int:
        return cls.RANK.get(authority, 0)

    @classmethod
    def outranks(cls, candidate: str, incumbent: str) -> bool:
        return cls.rank(candidate) > cls.rank(incumbent)


@dataclass
class Machine:
    """A discovered vending machine.

    ``distance_miles`` is always computed locally with the Haversine formula
    from the active search centroid, never taken from a source.
    """

    id: str
    retailer: str
    name: str
    address: str
    city: str
    state: str
    zip: str
    latitude: float
    longitude: float
    source: str
    source_authority: str = SourceAuthority.OFFICIAL
    source_url: Optional[str] = None
    distance_miles: Optional[float] = None
    discovered_at: Optional[str] = None
    last_verified_at: Optional[str] = None
    # Filled in by verification adapters (retailer websites).
    store_hours: Optional[Dict[str, Any]] = None
    kiosk_listed: Optional[bool] = None
    verifications: List[Dict[str, Any]] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Machine:
        known = {f for f in cls.__dataclass_fields__}  # noqa: C416 - explicit for clarity
        return cls(**{k: v for k, v in data.items() if k in known})

    def label(self) -> str:
        """Human-facing name used in match aliases and explanations."""
        return f"{self.retailer} {self.city}".strip()
