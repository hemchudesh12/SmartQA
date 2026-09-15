"""
tools/validate_dataset.py — Dataset Validation Script for SmartQA Phase 4.

USAGE:
    python tools/validate_dataset.py

WHAT IT VALIDATES:
    1.  Schema validity      — Required fields present in each JSONL record
    2.  Status validity      — Only PASS/FAIL/SKIP/ERROR values exist
    3.  Duration validity    — No negative durations
    4.  Duplicate detection  — (commit_sha, test_nodeid, run_id) triplet uniqueness
    5.  Missing values       — Unexpected blank commit_sha or test_nodeid
    6.  Referential check    — Every test result references a recorded commit_sha
    7.  Dataset count        — Records count vs expected 33 tests
    8.  Commit validity      — commit_sha is plausibly a git SHA (40 hex chars) or "UNKNOWN"
    9.  Data source check    — data_source is "real" or "controlled_failure"
    10. CSV consistency      — dataset.csv row count matches test_results.jsonl

EXIT CODES:
    0 → Dataset is VALID
    1 → Validation FAILED (see report for details)
"""

import csv
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
COMMITS_FILE = DATA_DIR / "commits.jsonl"
RESULTS_FILE = DATA_DIR / "test_results.jsonl"
DATASET_FILE = DATA_DIR / "dataset.csv"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = {"PASS", "FAIL", "SKIP", "ERROR"}
VALID_DATA_SOURCES = {"real", "controlled_failure"}
EXPECTED_TESTS_PER_RUN = 33  # Phase 2 baseline

# Required fields in each record
REQUIRED_COMMIT_FIELDS = {
    "commit_sha", "parent_sha", "commit_message", "author",
    "timestamp_iso", "branch", "changed_files", "changed_file_count",
    "lines_added", "lines_deleted", "run_id", "data_source",
}
REQUIRED_RESULT_FIELDS = {
    "commit_sha", "run_id", "test_nodeid", "test_file",
    "test_name", "markers", "status", "duration_sec",
    "run_timestamp_iso", "data_source",
}

SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_jsonl(filepath: Path) -> tuple[list[dict], list[str]]:
    """
    Load a JSONL file. Returns (records, errors).
    errors is a list of human-readable parse/schema problem descriptions.
    """
    records: list[dict] = []
    errors: list[str] = []

    if not filepath.exists():
        errors.append(f"File not found: {filepath}")
        return records, errors

    with open(filepath, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                errors.append(f"  Line {lineno}: JSON parse error — {exc}")

    return records, errors


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def check_commits(commits: list[dict]) -> list[str]:
    """Run all commit-level validation checks. Returns list of error strings."""
    errors: list[str] = []

    for i, record in enumerate(commits):
        # 1. Required fields
        missing = REQUIRED_COMMIT_FIELDS - set(record.keys())
        if missing:
            errors.append(f"  Commit record {i+1}: missing fields {sorted(missing)}")

        # 2. Commit SHA plausibility
        sha = record.get("commit_sha", "")
        if sha and sha != "UNKNOWN" and not SHA_PATTERN.match(sha):
            errors.append(f"  Commit record {i+1}: suspicious commit_sha '{sha[:20]}...'")

        # 3. Data source
        src = record.get("data_source", "")
        if src not in VALID_DATA_SOURCES:
            errors.append(
                f"  Commit record {i+1}: invalid data_source '{src}'. "
                f"Must be one of {VALID_DATA_SOURCES}"
            )

    return errors


def check_results(results: list[dict], known_shas: set[str]) -> list[str]:
    """Run all test-result-level validation checks."""
    errors: list[str] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for i, record in enumerate(results):
        # 1. Required fields
        missing = REQUIRED_RESULT_FIELDS - set(record.keys())
        if missing:
            errors.append(f"  Result record {i+1}: missing fields {sorted(missing)}")
            continue  # Can't proceed with validation on this record

        # 2. Status validity
        status = record.get("status", "")
        if status not in VALID_STATUSES:
            errors.append(
                f"  Result record {i+1} ({record.get('test_nodeid', '?')}): "
                f"invalid status '{status}'. Must be one of {VALID_STATUSES}"
            )

        # 3. Duration validity
        duration = record.get("duration_sec", 0)
        try:
            if float(duration) < 0:
                errors.append(
                    f"  Result record {i+1}: negative duration {duration} "
                    f"for test {record.get('test_nodeid', '?')}"
                )
        except (TypeError, ValueError):
            errors.append(
                f"  Result record {i+1}: non-numeric duration '{duration}' "
                f"for test {record.get('test_nodeid', '?')}"
            )

        # 4. Missing commit_sha or test_nodeid
        sha = record.get("commit_sha", "")
        nodeid = record.get("test_nodeid", "")
        run_id = record.get("run_id", "")

        if not sha:
            errors.append(f"  Result record {i+1}: blank commit_sha")
        if not nodeid:
            errors.append(f"  Result record {i+1}: blank test_nodeid")

        # 5. Duplicate check: (commit_sha, test_nodeid, run_id)
        key = (sha, nodeid, run_id)
        if key in seen_keys:
            errors.append(
                f"  Duplicate: ({sha[:12]}..., {nodeid}, {run_id})"
            )
        seen_keys.add(key)

        # 6. Referential integrity — result's commit_sha is in commits.jsonl
        if sha and sha != "UNKNOWN" and known_shas and sha not in known_shas:
            errors.append(
                f"  Result record {i+1}: commit_sha {sha[:12]}... "
                f"not found in commits.jsonl"
            )

        # 7. Data source
        src = record.get("data_source", "")
        if src not in VALID_DATA_SOURCES:
            errors.append(
                f"  Result record {i+1}: invalid data_source '{src}'"
            )

    return errors


def check_csv_consistency(results_count: int) -> list[str]:
    """Check that dataset.csv row count matches test_results.jsonl."""
    errors: list[str] = []
    if not DATASET_FILE.exists():
        errors.append(f"  dataset.csv not found — run: python tools/build_dataset.py")
        return errors

    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        csv_rows = sum(1 for _ in csv.reader(f)) - 1  # subtract header

    if csv_rows != results_count:
        errors.append(
            f"  dataset.csv has {csv_rows} rows but test_results.jsonl has "
            f"{results_count} records. Re-run: python tools/build_dataset.py"
        )
    return errors


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def compute_stats(commits: list[dict], results: list[dict]) -> dict:
    """Compute summary statistics for the report."""
    status_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    unique_tests: set[str] = set()
    unique_commits: set[str] = set()
    unique_run_ids: set[str] = set()

    for r in results:
        status = r.get("status", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
        src = r.get("data_source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
        unique_tests.add(r.get("test_nodeid", ""))
        unique_commits.add(r.get("commit_sha", ""))
        unique_run_ids.add(r.get("run_id", ""))

    return {
        "total_commit_records": len(commits),
        "total_result_records": len(results),
        "unique_commits": len(unique_commits),
        "unique_tests": len(unique_tests),
        "unique_runs": len(unique_run_ids),
        "status_counts": status_counts,
        "source_counts": source_counts,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("SmartQA Phase 4 — Dataset Validation")
    print("=" * 60)
    print()

    all_errors: list[str] = []

    # --- Load commits ---
    print("Loading commits.jsonl...")
    commits, commit_load_errors = _load_jsonl(COMMITS_FILE)
    if commit_load_errors:
        all_errors.extend(commit_load_errors)
    print(f"  → {len(commits)} commit record(s)")

    # --- Load test results ---
    print("Loading test_results.jsonl...")
    results, result_load_errors = _load_jsonl(RESULTS_FILE)
    if result_load_errors:
        all_errors.extend(result_load_errors)
    print(f"  → {len(results)} test result record(s)")

    # --- Run checks ---
    print("\nRunning validation checks...")

    known_shas = {r.get("commit_sha", "") for r in commits}

    commit_errors = check_commits(commits)
    result_errors = check_results(results, known_shas)
    csv_errors = check_csv_consistency(len(results))

    all_errors.extend(commit_errors)
    all_errors.extend(result_errors)
    all_errors.extend(csv_errors)

    # --- Stats ---
    stats = compute_stats(commits, results)

    # --- Report ---
    print()
    print("-" * 60)
    print("Dataset Validation Report")
    print("-" * 60)
    print(f"Commit records          : {stats['total_commit_records']}")
    print(f"Test result records     : {stats['total_result_records']}")
    print(f"Unique commits          : {stats['unique_commits']}")
    print(f"Unique test runs        : {stats['unique_runs']}")
    print(f"Unique tests            : {stats['unique_tests']}")
    print()

    status_counts = stats["status_counts"]
    for status in ("PASS", "FAIL", "SKIP", "ERROR"):
        count = status_counts.get(status, 0)
        print(f"  {status:<6}               : {count}")

    print("\nData Sources:")
    source_counts = stats["source_counts"]
    for src in sorted(source_counts.keys()):
        print(f"  {src:<20}: {source_counts[src]}")

    print()
    if all_errors:
        print(f"[ERROR] VALIDATION FAILED — {len(all_errors)} issue(s) found:")
        for err in all_errors:
            print(err)
        print()
        print("STATUS: INVALID")
        return 1
    else:
        # Advisory warnings (not failures)
        if stats["unique_tests"] > 0 and stats["unique_tests"] < EXPECTED_TESTS_PER_RUN:
            print(
                f"[WARNING] Advisory: Only {stats['unique_tests']} unique tests recorded "
                f"(expected {EXPECTED_TESTS_PER_RUN} per run)."
            )
        if stats["unique_commits"] == 1:
            print(
                "[WARNING] Advisory: Only 1 commit in dataset. "
                "More commits are needed for meaningful ML training."
            )
        print("STATUS: VALID [OK]")
        return 0


if __name__ == "__main__":
    sys.exit(main())
