"""
automation/conftest_collector.py — SmartQA Phase 4 Test Result Collector.

This is a SEPARATE pytest plugin file. It does NOT modify conftest.py.
It is registered via pytest.ini addopts: -p automation.conftest_collector

WHAT IT DOES:
    After each test completes, captures:
        - test node ID (stable, deterministic)
        - test file path
        - test name
        - markers (smoke, regression)
        - status (PASS / FAIL / SKIP / ERROR)
        - duration in seconds
        - failure message (truncated, secrets-safe)
        - run timestamp

    Appends one JSON record per test to data/test_results.jsonl.

    Deduplication: (commit_sha, test_nodeid) pairs are NOT duplicated
    in the same run. Multiple runs of the same commit produce multiple
    records — this is intentional for averaging/analysis.

    However, if the exact same (commit_sha, test_nodeid, run_id)
    triplet is detected, it is skipped.

DATA LEAKAGE NOTE:
    test_results.jsonl = LABELS (post-execution outcomes).
    commits.jsonl      = FEATURES (pre-execution git metadata).
    These two files must never be merged incorrectly in Phase 5.
    The 'status' field in this file is the prediction TARGET.
    It must NEVER be used as an input feature for the same run.

OUTPUT FORMAT (data/test_results.jsonl):
    One JSON object per line per test. Example:
    {
        "commit_sha":          "a81c2df3...",
        "run_id":              "2026-09-15T14:30:00Z",
        "test_nodeid":         "automation/tests/test_cart.py::test_cart_total_calculated_correctly",
        "test_file":           "automation/tests/test_cart.py",
        "test_name":           "test_cart_total_calculated_correctly",
        "markers":             ["regression"],
        "status":              "FAIL",
        "duration_sec":        1.42,
        "failure_message":     "AssertionError: Expected '4999.00', got '0.00'.",
        "run_timestamp_iso":   "2026-09-15T14:30:05+00:00",
        "data_source":         "real"
    }
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_FILE = DATA_DIR / "test_results.jsonl"

# Maximum characters captured from a failure message.
# Long stack traces are truncated to prevent dataset bloat.
MAX_FAILURE_MESSAGE_LEN = 500


# ---------------------------------------------------------------------------
# Commit SHA resolution (shared with collect_git_metadata.py logic)
# ---------------------------------------------------------------------------

def _resolve_commit_sha() -> str:
    """
    Determine the current commit SHA.
    In CI: reads GITHUB_SHA env var.
    Locally: runs git rev-parse HEAD.
    Returns "UNKNOWN" as last resort (never crashes the test run).
    """
    sha = os.environ.get("GITHUB_SHA", "").strip()
    if sha:
        return sha

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _load_existing_keys() -> set[tuple[str, str, str]]:
    """
    Load existing (commit_sha, test_nodeid, run_id) triplets to prevent
    exact duplicate records within the same run invocation.
    """
    keys: set[tuple[str, str, str]] = set()
    if not RESULTS_FILE.exists():
        return keys
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                key = (
                    record.get("commit_sha", ""),
                    record.get("test_nodeid", ""),
                    record.get("run_id", ""),
                )
                keys.add(key)
            except json.JSONDecodeError:
                pass
    return keys


# ---------------------------------------------------------------------------
# Plugin state — resolved once per session
# ---------------------------------------------------------------------------

class _CollectorState:
    """Mutable state shared across hook calls within one pytest session."""

    def __init__(self):
        self.commit_sha: str = "UNKNOWN"
        self.run_id: str = ""
        self.existing_keys: set[tuple[str, str, str]] = set()
        self.records: list[dict] = []   # buffered in memory, flushed at end


_state = _CollectorState()


# ---------------------------------------------------------------------------
# Pytest hooks
# ---------------------------------------------------------------------------

def pytest_sessionstart(session):
    """Resolve commit SHA and run ID once at the start of the session."""
    _state.commit_sha = _resolve_commit_sha()
    _state.run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _state.existing_keys = _load_existing_keys()

    print(
        f"\n[SmartQA Collector] commit_sha={_state.commit_sha[:12]}... "
        f"run_id={_state.run_id}",
        file=sys.stderr,
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Capture per-test result after the 'call' phase.

    Phases:
        setup   → fixture setup
        call    → actual test body  ← we capture here
        teardown → fixture teardown

    We only write a record after 'call' so we capture the real test outcome.
    For SKIP tests (skipped at collection time), we handle in pytest_runtest_logreport.
    """
    outcome = yield
    report = outcome.get_result()

    # Only process the "call" phase (the test body itself)
    if report.when != "call":
        return

    # Map pytest report outcome → clean status string
    if report.passed:
        status = "PASS"
    elif report.failed:
        status = "FAIL"
    elif report.skipped:
        status = "SKIP"
    else:
        status = "ERROR"

    _record_result(item, report, status)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_logreport(report):
    """
    Catch tests that are SKIPPED at the setup phase (before call phase).
    This handles @pytest.mark.skip and skipif decorators that skip
    before the test body executes (so call phase never fires).
    """
    yield
    if report.when == "setup" and report.skipped:
        # The item is available on the report as report.nodeid
        # We reconstruct a minimal record here
        _record_skipped(report)


def pytest_sessionfinish(session, exitstatus):
    """Write all collected records to test_results.jsonl at session end."""
    if not _state.records:
        print("\n[SmartQA Collector] No test records to write.", file=sys.stderr)
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        for record in _state.records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    print(
        f"\n[SmartQA Collector] Wrote {written} test result(s) to {RESULTS_FILE}",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_markers(item) -> list[str]:
    """Return a list of custom marker names applied to this test item."""
    # Exclude built-in pytest markers
    builtin_markers = {
        "parametrize", "skip", "skipif", "xfail", "usefixtures",
        "filterwarnings", "timeout", "tryfirst", "trylast",
    }
    markers = []
    for marker in item.own_markers:
        if marker.name not in builtin_markers:
            markers.append(marker.name)
    return sorted(markers)


def _safe_failure_message(report) -> str:
    """
    Extract a truncated, safe failure message from the report.
    - Does NOT dump full stack traces.
    - Truncated to MAX_FAILURE_MESSAGE_LEN characters.
    - Returns "" for passing/skipped tests.
    """
    if not hasattr(report, "longrepr") or report.longrepr is None:
        return ""

    longrepr = report.longrepr
    if isinstance(longrepr, str):
        msg = longrepr
    elif hasattr(longrepr, "reprcrash"):
        # ReprExceptionInfo — the most useful field is reprcrash.message
        msg = str(longrepr.reprcrash.message)
    else:
        msg = str(longrepr)

    # Truncate to prevent dataset bloat
    if len(msg) > MAX_FAILURE_MESSAGE_LEN:
        msg = msg[:MAX_FAILURE_MESSAGE_LEN] + "... [truncated]"

    return msg


def _is_sut_test(nodeid: str) -> bool:
    """
    Returns True only for System Under Test (SUT) tests in automation/tests/.
    Internal collector unit tests (tools/tests/) are ignored.
    """
    norm = nodeid.replace("\\", "/")
    return norm.startswith("automation/tests/") or "/automation/tests/" in norm


def _record_result(item, report, status: str) -> None:
    """Build and buffer a test result record."""
    nodeid = item.nodeid
    if not _is_sut_test(nodeid):
        return

    # Normalize path separators (Windows → forward slash)
    nodeid = nodeid.replace("\\", "/")

    # Derive test_file and test_name from nodeid
    # nodeid format: "automation/tests/test_cart.py::test_add_product_to_cart"
    parts = nodeid.split("::")
    test_file = parts[0] if parts else nodeid
    test_name = parts[-1] if len(parts) > 1 else nodeid

    markers = _extract_markers(item)
    duration_sec = round(report.duration, 4) if hasattr(report, "duration") else 0.0
    failure_message = _safe_failure_message(report) if status in ("FAIL", "ERROR") else ""
    run_timestamp_iso = datetime.now(timezone.utc).isoformat()

    record = {
        "commit_sha": _state.commit_sha,
        "run_id": _state.run_id,
        "test_nodeid": nodeid,
        "test_file": test_file,
        "test_name": test_name,
        "markers": markers,
        "status": status,
        "duration_sec": duration_sec,
        "failure_message": failure_message,
        "run_timestamp_iso": run_timestamp_iso,
        "data_source": os.environ.get("DATA_SOURCE", "real"),
    }

    # Deduplication: skip if exact (commit_sha, nodeid, run_id) triplet exists
    key = (_state.commit_sha, nodeid, _state.run_id)
    if key in _state.existing_keys:
        return

    _state.existing_keys.add(key)
    _state.records.append(record)


def _record_skipped(report) -> None:
    """Record a test that was skipped before its call phase."""
    if not _is_sut_test(report.nodeid):
        return
    nodeid = report.nodeid.replace("\\", "/")
    parts = nodeid.split("::")
    test_file = parts[0] if parts else nodeid
    test_name = parts[-1] if len(parts) > 1 else nodeid

    # Extract skip reason
    skip_reason = ""
    if isinstance(report.longrepr, tuple) and len(report.longrepr) == 3:
        skip_reason = str(report.longrepr[2])
    elif hasattr(report, "longrepr") and report.longrepr:
        skip_reason = str(report.longrepr)

    if len(skip_reason) > MAX_FAILURE_MESSAGE_LEN:
        skip_reason = skip_reason[:MAX_FAILURE_MESSAGE_LEN] + "... [truncated]"

    record = {
        "commit_sha": _state.commit_sha,
        "run_id": _state.run_id,
        "test_nodeid": nodeid,
        "test_file": test_file,
        "test_name": test_name,
        "markers": [],   # Can't access item.own_markers here; markers not available
        "status": "SKIP",
        "duration_sec": 0.0,
        "failure_message": skip_reason,
        "run_timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "data_source": os.environ.get("DATA_SOURCE", "real"),
    }

    key = (_state.commit_sha, nodeid, _state.run_id)
    if key in _state.existing_keys:
        return

    _state.existing_keys.add(key)
    _state.records.append(record)
