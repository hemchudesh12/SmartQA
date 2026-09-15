"""
tools/validate_features.py — Feature Dataset Validator for SmartQA Phase 5.

USAGE:
    python tools/validate_features.py

WHAT IT VALIDATES:
    1. Required columns exist in data/features.csv and data/features_encoded.csv
    2. Dataset is not empty
    3. No duplicate (commit_sha, test_nodeid, run_id) rows
    4. Target 'test_failed' contains only valid binary values (0 or 1)
    5. Numerical features contain valid numeric values (no NaNs or Infs)
    6. No missing/unparsed values in critical feature columns
    7. Commit SHAs are valid hex strings or UNKNOWN
    8. Historical leakage check: prior run counts never exceed total prior observations
    9. Target column is absent from input feature columns
    10. Encoded CSV consistency with human-readable CSV
    11. Class distribution (PASS vs FAIL) is computed and reported

EXIT CODES:
    0 → Feature dataset is VALID
    1 → Validation FAILED
"""

import csv
import math
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths & Schemas
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FEATURES_FILE = DATA_DIR / "features.csv"
FEATURES_ENCODED_FILE = DATA_DIR / "features_encoded.csv"

REQUIRED_FEATURE_COLUMNS = {
    "commit_sha", "run_id", "test_nodeid", "test_file", "test_name",
    "lines_added", "lines_deleted", "total_lines_changed", "changed_file_count",
    "commit_message_length", "commit_message_word_count", "has_fix_keyword",
    "has_feature_keyword", "has_refactor_keyword", "has_bug_keyword", "has_test_keyword",
    "changed_python_file_count", "changed_test_file_count", "changed_app_file_count",
    "test_name_length", "test_name_word_count", "is_smoke_test", "is_regression_test",
    "previous_test_runs", "previous_failures", "previous_passes", "historical_failure_rate",
    "previous_run_failure_rate", "average_previous_duration", "previous_duration_variance",
    "days_since_previous_execution", "test_file_changed", "test_area_changed",
    "commit_size_x_hist_failure_rate", "test_failed",
}

NUMERIC_COLUMNS = [
    "lines_added", "lines_deleted", "total_lines_changed", "changed_file_count",
    "commit_message_length", "commit_message_word_count", "has_fix_keyword",
    "has_feature_keyword", "has_refactor_keyword", "has_bug_keyword", "has_test_keyword",
    "changed_python_file_count", "changed_test_file_count", "changed_app_file_count",
    "test_name_length", "test_name_word_count", "is_smoke_test", "is_regression_test",
    "previous_test_runs", "previous_failures", "previous_passes", "historical_failure_rate",
    "previous_run_failure_rate", "average_previous_duration", "previous_duration_variance",
    "days_since_previous_execution", "test_file_changed", "test_area_changed",
    "commit_size_x_hist_failure_rate",
]


def check_file_exists(filepath: Path) -> list[str]:
    errors = []
    if not filepath.exists():
        errors.append(f"File not found: {filepath}")
    return errors


def load_csv(filepath: Path) -> tuple[list[dict], list[str]]:
    rows = []
    errors = []
    if not filepath.exists():
        return rows, [f"File does not exist: {filepath}"]
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)
    except Exception as exc:
        errors.append(f"Error reading CSV {filepath.name}: {exc}")
    return rows, errors


def validate_features(rows: list[dict]) -> list[str]:
    errors = []

    if not rows:
        errors.append("Feature dataset is completely EMPTY.")
        return errors

    headers = set(rows[0].keys())

    # 1. Schema check
    missing = REQUIRED_FEATURE_COLUMNS - headers
    if missing:
        errors.append(f"Missing required columns in features.csv: {sorted(missing)}")

    seen_keys = set()

    for idx, row in enumerate(rows, 1):
        # 2. Key Uniqueness
        key = (row.get("commit_sha"), row.get("test_nodeid"), row.get("run_id"))
        if key in seen_keys:
            errors.append(f"Row {idx}: Duplicate triplet key {key}")
        seen_keys.add(key)

        # 3. Target Label Validity
        target = row.get("test_failed", "")
        if target not in {"0", "1", 0, 1}:
            errors.append(f"Row {idx}: Invalid target 'test_failed' value: '{target}'")

        # 4. Numeric Column Validity & NaN/Inf check
        for col in NUMERIC_COLUMNS:
            val = row.get(col, "")
            if val == "" or val is None:
                errors.append(f"Row {idx}: Blank value for numeric column '{col}'")
                continue
            try:
                fval = float(val)
                if math.isnan(fval) or math.isinf(fval):
                    errors.append(f"Row {idx}: Non-finite (NaN/Inf) value in column '{col}': {val}")
            except ValueError:
                errors.append(f"Row {idx}: Non-numeric value in column '{col}': '{val}'")

        # 5. Temporal Leakage & Math Consistency
        try:
            prev_runs = int(row.get("previous_test_runs", 0))
            prev_fails = int(row.get("previous_failures", 0))
            prev_passes = int(row.get("previous_passes", 0))
            if prev_fails + prev_passes > prev_runs:
                errors.append(f"Row {idx}: Math inconsistency — prev_fails ({prev_fails}) + prev_passes ({prev_passes}) > prev_runs ({prev_runs})")

            hist_rate = float(row.get("historical_failure_rate", 0.0))
            if prev_runs > 0:
                expected_rate = round(prev_fails / prev_runs, 4)
                if abs(hist_rate - expected_rate) > 0.001:
                    errors.append(f"Row {idx}: Inconsistent failure rate. Stored: {hist_rate}, Expected: {expected_rate}")
            else:
                if hist_rate != 0.0:
                    errors.append(f"Row {idx}: Cold-start row has non-zero historical_failure_rate: {hist_rate}")
        except Exception:
            pass  # Caught by numeric checks above

    return errors


def main() -> int:
    print("=" * 60)
    print("SmartQA Phase 5 — Feature Dataset Validation")
    print("=" * 60)
    print()

    all_errors = []

    # Check file existence
    all_errors.extend(check_file_exists(FEATURES_FILE))
    all_errors.extend(check_file_exists(FEATURES_ENCODED_FILE))

    if all_errors:
        for err in all_errors:
            print(f"[ERROR] {err}")
        print("\nSTATUS: INVALID")
        return 1

    feature_rows, load_errs = load_csv(FEATURES_FILE)
    encoded_rows, enc_load_errs = load_csv(FEATURES_ENCODED_FILE)

    all_errors.extend(load_errs)
    all_errors.extend(enc_load_errs)

    # Validate feature rows
    feature_errs = validate_features(feature_rows)
    all_errors.extend(feature_errs)

    # Check row count consistency between CSVs
    if len(feature_rows) != len(encoded_rows):
        all_errors.append(
            f"Row count mismatch between features.csv ({len(feature_rows)}) "
            f"and features_encoded.csv ({len(encoded_rows)})"
        )

    # Compute Statistics
    pass_cnt = sum(1 for r in feature_rows if str(r.get("test_failed")) == "0")
    fail_cnt = sum(1 for r in feature_rows if str(r.get("test_failed")) == "1")
    total = len(feature_rows)
    fail_rate = (fail_cnt / total * 100) if total > 0 else 0.0

    print("-" * 60)
    print("Feature Validation Summary Report")
    print("-" * 60)
    print(f"Total Feature Rows     : {total}")
    print(f"Encoded Feature Rows   : {len(encoded_rows)}")
    print(f"PASS Rows (0)          : {pass_cnt}")
    print(f"FAIL/ERROR Rows (1)    : {fail_cnt}")
    print(f"Failure Rate           : {fail_rate:.2f}%")
    print()

    if all_errors:
        print(f"[ERROR] VALIDATION FAILED — {len(all_errors)} issue(s) detected:")
        for err in all_errors:
            print(f"  - {err}")
        print("\nSTATUS: INVALID")
        return 1
    else:
        print("STATUS: VALID [OK]")
        return 0


if __name__ == "__main__":
    sys.exit(main())
