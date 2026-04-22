# s01_singles: High-Performance Pokémon Heuristics Framework

> **The definitive environment for developing, benchmarking, and analyzing Pokémon Singles (1v1) agents.**

This framework bridges the gap between rule-based heuristics and Large Language Model (LLM) agents. It provides a robust, memory-safe, and highly parallelized platform for evaluating Pokémon Showdown strategies at scale.

---

## 1. Architecture Overview

The system is designed with **Subprocess Isolation** at its core. Pokémon simulation in Python is notoriously prone to memory leaks and thread deadlocks. To solve this, we use a **Master-Worker** pattern.

### Thread-Safe Parallelism

Instead of sharing state between threads, the system spawns **independent OS processes** for every chunk of work.

- **Orchestrator (`benchmark.py`)**: The brain of the operation. It manages task distribution, port allocation, and final data consolidation.
- **Worker (`worker.py`)**: Individual soldiers. Each worker runs in its own memory space, connects to a local Showdown port, plays a batch of games, and terminates—cleaning up all RAM usage automatically.

---

## 2. Directory Structure & Logic

### `core/` — The Foundation

Contains the shared infrastructure required to build and run any agent.

- **`factory.py`**: The *Unified AgentFactory*. This is the only entry point you need to instantiate any agent by its name (e.g., `"v6"`, `"abyssal"`, `"pokechamp"`).
- **`base.py`**: Definites the `BaseHeuristic1v1` contract. All custom heuristics must implement the `_select_action` method.
- **`common.py`**: Mathematical utilities (Speed tier calculation, damage estimation) used across multiple heuristic versions.

Categorized into three distinct families:

1. **`internal/`**: Our custom heuristic evolution (**V1 to V6**).
2. **`baselines/`**: Standard rule-based players including `random`, `max_power`, and `simple_heuristic`.
3. **`llm/`**: Connectors for agents like `Pokechamp` and `Pokellmon` that use Ollama as a thinking backend.

### `evaluation/` — The Proving Grounds

- **`engine/`**: Contains the `benchmark.py` and `worker.py` scripts. Use these for 90% of your testing.
- **`reporting/`**: Python scripts to turn massive CSV files into readable heatmaps and charts.
- **`docs/`**: Deep-dive technical guides (see [docs/s01_parallel_benchmark_guide.md](docs/s01_parallel_benchmark_guide.md)).

---

## 3. The Heuristic Evolution (V1 - V6)

Each version builds upon the successes and failures of the previous one:

| Version | Key Logic | Defensive Strategy |
| :--- | :--- | :--- |
| **V1** | Primary Power | Random switching. |
| **V2** | Physical/Special Split | Type-disadvantage awareness. |
| **V3** | **Defensive Stability** | Escape Toxic/Bad matchups + Speed-check pivoting. |
| **V4** | Field-Aware Damage Overhaul | Burn penalty + STAB + Weather/Terrain scaling. |
| **V5** | **Boost-Aware Field Expert** | Stat-boost-aware damage + KO pre-check + relaxed pivoting. |
| **V6** | **The Peak** | Priority move valuation + Refined field awareness. |

---

## 4. Usage Guide

For a full list of runnable commands and CLI flags, see [docs/s01_cli_reference.md](docs/s01_cli_reference.md).  
For the on-disk outputs layout, see [docs/s01_data_layout.md](docs/s01_data_layout.md).

### Running a Full Tournament

To run 1000 battles per matchup between all heuristics and baselines across 4 parallel workers:

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 1000 \
    --ports 4 \
    --concurrency 10
```

### Evaluating LLMs

Only run 1 or 2 ports for LLMs to avoid GPU bottlenecking:

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 50 \
    --agents pokechamp \
    --opponents v6 random \
    --ports 1 \
    --concurrency 2
```

### Generating the Heatmap

Once CSVs are generated in `data/1_vs_1/benchmarks/unified/`:

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/reporting/plots/generate_heatmap.py
```

---

## 5. Features You Should Know

### 1. Resume & Complete

If a benchmark is interrupted (crash, power loss, manual stop), simply **run the same command again**. The system will scan existing files, calculate the missing games, and finish them automatically.

### 2. Thinking Logs

When using LLM agents, a full chain-of-thought is saved for every single move.

- **Location**: `src/p01_heuristics/s01_singles/evaluation/results/LLM/`
- **Files**: `thinking_*.txt` (The rationale) and `decisions_*.txt` (The final choice).

### 3. Server Management

The benchmark automatically launches the required number of local Showdown servers. The default is `--restart-every 3` (recommended for long runs); increase or decrease as needed.

---

## 6. Advanced Battle Analytics (New!)

The evaluation engine now captures deeply granular data for every battle, providing insights far beyond simple winrates.

### Strategic Metrics
- **Switch Intelligence**: Tracks `voluntary_switches` (strategic) vs `forced_switches` (due to faints), allowing you to measure agent "pivoting" efficiency.
- **Move Usage Profiling**: Serialized move statistics (e.g., `bugbuzz:5|airslash:3`) to identify "spamming" patterns or preferred finishing moves.

### Luck & RNG Tracking
- **RNG Metrics**: Explicitly counts `critical_hits`, `misses`, and `super_effective_hits` for both players. This is essential for identifying "lucky wins" in large-scale simulations.

### Micro-State Monitoring
- **Team HP %**: Cumulative team health percentage (0.0 to 6.0) and percentage (0-100%) to differentiate between "close wins" and crushing victories.
- **Side Conditions**: Active hazards (Spikes, Stealth Rock, Sticky Web) are tracked per-side.
- **Detailed Team State**: Per-Pokémon items, abilities, and status effects (including `FNT` for fainted mons) are serialized into the CSV for deep post-game analysis.

---

## 7. Performance Monitoring

A new `matchup_performance.csv` is generated for every benchmark run to help optimize high-concurrency 10k game runs.

- **Seconds per Game (SPG)**: Real-time monitoring of agent decision speed.
- **Duration Tracking**: Total time taken per matchup to help plan long-running experiments.
- **Subfolder Organization**: Results are automatically grouped by battle format (e.g., `data/.../gens_10k_teams/gen9randombattle/`) to keep multi-generation data clean.

---

## 8. Troubleshooting

- **"Port Busy"**: Use `pkill node` or wait 10 seconds for the OS to release the port.
- **"Out of Memory"**: Reduce your `--concurrency` flag. Start with `5` and work your way up.
- **"Ollama Connection Failed"**: Ensure Ollama is running (`ollama ps`) and you have pulled the model (`ollama pull qwen3.5:8b`).

---

## 9. License & Credits

Developed as part of the **TFM Pokémon Research Project**. Built on top of the incredible `poke-env` library and the Pokémon Showdown engine.