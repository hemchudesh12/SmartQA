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

---

## Phase 7 — Test Prioritization

Phase 7 uses the failure probabilities produced by Phase 6 to determine the execution order of the test suite. **High-risk tests execute first.**

### What Prioritization Means

Prioritization does **not** skip tests. It reorders them.

> The full test suite always executes. Tests predicted to fail are moved to the front so that failures are discovered earlier in the CI run.

### Why Failure Probability Drives Priority

SmartQA's ML model outputs `P(test_failed = 1)` for each test given a commit's features. A higher probability means the test is more likely to fail for this commit. Running these tests first gives the fastest signal about regressions.

### Ranking Algorithm

```
PRIMARY:    predicted_failure_probability  DESC  (highest risk first)
TIE-BREAK:  test_nodeid                    ASC   (alphabetical, deterministic)
```

**No random ordering. No dictionary insertion order. No shuffling.**

#### Example

| Test | Predicted Probability |
|---|---|
| `test_B` | 0.81 |
| `test_D` | 0.67 |
| `test_C` | 0.44 |
| `test_A` | 0.12 |

**Before prioritization (default pytest order):**
```
test_A → test_B → test_C → test_D
```

**After prioritization:**
```
test_B → test_D → test_C → test_A
```

The system executes tests predicted to be most likely to fail first.

### Missing Prediction Policy

Some tests may not have a prediction (new tests, historical gaps):

| Situation | Placement |
|---|---|
| Valid probability available | Ranked by probability (first group) |
| No prediction / invalid probability | Appended after all predicted tests |
| Multiple unpredicted tests | Sorted alphabetically by test_nodeid |

**No test is ever dropped.**

### Invalid Probability Handling

The engine validates every probability value. Invalid values are treated as missing.

Invalid examples: `NaN`, empty string, negative, `> 1.0`, non-numeric.

### No-Test-Loss Guarantee

The prioritizer explicitly validates:

- `prioritized_count == discovered_count`
- No duplicate test node IDs
- All discovered tests appear in output

If validation fails, the script exits with a non-zero code.

### Execution Commands

```bash
# 1. Generate prioritized test order (from Phase 6 predictions)
python tools/prioritize_tests.py

# 2. Validate the generated prioritization
python tools/validate_prioritization.py

# 3. Run Phase 7 unit tests
python -m pytest tools/tests/test_prioritization.py -v

# 4. Run the full tool test suite (Phase 4 + 5 + 6 + 7)
python -m pytest tools/tests -v
```

### CI Integration

The GitHub Actions workflow integrates prioritization into the CI pipeline:

```
Build Phase 5 features
    ↓
Train Phase 6 predictor (continue-on-error)
    ↓
Generate prioritized order (continue-on-error)
    ↓
If prioritized_nodeids.txt exists:
    Run pytest with tests in priority order
Else:
    Fallback: Run normal pytest (full suite)
```

**The full test suite always runs.** Prioritization only changes the order.

### Fallback Behavior

If predictions or prioritization cannot be generated (e.g., model not yet trained):

```
[SmartQA] Prioritization unavailable. Falling back to baseline pytest.
```

The CI pipeline uses `continue-on-error: true` for Phase 6/7 steps so that a missing model never blocks CI.

### Determinism

Given identical predictions and identical discovered tests, the priority order is always identical. This is verified by automated tests.

### Distinction: Prediction vs. Prioritization

| Phase 6 — Prediction | Phase 7 — Prioritization |
|---|---|
| "How likely is this test to fail?" | "In what order should tests execute?" |
| Output: `P(test_failed = 1)` | Output: ranked list of test node IDs |
| One-time model training | Per-run ordering decision |

### Leakage Rule

`actual_test_failed` (historical outcome) is **never used** as a ranking signal. Only `predicted_failure_probability` drives priority order.

This is enforced by the prioritization engine design: the `prioritize()` function receives only the predicted probabilities, never the actual historical labels.

### Generated Artifacts

| File | Description |
|---|---|
| `data/prioritized_tests.csv` | Full ranked test list with probabilities (gitignored) |
| `data/prioritized_nodeids.txt` | One test node ID per line in priority order (gitignored, used by CI) |

### Known Limitations

1. Phase 6 model training is currently skipped (insufficient failure data) — prioritization runs in "all-unpredicted" mode, producing alphabetical ordering
2. Alphabetical fallback is still deterministic and correct — all tests are preserved
3. Test discovery requires Python environment with test dependencies installed
4. Shell array approach in CI uses `mapfile` (bash-specific, standard on ubuntu-latest)

---

## Phase 8 — Integration, Evaluation, and Dashboard

Phase 8 completes the SmartQA pipeline by adding a retrospective evaluation framework and a local monitoring dashboard.

### Components

#### 1. Prioritization Evaluation (`tools/evaluate_prioritization.py`)

Computes empirical metrics comparing baseline vs SmartQA test ordering using real historical data.

```bash
python tools/evaluate_prioritization.py
```

**Evaluation Type: RETROSPECTIVE**

The evaluation answers: *"If we had used the SmartQA prioritized order in historical runs that had failures, would we have detected failures sooner?"*

This is NOT a prospective (blind holdout) evaluation. The current dataset has limited failure diversity (1 genuine failure in 144 rows), so results are informative but should be interpreted with caution.

**Metrics computed:**

| Metric | Description |
|---|---|
| First-failure rank (baseline) | Position of first failure in default pytest order |
| First-failure rank (SmartQA) | Position of first failure in SmartQA priority order |
| First-failure fraction | Rank / total tests (lower = faster detection) |
| First-failure rank improvement | Baseline rank − SmartQA rank (positive = SmartQA wins) |
| APFD (baseline) | Average Percentage of Faults Detected — baseline order |
| APFD (SmartQA) | Average Percentage of Faults Detected — SmartQA order |

**APFD formula:**

```
APFD = 1 - (ΣTFi) / (n × m) + 1 / (2n)

where:
    TFi = 1-based position of the i-th failing test
    n   = total tests in ordering
    m   = total failing tests

APFD = 1.0 → all failures appear first (perfect prioritization)
APFD = 0.0 → all failures appear last (worst possible order)
```

**Honest Limitations:**

- 1 genuine failure in the dataset: APFD is computed on a single data point and has high variance
- The model training set includes the failure commit — evaluation is retrospective, not fully independent
- More failure data is required for statistically meaningful evaluation
- The pipeline is complete and correct; results will improve as more historical failures accumulate

#### 2. Dashboard (`dashboard/app.py`)

A local Flask dashboard that reads SmartQA-generated artifacts and presents them in a clean, structured interface.

```bash
python dashboard/app.py
```

Dashboard available at: **http://127.0.0.1:5001/**

The dashboard is READ-ONLY. It never writes to any data files and does not connect to the main application (port 5000).

**Dashboard Sections:**

| Section | Description |
|---|---|
| 1. Overview | Stats: total tests, predictions, runs, commits, failures, model status |
| 2. Risk Distribution | Count of tests by risk tier (High / Medium / Low / No Prediction) |
| 3. Test Risk Table | Full prioritized list with failure probability and risk badge |
| 4. Execution Results | Latest test run — PASS/FAIL/SKIP per test with duration |
| 5. Prioritization Comparison | Side-by-side baseline vs SmartQA order |
| 6. Evaluation Metrics | First-failure ranks, APFD, Phase 6 model classification metrics |
| 7. Historical Trend | Per-run fail rate and test count across all historical runs |

**JSON API endpoints:**

| Endpoint | Description |
|---|---|
| `GET /api/overview` | Overview statistics |
| `GET /api/risk` | Full test risk table |
| `GET /api/risk-distribution` | Risk tier counts |
| `GET /api/latest-run` | Latest run results |
| `GET /api/trend` | Historical trend data |
| `GET /api/prioritization` | Baseline vs SmartQA comparison |
| `GET /api/evaluation` | Evaluation metrics |

#### 3. Phase 8 Unit Tests (`tools/tests/test_evaluation.py`)

38 unit tests covering the evaluation module. All test data is labeled as FIXTURE DATA — synthetic data for mathematical verification only.

```bash
python -m pytest tools/tests/test_evaluation.py -v
```

Tests cover:
- `first_failure_position` — 7 tests (boundary cases, empty inputs, multiple failures)
- `compute_apfd` — 9 tests (formula correctness, boundary values, monotonicity)
- `apply_smartqa_order_to_run` — 6 tests (ordering, no-test-drop guarantee)
- `evaluate_run` — 5 tests (metrics, schema validation, no fabrication)
- `compute_dataset_stats` — 5 tests (counting, failure rate formula)
- Grouping helpers — 5 tests
- File loading — 5 tests (missing file, empty file, malformed JSONL)
- Dashboard data loader — 8 tests (all graceful-default contracts)

### Pipeline Execution — Phase 8

```bash
# 1. Run full pipeline (Phases 4–7 must be run first)
python tools/collect_git_metadata.py
python tools/build_features.py
python tools/train_model.py
python tools/evaluate_model.py
python tools/prioritize_tests.py

# 2. Phase 8 — Compute prioritization evaluation
python tools/evaluate_prioritization.py

# 3. Phase 8 — Run Phase 8 unit tests
python -m pytest tools/tests/test_evaluation.py -v

# 4. Phase 8 — Run all SmartQA tool tests
python -m pytest tools/tests/ -v

# 5. Phase 8 — Start monitoring dashboard
python dashboard/app.py
# → http://127.0.0.1:5001/
```

### Generated Artifacts

| File | Phase | Description |
|---|---|---|
| `data/prioritization_evaluation.json` | 8 | Retrospective evaluation: first-failure ranks, APFD, dataset stats |

### CI Integration

Phase 8 adds the following steps to the GitHub Actions pipeline:

```
...Phase 7 prioritization...
       ↓
Evaluate Failure Predictor (Phase 6, continue-on-error)
       ↓
Run PyTest Suite — Prioritized Order
       ↓
Build ML Dataset (Phase 4 denormalization)
       ↓
Validate Dataset Integrity (Phase 4)
       ↓
Evaluate Prioritization (Phase 8, continue-on-error)
       ↓
Run Phase 8 Unit Tests (continue-on-error)
       ↓
Upload Artifacts (data/, models/model_metadata.json, reports/)
```

All Phase 8 CI steps use `continue-on-error: true` so that missing data (e.g., no failures yet) never blocks the pipeline.

### Project Structure (Phase 8 additions)

```
smartqa/
├── tools/
│   ├── evaluate_prioritization.py     [NEW Phase 8] Retrospective evaluation
│   └── tests/
│       └── test_evaluation.py         [NEW Phase 8] 38 evaluation unit tests
├── dashboard/
│   ├── __init__.py                    [NEW Phase 8] Package init
│   ├── app.py                         [NEW Phase 8] Flask dashboard server (port 5001)
│   ├── data_loader.py                 [NEW Phase 8] Read-only artifact loading layer
│   └── templates/
│       └── dashboard.html             [NEW Phase 8] Dashboard UI
├── data/
│   └── prioritization_evaluation.json [NEW Phase 8 output, gitignored]
├── requirements.txt                   [MODIFIED] Added scikit-learn, joblib
├── .gitignore                         [MODIFIED] Added Phase 8 artifact
└── .github/workflows/
    └── smartqa-tests.yml              [MODIFIED] Added Phase 8 CI steps
```

### Scientific Honesty — Phase 8 Constraints

Consistent with the project's honesty requirements:

1. **No fabricated metrics** — All metrics come from actual `data/test_results.jsonl` and `data/prioritized_tests.csv`. Dashboard shows `N/A` when data is absent.
2. **Limitations disclosed** — Every evaluation output includes a `note` field explaining the retrospective nature and limited-failure-data constraints.
3. **Graceful degradation** — All tools produce a valid empty output (not an error) when data is insufficient. CI never blocks on missing evaluation data.
4. **Fixture labeling** — All synthetic data in test_evaluation.py is explicitly labeled `[FIXTURE]` in docstrings.
