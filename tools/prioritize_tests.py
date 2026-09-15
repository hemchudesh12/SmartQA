"""
tools/prioritize_tests.py — SmartQA Phase 7 Test Prioritization Engine.

USAGE:
    python tools/prioritize_tests.py

WHAT IT DOES:
    1. Loads Phase 6 predictions from data/predictions.csv.
    2. Discovers all executable pytest test node IDs from automation/tests/.
    3. Maps predictions to discovered tests.
    4. Ranks tests by predicted_failure_probability DESC,
       with test_nodeid ASC as a deterministic tie-breaker.
    5. Tests without a prediction are appended after ranked tests,
       ordered alphabetically by test_nodeid (deterministic).
    6. Validates: no test is lost, no duplicates exist.
    7. Writes data/prioritized_tests.csv.
    8. Prints a human-readable summary.

RANKING ALGORITHM:
    Primary key:   predicted_failure_probability DESC (higher risk first)
    Tie-breaker:   test_nodeid ASC (deterministic alphabetical)

MISSING PREDICTION POLICY:
    1. Tests with valid predictions → ranked first by probability DESC.
    2. Tests with invalid/missing predictions → appended after ranked tests.
    3. Missing-prediction tests → sorted alphabetically by test_nodeid.
    4. No test is ever dropped.

INVALID PROBABILITY HANDLING:
    Valid:   0.0 <= probability <= 1.0
    Invalid: NaN, None, empty string, negative, >1, non-numeric
    → Invalid treated as missing (falls into unpredicted bucket).

DETERMINISM:
    Given identical predictions + identical discovered tests,
    the output is always identical. No random.shuffle() or
    random ordering is used anywhere.

LEAKAGE RULE:
    actual_test_failed is NEVER used as a ranking signal.
    Only predicted_failure_probability drives priority.

EXIT CODES:
    0 — Success (prioritization complete and validated)
    1 — Error (file missing, validation failure, etc.)
    2 — Fallback triggered (predictions unavailable, baseline used)
"""

import csv
import subprocess
import sys
import math
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PREDICTIONS_FILE = DATA_DIR / "predictions.csv"
PRIORITIZED_FILE = DATA_DIR / "prioritized_tests.csv"
AUTOMATION_TESTS_DIR = PROJECT_ROOT / "automation" / "tests"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRIORITIZED_CSV_COLUMNS = [
    "priority_rank",
    "test_nodeid",
    "predicted_failure_probability",
    "prediction_available",
    "predicted_label",
    "commit_sha",
]


# ---------------------------------------------------------------------------
# Prediction loading
# ---------------------------------------------------------------------------

def load_predictions(filepath: Path = PREDICTIONS_FILE) -> dict[str, dict]:
    """
    Load predictions.csv into a dict keyed by test_nodeid.

    Returns:
        {test_nodeid: {predicted_failure_probability, predicted_label, commit_sha}}

    Skips rows with invalid/missing test_nodeid.
    Validates probability is a finite float in [0, 1].
    """
    predictions: dict[str, dict] = {}

    if not filepath.exists():
        return predictions

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nodeid = row.get("test_nodeid", "").strip()
            if not nodeid:
                continue

            prob_raw = row.get("predicted_failure_probability", "")
            prob = _parse_probability(prob_raw)

            predictions[nodeid] = {
                "predicted_failure_probability": prob,         # float or None
                "predicted_label": _parse_label(row.get("predicted_label", "")),
                "commit_sha": row.get("commit_sha", ""),
            }

    return predictions


def _parse_probability(raw: str) -> Optional[float]:
    """
    Parse a probability string. Returns float in [0.0, 1.0] or None if invalid.

    Invalid cases: empty string, non-numeric, NaN, Inf, negative, >1.
    """
    if raw is None or str(raw).strip() == "":
        return None
    try:
        val = float(raw)
        if math.isnan(val) or math.isinf(val):
            return None
        if val < 0.0 or val > 1.0:
            return None
        return val
    except (ValueError, TypeError):
        return None


def _parse_label(raw: str) -> Optional[int]:
    """Parse predicted_label string to int, or None if invalid."""
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Test discovery
# ---------------------------------------------------------------------------

def discover_tests(test_dir: Path = AUTOMATION_TESTS_DIR) -> list[str]:
    """
    Discover all executable pytest test node IDs using pytest --collect-only.

    ROOT CAUSE OF ORIGINAL BUG:
        pytest.ini addopts includes:
            -v
            --html=reports/report.html
            --self-contained-html
            -p automation.conftest_collector
        When a subprocess runs `pytest --collect-only`, those addopts are
        inherited. The HTML plugin and collector plugin fail or produce
        side-effects that corrupt stdout, resulting in zero collected node IDs.

    FIX:
        Pass --override-ini=addopts= to the subprocess, which clears addopts
        for the discovery invocation only. The project's testpaths, pythonpath,
        and markers config are still respected. The collector plugin is NOT
        loaded for discovery (correct — we are not running tests here).

    Returns:
        List of node IDs in default pytest discovery order.
        Falls back to empty list if discovery fails — caller handles that.

    Node ID format:
        automation/tests/test_cart.py::test_add_product_to_cart[chromium]
    """
    cmd = [
        sys.executable, "-m", "pytest",
        "--collect-only", "-q", "--no-header",
        "--override-ini=addopts=",   # ← THE FIX: clear addopts so --html
                                      #   and -p automation.conftest_collector
                                      #   are not injected into collection.
        str(test_dir),
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        nodeids = _parse_collected_nodeids(result.stdout)

        # Diagnostic: if nothing found, surface stderr so the caller can
        # understand why (shown via WARNING, not a hard crash).
        if not nodeids and result.stderr.strip():
            for line in result.stderr.strip().splitlines()[:15]:
                print(f"  [discovery-stderr] {line}", file=sys.stderr)

        return nodeids
    except Exception as exc:
        print(f"[WARNING] Test discovery failed: {exc}", file=sys.stderr)
        return []


def _parse_collected_nodeids(stdout: str) -> list[str]:
    """
    Parse `pytest --collect-only -q --no-header` stdout into node ID list.

    With `-q` and no conflicting addopts, output looks like:

        automation/tests/test_auth.py::test_valid_login[chromium]
        automation/tests/test_cart.py::test_add_product_to_cart[chromium]
        ...
        33 tests collected in 0.45s

    Rules:
        - Keep lines that contain "::"
        - Discard empty lines
        - Discard summary lines ("N tests collected", "==" borders)
        - Normalize Windows backslashes to forward slashes
    """
    nodeids = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip pytest border/header lines
        if line.startswith("=") or line.startswith("-"):
            continue
        # Skip summary lines: "33 tests collected in 0.45s"
        # These never contain "::"
        # Valid node IDs always contain "::"
        if "::" not in line:
            continue
        # Normalize Windows path separators
        nodeids.append(line.replace("\\", "/"))
    return nodeids



# ---------------------------------------------------------------------------
# Prioritization core
# ---------------------------------------------------------------------------

def prioritize(
    discovered_tests: list[str],
    predictions: dict[str, dict],
) -> list[dict]:
    """
    Rank discovered_tests by predicted failure probability.

    Algorithm:
        1. Tests with a valid probability → sorted by probability DESC,
           then test_nodeid ASC (tie-breaker).
        2. Tests without a valid prediction → sorted by test_nodeid ASC.
        3. Categories are concatenated: [predicted ranked] + [unpredicted ranked].
        4. priority_rank is assigned 1..N.

    Args:
        discovered_tests: list of pytest node IDs
        predictions: dict from load_predictions()

    Returns:
        list of dicts with PRIORITIZED_CSV_COLUMNS fields.

    LEAKAGE GUARANTEE:
        actual_test_failed is NOT present in the predictions dict
        consumed by this function. It is never used as a ranking signal.
    """
    with_pred = []
    without_pred = []

    for nodeid in discovered_tests:
        pred = predictions.get(nodeid)
        prob = pred["predicted_failure_probability"] if pred else None

        if prob is not None:
            with_pred.append({
                "test_nodeid": nodeid,
                "predicted_failure_probability": prob,
                "prediction_available": True,
                "predicted_label": pred.get("predicted_label"),
                "commit_sha": pred.get("commit_sha", ""),
            })
        else:
            without_pred.append({
                "test_nodeid": nodeid,
                "predicted_failure_probability": None,
                "prediction_available": False,
                "predicted_label": None,
                "commit_sha": (pred.get("commit_sha", "") if pred else ""),
            })

    # Sort by probability DESC, then nodeid ASC (deterministic tie-breaker)
    with_pred.sort(key=lambda r: (-r["predicted_failure_probability"], r["test_nodeid"]))

    # Sort unpredicted by nodeid ASC (deterministic)
    without_pred.sort(key=lambda r: r["test_nodeid"])

    ranked = with_pred + without_pred

    # Assign sequential ranks starting at 1
    for rank, entry in enumerate(ranked, start=1):
        entry["priority_rank"] = rank

    return ranked


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_prioritization(
    discovered: list[str],
    ranked: list[dict],
) -> list[str]:
    """
    Validate the prioritized list against discovered tests.

    Checks:
        - No test is lost
        - No duplicate test_nodeid
        - Ranks are consecutive integers starting at 1
        - All discovered tests appear in ranked output

    Returns list of error strings. Empty list = valid.
    """
    errors = []

    ranked_nodeids = [r["test_nodeid"] for r in ranked]
    discovered_set = set(discovered)
    ranked_set = set(ranked_nodeids)

    # No test loss
    missing = discovered_set - ranked_set
    if missing:
        errors.append(
            f"TEST LOSS DETECTED: {len(missing)} discovered test(s) not in "
            f"prioritized output: {sorted(missing)}"
        )

    # No extra tests
    extra = ranked_set - discovered_set
    if extra:
        errors.append(
            f"EXTRA TESTS DETECTED: {len(extra)} prioritized test(s) not in "
            f"discovered list: {sorted(extra)}"
        )

    # No duplicates
    seen = set()
    for nodeid in ranked_nodeids:
        if nodeid in seen:
            errors.append(f"DUPLICATE DETECTED: {nodeid}")
        seen.add(nodeid)

    # Count consistency
    if len(ranked) != len(discovered):
        errors.append(
            f"COUNT MISMATCH: discovered={len(discovered)}, "
            f"prioritized={len(ranked)}"
        )

    # Consecutive ranks
    expected_ranks = list(range(1, len(ranked) + 1))
    actual_ranks = [r["priority_rank"] for r in ranked]
    if actual_ranks != expected_ranks:
        errors.append(
            f"RANK SEQUENCE INVALID: expected {expected_ranks[:5]}..., "
            f"got {actual_ranks[:5]}..."
        )

    return errors


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------

def save_prioritized(ranked: list[dict], filepath: Path = PRIORITIZED_FILE) -> None:
    """Write ranked tests to prioritized_tests.csv."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PRIORITIZED_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in ranked:
            out = {
                "priority_rank": row["priority_rank"],
                "test_nodeid": row["test_nodeid"],
                "predicted_failure_probability": (
                    f"{row['predicted_failure_probability']:.6f}"
                    if row["predicted_failure_probability"] is not None
                    else "N/A"
                ),
                "prediction_available": str(row["prediction_available"]),
                "predicted_label": (
                    str(row["predicted_label"])
                    if row["predicted_label"] is not None
                    else "N/A"
                ),
                "commit_sha": row.get("commit_sha", ""),
            }
            writer.writerow(out)
    print(f"[OK] Priority list written to {filepath}")


def build_pytest_node_file(ranked: list[dict], filepath: Path) -> None:
    """
    Write a plain-text file with one pytest node ID per line,
    in priority order. Used for CI execution via `pytest $(cat file)`.
    """
    with open(filepath, "w", encoding="utf-8") as f:
        for row in ranked:
            f.write(row["test_nodeid"] + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 50)
    print("SmartQA Phase 7 — Test Prioritization")
    print("=" * 50)
    print()

    # 1. Load predictions
    print("Step 1: Loading Phase 6 predictions...")
    predictions = load_predictions()

    if not predictions:
        print(f"[WARNING] No predictions found at {PREDICTIONS_FILE}")
        print("[INFO] Predictions are absent. This is expected if Phase 6")
        print("       training was skipped due to insufficient class diversity.")
        print()
        print("[INFO] Continuing with baseline (unpredicted) ordering.")
        print("       All tests will be placed in alphabetical order.")
    else:
        print(f"  Loaded {len(predictions)} prediction(s).")

    # 2. Discover tests
    print("\nStep 2: Discovering executable tests...")
    discovered = discover_tests()

    if not discovered:
        print("[ERROR] No tests discovered. Cannot prioritize.")
        print(f"        Check that {AUTOMATION_TESTS_DIR} contains pytest tests.")
        print("        Ensure Flask server is not required for collection.")
        return 1

    print(f"  Discovered {len(discovered)} test(s).")

    # 3. Match and rank
    print("\nStep 3: Ranking tests by failure probability...")
    with_pred_count = sum(
        1 for t in discovered
        if t in predictions and predictions[t]["predicted_failure_probability"] is not None
    )
    without_pred_count = len(discovered) - with_pred_count
    print(f"  Tests with predictions:    {with_pred_count}")
    print(f"  Tests without predictions: {without_pred_count}")

    ranked = prioritize(discovered, predictions)

    # 4. Validate
    print("\nStep 4: Validating prioritization...")
    errors = validate_prioritization(discovered, ranked)
    if errors:
        print("[FAIL] Validation errors detected:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("  [OK] No tests lost")
    print("  [OK] No duplicates")
    print("  [OK] Ranks are consecutive")
    print("  [OK] Deterministic ordering")

    # 5. Save outputs
    print("\nStep 5: Writing outputs...")
    save_prioritized(ranked)

    # Also write node-id-per-line file for CI use
    nodeid_file = DATA_DIR / "prioritized_nodeids.txt"
    build_pytest_node_file(ranked, nodeid_file)
    print(f"[OK] Node IDs written to {nodeid_file}")

    # 6. Print human-readable summary
    print()
    print("=" * 50)
    print("Prioritization Summary")
    print("=" * 50)
    print(f"\nDiscovered tests:      {len(discovered)}")
    print(f"Predictions available: {with_pred_count}")
    print(f"Predictions missing:   {without_pred_count}")

    # Show top-ranked tests (up to 10)
    top_n = min(10, len(ranked))
    print(f"\nTop {top_n} highest-risk tests:")
    print()
    for entry in ranked[:top_n]:
        prob = entry["predicted_failure_probability"]
        prob_str = f"{prob:.6f}" if prob is not None else "N/A (no prediction)"
        print(f"  {entry['priority_rank']:>3}. {entry['test_nodeid']}")
        print(f"       Failure probability: {prob_str}")

    if len(ranked) > top_n:
        print(f"\n  ... {len(ranked) - top_n} more test(s) in prioritized_tests.csv")

    print()
    print(f"Priority list written to: {PRIORITIZED_FILE}")
    print()
    print("STATUS: PRIORITIZATION COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
