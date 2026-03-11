# # Phase 3: Training & Feature Extraction

## Overview
This folder contains the core machine learning logic. Once raw data has been downloaded (Step 1) and analyzed (Step 2), we must transform raw battle logs into discrete mathematical vectors that a computer can understand.

## The Training Pipeline

### 1. Feature Extraction
The raw text replays are parsed into a tabular CSV format.
**Command:**
```bash
uv run python src/p03_ml_baseline/s03_training/extract_ml_features.py
```
**Output:** `models/ml_training_data.csv`
**Features extracted:**
- `hp_diff`: Net HP advantage.
- `hazards_active`: Presence of Stealth Rocks.
- `is_late_game`: Turn index > 15.

### 2. Model Training
We use the extracted CSV to train an **XGBoost Classifier**.
**Command:**
```bash
uv run python src/p03_ml_baseline/s03_training/train_ml_baseline.py
```
**Outputs:**
- `models/ml_baseline.json`: The trained model weights.
- `models/feature_importance.png`: Proof of what the AI learned for the TFM Results chapter.
