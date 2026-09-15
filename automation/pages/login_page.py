"""
automation/pages/login_page.py — Page Object for /login.
"""

from playwright.sync_api import Locator

from automation.pages.base_page import BasePage


class LoginPage(BasePage):
    URL = "/login"

    # ------------------------------------------------------------------
    # Locators
    # ------------------------------------------------------------------

    @property
    def email_input(self) -> Locator:
        return self.page.get_by_test_id("login-email")

    @property
    def password_input(self) -> Locator:
        return self.page.get_by_test_id("login-password")

    @property
    def login_button(self) -> Locator:
        return self.page.get_by_test_id("login-button")

    @property
    def register_link(self) -> Locator:
        return self.page.get_by_test_id("register-link")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def login(self, email: str, password: str) -> None:
        """Navigate to login page and submit credentials."""
        self.navigate()
        self.email_input.fill(email)
        self.password_input.fill(password)
        self.login_button.click()
