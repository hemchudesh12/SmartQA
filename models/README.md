# models/

This directory stores trained Phase 6 ML model artifacts.

Files created here by `python tools/train_model.py`:

- `failure_predictor.joblib`  — Trained sklearn Pipeline (StandardScaler + LogisticRegression)
- `model_metadata.json`       — Training configuration, dataset stats, and feature list

Files in this directory are Git-ignored (regeneratable) except for this README.

To regenerate:

    python tools/build_features.py
    python tools/train_model.py
    python tools/evaluate_model.py
