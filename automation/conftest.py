"""
automation/conftest.py — Shared pytest fixtures for the entire automation suite.

Fixture hierarchy:
  seeded_db   (session, autouse) → resets DB to clean state once per run
  check_server (session, autouse) → fail fast if Flask is not running
  base_url    (session)          → "http://127.0.0.1:5000"
  browser     (session)          → provided by pytest-playwright
  context     (function)         → provided by pytest-playwright (fresh cookies per test)
  page        (function)         → provided by pytest-playwright
  logged_in_page (function)      → page + login as seeded test user
"""

import os
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from automation.utils.test_data import BASE_URL, VALID_USER


# ---------------------------------------------------------------------------
# Server health check — fail fast with a clear message if Flask isn't running
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def check_server():
    """Verify the Flask dev server is reachable before running any test."""
    host, port = "127.0.0.1", 5000
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    reachable = sock.connect_ex((host, port)) == 0
    sock.close()
    if not reachable:
        pytest.exit(
            "\n\n❌  Flask server is NOT running.\n"
            "   Start it first:  python run.py\n"
            "   Then re-run:     pytest\n",
            returncode=1,
        )


# ---------------------------------------------------------------------------
# Database reset — runs once per test session, before any test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def seeded_db(check_server):
    """
    Drop and reseed the database before the test session starts.

    Depends on check_server so the server check always runs first.
    The seed script is idempotent: safe to run multiple times.
    """
    project_root = Path(__file__).parent.parent
    result = subprocess.run(
        [sys.executable, "seed.py"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        pytest.fail(
            f"seed.py failed — cannot continue.\n\n"
            f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Base URL
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url() -> str:
    """Application base URL. Override pytest-playwright's default fixture."""
    return BASE_URL


# ---------------------------------------------------------------------------
# Authenticated page fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def logged_in_page(page, base_url):
    """
    Returns a Playwright page already authenticated as the seeded test user.

    Uses the pytest-playwright `page` fixture (function-scoped, fresh context
    per test), logs in via the UI, and returns the same page object.
    Tests that need auth should use this fixture instead of `page`.
    """
    page.goto(f"{base_url}/login")
    page.get_by_test_id("login-email").fill(VALID_USER["email"])
    page.get_by_test_id("login-password").fill(VALID_USER["password"])
    page.get_by_test_id("login-button").click()
    page.wait_for_url(f"{base_url}/")
    return page


# ---------------------------------------------------------------------------
# Screenshot on failure — captures state when a test fails
# ---------------------------------------------------------------------------

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        # Try both page fixtures (unauthenticated and authenticated)
        pg = item.funcargs.get("logged_in_page") or item.funcargs.get("page")
        if pg and not pg.is_closed():
            screenshot_dir = Path(__file__).parent.parent / "reports" / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)

            # Build a filesystem-safe filename from the test node id
            safe_name = re.sub(r"[^\w]", "_", item.nodeid)
            screenshot_path = screenshot_dir / f"{safe_name}.png"

            try:
                pg.screenshot(path=str(screenshot_path))
                report.sections.append(
                    ("Screenshot", f"Saved: {screenshot_path}")
                )
            except Exception:
                pass   # Never let screenshot failure mask the original test failure
