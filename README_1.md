# TFM Pokemon AI Platform

End-to-end research platform for competitive Pokemon AI, built around three complementary approaches:

1. **Heuristic AI** (expert rules and engineered decision logic)
2. **Deep Reinforcement Learning** (neural policies trained by self-play and curriculum)
3. **Hugging Face game analysis + imitation learning** (learn from high-Elo human replays)

This repository is designed to run large local benchmarks using Pokemon Showdown + `poke-env`, then turn results into research-grade metrics and plots.

---

## 1) Project Mission

The goal is not only to build one strong bot, but to compare **different AI paradigms** under the same simulator and evaluation framework:

- How far can hand-crafted battle logic go?
- How much can policy learning improve with RL?
- Can we imitate expert human behavior from replay data?
- Which paradigm is more robust across opponents and formats?

That comparison is the core value of the project.

---

## 2) High-Level Architecture

### Core stack
- **Battle engine:** Local `pokemon-showdown` server instances.
- **Client framework:** `poke-env`.
- **Python environment:** `uv` + Python 3.12.
- **Data/analysis:** Pandas, Matplotlib/Seaborn, Polars, XGBoost, SB3.

### Execution model
- Parallel battle execution over multiple local ports (`8000+`).
- Subprocess-based workers to isolate memory during long runs.
- CSV-first outputs for reproducible reporting.
- Resume-friendly benchmark behavior (re-run same command to complete missing work).

---

## 3) Repository Map

- `src/p01_heuristics/` -> rule-based agents and benchmark/reporting engine
- `src/p05_ppo_drl/` -> RL environment, training curriculum, RL evaluation
- `src/p02_imitation_learning/` -> Hugging Face replay download, EDA, feature extraction, XGBoost training
- `src/p00_core/scripts/` -> Pokemon Showdown launch scripts for local multi-port infrastructure
- `data/` -> benchmark outputs, datasets, generated artifacts
- `report/` -> thesis/report assets
- `docs/` + `SETUP.md` -> setup/dev workflows

---

## 4) Setup (New Machine)

## Requirements
- Node.js 18+
- Python 3.12
- `uv`

### 4.1 Clone and install Showdown

```bash
git clone https://github.com/smogon/pokemon-showdown.git
cd pokemon-showdown
npm install
```

### 4.2 Python environment

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv sync
```

Optional extras (RL/GPU/tooling):

```bash
uv sync --all-extras --group dev
```

### 4.3 Launch local Showdown servers

From repo root:

```bash
bash src/p00_core/scripts/launch_custom_servers.sh 4
```

This starts ports `8000-8003`.

---

## 5) Pillar A: Heuristic AI

Heuristics are deterministic/rule-based policies that score legal actions using battle math and strategic rules.

## How it works
- Agent families are exposed through a string-label factory (`v1`-`v6`, baselines, LLM labels).
- Singles and doubles have independent evaluation pipelines.
- Core benchmark engine distributes matchups across ports and merges CSV outputs.
- Latest heuristic evolution adds richer field awareness, defensive pivoting, and priority valuation.

## Main locations
- Heuristics: `src/p01_heuristics/`

## Run: Heuristics matrix benchmark

```bash
uv run python src/p00_core/engine/benchmark.py 1000 \
  --ports 4 \
  --concurrency 10
```

## Reporting

```bash
uv run python -m src.p00_core.reporting.plots.generate_heatmap \
  --data-dir data/benchmarks/all_10k \
  --output heatmap.png
```

---

## 6) Pillar B: Deep Reinforcement Learning

RL uses a neural policy (`MaskablePPO`) that learns from interaction instead of fixed rules.

## How it works
- `s01_env/vectorizer.py` converts battle states into numeric tensors.
- `s01_env/pokemon_env.py` maps policy actions to legal Showdown orders.
- Action masking prevents illegal moves/switches.
- Curriculum training progresses from easy opponents to stronger ones.

## RL training curriculum
1. `train_p1_base.py` -> basic combat competence (vs random)
2. `train_p1_5_tune.py` -> stronger tactical pressure
3. `train_p2_transfer.py` -> transfer to harder heuristic opponents
4. `train_p3_gauntlet.py` -> mixed-opponent generalization

## Run: Example RL phase

```bash
uv run python -m src.p05_ppo_drl.s02_training.train_p1_base \
  --timesteps 1000000 \
  --ports 8000 8001 8002 8003
```

## RL evaluation

```bash
uv run python src/p05_ppo_drl/s03_evaluation/run_benchmarks.py
uv run python src/p05_ppo_drl/s03_evaluation/benchmark_rl.py --games 1000 --ports 4
uv run python src/p05_ppo_drl/s03_evaluation/generate_rl_report.py
```

Outputs are stored under `src/p05_ppo_drl/s03_evaluation/results/`.

---

## 7) Pillar C: Hugging Face Replay Analysis + Imitation Learning

This track learns from human expert gameplay data.

## How it works
1. Download filtered high-Elo replays from Hugging Face datasets.
2. Run EDA to understand distributions, action behavior, and feature quality.
3. Convert battle logs into tabular supervised features.
4. Train XGBoost models to predict decisions.
5. Integrate trained models as online agents for benchmark comparisons.

## Run: Download dataset

```bash
uv run python src/p02_imitation_learning/s01_download/download_dataset.py
```

## Run: EDA

```bash
uv run python src/p02_imitation_learning/s02_eda/eda_pokemon_battles.py
```

## Run: Feature extraction + model training

```bash
uv run python src/p02_imitation_learning/s03_training/extract_ml_features.py --format gen9randombattle
uv run python src/p02_imitation_learning/s03_training/train_ml_baseline.py --format gen9randombattle
```

Produced artifacts are saved in `src/p02_imitation_learning/s03_training/models/`.

---

## 8) Unified Experiment Workflow

For reliable thesis-grade experiments:

1. Start local servers (`p00_core/scripts`).
2. Run heuristic baselines and collect benchmark CSVs.
3. Train/evaluate RL policies and export RL benchmark summaries.
4. Build imitation-learning models from Hugging Face replay data.
5. Compare all paradigms on shared metrics (win rate, turns, survivability, etc.).
6. Generate plots/tables for report sections.

---

## 9) Hardware Tuning (Your Machine)

For `AMD Ryzen 7 5700X3D` (16 threads) + `32 GB RAM`:

- Heuristic singles starting point: `--ports 4 --concurrency 10`
- Scale up gradually to `--ports 6-8` if stable.
- Doubles and long sweeps: monitor RAM and restart servers periodically.
- RL: use multiple ports for throughput, but keep an eye on simulator bottlenecks.
- LLM or heavy external backends: keep ports/concurrency low.

If instability appears:
- Reduce concurrency first.
- Then reduce number of ports.
- Run smaller chunks and merge results later.

---

## 10) Quality and Reproducibility

Use these checks before large experiment batches:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check
```

Best practices:
- Always run commands from repo root.
- Prefer `uv run python -m ...` when modules depend on package-relative imports.
- Keep benchmark commands and output directories consistent for reproducibility.

---

## 11) Practical Entry Points

If you are new to the codebase:

- Start with heuristics:
  - `src/p01_heuristics/heuristics.md`
  - `src/p01_heuristics/docs/cli_reference.md`
- Then RL:
  - `src/p05_ppo_drl/p05_ppo_drl_overview.md`
  - `src/p05_ppo_drl/s02_training/s02_training_guide.md`
- Then Hugging Face + ML baseline:
  - `src/p02_imitation_learning/README_ML_BASELINE.md`
  - `src/p02_imitation_learning/s02_eda/README_eda.md`

This path gives the fastest understanding of both architecture and execution.
