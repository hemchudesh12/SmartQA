"""
app/checkout/routes.py — Checkout: collect shipping info, create order, clear cart.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.cart.utils import clear_cart, get_cart
from app.models import Order, OrderItem, Product

checkout_bp = Blueprint("checkout", __name__, url_prefix="/")


# ---------------------------------------------------------------------------
# Checkout page (GET = show form, POST = process)
# ---------------------------------------------------------------------------

@checkout_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart = get_cart()

    if not cart:
        flash("Your cart is empty. Add items before checking out.", "warning")
        return redirect(url_for("cart.view_cart"))

    # Build the order summary for the template
    items, total = _build_summary(cart)

    if not items:
        # All products in cart have been removed from the catalog
        clear_cart()
        flash("Your cart contained unavailable products and has been cleared.", "warning")
        return redirect(url_for("products.product_list"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        postal_code = request.form.get("postal_code", "").strip()
        phone = request.form.get("phone", "").strip()
        payment_method = request.form.get("payment_method", "cod")

        # Validate form fields
        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not address:
            errors.append("Address is required.")
        if not city:
            errors.append("City is required.")
        if not postal_code:
            errors.append("Postal code is required.")
        if not phone:
            errors.append("Phone number is required.")
        if payment_method not in ("cod", "demo_card"):
            errors.append("Please select a valid payment method.")

        if errors:
            for msg in errors:
                flash(msg, "danger")
            return render_template(
                "checkout/checkout.html", items=items, total=total
            )

        # ── Create order ────────────────────────────────────────────────
        order = Order(
            user_id=current_user.id,
            full_name=full_name,
            address=address,
            city=city,
            postal_code=postal_code,
            phone=phone,
            payment_method=payment_method,
            status="confirmed",
        )
        db.session.add(order)
        db.session.flush()  # assigns order.id before we add line items

        for entry in items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=entry["product"].id,
                quantity=entry["quantity"],
                unit_price=entry["product"].price,  # snapshot current price
            )
            db.session.add(order_item)

        order.calculate_total()   # server-side total — never trust browser
        db.session.commit()

        clear_cart()
        flash(f"Order #{order.id} placed successfully! Thank you.", "success")
        return redirect(url_for("checkout.order_success", order_id=order.id))

    return render_template("checkout/checkout.html", items=items, total=total)


# ---------------------------------------------------------------------------
# Order success page
# ---------------------------------------------------------------------------

@checkout_bp.route("/order/success/<int:order_id>")
@login_required
def order_success(order_id):
    order = db.get_or_404(Order, order_id)

    # Authorisation: only the order owner may view this page
    if order.user_id != current_user.id:
        flash("You are not authorised to view that order.", "danger")
        return redirect(url_for("index"))

    return render_template("checkout/success.html", order=order)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _build_summary(cart: dict) -> tuple:
    """
    Convert session cart dict → list of item dicts and grand total.
    Skips cart entries whose product no longer exists in the DB.
    """
    items = []
    total = 0.0
    for pid_str, qty in cart.items():
        product = db.session.get(Product, int(pid_str))
        if product:
            subtotal = product.price * qty
            total += subtotal
            items.append({"product": product, "quantity": qty, "subtotal": subtotal})
    return items, total
