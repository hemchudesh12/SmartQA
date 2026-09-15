"""
tools/build_dataset.py — Dataset Builder for SmartQA Phase 4.

USAGE:
    python tools/build_dataset.py

WHAT IT DOES:
    Reads data/commits.jsonl and data/test_results.jsonl.
    Joins them on 'commit_sha'.
    Writes a flat, denormalized data/dataset.csv suitable for Phase 5 feature engineering.

WHY FLAT CSV FOR ML?
    The JSONL files are the source of truth (normalized, append-only).
    The CSV is a pre-joined view that:
      - pandas can read directly with pd.read_csv()
      - scikit-learn can consume without extra join logic in Phase 5
      - is regeneratable at any time from the JSONL sources

    The CSV is gitignored (regeneratable) but the JSONL files are committed.

DATA LEAKAGE REMINDER:
    The 'status' column in dataset.csv is the TARGET LABEL.
    Phase 5 must NEVER use 'status' of run N as an input feature for run N.
    Historical failure rates (computed from prior runs) are safe as features.

OUTPUT COLUMNS:
    Commit-level (features):
        commit_sha, parent_sha, commit_message, author, timestamp_iso, branch,
        changed_file_count, lines_added, lines_deleted, data_source

    Test-level (labels / identifiers):
        run_id, test_nodeid, test_file, test_name, markers,
        status, duration_sec, failure_message, run_timestamp_iso
"""

import csv
import json
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

# Ordered CSV columns — defines the Phase 5 input schema
COLUMNS = [
    # --- Commit-level (pre-execution features) ---
    "commit_sha",
    "parent_sha",
    "commit_message",
    "author",
    "timestamp_iso",
    "branch",
    "changed_files",          # comma-separated list of paths
    "changed_file_count",
    "lines_added",
    "lines_deleted",
    # --- Run + test identifiers ---
    "run_id",
    "test_nodeid",
    "test_file",
    "test_name",
    "markers",                # comma-separated list of marker names
    # --- Post-execution labels ---
    "status",                 # PASS / FAIL / SKIP / ERROR  ← TARGET LABEL
    "duration_sec",
    "failure_message",
    "run_timestamp_iso",
    # --- Metadata ---
    "data_source",            # "real" or "controlled_failure"
]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_commits() -> dict[str, dict]:
    """
    Load commits.jsonl into a dict keyed by commit_sha.
    If multiple records exist for the same SHA, last one wins
    (shouldn't happen due to deduplication, but be safe).
    """
    commits: dict[str, dict] = {}
    if not COMMITS_FILE.exists():
        print(f"[WARNING] {COMMITS_FILE} does not exist. Run: python tools/collect_git_metadata.py")
        return commits

    with open(COMMITS_FILE, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                sha = record.get("commit_sha", "")
                if sha:
                    commits[sha] = record
            except json.JSONDecodeError as exc:
                print(f"[WARNING] Malformed JSON in {COMMITS_FILE} line {lineno}: {exc}")

    print(f"  Loaded {len(commits)} commit record(s) from {COMMITS_FILE.name}")
    return commits


def load_test_results() -> list[dict]:
    """Load all records from test_results.jsonl."""
    results: list[dict] = []
    if not RESULTS_FILE.exists():
        print(f"[WARNING] {RESULTS_FILE} does not exist. Run pytest to generate test data.")
        return results

    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f"[WARNING] Malformed JSON in {RESULTS_FILE} line {lineno}: {exc}")

    print(f"  Loaded {len(results)} test result record(s) from {RESULTS_FILE.name}")
    return results


# ---------------------------------------------------------------------------
# Join + flatten
# ---------------------------------------------------------------------------

def build_rows(commits: dict[str, dict], results: list[dict]) -> list[dict]:
    """
    Join test results with commit metadata on commit_sha.
    Returns a list of flat dicts with all COLUMNS present.
    """
    rows = []
    unmatched = 0

    for result in results:
        sha = result.get("commit_sha", "")
        commit = commits.get(sha)

        if commit is None:
            unmatched += 1
            # Still include the row but with blank commit fields
            # so no data is silently dropped
            commit = {
                "commit_sha": sha,
                "parent_sha": "",
                "commit_message": "",
                "author": "",
                "timestamp_iso": "",
                "branch": "",
                "changed_files": [],
                "changed_file_count": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "data_source": result.get("data_source", "real"),
            }

        # Flatten list fields to comma-separated strings for CSV compatibility
        changed_files_str = ",".join(commit.get("changed_files", []))
        markers_str = ",".join(result.get("markers", []))

        row = {
            "commit_sha": sha,
            "parent_sha": commit.get("parent_sha", ""),
            "commit_message": commit.get("commit_message", ""),
            "author": commit.get("author", ""),
            "timestamp_iso": commit.get("timestamp_iso", ""),
            "branch": commit.get("branch", ""),
            "changed_files": changed_files_str,
            "changed_file_count": commit.get("changed_file_count", 0),
            "lines_added": commit.get("lines_added", 0),
            "lines_deleted": commit.get("lines_deleted", 0),
            "run_id": result.get("run_id", ""),
            "test_nodeid": result.get("test_nodeid", ""),
            "test_file": result.get("test_file", ""),
            "test_name": result.get("test_name", ""),
            "markers": markers_str,
            "status": result.get("status", ""),
            "duration_sec": result.get("duration_sec", 0.0),
            "failure_message": result.get("failure_message", ""),
            "run_timestamp_iso": result.get("run_timestamp_iso", ""),
            "data_source": result.get("data_source", "real"),
        }
        rows.append(row)

    if unmatched > 0:
        print(
            f"\n[WARNING] {unmatched} test result(s) had no matching commit record.\n"
            f"   Run: python tools/collect_git_metadata.py  to collect commit data."
        )

    return rows


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict]) -> None:
    """Write the flat dataset to data/dataset.csv."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATASET_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n[OK] Wrote {len(rows)} rows to {DATASET_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("SmartQA Phase 4 — Dataset Builder")
    print("=" * 60)
    print()

    commits = load_commits()
    results = load_test_results()

    if not results:
        print("\n[ERROR] No test results found. Cannot build dataset.")
        return 1

    rows = build_rows(commits, results)
    if not rows:
        print("\n[ERROR] No rows to write after join.")
        return 1

    write_csv(rows)

    # Summary
    status_counts: dict[str, int] = {}
    for row in rows:
        s = row.get("status", "")
        status_counts[s] = status_counts.get(s, 0) + 1

    print("\nDataset Summary:")
    print(f"  Total rows      : {len(rows)}")
    print(f"  Unique commits  : {len(set(r['commit_sha'] for r in rows))}")
    print(f"  Unique tests    : {len(set(r['test_nodeid'] for r in rows))}")
    for status, count in sorted(status_counts.items()):
        print(f"  {status:<6}          : {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
