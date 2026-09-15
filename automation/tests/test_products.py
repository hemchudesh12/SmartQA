"""
automation/tests/test_products.py — Tests for Product Catalog module.

Module: products
Routes tested: /products, /products?category=X, /product/<id>
Markers: smoke (critical path), regression (full coverage)

Test inventory (5 tests):
  Smoke:      test_products_page_loads, test_product_detail_page
  Regression: test_product_cards_have_name_and_price,
              test_category_filter_electronics,
              test_invalid_product_id_returns_404
"""

import pytest

from automation.pages.product_detail_page import ProductDetailPage
from automation.pages.products_page import ProductsPage
from automation.utils.test_data import (
    CATEGORY_COUNTS,
    KNOWN_PRODUCTS,
    NONEXISTENT_PRODUCT_ID,
)


@pytest.mark.smoke
def test_products_page_loads(page, base_url):
    """The product catalog loads and shows all 12 seeded products."""
    pp = ProductsPage(page, base_url)
    pp.navigate()

    assert pp.product_grid.is_visible(), "Product grid container should be visible."
    assert pp.product_cards.count() == CATEGORY_COUNTS["all"], \
        f"Expected {CATEGORY_COUNTS['all']} product cards, got {pp.product_cards.count()}."


@pytest.mark.regression
def test_product_cards_have_name_and_price(page, base_url):
    """Each product card displays the correct name and a price with ₹ symbol."""
    pp = ProductsPage(page, base_url)
    pp.navigate()

    product_id = KNOWN_PRODUCTS["headphones"]["id"]

    assert pp.product_name_text(product_id) == KNOWN_PRODUCTS["headphones"]["name"], \
        "Product name on card does not match seed data."
    assert "₹" in pp.product_price_text(product_id), \
        "Price should contain the ₹ symbol."
    assert str(int(KNOWN_PRODUCTS["headphones"]["price"])) in pp.product_price_text(product_id), \
        "Price value should appear on the card."


@pytest.mark.regression
def test_category_filter_electronics(page, base_url):
    """Filtering by Electronics shows only the 5 seeded Electronics products."""
    pp = ProductsPage(page, base_url)
    pp.navigate()
    pp.filter_by_category("Electronics")

    count = pp.product_cards.count()
    assert count == CATEGORY_COUNTS["Electronics"], \
        f"Expected {CATEGORY_COUNTS['Electronics']} Electronics products, got {count}."


@pytest.mark.smoke
def test_product_detail_page(page, base_url):
    """Clicking 'Details' on a product card navigates to the correct detail page."""
    pp = ProductsPage(page, base_url)
    pp.navigate()

    product_id = KNOWN_PRODUCTS["headphones"]["id"]
    pp.view_details(product_id)

    dp = ProductDetailPage(page, base_url)
    assert dp.product_detail_container.is_visible()
    assert dp.product_name_text() == KNOWN_PRODUCTS["headphones"]["name"], \
        "Product name on detail page does not match."
    assert "₹" in dp.product_price_text(), \
        "Price should be displayed on the detail page."
    assert dp.add_to_cart_button.is_visible(), \
        "Add to Cart button should be visible for an in-stock product."


@pytest.mark.regression
def test_invalid_product_id_returns_404(page, base_url):
    """Navigating to /product/9999 returns a 404 HTTP response."""
    response = page.goto(f"{base_url}/product/{NONEXISTENT_PRODUCT_ID}")
    assert response is not None
    assert response.status == 404, \
        f"Expected 404 for non-existent product, got {response.status}."
