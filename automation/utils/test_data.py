"""
automation/utils/test_data.py — All test constants in one place.

DO NOT scatter hard-coded values across test files.
Import from here instead.

Product IDs are deterministic because seed.py always drops and recreates
the database, resetting SQLite's autoincrement counter to 1.
Insertion order in seed.py determines IDs 1–12.
"""

import os

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")


# ---------------------------------------------------------------------------
# Test user — matches seed.py TEST_USER exactly
# ---------------------------------------------------------------------------

VALID_USER = {
    "name": "Test User",
    "email": "test@smartqa.com",
    "password": "Test@1234",
}

INVALID_USER = {
    "email": "nobody@nowhere.com",
    "password": "wrongpassword",
}


# ---------------------------------------------------------------------------
# Known products — IDs match seed.py insertion order
# ---------------------------------------------------------------------------
#
# Seed insertion order → SQLite autoincrement IDs:
#   1  Wireless Noise-Cancelling Headphones  Electronics  ₹4999  in stock
#   2  Mechanical Keyboard                   Electronics  ₹3499  in stock
#   3  USB-C Hub 7-in-1                      Electronics  ₹1799  in stock
#   4  Portable Bluetooth Speaker            Electronics  ₹2299  in stock
#   5  Smart LED Desk Lamp                   Electronics  ₹999   in stock
#   6  Laptop Sleeve 15-inch                 Accessories  ₹599   in stock
#   7  Ergonomic Mouse Pad XL                Accessories  ₹449   in stock
#   8  Phone Stand Adjustable                Accessories  ₹349   in stock
#   9  Cable Management Kit                  Accessories  ₹299   in stock
#  10  Digital Kitchen Scale                 Home         ₹799   in stock
#  11  Air Purifier Compact                  Home         ₹3999  in stock
#  12  Stainless Steel Water Bottle 1L       Home         ₹699   OUT OF STOCK
# ---------------------------------------------------------------------------

KNOWN_PRODUCTS = {
    "headphones": {
        "id": 1,
        "name": "Wireless Noise-Cancelling Headphones",
        "price": 4999.0,
        "category": "Electronics",
        "in_stock": True,
    },
    "keyboard": {
        "id": 2,
        "name": "Mechanical Keyboard",
        "price": 3499.0,
        "category": "Electronics",
        "in_stock": True,
    },
    "water_bottle": {
        "id": 12,
        "name": "Stainless Steel Water Bottle 1L",
        "price": 699.0,
        "category": "Home",
        "in_stock": False,   # intentionally OOS in seed data
    },
}

# Category counts (must match seed.py PRODUCTS list)
CATEGORY_COUNTS = {
    "Electronics": 5,
    "Accessories": 4,
    "Home": 3,
    "all": 12,
}

# ---------------------------------------------------------------------------
# Checkout form data
# ---------------------------------------------------------------------------

CHECKOUT_DATA = {
    "full_name": "Test Shopper",
    "address": "123 Automation Lane",
    "city": "Mumbai",
    "postal_code": "400001",
    "phone": "9876543210",
    "payment_method": "cod",
}

# ---------------------------------------------------------------------------
# Non-existent resource IDs for 404 / negative tests
# ---------------------------------------------------------------------------

NONEXISTENT_PRODUCT_ID = 9999
