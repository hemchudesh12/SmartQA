"""
tools/train_model.py — SmartQA Phase 6 ML Training Pipeline.

USAGE:
    python tools/train_model.py

WHAT IT DOES:
    1. Loads data/features_encoded.csv (Phase 5 output).
    2. Performs commit-level chronological train/test split.
    3. Detects class diversity. Aborts safely if training set
       contains only one target class.
    4. Trains a Logistic Regression baseline classifier
       (random_state=42, class_weight="balanced").
    5. Saves model pipeline to models/failure_predictor.joblib.
    6. Saves metadata to models/model_metadata.json.
    7. Saves predictions on test set to data/predictions.csv.

TEMPORAL SPLIT:
    Commits are sorted chronologically by the first timestamp
    seen for each commit_sha. Earliest 80% of unique commits
    are training; latest 20% are testing.

    ALL rows for a commit go entirely to train or entirely to
    test. No commit is split across both sets.

LEAKAGE POLICY:
    'test_failed' is the target and is NEVER included in X.
    Fields that reveal the current execution outcome
    (duration_sec, failure_message, status) are excluded.
    Only pre-execution features and historical features are used.

EXIT CODES:
    0  — Success or handled insufficient-data exit
    1  — Hard error (file missing, parse failure, etc.)
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
FEATURES_ENCODED = DATA_DIR / "features_encoded.csv"
PREDICTIONS_FILE = DATA_DIR / "predictions.csv"
MODEL_FILE = MODELS_DIR / "failure_predictor.joblib"
METADATA_FILE = MODELS_DIR / "model_metadata.json"

# ---------------------------------------------------------------------------
# Feature columns (no target, no leakage fields)
# ---------------------------------------------------------------------------
# These are all numeric — no categorical encoding needed for encoded CSV.
# Excluded: commit_sha, test_nodeid (identifiers), test_failed (target).
FEATURE_COLUMNS = [
    "lines_added",
    "lines_deleted",
    "total_lines_changed",
    "changed_file_count",
    "commit_message_length",
    "commit_message_word_count",
    "has_fix_keyword",
    "has_feature_keyword",
    "has_refactor_keyword",
    "has_bug_keyword",
    "has_test_keyword",
    "changed_python_file_count",
    "changed_test_file_count",
    "changed_app_file_count",
    "changed_template_file_count",
    "changed_static_file_count",
    "changed_config_file_count",
    "test_name_length",
    "test_name_word_count",
    "is_smoke_test",
    "is_regression_test",
    "previous_test_runs",
    "previous_failures",
    "previous_passes",
    "historical_failure_rate",
    "previous_run_failure_rate",
    "average_previous_duration",
    "previous_duration_variance",
    "days_since_previous_execution",
    "test_file_changed",
    "test_area_changed",
    "commit_size_x_hist_failure_rate",
]
TARGET_COLUMN = "test_failed"
RANDOM_STATE = 42
TRAIN_FRACTION = 0.8  # fraction of unique commits used for training


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_features() -> list[dict]:
    """Load features_encoded.csv and return raw rows as list of dicts."""
    if not FEATURES_ENCODED.exists():
        print(f"[ERROR] {FEATURES_ENCODED} not found.")
        print("        Run: python tools/build_features.py")
        return []
    rows = []
    with open(FEATURES_ENCODED, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    print(f"  Loaded {len(rows)} rows from {FEATURES_ENCODED.name}")
    return rows


def commit_order(rows: list[dict]) -> list[str]:
    """
    Return unique commit SHAs sorted chronologically.
    Uses the first timestamp seen for each commit_sha.
    Chronological order is inferred from row order in features_encoded.csv
    (which was already built temporally by build_features.py).
    Because the encoded CSV preserves temporal row order we simply collect
    commits in their first-appearance order.
    """
    seen = {}
    for row in rows:
        sha = row.get("commit_sha", "")
        if sha and sha not in seen:
            seen[sha] = len(seen)   # insertion order = temporal order
    # Sort by insertion index (i.e., temporal order)
    ordered = sorted(seen.keys(), key=lambda s: seen[s])
    return ordered


def temporal_split(rows: list[dict], train_frac: float = TRAIN_FRACTION):
    """
    Chronological commit-level split.
    Returns (train_rows, test_rows, train_commits, test_commits).
    """
    ordered_commits = commit_order(rows)
    n_commits = len(ordered_commits)
    n_train = max(1, int(n_commits * train_frac))

    train_commits = set(ordered_commits[:n_train])
    test_commits = set(ordered_commits[n_train:])

    train_rows = [r for r in rows if r["commit_sha"] in train_commits]
    test_rows = [r for r in rows if r["commit_sha"] in test_commits]

    return train_rows, test_rows, train_commits, test_commits


def extract_xy(rows: list[dict]) -> tuple:
    """
    Build feature matrix X (list of lists) and target y (list of int)
    from CSV rows. Returns (X, y, commit_shas, test_nodeids).
    """
    X, y, shas, nodeids = [], [], [], []
    for row in rows:
        try:
            feat_vec = [float(row[col]) for col in FEATURE_COLUMNS]
        except (KeyError, ValueError) as e:
            print(f"[WARNING] Skipping malformed row: {e}")
            continue
        target = int(row[TARGET_COLUMN])
        X.append(feat_vec)
        y.append(target)
        shas.append(row.get("commit_sha", ""))
        nodeids.append(row.get("test_nodeid", ""))
    return X, y, shas, nodeids


def class_summary(y: list[int]) -> dict:
    pos = sum(y)
    neg = len(y) - pos
    return {"pass": neg, "fail": pos, "total": len(y)}


def check_class_diversity(y_train: list[int]) -> bool:
    """Return True if training set contains both classes."""
    return len(set(y_train)) >= 2


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

def train(X_train, y_train):
    """Fit sklearn Pipeline: StandardScaler + LogisticRegression."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        print("[ERROR] scikit-learn is not installed.")
        print("        Run: pip install scikit-learn")
        return None

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            random_state=RANDOM_STATE,
            class_weight="balanced",
            max_iter=1000,
            solver="lbfgs",
        )),
    ])
    pipeline.fit(X_train, y_train)
    return pipeline


def save_model(pipeline, metadata: dict) -> None:
    """Persist model pipeline and metadata."""
    try:
        import joblib
    except ImportError:
        print("[ERROR] joblib is not installed. Run: pip install joblib")
        return

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_FILE)
    print(f"[OK] Model saved to {MODEL_FILE}")

    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[OK] Metadata saved to {METADATA_FILE}")


def save_predictions(predictions: list[dict]) -> None:
    """Write predictions to data/predictions.csv."""
    if not predictions:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cols = list(predictions[0].keys())
    with open(PREDICTIONS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(predictions)
    print(f"[OK] Predictions saved to {PREDICTIONS_FILE} ({len(predictions)} rows)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("SmartQA Phase 6 — ML Training Pipeline")
    print("=" * 60)
    print()

    # 1. Load
    print("Step 1: Loading features...")
    rows = load_features()
    if not rows:
        return 1

    total_rows = len(rows)
    all_targets = [int(r[TARGET_COLUMN]) for r in rows]
    dist = class_summary(all_targets)
    failure_rate = dist["fail"] / dist["total"] * 100 if dist["total"] > 0 else 0.0

    print(f"  Total rows:       {total_rows}")
    print(f"  PASS (0):         {dist['pass']}")
    print(f"  FAIL/ERROR (1):   {dist['fail']}")
    print(f"  Failure rate:     {failure_rate:.2f}%")
    print(f"  Unique commits:   {len(set(r['commit_sha'] for r in rows))}")

    # 2. Temporal split
    print("\nStep 2: Temporal commit-level split...")
    train_rows, test_rows, train_commits, test_commits = temporal_split(rows)

    print(f"  Training commits: {len(train_commits)}")
    print(f"  Test commits:     {len(test_commits)}")
    print(f"  Training rows:    {len(train_rows)}")
    print(f"  Test rows:        {len(test_rows)}")

    # Safety: no overlap
    overlap = train_commits & test_commits
    if overlap:
        print(f"[ERROR] Commit overlap detected between train and test: {overlap}")
        return 1
    print("  Commit overlap:   NONE [OK]")

    # 3. Extract X, y
    print("\nStep 3: Extracting features and target...")
    X_train, y_train, shas_train, nodeids_train = extract_xy(train_rows)
    X_test, y_test, shas_test, nodeids_test = extract_xy(test_rows)

    train_dist = class_summary(y_train)
    test_dist = class_summary(y_test)

    print(f"  Train — PASS: {train_dist['pass']}, FAIL: {train_dist['fail']}")
    print(f"  Test  — PASS: {test_dist['pass']},  FAIL: {test_dist['fail']}")

    # 4. Class diversity check
    print("\nStep 4: Checking class diversity in training set...")
    if not check_class_diversity(y_train):
        print()
        print("=" * 60)
        print("[RESULT] INSUFFICIENT CLASS DIVERSITY FOR SUPERVISED TRAINING")
        print("=" * 60)
        print()
        print("  Training data contains only one target class.")
        print(f"  Training PASS: {train_dist['pass']}, FAIL: {train_dist['fail']}")
        print()
        print("  A Logistic Regression classifier requires examples of BOTH")
        print("  PASS (0) and FAIL (1) outcomes in the training period.")
        print()
        print("  Current dataset has an extreme class imbalance:")
        print(f"  {dist['fail']} FAIL out of {dist['total']} total rows ({failure_rate:.2f}%).")
        print()
        print("  This is NOT a software bug. It is a scientifically correct")
        print("  response to insufficient historical failure data.")
        print()
        print("  ACTION REQUIRED:")
        print("  Collect more genuine test run data including real test failures.")
        print("  Re-run: python tools/build_features.py")
        print("  Then:   python tools/train_model.py")
        print()
        print("  The pipeline is complete and ready to train once sufficient")
        print("  failure examples are present in the training period.")
        print()
        print("STATUS: TRAINING SKIPPED — INSUFFICIENT CLASS DIVERSITY")
        return 0

    print("  Both classes present in training set. [OK]")

    # 5. Train model
    print("\nStep 5: Training Logistic Regression...")
    pipeline = train(X_train, y_train)
    if pipeline is None:
        return 1
    print("  Training complete. [OK]")

    # 6. Generate predictions on test set
    print("\nStep 6: Generating predictions on test set...")
    probas = pipeline.predict_proba(X_test)
    preds = pipeline.predict(X_test)

    predictions = []
    for sha, nodeid, actual, prob_arr, pred in zip(
        shas_test, nodeids_test, y_test, probas, preds
    ):
        predictions.append({
            "commit_sha": sha,
            "test_nodeid": nodeid,
            "actual_test_failed": actual,
            "predicted_failure_probability": round(float(prob_arr[1]), 6),
            "predicted_label": int(pred),
        })

    save_predictions(predictions)

    # 7. Save model & metadata
    print("\nStep 7: Saving model and metadata...")
    metadata = {
        "model_type": "LogisticRegression",
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "random_state": RANDOM_STATE,
        "class_weight": "balanced",
        "feature_columns": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "target_definition": {
            "PASS": 0,
            "FAIL": 1,
            "ERROR": 1,
            "SKIP": "excluded",
        },
        "train_commit_count": len(train_commits),
        "test_commit_count": len(test_commits),
        "train_row_count": len(X_train),
        "test_row_count": len(X_test),
        "train_pass_count": train_dist["pass"],
        "train_fail_count": train_dist["fail"],
        "test_pass_count": test_dist["pass"],
        "test_fail_count": test_dist["fail"],
        "dataset_total_rows": total_rows,
        "dataset_failure_rate_pct": round(failure_rate, 4),
        "train_fraction": TRAIN_FRACTION,
        "temporal_split": True,
        "commit_overlap": False,
        "leakage_safe": True,
        "scaler": "StandardScaler",
        "solver": "lbfgs",
        "max_iter": 1000,
    }
    save_model(pipeline, metadata)

    print()
    print("=" * 60)
    print("STATUS: TRAINING COMPLETE")
    print("=" * 60)
    print()
    print("Next step:")
    print("  python tools/evaluate_model.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
