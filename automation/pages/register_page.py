"""
automation/pages/register_page.py — Page Object for /register.
"""

from playwright.sync_api import Locator

from automation.pages.base_page import BasePage


class RegisterPage(BasePage):
    URL = "/register"

    # ------------------------------------------------------------------
    # Locators
    # ------------------------------------------------------------------

    @property
    def name_input(self) -> Locator:
        return self.page.get_by_test_id("register-name")

    @property
    def email_input(self) -> Locator:
        return self.page.get_by_test_id("register-email")

    @property
    def password_input(self) -> Locator:
        return self.page.get_by_test_id("register-password")

    @property
    def confirm_input(self) -> Locator:
        return self.page.get_by_test_id("register-confirm-password")

    @property
    def register_button(self) -> Locator:
        return self.page.get_by_test_id("register-button")

    @property
    def login_link(self) -> Locator:
        return self.page.get_by_test_id("login-link")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        email: str,
        password: str,
        confirm_password: str,
    ) -> None:
        """Navigate to register page and submit the registration form."""
        self.navigate()
        self.name_input.fill(name)
        self.email_input.fill(email)
        self.password_input.fill(password)
        self.confirm_input.fill(confirm_password)
        self.register_button.click()
