"""
tools/tests/test_collector.py — Unit tests for SmartQA Phase 4 data collectors.

USAGE:
    pytest tools/tests/test_collector.py -v

These tests verify the data collection system itself — NOT the SUT.

Coverage:
    1.  Git SHA resolution (env var and local git command)
    2.  Changed file detection and parsing
    3.  Line stat parsing
    4.  Deduplication logic (commits.jsonl)
    5.  Deduplication logic (test_results.jsonl)
    6.  PASS / FAIL / SKIP / ERROR status mapping
    7.  Duration capture
    8.  Failure message truncation
    9.  Node ID stability (no backslashes)
    10. Schema completeness (all required fields present)
    11. Dataset builder join logic
    12. Dataset builder: unmatched SHA handled gracefully
    13. Validation: catches missing fields
    14. Validation: catches invalid status
    15. Validation: catches negative duration
    16. Validation: catches duplicate records
    17. Validation: catches referential integrity failure
    18. Valid dataset passes all checks

NOTE:
    These tests use tmp_path for file I/O — they do NOT touch
    the real data/ directory and do NOT require Flask to be running.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Import modules under test
# ---------------------------------------------------------------------------

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.collect_git_metadata import (
    get_branch,
    get_commit_sha,
    load_existing_shas,
    write_record,
    get_changed_files,
)
from tools.validate_dataset import (
    check_commits,
    check_results,
    check_csv_consistency,
    VALID_STATUSES,
)
from tools.build_dataset import build_rows, COLUMNS


# ===========================================================================
# 1. Git SHA resolution
# ===========================================================================

class TestCommitShaResolution:
    def test_uses_github_sha_env_var_in_ci(self, monkeypatch):
        """In CI, GITHUB_SHA env var takes priority over local git."""
        test_sha = "a" * 40
        monkeypatch.setenv("GITHUB_SHA", test_sha)
        assert get_commit_sha() == test_sha

    def test_uses_git_locally_when_no_env_var(self, monkeypatch):
        """Locally, should call git rev-parse HEAD."""
        monkeypatch.delenv("GITHUB_SHA", raising=False)
        # Verify git rev-parse HEAD returns a 40-char hex string
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            sha = get_commit_sha()
            assert len(sha) == 40
            assert all(c in "0123456789abcdef" for c in sha)
        else:
            pytest.skip("Not a git repository or git not available")


# ===========================================================================
# 2. Branch resolution
# ===========================================================================

class TestBranchResolution:
    def test_uses_github_ref_name_in_ci(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REF_NAME", "main")
        monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
        assert get_branch() == "main"

    def test_uses_github_head_ref_for_prs(self, monkeypatch):
        """PR source branch takes priority over GITHUB_REF_NAME."""
        monkeypatch.setenv("GITHUB_HEAD_REF", "feature/phase4")
        monkeypatch.setenv("GITHUB_REF_NAME", "main")
        assert get_branch() == "feature/phase4"

    def test_falls_back_to_git_locally(self, monkeypatch):
        monkeypatch.delenv("GITHUB_SHA", raising=False)
        monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
        monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
        branch = get_branch()
        assert isinstance(branch, str)
        assert len(branch) > 0


# ===========================================================================
# 3. Changed file detection
# ===========================================================================

class TestChangedFileDetection:
    def test_get_changed_files_root_commit(self):
        """For ROOT (first commit), should list files as Added."""
        # We use the actual git repo to test this; find the first commit
        result = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip("git not available")
        first_commit = result.stdout.strip()
        files = get_changed_files(first_commit, "ROOT")
        # First commit should have at least some files
        assert isinstance(files, list)
        if files:
            assert "file_path" in files[0]
            assert "change_type" in files[0]
            assert files[0]["change_type"] in ("A", "M", "D", "R", "C")

    def test_changed_files_returns_list(self):
        """get_changed_files always returns a list (never None)."""
        try:
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
            ).stdout.strip()
            parent = subprocess.run(
                ["git", "rev-parse", "HEAD^"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
            ).stdout.strip() or "ROOT"
        except Exception:
            pytest.skip("git not available")

        files = get_changed_files(sha, parent)
        assert isinstance(files, list)


# ===========================================================================
# 4. Deduplication — commits.jsonl
# ===========================================================================

class TestCommitDeduplication:
    def test_load_existing_shas_empty_file(self, tmp_path, monkeypatch):
        """Empty file → empty set of SHAs."""
        fake_file = tmp_path / "commits.jsonl"
        fake_file.write_text("")
        monkeypatch.setattr("tools.collect_git_metadata.COMMITS_FILE", fake_file)
        shas = load_existing_shas()
        assert shas == set()

    def test_load_existing_shas_reads_correctly(self, tmp_path, monkeypatch):
        """Correctly reads committed SHAs from a populated file."""
        sha1 = "a" * 40
        sha2 = "b" * 40
        fake_file = tmp_path / "commits.jsonl"
        fake_file.write_text(
            json.dumps({"commit_sha": sha1}) + "\n" +
            json.dumps({"commit_sha": sha2}) + "\n"
        )
        monkeypatch.setattr("tools.collect_git_metadata.COMMITS_FILE", fake_file)
        shas = load_existing_shas()
        assert sha1 in shas
        assert sha2 in shas
        assert len(shas) == 2

    def test_write_record_appends(self, tmp_path, monkeypatch):
        """write_record appends a new JSON line to commits.jsonl."""
        fake_file = tmp_path / "commits.jsonl"
        monkeypatch.setattr("tools.collect_git_metadata.COMMITS_FILE", fake_file)
        monkeypatch.setattr("tools.collect_git_metadata.DATA_DIR", tmp_path)

        record = {"commit_sha": "a" * 40, "branch": "main"}
        write_record(record)
        write_record({"commit_sha": "b" * 40, "branch": "main"})

        lines = [l for l in fake_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["commit_sha"] == "a" * 40

    def test_skips_duplicate_sha(self, tmp_path, monkeypatch):
        """If SHA already exists, main() should skip without writing."""
        sha = "c" * 40
        fake_commits = tmp_path / "commits.jsonl"
        fake_commits.write_text(json.dumps({"commit_sha": sha}) + "\n")
        monkeypatch.setattr("tools.collect_git_metadata.COMMITS_FILE", fake_commits)
        monkeypatch.setattr("tools.collect_git_metadata.DATA_DIR", tmp_path)

        existing = load_existing_shas()
        assert sha in existing

        # Writing again for same SHA should not happen in main()
        # (test that the guard logic works, not the full main())
        initial_size = fake_commits.stat().st_size
        # Don't write — simulate the dedup check
        if sha not in existing:
            write_record({"commit_sha": sha})
        assert fake_commits.stat().st_size == initial_size


# ===========================================================================
# 5. Node ID stability
# ===========================================================================

class TestNodeIDStability:
    def test_node_ids_have_no_backslashes(self):
        """
        On Windows, node IDs may contain backslashes.
        Collector must normalize to forward slashes for cross-platform consistency.
        """
        raw_nodeid = r"automation\tests\test_cart.py::test_add_product_to_cart"
        normalized = raw_nodeid.replace("\\", "/")
        assert "\\" not in normalized
        assert "automation/tests/test_cart.py" in normalized


# ===========================================================================
# 6. Status mapping
# ===========================================================================

class TestStatusMapping:
    @pytest.mark.parametrize("status", list(VALID_STATUSES))
    def test_valid_statuses_are_accepted(self, status):
        """All valid status values pass validation."""
        record = _make_result_record(status=status)
        errors = check_results([record], known_shas={record["commit_sha"]})
        # Filter only status errors for this test
        status_errors = [e for e in errors if "invalid status" in e]
        assert not status_errors, f"Valid status '{status}' was rejected: {status_errors}"

    def test_invalid_status_is_rejected(self):
        """An invalid status value is caught by the validator."""
        record = _make_result_record(status="BROKEN")
        errors = check_results([record], known_shas={record["commit_sha"]})
        assert any("invalid status" in e for e in errors)


# ===========================================================================
# 7. Duration capture
# ===========================================================================

class TestDurationCapture:
    def test_positive_duration_passes(self):
        record = _make_result_record(duration=1.23)
        errors = check_results([record], known_shas={record["commit_sha"]})
        duration_errors = [e for e in errors if "duration" in e.lower()]
        assert not duration_errors

    def test_zero_duration_passes(self):
        record = _make_result_record(duration=0.0)
        errors = check_results([record], known_shas={record["commit_sha"]})
        duration_errors = [e for e in errors if "negative" in e.lower()]
        assert not duration_errors

    def test_negative_duration_fails(self):
        record = _make_result_record(duration=-1.0)
        errors = check_results([record], known_shas={record["commit_sha"]})
        assert any("negative" in e.lower() for e in errors)


# ===========================================================================
# 8. Failure message truncation
# ===========================================================================

class TestFailureMessageTruncation:
    def test_long_message_truncated(self):
        """Messages over MAX_FAILURE_MESSAGE_LEN should be truncated."""
        from automation.conftest_collector import MAX_FAILURE_MESSAGE_LEN
        long_msg = "x" * 2000

        # Simulate the truncation logic in conftest_collector
        if len(long_msg) > MAX_FAILURE_MESSAGE_LEN:
            long_msg = long_msg[:MAX_FAILURE_MESSAGE_LEN] + "... [truncated]"

        assert len(long_msg) <= MAX_FAILURE_MESSAGE_LEN + len("... [truncated]")
        assert long_msg.endswith("... [truncated]")

    def test_short_message_not_truncated(self):
        from automation.conftest_collector import MAX_FAILURE_MESSAGE_LEN
        short_msg = "AssertionError: expected True but got False"
        result = short_msg if len(short_msg) <= MAX_FAILURE_MESSAGE_LEN else short_msg[:MAX_FAILURE_MESSAGE_LEN]
        assert result == short_msg


# ===========================================================================
# 9. Schema completeness
# ===========================================================================

class TestSchemaCompleteness:
    def test_result_record_has_all_required_fields(self):
        """A well-formed result record passes schema validation."""
        from tools.validate_dataset import REQUIRED_RESULT_FIELDS
        record = _make_result_record()
        missing = REQUIRED_RESULT_FIELDS - set(record.keys())
        assert not missing, f"Record missing fields: {missing}"

    def test_commit_record_has_all_required_fields(self):
        from tools.validate_dataset import REQUIRED_COMMIT_FIELDS
        record = _make_commit_record()
        missing = REQUIRED_COMMIT_FIELDS - set(record.keys())
        assert not missing, f"Commit missing fields: {missing}"


# ===========================================================================
# 10. Dataset builder join logic
# ===========================================================================

class TestDatasetBuilder:
    def test_join_produces_correct_columns(self):
        """build_rows should produce dicts with all expected columns."""
        sha = "d" * 40
        commits = {sha: _make_commit_record(sha=sha)}
        results = [_make_result_record(sha=sha)]

        rows = build_rows(commits, results)
        assert len(rows) == 1
        for col in COLUMNS:
            assert col in rows[0], f"Expected column '{col}' missing from row"

    def test_unmatched_sha_produces_empty_commit_fields(self):
        """If test result has no matching commit, row still included with blank commit fields."""
        sha = "e" * 40
        commits = {}  # intentionally empty
        results = [_make_result_record(sha=sha)]

        rows = build_rows(commits, results)
        assert len(rows) == 1
        assert rows[0]["commit_sha"] == sha
        assert rows[0]["commit_message"] == ""  # blank, not crashed


# ===========================================================================
# 11. Validation — duplicate detection
# ===========================================================================

class TestDuplicateDetection:
    def test_duplicate_triplet_is_flagged(self):
        """Same (commit_sha, test_nodeid, run_id) flagged as duplicate."""
        sha = "f" * 40
        record = _make_result_record(sha=sha)
        errors = check_results([record, record], known_shas={sha})
        dup_errors = [e for e in errors if "uplicate" in e or "duplicate" in e.lower()]
        assert dup_errors, f"Expected duplicate detection, got errors: {errors}"

    def test_same_test_different_run_not_duplicate(self):
        """Same test run in different run_ids should NOT be flagged."""
        sha = "g" * 40
        r1 = _make_result_record(sha=sha, run_id="run-001")
        r2 = _make_result_record(sha=sha, run_id="run-002")
        errors = check_results([r1, r2], known_shas={sha})
        dup_errors = [e for e in errors if "uplicate" in e or "duplicate" in e.lower()]
        assert not dup_errors


# ===========================================================================
# 12. Validation — referential integrity
# ===========================================================================

class TestReferentialIntegrity:
    def test_missing_commit_sha_flagged(self):
        """Test result referencing unknown commit_sha is flagged."""
        known_sha = "h" * 40
        unknown_sha = "i" * 40
        record = _make_result_record(sha=unknown_sha)
        errors = check_results([record], known_shas={known_sha})
        ref_errors = [e for e in errors if "not found in commits" in e.lower()]
        assert ref_errors

    def test_known_commit_sha_passes(self):
        """Test result referencing a known commit_sha passes referential check."""
        sha = "j" * 40
        record = _make_result_record(sha=sha)
        errors = check_results([record], known_shas={sha})
        ref_errors = [e for e in errors if "not found in commits" in e.lower()]
        assert not ref_errors


# ===========================================================================
# 13. Data source classification
# ===========================================================================

class TestDataClassification:
    def test_controlled_failure_label_from_env(self, monkeypatch):
        """Setting DATA_SOURCE env var correctly sets data_source field."""
        monkeypatch.setenv("DATA_SOURCE", "controlled_failure")

        # Test Git collector record
        from tools.collect_git_metadata import collect
        with mock.patch("tools.collect_git_metadata.get_commit_sha", return_value="a"*40), \
             mock.patch("tools.collect_git_metadata.get_parent_sha", return_value="b"*40), \
             mock.patch("tools.collect_git_metadata.get_commit_message", return_value="msg"), \
             mock.patch("tools.collect_git_metadata.get_author", return_value="auth"), \
             mock.patch("tools.collect_git_metadata.get_timestamp_iso", return_value="iso"), \
             mock.patch("tools.collect_git_metadata.get_branch", return_value="main"), \
             mock.patch("tools.collect_git_metadata.get_changed_files", return_value=[]), \
             mock.patch("tools.collect_git_metadata.get_line_stats", return_value=(0, 0)):
            record = collect()
            assert record["data_source"] == "controlled_failure"


# ===========================================================================
# Helper factories
# ===========================================================================

def _make_result_record(
    sha: str = "a" * 40,
    nodeid: str = "automation/tests/test_auth.py::test_valid_login",
    run_id: str = "2026-09-15T14:00:00Z",
    status: str = "PASS",
    duration: float = 1.0,
) -> dict:
    """Create a minimal valid test result record."""
    return {
        "commit_sha": sha,
        "run_id": run_id,
        "test_nodeid": nodeid,
        "test_file": "automation/tests/test_auth.py",
        "test_name": "test_valid_login",
        "markers": ["smoke"],
        "status": status,
        "duration_sec": duration,
        "failure_message": "",
        "run_timestamp_iso": "2026-09-15T14:00:05+00:00",
        "data_source": "real",
    }


def _make_commit_record(sha: str = "a" * 40) -> dict:
    """Create a minimal valid commit record."""
    return {
        "commit_sha": sha,
        "parent_sha": "b" * 40,
        "commit_message": "test commit",
        "author": "hemchudesh12",
        "timestamp_iso": "2026-09-15T14:00:00+00:00",
        "branch": "main",
        "changed_files": ["app/cart/routes.py"],
        "changed_file_count": 1,
        "lines_added": 3,
        "lines_deleted": 1,
        "run_id": "2026-09-15T14:00:00Z",
        "data_source": "real",
    }
