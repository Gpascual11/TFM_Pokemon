# 🚀 Parallel Pokémon Benchmark Guide

This document explains the architecture, optimizations, and troubleshooting steps for the Parallel Benchmark system developed for **Pokechamp**.

## 🏗️ Architecture Overview

The system uses a **Master-Worker** architecture to run thousands of Pokémon battles in parallel across multiple CPU cores, bypassing the single-threaded nature of Python's `poke-env`.

### Core Components
1.  **Orchestrator (`benchmark_parallel.py`)**: 
    -   Manages the list of matchups.
    -   Launches and restarts multiple Pokémon Showdown servers.
    -   Assigns "Ports" to workers and handles task queueing.
    -   Merges results and manages the **Checkpoint System**.
2.  **Worker (`_worker_parallel.py`)**: 
    -   A standalone subprocess that runs a specific batch of games (e.g., 250 games for a matchup).
    -   Independent memory space to prevent memory leaks from affecting the main script.
    -   Streams results to temporary CSV files.
3.  **Checkpoint System (`checkpoint_parallel.json`)**:
    -   Tracks completed matchups.
    -   Allows resuming a 10,000+ game run after a crash or system restart using the `--resume` flag.

---

## 🛑 Problems & Solutions

During development, several critical bottlenecks were encountered and resolved.

### 1. Memory Exhaustion (RAM Crashing)
*   **Problem**: Every worker process was loading `torch`, `transformers`, and **every single heuristic version (v1-v6)**. This consumed ~4GB per worker, causing systems with 32GB RAM to crash when running 8+ workers.
*   **Solution**: **Lazy Loading Architecture**.
    -   **ML Imports**: Modified `LLAMAPlayer` and `LocalSim` to only import heavy libraries *inside* methods that actually use them.
    -   **Heuristic Registry**: Modified `agents/__init__.py` to use a `get_heuristic_class(version)` function. Now, a worker testing `v1` **never** loads the code for `v2, v3, v4, v5, or v6`.
    -   **Memory Drop**: Usage dropped from ~3.8GB per process to <1GB for simple matchups.

### 2. The "Abyssal Stalling" Bug
*   **Problem**: Certain "heavy" agents like `AbyssalPlayer` or `OneStepPlayer` perform complex simulations. Over 250 games, internal battle objects and state dictionaries (`move_set`, `item_set`) would grow infinitely, slowing down decisions until the process appeared "frozen."
*   **Solution**: **Streaming & State Clearing**.
    -   Implemented `_run_streaming` in the worker. Instead of running 250 games in one block, it runs them in **chunks of 10**.
    -   After every 10 games:
        1.  The CSV is appended.
        2.  `player.battles.clear()` is called.
        3.  Cumulative sets like `move_set` and `item_set` are emptied.
        4.  `gc.collect()` is manually triggered to release RAM.

### 3. Server Port Conflicts
*   **Problem**: Workers trying to connect to the same Showdown server would cause "Username Taken" errors or disconnected simulation states.
*   **Solution**: **Dynamic Port Assignment**.
    -   The Orchestrator launches `N` servers on ports 8000, 8001, etc.
    -   It uses an `asyncio.Queue` of available ports. A worker is only started when a port is free, and it returns the port to the queue when finished.

### 4. Code Quality & NameErrors
*   **Problem**: During the move to parallel, a `NameError: name 'Any' is not defined` crashed the simulation.
*   **Solution**: Comprehensive update to `local_simulation.py` to ensure all `typing` hints (`Any`, `Optional`, `Union`) are correctly imported.

---

## 🛠️ Recommended Usage

To run a reliable, high-power benchmark on a system with **32GB RAM**:

```bash
# Safest high-speed command
uv run python src/p01_heuristics/s01_singles/s01_pokechamp/benchmark_parallel.py 1000 \
    --ports 4 \
    --workers 4 \
    --batch-size 250 \
    --restart-every 5 \
    --resume
```

### Key Flags:
-   `--ports 4`: Launches 4 independent Showdown servers.
-   `--workers 4`: Runs 4 matchups at the same time.
-   `--batch-size 250`: Splits 1000 games into 4 parallel batches of 250.
-   `--restart-every 5`: Cleans up Showdown server memory leaks every 5 matchups.
-   `--resume`: Skips everything already recorded in `checkpoint_parallel.json`.

---

## 📝 Summary of Modified Files

| File | Role | Change Made |
| :--- | :--- | :--- |
| `benchmark_parallel.py` | Orchestrator | Port Queue, Subprocess management, Checkpointing. |
| `_worker_parallel.py` | Worker | Chunked streaming, State clearing, `gc.collect()`. |
| `agents/__init__.py` | Registry | Lazy loading versions to save RAM. |
| `core/factory.py` | Factory | Integration with lazy loader. |
| `llama_player.py` | Agent | Lazy ML imports (`torch`). |
| `local_simulation.py` | Simulation | Lazy ML imports & Type hint fixes. |
