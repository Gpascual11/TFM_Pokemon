# EVALUATION: Testing, Benchmarking & Analysis

The `evaluation` directory is the laboratory of the Singles (1v1) framework. It provides a robust, parallelized infrastructure to execute thousands of Pokémon battles and transform the raw logs into scientific insights.

---

> [!TIP]
> - For a complete list of CLI flags and `uv` commands, see [docs/s01_cli_reference.md](../docs/s01_cli_reference.md).
> - For information on the on-disk storage structure, see [docs/s01_data_layout.md](../docs/s01_data_layout.md).
> - For column documentation, see [docs/s01_csv_schema.md](../docs/s01_csv_schema.md).
> - For statistical methodology, see [docs/s01_statistical_justification.md](../docs/s01_statistical_justification.md).

---

## 1. Directory Structure

| Folder | Purpose | Key Scripts |
| :--- | :--- | :--- |
| **`engine/`** | Core execution logic | `benchmark.py`, `worker.py`, `run_single.py` |
| **`reporting/`** | Data analysis & Viz | `plots/generate_full_report.py`, `elo/elo_ranking.py` |
| **`debug/`** | Granular inspection | `debug_runner.py` |

---

## 2. The Benchmark Engine (`engine/`)

The engine is built on a **Master-Worker** architecture designed to solve the two biggest hurdles in Python-based Pokémon simulation: **Memory Leaks** and **Thread Deadlocks**.

### The Parallel Orchestrator (`benchmark.py`)
This is the main entry point for large-scale experiments. It manages the "Matchup Matrix," distributing pairings to available workers and merging the final CSV data.
- **Auto-Resume**: It intelligently skips already-completed matchups by scanning the output directory.
- **Safety Restarts**: Restarts local Showdown servers periodically (default: every 3 matchups) to prevent Node.js memory exhaustion.

### The Subprocess Worker (`worker.py`)
Each worker runs in its own **isolated OS process**. This ensures that if a battle logic or server communication error occurs, it is contained within that process and doesn't crash the entire benchmark.
- **Chunked Processing**: Battles are processed in batches (e.g., 250 at a time) with explicit Garbage Collection calls between them.
- **46-Column CSV Output**: Each battle records identity, outcome, decision quality, team state, tactical tracking, RNG metrics, and strategy counters. See [docs/s01_csv_schema.md](../docs/s01_csv_schema.md) for the full schema.

---

## 3. Battle Data Captured (46 Columns)

Every battle produces a rich data row covering 7 categories:

| Category | Columns | Purpose |
| :--- | :--- | :--- |
| Identity & Outcome | 8 | battle_id, format, agents, winner, turns, timestamp |
| Decision Quality | 6 | decisions, fallbacks, errors (both sides) |
| Team State | 12 | fainted, remaining, HP, team composition, side conditions |
| Tactical Tracking | 4 | voluntary/forced switches, move usage stats |
| RNG & Luck | 6 | crits, misses, super-effective hits (both sides) |
| Strategy (V7+) | 10 | hazard sets/removals, setup uses, KO checks, matchup switches |

Strategy columns are always 0 for V1-V6 and baselines. Non-zero values in V7+ prove the strategy logic is actively firing.

---

## 4. Reporting & Analytics (`reporting/`)

We have moved away from simple win-rate percentages to a multi-dimensional performance analysis.

### Scientific Visualization (`plots/`)
- **`generate_full_report.py`**: The primary analytical tool. It generates 11 distinct plots covering:
    - **Performance**: Heatmaps, sorted win-rate bar charts, and baseline comparisons.
    - **Efficiency**: Decision speed vs. win-rate scatter plots.
    - **Tactics**: Survival dominance, hazard management, and luck variance (RNG tracking).
- **`generate_heatmap.py`**: A specialized tool for creating targeted win-rate matrices.
- **`generate_report.py`**: Generates a detailed single-agent performance summary, useful for deep-dives into a specific version's strengths and weaknesses.
- **`styling.py`**: Internal utility that ensures a consistent visual aesthetic across all generated charts (premium color palettes and professional typography).

### Elo Ranking (`elo/`)
- **`elo_ranking.py`**: Uses **Maximum Likelihood Estimation (MLE)** via the Bradley-Terry model to calculate precise Elo ratings. Unlike standard Elo, this handles our non-linear "round-robin" data with high statistical confidence.
- **`s01_elo_reporting.md`**: Technical documentation explaining the mathematical foundations of the Bradley-Terry ranking system used in this project.

---

## 5. Granular Debugging (`debug/`)

When a specific agent version starts behaving unexpectedly, use the **`debug_runner.py`** (located in `evaluation/debug/`).
- Unlike the parallel engine, this runs in a single process and prints **turn-by-turn logic**.
- It allows you to see the "Thinking" logs in real-time to identify exactly which move evaluation caused a strategic error.

---

## 6. Data & Results Policy

**Co-location Policy**: To ensure research portability, we no longer store results in a centralized `results/` folder inside the source tree. 
- All plots, Elo ratings, and LaTeX tables are now saved **directly inside the data directory** (e.g., `data/benchmarks/all_10k/gen9randombattle/`).
- This makes it easy to archive and share the entire experimental context (raw data + analysis) as a single unit.

---

## 7. Statistical Methodology

All benchmarks use **10,000 games per matchup** per generation, providing:
- ±0.98% precision at 95% confidence
- Reliable detection of win rate differences ≥2 percentage points
- Same sample size across all generations (gen1-gen9) for uniform methodology

Pool size (number of Pokémon per gen) does NOT affect required sample size — the binary outcome variance `p(1-p)/n` is independent of game complexity. See [docs/s01_statistical_justification.md](../docs/s01_statistical_justification.md) for the full mathematical justification.

---

## 8. Performance & Scalability

The framework has been optimized for high-concurrency 10k-game runs:
- **Global Sets Cache**: By caching Pokémon set data (2.6MB) once per process instead of once per Pokémon, we reduced RAM usage from **31GB** to **13GB** for 8 parallel ports.
- **Optimized Throughput**: Recommended settings are **25 concurrency per port** with **8-16 parallel ports** (depending on your CPU). This keeps the CPU at 100% utilization while keeping RAM overhead flat.
