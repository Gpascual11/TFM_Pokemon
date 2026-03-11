# Step 4: ML Baseline Agent

## Overview
This folder contains the final "product" of the ML pipeline: a competitive AI agent that plays Pokémon by predicting human actions.

## Architecture
The `MLBaselineAgent` is a Python class that:
1.  Hooks into the `poke-env` battle engine.
2.  Observed the current live state of a battle.
3.  Calculates the same features used during training (`hp_diff`, `hazards`, etc.).
4.  **Inference:** Loads the trained `ml_baseline.json` model and asks it to predict the best action.

## Implementation Details
- **Base Class:** Inherits from `BaseHeuristic1v1` to ensure compatibility with our existing benchmarking infrastructure.
- **Model Loading:** Dynamically locates the model weights in the `s03_training/models/` directory.
- **Decision Logic:** Instead of hardcoded "if-else" rules, it follows the statistical probability learned from 1800+ Elo human players.
