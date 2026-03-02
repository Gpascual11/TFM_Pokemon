# s01_singles: 1-vs-1 Heuristic Agents

This directory contains the development and testing suite for Singles heuristics (1v1).

## Content Overview

### `agents/`
Contains the specific strategy versions:
- `v1.py`: Max-Damage greedy selector.
- `v2.py` - `v5.py`: Incremental improvements in logic and formula.
- `v6.py`: Most advanced version with speed-tiering and field awareness.

### `core/`
The internal machinery:
- `battle_manager.py`: Connects to multiple Showdown instances.
- `process_launcher.py`: Spawns the necessary sub-processes.
- `factory.py`: Interface to create agents by name string.

### Tools
- `run.py`: Standard entry point for single simulations.
- `benchmark.py`: Fully automated round-robin tournament script. Tracks win rates, turns, and HP with automatic server management and checkpointing.
- `generate_report.py`: Generates a professional visual analysis (charts, heatmaps, and rankings) in the `results/` folder.

---

## How it Works

The agents use a **rule-based scoring system**. Every turn, the code:
1.  **Estimates Damage**: calculates `Attack / Defense * Power * Multipliers`.
2.  **Checks Threats**: if the current Pokémon is at low health or has a 4x weakness, it considers switching.
3.  **KOs First**: if a move (especially a priority one) can KO the opponent, it is picked immediately.

---

## How to Run

### Single Simulation
```bash
# Run a benchmark of v6 vs v1 (Fast Positional Arguments)
uv run python src/p01_heuristics/s01_singles/run.py v6 v1 100
```

### Full Benchmark Matrix
The script is fully automated and manages its own servers. It generates a round-robin tournament between all versions and baselines.
```bash
# Run 1000 games of every combination using 4 parallel ports.
uv run python src/p01_heuristics/s01_singles/benchmark.py 1000 -p 4 --resume
```

### Generate Visual Analysis
After the benchmark finishes (or even while it's running), generate the report:
```bash
uv run python src/p01_heuristics/s01_singles/generate_report.py
```

---

## Technical Safety Features

### 1. Checkpoint & Resume (Self-Healing)
Both benchmark scripts are **crash-proof**.
- They save a `checkpoint_v2.json` after every matchup.
- Use the `--resume` flag to pick up exactly where you left off.
- The script is "Self-Healing": it scans your `data/` folder for completed CSVs and updates the checkpoint automatically before starting.

### 2. Automatic Server Management
The `benchmark.py` script manages its own servers:
- **Auto-Start**: It starts the necessary servers at the beginning.
- **Auto-Refresh**: It kills and restarts all servers **every single matchup** to clear Node.js memory leaks and prevent `slow battle` lag.
- **Auto-Cleanup**: It stops all servers gracefully when the script exits or is stopped with `Ctrl+C`.

### 3. RAM Management (Python)
- **Object Deletion**: Player objects are explicitly deleted and cleared from memory between matchups.
- **Garbage Collection**: Manual `gc.collect()` calls ensure Python releases RAM back to the operating system immediately.

### 4. Baselines
Benchmarks automatically include comparisons against:
- `random`: Purely random player.
- `max_power`: Always uses the move with the highest base power.
- `simple_heuristic`: The built-in baseline from `poke-env`.
