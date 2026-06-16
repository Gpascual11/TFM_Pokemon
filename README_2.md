# TFM: Pokemon Battle AI Research Environment

Research workspace for building, benchmarking, and analyzing Pokemon Showdown agents:
- Heuristic agents.
- Adversarial search agents (minimax and MCTS).
- RL pipelines and evaluation modules.
- LLM-based agents (Pokechamp/Pokellmon integrations).
- Reporting pipeline (CSV -> plots/tables for the thesis report).

The project is optimized for local parallel simulation using Pokemon Showdown + `poke-env`.

## What Is New in This Refactor

- Consolidated singles heuristics to `src/p01_heuristics/` and deleted doubles logic.
- Consolidated shared core engine, scripts, and evaluation under `src/p00_core/`.
- Consolidated MCTS agent design under `src/p04_mcts/`.
- Renamed and flattened curriculum RL under `src/p05_ppo_drl/`.
- Added current benchmark engine behavior (parallel workers, resume-by-rerun, server restarts).
- Added dev tooling (`ruff`, `ty`) and reproducible environment notes (`uv`, Python 3.12).
- Added machine-specific tuning guidance for your CPU (`AMD Ryzen 7 5700X3D`, 16 threads, 32 GB RAM).

## Requirements

- Node.js 18+
- Python 3.12 (required by project constraints)
- `uv` package manager
- Local `pokemon-showdown` clone (inside this repository root)

## Quick Setup

### 1) Clone and install Pokemon Showdown

```bash
git clone https://github.com/smogon/pokemon-showdown.git
cd pokemon-showdown
npm install
```

### 2) Configure Showdown for local offline benchmarking

Create `pokemon-showdown/config/config.js` (from `config-example.js`) and set:
- `exports.loginserver = null;`
- Worker/subprocess values according to your machine profile.

Recommended starting point for your hardware (`Ryzen 7 5700X3D`, 16 threads, 32 GB RAM):

```js
exports.workerprocesses = 10;
exports.subprocesses = {
  network: 2,
  simulator: 10,
};
exports.loginserver = null;
```

Notes:
- This is a safe baseline for long runs and thermal stability.
- If stable, you can try `workerprocesses = 12` and `simulator = 12`.
- For LLM-backed evaluations, keep Python `--ports` low (usually `1-2`).

### 3) Python environment (`uv`)

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# From repository root
uv python install 3.12
uv sync
```

The project enforces Python 3.12 (`pyproject.toml`: `>=3.12,<3.13`).

## Optional Extras

### RL/GPU dependencies

```bash
uv sync --all-extras
```

If you need to force PyTorch wheel index:

```bash
# Example for CUDA 12.4 wheels
uv lock --index-url https://download.pytorch.org/whl/cu124 --extra-index-url https://pypi.org/simple
uv sync --all-extras --index-url https://download.pytorch.org/whl/cu124 --extra-index-url https://pypi.org/simple
```

## Project Map

- `src/p01_heuristics/`: Heuristic agents (v1-v14) and guides.
- `src/p02_imitation_learning/`: Imitation learning pipeline.
- `src/p03_minmax/`: Minimax search agents (v7, v15).
- `src/p04_mcts/`: Information Set MCTS agent layout.
- `src/p05_ppo_drl/`: Deep Reinforcement Learning environment and training curriculum.
- `src/p00_core/`: Core benchmark engine, reporting scripts, server utilities, and guides.
- `data/`: Benchmark outputs, run artifacts, and generated datasets.
- `report/`: Thesis report sources.
- `docs/`: Development and workflow documentation.

## Running Benchmarks

### 1) Start local servers (recommended script)

```bash
bash src/p00_core/scripts/launch_custom_servers.sh 4
```

This launches ports `8000-8003` and handles cleanup on exit.

Alternative:
- `bash src/p00_core/scripts/start_fixed_servers.sh` (legacy fixed 6-server launcher).

### 2) Heuristics benchmark (recommended entrypoint)

```bash
uv run python src/p00_core/engine/benchmark.py 1000 \
  --ports 4 \
  --concurrency 10
```

Key behavior:
- Runs a full matchup matrix.
- Writes outputs to `data/testing/benchmarks/`.
- Resume-by-rerun: run the same command again to complete missing games only.

### 3) LLM agent benchmark (low-port mode)

```bash
uv run python src/p00_core/engine/benchmark.py 20 \
  --agents pokechamp \
  --opponents v6 random \
  --ports 1 \
  --concurrency 2 \
  --player_backend ollama/qwen3:8b \
  --player_prompt_algo io
```

## Reporting and Analysis

### Heatmap/reporting

```bash
uv run python src/p00_core/reporting/plots/generate_full_report.py --data-dir data/benchmarks/all_10k/gen9randombattle
```

### WHR Elo Calculation

```bash
uv run python src/p00_core/reporting/elo/elo_ranking.py --data-dir data/benchmarks/all_10k/gen9randombattle
```

## Performance Tuning (Your Machine)

For `AMD Ryzen 7 5700X3D` + `32 GB RAM`:
- Start with `--ports 4` and `--concurrency 10` for singles heuristics.
- Increase gradually to `--ports 6-8` if RAM and stability remain good.
- For long gen sweeps, keep server restarts enabled in benchmark defaults.
- For LLM runs, prefer `--ports 1` and low concurrency due to backend latency.

If you hit memory pressure:
- Lower `--concurrency` first.
- Then lower `--ports`.
- Keep each run chunked (smaller `n_battles`) if needed.

## Developer Quality Tools

The project ships with:
- `ruff` for formatting/linting.
- `ty` for static type checking.

Useful commands:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check
```

## Troubleshooting

- `"Name taken"` / stuck sessions: restart local servers.
- Busy ports: stop old processes or restart launcher script.
- OOM during benchmarks: reduce `--concurrency` and/or `--ports`.
- Import issues: run from repo root and use `uv run python ...`.
- LLM backend failures: verify Ollama/model availability before launching runs.

## Useful Internal Docs

- `SETUP.md`: clean setup for new machines.
- `src/p01_heuristics/heuristics.md`: complete heuristics architecture guide.
- `src/p01_heuristics/docs/cli_reference.md`: full CLI options reference.
- `docs/development_tools.md`: editor/lint/type-check/LaTeX tooling.
