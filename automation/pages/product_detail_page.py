"""
automation/pages/product_detail_page.py — Page Object for /product/<id>.
"""

from playwright.sync_api import Locator

from automation.pages.base_page import BasePage


class ProductDetailPage(BasePage):
    """
    The URL is dynamic (/product/<id>), so navigate() is overridden
    to accept a product_id argument.
    """

    URL = "/product"   # base prefix; full URL requires an id

    def navigate_to(self, product_id: int) -> None:
        """Navigate directly to a specific product detail page."""
        self.page.goto(f"{self.base_url}/product/{product_id}")

    # ------------------------------------------------------------------
    # Locators
    # ------------------------------------------------------------------

    @property
    def product_detail_container(self) -> Locator:
        return self.page.get_by_test_id("product-detail")

    @property
    def product_name(self) -> Locator:
        return self.page.get_by_test_id("product-name")

    @property
    def product_price(self) -> Locator:
        return self.page.get_by_test_id("product-price")

    @property
    def product_description(self) -> Locator:
        return self.page.get_by_test_id("product-description")

    @property
    def product_category(self) -> Locator:
        return self.page.get_by_test_id("product-category")

    @property
    def product_stock(self) -> Locator:
        return self.page.get_by_test_id("product-stock")

    @property
    def add_to_cart_button(self) -> Locator:
        return self.page.get_by_test_id("add-to-cart-button")

    @property
    def back_to_products(self) -> Locator:
        return self.page.get_by_test_id("back-to-products")

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    def product_name_text(self) -> str:
        return self.product_name.inner_text()

    def product_price_text(self) -> str:
        return self.product_price.inner_text()

    def product_description_text(self) -> str:
        return self.product_description.inner_text()

    def product_category_text(self) -> str:
        return self.product_category.inner_text()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def click_add_to_cart(self) -> None:
        self.add_to_cart_button.click()
        self.page.wait_for_load_state("networkidle")
