"""
automation/pages/checkout_page.py — Page Object for /checkout.

Note: Navigating to /checkout when the cart is empty causes Flask to
redirect to /cart/ with a flash message. Tests must add a product to
the cart before calling navigate() on this page.
"""

from playwright.sync_api import Locator

from automation.pages.base_page import BasePage


class CheckoutPage(BasePage):
    URL = "/checkout"

    # ------------------------------------------------------------------
    # Locators — Shipping form fields
    # ------------------------------------------------------------------

    @property
    def full_name_input(self) -> Locator:
        return self.page.get_by_test_id("checkout-full-name")

    @property
    def address_input(self) -> Locator:
        return self.page.get_by_test_id("checkout-address")

    @property
    def city_input(self) -> Locator:
        return self.page.get_by_test_id("checkout-city")

    @property
    def postal_code_input(self) -> Locator:
        return self.page.get_by_test_id("checkout-postal-code")

    @property
    def phone_input(self) -> Locator:
        return self.page.get_by_test_id("checkout-phone")

    @property
    def payment_cod(self) -> Locator:
        return self.page.get_by_test_id("checkout-payment-cod")

    @property
    def payment_demo_card(self) -> Locator:
        return self.page.get_by_test_id("checkout-payment-demo-card")

    @property
    def submit_button(self) -> Locator:
        return self.page.get_by_test_id("checkout-submit")

    @property
    def order_summary(self) -> Locator:
        return self.page.get_by_test_id("order-summary")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def fill_shipping(
        self,
        full_name: str,
        address: str,
        city: str,
        postal_code: str,
        phone: str,
        payment: str = "cod",
    ) -> None:
        """Fill all shipping fields and select payment method."""
        self.full_name_input.fill(full_name)
        self.address_input.fill(address)
        self.city_input.fill(city)
        self.postal_code_input.fill(postal_code)
        self.phone_input.fill(phone)
        if payment == "demo_card":
            self.payment_demo_card.check()
        else:
            self.payment_cod.check()

    def submit(self) -> None:
        """Click the Place Order button.
        The test is responsible for waiting on the resulting URL."""
        self.submit_button.click()
