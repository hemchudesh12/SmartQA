"""
automation/tests/test_cart.py — Tests for Shopping Cart module.

Module: cart
Routes tested: /cart/, /cart/add/<id>, /cart/remove/<id>,
               /cart/increase/<id>, /cart/decrease/<id>
Markers: smoke, regression

All cart tests require authentication. Uses the `logged_in_page` fixture
which provides a browser page already logged in as the seeded test user.

Each test gets a fresh browser context (fresh session/cookies), so the
cart starts empty at the beginning of every test.

Test inventory (6 tests):
  Smoke:      test_add_product_to_cart
  Regression: test_cart_shows_added_product, test_increase_quantity,
              test_decrease_quantity, test_remove_product_from_cart,
              test_cart_total_calculated_correctly
"""

import pytest

from automation.pages.cart_page import CartPage
from automation.pages.products_page import ProductsPage
from automation.utils.test_data import KNOWN_PRODUCTS


# Shared shortcut — headphones are used in most cart tests
HEADPHONES_ID = KNOWN_PRODUCTS["headphones"]["id"]
HEADPHONES_PRICE = KNOWN_PRODUCTS["headphones"]["price"]


def _add_headphones(logged_in_page, base_url) -> None:
    """Helper: add the headphones product to cart from the product listing."""
    pp = ProductsPage(logged_in_page, base_url)
    pp.navigate()
    pp.add_to_cart(HEADPHONES_ID)


@pytest.mark.smoke
def test_add_product_to_cart(logged_in_page, base_url):
    """Adding a product increments the cart badge in the navbar to 1."""
    _add_headphones(logged_in_page, base_url)

    badge = logged_in_page.get_by_test_id("cart-count")
    assert badge.is_visible(), "Cart count badge should appear after adding an item."
    assert badge.inner_text().strip() == "1", \
        "Cart count should be 1 after adding one product."


@pytest.mark.regression
def test_cart_shows_added_product(logged_in_page, base_url):
    """After adding a product, its row appears in the cart table."""
    _add_headphones(logged_in_page, base_url)

    cp = CartPage(logged_in_page, base_url)
    cp.navigate()

    assert cp.cart_item(HEADPHONES_ID).is_visible(), \
        "Cart item row should be visible for the added product."
    assert cp.get_quantity(HEADPHONES_ID) == 1


@pytest.mark.regression
def test_increase_quantity(logged_in_page, base_url):
    """Clicking the '+' button increments the quantity from 1 to 2."""
    _add_headphones(logged_in_page, base_url)

    cp = CartPage(logged_in_page, base_url)
    cp.navigate()
    cp.increase_quantity(HEADPHONES_ID)

    assert cp.get_quantity(HEADPHONES_ID) == 2, \
        "Quantity should be 2 after clicking increase once."


@pytest.mark.regression
def test_decrease_quantity(logged_in_page, base_url):
    """Clicking '+' then '−' brings the quantity back to 1."""
    _add_headphones(logged_in_page, base_url)

    cp = CartPage(logged_in_page, base_url)
    cp.navigate()
    cp.increase_quantity(HEADPHONES_ID)   # qty = 2
    cp.decrease_quantity(HEADPHONES_ID)   # qty = 1

    assert cp.get_quantity(HEADPHONES_ID) == 1, \
        "Quantity should be 1 after increase then decrease."


@pytest.mark.regression
def test_remove_product_from_cart(logged_in_page, base_url):
    """Removing the only cart item shows the empty cart state."""
    _add_headphones(logged_in_page, base_url)

    cp = CartPage(logged_in_page, base_url)
    cp.navigate()
    cp.remove_item(HEADPHONES_ID)

    assert cp.empty_cart_state.is_visible(), \
        "Empty cart state should be visible after removing the only item."
    assert not cp.cart_table.is_visible(), \
        "Cart table should not be visible when cart is empty."


@pytest.mark.regression
def test_cart_total_calculated_correctly(logged_in_page, base_url):
    """Cart total matches the product price × quantity (server-side calculation)."""
    _add_headphones(logged_in_page, base_url)

    cp = CartPage(logged_in_page, base_url)
    cp.navigate()

    expected = f"{HEADPHONES_PRICE:.2f}"
    total_text = cp.cart_total_text()

    assert expected in total_text, \
        f"Expected total to contain '{expected}', got: '{total_text}'."
