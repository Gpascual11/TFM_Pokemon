# s02_doubles: 2-vs-2 Heuristic Agents

This directory contains the testing suite for Doubles (2v2) heuristics.

## Content Overview

### `agents/`
Registered doubles heuristic versions.

### `core/`
The internal engine for double battles:
- `battle_manager.py`: Handles the doubles battle loop.
- `process_launcher.py`: Spawns parallel processes.

### Tools
- `run.py`: Single simulation entry point.
- `benchmark.py`: Fully automated benchmarking suite.
- `generate_report.py`: Visual analysis script (output to `results/`).

---

## How it Works

Doubles heuristics use a **Score-then-Combine** pattern:
1.  **Candidate Selection**: For each active slot, the engine lists all valid actions.
2.  **Scoring**: Each action is scored individually (e.g., damage against most vulnerable opponent).
3.  **Combination**: `DoubleBattleOrder.join_orders` produces valid pairings, filtering illegal moves (like switching to the same Pokémon twice).
4.  **Policy**: The pair with the highest combined score is picked.

---

## How to Run

### Automated Doubles Benchmark
No manual server setup is required. The script manages the server lifecycle automatically.
```bash
# Full tournament against all heuristics and baselines.
# Output: data/2_vs_2/benchmarks/unified/2_vs_2_<agent>_vs_<opponent>_*.csv
uv run python src/p01_heuristics/s02_doubles/benchmark.py 1000 --ports 8000 8001 8002 8003 --resume
```

### Visual Report
```bash
uv run python src/p01_heuristics/s02_doubles/generate_report.py
```

---

## Technical Features

### Memory Management
- **Python-level**: Forced garbage collection between matchups.
- **Server-level**: Automatic restarts every 5 matchups to prevent `pokemon-showdown` memory bloat.
- **Safe Batching**: Batch size is set to 250 to stay within 16GB RAM limits.

### Checkpoints
Uses `data/2_vs_2/benchmarks/unified/checkpoint_v2.json` to resume from failures.
