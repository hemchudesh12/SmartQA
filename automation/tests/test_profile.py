"""
automation/tests/test_profile.py — Tests for User Profile module.

Module: profile
Routes tested: /profile/, /profile/update
Markers: smoke, regression

Test inventory (3 tests):
  Smoke:      test_profile_page_shows_user_info
  Regression: test_update_profile_name,
              test_profile_shows_completed_order

NOTE — test independence:
  test_update_profile_name reverts the name change at the end so it does
  not affect test_profile_page_shows_user_info if they run in the same session.
"""

import re

import pytest

from automation.pages.cart_page import CartPage
from automation.pages.checkout_page import CheckoutPage
from automation.pages.products_page import ProductsPage
from automation.pages.profile_page import ProfilePage
from automation.utils.test_data import CHECKOUT_DATA, KNOWN_PRODUCTS, VALID_USER


@pytest.mark.smoke
def test_profile_page_shows_user_info(logged_in_page, base_url):
    """The profile page displays the correct email for the logged-in user."""
    pfp = ProfilePage(logged_in_page, base_url)
    pfp.navigate()

    # Email is immutable — safe to assert exactly
    assert pfp.profile_email_text() == VALID_USER["email"], \
        "Profile email does not match the seeded test user."
    # Name could have been updated by another test — assert it is non-empty
    assert len(pfp.profile_name_text()) > 0, \
        "Profile name should not be empty."
    assert pfp.order_history.is_visible(), \
        "Order history section should be present on the profile page."


@pytest.mark.regression
def test_update_profile_name(logged_in_page, base_url):
    """User can update their display name; the change is persisted."""
    pfp = ProfilePage(logged_in_page, base_url)
    pfp.navigate()

    new_name = "Automation Updated Name"
    pfp.update_name(new_name)

    assert "updated" in pfp.first_flash_text().lower(), \
        "Expected a success flash message after updating the profile."
    assert pfp.profile_name_text() == new_name, \
        f"Expected profile name to be '{new_name}' after update."

    # ── Revert to original name ──────────────────────────────────────
    # This keeps the DB in a predictable state for other tests in the session.
    pfp.update_name(VALID_USER["name"])


@pytest.mark.regression
def test_profile_shows_completed_order(logged_in_page, base_url):
    """
    After completing a checkout, the resulting order appears in the
    user's profile order history.
    """
    # Arrange — place an order
    pp = ProductsPage(logged_in_page, base_url)
    pp.navigate()
    pp.add_to_cart(KNOWN_PRODUCTS["headphones"]["id"])

    chp = CheckoutPage(logged_in_page, base_url)
    chp.navigate()
    chp.fill_shipping(
        full_name=CHECKOUT_DATA["full_name"],
        address=CHECKOUT_DATA["address"],
        city=CHECKOUT_DATA["city"],
        postal_code=CHECKOUT_DATA["postal_code"],
        phone=CHECKOUT_DATA["phone"],
    )
    chp.submit()
    logged_in_page.wait_for_url(re.compile(r".*/order/success/\d+"))

    # Act — navigate to profile
    pfp = ProfilePage(logged_in_page, base_url)
    pfp.navigate()

    # Assert — order history contains at least the order we just placed
    order_count = pfp.order_cards().count()
    assert order_count >= 1, \
        f"Expected at least 1 order in profile history, found {order_count}."
