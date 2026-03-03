# heuristics/ — Internal Benchmark for Singles Agents

This sub-package contains all tools for testing and benchmarking the internal
heuristic agents (v1–v6) against each other and against poke-env baselines.

It is fully self-contained: no dependency on the Pokechamp repository.

---

## Entry Points

| Script | Command |
|--------|---------|
| **`run.py`** | Quick single-matchup simulation |
| **`benchmark.py`** | Full automated round-robin tournament |
| **`generate_report.py`** | Visual PNG report from benchmark results |

---

## Quick Start

### 1. Start the server

```sh
bash src/p03_scripts/p03_launch_custom_servers.sh 1
```

### 2. Single simulation

```sh
# v6 vs random, 100 games
uv run python src/p01_heuristics/s01_singles/heuristics/run.py v6 random 100
```

### 3. Full round-robin benchmark (all versions × all opponents)

```sh
# 1 000 games per matchup, 4 parallel ports, resumable
uv run python src/p01_heuristics/s01_singles/heuristics/benchmark.py 1000 -p 4 --resume
```

### 4. Generate visual report

```sh
uv run python src/p01_heuristics/s01_singles/heuristics/generate_report.py
```

Output: `heuristics/results/benchmark_report.png`

---

## CLI Reference: benchmark.py

| Argument | Default | Description |
|----------|---------|-------------|
| `total_games` | *(required)* | Games per matchup |
| `-p / --ports` | `8000` | Server port(s) |
| `--resume` | `false` | Skip completed matchups |
| `--data-dir` | `data/benchmarks_v2` | Battle CSV directory |
| `--output-csv` | `heuristics/results/benchmark_summary.csv` | Summary output |

---

## Reliability Features

- **Checkpointing**: saves after every matchup; `--resume` picks up where you left off.
- **Server restart**: clears Node.js worker leak before each matchup.
- **GC discipline**: explicit `gc.collect()` + object deletion between matchups.
- **Baselines**: each matrix includes `random`, `max_power`, `simple_heuristic`.

---

## Shared Dependencies

Agents and infrastructure are imported from the parent package:

```
s01_singles/
├── agents/    ← v1–v6 heuristic implementations
└── core/      ← BattleManager, ProcessLauncher, HeuristicFactory
```
