# Benchmark Infrastructure Fixes (Doubles)

This document details the critical fixes implemented to resolve the `ImportError` and execution hangs during the 2v2 (Doubles) heuristics benchmarking.

---

## 1. Resolution of `ImportError` (Package vs. Script)

### Issue

Executing `uv run python src/.../benchmark.py` or the worker subprocesses resulted in:
`ImportError: attempted relative import with no known parent package`

### Cause

When a Python file is executed directly as a script, its `__name__` becomes `"__main__"`, and it loses context of its position within the package hierarchy. This makes relative imports (e.g., `from ...core import ...`) invalid.

### Fix

Converted all relative imports within the evaluation engine to **Absolute Imports**:

- Changed `from ...core.factory import AgentFactory` → `from p01_heuristics.s02_doubles.core.factory import AgentFactory`.
- Added `PYTHONPATH=src` to the execution environment to ensure the top-level package `p01_heuristics` is discoverable.

---

## 2. Showdown Connection Protocol

### Issue

The benchmark would start, "Executing v1 vs v2", but then hang indefinitely with 0% CPU usage and no progress.

### Cause

`poke-env` transitions in recent versions require a valid URI for the Showdown server. Providing just `127.0.0.1:8000` triggered an `InvalidURI` exception inside the worker subprocesses, which was being swallowed by the parent process.

### Fix

Updated `ServerConfiguration` in `worker.py` to use the full WebSocket URI:
`ws://127.0.0.1:{port}/showdown/websocket`

---

## 3. Heuristic Base Class Fallbacks

### Issue

Any logic error inside a heuristic would cause a hard crash because the fallback method (`choose_random_doubles_move`) was missing in the base class.

### Cause

The `BaseHeuristic2v2` implementation was referencing an undefined attribute during error handling.

### Fix

Updated `BaseHeuristic2v2` in `src/p01_heuristics/s02_doubles/core/base.py`:

- Replaced the failing fallback with `super().choose_move(battle)`.
- Added comprehensive logging (`logger.error(..., exc_info=True)`) to capture the root cause of heuristic failures without stopping the entire benchmark.

---

## 4. Orchestration & Visibility Improvements

### Server Management

`benchmark.py` was updated to be more aggressive with server cleanup (`pkill -f pokemon-showdown`) before starting a new batch, preventing "Address already in use" errors.

### Output Streaming

Modified `worker.py` to use `print(..., flush=True)` (indirectly via removing reconfigure and ensuring standard print behavior) and updated the parent `benchmark.py` to capture and report `stderr` if a worker fails.

---

## ✅ Correct Execution Command

To run the benchmark with full visibility and resolved paths, use:

```bash
# From the project root (TFM_Pokemon)
PYTHONPATH=src uv run python src/p01_heuristics/s02_doubles/evaluation/engine/benchmark.py 1000 --ports 4
```

### Verification Checklist

1. [x] **Import Check**: `PYTHONPATH=src` allows absolute imports to resolve.
2. [x] **Connection Check**: `ws://` protocol ensures WebSocket handshake success.
3. [x] **Fallback Check**: `BaseHeuristic2v2` now defaults to `Player.choose_move` on errors.
4. [x] **Data Dir Check**: Results are stored in `data/benchmarks_doubles_unified/`.
