"""
tools/validate_prioritization.py — SmartQA Phase 7 Prioritization Validator.

USAGE:
    python tools/validate_prioritization.py

WHAT IT VALIDATES:
    1.  Required columns present in prioritized_tests.csv
    2.  Dataset is not empty
    3.  priority_rank is an integer
    4.  Ranks are unique
    5.  Ranks are consecutive (1, 2, 3, ..., N)
    6.  test_nodeid is non-empty for every row
    7.  No duplicate test_nodeid values
    8.  predicted_failure_probability is numeric in [0,1] or "N/A"
    9.  prediction_available is "True" or "False"
    10. All tests with prediction_available=True have a numeric probability
    11. No row uses actual_test_failed as a ranking signal (column absent)

EXIT CODES:
    0 — VALID
    1 — INVALID
"""

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PRIORITIZED_FILE = DATA_DIR / "prioritized_tests.csv"

REQUIRED_COLUMNS = {
    "priority_rank",
    "test_nodeid",
    "predicted_failure_probability",
    "prediction_available",
    "predicted_label",
}

LEAKAGE_COLUMNS = {"actual_test_failed", "status", "failure_message"}


def main() -> int:
    print("=" * 60)
    print("SmartQA Phase 7 — Prioritization Validation")
    print("=" * 60)
    print()

    errors: list[str] = []

    if not PRIORITIZED_FILE.exists():
        print(f"[ERROR] {PRIORITIZED_FILE} not found.")
        print("        Run: python tools/prioritize_tests.py")
        print("\nSTATUS: INVALID")
        return 1

    rows: list[dict] = []
    with open(PRIORITIZED_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])
        for r in reader:
            rows.append(r)

    print(f"Loaded {len(rows)} row(s) from {PRIORITIZED_FILE.name}")
    print()

    # 1. Required columns
    missing_cols = REQUIRED_COLUMNS - headers
    if missing_cols:
        errors.append(f"Missing required columns: {sorted(missing_cols)}")

    # 1b. Leakage columns must NOT be present
    leakage_present = LEAKAGE_COLUMNS & headers
    if leakage_present:
        errors.append(
            f"LEAKAGE DETECTED: Columns that reveal execution outcome are present: "
            f"{sorted(leakage_present)}"
        )

    # 2. Not empty
    if not rows:
        errors.append("Prioritized dataset is empty.")
        print("STATUS: INVALID")
        return 1

    seen_ranks: set[int] = set()
    seen_nodeids: set[str] = set()

    for idx, row in enumerate(rows, start=1):
        # 3. priority_rank is integer
        rank_raw = row.get("priority_rank", "")
        try:
            rank = int(rank_raw)
        except (ValueError, TypeError):
            errors.append(f"Row {idx}: priority_rank '{rank_raw}' is not an integer.")
            continue

        # 4. Ranks are unique
        if rank in seen_ranks:
            errors.append(f"Row {idx}: Duplicate priority_rank {rank}.")
        seen_ranks.add(rank)

        # 5. test_nodeid non-empty
        nodeid = row.get("test_nodeid", "").strip()
        if not nodeid:
            errors.append(f"Row {idx} (rank {rank}): test_nodeid is empty.")

        # 6. No duplicate test_nodeid
        if nodeid in seen_nodeids:
            errors.append(f"Duplicate test_nodeid: {nodeid}")
        seen_nodeids.add(nodeid)

        # 7. predicted_failure_probability: numeric in [0,1] or "N/A"
        prob_raw = row.get("predicted_failure_probability", "").strip()
        if prob_raw != "N/A":
            try:
                prob = float(prob_raw)
                if prob < 0.0 or prob > 1.0:
                    errors.append(
                        f"Row {idx} ({nodeid}): probability {prob} out of [0,1]."
                    )
            except ValueError:
                errors.append(
                    f"Row {idx} ({nodeid}): non-numeric probability '{prob_raw}'."
                )

        # 8. prediction_available is True or False
        pa = row.get("prediction_available", "").strip()
        if pa not in {"True", "False"}:
            errors.append(
                f"Row {idx} ({nodeid}): prediction_available='{pa}' must be 'True' or 'False'."
            )

        # 9. If prediction_available=True, probability must be numeric
        if pa == "True" and prob_raw == "N/A":
            errors.append(
                f"Row {idx} ({nodeid}): prediction_available=True but probability is N/A."
            )

    # 5. Consecutive ranks
    if seen_ranks:
        expected = set(range(1, len(rows) + 1))
        if seen_ranks != expected:
            gaps = expected - seen_ranks
            errors.append(f"Ranks are not consecutive. Missing: {sorted(gaps)[:10]}")

    # Print report
    print("-" * 60)
    print("Validation Report")
    print("-" * 60)
    print(f"  Total rows:        {len(rows)}")
    print(f"  Unique test IDs:   {len(seen_nodeids)}")
    pred_cnt = sum(1 for r in rows if r.get("prediction_available") == "True")
    print(f"  With predictions:  {pred_cnt}")
    print(f"  Without pred:      {len(rows) - pred_cnt}")
    print()

    if errors:
        print(f"[FAIL] VALIDATION FAILED — {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        print()
        print("STATUS: INVALID")
        return 1

    print("STATUS: VALID [OK]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
