# `s01_singles` CLI Reference (Singles 1v1)

All commands below assume you run from the repository root and use `uv`:

```bash
uv run python <script> [args...]
```

---

## 1. Start Showdown servers

You need at least one local Showdown server before running battles.

```bash
bash src/p05_scripts/p05_launch_custom_servers.sh 1
```

This starts port `8000` (then `8001`, `8002`, … if you pass a larger number).

---

## 2. Parallel benchmark (recommended): `evaluation/engine/benchmark.py`

Runs a full matchup matrix (including self-play) and writes one CSV per matchup:
`data/1_vs_1/benchmarks/gens_10k_teams/gen9randombattle/{agent}_vs_{opponent}.csv`.

### Common runs

Rule-based matrix:

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 1000 \
  --ports 4 \
  --concurrency 10
```

LLM vs a few opponents (keep ports low):

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 20 \
  --agents pokechamp \
  --opponents v6 random \
  --ports 1 \
  --concurrency 2 \
  --player_backend ollama/qwen3:8b \
  --player_prompt_algo io
```

### Parameters

- **`n_battles`** *(positional)*: games per matchup.
- **`--agents <...>`**: primary agents to evaluate. If omitted, runs all registered heuristic and baseline agents from `AgentFactory` (no LLMs).
- **`--opponents <...>`**: opponent set. If omitted, runs all registered heuristic and baseline agents from `AgentFactory` (no LLMs).
- **`--ports N`**: number of worker ports (and processes) to use.
- **`--start-port P`**: first port (ports are `P..P+N-1`).
- **`--concurrency M`**: max concurrent battles per worker.
- **`--restart-every K`**: Restart Showdown servers every K **active** matchups (skipped matchups do not count). Use `0` to disable restarts.
- **`--out DIR`**: output directory for matchup CSVs.
- **`--battle-format FORMAT`**: e.g. `gen9randombattle`.
- **LLM-only (pokechamp/pokellmon/llm_vgc)**:
  - **`--player_backend BACKEND`**: e.g. `ollama/qwen3:8b`, `gemini-2.5-flash`.
  - **`--player_prompt_algo ALGO`**: usually `io`.
  - **`--temperature T`**.
  - **`--log-dir DIR`**: where pokechamp fork writes logs.

### Resume behavior

There is no `--resume` flag: re-running the exact same command will automatically
skip any matchup CSVs that already have `n_battles` rows.

---

## 3. Single worker batch: `evaluation/engine/worker.py`

Runs one `(agent vs opponent)` batch on a single port and writes a single CSV.
Mostly useful for debugging.

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/worker.py \
  --agent v6 \
  --opponent random \
  --n-battles 25 \
  --port 8000 \
  --concurrency 5 \
  --out /tmp/v6_vs_random.csv
```

LLM example:

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/worker.py \
  --agent pokechamp \
  --opponent random \
  --n-battles 1 \
  --port 8000 \
  --concurrency 1 \
  --player_backend ollama/qwen3:8b \
  --player_prompt_algo io \
  --out /tmp/pokechamp_vs_random.csv
```

---

## 4. Debug runner: `evaluation/debug/debug_runner.py`

Runs a few single battles (single-process) and prints turn progress.

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/debug/debug_runner.py \
  --backend ollama/qwen3:8b \
  --format gen9randombattle \
  --port 8000
```

---

## 5. Heuristic-only pipelines (legacy but still useful)

### `evaluation/engine/run_single.py`

Runs a single matchup using the `core/` pipeline (`BattleManager` / `ProcessLauncher`).
Default output goes to `data/1_vs_1/runs/`.

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/run_single.py v6 random 1000 \
  --ports 8000 8001 8002 8003
```

### `evaluation/engine/serial_benchmark.py`

Runs a heuristic-only round-robin matrix and writes into `--data-dir`.

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/serial_benchmark.py 1000 \
  --ports 4 \
  --resume
```

---

## 6. Reporting & Analytics

The reporting tools are designed to automatically save results into the source data directory.

### Full Scientific Report
Generates heatmaps, performance scatter plots, and LaTeX tables.
```bash
uv run python src/p01_heuristics/s01_singles/evaluation/reporting/plots/generate_full_report.py \
  --data-dir data/1_vs_1/benchmarks/gens_10k_teams/gen9randombattle
```

### Elo Ranking (MLE)
Calculates Bradley-Terry Elo ratings from all battles in a directory.
```bash
uv run python src/p01_heuristics/s01_singles/evaluation/reporting/elo/elo_ranking.py \
  --data-dir data/1_vs_1/benchmarks/gens_10k_teams/gen9randombattle
```

### Targeted Win-Rate Heatmap
```bash
uv run python src/p01_heuristics/s01_singles/evaluation/reporting/plots/generate_heatmap.py \
  --data-dir data/1_vs_1/benchmarks/gens_10k_teams/gen9randombattle \
  --agents v6 v5 random \
  --opponents v6 v5 random
```

### Per-Agent Metrics Report
```bash
uv run python src/p01_heuristics/s01_singles/evaluation/reporting/plots/generate_report.py \
  --data-dir data/1_vs_1/benchmarks/gens_10k_teams/gen9randombattle \
  --agent v6
```

