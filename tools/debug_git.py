import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def run_git(args):
    print(f"Testing git {' '.join(args)} ...", end=" ", flush=True)
    env = {**os.environ, "GIT_PAGER": "cat", "GIT_EXTERNAL_DIFF": ""}
    try:
        res = subprocess.run(
            ["git", "--no-pager"] + args,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            stdin=subprocess.DEVNULL,
            env=env
        )
        print(f"DONE (rc={res.returncode})")
        print(f"  STDOUT: {res.stdout.strip()}")
        print(f"  STDERR: {res.stderr.strip()}")
        return res.stdout.strip()
    except Exception as e:
        print(f"FAILED: {e}")
        return None

def main():
    print("--- GIT COMMAND DEBUG ---")
    sha = run_git(["rev-parse", "HEAD"])
    if sha:
        run_git(["rev-parse", f"{sha}~1"])
        run_git(["log", "-1", "--pretty=format:%s", sha])
        run_git(["log", "-1", "--pretty=format:%an", sha])
        run_git(["log", "-1", "--pretty=format:%aI", sha])
        run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        run_git(["diff-tree", "--no-commit-id", "-r", "--name-status", sha])
        run_git(["diff-tree", "--no-commit-id", "-r", "--shortstat", sha])

if __name__ == "__main__":
    main()
