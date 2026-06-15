# Phase 3: Training & Feature Extraction

## Overview
This folder contains the core machine learning logic. Once raw data has been downloaded (Step 1) and analyzed (Step 2), we must transform raw battle logs into discrete mathematical vectors that a computer can understand.

## The Training Pipeline

### 1. Feature Extraction
The raw text replays are parsed into a tabular CSV format.
**Command:**
```bash
uv run python src/p02_imitation_learning/s03_training/extract_ml_features.py --format gen9randombattle
```
**Output:** `models/{format}/ml_training_data.csv`

### 2. Model Training
We use the extracted CSV to train an **XGBoost Classifier**.
**Command:**
```bash
uv run python src/p02_imitation_learning/s03_training/train_ml_baseline.py --format gen9randombattle
```
**Outputs:**
- `models/{format}/ml_baseline.json`: The trained model weights.
- `models/{format}/feature_importance.png`: Feature importance plot.
