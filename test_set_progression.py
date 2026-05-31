"""
Acceptance tests for bounded set progression (±1 per session).

Tests verify:
1. If last session was 5 sets, today must be 4, 5, or 6 — never 1 or 10.
2. High soreness/fatigue -> 5 -> 4 (not 5 -> 1).
3. Low soreness/fatigue -> 5 -> 6 (not 5 -> 10).
4. First session uses conservative default.
5. Smoothing with 2 sessions of history.
6. Finishers always stay at stored target.
"""

import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

# Ensure we can import from the project root
sys.path.insert(0, os.path.dirname(__file__))

from progression import (
    compute_feedback_adjustment,
    adjust_sets_based_on_feedback,
    get_last_n_muscle_group_set_counts,
    MIN_SETS,
    MAX_SETS_MAIN,
    FINISHER_TARGET_SETS,
    DEFAULT_BASE_WEIGHT,
)
from plan import DEFAULT_TARGET_SETS


# ---- Helpers to build mock objects ----

def make_mock_feedback(soreness, pump, workload):
    fb = MagicMock()
    fb.soreness = soreness
    fb.pump = pump
    fb.workload = workload
    fb.created_at = datetime.now()
    return fb


def make_mock_we(target_sets=4, exercise_name="Bench Press", muscle_group="Chest", is_finisher_name=False):
    we = MagicMock()
    we.id = 1
    we.target_sets = target_sets
    we.target_reps = 10
    we.exercise = MagicMock()
    we.exercise.name = exercise_name
    we.exercise.muscle_group = muscle_group
    return we


# ---- Tests for compute_feedback_adjustment ----

def test_feedback_low_returns_plus_1():
    """Under-stimulated (all low) should return +1."""
    mock_db = MagicMock()
    with patch("progression.get_recent_muscle_group_feedback") as mock_fb:
        mock_fb.return_value = [
            make_mock_feedback(1, 1, 1),
            make_mock_feedback(2, 2, 2),
            make_mock_feedback(1, 2, 1),
        ]
        adj = compute_feedback_adjustment(mock_db, "Chest")
        assert adj == +1, f"Expected +1 for low feedback, got {adj}"
    print("  PASS: Low feedback -> +1")


def test_feedback_high_soreness_returns_minus_1():
    """High soreness should return -1."""
    mock_db = MagicMock()
    with patch("progression.get_recent_muscle_group_feedback") as mock_fb:
        mock_fb.return_value = [
            make_mock_feedback(4, 3, 3),
            make_mock_feedback(5, 3, 3),
            make_mock_feedback(4, 3, 3),
        ]
        adj = compute_feedback_adjustment(mock_db, "Chest")
        assert adj == -1, f"Expected -1 for high soreness, got {adj}"
    print("  PASS: High soreness -> -1")


def test_feedback_high_workload_returns_minus_1():
    """High workload should return -1."""
    mock_db = MagicMock()
    with patch("progression.get_recent_muscle_group_feedback") as mock_fb:
        mock_fb.return_value = [
            make_mock_feedback(2, 3, 5),
            make_mock_feedback(2, 3, 4),
            make_mock_feedback(3, 3, 4),
        ]
        adj = compute_feedback_adjustment(mock_db, "Chest")
        assert adj == -1, f"Expected -1 for high workload, got {adj}"
    print("  PASS: High workload -> -1")


def test_feedback_moderate_returns_0():
    """Moderate feedback should return 0 (no change)."""
    mock_db = MagicMock()
    with patch("progression.get_recent_muscle_group_feedback") as mock_fb:
        mock_fb.return_value = [
            make_mock_feedback(3, 3, 3),
            make_mock_feedback(3, 3, 3),
        ]
        adj = compute_feedback_adjustment(mock_db, "Chest")
        assert adj == 0, f"Expected 0 for moderate feedback, got {adj}"
    print("  PASS: Moderate feedback -> 0")


def test_no_feedback_returns_0():
    """No feedback should return 0."""
    mock_db = MagicMock()
    with patch("progression.get_recent_muscle_group_feedback") as mock_fb:
        mock_fb.return_value = []
        adj = compute_feedback_adjustment(mock_db, "Chest")
        assert adj == 0, f"Expected 0 for no feedback, got {adj}"
    print("  PASS: No feedback -> 0")


# ---- Acceptance Tests for adjust_sets_based_on_feedback ----

def test_acceptance_5_sets_stays_in_range():
    """ACCEPTANCE: If last session was 5 sets, today must be 4, 5, or 6."""
    we = make_mock_we(target_sets=5)
    mock_db = MagicMock()

    for adj_val in [-1, 0, +1]:
        with patch("progression.get_last_n_muscle_group_set_counts", return_value=[5]):
            with patch("progression.compute_feedback_adjustment", return_value=adj_val):
                with patch("progression.is_finisher", return_value=False):
                    result = adjust_sets_based_on_feedback(mock_db, we)
                    assert result in (4, 5, 6), \
                        f"Last session=5, adj={adj_val}: got {result}, expected 4/5/6"
    print("  PASS: 5 sets -> only 4, 5, or 6 possible")


def test_acceptance_high_fatigue_drops_by_1_only():
    """ACCEPTANCE: High soreness -> 5 -> 4, NOT 5 -> 1."""
    we = make_mock_we(target_sets=5)
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[5]):
        with patch("progression.compute_feedback_adjustment", return_value=-1):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 4, f"Expected 4, got {result}"
    print("  PASS: High fatigue: 5 -> 4 (not 1)")


def test_acceptance_low_fatigue_increases_by_1_only():
    """ACCEPTANCE: Low feedback -> 5 -> 6, NOT 5 -> 10."""
    we = make_mock_we(target_sets=5)
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[5]):
        with patch("progression.compute_feedback_adjustment", return_value=+1):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 6, f"Expected 6, got {result}"
    print("  PASS: Low fatigue: 5 -> 6 (not 10)")


def test_acceptance_no_history_uses_default():
    """ACCEPTANCE: No history -> use conservative default."""
    we = make_mock_we(target_sets=4, muscle_group="Glutes")
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[]):
        with patch("progression.is_finisher", return_value=False):
            result = adjust_sets_based_on_feedback(mock_db, we)
            assert result == 4, f"Expected default {DEFAULT_TARGET_SETS}, got {result}"
    print(f"  PASS: No history -> default ({DEFAULT_TARGET_SETS})")


def test_acceptance_smoothing_with_2_sessions():
    """ACCEPTANCE: With 2 sessions (4 and 6), anchor = round(5) = 5."""
    we = make_mock_we(target_sets=5)
    mock_db = MagicMock()

    # Last session: 6 sets, previous: 4 sets -> average = 5
    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[6, 4]):
        with patch("progression.compute_feedback_adjustment", return_value=0):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 5, f"Expected 5 (avg of 6,4), got {result}"
    print("  PASS: Smoothing: avg(6,4)=5, adj=0 -> 5")


def test_acceptance_smoothing_with_adjustment():
    """ACCEPTANCE: With 2 sessions (5 and 5), + feedback -> 6."""
    we = make_mock_we(target_sets=5)
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[5, 5]):
        with patch("progression.compute_feedback_adjustment", return_value=+1):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 6, f"Expected 6, got {result}"
    print("  PASS: Smoothing: avg(5,5)=5, adj=+1 -> 6")


def test_acceptance_never_exceeds_cap():
    """ACCEPTANCE: At max sets + positive feedback -> stays at cap."""
    we = make_mock_we(target_sets=MAX_SETS_MAIN)
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[MAX_SETS_MAIN]):
        with patch("progression.compute_feedback_adjustment", return_value=+1):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == MAX_SETS_MAIN, \
                    f"Expected {MAX_SETS_MAIN}, got {result}"
    print(f"  PASS: At cap ({MAX_SETS_MAIN}), adj=+1 -> stays at {MAX_SETS_MAIN}")


def test_acceptance_never_below_volume_window():
    """ACCEPTANCE: At low history + negative feedback -> stays at muscle window minimum."""
    we = make_mock_we(target_sets=MIN_SETS, muscle_group="Chest")
    mock_db = MagicMock()

    with patch("progression.get_last_n_muscle_group_set_counts", return_value=[MIN_SETS]):
        with patch("progression.compute_feedback_adjustment", return_value=-1):
            with patch("progression.is_finisher", return_value=False):
                result = adjust_sets_based_on_feedback(mock_db, we)
                assert result == 4, f"Expected Chest minimum 4, got {result}"
    print("  PASS: Low history + negative feedback -> stays at Chest minimum (4)")


def test_acceptance_finisher_stays_at_1():
    """ACCEPTANCE: Finishers always stay at 1 set, even if DB says 3."""
    # Even if target_sets drifted to 3, finishers must return 1
    we = make_mock_we(target_sets=3, exercise_name="Single-arm Chest Fly")
    mock_db = MagicMock()

    with patch("progression.is_finisher", return_value=True):
        result = adjust_sets_based_on_feedback(mock_db, we)
        assert result == FINISHER_TARGET_SETS, \
            f"Expected {FINISHER_TARGET_SETS} for finisher, got {result}"
    print(f"  PASS: Finisher always returns {FINISHER_TARGET_SETS} (even if DB says 3)")


# ---- Run all tests ----

if __name__ == "__main__":
    print("\n=== Feedback Adjustment Tests ===")
    test_feedback_low_returns_plus_1()
    test_feedback_high_soreness_returns_minus_1()
    test_feedback_high_workload_returns_minus_1()
    test_feedback_moderate_returns_0()
    test_no_feedback_returns_0()

    print("\n=== Acceptance Tests: Bounded Set Progression ===")
    test_acceptance_5_sets_stays_in_range()
    test_acceptance_high_fatigue_drops_by_1_only()
    test_acceptance_low_fatigue_increases_by_1_only()
    test_acceptance_no_history_uses_default()
    test_acceptance_smoothing_with_2_sessions()
    test_acceptance_smoothing_with_adjustment()
    test_acceptance_never_exceeds_cap()
    test_acceptance_never_below_volume_window()
    test_acceptance_finisher_stays_at_1()

    print("\nOK: All tests passed!")
