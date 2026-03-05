# ⚔️ Evaluation Lab — Benchmarking Pokémon Agents

This directory contains the unified engine for running large-scale battle simulations and analyzing agent performance.

## 🚀 Execution Guide

### 1. The Benchmark Engine
The primary entry point is `engine/benchmark.py`. It uses a parallel worker pattern to run battles across multiple Showdown server ports simultaneously.

**Run 100 battles for all combinations (Standard):**
```bash
uv run python evaluation/engine/benchmark.py 100 --ports 4
```

**Test a specific matchup (e.g., v6 vs abyssal):**
```bash
uv run python evaluation/engine/benchmark.py 50 --agents v6 --opponents abyssal
```

### 2. Visualization & Reporting
After running benchmarks, data is stored in `data/benchmarks_unified/`. Use the reporting scripts to visualize results.

**Generate a full cross-matchup heatmap:**
```bash
uv run python evaluation/reporting/heatmaps.py
```

## 📂 Folder Overview

- **`engine/`**: The core execution logic. 
    - `benchmark.py`: Orchestrator that manages workers and restarts servers.
    - `worker.py`: Isolated subprocess that runs battles (prevents memory leaks).
- **`reporting/`**: Scripts for data analysis and graph generation.
- **`docs/`**: Detailed guides on specific topics (e.g., [LLM Setup with Ollama](docs/LLM_SETUP_GUIDE.md)).
- **`results/`**: Final artifacts like PNG heatmaps and summary CSVs.

## 🛠️ Performance Tuning
- **`--ports`**: Number of parallel Showdown servers to use. Recommended: 4-8.
- **`--n-battles`**: Total battles per matchup. Recommended: 100 for dev, 1000 for final results.
- **Server Restarts**: The engine automatically restarts Showdown servers between matchups to clear Node.js memory bloat.
