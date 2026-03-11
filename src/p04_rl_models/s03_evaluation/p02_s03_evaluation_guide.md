# s03_evaluation: Performance Benchmarking

This directory contains the tools to evaluate the final performance of the trained RL models against expert heuristics.

## Main Tools

### 1. `run_benchmarks.py`
The primary evaluation suite. It tests two types of agents against a gauntlet of 9 different opponents (Random, MaxBP, and Heuristics v1-v6).
- **Pure PPO**: The neural network making 100% of the decisions.
- **Ensemble Agent**: A "Hybrid" player that blends the PPO's overall strategy with the Heuristic's tactical math using a weighted average (`alpha`).

### 2. `benchmark_rl.py`
The high-performance benchmarking engine. It performs a distributed "Gauntlet Study" across 4 parallel Showdown servers to collect high-quality data (1000+ games per matchup) with RAM-isolated subprocesses.

### 3. `generate_rl_report.py`
A visualization script that parses the `results/*.csv` data and produces a 4-panel visual heatmap and trend report.

---

## How to Run

To run a basic benchmark:
```bash
python src/p04_rl_models/s03_evaluation/run_benchmarks.py
```

To run the full 4-server parallel gauntlet:
```bash
python src/p04_rl_models/s03_evaluation/benchmark_rl.py --games 1000
```

To generate victory heatmaps:
```bash
python src/p04_rl_models/s03_evaluation/generate_rl_report.py
```

---

## Results Location
- **Raw Data**: `src/p04_rl_models/s03_evaluation/results/benchmark_rl_summary.csv`
- **Visual Report**: `src/p04_rl_models/s03_evaluation/results/rl_model_report.png`
