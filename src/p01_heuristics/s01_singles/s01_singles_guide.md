# s01_singles: 1-vs-1 Heuristic Agents

This directory contains the development and testing suite for Singles heuristics (1v1).

## Content Overview

### `agents/`
Contains the specific strategy versions:
- `v1.py`: Max-Damage greedy selector.
- `v4.py`: High-tier damage formula with Weather/Terrain modifiers.
- `v6.py`: Most advanced version with speed-tiering and field awareness.

### `core/`
The machinery that runs the simulations:
- `battle_manager.py`: Connects to multiple Showdown instances.
- `process_launcher.py`: Spawns the necessary sub-processes.
- `factory.py`: Interface to create agents by name string.

---

## How it Works

The agents use a **rule-based scoring system**. Every turn, the code:
1.  **Estimates Damage**: calculates `Attack / Defense * Power * Multipliers`.
2.  **Checks Threats**: if the current Pokémon is at low health or has a 4x weakness, it considers switching.
3.  **KOs First**: if a move (especially a priority one) can KO the opponent, it is picked immediately.

---

## How to Run

To run a simulation where a heuristic agent plays against itself or random players:

```bash
# Example: Run a benchmark of v6 vs v1 (Fast Positional Arguments)
uv run python src/p01_heuristics/s01_singles/run.py v6 v1 100
```

### Main script arguments:
1. `version`: The heuristic version to test (v1 to v6).
2. `opponent`: (Optional) Opponent version or type (default: random).
3. `total_games`: (Optional) Number of battles to simulate (default: 1000).

### Optional Flags:
- `-p`, `--ports`: Server port(s) (default: 8000).
- `-c`, `--concurrent-battles`: Number of parallel battle threads (default: 16).

The results (win rates, move logs) are typically saved to the root directory as CSV or Log files for further analysis.
