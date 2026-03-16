# # Phase 3: Training & Feature Extraction

## Overview
This folder contains the core machine learning logic. Once raw data has been downloaded (Step 1) and analyzed (Step 2), we must transform raw battle logs into discrete mathematical vectors that a computer can understand.

## The Training Pipeline

The pipeline is now separated by gamemode: `gen9ou/` and `gen9random/`.

### 1. Feature Extraction
The raw text replays are parsed into a tabular CSV format.
**Commands:**
```bash
# For Gen 9 OU
uv run python src/p03_ml_baseline/s03_training/gen9ou/extract_ml_features.py

# For Gen 9 Random Battle
uv run python src/p03_ml_baseline/s03_training/gen9random/extract_ml_features.py
```
**Output:** `models/[gamemode]/ml_training_data.csv`

### 2. Model Training
We use the extracted CSV to train an **XGBoost Classifier**.
**Commands:**
```bash
# For Gen 9 OU
uv run python src/p03_ml_baseline/s03_training/gen9ou/train_ml_baseline.py

# For Gen 9 Random Battle
uv run python src/p03_ml_baseline/s03_training/gen9random/train_ml_baseline.py
```
**Outputs:**
- `models/[gamemode]/ml_baseline.json`: The trained model weights.
- `models/[gamemode]/feature_importance.png`: Feature importance plot.
