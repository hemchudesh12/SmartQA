"""
automation/pages/base_page.py — Shared base class for all Page Objects.

Rules:
  - Page Objects hold locators and user interactions only.
  - Assertions stay in the test files.
  - No bare except clauses.
  - No time.sleep().
"""

from playwright.sync_api import Page, Locator


class BasePage:
    """Base class inherited by every Page Object."""

    # Subclasses set this to the path portion of their URL, e.g. "/login"
    URL: str = "/"

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self) -> None:
        """Navigate directly to this page's URL."""
        self.page.goto(f"{self.base_url}{self.URL}")

    def full_url(self) -> str:
        return f"{self.base_url}{self.URL}"

    # ------------------------------------------------------------------
    # Flash messages (present on every page via base.html)
    # ------------------------------------------------------------------

    def flash_messages(self) -> Locator:
        """Returns all flash message elements."""
        return self.page.get_by_test_id("flash-message")

    def first_flash_text(self) -> str:
        """Returns the text content of the first flash message."""
        return self.flash_messages().first.inner_text()

    # ------------------------------------------------------------------
    # Navbar helpers
    # ------------------------------------------------------------------

    def navbar_cart_count(self) -> int:
        """Returns the number shown in the navbar cart badge, or 0 if not visible."""
        badge = self.page.get_by_test_id("cart-count")
        if badge.is_visible():
            return int(badge.inner_text().strip())
        return 0

    def is_logged_in(self) -> bool:
        """Returns True if the logout link is visible in the navbar."""
        return self.page.get_by_test_id("nav-logout").is_visible()

    def click_nav_logout(self) -> None:
        self.page.get_by_test_id("nav-logout").click()
        self.page.wait_for_url(f"{self.base_url}/login")
