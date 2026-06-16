# Project Context (v10): Pokémon Showdown AI Research Platform

This file contains the technical state and inventory of the Pokémon Showdown AI repository. It documents what has been implemented, the file structures, the heuristics mechanics, and the data stored on disk.

---

## 1. Project Directory Structure

```
├── CONTEXT.md
├── README.md
├── SETUP.md
├── pyproject.toml
├── uv.lock
├── data/
│   ├── benchmarks/             ← Evaluation results grouped by paradigm (all_10k, imitation_learning, minmax)
│   ├── huggingface_cache/      ← Download cache for raw datasets
│   ├── imitation_learning_expert_replays/ ← Processed expert replay Parquet datasets
│   └── testing/                ← Diagnostics, logs, and legacy backups
├── docs/
│   ├── development_tools.md
│   └── pytorch-cpu-gpu-setup.md
├── pokechamp/
├── pokemon-showdown/
├── scratch/
└── src/
    ├── p00_core/               ← Unified core: engine, common utilities, reporting, online bot, and launcher scripts
    │   ├── core/               ← Shared heuristic engine types and factory
    │   ├── engine/             ← Benchmark runners (benchmark.py, worker.py, run_single.py)
    │   ├── scripts/            ← Showdown server setup & launch utilities
    │   ├── online_bot/         ← Public Showdown server deployment hook
    │   └── reporting/          ← Automated plot builders and WHR Elo calculations
    ├── p01_heuristics/         ← Rule-based agents (v1–v14)
    │   ├── agents/
    │   │   ├── baselines/
    │   │   └── internal/
    │   └── docs/
    ├── p02_imitation_learning/ ← Imitation learning: download → extract → train → agent
    │   ├── s01_download/
    │   ├── s02_eda/
    │   ├── s03_training/
    │   └── s04_agent/
    ├── p03_minmax/             ← Minimax search agents (v7, v15)
    │   └── agents/
    │       └── internal/
    ├── p04_mcts/               ← MCTS agent planning
    └── p05_ppo_drl/            ← Deep Reinforcement Learning pipeline
        ├── s01_env/
        ├── s02_training/
        └── s03_evaluation/
```

---

## 2. Inventory of Current Modules & Components

### A. Heuristics Framework (`src/p01_heuristics/`)
* **Agents (`agents/internal/`):** Implements rule-based agents `v1` to `v14`.
  * **Reference Doc (`agents/internal/agents_reference.md`):** Comprehensive guide on strategy genealogy, implementation key logic, and comparison of bot-vs-bot vs. human-vs-bot dynamics.
  * **`v1` to `v6`:** Greedy, damage-focused heuristics.
  * **`v7` to `v11`:** Strategic rule layers incorporating entry hazard setup/removal, stat-boosting moves, item/ability/screen modifiers, status moves, Volt Switch/U-turn pivots, and low-HP sack behavior.
  * **`v12`:** Hybrid agent adding matchup-based Team Preview sorting, matchup-based fainted switch-in selection, and Generation 9 Terastallization evaluations.
  * **`v13`:** Predictive agent adding lazy-loaded Showdown random battle sets database lookups (Gens 1–9), move- and stat-aware matchup damage simulation, choice-lock detection, setup sweeper phazing, smart HP recovery below 60%, and conservative Tera usage.
  * **`v14`:** Championship agent adding team preview role classification, double-switch prediction/pivots, defensive bait-and-switch Tera, boots detection, status absorption switches, PP tracking, win-condition preservation, Yomi Layer 2 opponent tendency tracking, turns 1-3 scouting priorities, 16-step exact damage calculation, and a 1-ply endgame solver.
* **Baselines (`agents/baselines/`):** Wrappers for `random`, `max_power`, `safe_one_step_player.py`, and `true_simple_heuristic.py`.

### B. Shared Core Utilities (`src/p00_core/`)
* **Core Utilities (`core/`):**
  * `base.py`: Declares `BaseHeuristic1v1` class and tracks in-battle strategic counters.
  * `common.py`: Math helpers for type effectiveness, raw damage calculations, and speed brackets.
  * `factory.py`: Instantiates agents from string labels.
* **Evaluation Engine (`engine/`):**
  * `benchmark.py` & `worker.py`: Parallelized, multi-port master-worker framework with resume-by-rerun logic.
  * `run_single.py` & `serial_benchmark.py`: Local diagnostics and sequential test suites.
* **Reporting (`reporting/`):** Scripts converting raw CSV logs to heatmap plots and Bradley-Terry Elo lists.
* **Online Bot Hook (`online_bot/`):** Deployment wrapper to run heuristics on the public Showdown Smogon server.
* **Shell Utilities (`scripts/`):**
  * `launch_custom_servers.sh`: Spawns a user-defined number of local Showdown Node.js instances sequentially on ports `8000+` and handles cleanups.
  * `start_fixed_servers.sh`: Legacy launcher for 6 fixed server ports.

### C. Adversarial Search Framework (`src/p03_minmax/`)
* **Agent (`agents/internal/v15_minimax.py`):** Implements 1-ply Minimax search. Evaluates the immediate game tree (1 turn ahead) by simulating candidate actions against predicted opponent actions and selecting the maximin option.
* **Agent (`agents/internal/v7_minimax.py`):** Legacy 1-ply Minimax agent.

### D. Machine Learning Imitation Pipeline (`src/p02_imitation_learning/`)
* **`s01_download/`:** Hugging Face expert replay downloader.
* **`s02_eda/`:** Behavioral analysis and graphing scripts.
* **`s03_training/`:** Tabular features extractor and training scripts for XGBoost models.
* **`s04_agent/`:** Deploys trained XGBoost models as live players (`MLBaselineAgent`, `MLAdvancedAgent`).

### E. Reinforcement Learning Pipeline (`src/p05_ppo_drl/`)
* **Environment (`s01_env/`):**
  * `vectorizer.py`: Flattens a Showdown `Battle` state into a numeric tensor.
  * `pokemon_env.py`: Gymnasium interface with action masking (indexes 0-3 for moves, 4-9 for switches).
* **Training Scripts (`s02_training/`):** Curriculum scripts (`train_p1_base`, `train_p1_5_tune`, `train_p2_transfer`, `train_p3_gauntlet`).
* **Evaluation (`s03_evaluation/`):** Verification and comparative graphing suite for trained RL checkpoints.

---

## 3. Data & Benchmark Assets (`data/`)

### A. 1v1 Singles Benchmark Matrix
* **Location:** `data/benchmarks/all_10k/`
* **Details:** Matchup CSVs (e.g. `v15_vs_abyssal.csv`, `v12_vs_abyssal.csv`) containing completed games for each matchup.

---

## 4. Platform Setup and Configuration
* **Centralized Python Tooling:** Virtual environment managed by `uv` utilizing Python 3.12. Code formatting, checking, and type-checks are driven by Ruff (`ruff format .`, `ruff check .`) and Ty (`ty check`).
* **Offline Local Server Architecture:** Local Smogon `pokemon-showdown` instance configured to disable login servers (`loginserver = null`) and bound to offline multi-port runs (ports 8000+).
