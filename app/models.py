"""
models.py — Database models for SmartQA Demo Store.

All models are in one file intentionally:
  - Simple to understand and trace
  - SmartQA Phase 3+ maps this file to multiple test suites
  - No premature abstraction for a testing SUT

Tables:
  users         → User accounts
  products      → Product catalog
  orders        → Customer orders (post-checkout)
  order_items   → Line items per order
"""

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login_manager


# ---------------------------------------------------------------------------
# Flask-Login user loader
# ---------------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    """
    Registered user account.

    UserMixin provides: is_authenticated, is_active, is_anonymous, get_id()
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    orders = db.relationship("Order", back_populates="user", lazy="select")

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------

    def set_password(self, password: str) -> None:
        """Hash and store password. Never store plaintext."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True if the given password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class Product(db.Model):
    """
    A single product in the catalog.

    stock == 0  → item is unavailable / out of stock.
    """

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    price = db.Column(db.Float, nullable=False)           # stored in INR (₹)
    category = db.Column(db.String(80), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image_filename = db.Column(db.String(200), nullable=True)  # optional

    # Relationships
    order_items = db.relationship("OrderItem", back_populates="product", lazy="select")

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r} price={self.price}>"


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class Order(db.Model):
    """
    A completed customer order created at checkout.

    status values: 'pending', 'confirmed', 'cancelled'
    payment_method values: 'cod', 'demo_card'
    """

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Shipping info captured at checkout
    full_name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20), nullable=False)

    payment_method = db.Column(db.String(20), nullable=False, default="cod")
    status = db.Column(db.String(20), nullable=False, default="confirmed")

    # Total stored on the order — calculated server-side at checkout
    total = db.Column(db.Float, nullable=False, default=0.0)

    # Relationships
    user = db.relationship("User", back_populates="orders")
    items = db.relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def calculate_total(self) -> float:
        """Recalculate total from line items. Always call before saving."""
        self.total = sum(item.subtotal for item in self.items)
        return self.total

    def __repr__(self) -> str:
        return f"<Order id={self.id} user_id={self.user_id} total={self.total}>"


# ---------------------------------------------------------------------------
# OrderItem
# ---------------------------------------------------------------------------

class OrderItem(db.Model):
    """
    A single line item within an Order.

    unit_price is snapshotted at order time so historical orders are
    not affected if the product price changes later.
    """

    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False)   # snapshot at order time

    # Relationships
    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")

    @property
    def subtotal(self) -> float:
        return self.unit_price * self.quantity

    def __repr__(self) -> str:
        return (
            f"<OrderItem id={self.id} product_id={self.product_id} "
            f"qty={self.quantity} unit_price={self.unit_price}>"
        )
