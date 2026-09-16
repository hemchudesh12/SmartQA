"""
tools/tests/test_evaluation.py — Unit Tests for SmartQA Phase 8 Evaluation.

USAGE:
    python -m pytest tools/tests/test_evaluation.py -v

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
IMPORTANT — ACADEMIC INTEGRITY NOTICE
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

All test data in this module is FIXTURE DATA — synthetic data constructed
specifically to verify the mathematical correctness of evaluation functions.

FIXTURE DATA IS:
    - Clearly labeled as fixtures (prefixed with _make_ or _fixture_)
    - Contained within test functions only
    - Used solely to verify computation logic (APFD formula, rank arithmetic, etc.)

FIXTURE DATA IS NOT:
    - Real SmartQA project history
    - Real commit data
    - Real test execution results
    - Fabricated project performance metrics

The dashboard and evaluation scripts read ONLY from actual generated data files.
They never use fixture data from this module.
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

TESTS COVER:
    1.  first_failure_position — all passing → None
    2.  first_failure_position — failure at start → rank 1
    3.  first_failure_position — failure at end → rank N
    4.  first_failure_position — multiple failures → first rank returned
    5.  first_failure_position — empty ordered_tests → None
    6.  first_failure_position — failure not in ordering → None
    7.  compute_apfd — no failures → None
    8.  compute_apfd — empty test list → None
    9.  compute_apfd — single failure at position 1 (best case)
    10. compute_apfd — single failure at last position (worst case)
    11. compute_apfd — all tests fail (APFD = 0.5 + 1/(2n))
    12. compute_apfd — mathematical correctness of formula
    13. compute_apfd — result is in [0, 1]
    14. compute_apfd — single test single failure (boundary)
    15. apply_smartqa_order_to_run — in-order tests only
    16. apply_smartqa_order_to_run — tests not in SmartQA appended alphabetically
    17. apply_smartqa_order_to_run — all tests missing from SmartQA → alphabetical
    18. apply_smartqa_order_to_run — empty run → empty result
    19. apply_smartqa_order_to_run — no test is dropped
    20. evaluate_run — no failures, all metrics None
    21. evaluate_run — one failure, SmartQA rank 1 (best case)
    22. evaluate_run — one failure, SmartQA rank same as baseline
    23. evaluate_run — improvement computed correctly
    24. compute_dataset_stats — empty dataset
    25. compute_dataset_stats — all pass
    26. compute_dataset_stats — mix of PASS/FAIL/SKIP
    27. compute_dataset_stats — failure rate calculation
    28. group_results_by_run — grouping preserves order within run
    29. get_baseline_order — extracts nodeids in order
    30. get_failures_in_run — only FAIL and ERROR included
    31. load_test_results — missing file → empty list
    32. load_prioritized_order — missing file → empty list
    33. Evaluation output schema validation
    34. Determinism — same inputs → same outputs
    35. APFD edge case — exactly 2 tests, 1 failure at each position
    36. Dashboard data_loader — missing file graceful defaults
    37. Dashboard data_loader — empty JSONL graceful defaults
    38. Dashboard data_loader — malformed JSONL lines skipped
"""

import json
import sys
from pathlib import Path
from typing import Optional

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.evaluate_prioritization import (
    apply_smartqa_order_to_run,
    compute_apfd,
    compute_dataset_stats,
    first_failure_position,
    get_baseline_order,
    get_failures_in_run,
    group_results_by_run,
    load_prioritized_order,
    load_test_results,
    evaluate_run,
)


# ---------------------------------------------------------------------------
# FIXTURE HELPERS
# Note: these helpers build SYNTHETIC data for mathematical unit tests only.
# ---------------------------------------------------------------------------

def _make_result_row(
    run_id: str,
    nodeid: str,
    status: str,
    commit_sha: str = "aabbccdd" * 5,
    duration: float = 0.5,
) -> dict:
    """Build a synthetic test result row for fixture use."""
    return {
        "run_id": run_id,
        "test_nodeid": nodeid,
        "status": status,
        "commit_sha": commit_sha,
        "duration_sec": duration,
        "failure_message": "" if status.upper() == "PASS" else "AssertionError",
        "run_timestamp_iso": f"2026-01-01T{run_id[:2]}:00:00+00:00",
    }


def _make_run(run_id: str, nodeids: list[str], statuses: list[str]) -> list[dict]:
    """Build a list of synthetic result rows for a single run."""
    return [
        _make_result_row(run_id, nid, stat)
        for nid, stat in zip(nodeids, statuses)
    ]


# ===========================================================================
# 1-6. first_failure_position
# ===========================================================================

class TestFirstFailurePosition:

    def test_all_passing_returns_none(self):
        """[FIXTURE] No failures → None returned."""
        ordered = ["test_A", "test_B", "test_C"]
        failures = set()
        assert first_failure_position(ordered, failures) is None

    def test_failure_at_first_position(self):
        """[FIXTURE] Failure at rank 1."""
        ordered = ["test_FAIL", "test_B", "test_C"]
        failures = {"test_FAIL"}
        assert first_failure_position(ordered, failures) == 1

    def test_failure_at_last_position(self):
        """[FIXTURE] Failure at rank N (last)."""
        ordered = ["test_A", "test_B", "test_FAIL"]
        failures = {"test_FAIL"}
        assert first_failure_position(ordered, failures) == 3

    def test_multiple_failures_returns_first(self):
        """[FIXTURE] Multiple failures → earliest rank returned."""
        ordered = ["test_A", "test_FAIL1", "test_FAIL2", "test_D"]
        failures = {"test_FAIL1", "test_FAIL2"}
        result = first_failure_position(ordered, failures)
        assert result == 2  # test_FAIL1 is at index 1 (rank 2)

    def test_empty_ordered_tests_returns_none(self):
        """[FIXTURE] Empty ordering → None."""
        assert first_failure_position([], {"test_FAIL"}) is None

    def test_failure_not_in_ordering_returns_none(self):
        """[FIXTURE] Failure not present in ordering → None."""
        ordered = ["test_A", "test_B"]
        failures = {"test_UNKNOWN"}
        assert first_failure_position(ordered, failures) is None

    def test_rank_is_one_based(self):
        """[FIXTURE] First item returns rank 1, not 0."""
        ordered = ["test_X"]
        assert first_failure_position(ordered, {"test_X"}) == 1


# ===========================================================================
# 7-14. compute_apfd
# ===========================================================================

class TestComputeApfd:

    def test_no_failures_returns_none(self):
        """[FIXTURE] No failures → APFD undefined → None."""
        ordered = ["test_A", "test_B", "test_C"]
        assert compute_apfd(ordered, set()) is None

    def test_empty_test_list_returns_none(self):
        """[FIXTURE] Empty test list → APFD undefined → None."""
        assert compute_apfd([], {"test_A"}) is None

    def test_single_failure_at_position_1_is_best_case(self):
        """
        [FIXTURE] Best case: single failure at rank 1 of N=5.
        APFD = 1 - (1 / (5 × 1)) + 1/(2 × 5)
             = 1 - 0.2 + 0.1
             = 0.9
        """
        ordered = ["F", "A", "B", "C", "D"]
        failures = {"F"}
        result = compute_apfd(ordered, failures)
        expected = round(1.0 - (1 / (5 * 1)) + (1 / (2 * 5)), 4)
        assert result == expected
        assert abs(result - 0.9) < 1e-6

    def test_single_failure_at_last_position_is_worst_case(self):
        """
        [FIXTURE] Worst case: single failure at rank N=5.
        APFD = 1 - (5 / (5 × 1)) + 1/(2 × 5)
             = 1 - 1.0 + 0.1
             = 0.1
        """
        ordered = ["A", "B", "C", "D", "F"]
        failures = {"F"}
        result = compute_apfd(ordered, failures)
        expected = round(1.0 - (5 / (5 * 1)) + (1 / (2 * 5)), 4)
        assert result == expected
        assert abs(result - 0.1) < 1e-6

    def test_all_tests_fail(self):
        """
        [FIXTURE] All 4 tests fail.
        APFD = 1 - (1+2+3+4) / (4×4) + 1/(2×4)
             = 1 - 10/16 + 1/8
             = 1 - 0.625 + 0.125
             = 0.5
        """
        ordered = ["A", "B", "C", "D"]
        failures = {"A", "B", "C", "D"}
        result = compute_apfd(ordered, failures)
        expected = round(1.0 - (1 + 2 + 3 + 4) / (4 * 4) + (1 / (2 * 4)), 4)
        assert result == expected
        assert abs(result - 0.5) < 1e-6

    def test_apfd_formula_mathematical_correctness(self):
        """
        [FIXTURE] Manual calculation check.
        ordered = [A, F1, B, F2, C]  (n=5, m=2)
        TF1=2 (F1 at rank 2), TF2=4 (F2 at rank 4)
        APFD = 1 - (2+4)/(5×2) + 1/(2×5)
             = 1 - 6/10 + 0.1
             = 1 - 0.6 + 0.1
             = 0.5
        """
        ordered = ["A", "F1", "B", "F2", "C"]
        failures = {"F1", "F2"}
        result = compute_apfd(ordered, failures)
        expected = round(1.0 - (2 + 4) / (5 * 2) + (1 / (2 * 5)), 4)
        assert result == expected

    def test_apfd_result_in_valid_range(self):
        """[FIXTURE] APFD must always be in [0, 1]."""
        ordered = [f"test_{i}" for i in range(10)]
        for fail_pos in range(10):
            failures = {f"test_{fail_pos}"}
            result = compute_apfd(ordered, failures)
            assert result is not None
            assert 0.0 <= result <= 1.0, f"APFD out of range at fail_pos={fail_pos}: {result}"

    def test_single_test_single_failure_boundary(self):
        """
        [FIXTURE] n=1, m=1, failure at rank 1.
        APFD = 1 - (1/(1×1)) + 1/(2×1) = 1 - 1 + 0.5 = 0.5
        """
        ordered = ["only_test"]
        failures = {"only_test"}
        result = compute_apfd(ordered, failures)
        assert result == 0.5

    def test_apfd_values_for_n_33_failure_at_rank_1_vs_18(self):
        """
        [FIXTURE] Simulate real project scenario (n=33, 1 failure).
        At rank 1 (SmartQA): APFD = 1 - 1/33 + 1/66 ≈ 0.9849
        At rank 18 (baseline): APFD = 1 - 18/33 + 1/66 ≈ 0.4697
        NOTE: This uses n=33 tests as in the real project, but with
        FIXTURE data. Does NOT represent actual project measurements.
        """
        ordered_33 = [f"test_{i}" for i in range(1, 34)]
        failing_test = "test_1"   # rank 1

        apfd_rank1 = compute_apfd(ordered_33, {failing_test})
        expected_rank1 = round(1.0 - (1 / (33 * 1)) + (1 / (2 * 33)), 4)
        assert apfd_rank1 == expected_rank1
        assert abs(apfd_rank1 - 0.9848) < 0.001

        failing_test_18 = "test_18"  # rank 18
        apfd_rank18 = compute_apfd(ordered_33, {failing_test_18})
        expected_rank18 = round(1.0 - (18 / (33 * 1)) + (1 / (2 * 33)), 4)
        assert apfd_rank18 == expected_rank18
        assert abs(apfd_rank18 - 0.4697) < 0.001

        # SmartQA-like ordering should have higher APFD than baseline-like ordering
        assert apfd_rank1 > apfd_rank18


# ===========================================================================
# 15-19. apply_smartqa_order_to_run
# ===========================================================================

class TestApplySmartqaOrderToRun:

    def test_all_tests_in_smartqa_preserves_smartqa_order(self):
        """[FIXTURE] All run tests are in SmartQA → order preserved."""
        smartqa_ordered = ["test_C", "test_A", "test_B"]  # priority order
        run_nodeids = {"test_A", "test_B", "test_C"}
        result = apply_smartqa_order_to_run(smartqa_ordered, run_nodeids)
        assert result == ["test_C", "test_A", "test_B"]

    def test_tests_not_in_smartqa_appended_alphabetically(self):
        """[FIXTURE] Extra run tests not in SmartQA → appended alphabetically."""
        smartqa_ordered = ["test_B", "test_A"]
        run_nodeids = {"test_A", "test_B", "test_Z", "test_M"}
        result = apply_smartqa_order_to_run(smartqa_ordered, run_nodeids)
        # SmartQA tests first, then extra tests alphabetically
        assert result[:2] == ["test_B", "test_A"]
        assert result[2:] == ["test_M", "test_Z"]  # alphabetical

    def test_no_tests_in_smartqa_all_alphabetical(self):
        """[FIXTURE] No run tests in SmartQA → alphabetical order."""
        smartqa_ordered = ["smartqa_only_test"]
        run_nodeids = {"test_Z", "test_A", "test_M"}
        result = apply_smartqa_order_to_run(smartqa_ordered, run_nodeids)
        assert result == ["test_A", "test_M", "test_Z"]

    def test_empty_run_returns_empty(self):
        """[FIXTURE] Empty run → empty result."""
        result = apply_smartqa_order_to_run(["test_A", "test_B"], set())
        assert result == []

    def test_no_test_is_dropped(self):
        """[FIXTURE] Every test in run_nodeids appears in result."""
        smartqa_ordered = ["test_C", "test_A"]
        run_nodeids = {"test_A", "test_B", "test_C", "test_D"}
        result = apply_smartqa_order_to_run(smartqa_ordered, run_nodeids)
        assert set(result) == run_nodeids

    def test_partial_overlap_correct_structure(self):
        """[FIXTURE] Partial overlap: SmartQA tests in priority order, rest alphabetical."""
        smartqa_ordered = ["high", "medium", "low"]
        run_nodeids = {"high", "low", "extra_alpha", "extra_z"}
        result = apply_smartqa_order_to_run(smartqa_ordered, run_nodeids)
        # SmartQA overlap first (respecting priority order)
        assert result[0] == "high"
        assert result[1] == "low"
        # Extras alphabetically
        assert result[2] == "extra_alpha"
        assert result[3] == "extra_z"


# ===========================================================================
# 20-23. evaluate_run
# ===========================================================================

class TestEvaluateRun:

    def test_evaluate_run_no_failures(self):
        """[FIXTURE] Run with no failures → all first_failure metrics are None."""
        run_rows = _make_run(
            "run1",
            ["test_A", "test_B", "test_C"],
            ["PASS", "PASS", "PASS"],
        )
        smartqa_ordered = ["test_B", "test_A", "test_C"]
        result = evaluate_run("run1", run_rows, smartqa_ordered)

        assert result["has_failures"] is False
        assert result["total_failures"] == 0
        assert result["baseline"]["first_failure_rank"] is None
        assert result["smartqa"]["first_failure_rank"] is None
        assert result["baseline"]["apfd"] is None
        assert result["smartqa"]["apfd"] is None
        assert result["first_failure_rank_improvement"] is None

    def test_evaluate_run_smartqa_rank_1_failure(self):
        """[FIXTURE] Failure at SmartQA rank 1 → best case for SmartQA."""
        run_rows = _make_run(
            "run2",
            ["test_A", "test_B", "test_FAIL"],
            ["PASS", "PASS", "FAIL"],
        )
        # SmartQA puts test_FAIL first
        smartqa_ordered = ["test_FAIL", "test_A", "test_B"]
        result = evaluate_run("run2", run_rows, smartqa_ordered)

        assert result["has_failures"] is True
        assert result["total_failures"] == 1
        # Baseline: test_FAIL is 3rd in run order
        assert result["baseline"]["first_failure_rank"] == 3
        # SmartQA: test_FAIL is rank 1
        assert result["smartqa"]["first_failure_rank"] == 1
        # Improvement = 3 - 1 = 2
        assert result["first_failure_rank_improvement"] == 2

    def test_evaluate_run_same_rank_both_orderings(self):
        """[FIXTURE] Failure appears at same rank in both orderings."""
        run_rows = _make_run(
            "run3",
            ["test_FAIL", "test_A", "test_B"],
            ["FAIL", "PASS", "PASS"],
        )
        # SmartQA also puts test_FAIL first
        smartqa_ordered = ["test_FAIL", "test_A", "test_B"]
        result = evaluate_run("run3", run_rows, smartqa_ordered)

        assert result["baseline"]["first_failure_rank"] == 1
        assert result["smartqa"]["first_failure_rank"] == 1
        assert result["first_failure_rank_improvement"] == 0

    def test_evaluate_run_fractions_computed_correctly(self):
        """[FIXTURE] Fractions = rank / total_tests."""
        run_rows = _make_run(
            "run4",
            [f"test_{i}" for i in range(1, 11)],
            ["PASS"] * 4 + ["FAIL"] + ["PASS"] * 5,
        )
        # Failure is test_5, at baseline rank 5/10
        smartqa_ordered = [f"test_{i}" for i in range(1, 11)]
        result = evaluate_run("run4", run_rows, smartqa_ordered)

        assert result["total_tests"] == 10
        assert result["baseline"]["first_failure_rank"] == 5
        assert abs(result["baseline"]["first_failure_fraction"] - 0.5) < 1e-6

    def test_evaluate_run_output_schema(self):
        """[FIXTURE] evaluate_run output must contain required keys."""
        run_rows = _make_run("runX", ["test_A"], ["PASS"])
        result = evaluate_run("runX", run_rows, ["test_A"])

        required_keys = {
            "run_id", "commit_sha", "total_tests", "total_failures",
            "has_failures", "baseline", "smartqa", "observation",
        }
        for key in required_keys:
            assert key in result, f"Missing key in evaluate_run output: {key}"

        baseline_keys = {"order_type", "first_failure_rank", "first_failure_fraction", "apfd"}
        for key in baseline_keys:
            assert key in result["baseline"], f"Missing baseline key: {key}"
            assert key in result["smartqa"], f"Missing smartqa key: {key}"


# ===========================================================================
# 24-27. compute_dataset_stats
# ===========================================================================

class TestComputeDatasetStats:

    def test_empty_dataset(self):
        """[FIXTURE] Empty dataset → all zeros."""
        result = compute_dataset_stats([])
        assert result["total_result_rows"] == 0
        assert result["unique_runs"] == 0
        assert result["total_failures"] == 0
        assert result["overall_failure_rate_pct"] == 0.0

    def test_all_pass(self):
        """[FIXTURE] All PASS → failure rate 0."""
        rows = _make_run("r1", ["A", "B", "C"], ["PASS", "PASS", "PASS"])
        result = compute_dataset_stats(rows)
        assert result["total_passes"] == 3
        assert result["total_failures"] == 0
        assert result["overall_failure_rate_pct"] == 0.0

    def test_mix_pass_fail_skip(self):
        """[FIXTURE] Mix of statuses → correct counts."""
        rows = [
            _make_result_row("r1", "A", "PASS"),
            _make_result_row("r1", "B", "FAIL"),
            _make_result_row("r1", "C", "SKIP"),
            _make_result_row("r2", "D", "ERROR"),
        ]
        result = compute_dataset_stats(rows)
        assert result["total_passes"] == 1
        assert result["total_failures"] == 2   # FAIL + ERROR
        assert result["total_skips"] == 1
        assert result["unique_runs"] == 2

    def test_failure_rate_calculation(self):
        """[FIXTURE] Failure rate = failures / (pass + failures) × 100."""
        rows = [
            _make_result_row("r1", "A", "PASS"),
            _make_result_row("r1", "B", "PASS"),
            _make_result_row("r1", "C", "PASS"),
            _make_result_row("r1", "D", "FAIL"),  # 1 of 4 non-skip
        ]
        result = compute_dataset_stats(rows)
        assert result["total_failures"] == 1
        assert result["total_passes"] == 3
        expected_rate = round(1 / 4 * 100, 4)
        assert result["overall_failure_rate_pct"] == expected_rate

    def test_skip_excluded_from_failure_rate(self):
        """[FIXTURE] SKIP rows are NOT counted in failure rate denominator."""
        rows = [
            _make_result_row("r1", "A", "PASS"),
            _make_result_row("r1", "B", "FAIL"),
            _make_result_row("r1", "C", "SKIP"),  # should not affect rate
        ]
        result = compute_dataset_stats(rows)
        # Denominator = 1 PASS + 1 FAIL = 2 (not 3)
        expected_rate = round(1 / 2 * 100, 4)
        assert result["overall_failure_rate_pct"] == expected_rate


# ===========================================================================
# 28-30. group_results_by_run, get_baseline_order, get_failures_in_run
# ===========================================================================

class TestGroupingHelpers:

    def test_group_results_by_run_preserves_order(self):
        """[FIXTURE] Grouping preserves JSONL insertion order within each run."""
        rows = [
            _make_result_row("run1", "test_A", "PASS"),
            _make_result_row("run1", "test_B", "FAIL"),
            _make_result_row("run2", "test_C", "PASS"),
            _make_result_row("run1", "test_C", "PASS"),
        ]
        groups = group_results_by_run(rows)
        assert set(groups.keys()) == {"run1", "run2"}
        nodeids_run1 = [r["test_nodeid"] for r in groups["run1"]]
        assert nodeids_run1 == ["test_A", "test_B", "test_C"]  # insertion order

    def test_get_baseline_order_extracts_nodeids_in_order(self):
        """[FIXTURE] Baseline order = nodeids in JSONL order."""
        rows = _make_run("r1", ["X", "Y", "Z"], ["PASS", "FAIL", "PASS"])
        order = get_baseline_order(rows)
        assert order == ["X", "Y", "Z"]

    def test_get_baseline_order_skips_empty_nodeid(self):
        """[FIXTURE] Rows with empty test_nodeid are excluded."""
        rows = [
            _make_result_row("r1", "", "PASS"),
            _make_result_row("r1", "test_A", "PASS"),
        ]
        order = get_baseline_order(rows)
        assert order == ["test_A"]

    def test_get_failures_in_run_includes_fail_and_error(self):
        """[FIXTURE] FAIL and ERROR both count as failures."""
        rows = [
            _make_result_row("r1", "test_PASS", "PASS"),
            _make_result_row("r1", "test_FAIL", "FAIL"),
            _make_result_row("r1", "test_ERROR", "ERROR"),
            _make_result_row("r1", "test_SKIP", "SKIP"),
        ]
        failures = get_failures_in_run(rows)
        assert "test_FAIL" in failures
        assert "test_ERROR" in failures
        assert "test_PASS" not in failures
        assert "test_SKIP" not in failures

    def test_get_failures_in_run_case_insensitive_status(self):
        """[FIXTURE] Status matching is case-insensitive."""
        rows = [
            _make_result_row("r1", "test_X", "fail"),  # lowercase
            _make_result_row("r1", "test_Y", "PASS"),
        ]
        failures = get_failures_in_run(rows)
        assert "test_X" in failures


# ===========================================================================
# 31-32. File loading with missing files
# ===========================================================================

class TestFileLoding:

    def test_load_test_results_missing_file_returns_empty(self, tmp_path):
        """[FIXTURE] Missing test_results.jsonl → empty list, no exception."""
        result = load_test_results(tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_load_prioritized_order_missing_file_returns_empty(self, tmp_path):
        """[FIXTURE] Missing prioritized_tests.csv → empty list, no exception."""
        result = load_prioritized_order(tmp_path / "nonexistent.csv")
        assert result == []

    def test_load_test_results_empty_file_returns_empty(self, tmp_path):
        """[FIXTURE] Empty test_results.jsonl → empty list."""
        empty_file = tmp_path / "test_results.jsonl"
        empty_file.write_text("", encoding="utf-8")
        result = load_test_results(empty_file)
        assert result == []

    def test_load_test_results_malformed_lines_skipped(self, tmp_path):
        """[FIXTURE] Malformed JSONL lines are skipped; valid lines loaded."""
        jsonl_file = tmp_path / "test_results.jsonl"
        jsonl_file.write_text(
            '{"run_id":"r1","test_nodeid":"test_A","status":"PASS"}\n'
            'THIS IS NOT VALID JSON\n'
            '{"run_id":"r1","test_nodeid":"test_B","status":"FAIL"}\n',
            encoding="utf-8",
        )
        result = load_test_results(jsonl_file)
        assert len(result) == 2  # 2 valid rows, 1 malformed skipped
        nodeids = {r["test_nodeid"] for r in result}
        assert nodeids == {"test_A", "test_B"}

    def test_load_test_results_blank_lines_ignored(self, tmp_path):
        """[FIXTURE] Blank lines in JSONL are silently ignored."""
        jsonl_file = tmp_path / "test_results.jsonl"
        jsonl_file.write_text(
            '\n'
            '{"run_id":"r1","test_nodeid":"test_A","status":"PASS"}\n'
            '\n',
            encoding="utf-8",
        )
        result = load_test_results(jsonl_file)
        assert len(result) == 1


# ===========================================================================
# 33. Evaluation output schema validation
# ===========================================================================

class TestEvaluationOutputSchema:

    def test_evaluate_run_baseline_and_smartqa_keys_present(self):
        """[FIXTURE] evaluate_run output has all required schema fields."""
        run_rows = _make_run("r_schema", ["A", "B"], ["PASS", "PASS"])
        result = evaluate_run("r_schema", run_rows, ["B", "A"])

        # Top-level keys
        for key in ["run_id", "commit_sha", "total_tests", "total_failures",
                    "has_failures", "baseline", "smartqa", "observation"]:
            assert key in result, f"Missing top-level key: {key}"

        # Baseline/smartqa sub-keys
        for key in ["order_type", "first_failure_rank", "first_failure_fraction", "apfd"]:
            assert key in result["baseline"], f"Missing baseline key: {key}"
            assert key in result["smartqa"], f"Missing smartqa key: {key}"

    def test_no_fabricated_values_when_no_failures(self):
        """
        [FIXTURE] When no failures, evaluation must not invent rank values.
        first_failure_rank must be None, not 0 or any other invented value.
        """
        run_rows = _make_run("r_no_fail", ["A", "B", "C"], ["PASS", "PASS", "PASS"])
        result = evaluate_run("r_no_fail", run_rows, ["A", "B", "C"])

        assert result["baseline"]["first_failure_rank"] is None, (
            "Must not fabricate a rank when no failures exist"
        )
        assert result["smartqa"]["first_failure_rank"] is None, (
            "Must not fabricate a rank when no failures exist"
        )
        assert result["baseline"]["apfd"] is None, (
            "APFD must be None, not a fabricated value"
        )


# ===========================================================================
# 34. Determinism
# ===========================================================================

class TestDeterminism:

    def test_same_inputs_produce_same_apfd(self):
        """[FIXTURE] compute_apfd is deterministic for identical inputs."""
        ordered = ["A", "B", "FAIL", "C", "D"]
        failures = {"FAIL"}
        result1 = compute_apfd(ordered, failures)
        result2 = compute_apfd(ordered, failures)
        result3 = compute_apfd(ordered, failures)
        assert result1 == result2 == result3

    def test_same_inputs_produce_same_first_failure_rank(self):
        """[FIXTURE] first_failure_position is deterministic."""
        ordered = ["A", "B", "FAIL"]
        failures = {"FAIL"}
        r1 = first_failure_position(ordered, failures)
        r2 = first_failure_position(ordered, failures)
        assert r1 == r2 == 3

    def test_evaluate_run_deterministic(self):
        """[FIXTURE] evaluate_run produces identical output for identical input."""
        run_rows = _make_run("r_det", ["A", "FAIL", "B"], ["PASS", "FAIL", "PASS"])
        smartqa = ["FAIL", "A", "B"]
        r1 = evaluate_run("r_det", run_rows, smartqa)
        r2 = evaluate_run("r_det", run_rows, smartqa)
        assert r1["baseline"]["first_failure_rank"] == r2["baseline"]["first_failure_rank"]
        assert r1["smartqa"]["first_failure_rank"] == r2["smartqa"]["first_failure_rank"]
        assert r1["baseline"]["apfd"] == r2["baseline"]["apfd"]
        assert r1["smartqa"]["apfd"] == r2["smartqa"]["apfd"]


# ===========================================================================
# 35. APFD edge cases — 2 tests
# ===========================================================================

class TestApfdEdgeCases:

    def test_two_tests_failure_at_1(self):
        """
        [FIXTURE] n=2, failure at rank 1.
        APFD = 1 - 1/(2×1) + 1/(2×2) = 1 - 0.5 + 0.25 = 0.75
        """
        ordered = ["FAIL", "PASS"]
        failures = {"FAIL"}
        result = compute_apfd(ordered, failures)
        expected = round(1.0 - 1 / (2 * 1) + 1 / (2 * 2), 4)
        assert result == expected
        assert abs(result - 0.75) < 1e-6

    def test_two_tests_failure_at_2(self):
        """
        [FIXTURE] n=2, failure at rank 2 (worst case for 2 tests).
        APFD = 1 - 2/(2×1) + 1/(2×2) = 1 - 1.0 + 0.25 = 0.25
        """
        ordered = ["PASS", "FAIL"]
        failures = {"FAIL"}
        result = compute_apfd(ordered, failures)
        expected = round(1.0 - 2 / (2 * 1) + 1 / (2 * 2), 4)
        assert result == expected
        assert abs(result - 0.25) < 1e-6

    def test_apfd_higher_when_failure_earlier(self):
        """[FIXTURE] APFD must be monotonically higher when failure appears earlier."""
        ordered = ["t1", "t2", "t3", "t4", "t5"]
        prev_apfd = 0.0
        for rank in range(5, 0, -1):  # 5, 4, 3, 2, 1
            failures = {f"t{rank}"}
            apfd = compute_apfd(ordered, failures)
            assert apfd is not None
            assert apfd >= prev_apfd, (
                f"APFD should increase as failure moves earlier: "
                f"rank={rank}, apfd={apfd}, prev_apfd={prev_apfd}"
            )
            prev_apfd = apfd


# ===========================================================================
# 36-38. Dashboard data_loader graceful defaults
# ===========================================================================

class TestDashboardDataLoader:
    """
    Tests for dashboard/data_loader.py — graceful handling of missing/malformed data.
    These tests validate the safety contract: no exception ever raised by the loader.
    """

    def test_data_loader_imports_cleanly(self):
        """The data_loader module must import without error."""
        from dashboard import data_loader  # noqa: F401

    def test_load_commits_missing_file_returns_empty(self, tmp_path, monkeypatch):
        """[FIXTURE] load_commits on missing file → empty list."""
        import dashboard.data_loader as dl
        monkeypatch.setattr(dl, "_DATA_DIR", tmp_path)
        result = dl.load_commits()
        assert result == []

    def test_load_test_results_missing_returns_empty(self, tmp_path, monkeypatch):
        """[FIXTURE] load_test_results on missing file → empty list."""
        import dashboard.data_loader as dl
        monkeypatch.setattr(dl, "_DATA_DIR", tmp_path)
        result = dl.load_test_results()
        assert result == []

    def test_load_predictions_missing_returns_empty(self, tmp_path, monkeypatch):
        """[FIXTURE] load_predictions on missing file → empty list."""
        import dashboard.data_loader as dl
        monkeypatch.setattr(dl, "_DATA_DIR", tmp_path)
        result = dl.load_predictions()
        assert result == []

    def test_load_model_metadata_missing_returns_empty_dict(self, tmp_path, monkeypatch):
        """[FIXTURE] load_model_metadata on missing file → empty dict."""
        import dashboard.data_loader as dl
        monkeypatch.setattr(dl, "_MODELS_DIR", tmp_path)
        result = dl.load_model_metadata()
        assert result == {}

    def test_compute_overview_stats_no_data_no_exception(self, tmp_path, monkeypatch):
        """[FIXTURE] compute_overview_stats with all files missing → no exception."""
        import dashboard.data_loader as dl
        monkeypatch.setattr(dl, "_DATA_DIR", tmp_path)
        monkeypatch.setattr(dl, "_MODELS_DIR", tmp_path)
        result = dl.compute_overview_stats()
        assert isinstance(result, dict)
        assert "total_tests" in result
        assert "model_status" in result

    def test_compute_risk_table_no_data_returns_empty(self, tmp_path, monkeypatch):
        """[FIXTURE] compute_risk_table with no prioritized file → empty list."""
        import dashboard.data_loader as dl
        monkeypatch.setattr(dl, "_DATA_DIR", tmp_path)
        result = dl.compute_risk_table()
        assert result == []

    def test_compute_historical_trend_no_data_returns_empty(self, tmp_path, monkeypatch):
        """[FIXTURE] compute_historical_trend with no test results → empty list."""
        import dashboard.data_loader as dl
        monkeypatch.setattr(dl, "_DATA_DIR", tmp_path)
        result = dl.compute_historical_trend()
        assert result == []

    def test_compute_evaluation_display_no_file_available_false(self, tmp_path, monkeypatch):
        """[FIXTURE] compute_evaluation_display with no eval file → available=False."""
        import dashboard.data_loader as dl
        monkeypatch.setattr(dl, "_DATA_DIR", tmp_path)
        monkeypatch.setattr(dl, "_MODELS_DIR", tmp_path)
        result = dl.compute_evaluation_display()
        assert result["available"] is False
        assert "reason" in result

    def test_compute_evaluation_display_does_not_fabricate_values(self, tmp_path, monkeypatch):
        """
        [FIXTURE] When evaluation file exists with no failures,
        dashboard must not invent APFD values.
        """
        import dashboard.data_loader as dl
        # Write a valid evaluation file that has no failures
        eval_data = {
            "evaluation_type": "retrospective",
            "evaluation_note": "test",
            "status": "limited_data",
            "status_note": "no failures",
            "dataset_stats": {"total_failures": 0},
            "summary": {
                "total_runs_evaluated": 5,
                "runs_with_failures": 0,
                "total_failures_observed": 0,
                "apfd": {
                    "status": "unavailable_no_failures",
                    "note": "No failures.",
                    "baseline_mean_apfd": None,
                    "smartqa_mean_apfd": None,
                },
                "first_failure_ranks": {"note": "", "runs": []},
            },
            "runs": [],
        }
        eval_file = tmp_path / "prioritization_evaluation.json"
        eval_file.write_text(json.dumps(eval_data), encoding="utf-8")
        monkeypatch.setattr(dl, "_DATA_DIR", tmp_path)
        monkeypatch.setattr(dl, "_MODELS_DIR", tmp_path)

        result = dl.compute_evaluation_display()
        assert result["available"] is True
        assert result["summary"]["baseline_apfd"] is None
        assert result["summary"]["smartqa_apfd"] is None
        assert result["failure_runs"] == []
