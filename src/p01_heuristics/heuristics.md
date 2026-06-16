# Heuristics: High-Performance Pokémon Heuristics Framework

> **The definitive environment for developing, benchmarking, and analyzing Pokémon heuristics agents.**

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

### `src/p01_heuristics/` — Heuristics Logic

- **`agents/`**: Contains the heuristic agent implementations, categorized into two families:
  - **`internal/`**: Our custom heuristic evolution (**V1 to V14**).
  - **`baselines/`**: Standard rule-based players including `random`, `max_power`, and `simple_heuristic`.

### `src/p00_core/` — The Shared Core

All core systems, benchmarking scripts, and documentation are shared in the `p00_core` directory:
- **`core/`**: Contains the base classes (`BaseHeuristic1v1`), factories (`AgentFactory`, `HeuristicFactory`), and parallel simulation engine.
- **`engine/`**: Contains the `benchmark.py` and `worker.py` tournament scripts.
- **`reporting/`**: Python scripts to turn massive CSV files into readable heatmaps, Elo rankings, and charts.
- **`docs/`**: Deep-dive technical guides (see [docs/parallel_benchmark_guide.md](../p00_core/docs/parallel_benchmark_guide.md)).

---

## 3. The Heuristic Evolution (V1 - V14)

Each version builds upon the successes and failures of the previous ones:

| Version | Key Logic | Switching Strategy |
| :--- | :--- | :--- |
| **V1** | Max `bp × eff × stab` | None |
| **V2** | Stats-based damage + burn penalty | TOX escape + outsped pivot |
| **V3** | V2 + per-battle move tracking | Same as V2 |
| **V4** | V3 + weather/terrain + accuracy × priority | V3 triggers + smart type-based target |
| **V5** | V4 + stat-boost-aware damage | V3 triggers + smart type-based target |
| **V6** | V3 + weather/terrain/priority (lightweight) | V3 triggers (slot 0) |
| **V7** | Hazards + setup + KO check + matchup switching | Matchup score (Abyssal formula) |
| **V8** | V7 + item/ability/screen/Trick Room awareness | Matchup + Trick Room reversal |
| **V9** | V7 boost core + tight hazards & setup on free turns | Same as V7 |
| **V10** | V8 core + status moves (Toxic/WoW/TWave) | V8 matchup switch + ≤20% HP sack logic + Volt Switch/U-turn pivot |
| **V11** | Hybrid (V9 + V10) + Gen-Aware adaptations | Same as V10 |
| **V12** | V11 + Gen 9 Terastallization | V11 + Matchup-based Lead (teampreview) & Matchup-based Fainted switch-in |
| **V13** | V12 + Showdown sets prediction + Sweeper reaction + Smart recovery/draining + Dynamic hazards + Conservative Tera | V12 + Move- & Stat-Aware matchup damage calculations + Choice-lock exploitation + Fixed bench switch fallback bug |
| **V14** | V13 + Advanced opponent switch prediction (Yomi Layer 1) | V13 + Profiling of human strategic playstyles (predictive vs conservative) |

### Key Research Finding

V1, V2, V3, and V6 perform similarly, proving that naive damage optimization plateaus quickly. Positional awareness (V7/V8) and tactical refinements (V9/V10/V11) close the gap to strong baselines. **Heuristic V12 is the first agent in project history to beat both Abyssal and SimpleHeuristic in Gen 9 Random Battles over a large-scale 10,000-game tournament**, achieving a **59.8% win rate** against Abyssal. **Heuristic V13 takes this a step further**, achieving a **90% win rate against V12** in validation tests. **Heuristic V14** adds predictive counter-switching to further exploit opponent patterns.

---

## 4. Usage Guide

For a full list of runnable commands and CLI flags, see [docs/cli_reference.md](docs/cli_reference.md).  
For the on-disk outputs layout, see [docs/data_layout.md](../p00_core/docs/data_layout.md).  
For CSV column documentation, see [docs/csv_schema.md](../p00_core/docs/csv_schema.md).

### Running a Full Tournament

To run 10,000 battles per matchup between all heuristics and baselines across 4 parallel workers:

```bash
uv run python src/p00_core/engine/benchmark.py 10000 \
    --ports 4 \
    --concurrency 10
```

### Running a Specific Generation

```bash
uv run python src/p00_core/engine/benchmark.py 10000 \
    --ports 4 \
    --concurrency 10 \
    --battle-format gen4randombattle
```

### Evaluating LLMs

Only run 1 or 2 ports for LLMs to avoid GPU bottlenecking:

```bash
uv run python src/p00_core/engine/benchmark.py 50 \
    --agents pokechamp \
    --opponents v8 random \
    --ports 1 \
    --concurrency 2
```

### Generating the Heatmap

Once CSVs are generated in `data/benchmarks/all_10k/`:

```bash
uv run python src/p00_core/reporting/plots/generate_heatmap.py
```

---

## 5. Features You Should Know

### 1. Resume & Complete

If a benchmark is interrupted (crash, power loss, manual stop), simply **run the same command again**. The system will scan existing files, calculate the missing games, and finish them automatically.

### 2. Strategy Tracking (V7+)

The CSV output includes per-battle counters proving intelligent play:
- `hazard_sets_us`: Times entry hazards were deliberately set
- `setup_uses_us`: Times boost moves (Swords Dance, etc.) were used
- `ko_checks_us`: Times a guaranteed KO was detected and executed
- `matchup_switches_us`: Times switching was triggered by type matchup analysis

These are always 0 for V1-V6, providing direct evidence that V7+ agents make qualitatively different decisions.

### 3. Thinking Logs (LLM Agents)

When using LLM agents, a full chain-of-thought is saved for every single move.

- **Location**: `src/p00_core/results/LLM/`
- **Files**: `thinking_*.txt` (The rationale) and `decisions_*.txt` (The final choice).

### 4. Server Management

The benchmark automatically launches the required number of local Showdown servers. The default is `--restart-every 3` (recommended for long runs); increase or decrease as needed.

---

## 6. Battle Analytics

The evaluation engine captures deeply granular data for every battle (46 columns per game). See [docs/csv_schema.md](../p00_core/docs/csv_schema.md) for the complete schema.

### Decision Quality
- **Fallback rate**: How often the agent couldn't decide and fell back to random.
- **Error rate**: How often the agent's logic crashed internally.

### Strategic Metrics
- **Switch Intelligence**: Tracks `voluntary_switches` (strategic) vs `forced_switches` (due to faints).
- **Move Usage Profiling**: Serialized move statistics (e.g., `stealthrock:2|swordsdance:1|earthquake:5`).

### Luck & RNG Tracking
- **RNG Metrics**: Explicitly counts `critical_hits`, `misses`, and `super_effective_hits` for both players. Essential for identifying "lucky wins" in large-scale simulations.

### Strategy Metrics (V7+)
- **Hazard Management**: How often hazards were set vs removed.
- **Setup Usage**: How often boost moves were used.
- **KO Detection**: How often guaranteed knockouts were identified and executed.

---

## 7. Statistical Methodology

See [docs/statistical_justification.md](../p00_core/docs/statistical_justification.md) for the full analysis.

- **10,000 games per matchup** provides ±0.98% precision at 95% confidence.
- Can reliably detect win rate differences of ≥2 percentage points.
- Pool size (number of Pokemon per gen) does NOT affect required sample size.

---

## 8. Performance Monitoring

A `matchup_performance.csv` is generated for every benchmark run to help optimize high-concurrency runs.

- **Seconds per Game (SPG)**: Real-time monitoring of agent decision speed.
- **Duration Tracking**: Total time taken per matchup to help plan long-running experiments.
- **Subfolder Organization**: Results are automatically grouped by battle format (e.g., `data/.../gens_10k_teams/gen9randombattle/`).

---

## 9. Troubleshooting

- **"Port Busy"**: Use `pkill node` or wait 10 seconds for the OS to release the port.
- **"Out of Memory"**: Reduce your `--concurrency` flag. Start with `5` and work your way up.
- **"Ollama Connection Failed"**: Ensure Ollama is running (`ollama ps`) and you have pulled the model (`ollama pull qwen3:8b`).
