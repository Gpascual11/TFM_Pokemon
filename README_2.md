# TFM: Pokemon Battle AI Research Environment

Research workspace for building, benchmarking, and analyzing Pokemon Showdown agents:
- Heuristic agents (singles and doubles).
- RL pipelines and evaluation modules.
- LLM-based agents (Pokechamp/Pokellmon integrations).
- Reporting pipeline (CSV -> plots/tables for the thesis report).

The project is optimized for local parallel simulation using Pokemon Showdown + `poke-env`.

## What Is New in This Refactor

- Updated all old paths/commands to current modules under `src/p01_heuristics/...`.
- Added both Singles (`s01_singles`) and Doubles (`s02_doubles`) workflows.
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

- `src/p01_heuristics/s01_singles/`: Singles (1v1) agents, benchmark engine, reporting.
- `src/p01_heuristics/s02_doubles/`: Doubles (2v2) agents, benchmark engine, reporting.
- `src/p02_rl_models/` and `src/p04_rl_models/`: RL training/evaluation pipelines.
- `src/p05_scripts/`: Infrastructure scripts for launching local Showdown servers.
- `data/`: Benchmark outputs, run artifacts, and generated datasets.
- `report/`: Thesis report sources.
- `docs/`: Development and workflow documentation.

## Running Benchmarks

### 1) Start local servers (recommended script)

```bash
bash src/p05_scripts/p05_launch_custom_servers.sh 4
```

This launches ports `8000-8003` and handles cleanup on exit.

Alternative:
- `bash src/p05_scripts/p05_start_fixed_servers.sh` (legacy fixed 6-server launcher).

### 2) Singles benchmark (recommended entrypoint)

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 1000 \
  --ports 4 \
  --concurrency 10
```

Key behavior:
- Runs a full matchup matrix.
- Writes outputs to `data/1_vs_1/benchmarks/unified/`.
- Resume-by-rerun: run the same command again to complete missing games only.

### 3) Doubles benchmark

```bash
uv run python src/p01_heuristics/s02_doubles/evaluation/engine/benchmark.py 10000 \
  --ports 8 \
  --battle-format gen9randomdoublesbattle
```

Outputs are organized by generation under `data/2_vs_2/benchmarks/`.

### 4) LLM agent benchmark (low-port mode)

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 20 \
  --agents pokechamp \
  --opponents v6 random \
  --ports 1 \
  --concurrency 2 \
  --player_backend ollama/qwen3:8b \
  --player_prompt_algo io
```

## Reporting and Analysis

### Singles heatmap/reporting

```bash
uv run python -m src.p01_heuristics.s01_singles.evaluation.reporting.plots.generate_heatmap \
  --data-dir data/1_vs_1/benchmarks/unified \
  --output heatmap.png
```

### Legacy/full report generators

```bash
uv run python src/p01_heuristics/s01_singles/evaluation/reporting/generate_report.py --agent pokechamp
uv run python src/p01_heuristics/s01_singles/evaluation/reporting/plots/generate_full_report.py
```

### Doubles report

```bash
uv run python src/p01_heuristics/s02_doubles/evaluation/reporting/generate_report.py
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
- `src/p01_heuristics/s01_singles/README.md`: complete singles architecture guide.
- `src/p01_heuristics/s02_doubles/s02_doubles_guide.md`: doubles usage and metrics.
- `src/p01_heuristics/s01_singles/docs/CLI_REFERENCE.md`: full CLI options.
- `docs/development_tools.md`: editor/lint/type-check/LaTeX tooling.
