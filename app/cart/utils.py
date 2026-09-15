# app/cart/utils.py — Shared cart helpers used by cart and checkout modules.
# Cart is stored in the Flask session as {str(product_id): quantity}.

from flask import session

CART_KEY = "cart"


def get_cart() -> dict:
    """Return the current session cart. Always returns a dict."""
    return session.get(CART_KEY, {})


def save_cart(cart: dict) -> None:
    """Persist cart dict back to session."""
    session[CART_KEY] = cart
    session.modified = True


def clear_cart() -> None:
    """Wipe the cart from session (called after successful checkout)."""
    session.pop(CART_KEY, None)
    session.modified = True
