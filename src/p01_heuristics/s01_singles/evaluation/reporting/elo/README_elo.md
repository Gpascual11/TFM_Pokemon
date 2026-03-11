# Elo Ranking Script (`elo_ranking.py`)

## What it does
This script runs a **Whole-History Rating (WHR)** calculation—a Maximum Likelihood Estimation of Elo ratings—using the Bradley-Terry model. It computes an objective "Elo Rating" for all the AI agents based on the 1v1 battle results recorded in the benchmark CSV files.

## Input Data
It automatically scans the `data/1_vs_1/benchmarks/pokechamp/` directory for any `*.csv` files. These files contain individual match outputs between agents (e.g., `v6` vs `v5`, `abyssal` vs `max_power`), where a "1" indicates the first model won and a "0" indicates the second model won.

## Output
1. **`elo_ratings.txt`**: A clean text file listing each agent and its respective Elo rating.
2. **`elo_ratings_plot.png`**: A bar chart visualizing the performance of the agents.

These files are saved to `src/p01_heuristics/s01_singles/evaluation/results/` and are perfectly formatted to be included in your Master's Thesis Results chapter.

## How to run
From the `TFM` root directory, simply execute:
```bash
python ./src/p01_heuristics/s01_singles/evaluation/reporting/elo_ranking.py
```
