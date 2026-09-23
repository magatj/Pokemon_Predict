"""Local-time conversion for time-of-day features.

Minute-of-hour, hour-of-day and weekday patterns only mean anything in the
machine's own local time, so every feature is computed after converting out of
UTC.

``zoneinfo`` is used when the runtime provides it (Python 3.9+). On 3.8 there is
no stdlib tz database, so a US DST implementation is used instead: the rules
(second Sunday in March, first Sunday in November) are fixed in US federal law
and cover every machine in scope.
"""
from __future__ import annotations

from datetime import datetime, timedelta, tzinfo
from typing import Optional

try:  # pragma: no cover - depends on runtime version
    from zoneinfo import ZoneInfo  # type: ignore

    _HAVE_ZONEINFO = True
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore
    _HAVE_ZONEINFO = False


#: Standard offsets for the US zones a machine in scope can sit in.
_US_ZONE_OFFSETS = {
    "America/Los_Angeles": -8,
    "America/Denver": -7,
    "America/Phoenix": -7,  # no DST
    "America/Chicago": -6,
    "America/New_York": -5,
}

_NO_DST_ZONES = frozenset({"America/Phoenix"})


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> datetime:
    """The nth given weekday of a month (weekday: Monday=0 ... Sunday=6)."""
    day = datetime(year, month, 1)
    offset = (weekday - day.weekday()) % 7
    return day + timedelta(days=offset + 7 * (nth - 1))


def us_dst_bounds(year: int):
    """DST start/end in local standard time: 2nd Sunday March -> 1st Sunday Nov."""
    start = _nth_weekday(year, 3, 6, 2).replace(hour=2)
    end = _nth_weekday(year, 11, 6, 1).replace(hour=2)
    return start, end


class USTimeZone(tzinfo):
    """Fallback tzinfo implementing the US DST rules."""

    def __init__(self, name: str, standard_offset_hours: int, observes_dst: bool = True):
        self._name = name
        self._standard = timedelta(hours=standard_offset_hours)
        self._observes_dst = observes_dst

    def utcoffset(self, dt: Optional[datetime]) -> timedelta:
        return self._standard + self.dst(dt)

    def dst(self, dt: Optional[datetime]) -> timedelta:
        if dt is None or not self._observes_dst:
            return timedelta(0)
        naive = dt.replace(tzinfo=None)
        start, end = us_dst_bounds(naive.year)
        return timedelta(hours=1) if start <= naive < end else timedelta(0)

    def tzname(self, dt: Optional[datetime]) -> str:
        return self._name


def get_timezone(name: str = "America/Los_Angeles"):
    """Return a tzinfo for ``name``, preferring the stdlib tz database."""
    if _HAVE_ZONEINFO:
        try:
            return ZoneInfo(name)
        except Exception:  # noqa: BLE001 - missing tzdata falls through
            pass
    offset = _US_ZONE_OFFSETS.get(name)
    if offset is None:
        # Unknown zone with no tz database available: UTC is the honest answer.
        return USTimeZone("UTC", 0, observes_dst=False)
    return USTimeZone(name, offset, observes_dst=name not in _NO_DST_ZONES)


def to_local(value: datetime, timezone_name: str = "America/Los_Angeles") -> datetime:
    """Convert an aware UTC datetime into local time for the given zone."""
    return value.astimezone(get_timezone(timezone_name))
