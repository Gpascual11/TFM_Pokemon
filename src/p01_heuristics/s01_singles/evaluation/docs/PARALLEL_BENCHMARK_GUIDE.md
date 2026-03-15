# 🚀 The Definitive Guide to the Pokémon Parallel Benchmark System

This document provides an exhaustive explanation of the High-Performance Evaluation Framework. Designed for developers and researchers, this guide covers architecture, memory-safety patterns, concurrency models, and advanced usage scenarios.

---

## 📖 1. System Philosophy: Isolation is Safety

The primary challenge in simulating thousands of Pokémon battles is **state corruption** and **resource exhaustion**. Python's Global Interpreter Lock (GIL) and the memory-hungry nature of `poke-env` and LLM backends (like Ollama) make monolithic runners unstable at scale.

This system is built on the core principle of **Subprocess Isolation**:

1. **The Orchestrator (`benchmark.py`)** never plays a single match. It only manages the "Queue of Work."
2. **The Workers (`worker.py`)** are ephemeral. They are born, perform a single task, and die.
3. **Result Persistence**: Results are streamed to disk continuously, ensuring that a crash in Game #999 doesn't lose the data from Game #1.

---

## 🏗️ 2. Detailed Internal Logic

### 2.1 The Master Orchestrator Strategy

When you run a tournament, the `benchmark.py` script executes the following handshake:

1. **Matchup Generation**: It uses the `AgentFactory` to resolve labels into classes. It then builds a Cartesian product of all requested `--agents` and `--opponents`, **including self-matchups** (e.g., `v6 vs v6`).
2. **Missing Data Analysis (Self-Healing)**:
    - For every matchup (e.g., `v1 vs random`), it checks if `data/1_vs_1/benchmarks/unified/v1_vs_random.csv` exists (legacy: `data/1_vs_1/benchmarks_unified/...` or `data/benchmarks_unified/...`).
    - If it exists, it reads the row count.
    - If `row_count < target_n`, it calculates precisely how many battles are left to play.
    - If `row_count >= target_n`, it skips that matchup entirely.
3. **Server Startup**: It calls `src/p05_scripts/p05_launch_custom_servers.sh` to spawn `N` separate Node.js processes for Pokémon Showdown on consecutive ports.
4. **Optimized Restarts**: The `--restart-every K` counter only increments when at least one battle is actually executed. Skipped matchups during resume do not trigger server restarts.
5. **Self-Healing Retry Loop**: If a worker batch fails or times out, the orchestrator recalculates the missing games and re-queues them. It will continue looping until the target number of games is reached or no progress is being made.
6. **Port-Aware Delegation**: It initializes an `asyncio.Queue` containing all available ports. It then starts workers:
    - A worker is popped from the queue.
    - It is assigned a port and a batch of battles.
    - When the worker finishes, the port is returned to the queue for the next batch.

### 2.2 The Worker's Internal Loop

The `worker.py` script is highly optimized for RAM:

1. **Directory Switching**: It automatically changes its working directory to `pokechamp/`. This ensures that `poke-env` can find its internal static data files (like move effects and ability tables) without path errors.
2. **The Chunking Engine**:
    - It splits its assigned batch into smaller **chunks of 25**.
    - It utilizes `await player.battle_against(...)`.
    - After 25 battles, it iterates through the finished battles, extracts the 11 key metrics (won, turns, fainted_us, hp_opp, etc.), and appends them to a **Worker-Unique CSV**.
    - It calls `player.reset_battles()` to clear all reference IDs.
    - It explicitly invokes `gc.collect()` to force Python to clear deleted objects from RAM.

---

## 🤖 3. Catalog of Available Agents

The `AgentFactory` (and its alias `HeuristicFactory`) allows you to swap agents simply by using their string labels.

### 🏠 Internal Heuristics

| Label | Description | Characteristics |
| :--- | :--- | :--- |
| `v1` | Phase 1 baseline | High switch frequency, simple power checks. |
| `v2` | Phase 2 refactor | Improved damage calculations and basic switching. |
| `v3` | Defensive Pivot | Tracks moves and switches defensively (Toxic escape). |
| `v4` | Field Strategist | Advanced scoring with Weather and Terrain support. |
| `v5` | Expert Model | Accounts for Stat Boosts (stages) in damage. |
| `v6` | Current Peak | Dynamic field evaluation + Priority move optimization. |

### 📊 Baselines & Poke-Env Standards

| Label | Family | Logic |
| :--- | :--- | :--- |
| `random` | Standard | Chooses a random legal move. |
| `max_power` | Standard | Chooses the move with the highest base power. |
| `simple_heuristic` | Optimized | Use basic type-effectiveness table. |
| `abyssal` | Pokechamp | Uses the Abyssal rule-set for singles. |
| `one_step` | Pokechamp | Evaluates moves based on one-step lookahead. |
| `safe_one_step` | Pokechamp | One-step damage-based lookahead using poke_env only (no LocalSim/prompts). |

### 🧠 LLM / AI Agents

| Label | Backend | Description |
| :--- | :--- | :--- |
| `pokechamp` | Ollama/Qwen | Full reasoning-based agent with thinking logs. |
| `pokellmon` | Ollama/Llama | Chain-of-thought agent for competitive play. |

---

## 🛠️ 4. Master Command Configuration

### 4.1 Running a Full Tournament

The standard way to execute a large-scale evaluation between rule-based agents:

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 1000 \
    --ports 8 \
    --concurrency 10 \
    --restart-every 5
```

**Math Breakdown**:

- **Total Battles**: 1,000 per matchup.
- **Batches**: 125 battles per server (across 8 ports).
- **Parallel Speed**: With concurrency 10, each server plays 10 simultaneous games. If 1 game takes 5s, the whole 1000 games finish in roughly **~1 minute**.

### 4.2 The "Single Surgeon" (Debugging)

If a specific agent keeps crashing, run only that matchup on a single port for debugging:

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 50 \
    --agents v6 \
    --opponents v6 \
    --ports 1 \
    --concurrency 1
```

### 4.3 Parallel LLM Execution (IMPORTANT)

LLMs have a **GPU serialization bottleneck**. Parallelizing them requires care:

- **Rule of Thumb**: Set `--ports` to the number of GPUs you have. If you have 1 GPU, set `--ports 1`.
- **Reason**: 4 workers asking Ollama for answers at the same time will not run faster; they will just time out.
- **Command**:

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 20 \
    --agents pokechamp \
    --ports 1 \
    --concurrency 2
```

---

## 🔄 5. Understanding Concurrency vs Ports

This is the most common point of confusion.

- **Ports (`--ports N`)**: This is **Process-Level Parallelism**. It starts `N` separate Python programs and `N` server instances. It consumes a massive amount of **RAM**.
- **Concurrency (`--concurrency M`)**: This is **Asyncio-Level Parallelism**. A single Python process plays `M` games. It is very efficient but puts high load on the same Showdown server.

**Optimization Table**:

| Memory | CPU | Configuration |
| :--- | :--- | :--- |
| 8GB RAM | 4 Cores | `--ports 2 --concurrency 5` |
| 16GB RAM | 8 Cores | `--ports 4 --concurrency 10` |
| 32GB+ RAM | 16 Cores | `--ports 8 --concurrency 20` |

---

## 🔦 6. Troubleshooting & FAQs

### Q: Why do I see "Port 800X is busy"?

Sometimes the Node.js server doesn't die immediately. Use `fuser -k 8000/tcp` to manually kill it, or run the benchmark again; the `--restart-every` logic will attempt to `pkill` them automatically.

### Q: Where are my results?

- **Combined CSV**: `data/1_vs_1/benchmarks/unified/` (legacy: `data/1_vs_1/benchmarks_unified/` or `data/benchmarks_unified/`)
- **Thinking Logs**: `src/p01_heuristics/s01_singles/evaluation/results/LLM/`
- **Temporary Buffers**: If you see files starting with `_tmp_`, it means the benchmark is still running or was interrupted. The next run will clean them up.

### Q: What is the "Resume" logic checking?

It checks for **Total Line Count** (excluding header). If the file exists and is empty, it will restart from game zero.

---

## 🦙 Ollama & LLM Backend Setup

The LLM agents (`pokechamp`, `pokellmon`) rely on **Ollama** as the inference engine. You must ensure it is installed and the models are pre-downloaded.

### 1. Installation

If you don't have Ollama, install it via the official script:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Check if it's Running

You can verify the status of the Ollama service using:

```bash
# Check if the process is active
ollama ps

# Or via systemd
systemctl status ollama
```

### 3. Pulling the Models

The agents expect specific models to be available locally. Before running a benchmark, pull the models:

```bash
ollama pull qwen3.5:8b
# Or whichever model is specified in your backend flag
```

---

## 🔬 Agent Comparison: Abyssal vs. SimpleHeuristic

If you notice a **~50.0% Win Rate** between `abyssal` and `simple_heuristic`, it is because they are **internally identical**.

- Both agents use the same heuristic coefficients (`SPEED_TIER=0.1`, `HP=0.4`) and the same damage estimation logic.
- `abyssal` is the baseline included in the `pokechamp` repository fork.
- `simple_heuristic` is our local implementation of that same logic.
- They are both highly effective rule-based agents, but fighting each other results in a "mirror match."

---

## 📁 7. File Directory Reference

```text
src/p01_heuristics/s01_singles/
├── core/
│   └── factory.py        <-- Agent Management
├── evaluation/
│   ├── docs/
│   │   └── PARALLEL_BENCHMARK_GUIDE.md <-- THIS FILE
│   ├── engine/
│   │   ├── benchmark.py  <-- The Orchestrator
│   │   └── worker.py     <-- The Worker
│   └── results/          <-- LLM logs and JSONs
data/
└── 1_vs_1/
    └── benchmarks/
        └── unified/    <-- CSV Tournament Outputs
```
