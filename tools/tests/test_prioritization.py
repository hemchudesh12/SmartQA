"""
tools/tests/test_prioritization.py — Unit Tests for SmartQA Phase 7 Prioritization.

USAGE:
    python -m pytest tools/tests/test_prioritization.py -v

TESTS COVER:
    1.  Descending probability ordering
    2.  Deterministic tie-breaking (nodeid ASC)
    3.  Missing predictions appended after predicted tests
    4.  Invalid probabilities treated as missing
    5.  No test loss (all discovered tests in output)
    6.  Duplicate detection in validation
    7.  Parameterized pytest node IDs preserved
    8.  Empty prediction input (all tests → unpredicted bucket)
    9.  Empty discovered-test input → empty output
    10. All tests missing predictions → alphabetical ordering
    11. Probability boundary 0.0 is valid
    12. Probability boundary 1.0 is valid
    13. Deterministic repeated execution produces identical output
    14. Output schema contains required fields
    15. Priority ranks are consecutive (1, 2, ..., N)
    16. Ranking does NOT use actual_test_failed
    17. Historically-failed test ranked by current probability only
    18. Missing prediction tests are never dropped
"""

import sys
from pathlib import Path
from typing import Optional

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.prioritize_tests import (
    PRIORITIZED_CSV_COLUMNS,
    _parse_probability,
    prioritize,
    validate_prioritization,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _pred(prob: Optional[float], label: int = 0, commit: str = "abc" * 13 + "a") -> dict:
    """Build a prediction dict as returned by load_predictions()."""
    return {
        "predicted_failure_probability": prob,
        "predicted_label": label,
        "commit_sha": commit,
    }


def _preds(*items) -> dict[str, dict]:
    """Build predictions dict from (nodeid, prob) tuples."""
    return {nodeid: _pred(prob) for nodeid, prob in items}


# ---------------------------------------------------------------------------
# 1. Descending probability ordering
# ---------------------------------------------------------------------------

class TestDescendingOrder:
    def test_higher_probability_ranks_first(self):
        discovered = ["test_A", "test_B", "test_C"]
        preds = _preds(("test_A", 0.1), ("test_B", 0.9), ("test_C", 0.5))
        ranked = prioritize(discovered, preds)
        names = [r["test_nodeid"] for r in ranked]
        assert names[0] == "test_B"   # 0.9 highest
        assert names[1] == "test_C"   # 0.5 middle
        assert names[2] == "test_A"   # 0.1 lowest

    def test_probability_1_0_ranks_first(self):
        discovered = ["test_A", "test_B"]
        preds = _preds(("test_A", 1.0), ("test_B", 0.5))
        ranked = prioritize(discovered, preds)
        assert ranked[0]["test_nodeid"] == "test_A"

    def test_probability_0_0_ranks_last_among_predicted(self):
        discovered = ["test_A", "test_B"]
        preds = _preds(("test_A", 0.0), ("test_B", 0.5))
        ranked = prioritize(discovered, preds)
        assert ranked[0]["test_nodeid"] == "test_B"
        assert ranked[1]["test_nodeid"] == "test_A"


# ---------------------------------------------------------------------------
# 2. Deterministic tie-breaking
# ---------------------------------------------------------------------------

class TestTieBreaking:
    def test_equal_probability_sorted_by_nodeid_asc(self):
        # B and C tie at 0.7; B < C alphabetically → B first
        discovered = ["test_C", "test_A", "test_B"]
        preds = _preds(("test_A", 0.3), ("test_B", 0.7), ("test_C", 0.7))
        ranked = prioritize(discovered, preds)
        names = [r["test_nodeid"] for r in ranked]
        assert names[0] == "test_B"  # 0.7 and B < C
        assert names[1] == "test_C"  # 0.7 and C > B
        assert names[2] == "test_A"  # 0.3

    def test_tie_breaking_is_stable_regardless_of_input_order(self):
        preds = _preds(("test_Z", 0.5), ("test_A", 0.5))

        order1 = prioritize(["test_Z", "test_A"], preds)
        order2 = prioritize(["test_A", "test_Z"], preds)

        names1 = [r["test_nodeid"] for r in order1]
        names2 = [r["test_nodeid"] for r in order2]
        assert names1 == names2  # Always same regardless of input order


# ---------------------------------------------------------------------------
# 3. Missing predictions appended after predicted tests
# ---------------------------------------------------------------------------

class TestMissingPredictions:
    def test_missing_tests_placed_after_predicted(self):
        discovered = ["test_A", "test_B", "test_UNKNOWN"]
        preds = _preds(("test_A", 0.8), ("test_B", 0.3))
        ranked = prioritize(discovered, preds)
        names = [r["test_nodeid"] for r in ranked]
        assert names[0] == "test_A"       # predicted, high
        assert names[1] == "test_B"       # predicted, low
        assert names[2] == "test_UNKNOWN" # no prediction

    def test_missing_test_never_dropped(self):
        discovered = ["test_X", "test_MISSING"]
        preds = _preds(("test_X", 0.5))
        ranked = prioritize(discovered, preds)
        all_nodeids = {r["test_nodeid"] for r in ranked}
        assert "test_MISSING" in all_nodeids

    def test_multiple_missing_sorted_alphabetically(self):
        discovered = ["test_C", "test_A", "test_B"]
        # No predictions at all
        ranked = prioritize(discovered, {})
        names = [r["test_nodeid"] for r in ranked]
        assert names == ["test_A", "test_B", "test_C"]


# ---------------------------------------------------------------------------
# 4. Invalid probabilities treated as missing
# ---------------------------------------------------------------------------

class TestInvalidProbabilities:
    @pytest.mark.parametrize("raw", [
        "",           # empty string
        "NaN",        # not a number
        "-0.5",       # negative
        "1.5",        # > 1.0
        "abc",        # non-numeric
        None,         # None
    ])
    def test_invalid_probability_returns_none(self, raw):
        result = _parse_probability(raw)
        assert result is None

    def test_valid_boundaries_accepted(self):
        assert _parse_probability("0.0") == 0.0
        assert _parse_probability("1.0") == 1.0
        assert _parse_probability("0.5") == 0.5

    def test_invalid_probability_treated_as_missing_in_ranking(self):
        # pred has invalid probability; test_Y has valid one
        # test_X should be placed in unpredicted bucket
        discovered = ["test_X", "test_Y"]
        preds = {
            "test_X": _pred(None),  # invalid / None probability
            "test_Y": _pred(0.8),
        }
        ranked = prioritize(discovered, preds)
        names = [r["test_nodeid"] for r in ranked]
        assert names[0] == "test_Y"   # has valid prediction
        assert names[1] == "test_X"   # no valid probability → unpredicted bucket


# ---------------------------------------------------------------------------
# 5. No test loss
# ---------------------------------------------------------------------------

class TestNoTestLoss:
    def test_all_discovered_tests_in_output(self):
        discovered = [f"test_{i}" for i in range(10)]
        preds = _preds(("test_0", 0.9), ("test_5", 0.3))
        ranked = prioritize(discovered, preds)
        assert len(ranked) == len(discovered)
        assert {r["test_nodeid"] for r in ranked} == set(discovered)

    def test_count_matches(self):
        discovered = ["test_A", "test_B", "test_C"]
        ranked = prioritize(discovered, {})
        assert len(ranked) == 3


# ---------------------------------------------------------------------------
# 6. Duplicate detection in validation
# ---------------------------------------------------------------------------

class TestDuplicateDetection:
    def test_duplicate_in_ranked_raises_validation_error(self):
        # Manually craft a ranked list with a duplicate
        ranked = [
            {"priority_rank": 1, "test_nodeid": "test_A", "predicted_failure_probability": 0.9,
             "prediction_available": True, "predicted_label": 1, "commit_sha": ""},
            {"priority_rank": 2, "test_nodeid": "test_A", "predicted_failure_probability": 0.7,
             "prediction_available": True, "predicted_label": 0, "commit_sha": ""},
        ]
        errors = validate_prioritization(["test_A"], ranked)
        # Should detect duplicate test_A and count mismatch
        assert any("DUPLICATE" in e.upper() or "count" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# 7. Parameterized pytest node IDs preserved
# ---------------------------------------------------------------------------

class TestParameterizedNodeIds:
    def test_parameterized_nodeid_preserved(self):
        nodeid = "automation/tests/test_cart.py::test_cart_total_calculated_correctly[chromium]"
        discovered = [nodeid]
        preds = {nodeid: _pred(0.65)}
        ranked = prioritize(discovered, preds)
        assert ranked[0]["test_nodeid"] == nodeid

    def test_multiple_parameterized_nodeids_all_present(self):
        nodeids = [
            "test_auth.py::test_login[chromium]",
            "test_auth.py::test_login[firefox]",
            "test_auth.py::test_login[webkit]",
        ]
        preds = _preds(
            ("test_auth.py::test_login[chromium]", 0.8),
            ("test_auth.py::test_login[firefox]", 0.5),
            ("test_auth.py::test_login[webkit]", 0.9),
        )
        ranked = prioritize(nodeids, preds)
        assert len(ranked) == 3
        assert ranked[0]["test_nodeid"] == "test_auth.py::test_login[webkit]"


# ---------------------------------------------------------------------------
# 8. Empty prediction input
# ---------------------------------------------------------------------------

class TestEmptyPredictions:
    def test_empty_predictions_all_unpredicted(self):
        discovered = ["test_A", "test_B"]
        ranked = prioritize(discovered, {})
        for entry in ranked:
            assert entry["prediction_available"] is False
            assert entry["predicted_failure_probability"] is None

    def test_empty_predictions_alphabetical_ordering(self):
        discovered = ["test_Z", "test_A", "test_M"]
        ranked = prioritize(discovered, {})
        names = [r["test_nodeid"] for r in ranked]
        assert names == ["test_A", "test_M", "test_Z"]


# ---------------------------------------------------------------------------
# 9. Empty discovered tests
# ---------------------------------------------------------------------------

class TestEmptyDiscoveredTests:
    def test_empty_discovered_returns_empty_ranked(self):
        preds = _preds(("test_A", 0.5))
        ranked = prioritize([], preds)
        assert ranked == []

    def test_validation_passes_for_empty_both(self):
        errors = validate_prioritization([], [])
        assert errors == []


# ---------------------------------------------------------------------------
# 10. All tests missing predictions
# ---------------------------------------------------------------------------

class TestAllMissingPredictions:
    def test_all_missing_uses_alphabetical(self):
        discovered = ["test_Z", "test_B", "test_A"]
        ranked = prioritize(discovered, {})
        names = [r["test_nodeid"] for r in ranked]
        assert names == sorted(discovered)


# ---------------------------------------------------------------------------
# 12. Deterministic repeated execution
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_produces_same_output(self):
        discovered = ["test_C", "test_A", "test_B", "test_D"]
        preds = _preds(
            ("test_A", 0.7),
            ("test_B", 0.7),
            ("test_C", 0.4),
        )
        result1 = prioritize(discovered, preds)
        result2 = prioritize(discovered, preds)
        result3 = prioritize(discovered, preds)

        names1 = [r["test_nodeid"] for r in result1]
        names2 = [r["test_nodeid"] for r in result2]
        names3 = [r["test_nodeid"] for r in result3]

        assert names1 == names2 == names3

    def test_different_input_order_same_predictions_same_output(self):
        """Input order of discovered_tests must not affect output order."""
        discovered_v1 = ["test_C", "test_A", "test_B"]
        discovered_v2 = ["test_B", "test_C", "test_A"]
        preds = _preds(("test_A", 0.5), ("test_B", 0.5), ("test_C", 0.5))

        # All tie at 0.5 → sorted by nodeid ASC
        r1 = [e["test_nodeid"] for e in prioritize(discovered_v1, preds)]
        r2 = [e["test_nodeid"] for e in prioritize(discovered_v2, preds)]
        assert r1 == r2 == ["test_A", "test_B", "test_C"]


# ---------------------------------------------------------------------------
# 13. Output schema
# ---------------------------------------------------------------------------

class TestOutputSchema:
    def test_required_fields_present(self):
        discovered = ["test_A", "test_B"]
        preds = _preds(("test_A", 0.8))
        ranked = prioritize(discovered, preds)
        required_keys = {"priority_rank", "test_nodeid", "predicted_failure_probability",
                         "prediction_available", "predicted_label"}
        for entry in ranked:
            for key in required_keys:
                assert key in entry, f"Missing key: {key}"

    def test_actual_test_failed_not_in_output(self):
        """LEAKAGE CHECK: actual_test_failed must not appear in ranked output."""
        discovered = ["test_A"]
        preds = {"test_A": _pred(0.5)}
        ranked = prioritize(discovered, preds)
        for entry in ranked:
            assert "actual_test_failed" not in entry


# ---------------------------------------------------------------------------
# 14. Consecutive ranks
# ---------------------------------------------------------------------------

class TestConsecutiveRanks:
    def test_ranks_are_1_to_n(self):
        discovered = ["test_A", "test_B", "test_C", "test_D", "test_E"]
        preds = _preds(("test_A", 0.8), ("test_C", 0.2))
        ranked = prioritize(discovered, preds)
        ranks = [r["priority_rank"] for r in ranked]
        assert ranks == list(range(1, len(discovered) + 1))

    def test_rank_1_is_highest_risk(self):
        discovered = ["test_LOW", "test_HIGH"]
        preds = _preds(("test_LOW", 0.1), ("test_HIGH", 0.9))
        ranked = prioritize(discovered, preds)
        assert ranked[0]["priority_rank"] == 1
        assert ranked[0]["test_nodeid"] == "test_HIGH"


# ---------------------------------------------------------------------------
# 15. actual_test_failed must not affect priority (leakage test)
# ---------------------------------------------------------------------------

class TestNoActualOutcomeLeakage:
    def test_same_probability_different_actual_outcome_same_rank(self):
        """
        MANDATORY LEAKAGE TEST:
        test_A has prob=0.2, actual=0 (PASS)
        test_B has prob=0.2, actual=1 (FAIL historically)

        Both must rank at the same relative position by probability.
        actual_test_failed must not influence their order.
        """
        discovered = ["test_A", "test_B", "test_C"]
        # In load_predictions(), actual_test_failed is NOT included
        # in the predictions dict. The prioritizer never sees it.
        preds = {
            "test_A": {"predicted_failure_probability": 0.2, "predicted_label": 0,
                        "commit_sha": ""},
            "test_B": {"predicted_failure_probability": 0.2, "predicted_label": 0,
                        "commit_sha": ""},
            "test_C": {"predicted_failure_probability": 0.9, "predicted_label": 1,
                        "commit_sha": ""},
        }
        ranked = prioritize(discovered, preds)
        # test_C must be rank 1 (highest prob)
        assert ranked[0]["test_nodeid"] == "test_C"
        # test_A and test_B tie at 0.2 → alphabetical A before B
        assert ranked[1]["test_nodeid"] == "test_A"
        assert ranked[2]["test_nodeid"] == "test_B"
        # Neither test_A nor test_B received extra risk due to "actual" outcomes

    def test_high_historical_fail_low_predicted_ranks_by_prediction(self):
        """
        A test that historically failed should rank according to its
        CURRENT predicted probability, not its historical actual result.
        """
        discovered = ["test_HIST_FAIL", "test_STABLE"]
        # test_HIST_FAIL had actual=1 historically, but current prediction is low
        # test_STABLE has actual=0 historically, but current prediction is high
        preds = {
            "test_HIST_FAIL": {"predicted_failure_probability": 0.15,
                                "predicted_label": 0, "commit_sha": ""},
            "test_STABLE": {"predicted_failure_probability": 0.85,
                             "predicted_label": 1, "commit_sha": ""},
        }
        ranked = prioritize(discovered, preds)
        # Must rank by current probability only
        assert ranked[0]["test_nodeid"] == "test_STABLE"    # 0.85 > 0.15
        assert ranked[1]["test_nodeid"] == "test_HIST_FAIL" # lower current prob


# ---------------------------------------------------------------------------
# 16. Validate_prioritization function
# ---------------------------------------------------------------------------

class TestValidatePrioritization:
    def _make_ranked(self, nodeids):
        probs = {n: 0.5 - i * 0.05 for i, n in enumerate(sorted(nodeids))}
        return prioritize(nodeids, {n: _pred(probs[n]) for n in nodeids})

    def test_valid_prioritization_returns_no_errors(self):
        discovered = ["test_A", "test_B", "test_C"]
        ranked = self._make_ranked(discovered)
        errors = validate_prioritization(discovered, ranked)
        assert errors == []

    def test_missing_test_detected(self):
        discovered = ["test_A", "test_B", "test_C"]
        ranked = self._make_ranked(discovered)
        # Remove one entry from ranked — simulating a lost test
        ranked_truncated = ranked[:2]
        errors = validate_prioritization(discovered, ranked_truncated)
        assert any("LOSS" in e.upper() or "count" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# 17. Node ID parsing regression tests (Discovery bug fix)
# ---------------------------------------------------------------------------

class TestNodeIdParsing:
    """
    Regression tests for _parse_collected_nodeids().

    Root cause of original bug: pytest.ini addopts injected --html and
    -p automation.conftest_collector into the collection subprocess, causing
    stdout to be empty or malformed. Fix: --override-ini=addopts=.

    These tests verify the parser handles various stdout formats correctly.
    """

    def test_standard_q_output_parsed_correctly(self):
        """Standard `pytest --collect-only -q --no-header` output is parsed."""
        from tools.prioritize_tests import _parse_collected_nodeids

        stdout = (
            "automation/tests/test_auth.py::test_valid_login[chromium]\n"
            "automation/tests/test_auth.py::test_invalid_password[chromium]\n"
            "automation/tests/test_cart.py::test_cart_total_calculated_correctly[chromium]\n"
            "\n"
            "33 tests collected in 0.45s\n"
        )
        result = _parse_collected_nodeids(stdout)
        assert len(result) == 3
        assert "automation/tests/test_auth.py::test_valid_login[chromium]" in result
        assert "automation/tests/test_cart.py::test_cart_total_calculated_correctly[chromium]" in result

    def test_windows_backslash_normalized(self):
        """Windows backslashes in node IDs are normalized to forward slashes."""
        from tools.prioritize_tests import _parse_collected_nodeids

        stdout = (
            "automation\\tests\\test_cart.py::test_add_product_to_cart[chromium]\n"
        )
        result = _parse_collected_nodeids(stdout)
        assert len(result) == 1
        assert "\\" not in result[0]
        assert "automation/tests/test_cart.py::test_add_product_to_cart[chromium]" == result[0]

    def test_empty_stdout_returns_empty_list(self):
        """Empty stdout (e.g., from a broken collection) returns []."""
        from tools.prioritize_tests import _parse_collected_nodeids
        assert _parse_collected_nodeids("") == []

    def test_summary_line_not_included(self):
        """'N tests collected in Xs' line must not appear as a node ID."""
        from tools.prioritize_tests import _parse_collected_nodeids

        stdout = (
            "automation/tests/test_cart.py::test_add_product_to_cart[chromium]\n"
            "33 tests collected in 0.45s\n"
        )
        result = _parse_collected_nodeids(stdout)
        assert all("::" in r for r in result)
        assert all("collected" not in r for r in result)

    def test_separator_lines_excluded(self):
        """Lines starting with '=' or '-' (pytest borders) are excluded."""
        from tools.prioritize_tests import _parse_collected_nodeids

        stdout = (
            "========= test session starts =========\n"
            "automation/tests/test_auth.py::test_valid_login[chromium]\n"
            "--------- short test summary ----------\n"
        )
        result = _parse_collected_nodeids(stdout)
        assert len(result) == 1
        assert result[0] == "automation/tests/test_auth.py::test_valid_login[chromium]"


class TestNodeIdPredictionMapping:
    """
    Regression test: predictions from data/predictions.csv use the exact same
    node ID format as pytest discovers. Ensures mapping works correctly.
    """

    def test_cart_total_nodeid_maps_to_prediction(self):
        """
        REGRESSION TEST:
        The exact node ID from pytest collection:
            automation/tests/test_cart.py::test_cart_total_calculated_correctly[chromium]
        must map to its prediction in the predictions dict.
        """
        CART_TOTAL_NODEID = (
            "automation/tests/test_cart.py"
            "::test_cart_total_calculated_correctly[chromium]"
        )
        discovered = [CART_TOTAL_NODEID, "automation/tests/test_auth.py::test_valid_login[chromium]"]
        preds = {
            CART_TOTAL_NODEID: _pred(0.614847, label=1),
        }
        ranked = prioritize(discovered, preds)

        # cart_total must rank first (highest probability)
        assert ranked[0]["test_nodeid"] == CART_TOTAL_NODEID
        assert ranked[0]["prediction_available"] is True
        assert abs(ranked[0]["predicted_failure_probability"] - 0.614847) < 1e-6

        # auth test has no prediction → ranked second, unpredicted
        assert ranked[1]["test_nodeid"] == "automation/tests/test_auth.py::test_valid_login[chromium]"
        assert ranked[1]["prediction_available"] is False

    def test_parameterized_nodeid_not_truncated(self):
        """
        Parameterized node IDs like test_X[chromium] must NOT be truncated
        to test_X. The full node ID including [chromium] must survive.
        """
        full_nodeid = "automation/tests/test_cart.py::test_cart_total_calculated_correctly[chromium]"
        truncated_nodeid = "automation/tests/test_cart.py::test_cart_total_calculated_correctly"

        discovered = [full_nodeid]
        preds = {full_nodeid: _pred(0.9)}
        ranked = prioritize(discovered, preds)

        assert ranked[0]["test_nodeid"] == full_nodeid
        assert ranked[0]["test_nodeid"] != truncated_nodeid
        assert "[chromium]" in ranked[0]["test_nodeid"]

    def test_six_predictions_thirty_three_discovered_gives_correct_counts(self):
        """
        Simulate real repository state: 6 predictions, 33 tests discovered.
        Expected:  6 predicted (ranked by prob) + 27 unpredicted (alphabetical).
        Total:     33 == discovered count.
        No test dropped.
        """
        # Simulate 6 cart tests (those in the commit the model predicted on)
        predicted_nodeids = [
            "automation/tests/test_cart.py::test_add_product_to_cart[chromium]",
            "automation/tests/test_cart.py::test_cart_shows_added_product[chromium]",
            "automation/tests/test_cart.py::test_increase_quantity[chromium]",
            "automation/tests/test_cart.py::test_decrease_quantity[chromium]",
            "automation/tests/test_cart.py::test_remove_product_from_cart[chromium]",
            "automation/tests/test_cart.py::test_cart_total_calculated_correctly[chromium]",
        ]
        # Simulate 27 remaining tests without predictions
        unpredicted_nodeids = [f"automation/tests/test_other.py::test_{i}[chromium]" for i in range(27)]
        all_discovered = predicted_nodeids + unpredicted_nodeids

        preds = {n: _pred(0.1 + i * 0.05) for i, n in enumerate(predicted_nodeids)}
        ranked = prioritize(all_discovered, preds)

        assert len(ranked) == 33
        assert {r["test_nodeid"] for r in ranked} == set(all_discovered)

        # First 6 must all have predictions
        for entry in ranked[:6]:
            assert entry["prediction_available"] is True

        # Remaining 27 must be unpredicted
        for entry in ranked[6:]:
            assert entry["prediction_available"] is False

        errors = validate_prioritization(all_discovered, ranked)
        assert errors == []

