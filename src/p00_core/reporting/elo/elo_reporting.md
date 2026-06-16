# Elo Ranking Script (`elo_ranking.py`)

## What it does

This script runs a **Whole-History Rating (WHR)** calculation—a Maximum Likelihood Estimation of Elo ratings—using the Bradley-Terry model. It computes an objective "Elo Rating" for all the AI agents based on the 1v1 battle results recorded in the benchmark CSV files.

## Input Data

It automatically scans the `data/benchmarks/all_10k/` directory for any `*.csv` files. These files contain individual match outputs between agents.

## Output

1. **`elo_ratings.txt`**: A clean text file listing each agent and its respective Elo rating.
2. **`elo_ratings_plot.png`**: A bar chart visualizing the performance of the agents.

These files are saved to `src/p00_core/results/` and are perfectly formatted to be included in your Master's Thesis Results chapter.

## How to run

From the `TFM` root directory, simply execute:

```bash
uv run python src/p00_core/reporting/elo/elo_ranking.py
```

