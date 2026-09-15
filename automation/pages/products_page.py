"""
automation/pages/products_page.py — Page Object for /products.
"""

from playwright.sync_api import Locator

from automation.pages.base_page import BasePage


class ProductsPage(BasePage):
    URL = "/products"

    # ------------------------------------------------------------------
    # Container locators
    # ------------------------------------------------------------------

    @property
    def product_grid(self) -> Locator:
        return self.page.get_by_test_id("product-grid")

    @property
    def product_cards(self) -> Locator:
        """All product cards — uses attribute-prefix selector to target
        only card containers (data-testid="product-card-{id}"), not child
        elements inside them."""
        return self.page.locator("[data-testid^='product-card-']")

    @property
    def category_filter(self) -> Locator:
        return self.page.get_by_test_id("category-filter")

    # ------------------------------------------------------------------
    # Per-product locators (product_id is the integer DB id)
    # ------------------------------------------------------------------

    def product_card(self, product_id: int) -> Locator:
        return self.page.get_by_test_id(f"product-card-{product_id}")

    def product_name_locator(self, product_id: int) -> Locator:
        return self.page.get_by_test_id(f"product-name-{product_id}")

    def product_price_locator(self, product_id: int) -> Locator:
        return self.page.get_by_test_id(f"product-price-{product_id}")

    def product_stock_locator(self, product_id: int) -> Locator:
        return self.page.get_by_test_id(f"product-stock-{product_id}")

    def product_name_text(self, product_id: int) -> str:
        return self.product_name_locator(product_id).inner_text()

    def product_price_text(self, product_id: int) -> str:
        return self.product_price_locator(product_id).inner_text()

    def product_stock_text(self, product_id: int) -> str:
        return self.product_stock_locator(product_id).inner_text()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def add_to_cart(self, product_id: int) -> None:
        """Click the Add to Cart button for the given product.
        Waits for the resulting redirect to complete."""
        self.page.get_by_test_id(f"add-to-cart-{product_id}").click()
        self.page.wait_for_load_state("networkidle")

    def view_details(self, product_id: int) -> None:
        """Click the Details link for the given product."""
        self.page.get_by_test_id(f"view-details-{product_id}").click()
        self.page.wait_for_load_state("networkidle")

    def filter_by_category(self, category: str) -> None:
        """Click a category filter button.
        category should match the display name, e.g. 'Electronics'."""
        testid = f"category-{category.lower().replace(' ', '-')}"
        self.page.get_by_test_id(testid).click()
        self.page.wait_for_load_state("networkidle")

    def filter_all(self) -> None:
        self.page.get_by_test_id("category-all").click()
        self.page.wait_for_load_state("networkidle")
