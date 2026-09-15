# SmartQA Demo Store

A minimal e-commerce web application built as the **System Under Test (SUT)** for **SmartQA** — an ML-based test prioritization system.

This application is intentionally simple, deterministic, and modular. It is designed to be tested by an automated Playwright + PyTest suite in Phase 2, and analyzed by SmartQA's ML engine in Phase 3.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Web Framework | Flask 3.x |
| Database | SQLite (via Flask-SQLAlchemy) |
| Auth Sessions | Flask-Login |
| Passwords | Werkzeug (password_hash) |
| Templates | Jinja2 |
| Frontend | Vanilla HTML + CSS |

---

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd smartqa
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the virtual environment

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Database Setup

Run the seed script to create and populate the SQLite database:

```bash
python seed.py
```

This will:
- Drop and recreate all tables
- Insert 1 test user
- Insert 12 products across 3 categories

> **The seed process is fully repeatable.** Running `python seed.py` again resets the database to a clean known state — which is required for reliable automated testing.

---

## Running the Application

```bash
python run.py
```

The application starts at: **http://127.0.0.1:5000**

---

## Test Credentials

The following account is created by `seed.py`:

| Field | Value |
|---|---|
| **Email** | `test@smartqa.com` |
| **Password** | `Test@1234` |

---

## Application Modules

### Authentication (`/login`, `/register`, `/logout`)
- User registration with name, email, and password
- Login with email + password
- Session-based authentication via Flask-Login
- `@login_required` protection on cart, checkout, and profile

### Products (`/products`, `/product/<id>`)
- 12 products across 3 categories: Electronics, Accessories, Home
- Category filter on the listing page
- Individual product detail pages at stable URLs

### Search (`/search?q=...`)
- Case-insensitive search by product name
- Handles: matching results, no results, empty query

### Cart (`/cart`)
- Session-based shopping cart
- Add, remove, increase, decrease quantity
- Server-side total calculation
- Requires login

### Checkout (`/checkout`, `/order/success/<id>`)
- Collects shipping details and payment method (Cash on Delivery / Demo Card)
- Creates an Order and OrderItems in the database
- Clears the cart after successful checkout
- Requires login

### Profile (`/profile`)
- View name, email, and join date
- Update display name
- View full order history with line items and totals

---

## Resetting the Database

To reset to a clean state at any time:

```bash
python seed.py
```

---

## Project Structure

```
smartqa/
├── app/
│   ├── __init__.py          # App factory (create_app)
│   ├── models.py            # User, Product, Order, OrderItem
│   ├── auth/
│   │   └── routes.py        # /login, /register, /logout
│   ├── products/
│   │   └── routes.py        # /products, /product/<id>, /search
│   ├── cart/
│   │   ├── routes.py        # /cart and cart operations
│   │   └── utils.py         # Session cart helpers
│   ├── checkout/
│   │   └── routes.py        # /checkout, /order/success/<id>
│   ├── profile/
│   │   └── routes.py        # /profile, /profile/update
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS + JS
├── instance/
│   └── smartqa.db           # SQLite database (git-ignored)
├── config.py                # Dev / Testing / Production configs
├── seed.py                  # Deterministic database seeder
├── run.py                   # Application entry point
└── requirements.txt
```

---

## Testability

All important UI elements carry stable `data-testid` attributes:

| Element | Selector |
|---|---|
| Login email field | `[data-testid="login-email"]` |
| Login submit | `[data-testid="login-button"]` |
| Register form | `[data-testid="register-form"]` |
| Product card (by id) | `[data-testid="product-card-{id}"]` |
| Add to cart (by id) | `[data-testid="add-to-cart-{id}"]` |
| Cart item row | `[data-testid="cart-item-{id}"]` |
| Cart total | `[data-testid="cart-total"]` |
| Checkout form | `[data-testid="checkout-form"]` |
| Checkout submit | `[data-testid="checkout-submit"]` |
| Order ID on success | `[data-testid="order-id"]` |
| Flash messages | `[data-testid="flash-message"]` |

---

## Phase 2 — Automated Testing Suite

SmartQA includes a complete automated testing suite built with **Playwright + PyTest** using the **Page Object Model (POM)** architecture.

### Running Tests Locally

First, ensure the application server is running in a separate terminal:

```bash
python seed.py
python run.py
```

In a second terminal:

```bash
# Run all 33 automated tests
pytest

# Verbose execution output
pytest -v

# Run by test markers
pytest -m smoke
pytest -m regression

# Run specific test modules
pytest automation/tests/test_auth.py
pytest automation/tests/test_products.py
pytest automation/tests/test_cart.py
pytest automation/tests/test_checkout.py
pytest automation/tests/test_profile.py

# Visible browser execution (for debugging)
pytest --headed
```

Reports are automatically generated at `reports/report.html`. Failure screenshots are captured under `reports/screenshots/`.

---

## Phase 3 — CI/CD Integration (GitHub Actions)

Every push and pull request triggers an automated CI pipeline via **GitHub Actions** (`.github/workflows/smartqa-tests.yml`).

### CI Pipeline Steps

1. **Environment Setup**: Provisions Python 3.10 on `ubuntu-latest`.
2. **Dependency Provisioning**: Installs Python dependencies (`requirements.txt`) and Playwright Chromium with Linux OS system libraries (`playwright install --with-deps chromium`).
3. **Database Initialization**: Runs `python seed.py` to create a fresh, clean database state.
4. **Server Startup**: Starts the Flask server in the background on port `5000`.
5. **Health Check**: Polls `http://127.0.0.1:5000/` until an `HTTP 200 OK` readiness response is received.
6. **Automated Test Execution**: Executes `pytest -v` across the entire 33-test suite.
7. **Artifact Collection**: HTML test reports (`reports/report.html`) and failure screenshots are archived and available for download under the workflow run's **Artifacts** section (retained for 14 days).

---

## Future SmartQA ML Integration (Phase 4+)

With a reliable CI execution pipeline established, SmartQA collects historical test run results to:
1. Analyze code changes per commit.
2. Map source diffs to failure risks.
3. Predict high-risk tests using ML models (Logistic Regression, Random Forest).
4. Prioritize and execute risky tests first.
5. Measure APFD (Average Percentage of Faults Detected).

