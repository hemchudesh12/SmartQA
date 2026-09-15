"""
automation/tests/test_auth.py — Tests for Authentication module.

Module: auth
Routes tested: /login, /register, /logout, /cart/ (protected redirect)
Markers: smoke (critical path), regression (full coverage)

Test inventory (12 tests):
  Smoke:      test_valid_login, test_logout, test_valid_registration
  Regression: test_invalid_password, test_invalid_email, test_empty_email,
              test_empty_password, test_protected_cart_redirects_to_login,
              test_duplicate_email_registration,
              test_registration_password_too_short,
              test_registration_passwords_mismatch,
              test_registration_invalid_email
"""

import uuid

import pytest

from automation.pages.login_page import LoginPage
from automation.pages.register_page import RegisterPage
from automation.utils.test_data import VALID_USER


# ===========================================================================
# Login tests
# ===========================================================================

@pytest.mark.smoke
def test_valid_login(page, base_url):
    """Valid credentials → user is logged in; logout link appears in navbar."""
    lp = LoginPage(page, base_url)
    lp.login(VALID_USER["email"], VALID_USER["password"])
    assert page.get_by_test_id("nav-logout").is_visible(), \
        "Expected nav-logout to be visible after successful login."


@pytest.mark.regression
def test_invalid_password(page, base_url):
    """Wrong password → stays on login page with error flash message."""
    lp = LoginPage(page, base_url)
    lp.login(VALID_USER["email"], "completely_wrong_password")
    assert "invalid email or password" in lp.first_flash_text().lower()


@pytest.mark.regression
def test_invalid_email(page, base_url):
    """Non-existent email → login fails with an error message."""
    lp = LoginPage(page, base_url)
    lp.login("nobody@nowhere.invalid", "anypassword123")
    assert "invalid email or password" in lp.first_flash_text().lower()


@pytest.mark.regression
def test_empty_email(page, base_url):
    """Empty email field → server rejects with 'required' message."""
    lp = LoginPage(page, base_url)
    lp.login("", "somepassword")
    assert "required" in lp.first_flash_text().lower()


@pytest.mark.regression
def test_empty_password(page, base_url):
    """Empty password field → server rejects with 'required' message."""
    lp = LoginPage(page, base_url)
    lp.login(VALID_USER["email"], "")
    assert "required" in lp.first_flash_text().lower()


@pytest.mark.smoke
def test_logout(page, base_url):
    """Logged-in user can log out; navbar switches back to showing Login."""
    lp = LoginPage(page, base_url)
    lp.login(VALID_USER["email"], VALID_USER["password"])
    page.wait_for_url(f"{base_url}/")

    lp.click_nav_logout()

    assert page.get_by_test_id("nav-login").is_visible(), \
        "Expected nav-login to appear after logout."
    assert not page.get_by_test_id("nav-logout").is_visible(), \
        "Expected nav-logout to disappear after logout."


@pytest.mark.regression
def test_protected_cart_redirects_to_login(page, base_url):
    """Unauthenticated request to /cart/ is redirected to /login."""
    page.goto(f"{base_url}/cart/")
    page.wait_for_url(lambda url: "/login" in url)
    assert page.get_by_test_id("login-form").is_visible(), \
        "Expected login form after redirect from protected /cart/ route."


# ===========================================================================
# Registration tests
# ===========================================================================

@pytest.mark.smoke
def test_valid_registration(page, base_url):
    """A new user can register and is immediately logged in."""
    unique_email = f"reg_{uuid.uuid4().hex[:8]}@smartqa.com"
    rp = RegisterPage(page, base_url)
    rp.register("New Tester", unique_email, "Password123", "Password123")

    assert page.get_by_test_id("nav-logout").is_visible(), \
        "Expected user to be logged in after successful registration."


@pytest.mark.regression
def test_duplicate_email_registration(page, base_url):
    """Registering with an already-used email shows a duplicate error."""
    rp = RegisterPage(page, base_url)
    rp.register(VALID_USER["name"], VALID_USER["email"], "Password123", "Password123")

    assert "already exists" in rp.first_flash_text().lower()


@pytest.mark.regression
def test_registration_password_too_short(page, base_url):
    """Password shorter than 6 characters is rejected."""
    unique_email = f"short_{uuid.uuid4().hex[:8]}@smartqa.com"
    rp = RegisterPage(page, base_url)
    rp.register("User", unique_email, "abc", "abc")

    assert "6 characters" in rp.first_flash_text().lower()


@pytest.mark.regression
def test_registration_passwords_mismatch(page, base_url):
    """Mismatched password and confirm-password is rejected."""
    unique_email = f"mismatch_{uuid.uuid4().hex[:8]}@smartqa.com"
    rp = RegisterPage(page, base_url)
    rp.register("User", unique_email, "password123", "different456")

    assert "do not match" in rp.first_flash_text().lower()


@pytest.mark.regression
def test_registration_invalid_email(page, base_url):
    """Email without '@' is rejected with a validation message."""
    rp = RegisterPage(page, base_url)
    rp.register("User", "not-an-email", "password123", "password123")

    assert "valid email" in rp.first_flash_text().lower()
