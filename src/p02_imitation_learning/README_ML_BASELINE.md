# Phase 4: Machine Learning (Imitation Learning)

## Overview
This module (`p02_imitation_learning`) contains the implementation of the "Learning" phase of the Master's Thesis. While `p01_heuristics` relied on human-engineered expert rules, this module aims to create agents that play Pokémon purely by observing and imitating professional human players, requiring zero hardcoded domain knowledge for move evaluation.

---

## Workflow & Execution Guide

The module is split into 4 chronological phases following a standard Data Science lifecycle.

### Step 1: Dataset Acquisition (`s01_download/`)
Download professional human replays (>1800 Elo) from HuggingFace to the external cache.
- **Command:** `uv run python src/p02_imitation_learning/s01_download/download_dataset.py`
- **Generates:** Cached raw data in `data/huggingface_cache/`.

### Step 2: Exploratory Data Analysis (`s02_eda/`)
Analyze raw replays to extract behavioral insights and validate the feature space.
- **Notebooks:** 
  - `01_metadata_eda.ipynb` (Metadata exploration)
  - `02_behavioral_parsing.ipynb` (Action distributions)
  - `03_imitation_learning.ipynb` (Baseline model testing)
  - `04_advanced_feature_engineering.ipynb` (1,150-column state representation)
  - `05_advanced_modeling.ipynb` (Advanced XGBoost evaluation)
- **Generates:** Professional plots in `s02_eda/plots/` for the thesis.

### Step 3: Feature Extraction & Training (`s03_training/`)
Transform logs into tabular data and train the XGBoost model.
- **Commands:**
  1. `uv run python src/p02_imitation_learning/s03_training/extract_ml_features.py`
  2. `uv run python src/p02_imitation_learning/s03_training/train_ml_baseline.py` (Trains baseline agent)
  3. `uv run python src/p02_imitation_learning/s03_training/train_ml_advanced.py` (Trains advanced agent)
- **Data Size**: **1.1 million turns** of expert battles.
- **Advanced Model Performance**: 
  - **Overall Accuracy**: **65.53%**
  - **ROC AUC**: **0.720**
- **Generates:** `xgboost_advanced_model.json` and features list in `s03_training/models/gen9randombattle/`.

### Step 4: Agent Integration (`s04_agent/`)
Deploy the trained model as a live competitive agent.
- **Agents**:
  - `MLBaselineAgent` (`s04_agent/ml_baseline.py`) - Baseline model predicting based on raw turn states.
  - `MLAdvancedAgent` (`s04_agent/ml_advanced.py`) - Advanced model incorporating context-aware features (team matching, hazard state, speed tiers).
- **Cognitive-Tactical Hybrid Upgrade**:
  - Initially, the `MLAdvancedAgent` used XGBoost to choose the action type (`Attack` vs `Switch`) but selected the specific move/switch at random, leading to a low win rate.
  - We have **upgraded the execution logic**: now, the XGBoost model acts as the high-level cognitive director (deciding *when* to pivot/switch vs when to stay in and attack based on human expert play patterns), while **HeuristicV14** acts as the tactical engine (calculating exact damage rolls, type effective multipliers, and team matchup scores to execute the optimal specific move or switch target).

---

## Benchmark Results (10,000 Games)

We executed parallel benchmark tournaments consisting of **10,000 games per matchup** to compare the Machine Learning agents against baseline and expert agents in `gen9randombattle`.

| Agent | Opponent | Win Rate (%) | Total Games | Notes |
| :--- | :--- | :---: | :---: | :--- |
| **ml_baseline** | abyssal | **8.7%** | 10000 / 10000 | Baseline (uses random moves/switches) |
| **ml_baseline** | v14 | **8.0%** | 10000 / 10000 | Baseline (uses random moves/switches) |
| **ml_baseline** | random | **92.3%** | 10000 / 10000 | Baseline (uses random moves/switches) |
| **ml_baseline** | v6 | **15.8%** | 10000 / 10000 | Baseline (uses random moves/switches) |
| **ml_baseline** | max_power | **46.7%** | 10000 / 10000 | Baseline (uses random moves/switches) |
| | | | | |
| **ml_advanced** | abyssal | *Pending* | - | Upgraded (V14 exact execution; old random logs deleted) |
| **ml_advanced** | v14 | *Pending* | - | Upgraded (V14 exact execution; old random logs deleted) |
| **ml_advanced** | random | *Pending* | - | Upgraded (V14 exact execution; old random logs deleted) |
| **ml_advanced** | v6 | *Pending* | - | Upgraded (V14 exact execution; old random logs deleted) |
| **ml_advanced** | max_power | *Pending* | - | Upgraded (V14 exact execution; old random logs deleted) |

### Key Findings
1. **Decision Execution starves ML Agents**: The baseline ML agent performs poorly against expert heuristics due to choosing specific moves/switches randomly.
2. **Cognitive-Tactical Separation**: By upgrading the agent to use the trained XGBoost model for high-level switch-vs-attack decisions and `HeuristicV14` for low-level damage resolution, the model's win rate is expected to see a massive improvement.
