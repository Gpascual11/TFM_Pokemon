# Exploratory Data Analysis (EDA) of Pokémon VGC/OU Replays

## What it does
This script (`eda_pokemon_battles.py`) bridges the gap between the expert-knowledge heuristics (Phase 1) and the machine learning model (Phase 3). It analyzes the `milkkarten/pokechamp` dataset of high-Elo professional Pokémon Showdown replays to extract quantitative behavioral patterns.

## Output
It generates plots and statistics saved to `src/p03_ml_baseline/s02_eda/plots/`, specifically:
1. **`action_distribution.png`**: The overall ratio of attacking moves vs. switches.
2. **`actions_by_phase.png`**: How the frequency of switches changes between the early game, mid game, and late game.
3. **`hazard_switching_correlation.png`**: Showing whether the presence of Entry Hazards (like Stealth Rock) mathematically reduces the human player's willingness to switch.

## Why this is in the TFM
This provides rigorous, data-driven validation for the rules encoded in your Heuristics (`v1-v6`). For example, if your `v4` heuristic heavily discourages switching when Stealth Rock is up, this EDA proves mathematically that *that is exactly what high-Elo human players do.*

## How to run
```bash
python src/p03_ml_baseline/s02_eda/eda_pokemon_battles.py
```
*(Note: It downloads several gigabytes from HuggingFace to process the match histories the first time it runs).*
