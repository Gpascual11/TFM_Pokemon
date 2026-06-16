# Step 4: ML Baseline Agent

## Overview
This folder contains the final "product" of the ML pipeline: a competitive AI agent that plays Pokémon by predicting human actions.

## Architecture
The folder contains two main agents that implement different levels of imitation learning:
- **`MLBaselineAgent`** ([ml_baseline.py](file:///home/sirp/Documents/MUDS/TFM_Pokemon/src/p02_imitation_learning/s04_agent/ml_baseline.py)): Uses a basic XGBoost model trained on 3 continuous/discrete features: HP difference, active side conditions (hazards), and whether the game is in the late-game phase (turn > 15).
- **`MLAdvancedAgent`** ([ml_advanced.py](file:///home/sirp/Documents/MUDS/TFM_Pokemon/src/p02_imitation_learning/s04_agent/ml_advanced.py)): Uses a context-aware XGBoost model trained on 654 features (including continuous HP percents for both sides, hazard/Tera flags, and one-hot active species identity).

Both agents:
1. Hook into the `poke-env` battle engine.
2. Observe the current live state of a battle.
3. Calculate live features matching their respective training pipelines.
4. **Inference:** Load their respective trained models from `s03_training/models/gen9randombattle/`.
5. Decide whether to Attack or Switch based on the model's prediction.
   - For `MLBaselineAgent`, specific moves/switches are chosen randomly.
   - For `MLAdvancedAgent`, if a move is chosen, it selects the optimal move based on damage-simulated heuristics, and if a switch is chosen, it selects a switch at random. An infinite-switching guard is implemented to avoid loops.
