# s02_doubles: 2-vs-2 Heuristic Agents

This directory contains the testing suite for Doubles (2v2) heuristics.

## Content Overview

### `agents/`
Registered doubles heuristic versions.

### `evaluation/`
The testing and analysis suite for doubles:
- `engine/benchmark.py`: Fully automated benchmarking suite.
- `engine/run.py`: Single simulation entry point.
- `reporting/generate_report.py`: Visual analysis script.
- `results/`: Local summary CSVs and generated plots.

---

## How it Works

Doubles heuristics use a **Score-then-Combine** pattern:
1.  **Candidate Selection**: Validates all possible actions for both active slots.
2.  **Scoring**: Each action is scored individually (incorporating damage, status, and survival).
3.  **Combination**: `DoubleBattleOrder.join_orders` produces valid pairings, filtering illegal moves.
4.  **Policy**: The pair with the highest combined score (Slot 0 + Slot 1) is selected.

---

## How to Run

### Automated Doubles Benchmark (10k Games)
The script handles the server lifecycle (restarts every 5 matchups) automatically. Results are organized by generation.

```bash
# Run a specific benchmark (e.g. Gen 9)
# Output: data/2_vs_2/benchmarks/gens_10k_teams/gen9randomdoublesbattle/*.csv
uv run python src/p01_heuristics/s02_doubles/evaluation/engine/benchmark.py 10000 \
    --ports 8 \
    --battle-format gen9randomdoublesbattle
```

### Multi-Generation Sweep
To replicate the singles "all-gen" benchmark:
```bash
for gen in {4..9}; do
  uv run python src/p01_heuristics/s02_doubles/evaluation/engine/benchmark.py 10000 \
      --ports 8 --battle-format gen${gen}randomdoublesbattle
done
```

### Visual Report
```bash
uv run python src/p01_heuristics/s02_doubles/evaluation/reporting/generate_report.py
```

---

## Data Schema & Metrics
The doubles engine records 30+ metrics per battle to remain compatible with `s01_singles` analysis tools:
- **Core**: `won`, `turns`, `winner`, `format`.
- **Survival**: `hp_perc_us`, `remaining_pokemon_us`, `side_conditions_us`.
- **Performance**: crits, misses, and move effectiveness (schema matched to singles).
- **Organization**: Data is stored in `data/2_vs_2/benchmarks/gens_10k_teams/`.
