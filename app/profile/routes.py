"""
app/profile/routes.py — User profile: view info + order history, update name.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


# ---------------------------------------------------------------------------
# Profile page
# ---------------------------------------------------------------------------

@profile_bp.route("/")
@login_required
def profile():
    # Eager-load orders and their items+products for the order history table
    orders = (
        current_user.orders
    )
    return render_template("profile/profile.html", user=current_user, orders=orders)


# ---------------------------------------------------------------------------
# Update profile (name only for Phase 1)
# ---------------------------------------------------------------------------

@profile_bp.route("/update", methods=["POST"])
@login_required
def update_profile():
    name = request.form.get("name", "").strip()

    if not name:
        flash("Name cannot be empty.", "danger")
        return redirect(url_for("profile.profile"))

    current_user.name = name
    db.session.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for("profile.profile"))
