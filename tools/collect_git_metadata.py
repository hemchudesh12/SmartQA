"""
tools/collect_git_metadata.py — Git Metadata Collector for SmartQA Phase 4.

USAGE:
    python tools/collect_git_metadata.py

WHAT IT DOES:
    1. Determines the current commit SHA (CI env var or git command).
    2. Reads parent commit, message, author, timestamp, branch.
    3. Reads changed files and line diff statistics.
    4. Appends one record to data/commits.jsonl (append-only).
    5. Skips if this commit_sha is already recorded (deduplication).

WORKS IN:
    - GitHub Actions (uses GITHUB_SHA, GITHUB_REF_NAME, etc.)
    - Local development (uses git commands)

OUTPUT FORMAT (data/commits.jsonl):
    One JSON object per line. Example:
    {
        "commit_sha":        "a81c2df3...",      (full 40-char SHA)
        "parent_sha":        "b93e4fa1...",      (parent SHA, or "ROOT" for first commit)
        "commit_message":    "fix: cart total",
        "author":            "hemchudesh12",
        "timestamp_iso":     "2026-09-15T14:30:00+00:00",
        "branch":            "main",
        "changed_files":     ["app/cart/routes.py"],
        "changed_file_count": 1,
        "lines_added":       5,
        "lines_deleted":     3,
        "run_id":            "2026-09-15T14:30:00Z",
        "data_source":       "real"
    }

DATA LEAKAGE NOTE:
    This script collects ONLY pre-execution information (commit metadata, changed files).
    It does NOT collect test results — those are collected by conftest_collector.py.
    The commit metadata = feature space. Test results = label space.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
COMMITS_FILE = DATA_DIR / "commits.jsonl"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run_git(args: list[str], cwd: Path = PROJECT_ROOT) -> str:
    """
    Run a git command with --no-pager and return stripped stdout.
    Raises RuntimeError with clear message on failure.
    """
    env = {**os.environ, "GIT_PAGER": "cat", "GIT_EXTERNAL_DIFF": ""}
    try:
        result = subprocess.run(
            ["git", "--no-pager"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"git {' '.join(args)} timed out after 5 seconds")

    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed:\n"
            f"  STDOUT: {result.stdout.strip()}\n"
            f"  STDERR: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def get_commit_sha() -> str:
    """
    Return the current commit SHA.
    In CI: uses GITHUB_SHA env var (most reliable).
    Locally: uses git rev-parse HEAD.
    """
    sha = os.environ.get("GITHUB_SHA", "").strip()
    if sha:
        return sha
    return _run_git(["rev-parse", "HEAD"])


def get_parent_sha(commit_sha: str) -> str:
    """
    Return the parent commit SHA.
    Returns "ROOT" for the very first commit (no parent).
    """
    try:
        return _run_git(["rev-parse", f"{commit_sha}^"])
    except RuntimeError:
        # First commit has no parent
        return "ROOT"


def get_commit_message(commit_sha: str) -> str:
    """Return the full commit message for the given SHA."""
    return _run_git(["log", "-1", "--pretty=format:%s", commit_sha])


def get_author(commit_sha: str) -> str:
    """Return the commit author name."""
    return _run_git(["log", "-1", "--pretty=format:%an", commit_sha])


def get_timestamp_iso(commit_sha: str) -> str:
    """Return the commit author timestamp in ISO 8601 format."""
    raw = _run_git(["log", "-1", "--pretty=format:%aI", commit_sha])
    return raw


def get_branch() -> str:
    """
    Return the current branch name.
    In CI: GITHUB_REF_NAME (e.g., "main") or GITHUB_HEAD_REF (for PRs).
    Locally: git rev-parse --abbrev-ref HEAD.
    Falls back to "unknown" rather than crashing.
    """
    # GitHub Actions on PRs: GITHUB_HEAD_REF is the source branch
    branch = os.environ.get("GITHUB_HEAD_REF", "").strip()
    if branch:
        return branch

    # GitHub Actions on push: GITHUB_REF_NAME is the branch/tag name
    branch = os.environ.get("GITHUB_REF_NAME", "").strip()
    if branch:
        return branch

    # Local fallback
    try:
        return _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    except RuntimeError:
        return "unknown"


def get_changed_files(commit_sha: str, parent_sha: str) -> list[dict]:
    """
    Return a list of changed file records between parent and current commit.

    Each record:
        {
            "file_path": "app/cart/routes.py",
            "change_type": "M"   # A=Added, M=Modified, D=Deleted, R=Renamed
        }

    For the ROOT commit (first ever commit): lists all files as "A" (Added).
    """
    if parent_sha == "ROOT":
        # First commit — all files are "added"
        try:
            raw = _run_git(["diff-tree", "--no-commit-id", "-r", "--name-status", commit_sha])
        except RuntimeError:
            return []
    else:
        try:
            raw = _run_git(["diff", "--name-status", parent_sha, commit_sha])
        except RuntimeError:
            return []

    if not raw:
        return []

    files = []
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            change_type = parts[0].strip()[0]  # First char: A, M, D, R, C
            file_path = parts[1].strip()
            files.append({"file_path": file_path, "change_type": change_type})
    return files


def get_line_stats(commit_sha: str, parent_sha: str) -> tuple[int, int]:
    """
    Return (lines_added, lines_deleted) for the diff.
    Uses git diff --shortstat.
    Returns (0, 0) if no changes or stats unavailable.
    """
    if parent_sha == "ROOT":
        try:
            raw = _run_git(["diff-tree", "--no-commit-id", "-r", "--shortstat", commit_sha])
        except RuntimeError:
            return 0, 0
    else:
        try:
            raw = _run_git(["diff", "--shortstat", parent_sha, commit_sha])
        except RuntimeError:
            return 0, 0

    if not raw:
        return 0, 0

    # Format: "2 files changed, 15 insertions(+), 3 deletions(-)"
    added = 0
    deleted = 0
    for part in raw.split(","):
        part = part.strip()
        if "insertion" in part:
            added = int(part.split()[0])
        elif "deletion" in part:
            deleted = int(part.split()[0])
    return added, deleted


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def load_existing_shas() -> set[str]:
    """Return the set of commit SHAs already recorded in commits.jsonl."""
    shas = set()
    if not COMMITS_FILE.exists():
        return shas
    with open(COMMITS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                sha = record.get("commit_sha", "")
                if sha:
                    shas.add(sha)
            except json.JSONDecodeError:
                pass  # Skip malformed lines
    return shas


# ---------------------------------------------------------------------------
# Main collection
# ---------------------------------------------------------------------------

def collect() -> dict:
    """
    Collect full git metadata for the current commit.
    Returns the metadata dict (does NOT write to file — caller decides).
    """
    commit_sha = get_commit_sha()
    parent_sha = get_parent_sha(commit_sha)
    commit_message = get_commit_message(commit_sha)
    author = get_author(commit_sha)
    timestamp_iso = get_timestamp_iso(commit_sha)
    branch = get_branch()
    changed_file_records = get_changed_files(commit_sha, parent_sha)
    lines_added, lines_deleted = get_line_stats(commit_sha, parent_sha)

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "commit_sha": commit_sha,
        "parent_sha": parent_sha,
        "commit_message": commit_message,
        "author": author,
        "timestamp_iso": timestamp_iso,
        "branch": branch,
        "changed_files": [f["file_path"] for f in changed_file_records],
        "changed_file_details": changed_file_records,
        "changed_file_count": len(changed_file_records),
        "lines_added": lines_added,
        "lines_deleted": lines_deleted,
        "run_id": run_id,
        "data_source": os.environ.get("DATA_SOURCE", "real"),
    }


def write_record(record: dict) -> None:
    """Append one record to commits.jsonl (creates file if needed)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(COMMITS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    """
    Entry point.
    Returns 0 on success, 1 on error.
    """
    print("=" * 60)
    print("SmartQA Phase 4 — Git Metadata Collector")
    print("=" * 60)

    try:
        record = collect()
    except RuntimeError as exc:
        print(f"\n[ERROR] Collection failed:\n{exc}", file=sys.stderr)
        return 1

    commit_sha = record["commit_sha"]
    print(f"\nCommit SHA   : {commit_sha}")
    print(f"Parent SHA   : {record['parent_sha']}")
    print(f"Branch       : {record['branch']}")
    print(f"Author       : {record['author']}")
    print(f"Message      : {record['commit_message']}")
    print(f"Timestamp    : {record['timestamp_iso']}")
    print(f"Changed files: {record['changed_file_count']}")
    for f in record["changed_file_details"]:
        print(f"  [{f['change_type']}] {f['file_path']}")
    print(f"Lines added  : {record['lines_added']}")
    print(f"Lines deleted: {record['lines_deleted']}")

    # Deduplication check
    existing_shas = load_existing_shas()
    if commit_sha in existing_shas:
        print(f"\n[SKIP] Commit {commit_sha[:12]}... already recorded. Skipping to prevent duplicate.")
        return 0

    write_record(record)
    print(f"\n[OK] Recorded to {COMMITS_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
