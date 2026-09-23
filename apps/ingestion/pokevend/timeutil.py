"""Timestamp helpers.

Python 3.8's ``datetime.fromisoformat`` rejects a trailing ``Z``, and sources
emit a mix of offsets, so all parsing funnels through here.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

_ISO_Z = re.compile(r"Z$", re.IGNORECASE)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso8601(value) -> Optional[datetime]:
    """Parse an ISO-8601 string (or epoch seconds) into an aware UTC datetime.

    Returns ``None`` rather than raising: a single malformed timestamp in a
    community post must never abort an ingestion run.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    text = _ISO_Z.sub("+00:00", text)
    # Normalise "+0000" to "+00:00" for 3.8's stricter parser.
    match = re.search(r"([+-])(\d{2})(\d{2})$", text)
    if match:
        text = text[: match.start()] + "{}{}:{}".format(*match.groups())
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def to_iso8601(value: datetime) -> str:
    """Render an aware datetime as a ``Z``-suffixed UTC string."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hours_between(later: datetime, earlier: datetime) -> float:
    return (later - earlier).total_seconds() / 3600.0


def minutes_between(later: datetime, earlier: datetime) -> float:
    return (later - earlier).total_seconds() / 60.0


def floor_to_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def add_minutes(value: datetime, minutes: float) -> datetime:
    return value + timedelta(minutes=minutes)
