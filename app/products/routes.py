"""
app/products/routes.py — Product catalog: list, detail, search.
"""

from flask import Blueprint, render_template, request

from app import db
from app.models import Product

products_bp = Blueprint("products", __name__, url_prefix="/")


# ---------------------------------------------------------------------------
# Product listing (with optional category filter)
# ---------------------------------------------------------------------------

@products_bp.route("/products")
def product_list():
    selected_category = request.args.get("category", "").strip()

    if selected_category:
        products = (
            Product.query
            .filter_by(category=selected_category)
            .order_by(Product.name)
            .all()
        )
    else:
        products = Product.query.order_by(Product.name).all()

    # Get distinct categories for the filter bar
    rows = db.session.execute(
        db.select(Product.category).distinct().order_by(Product.category)
    ).all()
    categories = [r[0] for r in rows]

    return render_template(
        "products/list.html",
        products=products,
        categories=categories,
        selected_category=selected_category,
    )


# ---------------------------------------------------------------------------
# Product detail
# ---------------------------------------------------------------------------

@products_bp.route("/product/<int:product_id>")
def product_detail(product_id):
    product = db.get_or_404(Product, product_id)
    return render_template("products/detail.html", product=product)


# ---------------------------------------------------------------------------
# Product search
# ---------------------------------------------------------------------------

@products_bp.route("/search")
def search():
    query = request.args.get("q", "").strip()
    results = []

    if query:
        results = (
            Product.query
            .filter(Product.name.ilike(f"%{query}%"))
            .order_by(Product.name)
            .all()
        )

    return render_template("products/search.html", results=results, query=query)
