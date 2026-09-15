"""
automation/pages/cart_page.py — Page Object for /cart/.
"""

from playwright.sync_api import Locator

from automation.pages.base_page import BasePage


class CartPage(BasePage):
    URL = "/cart/"

    # ------------------------------------------------------------------
    # Container locators
    # ------------------------------------------------------------------

    @property
    def cart_table(self) -> Locator:
        return self.page.get_by_test_id("cart-table")

    @property
    def empty_cart_state(self) -> Locator:
        return self.page.get_by_test_id("empty-cart")

    @property
    def cart_total(self) -> Locator:
        return self.page.get_by_test_id("cart-total")

    @property
    def checkout_button(self) -> Locator:
        return self.page.get_by_test_id("checkout-button")

    # ------------------------------------------------------------------
    # Per-item locators (product_id is the integer DB id)
    # ------------------------------------------------------------------

    def cart_item(self, product_id: int) -> Locator:
        """The full table row for a cart item."""
        return self.page.get_by_test_id(f"cart-item-{product_id}")

    def quantity_display(self, product_id: int) -> Locator:
        return self.page.get_by_test_id(f"cart-quantity-{product_id}")

    def increase_button(self, product_id: int) -> Locator:
        return self.page.get_by_test_id(f"cart-increase-{product_id}")

    def decrease_button(self, product_id: int) -> Locator:
        return self.page.get_by_test_id(f"cart-decrease-{product_id}")

    def remove_button(self, product_id: int) -> Locator:
        return self.page.get_by_test_id(f"cart-remove-{product_id}")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_quantity(self, product_id: int) -> int:
        """Returns the displayed quantity for a product."""
        text = self.quantity_display(product_id).inner_text()
        return int(text.strip())

    def cart_total_text(self) -> str:
        """Returns the total string as displayed, e.g. '₹4999.00'."""
        return self.cart_total.inner_text()

    def item_count(self) -> int:
        """Returns the number of distinct product rows in the cart."""
        return self.cart_table.locator("tbody tr").count()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def increase_quantity(self, product_id: int) -> None:
        self.increase_button(product_id).click()
        self.page.wait_for_url(f"{self.base_url}/cart/")

    def decrease_quantity(self, product_id: int) -> None:
        self.decrease_button(product_id).click()
        self.page.wait_for_url(f"{self.base_url}/cart/")

    def remove_item(self, product_id: int) -> None:
        self.remove_button(product_id).click()
        self.page.wait_for_url(f"{self.base_url}/cart/")

    def go_to_checkout(self) -> None:
        self.checkout_button.click()
        self.page.wait_for_load_state("networkidle")
