"""
seed.py — Deterministic seed script for SmartQA Demo Store.

Usage:
    python seed.py

Behaviour:
  - Drops and recreates all tables (safe wipe).
  - Inserts 1 test user.
  - Inserts 12 products across 3 categories.

Running multiple times always produces an identical database state.
This is critical for Phase 2 test repeatability.

Test credentials (also documented in README.md):
    Email   : test@smartqa.com
    Password: Test@1234
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Order, OrderItem, Product, User  # noqa: F401 — needed for create_all

app = create_app("development")

# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

TEST_USER = {
    "name": "Test User",
    "email": "test@smartqa.com",
    "password": "Test@1234",
}

PRODUCTS = [
    # ── Electronics ────────────────────────────────────────────────────────
    {
        "name": "Wireless Noise-Cancelling Headphones",
        "description": (
            "Over-ear Bluetooth headphones with active noise cancellation, "
            "30-hour battery life, and foldable design. Ideal for commuters and remote workers."
        ),
        "price": 4999.0,
        "category": "Electronics",
        "stock": 25,
    },
    {
        "name": "Mechanical Keyboard",
        "description": (
            "Compact TKL mechanical keyboard with blue switches, RGB backlight, "
            "and USB-C connectivity. Anti-ghosting with N-key rollover."
        ),
        "price": 3499.0,
        "category": "Electronics",
        "stock": 15,
    },
    {
        "name": "USB-C Hub 7-in-1",
        "description": (
            "Expand your laptop ports: HDMI 4K, 3× USB-A 3.0, SD card reader, "
            "microSD reader, and 100W USB-C PD pass-through."
        ),
        "price": 1799.0,
        "category": "Electronics",
        "stock": 40,
    },
    {
        "name": "Portable Bluetooth Speaker",
        "description": (
            "Waterproof IPX6 Bluetooth 5.0 speaker with 360° sound, "
            "12-hour playback, and built-in power bank."
        ),
        "price": 2299.0,
        "category": "Electronics",
        "stock": 30,
    },
    {
        "name": "Smart LED Desk Lamp",
        "description": (
            "Touch-controlled desk lamp with 5 colour temperatures, "
            "10 brightness levels, USB charging port, and memory function."
        ),
        "price": 999.0,
        "category": "Electronics",
        "stock": 50,
    },
    # ── Accessories ────────────────────────────────────────────────────────
    {
        "name": "Laptop Sleeve 15-inch",
        "description": (
            "Water-resistant neoprene sleeve with accessory pocket. "
            "Compatible with 14–15.6-inch laptops."
        ),
        "price": 599.0,
        "category": "Accessories",
        "stock": 60,
    },
    {
        "name": "Ergonomic Mouse Pad XL",
        "description": (
            "900×400mm extended desk mat with stitched edges, "
            "non-slip rubber base, and smooth micro-weave surface."
        ),
        "price": 449.0,
        "category": "Accessories",
        "stock": 80,
    },
    {
        "name": "Phone Stand Adjustable",
        "description": (
            "Aluminium foldable phone and tablet stand. "
            "Adjustable angle, compatible with all devices 4–13 inches."
        ),
        "price": 349.0,
        "category": "Accessories",
        "stock": 70,
    },
    {
        "name": "Cable Management Kit",
        "description": (
            "30-piece kit: velcro ties, cable clips, cable sleeves, "
            "and labels. Keeps your desk clean and organized."
        ),
        "price": 299.0,
        "category": "Accessories",
        "stock": 100,
    },
    # ── Home ───────────────────────────────────────────────────────────────
    {
        "name": "Digital Kitchen Scale",
        "description": (
            "Precision scale with 1g accuracy up to 5kg. "
            "Tare function, unit conversion, and stainless steel platform."
        ),
        "price": 799.0,
        "category": "Home",
        "stock": 35,
    },
    {
        "name": "Air Purifier Compact",
        "description": (
            "HEPA + activated carbon 3-stage filter. "
            "Coverage up to 200 sq ft, whisper-quiet 25dB sleep mode, auto-shutoff timer."
        ),
        "price": 3999.0,
        "category": "Home",
        "stock": 20,
    },
    {
        "name": "Stainless Steel Water Bottle 1L",
        "description": (
            "Double-wall vacuum insulated. "
            "Keeps drinks cold 24h, hot 12h. Leak-proof lid, BPA-free."
        ),
        "price": 699.0,
        "category": "Home",
        "stock": 0,   # intentionally out of stock — for OOS test cases
    },
]


# ---------------------------------------------------------------------------
# Seed execution
# ---------------------------------------------------------------------------

def seed():
    instance_dir = os.path.join(os.path.dirname(__file__), "instance")
    os.makedirs(instance_dir, exist_ok=True)

    with app.app_context():
        print("[seed] Dropping all tables...")
        db.drop_all()

        print("[seed] Creating all tables...")
        db.create_all()

        # ── Test user ──────────────────────────────────────────────────
        user = User(name=TEST_USER["name"], email=TEST_USER["email"])
        user.set_password(TEST_USER["password"])
        db.session.add(user)
        print(f"[seed] Created user: {user.email}")

        # ── Products ───────────────────────────────────────────────────
        for p in PRODUCTS:
            product = Product(**p)
            db.session.add(product)
        print(f"[seed] Inserted {len(PRODUCTS)} products.")

        db.session.commit()
        print("[seed] ✓ Database seeded successfully.")
        print()
        print("  Test credentials:")
        print(f"    Email   : {TEST_USER['email']}")
        print(f"    Password: {TEST_USER['password']}")


if __name__ == "__main__":
    seed()
