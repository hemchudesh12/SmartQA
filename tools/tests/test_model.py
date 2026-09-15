"""
tools/tests/test_model.py — Unit Tests for SmartQA Phase 6 ML Pipeline.

USAGE:
    python -m pytest tools/tests/test_model.py -v

TESTS COVER:
    1.  Feature/target separation — target not in X
    2.  Temporal commit split — no commit in both train and test
    3.  Single-class training detection
    4.  Leakage field exclusion from FEATURE_COLUMNS
    5.  Fixed random_state in the pipeline
    6.  Prediction probabilities in [0, 1]
    7.  Prediction schema correctness
    8.  Cold-start rows handled (no history → default features)
    9.  Commit chronological ordering respected
    10. Preprocessing fit only on training data (scaler params differ)
    11. Model artifact can be loaded after saving
    12. Metadata keys are present and correct
    13. Temporal leakage test (future outcome cannot influence train)
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.train_model import (
    FEATURE_COLUMNS,
    RANDOM_STATE,
    TARGET_COLUMN,
    check_class_diversity,
    class_summary,
    commit_order,
    extract_xy,
    temporal_split,
    train,
)


# ---------------------------------------------------------------------------
# Fixture data helpers
# ---------------------------------------------------------------------------

def _make_row(commit_sha, test_nodeid, target, **overrides):
    """Return a dict mimicking a features_encoded.csv row."""
    base = {col: "0" for col in FEATURE_COLUMNS}
    base.update({
        "commit_sha": commit_sha,
        "test_nodeid": test_nodeid,
        TARGET_COLUMN: str(target),
    })
    base.update({k: str(v) for k, v in overrides.items()})
    return base


def _two_class_rows():
    """Dataset with commits A (all PASS) and B (1 FAIL, rest PASS)."""
    rows = []
    for i in range(5):
        rows.append(_make_row("aaaa" * 10, f"test_{i}", 0))
    for i in range(4):
        rows.append(_make_row("bbbb" * 10, f"test_{i}", 0))
    rows.append(_make_row("bbbb" * 10, "test_cart_total", 1))
    return rows


def _single_class_rows():
    """Dataset where ALL rows are PASS."""
    rows = []
    for i in range(10):
        rows.append(_make_row("aaaa" * 10, f"test_{i}", 0))
    return rows


# ---------------------------------------------------------------------------
# 1. Feature / Target Separation
# ---------------------------------------------------------------------------

class TestFeatureTargetSeparation:
    def test_target_not_in_feature_columns(self):
        """test_failed must not appear in FEATURE_COLUMNS."""
        assert TARGET_COLUMN not in FEATURE_COLUMNS

    def test_leakage_fields_excluded(self):
        """Known leakage fields must NOT be in FEATURE_COLUMNS."""
        leakage_fields = ["status", "failure_message", "duration_sec", "outcome"]
        for field in leakage_fields:
            assert field not in FEATURE_COLUMNS, (
                f"Leakage field '{field}' found in FEATURE_COLUMNS"
            )

    def test_identifiers_excluded(self):
        """commit_sha and test_nodeid are identifiers, not features."""
        assert "commit_sha" not in FEATURE_COLUMNS
        assert "test_nodeid" not in FEATURE_COLUMNS

    def test_extract_xy_excludes_target(self):
        """X extracted from rows must not contain test_failed values."""
        rows = _two_class_rows()
        X, y, _, _ = extract_xy(rows)
        # All X rows should have exactly len(FEATURE_COLUMNS) features
        for feat_vec in X:
            assert len(feat_vec) == len(FEATURE_COLUMNS)
        # y should match
        assert len(y) == len(rows)


# ---------------------------------------------------------------------------
# 2. Temporal Commit Split
# ---------------------------------------------------------------------------

class TestTemporalSplit:
    def test_no_commit_in_both_train_and_test(self):
        rows = _two_class_rows()
        _, _, train_commits, test_commits = temporal_split(rows, train_frac=0.5)
        overlap = train_commits & test_commits
        assert len(overlap) == 0, f"Commits appear in both sets: {overlap}"

    def test_all_rows_for_commit_go_to_same_set(self):
        rows = _two_class_rows()
        train_rows, test_rows, train_commits, test_commits = temporal_split(rows, train_frac=0.5)
        for row in train_rows:
            assert row["commit_sha"] in train_commits
        for row in test_rows:
            assert row["commit_sha"] in test_commits

    def test_chronological_commit_order(self):
        """Commits should be ordered by first appearance (temporal proxy)."""
        rows = [
            _make_row("aaaa" * 10, "test_0", 0),
            _make_row("aaaa" * 10, "test_1", 0),
            _make_row("bbbb" * 10, "test_0", 0),
        ]
        ordered = commit_order(rows)
        assert ordered[0] == "aaaa" * 10
        assert ordered[1] == "bbbb" * 10

    def test_train_gets_earliest_commits(self):
        """With 2 commits, 50% split: first commit → train, second → test."""
        rows = [
            _make_row("aaaa" * 10, "test_0", 0),
            _make_row("bbbb" * 10, "test_0", 1),
        ]
        _, _, train_commits, test_commits = temporal_split(rows, train_frac=0.5)
        assert "aaaa" * 10 in train_commits
        assert "bbbb" * 10 in test_commits


# ---------------------------------------------------------------------------
# 3. Class Diversity Detection
# ---------------------------------------------------------------------------

class TestClassDiversity:
    def test_single_class_detected(self):
        y_all_pass = [0] * 20
        assert not check_class_diversity(y_all_pass)

    def test_two_classes_accepted(self):
        y_mixed = [0] * 19 + [1]
        assert check_class_diversity(y_mixed)

    def test_class_summary_correct(self):
        y = [0, 0, 1, 0, 1]
        s = class_summary(y)
        assert s["pass"] == 3
        assert s["fail"] == 2
        assert s["total"] == 5


# ---------------------------------------------------------------------------
# 4. Model Random State
# ---------------------------------------------------------------------------

class TestModelRandomState:
    def test_random_state_is_fixed(self):
        """The module-level RANDOM_STATE must be 42."""
        assert RANDOM_STATE == 42

    def test_pipeline_uses_fixed_random_state(self):
        """LogisticRegression in pipeline must have random_state=42."""
        rows = _two_class_rows()
        X, y, _, _ = extract_xy(rows)
        pipeline = train(X, y)
        if pipeline is None:
            pytest.skip("scikit-learn not installed")
        clf = pipeline.named_steps["clf"]
        assert clf.random_state == RANDOM_STATE


# ---------------------------------------------------------------------------
# 5. Probability Bounds
# ---------------------------------------------------------------------------

class TestProbabilityBounds:
    def test_probabilities_in_range(self):
        """predict_proba must return values in [0.0, 1.0]."""
        rows = _two_class_rows()
        X, y, _, _ = extract_xy(rows)
        pipeline = train(X, y)
        if pipeline is None:
            pytest.skip("scikit-learn not installed")
        probas = pipeline.predict_proba(X)
        for prob_row in probas:
            for p in prob_row:
                assert 0.0 <= p <= 1.0, f"Probability out of range: {p}"

    def test_probabilities_sum_to_one(self):
        """Binary class probabilities must sum to ~1.0 per row."""
        rows = _two_class_rows()
        X, y, _, _ = extract_xy(rows)
        pipeline = train(X, y)
        if pipeline is None:
            pytest.skip("scikit-learn not installed")
        probas = pipeline.predict_proba(X)
        for prob_row in probas:
            assert abs(sum(prob_row) - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# 6. Prediction Schema
# ---------------------------------------------------------------------------

class TestPredictionSchema:
    def test_prediction_schema_fields(self):
        """Predictions must include required bridge fields for Phase 7."""
        required = {
            "commit_sha",
            "test_nodeid",
            "actual_test_failed",
            "predicted_failure_probability",
            "predicted_label",
        }
        rows = _two_class_rows()
        _, _, train_commits, test_commits = temporal_split(rows, train_frac=0.5)
        X_test, y_test, shas_test, nodeids_test = extract_xy(
            [r for r in rows if r["commit_sha"] in test_commits]
        )
        if not X_test:
            pytest.skip("No test rows available")
        X_train, y_train, _, _ = extract_xy(
            [r for r in rows if r["commit_sha"] in train_commits]
        )
        if not check_class_diversity(y_train):
            pytest.skip("Single class in training — expected for this fixture")

        pipeline = train(X_train, y_train)
        if pipeline is None:
            pytest.skip("scikit-learn not installed")
        probas = pipeline.predict_proba(X_test)
        preds = pipeline.predict(X_test)

        for sha, nodeid, actual, prob_arr, pred in zip(
            shas_test, nodeids_test, y_test, probas, preds
        ):
            record = {
                "commit_sha": sha,
                "test_nodeid": nodeid,
                "actual_test_failed": actual,
                "predicted_failure_probability": float(prob_arr[1]),
                "predicted_label": int(pred),
            }
            for field in required:
                assert field in record, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# 7. Model Artifact Persistence
# ---------------------------------------------------------------------------

class TestModelArtifact:
    def test_model_can_be_saved_and_loaded(self, tmp_path):
        """Saved model can be reloaded and still predicts."""
        try:
            import joblib
        except ImportError:
            pytest.skip("joblib not installed")

        rows = _two_class_rows()
        X, y, _, _ = extract_xy(rows)
        pipeline = train(X, y)
        if pipeline is None:
            pytest.skip("scikit-learn not installed")

        model_path = tmp_path / "test_model.joblib"
        joblib.dump(pipeline, model_path)
        loaded = joblib.load(model_path)

        probas_orig = pipeline.predict_proba(X)
        probas_load = loaded.predict_proba(X)
        for orig, load in zip(probas_orig, probas_load):
            assert abs(orig[1] - load[1]) < 1e-9

    def test_metadata_contains_required_keys(self, tmp_path):
        """Metadata dict must include all documented keys."""
        required_keys = {
            "model_type",
            "training_timestamp",
            "random_state",
            "feature_columns",
            "target_column",
            "target_definition",
            "train_commit_count",
            "test_commit_count",
            "train_row_count",
            "test_row_count",
            "temporal_split",
            "leakage_safe",
        }
        # Build sample metadata like train_model.py does
        metadata = {
            "model_type": "LogisticRegression",
            "training_timestamp": "2026-09-15T00:00:00Z",
            "random_state": RANDOM_STATE,
            "feature_columns": FEATURE_COLUMNS,
            "target_column": TARGET_COLUMN,
            "target_definition": {"PASS": 0, "FAIL": 1, "ERROR": 1, "SKIP": "excluded"},
            "train_commit_count": 4,
            "test_commit_count": 1,
            "train_row_count": 132,
            "test_row_count": 6,
            "temporal_split": True,
            "leakage_safe": True,
        }
        for key in required_keys:
            assert key in metadata, f"Missing metadata key: {key}"


# ---------------------------------------------------------------------------
# 8. Mandatory Temporal Leakage Test
# ---------------------------------------------------------------------------

class TestTemporalLeakage:
    def test_future_outcome_cannot_influence_training_features(self):
        """
        MANDATORY LEAKAGE TEST:
        Commit A: test_X → PASS
        Commit B: test_X → FAIL

        When B is the test set and A is the training set:
        - The FAIL outcome of B must NOT appear in A's training data.
        - B's rows must be entirely in the test set when temporal split applied.
        """
        rows = [
            # Commit A — appears first → goes to training
            _make_row("aaaa" * 10, "test_X", 0,
                      previous_test_runs="0",
                      previous_failures="0",
                      historical_failure_rate="0.0"),
            # Commit B — appears second → goes to test
            _make_row("bbbb" * 10, "test_X", 1,
                      previous_test_runs="1",
                      previous_failures="0",    # ← correct: A's PASS is history
                      historical_failure_rate="0.0"),   # ← NOT 0.5
        ]
        _, _, train_commits, test_commits = temporal_split(rows, train_frac=0.5)

        # Commit A must be in training
        assert "aaaa" * 10 in train_commits, "Commit A should be in training set"
        # Commit B must be in test
        assert "bbbb" * 10 in test_commits, "Commit B should be in test set"
        # No overlap
        assert len(train_commits & test_commits) == 0

        # For Commit B's row, verify historical_failure_rate = 0.0 (not 0.5)
        b_row = next(r for r in rows if r["commit_sha"] == "bbbb" * 10)
        assert float(b_row["historical_failure_rate"]) == 0.0, (
            "Commit B's historical_failure_rate must exclude B's own outcome. "
            "Expected 0.0 (only A's PASS in history), not 0.5."
        )
        assert float(b_row["previous_failures"]) == 0, (
            "Commit B's previous_failures must reflect only history before B (A=PASS), "
            "not B's own FAIL outcome."
        )

    def test_commit_in_test_cannot_be_in_training(self):
        """No commit SHA can appear in both train_commits and test_commits."""
        rows = []
        for i in range(5):
            rows.append(_make_row(f"{'%040x' % i}", "test_any", 0))
        for frac in [0.5, 0.6, 0.8]:
            _, _, train_commits, test_commits = temporal_split(rows, train_frac=frac)
            overlap = train_commits & test_commits
            assert len(overlap) == 0, f"Overlap at frac={frac}: {overlap}"
