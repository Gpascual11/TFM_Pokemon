# CORE: Shared Infrastructure

The `core` directory contains the foundational plumbing that allows agents to exist and communicate with the Pokémon Showdown engine in a reliable, thread-safe, and scalable way.

---

## 1. Architecture: The Execution Pipeline

### `base.py` — The Strategy Contract

This file defines `BaseHeuristic1v1`. We use the **Template Method Pattern**:

- **`choose_move`**: This is the "Public API" caller. It implements a safe 3-phase pipeline:
    1. `_pre_move_hook`: Early-exit logic (used by V7/V8 for KO detection).
    2. `_select_action`: The main logic (implemented by subclasses V1-V8).
    3. `choose_random_move`: The absolute safety fallback.
- **Why?**: This prevents "battle freezes" if a specific heuristic crashes. The system will simply log the error and move on with a random action.

#### Tracking Counters

`BaseHeuristic1v1` maintains per-battle counters for analysis:

| Counter | Purpose | Agents that use it |
|---------|---------|-------------------|
| `_total_decisions_by_battle` | Total `choose_move` calls | All |
| `_fallback_moves_by_battle` | Times no move was selected (random fallback) | All |
| `_error_moves_by_battle` | Times logic crashed (exception caught) | All |
| `_used_moves_by_battle` | Set of move IDs used per battle | V3+ (tracks_moves=True) |
| `_hazard_sets_by_battle` | Times entry hazards were set | V7, V8 |
| `_hazard_removals_by_battle` | Times hazards were removed | V7, V8 |
| `_setup_uses_by_battle` | Times boost moves were used | V7, V8 |
| `_ko_checks_by_battle` | Times KO pre-check triggered | V7, V8 |
| `_matchup_switches_by_battle` | Times matchup-based switching fired | V7, V8 |

All counters are cleared in `reset_battles()` between batches.

### `factory.py` — Dependency Injection

The **`AgentFactory`** is the "single source of truth" for instantiating players.

- **Unified Naming**: Just call `AgentFactory.create("v8")` — no imports needed.
- **Registered Agents**:
  - Internal: `v1`, `v2`, `v3`, `v4`, `v5`, `v6`, `v7`, `v8`
  - Baselines: `random`, `max_power`, `abyssal`, `one_step`, `safe_one_step`, `simple_heuristic`
  - LLM: `pokechamp`, `pokellmon`, `llm_vgc`
- **Legacy Support**: Automatically handles path-injection for `abyssal` and other agents that require the `pokechamp` external repo.

---

## 2. Parallel Processing Infrastructure

One of the project's biggest achievements is solving the "Asyncio Deadlock" and "Memory Bloat" issues inherent in Python/Pokémon simulations.

### `process_launcher.py`

This module implements a **Pre-flight-Check Process Launcher**.

- It checks if all required ports (8000, 8001, etc.) are actually reachable before starting.
- It uses the `spawn` multiprocessing context.
- **Process Isolation**: Every child process is a "sandbox." When the simulation finishes, the process is killed, reclaiming 100% of the memory.

### `battle_manager.py` (Legacy)

The internal orchestrator for the older `run_single.py` pipeline. The primary benchmark now uses `benchmark.py` + `worker.py` directly.

---

## 3. Shared Mathematics (`common.py`)

To ensure V2, V3, V4, and V6 are comparable, they all use the same underlying math helper for baseline damage and speed estimation.

- **`calculate_base_damage`**: Standardized physical/special attack split with burn, STAB, and type effectiveness. Used by V2, V3, V4, V6.
- **`get_speed`**: Correctly factors in Paralysis penalties.
- **`get_status_name`**: Normalizes `None` to `"HEALTHY"` for safe string comparisons.
- **`GameDataManager`**: A performance-optimized singleton that prevents loading the massive Pokémon move/data JSONs multiple times into memory.

V5, V7, and V8 use their own `_get_boosted_stat()` method for stat-stage-aware damage estimation, building on the same proportional formula.

---

## Important for Developers

When modifying the logic in `core/`:

1. **Counter Lifecycle**: Any new counter added to `BaseHeuristic1v1.__init__` must also be cleared in `reset_battles()`, or it will accumulate across batches and produce incorrect CSV data.
2. **Thread Safety**: Assume any variable in `BattleManager` or `ProcessLauncher` will be accessed by concurrent processes.
3. **Path Resolution**: Use `Path(__file__).parent` rather than hardcoded strings, as these files are often executed from the root via `uv run`.
4. **Logging**: Child processes suppress `INFO` level logs to prevent terminal spam; use `print(..., flush=True)` for critical cross-process progress updates.
