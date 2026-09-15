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

## Phase 4 — Data Collection & Validation Pipeline

SmartQA includes an automated historical data collection pipeline for capturing commit metadata and test execution metrics:

1. **Commit Metadata Collection**: `python tools/collect_git_metadata.py` extracts lines added/deleted, changed files, author, and commit messages into `data/commits.jsonl`.
2. **Test Result Capture**: PyTest hooks in `automation/conftest.py` capture test durations, statuses (PASS/FAIL/SKIP/ERROR), and metadata into `data/test_results.jsonl`.
3. **Flat Dataset Compilation**: `python tools/build_dataset.py` joins commits and test results on `commit_sha` to output `data/dataset.csv`.
4. **Data Integrity Validation**: `python tools/validate_dataset.py` validates referential integrity, schemas, and status values.

---

## Phase 5 — Feature Engineering & ML Dataset Pipeline

Phase 5 transforms validated Phase 4 historical execution data into a temporal, machine-learning-ready feature dataset.

### Pipeline Execution Commands

```bash
# 1. Generate engineered feature datasets
python tools/build_features.py

# 2. Validate feature dataset integrity and schema rules
python tools/validate_features.py

# 3. Run unit tests for feature extraction and leakage prevention
python -m pytest tools/tests/test_features.py -v
```

### Generated Datasets

- `data/features.csv`: Human-readable engineered dataset containing commit, test, historical, and interaction features.
- `data/features_encoded.csv`: Machine-ready numerical dataset prepared for Phase 6 model training.

### Feature Categories & Dictionary

| Category | Feature Name | Type | Description | Leakage Safe? |
|---|---|---|---|---|
| **Commit** | `lines_added` | Int | Number of lines inserted in commit | Yes |
| **Commit** | `lines_deleted` | Int | Number of lines removed in commit | Yes |
| **Commit** | `total_lines_changed` | Int | Total lines added + deleted | Yes |
| **Commit** | `changed_file_count` | Int | Count of files modified | Yes |
| **Commit** | `commit_message_length` | Int | Character count of commit message | Yes |
| **Commit** | `commit_message_word_count` | Int | Word count of commit message | Yes |
| **Commit** | `has_fix_keyword` | Binary | 1 if message contains fix/patch keywords | Yes |
| **Commit** | `has_feature_keyword` | Binary | 1 if message contains feat/feature keywords | Yes |
| **Commit** | `has_refactor_keyword` | Binary | 1 if message contains refactor/clean keywords | Yes |
| **Commit** | `has_bug_keyword` | Binary | 1 if message contains bug/issue/fail keywords | Yes |
| **Commit** | `has_test_keyword` | Binary | 1 if message contains test/coverage keywords | Yes |
| **Commit** | `changed_python_file_count` | Int | Number of `.py` files changed | Yes |
| **Commit** | `changed_test_file_count` | Int | Number of test files changed | Yes |
| **Commit** | `changed_app_file_count` | Int | Number of `app/` files changed | Yes |
| **Test** | `test_name_length` | Int | Character length of test function name | Yes |
| **Test** | `test_name_word_count` | Int | Word count of test function name | Yes |
| **Test** | `is_smoke_test` | Binary | 1 if tagged `@pytest.mark.smoke` | Yes |
| **Test** | `is_regression_test` | Binary | 1 if tagged `@pytest.mark.regression` | Yes |
| **Historical** | `previous_test_runs` | Int | Total runs of test prior to current commit | Yes |
| **Historical** | `previous_failures` | Int | Total failures of test prior to current commit | Yes |
| **Historical** | `historical_failure_rate` | Float | `previous_failures / previous_test_runs` (0.0 if cold start) | Yes |
| **Historical** | `previous_run_failure_rate` | Float | Failure rate of immediately preceding run | Yes |
| **Historical** | `average_previous_duration` | Float | Mean duration (sec) of prior executions | Yes |
| **Historical** | `previous_duration_variance` | Float | Variance of prior execution durations | Yes |
| **Historical** | `days_since_previous_execution` | Float | Days elapsed since prior test run | Yes |
| **Interaction** | `test_file_changed` | Binary | 1 if test file was modified in commit | Yes |
| **Interaction** | `test_area_changed` | Binary | 1 if test domain/module was modified in commit | Yes |
| **Interaction** | `commit_size_x_hist_failure_rate` | Float | `total_lines_changed * historical_failure_rate` | Yes |
| **Target** | `test_failed` | Binary | **Target Label**: `0` for PASS, `1` for FAIL/ERROR (SKIP excluded) | Target |

### Key Design & Data Integrity Principles

1. **Temporal Leakage Safeguard**: Historical features are calculated strictly using observations recorded *prior* to the current commit. Current row outcomes never contaminate historical counters.
2. **Cold-Start Strategy**: Unobserved tests default to `previous_test_runs=0`, `historical_failure_rate=0.0`, and `average_previous_duration=0.0` without row dropping.
3. **Target Definition**: PASS = `0`, FAIL = `1`, ERROR = `1`. SKIP records are excluded from supervised training sets.

---

## Phase 6 — ML Failure-Risk Prediction

Phase 6 trains a baseline ML classifier to predict which tests are likely to fail for a given commit.

### ML Objective

> Given the features available **before** a test executes for a commit, what is the probability that this test will fail?

Output: `P(test_failed = 1)` — a failure-risk probability for each (commit, test) pair.

### Pipeline Architecture

```
Historical features (data/features_encoded.csv)
          ↓
Temporal commit-level split (earliest 80% → train, latest 20% → test)
          ↓
StandardScaler (fit only on training data)
          ↓
LogisticRegression (random_state=42, class_weight="balanced")
          ↓
Failure probability P(test_failed=1)
          ↓
Phase 7 test prioritization (future)
```

### Execution Commands

```bash
# 1. Generate the ML feature dataset (if not already done)
python tools/build_features.py

# 2. Train the model
python tools/train_model.py

# 3. Evaluate the model
python tools/evaluate_model.py

# 4. Run Phase 6 unit tests
python -m pytest tools/tests/test_model.py -v

# 5. Run all tools tests together
python -m pytest tools/tests -v
```

### Temporal Train/Test Split

**Random split is explicitly avoided.** Tests from the same commit must all go to the same set.

The split works on unique commits sorted by temporal order:

| Set | Commits | Rule |
|---|---|---|
| Training | Earliest 80% of unique commits | Historical knowledge |
| Testing  | Latest 20% of unique commits | Simulates future prediction |

No commit SHA ever appears in both training and test sets.

### Why Random Split is Wrong for SmartQA

SmartQA simulates: *"Given a new commit, which tests will fail?"*

If future commits contaminate the training set, historical features (like `historical_failure_rate`) would encode future information — making the model appear better than it is.

Temporal split prevents this by strictly ordering data.

### Leakage Prevention

Fields excluded from X (not available before a test executes):

| Field | Reason |
|---|---|
| `test_failed` | **Target label** — never in X |
| `status` | Post-execution result |
| `failure_message` | Post-execution result |
| `duration_sec` | Only known after execution |
| `commit_sha` | Identifier, not feature |
| `test_nodeid` | Identifier, not feature |

### Model

| Setting | Value |
|---|---|
| Algorithm | Logistic Regression |
| Library | scikit-learn |
| `random_state` | 42 |
| `class_weight` | `"balanced"` |
| Scaler | StandardScaler (fit on train only) |
| Solver | lbfgs |

`class_weight="balanced"` addresses the severe class imbalance by automatically upweighting FAIL examples in the loss function.

### Class Imbalance

Current dataset: **~0.69% failure rate** (1 FAIL out of 145 rows).

This is far too little for a valid classifier. The pipeline handles this explicitly:

- If the **training** set contains only one class → training is **skipped with a clear message**
- SMOTE / synthetic oversampling is NOT applied in Phase 5 or 6
- This is correct scientific behavior, not a software bug

### Evaluation Metrics

When both classes exist in the test set:

| Metric | Notes |
|---|---|
| Accuracy | Overall correctness |
| Precision (FAIL) | Of predicted FAILs, how many were real? |
| **Recall (FAIL)** | **Most important: of real FAILs, how many were caught?** |
| F1-score | Harmonic mean of precision and recall |
| ROC-AUC | Probability ranking quality |
| PR-AUC | Precision-recall tradeoff |

**Recall** is the primary metric because missing a test that will fail (False Negative) means a defect goes undetected — the worst outcome for SmartQA.

Metrics are reported as `undefined` when the test set lacks both classes — honest reporting only.

### Generated Artifacts

| File | Description |
|---|---|
| `models/failure_predictor.joblib` | Trained sklearn Pipeline (gitignored, regeneratable) |
| `models/model_metadata.json` | Training config and dataset statistics (gitignored) |
| `data/predictions.csv` | Per-row predictions on test set (gitignored) |
| `data/evaluation_report.json` | Full metrics report (gitignored) |

### Current Dataset Limitation

With only **1 genuine FAIL** in the current historical dataset:

- The temporal split produces a training period with **0 FAIL examples**
- Training is **correctly skipped** with the message: `INSUFFICIENT CLASS DIVERSITY`
- The pipeline infrastructure is **complete and correct**
- Training will activate automatically once more real failures are collected

**This is an honest result, not a failure of the implementation.**

### Known Limitations

1. Only 1 FAIL in 145 rows — insufficient for a production-ready model
2. All data was collected on a single day — temporal diversity is limited
3. Only one test runner (Chromium) — no multi-browser failure patterns
4. 5 unique commits — temporal split leaves minimal test data
5. Logistic Regression assumes linear decision boundary — may underfit if relationships are nonlinear (Random Forest can be added in Phase 6b)
