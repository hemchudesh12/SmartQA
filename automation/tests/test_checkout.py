"""
automation/tests/test_checkout.py — Tests for Checkout module.

Module: checkout
Routes tested: /checkout, /order/success/<id>, /cart/ (post-checkout)
Markers: smoke, regression

Test inventory (3 tests):
  Smoke:      test_successful_checkout
  Regression: test_cart_cleared_after_checkout,
              test_checkout_missing_fields
"""

import re

import pytest

from automation.pages.cart_page import CartPage
from automation.pages.checkout_page import CheckoutPage
from automation.pages.products_page import ProductsPage
from automation.utils.test_data import CHECKOUT_DATA, KNOWN_PRODUCTS


HEADPHONES_ID = KNOWN_PRODUCTS["headphones"]["id"]


def _add_and_navigate_to_checkout(logged_in_page, base_url) -> CheckoutPage:
    """
    Shared setup:
      1. Add headphones to cart from the product listing.
      2. Navigate to the checkout page.
    Returns the CheckoutPage object ready for further interaction.
    """
    pp = ProductsPage(logged_in_page, base_url)
    pp.navigate()
    pp.add_to_cart(HEADPHONES_ID)

    chp = CheckoutPage(logged_in_page, base_url)
    chp.navigate()
    return chp


@pytest.mark.smoke
def test_successful_checkout(logged_in_page, base_url):
    """
    Completing checkout with valid data:
      - Redirects to /order/success/<id>
      - Order success page is displayed
      - Order ID element is present
    """
    chp = _add_and_navigate_to_checkout(logged_in_page, base_url)

    chp.fill_shipping(
        full_name=CHECKOUT_DATA["full_name"],
        address=CHECKOUT_DATA["address"],
        city=CHECKOUT_DATA["city"],
        postal_code=CHECKOUT_DATA["postal_code"],
        phone=CHECKOUT_DATA["phone"],
    )
    chp.submit()

    # Wait for redirect to order success URL
    logged_in_page.wait_for_url(re.compile(r".*/order/success/\d+"))

    assert logged_in_page.get_by_test_id("order-success").is_visible(), \
        "Order success confirmation should be visible after checkout."
    assert logged_in_page.get_by_test_id("order-id").is_visible(), \
        "Order ID should be displayed on the success page."


@pytest.mark.regression
def test_cart_cleared_after_checkout(logged_in_page, base_url):
    """After a successful checkout, the cart is empty."""
    chp = _add_and_navigate_to_checkout(logged_in_page, base_url)
    chp.fill_shipping(
        full_name=CHECKOUT_DATA["full_name"],
        address=CHECKOUT_DATA["address"],
        city=CHECKOUT_DATA["city"],
        postal_code=CHECKOUT_DATA["postal_code"],
        phone=CHECKOUT_DATA["phone"],
    )
    chp.submit()
    logged_in_page.wait_for_url(re.compile(r".*/order/success/\d+"))

    # Navigate to cart and assert it is empty
    cp = CartPage(logged_in_page, base_url)
    cp.navigate()

    assert cp.empty_cart_state.is_visible(), \
        "Cart should show empty state after a completed checkout."
    assert not cp.cart_table.is_visible(), \
        "Cart table should not be present when cart is empty."


@pytest.mark.regression
def test_checkout_missing_fields(logged_in_page, base_url):
    """
    Submitting the checkout form with all fields blank returns validation errors.
    The form is re-displayed with at least one flash error message.
    """
    chp = _add_and_navigate_to_checkout(logged_in_page, base_url)
    # Do NOT call fill_shipping — submit with blank fields
    chp.submit()

    # The route flashes one message per missing field
    flash_messages = logged_in_page.get_by_test_id("flash-message")
    assert flash_messages.count() >= 1, \
        "Expected at least one validation error message."
    assert "required" in flash_messages.first.inner_text().lower(), \
        "First error message should indicate a required field."
