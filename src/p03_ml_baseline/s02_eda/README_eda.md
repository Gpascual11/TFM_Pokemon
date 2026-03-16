# Exploratory Data Analysis (EDA) of Pokémon VGC/OU Replays

## What it does
This folder contains the Exploratory Data Analysis (EDA) notebooks and scripts that bridge the gap between heuristics and ML modeling. It is now separated by gamemode:
- **`gen9ou/`**: Notebooks and scripts specifically for Gen 9 OU battles.
- **`gen9random/`**: Adapted notebooks and scripts for Gen 9 Random Battles.

## Output
Plots are saved to `src/p03_ml_baseline/s02_eda/plots/[gamemode]/`.

## How to run
```bash
# For Gen 9 OU
python src/p03_ml_baseline/s02_eda/gen9ou/eda_pokemon_battles.py

# For Gen 9 Random Battle
python src/p03_ml_baseline/s02_eda/gen9random/eda_pokemon_battles.py
```
*(Note: It downloads several gigabytes from HuggingFace to process the match histories the first time it runs).*
