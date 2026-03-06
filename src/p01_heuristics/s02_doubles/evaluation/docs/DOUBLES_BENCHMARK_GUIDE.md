# ⚔️ High-Performance Doubles Benchmark Guide

Welcome to the **Unified Doubles Benchmarking System**. This guide provides a comprehensive breakdown of the architecture, logic, and operational procedures for running large-scale Pokémon Double Battle (2v2) simulations.

---

## 🏗️ System Architecture

The benchmarking framework uses a **Master-Worker subprocess architecture** designed for extreme reliability and horizontal scalability.

### 1. The Orchestrator (`benchmark.py`)

- **Master Process**: Manages the tournament queue and port allocation.
- **Port Queue**: Uses `asyncio.Queue` to dynamically assign available Showdown servers to incoming matchups.
- **Resumption Logic**: Scans existing CSVs in `data/benchmarks_doubles_unified/`. If a matchup (e.g., `v6_vs_abyssal`) has 450/1000 games, it only requests the remaining 550.
- **Memory Safety**: Periodic server restarts (default: every 10 matchups) to clear Node.js memory bloat.

### 2. The Worker (`worker.py`)

- **Self-Contained Subprocess**: Each batch of games runs in a fresh Python process. This is CRITICAL for memory management because:
  - It ensures all RAM is reclaimed by the OS between matchups.
  - It contains memory leaks from background threads (especially from LLM libraries).
  - It allows for granular garbage collection (`gc.collect`) every 25 games.
- **Result Streaming**: Results are written directly to temporary CSVs to prevent data loss in case of a crash.

---

## 🧠 Agent Catalog (Doubles)

### 🔴 Internal Heuristics

| Agent | Description | Strategy Focus |
| :--- | :--- | :--- |
| `v1` | **Maximum Damage** | Simple greedy selection of the highest base power moves. |
| `v2` | **Type Advantage** | Basic type-effectiveness scoring and switching. |
| `v6` | **Advanced VGC** | Advanced KO detection, defensive pivoting, and state analysis. |

### 🔵 Baselines & Opponents

| Agent | Source | Characteristics |
| :--- | :--- | :--- |
| `abyssal` | Abyssal Bot | Strong rule-based baseline. |
| `vgc` | Specialized | Focuses on speed control and spread damage (Spread moves, Tailwind). |
| `one_step` | Lookahead | Simulates one turn ahead to find optimal moves. |
| `max_power` | Baseline | Only uses the move with the highest power. |
| `random` | Baseline | Selects moves entirely at random. |
| `simple_heuristic` | Baseline | Basic rule-based player from `poke-env`. |

---

## 🤖 LLM Benchmarking (`benchmark_llm.py`)

LLM agents require special handling due to their resource intensity (Ollama/GPU).

### Why Separate?

1. **GPU RAM**: Running multiple LLM instances simultaneously can easily exceed VRAM. `benchmark_llm.py` defaults to 1 worker.
2. **Logging**: LLM agents generate detailed **Thought Logs** (Chain-of-Thought) and **Decision Logs** which are saved to `src/p01_heuristics/s02_doubles/results/LLM/`.
3. **Latency**: LLM turns take 1-5 seconds, whereas heuristics take milliseconds. Mixing them in the general benchmark slows down everything.

### LLM Agents

- `pokechamp`: Uses a **Minimax Algorithm** enhanced by LLM evaluation for state scoring.
- `pokellmon`: A pure LLM agent with various prompt strategies for double battles.

---

## 🛠️ Usage Commands

### Standard Tournament

Run 1000 games per matchup using 4 servers:

```bash
uv run python src/p01_heuristics/s02_doubles/evaluation/engine/benchmark.py 1000 --ports 4
```

### LLM Focused Run

Run 100 games for LLM agents against specific opponents:

```bash
uv run python src/p01_heuristics/s02_doubles/evaluation/engine/benchmark_llm.py 100 --agents pokellmon pokechamp --opponents v6 random
```

---

## 📊 Results & Reporting

1. **CSVs**: All raw data is stored in `data/benchmarks_doubles_unified/`.
2. **Logs**: LLM thinking files are in `src/p01_heuristics/s02_doubles/results/LLM/`.
3. **Heatmaps**: Generate a visual matrix of win rates:

   ```bash
   uv run python src/p01_heuristics/s02_doubles/evaluation/reporting/heatmaps.py
   ```

---

## 🔍 Troubleshooting & Verification

- **Check Server Status**: If battles aren't starting, ensure no other `pokemon-showdown` processes are hogging ports:

  ```bash
  pkill -f pokemon-showdown
  ```

- **Verify RAM**: If system slows down, check worker concurrency. Doubles usage is higher than Singles. Default of 10-15 per worker is usually safe.
- **CSV Corruptions**: If a CSV is corrupted, delete it; the orchestrator will automatically re-run those games on the next start.
