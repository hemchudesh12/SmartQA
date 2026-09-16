"""
dashboard/app.py — SmartQA Phase 8 Dashboard Server.

USAGE:
    python dashboard/app.py

Starts a local Flask server at http://127.0.0.1:5001/

This dashboard is a READ-ONLY interface into SmartQA-generated artifacts.
It does NOT:
    - Modify any data files
    - Connect to the main SmartQA Demo Store application (port 5000)
    - Expose secrets or credentials
    - Allow arbitrary file access

PORT: 5001 (avoids conflict with main app on port 5000)

DATA SOURCES (read-only):
    data/commits.jsonl
    data/test_results.jsonl
    data/predictions.csv
    data/prioritized_tests.csv
    data/prioritization_evaluation.json
    data/evaluation_report.json
    models/model_metadata.json

The dashboard reads the LATEST generated artifacts each time a page is loaded.
To update the dashboard data, regenerate the artifacts and refresh the browser.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from flask import Flask, render_template, jsonify

from dashboard.data_loader import (
    compute_evaluation_display,
    compute_historical_trend,
    compute_overview_stats,
    compute_prioritization_comparison,
    compute_risk_distribution,
    compute_risk_table,
    compute_latest_run_results,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__, template_folder="templates")
# Secret key is for Flask session management only (not used functionally)
app.config["SECRET_KEY"] = "smartqa-dashboard-readonly-phase8"
app.config["DEBUG"] = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Main dashboard page — loads all sections."""
    overview = compute_overview_stats()
    risk_table = compute_risk_table()
    risk_distribution = compute_risk_distribution()
    latest_run = compute_latest_run_results()
    historical_trend = compute_historical_trend()
    prioritization = compute_prioritization_comparison()
    evaluation = compute_evaluation_display()

    return render_template(
        "dashboard.html",
        overview=overview,
        risk_table=risk_table,
        risk_distribution=risk_distribution,
        latest_run=latest_run,
        historical_trend=historical_trend,
        prioritization=prioritization,
        evaluation=evaluation,
    )


@app.route("/api/overview")
def api_overview():
    """JSON API — overview statistics."""
    return jsonify(compute_overview_stats())


@app.route("/api/risk")
def api_risk():
    """JSON API — test risk table."""
    return jsonify(compute_risk_table())


@app.route("/api/risk-distribution")
def api_risk_distribution():
    """JSON API — risk tier distribution."""
    return jsonify(compute_risk_distribution())


@app.route("/api/latest-run")
def api_latest_run():
    """JSON API — latest test execution results."""
    return jsonify(compute_latest_run_results())


@app.route("/api/trend")
def api_trend():
    """JSON API — historical trend data."""
    return jsonify(compute_historical_trend())


@app.route("/api/prioritization")
def api_prioritization():
    """JSON API — baseline vs SmartQA ordering comparison."""
    return jsonify(compute_prioritization_comparison())


@app.route("/api/evaluation")
def api_evaluation():
    """JSON API — evaluation metrics."""
    return jsonify(compute_evaluation_display())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 55)
    print("SmartQA Phase 8 Dashboard")
    print("=" * 55)
    print()
    print("Dashboard URL:   http://127.0.0.1:5001/")
    print()
    print("Data sources (read-only):")
    data_sources = [
        "data/commits.jsonl",
        "data/test_results.jsonl",
        "data/predictions.csv",
        "data/prioritized_tests.csv",
        "data/prioritization_evaluation.json",
        "data/evaluation_report.json",
        "models/model_metadata.json",
    ]
    for src in data_sources:
        path = _PROJECT_ROOT / src
        status = "[found]" if path.exists() else "[not yet generated]"
        print(f"  {src:<45} {status}")
    print()
    print("To generate missing files:")
    print("  python tools/build_features.py")
    print("  python tools/train_model.py")
    print("  python tools/evaluate_model.py")
    print("  python tools/prioritize_tests.py")
    print("  python tools/evaluate_prioritization.py")
    print()
    print("Press Ctrl+C to stop the dashboard.")
    print()

    app.run(host="127.0.0.1", port=5001, debug=False)
