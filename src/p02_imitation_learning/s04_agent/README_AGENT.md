# Step 4: ML Baseline Agent

## Overview
This folder contains the final "product" of the ML pipeline: a competitive AI agent that plays Pokémon by predicting human actions.

## Architecture
Agents are now separated by gamemode:
- **`gen9ou/`**: Agents trained on Gen 9 OU data.
- **`gen9random/`**: Agents trained on Gen 9 Random Battle data.

The `MLBaselineAgent` and `MLAdvancedAgent` in each folder:
1.  Hook into the `poke-env` battle engine.
2.  Observe the current live state of a battle.
3.  Calculate features matching their respective training pipelines.
4.  **Inference:** Load their respective trained models from `s03_training/models/[gamemode]/`.
