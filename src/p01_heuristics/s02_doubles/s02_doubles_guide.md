# s02_doubles: 2-vs-2 Heuristic Agents

This directory contains the development and testing suite for Doubles heuristics (2v2).

## Content Overview

### `agents/`
Strategy implementations for doubles:
- `v1.py`: Per-slot greedy selection (treats each slot independently).
- `v2.py`: Joint-action selection (scores pairs of actions to allow coordination).
- `v6.py`: Advanced joint-action with Field/Weather awareness.

### `core/`
The infrastructure for 2v2:
- `base.py`: Abstract `BaseHeuristic2v2` player class.
- `battle_manager.py`: Specialized manager for managing 2-wide battle objects.

---

## How it Works

Doubles are significantly more complex than singles due to **Joint Decision Making**. 
- Instead of picking 1 action, the v6 agent evaluates the **Best Pair** of actions (Slot 0 and Slot 1).
- **Coordination**: It penalizes "overkill" (both attacking a target that would die from one hit) and rewards "focus-firing" (attacking a target that needs two hits to die).
- **Protect**: The agents recognize when they are in danger and use the move `Protect` to scout or stall while the ally attacks.

---

## How to Run

To execute a doubles benchmark:

```bash
# Run a benchmark of Doubles-v6 vs Doubles-v2 (Fast Positional Arguments)
uv run python src/p01_heuristics/s02_doubles/run.py v6 v2 50
```

### Main script arguments:
1. `version`: Heuristic version to test (v1-v6).
2. `opponent`: (Optional) Opponent version or type (default: random).
3. `total_games`: (Optional) Number of total battles (default: 1000).

### Optional Flags:
- `-p`, `--ports`: Server port(s) (default: 8000).
- `-c`, `--concurrent-battles`: parallel battle instances (default: 16).
