"""
app/cart/routes.py — Shopping cart: view, add, remove, increase, decrease.

Cart data is stored in the Flask session as {str(product_id): quantity}.
All mutating operations are POST to prevent browser prefetch/back issues.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.cart.utils import get_cart, save_cart
from app.models import Product

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")


# ---------------------------------------------------------------------------
# View cart
# ---------------------------------------------------------------------------

@cart_bp.route("/")
@login_required
def view_cart():
    cart = get_cart()
    items = []
    total = 0.0

    for pid_str, qty in cart.items():
        product = db.session.get(Product, int(pid_str))
        if product:
            subtotal = product.price * qty
            total += subtotal
            items.append({"product": product, "quantity": qty, "subtotal": subtotal})

    return render_template("cart/cart.html", items=items, total=total)


# ---------------------------------------------------------------------------
# Add to cart
# ---------------------------------------------------------------------------

@cart_bp.route("/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    product = db.get_or_404(Product, product_id)

    if not product.in_stock:
        flash(f"'{product.name}' is out of stock.", "danger")
        return redirect(request.referrer or url_for("products.product_list"))

    cart = get_cart()
    pid = str(product_id)
    cart[pid] = cart.get(pid, 0) + 1
    save_cart(cart)

    flash(f"'{product.name}' added to cart.", "success")
    return redirect(request.referrer or url_for("products.product_list"))


# ---------------------------------------------------------------------------
# Remove from cart
# ---------------------------------------------------------------------------

@cart_bp.route("/remove/<int:product_id>", methods=["POST"])
@login_required
def remove_from_cart(product_id):
    cart = get_cart()
    cart.pop(str(product_id), None)
    save_cart(cart)
    flash("Item removed from cart.", "info")
    return redirect(url_for("cart.view_cart"))


# ---------------------------------------------------------------------------
# Increase quantity
# ---------------------------------------------------------------------------

@cart_bp.route("/increase/<int:product_id>", methods=["POST"])
@login_required
def increase_quantity(product_id):
    cart = get_cart()
    pid = str(product_id)
    if pid in cart:
        cart[pid] += 1
        save_cart(cart)
    return redirect(url_for("cart.view_cart"))


# ---------------------------------------------------------------------------
# Decrease quantity (removes item when quantity reaches 0)
# ---------------------------------------------------------------------------

@cart_bp.route("/decrease/<int:product_id>", methods=["POST"])
@login_required
def decrease_quantity(product_id):
    cart = get_cart()
    pid = str(product_id)
    if pid in cart:
        if cart[pid] > 1:
            cart[pid] -= 1
        else:
            cart.pop(pid)
        save_cart(cart)
    return redirect(url_for("cart.view_cart"))
