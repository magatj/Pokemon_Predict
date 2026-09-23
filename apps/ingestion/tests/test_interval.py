"""Recurring-interval detection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pokevend.forecast.interval import consecutive_gaps_minutes, detect_interval, interval_score

BASE = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def times(*offsets_minutes):
    return [BASE + timedelta(minutes=offset) for offset in offsets_minutes]


def test_hourly_events_detect_a_60_minute_interval():
    """12:37, 1:37, 2:37, 3:37 -> 60 minutes."""
    detected = detect_interval(times(37, 97, 157, 217))
    assert detected["intervalMinutes"] == 60
    assert detected["support"] == 1.0
    assert detected["sampleCount"] == 4


def test_half_hourly_events_detect_a_30_minute_interval():
    """12:12, 12:42, 1:12, 1:42 -> 30 minutes."""
    detected = detect_interval(times(12, 42, 72, 102))
    assert detected["intervalMinutes"] == 30


def test_hourly_events_are_not_reported_as_30_minutes():
    """60 is a multiple of 30, so the tie must break toward the observed gap."""
    detected = detect_interval(times(0, 60, 120, 180, 240))
    assert detected["intervalMinutes"] == 60


def test_small_jitter_is_tolerated():
    detected = detect_interval(times(0, 62, 119, 181), tolerance_minutes=4)
    assert detected["intervalMinutes"] == 60


def test_a_missed_observation_still_supports_the_cadence():
    """A skipped report shows up as a double gap, which is still a multiple."""
    detected = detect_interval(times(0, 60, 180, 240, 300))
    assert detected["intervalMinutes"] == 60


def test_too_few_events_yields_no_interval():
    assert detect_interval(times(0, 60, 120), min_samples=4) is None
    assert detect_interval([]) is None


def test_irregular_events_yield_no_interval():
    assert detect_interval(times(0, 7, 53, 61, 200, 202), min_support=0.5) is None


def test_support_threshold_is_enforced():
    # Three of five gaps are hourly; below a 0.9 support requirement that is not
    # enough to call the cadence established.
    stamps = times(0, 60, 120, 133, 400, 460)
    assert detect_interval(stamps, min_support=0.9) is None
    assert detect_interval(stamps, min_support=0.5) is not None


def test_consecutive_gaps_are_order_independent():
    assert consecutive_gaps_minutes(times(120, 0, 60)) == [60.0, 60.0]


# -- scoring -------------------------------------------------------------

def test_score_peaks_when_the_next_event_is_due():
    detected = detect_interval(times(0, 60, 120, 180))

    due = interval_score(detected, 60.0)
    early = interval_score(detected, 30.0)

    assert due > 0
    assert early == 0.0


def test_score_is_zero_without_an_interval_or_history():
    detected = detect_interval(times(0, 60, 120, 180))
    assert interval_score(None, 60.0) == 0.0
    assert interval_score(detected, None) == 0.0


@pytest.mark.parametrize("since", [59.0, 60.0, 61.0, 120.0])
def test_score_recognises_multiples_of_the_interval(since):
    detected = detect_interval(times(0, 60, 120, 180))
    assert interval_score(detected, since) > 0
