"""
tools/tests/test_features.py — Unit Tests for SmartQA Phase 5 Feature Engineering.

USAGE:
    python -m pytest tools/tests/test_features.py -v
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.build_features import (
    build_features,
    extract_commit_features,
    extract_interaction_features,
    extract_test_features,
)


def test_target_generation_and_skip_handling():
    """Verify target generation: PASS=0, FAIL=1, ERROR=1, SKIP=excluded."""
    sample_rows = [
        {
            "commit_sha": "a" * 40,
            "run_id": "run_1",
            "test_nodeid": "test_auth.py::test_login",
            "test_file": "automation/tests/test_auth.py",
            "test_name": "test_login",
            "status": "PASS",
            "duration_sec": 1.5,
            "run_timestamp_iso": "2026-09-01T10:00:00Z",
        },
        {
            "commit_sha": "a" * 40,
            "run_id": "run_1",
            "test_nodeid": "test_auth.py::test_logout",
            "test_file": "automation/tests/test_auth.py",
            "test_name": "test_logout",
            "status": "FAIL",
            "duration_sec": 2.0,
            "run_timestamp_iso": "2026-09-01T10:00:00Z",
        },
        {
            "commit_sha": "a" * 40,
            "run_id": "run_1",
            "test_nodeid": "test_auth.py::test_reset",
            "test_file": "automation/tests/test_auth.py",
            "test_name": "test_reset",
            "status": "ERROR",
            "duration_sec": 0.5,
            "run_timestamp_iso": "2026-09-01T10:00:00Z",
        },
        {
            "commit_sha": "a" * 40,
            "run_id": "run_1",
            "test_nodeid": "test_auth.py::test_skip_feature",
            "test_file": "automation/tests/test_auth.py",
            "test_name": "test_skip_feature",
            "status": "SKIP",
            "duration_sec": 0.0,
            "run_timestamp_iso": "2026-09-01T10:00:00Z",
        },
    ]

    feature_rows, encoded_rows = build_features(sample_rows)

    # SKIP test should be excluded
    assert len(feature_rows) == 3

    nodeid_to_target = {r["test_nodeid"]: r["test_failed"] for r in feature_rows}
    assert nodeid_to_target["test_auth.py::test_login"] == 0
    assert nodeid_to_target["test_auth.py::test_logout"] == 1
    assert nodeid_to_target["test_auth.py::test_reset"] == 1


def test_mandatory_data_leakage_prevention():
    """
    MANDATORY LEAKAGE TEST:
    Prove that current test outcome (e.g. FAIL on Commit B) does NOT influence historical features for Commit B.
    """
    rows = [
        # Commit A: test_X PASS
        {
            "commit_sha": "1111111111111111111111111111111111111111",
            "run_id": "run_1",
            "test_nodeid": "test_suite.py::test_X",
            "test_file": "automation/tests/test_suite.py",
            "test_name": "test_X",
            "status": "PASS",
            "duration_sec": 1.0,
            "run_timestamp_iso": "2026-09-01T10:00:00Z",
        },
        # Commit B: test_X FAIL
        {
            "commit_sha": "2222222222222222222222222222222222222222",
            "run_id": "run_2",
            "test_nodeid": "test_suite.py::test_X",
            "test_file": "automation/tests/test_suite.py",
            "test_name": "test_X",
            "status": "FAIL",
            "duration_sec": 1.2,
            "run_timestamp_iso": "2026-09-02T10:00:00Z",
        },
    ]

    feature_rows, _ = build_features(rows)
    assert len(feature_rows) == 2

    row_commit_a = feature_rows[0]
    row_commit_b = feature_rows[1]

    # For Commit A (Cold start):
    assert row_commit_a["previous_test_runs"] == 0
    assert row_commit_a["previous_failures"] == 0
    assert row_commit_a["historical_failure_rate"] == 0.0

    # For Commit B:
    # Must use ONLY history before Commit B (1 pass, 0 fail)
    assert row_commit_b["previous_test_runs"] == 1
    assert row_commit_b["previous_failures"] == 0
    assert row_commit_b["historical_failure_rate"] == 0.0  # NOT 0.5!
    assert row_commit_b["test_failed"] == 1


def test_chronological_ordering_and_history():
    """Verify feature calculation across 3 runs of same test."""
    rows = [
        # Run 1 (Cold start): PASS
        {
            "commit_sha": "a" * 40,
            "run_id": "run_1",
            "test_nodeid": "test_cart.py::test_add",
            "status": "PASS",
            "duration_sec": 2.0,
            "run_timestamp_iso": "2026-09-01T10:00:00Z",
        },
        # Run 2: FAIL
        {
            "commit_sha": "b" * 40,
            "run_id": "run_2",
            "test_nodeid": "test_cart.py::test_add",
            "status": "FAIL",
            "duration_sec": 4.0,
            "run_timestamp_iso": "2026-09-02T10:00:00Z",
        },
        # Run 3: PASS
        {
            "commit_sha": "c" * 40,
            "run_id": "run_3",
            "test_nodeid": "test_cart.py::test_add",
            "status": "PASS",
            "duration_sec": 3.0,
            "run_timestamp_iso": "2026-09-03T10:00:00Z",
        },
    ]

    feature_rows, _ = build_features(rows)
    assert len(feature_rows) == 3

    # Run 1
    r1 = feature_rows[0]
    assert r1["previous_test_runs"] == 0
    assert r1["historical_failure_rate"] == 0.0

    # Run 2
    r2 = feature_rows[1]
    assert r2["previous_test_runs"] == 1
    assert r2["previous_passes"] == 1
    assert r2["previous_failures"] == 0
    assert r2["historical_failure_rate"] == 0.0

    # Run 3
    r3 = feature_rows[2]
    assert r3["previous_test_runs"] == 2
    assert r3["previous_passes"] == 1
    assert r3["previous_failures"] == 1
    assert r3["historical_failure_rate"] == 0.5
    assert r3["average_previous_duration"] == 3.0  # (2.0 + 4.0)/2


def test_commit_and_interaction_features():
    """Verify commit level and commit x test interaction feature extraction."""
    row = {
        "commit_message": "fix: resolve login bug in auth system",
        "lines_added": 15,
        "lines_deleted": 5,
        "changed_files": "app/auth/routes.py,automation/tests/test_auth.py",
        "changed_file_count": 2,
    }

    commit_feats = extract_commit_features(row)
    assert commit_feats["lines_added"] == 15
    assert commit_feats["lines_deleted"] == 5
    assert commit_feats["total_lines_changed"] == 20
    assert commit_feats["has_fix_keyword"] == 1
    assert commit_feats["has_bug_keyword"] == 1
    assert commit_feats["changed_python_file_count"] == 2
    assert commit_feats["changed_app_file_count"] == 1

    test_feats = {
        "test_file": "automation/tests/test_auth.py",
        "test_name": "test_login",
    }

    interaction_feats = extract_interaction_features(row, commit_feats, test_feats, hist_failure_rate=0.25)
    assert interaction_feats["test_file_changed"] == 1
    assert interaction_feats["test_area_changed"] == 1
    assert interaction_feats["commit_size_x_hist_failure_rate"] == 5.0  # 20 * 0.25
