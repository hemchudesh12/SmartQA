"""
automation/pages/profile_page.py — Page Object for /profile/.
"""

from playwright.sync_api import Locator

from automation.pages.base_page import BasePage


class ProfilePage(BasePage):
    URL = "/profile/"

    # ------------------------------------------------------------------
    # Locators — Profile info
    # ------------------------------------------------------------------

    @property
    def profile_name(self) -> Locator:
        return self.page.get_by_test_id("profile-name")

    @property
    def profile_email(self) -> Locator:
        return self.page.get_by_test_id("profile-email")

    @property
    def profile_joined(self) -> Locator:
        return self.page.get_by_test_id("profile-joined")

    # ------------------------------------------------------------------
    # Locators — Update form
    # ------------------------------------------------------------------

    @property
    def name_input(self) -> Locator:
        return self.page.get_by_test_id("profile-name-input")

    @property
    def update_button(self) -> Locator:
        return self.page.get_by_test_id("profile-update-button")

    # ------------------------------------------------------------------
    # Locators — Order history
    # ------------------------------------------------------------------

    @property
    def order_history(self) -> Locator:
        return self.page.get_by_test_id("order-history")

    @property
    def no_orders_state(self) -> Locator:
        return self.page.get_by_test_id("no-orders")

    def order_cards(self) -> Locator:
        """All order cards within the order history section."""
        return self.order_history.locator(".order-card")

    def order_card(self, order_id: int) -> Locator:
        return self.page.get_by_test_id(f"order-card-{order_id}")

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    def profile_name_text(self) -> str:
        return self.profile_name.inner_text()

    def profile_email_text(self) -> str:
        return self.profile_email.inner_text()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def update_name(self, new_name: str) -> None:
        """Fill the name input and submit the update form."""
        self.name_input.fill(new_name)
        self.update_button.click()
        self.page.wait_for_url(f"{self.base_url}/profile/")
