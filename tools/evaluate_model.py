"""
tools/evaluate_model.py — SmartQA Phase 6 Model Evaluation.

USAGE:
    python tools/evaluate_model.py

WHAT IT DOES:
    1. Loads models/failure_predictor.joblib.
    2. Loads models/model_metadata.json.
    3. Loads data/predictions.csv.
    4. Computes and prints evaluation metrics.
    5. Saves evaluation_report.json to data/.

METRICS COMPUTED (only when both classes exist in y_test):
    - Accuracy
    - Precision (for class 1 = FAIL)
    - Recall    (for class 1 = FAIL)
    - F1-score  (for class 1 = FAIL)
    - Confusion matrix
    - ROC-AUC
    - PR-AUC

WHY RECALL MATTERS:
    Missing a test that will fail has a higher cost than a false alarm.
    Recall for the FAIL class is the primary operational metric for
    SmartQA Phase 7 test prioritization.

EXIT CODES:
    0  — Evaluation complete (or model/predictions not yet available)
    1  — Hard error
"""

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
PREDICTIONS_FILE = DATA_DIR / "predictions.csv"
MODEL_FILE = MODELS_DIR / "failure_predictor.joblib"
METADATA_FILE = MODELS_DIR / "model_metadata.json"
EVAL_REPORT_FILE = DATA_DIR / "evaluation_report.json"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_predictions() -> list[dict]:
    if not PREDICTIONS_FILE.exists():
        return []
    rows = []
    with open(PREDICTIONS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def load_metadata() -> dict:
    if not METADATA_FILE.exists():
        return {}
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def compute_metrics(y_true: list[int], y_pred: list[int], y_prob: list[float]) -> dict:
    """Compute classification metrics. Returns dict."""
    try:
        from sklearn.metrics import (
            accuracy_score,
            average_precision_score,
            classification_report,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )
    except ImportError:
        print("[ERROR] scikit-learn not installed.")
        return {}

    result = {}
    unique_classes = set(y_true)
    has_both_classes = len(unique_classes) >= 2

    result["accuracy"] = round(accuracy_score(y_true, y_pred), 4)
    result["unique_classes_in_test"] = sorted(unique_classes)

    if has_both_classes:
        result["precision_fail"] = round(precision_score(y_true, y_pred, pos_label=1, zero_division=0), 4)
        result["recall_fail"] = round(recall_score(y_true, y_pred, pos_label=1, zero_division=0), 4)
        result["f1_fail"] = round(f1_score(y_true, y_pred, pos_label=1, zero_division=0), 4)

        cm = confusion_matrix(y_true, y_pred).tolist()
        result["confusion_matrix"] = cm

        try:
            result["roc_auc"] = round(roc_auc_score(y_true, y_prob), 4)
        except Exception as e:
            result["roc_auc"] = f"undefined: {e}"

        try:
            result["pr_auc"] = round(average_precision_score(y_true, y_prob), 4)
        except Exception as e:
            result["pr_auc"] = f"undefined: {e}"
    else:
        msg = "undefined — test set contains only one class"
        result["precision_fail"] = msg
        result["recall_fail"] = msg
        result["f1_fail"] = msg
        result["roc_auc"] = msg
        result["pr_auc"] = msg
        result["confusion_matrix"] = msg

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("SmartQA Phase 6 — Model Evaluation")
    print("=" * 60)
    print()

    # Check model exists
    if not MODEL_FILE.exists():
        print(f"[INFO] Model file not found: {MODEL_FILE}")
        print("       Training was likely skipped due to insufficient class")
        print("       diversity. This is expected with the current dataset.")
        print()
        print("       Run: python tools/train_model.py")
        print("       Once training completes, re-run this evaluation.")
        print()
        print("STATUS: EVALUATION SKIPPED — NO TRAINED MODEL")
        return 0

    # Load metadata
    metadata = load_metadata()
    print("Model Metadata:")
    print(f"  Model type:        {metadata.get('model_type', 'unknown')}")
    print(f"  Training time:     {metadata.get('training_timestamp', 'unknown')}")
    print(f"  Train commits:     {metadata.get('train_commit_count', 'unknown')}")
    print(f"  Test commits:      {metadata.get('test_commit_count', 'unknown')}")
    print(f"  Train rows:        {metadata.get('train_row_count', 'unknown')}")
    print(f"  Test rows:         {metadata.get('test_row_count', 'unknown')}")
    print(f"  random_state:      {metadata.get('random_state', 'unknown')}")
    print(f"  class_weight:      {metadata.get('class_weight', 'unknown')}")
    print()

    # Load predictions
    preds_rows = load_predictions()
    if not preds_rows:
        print(f"[INFO] No predictions file found at {PREDICTIONS_FILE}")
        print("       Run: python tools/train_model.py  to generate predictions.")
        return 0

    print(f"Loaded {len(preds_rows)} prediction rows.")
    print()

    y_true = [int(r["actual_test_failed"]) for r in preds_rows]
    y_pred = [int(r["predicted_label"]) for r in preds_rows]
    y_prob = [float(r["predicted_failure_probability"]) for r in preds_rows]

    pass_cnt = sum(1 for y in y_true if y == 0)
    fail_cnt = sum(1 for y in y_true if y == 1)
    print(f"Test set distribution:")
    print(f"  PASS (0): {pass_cnt}")
    print(f"  FAIL (1): {fail_cnt}")
    print()

    prob_min = min(y_prob)
    prob_max = max(y_prob)
    print(f"Predicted probability range: [{prob_min:.4f}, {prob_max:.4f}]")
    print()

    # Compute metrics
    metrics = compute_metrics(y_true, y_pred, y_prob)

    # Print evaluation report
    print("-" * 60)
    print("Evaluation Results")
    print("-" * 60)
    print(f"  Accuracy:               {metrics.get('accuracy', 'N/A')}")
    print(f"  Precision (FAIL class): {metrics.get('precision_fail', 'N/A')}")
    print(f"  Recall    (FAIL class): {metrics.get('recall_fail', 'N/A')}")
    print(f"  F1-score  (FAIL class): {metrics.get('f1_fail', 'N/A')}")
    print(f"  ROC-AUC:                {metrics.get('roc_auc', 'N/A')}")
    print(f"  PR-AUC:                 {metrics.get('pr_auc', 'N/A')}")
    print()

    cm = metrics.get("confusion_matrix", None)
    if isinstance(cm, list):
        print("  Confusion Matrix:")
        print("                Predicted 0  Predicted 1")
        print(f"  Actual 0:         {cm[0][0]:>5}        {cm[0][1]:>5}")
        print(f"  Actual 1:         {cm[1][0]:>5}        {cm[1][1]:>5}")
        print()
        tn, fp = cm[0][0], cm[0][1]
        fn, tp = cm[1][0], cm[1][1]
        print(f"  True Negatives (correct PASS): {tn}")
        print(f"  False Positives (wrong alarm):  {fp}")
        print(f"  False Negatives (missed FAIL):  {fn}  ← minimize this")
        print(f"  True Positives (caught FAIL):   {tp}")

    print()
    print("Why Recall matters for SmartQA:")
    print("  Failing to detect a test that will fail (False Negative)")
    print("  means a defect goes undetected. Recall for the FAIL class")
    print("  is therefore the most operationally important metric for")
    print("  Phase 7 test prioritization.")

    # Save evaluation report
    report = {
        "model_type": metadata.get("model_type", "unknown"),
        "training_timestamp": metadata.get("training_timestamp", "unknown"),
        "test_rows": len(preds_rows),
        "test_pass_count": pass_cnt,
        "test_fail_count": fail_cnt,
        "probability_range": [prob_min, prob_max],
        "metrics": metrics,
        "note": (
            "With only 1 FAIL in the full dataset and a temporal split, "
            "the test set may contain 0 FAIL rows, making ROC-AUC/PR-AUC undefined. "
            "This is an honest reporting of insufficient historical data."
        ),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(EVAL_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print()
    print(f"[OK] Evaluation report saved to {EVAL_REPORT_FILE}")
    print()
    print("STATUS: EVALUATION COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
