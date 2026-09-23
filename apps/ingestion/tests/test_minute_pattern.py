"""Minute-of-hour clustering."""
from __future__ import annotations

import pytest

from pokevend.forecast.minute_pattern import (
    circular_distance,
    circular_mean,
    detect_minute_pattern,
    minute_pattern_score,
)


def test_clusters_scattered_minutes_onto_one_pattern_minute():
    """The worked example from the spec: :36 / :37 / :38 collapse to :37."""
    pattern = detect_minute_pattern([37, 36, 38, 37, 37, 38], tolerance=3, min_samples=4)

    assert pattern["patternMinute"] == 37
    assert pattern["toleranceMinutes"] == 3
    assert pattern["sampleCount"] == 6
    assert pattern["support"] == 1.0


def test_support_reflects_the_share_of_observations_in_the_cluster():
    pattern = detect_minute_pattern([37, 36, 38, 37, 5, 20], tolerance=3, min_samples=4)
    assert pattern["sampleCount"] == 4
    assert pattern["totalSamples"] == 6
    assert pattern["support"] == pytest.approx(4 / 6, abs=0.001)


def test_exact_minute_match_is_not_required():
    pattern = detect_minute_pattern([15, 17, 13, 16], tolerance=3, min_samples=4)
    assert pattern is not None
    assert abs(circular_distance(pattern["patternMinute"], 15)) <= 2


def test_cluster_spanning_the_hour_boundary():
    """:58, :59, :00, :01 is one cluster, not two."""
    pattern = detect_minute_pattern([58, 59, 0, 1], tolerance=3, min_samples=4)
    assert pattern is not None
    assert pattern["sampleCount"] == 4
    assert circular_distance(pattern["patternMinute"], 59) <= 1


def test_too_few_samples_yields_no_pattern():
    assert detect_minute_pattern([37, 37], tolerance=3, min_samples=4) is None
    assert detect_minute_pattern([], tolerance=3, min_samples=4) is None


def test_scattered_minutes_do_not_reach_the_sample_threshold():
    assert detect_minute_pattern([1, 14, 27, 41, 55], tolerance=3, min_samples=4) is None


def test_weights_move_the_pattern_toward_stronger_evidence():
    minutes = [10, 10, 10, 10, 40, 40, 40, 40]
    light = [1, 1, 1, 1, 0.1, 0.1, 0.1, 0.1]
    heavy = [0.1, 0.1, 0.1, 0.1, 1, 1, 1, 1]

    assert detect_minute_pattern(minutes, weights=light)["patternMinute"] == 10
    assert detect_minute_pattern(minutes, weights=heavy)["patternMinute"] == 40


def test_zero_total_weight_is_not_a_pattern():
    assert detect_minute_pattern([1, 2, 3, 4], weights=[0, 0, 0, 0]) is None


# -- circular helpers ----------------------------------------------------

@pytest.mark.parametrize(
    "left,right,expected", [(0, 0, 0), (1, 59, 2), (59, 1, 2), (0, 30, 30), (10, 20, 10)]
)
def test_circular_distance(left, right, expected):
    assert circular_distance(left, right) == expected


def test_circular_mean_wraps_correctly():
    assert circular_mean([59, 0, 1]) == pytest.approx(0, abs=0.01)
    assert circular_mean([10, 20]) == pytest.approx(15, abs=0.01)


# -- scoring -------------------------------------------------------------

def test_score_peaks_on_the_pattern_minute():
    pattern = detect_minute_pattern([37] * 6, tolerance=3, min_samples=4)
    on = minute_pattern_score(pattern, 37)
    near = minute_pattern_score(pattern, 39)
    off = minute_pattern_score(pattern, 12)

    assert on > near > off == 0.0


def test_score_is_zero_without_a_pattern():
    assert minute_pattern_score(None, 37) == 0.0
