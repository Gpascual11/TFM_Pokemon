# CORE: Shared Infrastructure

The `core` directory contains the foundational plumbing that allows agents to exist and communicate with the Pokémon Showdown engine in a reliable, thread-safe, and scalable way.

---

## 1. Architecture: The Execution Pipeline

### `base.py` — The Strategy Contract

This file defines `BaseHeuristic1v1`. We use the **Template Method Pattern**:

- **`choose_move`**: This is the "Public API" caller. It implements a safe 3-phase pipeline:
    1. `_pre_move_hook`: Early-exit logic.
    2. `_select_action`: The main logic (implemented by subclasses like V1-V6).
    3. `choose_random_move`: The absolute safety fallback.
- **Why?**: This prevents "battle freezes" if a specific heuristic crashes. The system will simply log the error and move on with a random action.

### `factory.py` — Dependency Injection

The **`AgentFactory`** is the "single source of truth" for instantiating players.

- **Unified Naming**: You don't need to know which class to import. Just call `AgentFactory.create("v6")`.
- **Legacy Support**: It automatically handles path-injection for `abyssal` and other agents that require the `pokechamp` external repo.

---

## 2. Parallel Processing Infrastructure

One of the project's biggest achievements is solving the "Asyncio Deadlock" and "Memory Bloat" issues inherent in Python/Pokémon simulations.

### `process_launcher.py`

This module implements a **Pre-flight-Check Process Launcher**.

- It checks if all required ports (8000, 8001, etc.) are actually reachable before starting.
- It uses the `spawn` multiprocessing context.
- **Process Isolation**: Every child process is a "sandbox." When the simulation finishes, the process is killed, reclaiming 100% of the memory.

### `battle_manager.py`

This is the internal orchestrator used by the worker processes.

- **Batching**: It breaks a 1000-game request into small, digestible chunks (e.g., 250 games).
- **GC Triggering**: It explicitly calls `gc.collect()` after every batch to keep RAM usage flat throughout the run.
- **Analytic Extraction**: It transforms hundreds of raw `Battle` objects into clean CSV rows with 11 distinct metrics.

---

## 3. Shared Mathematics (`common.py`)

To ensure that V2, V3, and V6 are comparable, they all use the same underlying math helper for baseline damage and speed estimation.

- **`calculate_base_damage`**: Standardized physical/special attack split with burn, STAB, and type effectiveness (used by V2, V3, and V6).
- **`get_speed`**: Correctly factors in Paralysis penalties.
- **`GameDataManager`**: A performance-optimized singleton that prevents loading the massive Pokémon move/data JSONs multiple times into memory.

V4 and V5 build on the same ideas but use their own extended damage estimators that layer in weather, terrain, and stat-boost awareness.

---

## Important for Developers

When modifying the logic in `core/`:

1. **Thread Safety**: Assume any variable in `BattleManager` or `ProcessLauncher` will be accessed by concurrent processes.
2. **Path Resolution**: Use `Path(__file__).parent` rather than hardcoded strings, as these files are often executed from the root via `uv run`.
3. **Logging**: Child processes suppress `INFO` level logs to prevent terminal spam; use `print(..., flush=True)` for critical cross-process progress updates.
