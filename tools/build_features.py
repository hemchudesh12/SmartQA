"""
tools/build_features.py — Feature Engineering Pipeline for SmartQA Phase 5.

USAGE:
    python tools/build_features.py

WHAT IT DOES:
    1. Reads data/dataset.csv (or data/commits.jsonl & data/test_results.jsonl).
    2. Sorts records chronologically.
    3. Computes:
       - Commit-level features (lines changed, commit msg keywords, file area counts)
       - Test-level features (nodeid, file, markers, name lengths)
       - Historical test features strictly BEFORE current observation (temporal leakage prevention)
       - Commit × Test interaction features (file matches, size x failure rate)
       - Target label `test_failed` (PASS=0, FAIL=1, ERROR=1; SKIP excluded)
    4. Outputs:
       - data/features.csv (human-readable engineered feature dataset)
       - data/features_encoded.csv (machine-ready ML dataset)
"""

import csv
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
COMMITS_FILE = DATA_DIR / "commits.jsonl"
RESULTS_FILE = DATA_DIR / "test_results.jsonl"
DATASET_FILE = DATA_DIR / "dataset.csv"
FEATURES_FILE = DATA_DIR / "features.csv"
FEATURES_ENCODED_FILE = DATA_DIR / "features_encoded.csv"

# Keyword definitions for commit messages
FIX_KEYWORDS = {"fix", "fixed", "fixing", "bugfix", "patch"}
FEAT_KEYWORDS = {"feat", "feature", "add", "added", "adding", "new"}
REFACTOR_KEYWORDS = {"refactor", "clean", "cleanup", "structure", "restructure"}
BUG_KEYWORDS = {"bug", "issue", "error", "defect", "fail", "failure", "broken"}
TEST_KEYWORDS = {"test", "tests", "testing", "coverage", "assert"}

# ---------------------------------------------------------------------------
# Feature Extraction Helpers
# ---------------------------------------------------------------------------

def parse_iso_datetime(ts_str: str) -> datetime:
    """Parse ISO timestamp string into datetime object for chronological sorting."""
    if not ts_str:
        return datetime.min
    try:
        # Normalize Z to +00:00 if present
        ts_str_clean = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str_clean)
    except Exception:
        return datetime.min


def extract_commit_features(row: dict) -> dict:
    """Extract commit-level features from a row."""
    commit_msg = str(row.get("commit_message", "") or "").strip()
    commit_msg_lower = commit_msg.lower()
    words = set(re.findall(r"\w+", commit_msg_lower))

    lines_added = int(row.get("lines_added", 0) or 0)
    lines_deleted = int(row.get("lines_deleted", 0) or 0)
    total_lines_changed = lines_added + lines_deleted

    changed_files_raw = str(row.get("changed_files", "") or "").strip()
    changed_files = [f.strip() for f in changed_files_raw.split(",") if f.strip()]
    changed_file_count = int(row.get("changed_file_count", len(changed_files)) or len(changed_files))

    # File type / domain breakdown
    py_count = sum(1 for f in changed_files if f.endswith(".py"))
    test_count = sum(1 for f in changed_files if "test" in f.lower() or f.startswith("automation/") or f.startswith("tests/"))
    app_count = sum(1 for f in changed_files if f.startswith("app/"))
    template_count = sum(1 for f in changed_files if f.endswith(".html") or f.endswith(".jinja") or "templates" in f)
    static_count = sum(1 for f in changed_files if f.endswith(".css") or f.endswith(".js") or f.endswith(".png") or "static" in f)
    config_count = sum(1 for f in changed_files if f.endswith(".ini") or f.endswith(".json") or f.endswith(".yml") or f.endswith(".yaml") or f in {"config.py", "requirements.txt", "seed.py"})

    return {
        "lines_added": lines_added,
        "lines_deleted": lines_deleted,
        "total_lines_changed": total_lines_changed,
        "changed_file_count": changed_file_count,
        "commit_message_length": len(commit_msg),
        "commit_message_word_count": len(commit_msg.split()),
        "has_fix_keyword": int(bool(words & FIX_KEYWORDS)),
        "has_feature_keyword": int(bool(words & FEAT_KEYWORDS)),
        "has_refactor_keyword": int(bool(words & REFACTOR_KEYWORDS)),
        "has_bug_keyword": int(bool(words & BUG_KEYWORDS)),
        "has_test_keyword": int(bool(words & TEST_KEYWORDS)),
        "changed_python_file_count": py_count,
        "changed_test_file_count": test_count,
        "changed_app_file_count": app_count,
        "changed_template_file_count": template_count,
        "changed_static_file_count": static_count,
        "changed_config_file_count": config_count,
    }


def extract_test_features(row: dict) -> dict:
    """Extract test-level deterministic features."""
    test_nodeid = str(row.get("test_nodeid", "") or "").strip()
    test_file = str(row.get("test_file", "") or "").strip()
    test_name = str(row.get("test_name", "") or "").strip()
    markers_str = str(row.get("markers", "") or "").strip()
    markers = set(m.strip().lower() for m in markers_str.split(",") if m.strip())

    return {
        "test_nodeid": test_nodeid,
        "test_file": test_file,
        "test_name": test_name,
        "test_name_length": len(test_name),
        "test_name_word_count": len(re.findall(r"\w+", test_name)),
        "is_smoke_test": int("smoke" in markers),
        "is_regression_test": int("regression" in markers),
    }


def extract_interaction_features(row: dict, commit_feats: dict, test_feats: dict, hist_failure_rate: float) -> dict:
    """Extract commit × test interaction features."""
    test_file = test_feats["test_file"]
    changed_files_raw = str(row.get("changed_files", "") or "").strip()
    changed_files = [f.strip() for f in changed_files_raw.split(",") if f.strip()]

    # Is the test file directly modified in this commit?
    test_file_changed = int(test_file in changed_files or any(f.endswith(Path(test_file).name) for f in changed_files))

    # Test area match: e.g. test_auth.py vs app/auth or auth routes
    test_stem = Path(test_file).stem.replace("test_", "")
    test_area_changed = 0
    for cf in changed_files:
        if test_stem in cf.lower():
            test_area_changed = 1
            break

    total_lines = commit_feats["total_lines_changed"]
    commit_size_x_hist_failure_rate = float(total_lines) * hist_failure_rate

    return {
        "test_file_changed": test_file_changed,
        "test_area_changed": test_area_changed,
        "commit_size_x_hist_failure_rate": round(commit_size_x_hist_failure_rate, 4),
    }

# ---------------------------------------------------------------------------
# Main Feature Generation Engine
# ---------------------------------------------------------------------------

def load_source_dataset() -> list[dict]:
    """Load records from dataset.csv or JSONL files."""
    rows = []
    if DATASET_FILE.exists():
        with open(DATASET_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)
        print(f"Loaded {len(rows)} raw rows from {DATASET_FILE.name}")
    else:
        # Fallback to JSONL
        if not COMMITS_FILE.exists() or not RESULTS_FILE.exists():
            raise FileNotFoundError("Neither dataset.csv nor JSONL source files exist in data/")
        commits = {}
        with open(COMMITS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    commits[rec["commit_sha"]] = rec
        results = []
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))

        for r in results:
            sha = r.get("commit_sha", "")
            c = commits.get(sha, {})
            merged = {
                "commit_sha": sha,
                "parent_sha": c.get("parent_sha", ""),
                "commit_message": c.get("commit_message", ""),
                "author": c.get("author", ""),
                "timestamp_iso": c.get("timestamp_iso", ""),
                "branch": c.get("branch", ""),
                "changed_files": ",".join(c.get("changed_files", [])),
                "changed_file_count": c.get("changed_file_count", 0),
                "lines_added": c.get("lines_added", 0),
                "lines_deleted": c.get("lines_deleted", 0),
                "run_id": r.get("run_id", ""),
                "test_nodeid": r.get("test_nodeid", ""),
                "test_file": r.get("test_file", ""),
                "test_name": r.get("test_name", ""),
                "markers": ",".join(r.get("markers", [])),
                "status": r.get("status", ""),
                "duration_sec": r.get("duration_sec", 0.0),
                "failure_message": r.get("failure_message", ""),
                "run_timestamp_iso": r.get("run_timestamp_iso", ""),
                "data_source": r.get("data_source", "real"),
            }
            rows.append(merged)
        print(f"Loaded {len(rows)} raw rows from JSONL files")
    return rows


def build_features(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Build temporal feature dataset.
    Returns (human_readable_features, encoded_features).
    """
    # 1. Sort records chronologically
    # Use run_timestamp_iso if present, else timestamp_iso
    def sort_key(r):
        ts = r.get("run_timestamp_iso") or r.get("timestamp_iso") or ""
        return (parse_iso_datetime(ts), r.get("run_id", ""), r.get("test_nodeid", ""))

    sorted_rows = sorted(rows, key=sort_key)

    # Historical state tracker per test_nodeid
    # Keeps track of PREVIOUS executions strictly before current observation
    test_history: dict[str, list[dict]] = {}

    feature_rows = []
    encoded_rows = []

    for row in sorted_rows:
        status = str(row.get("status", "") or "").upper()

        # Handle Target Label & Exclude SKIPs from training dataset
        if status == "SKIP":
            continue
        elif status == "PASS":
            target_failed = 0
        elif status in {"FAIL", "ERROR"}:
            target_failed = 1
        else:
            # Unknown status, skip
            continue

        nodeid = str(row.get("test_nodeid", "") or "").strip()
        curr_ts_str = row.get("run_timestamp_iso") or row.get("timestamp_iso") or ""
        curr_dt = parse_iso_datetime(curr_ts_str)

        # 2. Extract historical features ONLY from prior executions
        history = test_history.get(nodeid, [])
        prev_runs = len(history)
        prev_failures = sum(1 for h in history if h["status"] in {"FAIL", "ERROR"})
        prev_passes = sum(1 for h in history if h["status"] == "PASS")

        if prev_runs > 0:
            hist_failure_rate = round(prev_failures / prev_runs, 4)
            durations = [h["duration_sec"] for h in history]
            avg_duration = round(sum(durations) / prev_runs, 4)
            if prev_runs > 1:
                variance = sum((d - avg_duration) ** 2 for d in durations) / (prev_runs - 1)
                dur_variance = round(variance, 4)
            else:
                dur_variance = 0.0

            # Last run failure rate
            last_status = history[-1]["status"]
            prev_run_failure_rate = 1.0 if last_status in {"FAIL", "ERROR"} else 0.0

            # Days since last execution
            last_dt = history[-1]["dt"]
            if curr_dt != datetime.min and last_dt != datetime.min:
                delta_days = (curr_dt - last_dt).total_seconds() / 86400.0
                days_since_prev = round(max(0.0, delta_days), 4)
            else:
                days_since_prev = 0.0
        else:
            # Cold-start defaults
            hist_failure_rate = 0.0
            avg_duration = 0.0
            dur_variance = 0.0
            prev_run_failure_rate = 0.0
            days_since_prev = 0.0

        # Extract features
        commit_feats = extract_commit_features(row)
        test_feats = extract_test_features(row)
        interaction_feats = extract_interaction_features(row, commit_feats, test_feats, hist_failure_rate)

        hist_feats = {
            "previous_test_runs": prev_runs,
            "previous_failures": prev_failures,
            "previous_passes": prev_passes,
            "historical_failure_rate": hist_failure_rate,
            "previous_run_failure_rate": prev_run_failure_rate,
            "average_previous_duration": avg_duration,
            "previous_duration_variance": dur_variance,
            "days_since_previous_execution": days_since_prev,
        }

        # Combine all features into readable record
        readable_record = {
            "commit_sha": row.get("commit_sha", ""),
            "run_id": row.get("run_id", ""),
            "test_nodeid": nodeid,
            "test_file": test_feats["test_file"],
            "test_name": test_feats["test_name"],
            "data_source": row.get("data_source", "real"),
            **commit_feats,
            **test_feats,
            **hist_feats,
            **interaction_feats,
            "test_failed": target_failed,  # TARGET LABEL
        }

        # Numeric ML Encoded record
        encoded_record = {
            "commit_sha": row.get("commit_sha", ""),
            "test_nodeid": nodeid,
            **commit_feats,
            "test_name_length": test_feats["test_name_length"],
            "test_name_word_count": test_feats["test_name_word_count"],
            "is_smoke_test": test_feats["is_smoke_test"],
            "is_regression_test": test_feats["is_regression_test"],
            **hist_feats,
            **interaction_feats,
            "test_failed": target_failed,
        }

        feature_rows.append(readable_record)
        encoded_rows.append(encoded_record)

        # 3. NOW UPDATE HISTORY AFTER feature extraction (Data Leakage Safeguard!)
        duration_sec = float(row.get("duration_sec", 0.0) or 0.0)
        test_history.setdefault(nodeid, []).append({
            "status": status,
            "duration_sec": duration_sec,
            "dt": curr_dt,
        })

    return feature_rows, encoded_rows


def save_datasets(feature_rows: list[dict], encoded_rows: list[dict]) -> None:
    """Write output CSV files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if feature_rows:
        headers = list(feature_rows[0].keys())
        with open(FEATURES_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(feature_rows)
        print(f"[OK] Saved {len(feature_rows)} rows to {FEATURES_FILE.name}")

    if encoded_rows:
        headers_enc = list(encoded_rows[0].keys())
        with open(FEATURES_ENCODED_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers_enc)
            writer.writeheader()
            writer.writerows(encoded_rows)
        print(f"[OK] Saved {len(encoded_rows)} rows to {FEATURES_ENCODED_FILE.name}")


def main() -> int:
    print("=" * 60)
    print("SmartQA Phase 5 — Feature Engineering Pipeline")
    print("=" * 60)
    print()

    try:
        rows = load_source_dataset()
    except Exception as exc:
        print(f"[ERROR] Failed to load dataset: {exc}")
        return 1

    feature_rows, encoded_rows = build_features(rows)
    save_datasets(feature_rows, encoded_rows)

    # Class distribution statistics
    pass_cnt = sum(1 for r in feature_rows if r["test_failed"] == 0)
    fail_cnt = sum(1 for r in feature_rows if r["test_failed"] == 1)
    total = len(feature_rows)
    fail_rate = (fail_cnt / total * 100) if total > 0 else 0.0

    print("\nFeature Generation Summary:")
    print(f"  Total Feature Rows : {total}")
    print(f"  Feature Columns    : {len(feature_rows[0]) if feature_rows else 0}")
    print(f"  PASS (0)           : {pass_cnt}")
    print(f"  FAIL/ERROR (1)     : {fail_cnt}")
    print(f"  Failure Rate       : {fail_rate:.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
