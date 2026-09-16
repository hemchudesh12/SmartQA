"""
tools/evaluate_prioritization.py — SmartQA Phase 8 Prioritization Evaluation.

USAGE:
    python tools/evaluate_prioritization.py

WHAT IT DOES:
    1. Loads data/test_results.jsonl (all historical test execution records).
    2. Loads data/prioritized_tests.csv (current SmartQA priority order).
    3. Groups results by run_id.
    4. Identifies runs containing genuine failures (FAIL or ERROR).
    5. For each failure run:
        a. Determines baseline order — the recorded test sequence in that run.
        b. Applies SmartQA order to that run's test set.
        c. Computes first-failure rank and fraction for each ordering.
        d. Computes APFD for each ordering.
    6. Computes dataset-level summary statistics.
    7. Saves structured output to data/prioritization_evaluation.json.

EVALUATION TYPE:
    RETROSPECTIVE.
    The current SmartQA prioritized order (generated for the latest commit)
    is applied retrospectively to historical runs where failures occurred.

    This answers: "If we had used the SmartQA ordering in historical failure
    runs, at what position would the first failure have appeared?"

    This is NOT a prospective evaluation on unseen data.

    The model's training set INCLUDES the failure commit, so the evaluation
    is informative about prioritization behavior but is not a fully
    independent out-of-sample measurement.

APFD FORMULA:
    APFD = 1 - (ΣTFi) / (n × m) + 1 / (2n)
    where:
        TFi = 1-based position of the i-th failing test in the ordering
        n   = total tests in the ordering
        m   = total number of failing tests

    APFD = 1.0 means all failures appear first.
    APFD = 0.0 means all failures appear last.

    Only computed when m >= 1 and n >= 1.

MISSING PREDICTIONS POLICY:
    If a test appears in a run but not in the SmartQA prioritized order,
    it is appended at the end of the SmartQA ordering (alphabetically).
    No test is ever dropped from analysis.

HONEST LIMITATIONS:
    - With only 1 genuine failure in the entire dataset, APFD is computed
      from a single data point and has high variance.
    - Evaluation is retrospective, not prospective.
    - More failures are needed for statistically meaningful results.

EXIT CODES:
    0 — Success (or graceful handling of empty/missing data)
    1 — Hard error (file parse failure, unexpected exception)
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_FILE = DATA_DIR / "test_results.jsonl"
PRIORITIZED_FILE = DATA_DIR / "prioritized_tests.csv"
EVAL_OUTPUT_FILE = DATA_DIR / "prioritization_evaluation.json"

# Risk threshold definitions (used in evaluation report)
HIGH_RISK_THRESHOLD = 0.5   # P >= 0.50 → High
MEDIUM_RISK_THRESHOLD = 0.2  # P >= 0.20 → Medium, else Low


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_test_results(filepath: Path = RESULTS_FILE) -> list[dict]:
    """
    Load all test results from test_results.jsonl.

    Returns:
        List of result dicts, in file order. Malformed lines are skipped.
        Returns [] if file is missing or empty.
    """
    if not filepath.exists():
        return []
    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(
                    f"[WARNING] Skipping malformed line {line_num} in {filepath.name}: {exc}",
                    file=sys.stderr,
                )
    return rows


def load_prioritized_order(filepath: Path = PRIORITIZED_FILE) -> list[dict]:
    """
    Load prioritized_tests.csv and return rows sorted by priority_rank.

    Returns:
        List of dicts from CSV, sorted by priority_rank ascending.
        Returns [] if file is missing or empty.
    """
    if not filepath.exists():
        return []
    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    # Sort by priority_rank to guarantee correct ordering
    try:
        rows.sort(key=lambda r: int(r.get("priority_rank", 9999)))
    except (ValueError, TypeError):
        pass
    return rows


# ---------------------------------------------------------------------------
# Grouping and ordering helpers
# ---------------------------------------------------------------------------

def group_results_by_run(results: list[dict]) -> dict[str, list[dict]]:
    """
    Group test result rows by run_id, preserving JSONL file order.

    Returns:
        {run_id: [rows in JSONL order]} — file order is execution order.
    """
    runs: dict[str, list[dict]] = defaultdict(list)
    for row in results:
        run_id = row.get("run_id", "unknown")
        runs[run_id].append(row)
    return dict(runs)


def get_baseline_order(run_rows: list[dict]) -> list[str]:
    """
    Return test node IDs in baseline execution order for a run.

    The baseline order is the sequence tests appear in test_results.jsonl
    for this run_id. This reflects the default pytest discovery order.

    Args:
        run_rows: test result rows for a single run_id, in JSONL order.

    Returns:
        List of non-empty test_nodeids in execution order.
    """
    return [
        r.get("test_nodeid", "")
        for r in run_rows
        if r.get("test_nodeid", "").strip()
    ]


def get_failures_in_run(run_rows: list[dict]) -> list[str]:
    """
    Return test_nodeids of tests that FAIL or ERROR in this run.

    SKIP tests are excluded — consistent with Phase 5/6 target definition.
    """
    return [
        r.get("test_nodeid", "")
        for r in run_rows
        if r.get("status", "").upper() in {"FAIL", "ERROR"}
        and r.get("test_nodeid", "").strip()
    ]


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def first_failure_position(
    ordered_tests: list[str],
    failures: set[str],
) -> Optional[int]:
    """
    Return the 1-based rank of the first failure in ordered_tests.

    Args:
        ordered_tests: test node IDs in execution order.
        failures: set of failing test node IDs.

    Returns:
        1-based integer rank, or None if no failure is found in ordered_tests.
    """
    for i, nodeid in enumerate(ordered_tests, start=1):
        if nodeid in failures:
            return i
    return None


def compute_apfd(
    ordered_tests: list[str],
    failures: set[str],
) -> Optional[float]:
    """
    Compute APFD (Average Percentage of Faults Detected).

    Formula:
        APFD = 1 - (ΣTFi) / (n × m) + 1 / (2n)

    where TFi is the 1-based position of the i-th failing test.

    Args:
        ordered_tests: test node IDs in execution order.
        failures: set of failing test node IDs.

    Returns:
        APFD value in [0.0, 1.0], rounded to 4 decimal places.
        Returns None if ordered_tests is empty or no failures found.

    Mathematical notes:
        - APFD = 1.0 is achieved when all failures appear first.
        - APFD approaches 0.0 when all failures appear last.
        - The + 1/(2n) term corrects for discrete ordering.
    """
    n = len(ordered_tests)
    if n == 0:
        return None

    failure_positions = [
        i for i, nodeid in enumerate(ordered_tests, start=1)
        if nodeid in failures
    ]

    m = len(failure_positions)
    if m == 0:
        return None

    sum_tf = sum(failure_positions)
    apfd = 1.0 - (sum_tf / (n * m)) + (1.0 / (2 * n))
    return round(apfd, 4)


def apply_smartqa_order_to_run(
    smartqa_ordered: list[str],
    run_test_nodeids: set[str],
) -> list[str]:
    """
    Produce the SmartQA-ordered test sequence restricted to a specific run's tests.

    Policy:
        1. Tests in SmartQA order that are present in the run → first, in priority order.
        2. Tests in the run but absent from SmartQA ordering → appended alphabetically.

    No test in run_test_nodeids is ever dropped.

    Args:
        smartqa_ordered: test_nodeids in SmartQA priority order (highest risk first).
        run_test_nodeids: set of test_nodeids that actually ran.

    Returns:
        Ordered list of test_nodeids for this run under SmartQA ordering.
    """
    in_smartqa = [n for n in smartqa_ordered if n in run_test_nodeids]
    in_run_not_in_smartqa = sorted(run_test_nodeids - set(smartqa_ordered))
    return in_smartqa + in_run_not_in_smartqa


# ---------------------------------------------------------------------------
# Run-level evaluation
# ---------------------------------------------------------------------------

def evaluate_run(
    run_id: str,
    run_rows: list[dict],
    smartqa_ordered: list[str],
) -> dict:
    """
    Evaluate a single run comparing baseline vs SmartQA prioritization.

    Args:
        run_id: identifier for this run.
        run_rows: all test result rows for this run_id, in JSONL order.
        smartqa_ordered: test_nodeids in SmartQA priority order.

    Returns:
        Dict with metrics for this run.
    """
    baseline_order = get_baseline_order(run_rows)
    failures = set(get_failures_in_run(run_rows))
    run_nodeids = set(baseline_order)

    commit_sha = run_rows[0].get("commit_sha", "") if run_rows else ""
    total_tests = len(baseline_order)
    total_failures = len(failures)

    # ------------------------------------------------------------------
    # Baseline metrics
    # ------------------------------------------------------------------
    baseline_first_rank = first_failure_position(baseline_order, failures)
    baseline_first_fraction = (
        round(baseline_first_rank / total_tests, 4)
        if baseline_first_rank is not None and total_tests > 0
        else None
    )
    baseline_apfd = compute_apfd(baseline_order, failures) if total_failures > 0 else None

    # ------------------------------------------------------------------
    # SmartQA metrics
    # ------------------------------------------------------------------
    smartqa_run_order = apply_smartqa_order_to_run(smartqa_ordered, run_nodeids)
    smartqa_first_rank = first_failure_position(smartqa_run_order, failures)
    smartqa_first_fraction = (
        round(smartqa_first_rank / total_tests, 4)
        if smartqa_first_rank is not None and total_tests > 0
        else None
    )
    smartqa_apfd = compute_apfd(smartqa_run_order, failures) if total_failures > 0 else None

    # ------------------------------------------------------------------
    # Build result dict
    # ------------------------------------------------------------------
    result = {
        "run_id": run_id,
        "commit_sha": commit_sha,
        "total_tests": total_tests,
        "total_failures": total_failures,
        "has_failures": total_failures > 0,
        "baseline": {
            "order_type": "pytest_discovery_order",
            "description": "Default pytest test collection order",
            "first_failure_rank": baseline_first_rank,
            "first_failure_fraction": baseline_first_fraction,
            "apfd": baseline_apfd,
        },
        "smartqa": {
            "order_type": "predicted_failure_probability_desc",
            "description": "SmartQA ML-predicted risk order (highest probability first)",
            "first_failure_rank": smartqa_first_rank,
            "first_failure_fraction": smartqa_first_fraction,
            "apfd": smartqa_apfd,
        },
    }

    # Observation note
    if total_failures == 0:
        result["observation"] = "No failures in this run — no improvement measurable."
        result["first_failure_rank_improvement"] = None
    elif baseline_first_rank is not None and smartqa_first_rank is not None:
        improvement = baseline_first_rank - smartqa_first_rank
        result["first_failure_rank_improvement"] = improvement
        if improvement > 0:
            result["observation"] = (
                f"SmartQA detected first failure at rank {smartqa_first_rank} "
                f"vs baseline rank {baseline_first_rank}. "
                f"SmartQA executed {improvement} fewer tests before detecting failure."
            )
        elif improvement == 0:
            result["observation"] = (
                f"SmartQA and baseline both detected first failure at rank {baseline_first_rank}."
            )
        else:
            result["observation"] = (
                f"SmartQA detected first failure at rank {smartqa_first_rank} "
                f"vs baseline rank {baseline_first_rank}. "
                f"Baseline was {abs(improvement)} positions earlier for this run."
            )
    else:
        result["first_failure_rank_improvement"] = None
        result["observation"] = (
            "Failing test not found in ordering — check test_nodeid alignment."
        )

    return result


# ---------------------------------------------------------------------------
# Dataset-level statistics
# ---------------------------------------------------------------------------

def compute_dataset_stats(results: list[dict]) -> dict:
    """Compute overall statistics from all test result rows."""
    if not results:
        return {
            "total_result_rows": 0,
            "unique_runs": 0,
            "unique_commits": 0,
            "total_passes": 0,
            "total_failures": 0,
            "total_skips": 0,
            "overall_failure_rate_pct": 0.0,
        }

    run_ids = set(r.get("run_id", "") for r in results if r.get("run_id"))
    commit_shas = set(r.get("commit_sha", "") for r in results if r.get("commit_sha"))
    total_passes = sum(1 for r in results if r.get("status", "").upper() == "PASS")
    total_failures = sum(
        1 for r in results if r.get("status", "").upper() in {"FAIL", "ERROR"}
    )
    total_skips = sum(1 for r in results if r.get("status", "").upper() == "SKIP")

    denominator = total_passes + total_failures
    failure_rate = round(total_failures / denominator * 100, 4) if denominator > 0 else 0.0

    return {
        "total_result_rows": len(results),
        "unique_runs": len(run_ids),
        "unique_commits": len(commit_shas),
        "total_passes": total_passes,
        "total_failures": total_failures,
        "total_skips": total_skips,
        "overall_failure_rate_pct": failure_rate,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("SmartQA Phase 8 — Prioritization Evaluation")
    print("=" * 60)
    print()
    print("Evaluation type: RETROSPECTIVE")
    print("The SmartQA prioritized order is applied retrospectively to")
    print("historical runs that contained genuine test failures.")
    print()

    # ------------------------------------------------------------------
    # Step 1: Load test results
    # ------------------------------------------------------------------
    print("Step 1: Loading test results...")
    results = load_test_results()

    if not results:
        print(f"[WARNING] No test results at {RESULTS_FILE}")
        print("         Cannot evaluate without execution history.")
        output = {
            "evaluation_type": "retrospective",
            "status": "unavailable",
            "reason": "No test results found in data/test_results.jsonl",
            "dataset_stats": {},
            "summary": {},
            "runs": [],
        }
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(EVAL_OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"[OK] Wrote empty evaluation to {EVAL_OUTPUT_FILE}")
        return 0

    print(f"  Loaded {len(results)} test result rows.")

    # ------------------------------------------------------------------
    # Step 2: Load SmartQA order
    # ------------------------------------------------------------------
    print("\nStep 2: Loading SmartQA prioritized order...")
    prioritized_rows = load_prioritized_order()

    if not prioritized_rows:
        print(f"[WARNING] Prioritized order not found at {PRIORITIZED_FILE}")
        print("         Run: python tools/prioritize_tests.py")
        smartqa_ordered: list[str] = []
        smartqa_available = False
    else:
        smartqa_ordered = [
            r.get("test_nodeid", "")
            for r in prioritized_rows
            if r.get("test_nodeid", "").strip()
        ]
        smartqa_available = True
        print(f"  Loaded {len(smartqa_ordered)} tests in SmartQA priority order.")

    # ------------------------------------------------------------------
    # Step 3: Dataset statistics
    # ------------------------------------------------------------------
    print("\nStep 3: Computing dataset statistics...")
    dataset_stats = compute_dataset_stats(results)
    print(f"  Total result rows:   {dataset_stats['total_result_rows']}")
    print(f"  Unique runs:         {dataset_stats['unique_runs']}")
    print(f"  Unique commits:      {dataset_stats['unique_commits']}")
    print(f"  Total PASS:          {dataset_stats['total_passes']}")
    print(f"  Total FAIL/ERROR:    {dataset_stats['total_failures']}")
    print(f"  Total SKIP:          {dataset_stats['total_skips']}")
    print(f"  Failure rate:        {dataset_stats['overall_failure_rate_pct']:.4f}%")

    # ------------------------------------------------------------------
    # Step 4: Group by run
    # ------------------------------------------------------------------
    print("\nStep 4: Grouping by run...")
    runs = group_results_by_run(results)
    print(f"  Found {len(runs)} distinct run(s).")

    # ------------------------------------------------------------------
    # Step 5: Evaluate each run
    # ------------------------------------------------------------------
    print("\nStep 5: Evaluating runs...")
    run_evaluations: list[dict] = []
    runs_with_failures = 0

    for run_id, run_rows in runs.items():
        failure_nodeids = get_failures_in_run(run_rows)
        has_failures = len(failure_nodeids) > 0

        if has_failures:
            runs_with_failures += 1
            print(f"\n  [FAILURE RUN] run_id={run_id}")
            for fn in failure_nodeids:
                print(f"    FAIL: {fn}")

        if smartqa_available:
            eval_result = evaluate_run(run_id, run_rows, smartqa_ordered)
        else:
            baseline_order = get_baseline_order(run_rows)
            failures_set = set(failure_nodeids)
            baseline_rank = first_failure_position(baseline_order, failures_set)
            n = len(baseline_order)
            eval_result = {
                "run_id": run_id,
                "commit_sha": run_rows[0].get("commit_sha", "") if run_rows else "",
                "total_tests": n,
                "total_failures": len(failure_nodeids),
                "has_failures": has_failures,
                "baseline": {
                    "order_type": "pytest_discovery_order",
                    "first_failure_rank": baseline_rank,
                    "first_failure_fraction": (
                        round(baseline_rank / n, 4) if baseline_rank and n > 0 else None
                    ),
                    "apfd": compute_apfd(baseline_order, failures_set) if has_failures else None,
                },
                "smartqa": {
                    "order_type": "unavailable",
                    "first_failure_rank": None,
                    "first_failure_fraction": None,
                    "apfd": None,
                },
                "first_failure_rank_improvement": None,
                "observation": "SmartQA prioritized order not available for comparison.",
            }

        run_evaluations.append(eval_result)

        if has_failures:
            b_rank = eval_result["baseline"]["first_failure_rank"]
            s_rank = eval_result["smartqa"]["first_failure_rank"]
            total = eval_result["total_tests"]
            print(f"    Baseline first failure rank:  {b_rank}/{total}")
            if smartqa_available and s_rank is not None:
                print(f"    SmartQA first failure rank:   {s_rank}/{total}")
                print(f"    Observation: {eval_result.get('observation', '')}")

    # ------------------------------------------------------------------
    # Step 6: Build summary
    # ------------------------------------------------------------------
    print("\nStep 6: Building evaluation summary...")

    failure_runs = [e for e in run_evaluations if e["has_failures"]]

    # Aggregate APFD
    baseline_apdfs = [
        e["baseline"]["apfd"]
        for e in failure_runs
        if e["baseline"]["apfd"] is not None
    ]
    smartqa_apdfs = [
        e["smartqa"]["apfd"]
        for e in failure_runs
        if e["smartqa"]["apfd"] is not None
    ]

    baseline_apfd_mean = (
        round(sum(baseline_apdfs) / len(baseline_apdfs), 4)
        if baseline_apdfs else None
    )
    smartqa_apfd_mean = (
        round(sum(smartqa_apdfs) / len(smartqa_apdfs), 4)
        if smartqa_apdfs else None
    )

    if runs_with_failures == 0:
        apfd_status = "unavailable_no_failures"
        apfd_note = (
            "No genuine failures observed in any historical run. "
            "APFD cannot be computed without at least one failing test."
        )
    elif not smartqa_available:
        apfd_status = "unavailable_no_prioritization"
        apfd_note = "SmartQA prioritized order not available. Cannot compute SmartQA APFD."
    elif not baseline_apdfs:
        apfd_status = "unavailable_computation_error"
        apfd_note = "APFD computation did not produce results. Check data alignment."
    else:
        apfd_status = "computed_retrospective"
        apfd_note = (
            "APFD computed retrospectively. The SmartQA order (for the latest commit) "
            "was applied to historical failure runs. "
            "The model training set includes the failure commit, so this is not "
            "a fully independent holdout evaluation. "
            f"Failure count in dataset: {dataset_stats['total_failures']}. "
            "Interpret with caution given small sample size."
        )

    summary = {
        "total_runs_evaluated": len(run_evaluations),
        "runs_with_failures": runs_with_failures,
        "runs_without_failures": len(run_evaluations) - runs_with_failures,
        "total_failures_observed": dataset_stats["total_failures"],
        "smartqa_order_available": smartqa_available,
        "apfd": {
            "status": apfd_status,
            "note": apfd_note,
            "baseline_mean_apfd": baseline_apfd_mean,
            "smartqa_mean_apfd": smartqa_apfd_mean,
        },
        "first_failure_ranks": {
            "note": (
                "First failure rank in each ordering for runs that had at least one failure. "
                "Lower rank = failure detected earlier = better prioritization."
            ),
            "runs": [
                {
                    "run_id": e["run_id"],
                    "commit_sha": e["commit_sha"],
                    "total_tests": e["total_tests"],
                    "total_failures": e["total_failures"],
                    "baseline_first_failure_rank": e["baseline"]["first_failure_rank"],
                    "baseline_first_failure_fraction": e["baseline"]["first_failure_fraction"],
                    "smartqa_first_failure_rank": e["smartqa"]["first_failure_rank"],
                    "smartqa_first_failure_fraction": e["smartqa"]["first_failure_fraction"],
                    "first_failure_rank_improvement": e.get("first_failure_rank_improvement"),
                    "observation": e.get("observation", ""),
                }
                for e in failure_runs
            ],
        },
    }

    # ------------------------------------------------------------------
    # Step 7: Assemble and save output
    # ------------------------------------------------------------------
    output = {
        "evaluation_type": "retrospective",
        "evaluation_note": (
            "This evaluation applies the current SmartQA prioritized order "
            "retrospectively to historical runs that contained test failures. "
            "It answers: 'If we had used this ordering in those failure runs, "
            "would we have found failures sooner?' "
            "This is NOT a prospective evaluation on unseen future data."
        ),
        "risk_thresholds": {
            "high": f">= {HIGH_RISK_THRESHOLD}",
            "medium": f">= {MEDIUM_RISK_THRESHOLD}",
            "low": f"< {MEDIUM_RISK_THRESHOLD}",
            "note": "Thresholds applied to predicted_failure_probability",
        },
        "status": (
            "limited_data" if runs_with_failures < 2 else "computed"
        ),
        "status_note": (
            "limited_data: fewer than 2 failure runs found. "
            "Metrics are computed on available data but have limited statistical power."
            if runs_with_failures < 2
            else "Computed from historical failure runs."
        ),
        "dataset_stats": dataset_stats,
        "summary": summary,
        "runs": run_evaluations,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(EVAL_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"[OK] Evaluation saved to {EVAL_OUTPUT_FILE}")

    # ------------------------------------------------------------------
    # Step 8: Print summary report
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("Prioritization Evaluation Summary")
    print("=" * 60)
    print(f"  Total runs:              {len(run_evaluations)}")
    print(f"  Runs with failures:      {runs_with_failures}")
    print(f"  Total failures observed: {dataset_stats['total_failures']}")
    print()

    print(f"  APFD Status:             {apfd_status}")
    print(f"  Baseline mean APFD:      "
          f"{baseline_apfd_mean if baseline_apfd_mean is not None else 'N/A'}")
    print(f"  SmartQA mean APFD:       "
          f"{smartqa_apfd_mean if smartqa_apfd_mean is not None else 'N/A'}")
    print()

    if runs_with_failures == 0:
        print("  [NOTE] No genuine failures found in historical data.")
        print("         First-failure and APFD metrics are unavailable.")
        print("         This is an honest result with the current dataset.")
        print("         The pipeline is complete and ready for future failures.")
    else:
        print("  First-failure rank comparison (failure runs only):")
        for r in summary["first_failure_ranks"]["runs"]:
            n = r["total_tests"]
            b_rank = r["baseline_first_failure_rank"]
            s_rank = r["smartqa_first_failure_rank"]
            b_frac = r["baseline_first_failure_fraction"]
            s_frac = r["smartqa_first_failure_fraction"]

            print(f"\n  Run: {r['run_id']}")
            print(f"    Commit:          {r['commit_sha'][:12]}")
            print(f"    Failures:        {r['total_failures']}/{n}")
            print(
                f"    Baseline:        first failure at rank {b_rank}/{n} "
                f"({b_frac if b_frac is not None else 'N/A'})"
            )
            if s_rank is not None:
                print(
                    f"    SmartQA:         first failure at rank {s_rank}/{n} "
                    f"({s_frac if s_frac is not None else 'N/A'})"
                )
            else:
                print("    SmartQA:         N/A (order unavailable)")
            print(f"    Note:            {r.get('observation', '')}")

    print()
    print("STATUS: EVALUATION COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
