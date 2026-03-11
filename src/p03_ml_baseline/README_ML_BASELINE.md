# Phase 4: Machine Learning Baseline (Imitation Learning)

## Overview
This module (`p03_ml_baseline`) contains the implementation of the "Learning" phase of the Master's Thesis. While `p01_heuristics` relied on human-engineered expert rules (Greedy algorithms), this module aims to create an agent that plays Pokémon purely by observing and imitating professional human players, requiring zero hardcoded domain knowledge for move evaluation.

## Workflow & Execution Guide

This module is split into 4 chronological phases following a standard Data Science lifecycle.

### Step 1: Dataset Acquisition (`s01_download/`)
Download professional human replays (>1800 Elo) from HuggingFace to the external cache.
- **Command:** `uv run python src/p03_ml_baseline/s01_download/download_dataset.py`
- **Generates:** Cached raw data in `data/huggingface_cache/`.

### Step 2: Exploratory Data Analysis (`s02_eda/`)
Analyze raw replays to extract behavioral insights and validate the feature space.
- **Command:** `uv run python src/p03_ml_baseline/s02_eda/eda_pokemon_battles.py`
- **Generates:** Professional plots in `s02_eda/plots/` for the thesis.

### Step 3: Feature Extraction & Training (`s03_training/`)
Transform logs into tabular data and train the XGBoost model.
- **Commands:**
  1. `uv run python src/p03_ml_baseline/s03_training/extract_ml_features.py`
  2. `uv run python src/p03_ml_baseline/s03_training/train_ml_baseline.py`
- **Generates:** `ml_baseline.json` and training statistics in `s03_training/models/`.

### Step 4: Agent Integration (`s04_agent/`)
Deploy the trained model as a live competitive agent.
- **How it works:** The `MLBaselineAgent` loads the model weights and predicts moves in real-time during battles.

## Thesis Relevance
By benchmarking this data-driven agent against `v6` (Expert Rules) and `v7_minimax` (Adversarial Search), we can quantitatively compare the efficacy of Imitation Learning against classical AI paradigms in the domain of Pokémon VGC.
