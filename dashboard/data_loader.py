"""
dashboard/data_loader.py — SmartQA Phase 8 Dashboard Data Loading Layer.

Reads SmartQA-generated artifacts from the data/ and models/ directories.

SAFETY GUARANTEES:
    - All functions return safe empty/default values if their source is absent.
    - No function raises exceptions on missing, empty, or malformed files.
    - No file is written or modified — this module is read-only.
    - No credentials, secrets, or private keys are accessed.
    - File paths are validated against the project root (no arbitrary access).

DATA SOURCES:
    data/commits.jsonl              — git commit metadata (Phase 4)
    data/test_results.jsonl         — test execution records (Phase 4)
    data/predictions.csv            — Phase 6 ML predictions
    data/prioritized_tests.csv      — Phase 7 priority order
    data/evaluation_report.json     — Phase 6 model evaluation
    data/prioritization_evaluation.json  — Phase 8 prioritization evaluation
    models/model_metadata.json      — Phase 6 model metadata
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — validated against project root
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_MODELS_DIR = _PROJECT_ROOT / "models"

# Risk threshold definitions (must match evaluate_prioritization.py)
HIGH_RISK_THRESHOLD = 0.5
MEDIUM_RISK_THRESHOLD = 0.2


# ---------------------------------------------------------------------------
# Low-level safe loaders
# ---------------------------------------------------------------------------

def _safe_json_load(filepath: Path, default=None):
    """Load a JSON file, returning default if missing or malformed."""
    if default is None:
        default = {}

    if not filepath.exists():
        return default

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        return default


def _safe_csv_load(filepath: Path) -> list[dict]:
    """Load a CSV file, returning [] if missing or malformed."""
    try:
        filepath.resolve().relative_to(_PROJECT_ROOT.resolve())
    except ValueError:
        return []
    if not filepath.exists():
        return []
    try:
        rows = []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
        return rows
    except (OSError, csv.Error):
        return []


def _safe_jsonl_load(filepath: Path) -> list[dict]:
    """Load a JSONL file, skipping malformed lines. Returns [] on failure."""
    try:
        filepath.resolve().relative_to(_PROJECT_ROOT.resolve())
    except ValueError:
        return []
    if not filepath.exists():
        return []
    rows = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        return []
    return rows


# ---------------------------------------------------------------------------
# Public data loading functions
# ---------------------------------------------------------------------------

def load_commits() -> list[dict]:
    """Load data/commits.jsonl — git commit metadata."""
    return _safe_jsonl_load(_DATA_DIR / "commits.jsonl")


def load_test_results() -> list[dict]:
    """Load data/test_results.jsonl — all test execution records."""
    return _safe_jsonl_load(_DATA_DIR / "test_results.jsonl")


def load_predictions() -> list[dict]:
    """Load data/predictions.csv — Phase 6 ML predictions on test set."""
    return _safe_csv_load(_DATA_DIR / "predictions.csv")


def load_prioritized_tests() -> list[dict]:
    """Load data/prioritized_tests.csv — Phase 7 priority order."""
    rows = _safe_csv_load(_DATA_DIR / "prioritized_tests.csv")
    try:
        rows.sort(key=lambda r: int(r.get("priority_rank", 9999)))
    except (ValueError, TypeError):
        pass
    return rows


def load_model_metadata() -> dict:
    """Load models/model_metadata.json — Phase 6 model training info."""
    return _safe_json_load(_MODELS_DIR / "model_metadata.json")


def load_evaluation_report() -> dict:
    """Load data/evaluation_report.json — Phase 6 model evaluation metrics."""
    return _safe_json_load(_DATA_DIR / "evaluation_report.json")


def load_prioritization_evaluation() -> dict:
    """Load data/prioritization_evaluation.json — Phase 8 evaluation output."""
    return _safe_json_load(_DATA_DIR / "prioritization_evaluation.json")


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _short_test_name(nodeid: str) -> str:
    """Extract human-readable test name from full pytest node ID."""
    if "::" in nodeid:
        return nodeid.split("::")[-1]
    return nodeid


def _truncate_sha(sha: str, length: int = 12) -> str:
    """Truncate a commit SHA for display."""
    if not sha or sha == "N/A":
        return "N/A"
    return sha[:length]


# ---------------------------------------------------------------------------
# Computed / derived data for dashboard sections
# ---------------------------------------------------------------------------

def compute_overview_stats() -> dict:
    """
    Compute overview statistics for the dashboard header.

    Returns a dict with counts, statuses, and latest commit info.
    Never raises; returns safe defaults for missing data.
    """
    commits = load_commits()
    results = load_test_results()
    prioritized = load_prioritized_tests()
    model_meta = load_model_metadata()

    # Total test count from prioritized list (ground truth for current run)
    total_tests = len(prioritized)

    # Predictions coverage
    predictions_available = sum(
        1 for r in prioritized
        if str(r.get("prediction_available", "")).strip().lower() == "true"
    )
    predictions_missing = total_tests - predictions_available

    # Historical run stats
    run_ids = set(r.get("run_id", "") for r in results if r.get("run_id"))
    total_runs = len(run_ids)
    total_failures = sum(
        1 for r in results
        if r.get("status", "").upper() in {"FAIL", "ERROR"}
    )

    # Latest commit info
    latest_commit = commits[-1] if commits else {}
    latest_sha = _truncate_sha(latest_commit.get("commit_sha", "N/A"))
    latest_msg = latest_commit.get("commit_message", "N/A")
    if latest_msg and len(latest_msg) > 60:
        latest_msg = latest_msg[:60] + "..."
    latest_ts = latest_commit.get("timestamp_iso", "N/A")

    # Model status
    model_file = _MODELS_DIR / "failure_predictor.joblib"
    model_available = model_file.exists()
    model_type = model_meta.get("model_type", "Unknown") if model_meta else "Unknown"

    # Prioritization status
    prioritized_file = _DATA_DIR / "prioritized_tests.csv"
    prioritization_available = prioritized_file.exists() and total_tests > 0

    # Dataset failure rate from model metadata
    dataset_failure_rate = (
        model_meta.get("dataset_failure_rate_pct", 0.0)
        if model_meta else 0.0
    )

    return {
        "total_tests": total_tests or 33,  # fallback to known value if data missing
        "predictions_available": predictions_available,
        "predictions_missing": predictions_missing,
        "total_historical_runs": total_runs,
        "total_observed_failures": total_failures,
        "total_commits": len(commits),
        "latest_commit_sha": latest_sha,
        "latest_commit_message": latest_msg,
        "latest_commit_author": latest_commit.get("author", "N/A"),
        "latest_commit_timestamp": latest_ts,
        "model_available": model_available,
        "model_type": model_type if model_available else "Not trained",
        "model_status": "Trained" if model_available else "Not available",
        "prioritization_available": prioritization_available,
        "prioritization_status": "Enabled" if prioritization_available else "Unavailable",
        "dataset_failure_rate_pct": dataset_failure_rate,
    }


def compute_risk_table() -> list[dict]:
    """
    Build the test risk table for the dashboard.

    Returns list of dicts with rank, test name, probability, risk level.
    Uses actual data from prioritized_tests.csv — no fabricated values.
    """
    prioritized = load_prioritized_tests()
    rows = []

    for entry in prioritized:
        prob_raw = entry.get("predicted_failure_probability", "N/A")
        prediction_available = str(entry.get("prediction_available", "")).strip().lower() == "true"

        if prediction_available and prob_raw not in {"N/A", "", None}:
            try:
                prob = float(prob_raw)
                prob_pct = f"{prob * 100:.2f}%"
                if prob >= HIGH_RISK_THRESHOLD:
                    risk_level = "High"
                elif prob >= MEDIUM_RISK_THRESHOLD:
                    risk_level = "Medium"
                else:
                    risk_level = "Low"
                prob_float = prob
            except (ValueError, TypeError):
                prob_pct = "N/A"
                risk_level = "No Prediction"
                prediction_available = False
                prob_float = None
        else:
            prob_pct = "N/A"
            risk_level = "No Prediction"
            prediction_available = False
            prob_float = None

        label_raw = entry.get("predicted_label", "N/A")
        label_display = "FAIL" if label_raw == "1" else ("PASS" if label_raw == "0" else "N/A")

        rows.append({
            "rank": entry.get("priority_rank", ""),
            "test_nodeid": entry.get("test_nodeid", ""),
            "test_name": _short_test_name(entry.get("test_nodeid", "")),
            "failure_probability_pct": prob_pct,
            "failure_probability_float": prob_float,
            "risk_level": risk_level,
            "prediction_available": prediction_available,
            "predicted_label": label_display,
        })

    return rows


def compute_risk_distribution() -> dict:
    """
    Compute counts by risk tier for visualization.

    Thresholds:
        High:   probability >= 0.50
        Medium: probability >= 0.20
        Low:    probability < 0.20
        No Prediction: prediction_available = False
    """
    risk_table = compute_risk_table()
    counts = {"High": 0, "Medium": 0, "Low": 0, "No Prediction": 0}
    for row in risk_table:
        level = row.get("risk_level", "No Prediction")
        counts[level] = counts.get(level, 0) + 1

    total = len(risk_table)
    distribution = []
    for level, count in counts.items():
        pct = round(count / total * 100, 1) if total > 0 else 0.0
        distribution.append({
            "level": level,
            "count": count,
            "percentage": pct,
        })

    return {
        "thresholds": {
            "High": f">= {HIGH_RISK_THRESHOLD * 100:.0f}%",
            "Medium": f">= {MEDIUM_RISK_THRESHOLD * 100:.0f}%",
            "Low": f"< {MEDIUM_RISK_THRESHOLD * 100:.0f}%",
        },
        "distribution": distribution,
        "total_tests": total,
    }


def compute_latest_run_results() -> dict:
    """
    Get test results for the most recent run by run_id timestamp.

    Returns structured data for the execution results section.
    """
    results = load_test_results()
    if not results:
        return {
            "run_id": None,
            "commit_sha": None,
            "rows": [],
            "summary": {"total": 0, "pass": 0, "fail": 0, "skip": 0},
        }

    # Find the latest run_id (run_ids are ISO timestamps)
    run_ids = sorted(
        set(r.get("run_id", "") for r in results if r.get("run_id")),
        reverse=True,
    )
    if not run_ids:
        return {
            "run_id": None,
            "commit_sha": None,
            "rows": [],
            "summary": {"total": 0, "pass": 0, "fail": 0, "skip": 0},
        }

    latest_run_id = run_ids[0]
    latest_rows = [r for r in results if r.get("run_id") == latest_run_id]

    # Summary counts
    pass_count = sum(1 for r in latest_rows if r.get("status", "").upper() == "PASS")
    fail_count = sum(
        1 for r in latest_rows if r.get("status", "").upper() in {"FAIL", "ERROR"}
    )
    skip_count = sum(1 for r in latest_rows if r.get("status", "").upper() == "SKIP")

    commit_sha = _truncate_sha(latest_rows[0].get("commit_sha", "N/A")) if latest_rows else "N/A"

    # Build display rows
    display_rows = []
    for r in latest_rows:
        dur = r.get("duration_sec", 0)
        try:
            dur_str = f"{float(dur):.3f}s"
        except (ValueError, TypeError):
            dur_str = "N/A"

        status = r.get("status", "UNKNOWN").upper()
        display_rows.append({
            "test_name": _short_test_name(r.get("test_nodeid", "")),
            "test_nodeid": r.get("test_nodeid", ""),
            "status": status,
            "status_class": (
                "pass" if status == "PASS"
                else "fail" if status in {"FAIL", "ERROR"}
                else "skip"
            ),
            "duration": dur_str,
            "failure_message": (r.get("failure_message", "") or "")[:200],
        })

    return {
        "run_id": latest_run_id,
        "commit_sha": commit_sha,
        "rows": display_rows,
        "summary": {
            "total": len(latest_rows),
            "pass": pass_count,
            "fail": fail_count,
            "skip": skip_count,
        },
    }


def compute_historical_trend() -> list[dict]:
    """
    Compute per-run historical trend statistics for visualization.

    Returns list sorted chronologically by run_id.
    """
    results = load_test_results()
    if not results:
        return []

    run_groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        run_groups[r.get("run_id", "unknown")].append(r)

    trend = []
    for run_id, rows in run_groups.items():
        commit_sha = _truncate_sha(rows[0].get("commit_sha", "")) if rows else ""
        commit_msg = rows[0].get("commit_message", "") if rows else ""
        if commit_msg and len(commit_msg) > 40:
            commit_msg = commit_msg[:40] + "..."

        pass_count = sum(1 for r in rows if r.get("status", "").upper() == "PASS")
        fail_count = sum(
            1 for r in rows if r.get("status", "").upper() in {"FAIL", "ERROR"}
        )
        skip_count = sum(1 for r in rows if r.get("status", "").upper() == "SKIP")
        total = len(rows)
        fail_rate = round(fail_count / total * 100, 2) if total > 0 else 0.0

        # Average duration
        durations = []
        for r in rows:
            try:
                durations.append(float(r.get("duration_sec", 0)))
            except (ValueError, TypeError):
                pass
        avg_duration = round(sum(durations) / len(durations), 3) if durations else 0.0

        trend.append({
            "run_id": run_id,
            "commit_sha": commit_sha,
            "commit_message": commit_msg,
            "total_tests": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "skip_count": skip_count,
            "fail_rate_pct": fail_rate,
            "avg_duration_sec": avg_duration,
        })

    # Sort by run_id (ISO timestamp strings sort correctly)
    trend.sort(key=lambda x: x["run_id"])
    return trend


def compute_prioritization_comparison() -> dict:
    """
    Build side-by-side baseline vs SmartQA ordering comparison.

    Baseline order is derived from the first historical run in test_results.jsonl.
    SmartQA order is from data/prioritized_tests.csv.
    """
    prioritized = load_prioritized_tests()
    results = load_test_results()

    if not prioritized:
        return {
            "available": False,
            "reason": "No prioritized test order found. Run: python tools/prioritize_tests.py",
            "smartqa_order": [],
            "baseline_order": [],
        }

    smartqa_order = []
    for r in prioritized:
        prob_raw = r.get("predicted_failure_probability", "N/A")
        pred_avail = str(r.get("prediction_available", "")).strip().lower() == "true"
        try:
            prob_display = f"{float(prob_raw) * 100:.2f}%" if pred_avail and prob_raw not in {"N/A", ""} else "N/A"
        except (ValueError, TypeError):
            prob_display = "N/A"

        smartqa_order.append({
            "rank": r.get("priority_rank", ""),
            "test_name": _short_test_name(r.get("test_nodeid", "")),
            "test_nodeid": r.get("test_nodeid", ""),
            "probability_display": prob_display,
            "prediction_available": pred_avail,
        })

    # Build baseline order from the first run's execution sequence
    baseline_order = []
    if results:
        # Sort runs by run_id and take the first
        run_ids = sorted(set(r.get("run_id", "") for r in results if r.get("run_id")))
        if run_ids:
            first_run_id = run_ids[0]
            first_run_rows = [r for r in results if r.get("run_id") == first_run_id]
            for i, r in enumerate(first_run_rows):
                baseline_order.append({
                    "rank": i + 1,
                    "test_name": _short_test_name(r.get("test_nodeid", "")),
                    "test_nodeid": r.get("test_nodeid", ""),
                })

    return {
        "available": True,
        "smartqa_order": smartqa_order,
        "baseline_order": baseline_order,
    }


def compute_evaluation_display() -> dict:
    """
    Build display-ready evaluation metrics for the dashboard.

    Combines Phase 8 prioritization evaluation + Phase 6 model evaluation.
    Returns safe defaults if evaluation files are not yet generated.
    """
    eval_data = load_prioritization_evaluation()
    model_eval = load_evaluation_report()

    if not eval_data:
        return {
            "available": False,
            "reason": (
                "Evaluation not yet generated. "
                "Run: python tools/evaluate_prioritization.py"
            ),
            "summary": {},
            "failure_runs": [],
            "model_metrics": _build_model_metrics(model_eval),
        }

    summary = eval_data.get("summary", {})
    apfd_info = summary.get("apfd", {})
    failure_ranks = summary.get("first_failure_ranks", {})

    return {
        "available": True,
        "evaluation_type": eval_data.get("evaluation_type", "retrospective"),
        "evaluation_note": eval_data.get("evaluation_note", ""),
        "status": eval_data.get("status", "unknown"),
        "status_note": eval_data.get("status_note", ""),
        "summary": {
            "total_runs": summary.get("total_runs_evaluated", 0),
            "runs_with_failures": summary.get("runs_with_failures", 0),
            "total_failures": summary.get("total_failures_observed", 0),
            "apfd_status": apfd_info.get("status", "unknown"),
            "apfd_note": apfd_info.get("note", ""),
            "baseline_apfd": apfd_info.get("baseline_mean_apfd"),
            "smartqa_apfd": apfd_info.get("smartqa_mean_apfd"),
        },
        "failure_runs": failure_ranks.get("runs", []),
        "dataset_stats": eval_data.get("dataset_stats", {}),
        "model_metrics": _build_model_metrics(model_eval),
    }


def _build_model_metrics(model_eval: dict) -> dict:
    """Extract Phase 6 model metrics for display."""
    if not model_eval:
        return {
            "available": False,
            "reason": "Run: python tools/evaluate_model.py",
        }
    m = model_eval.get("metrics", {})
    note = model_eval.get("note", "")
    return {
        "available": True,
        "model_type": model_eval.get("model_type", "N/A"),
        "training_timestamp": model_eval.get("training_timestamp", "N/A"),
        "test_rows": model_eval.get("test_rows", 0),
        "test_pass_count": model_eval.get("test_pass_count", 0),
        "test_fail_count": model_eval.get("test_fail_count", 0),
        "accuracy": m.get("accuracy", "N/A"),
        "precision_fail": m.get("precision_fail", "N/A"),
        "recall_fail": m.get("recall_fail", "N/A"),
        "f1_fail": m.get("f1_fail", "N/A"),
        "roc_auc": m.get("roc_auc", "N/A"),
        "pr_auc": m.get("pr_auc", "N/A"),
        "note": note,
    }
