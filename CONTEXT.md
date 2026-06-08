# Project Context (v10): Pokémon Showdown AI Research Platform

This file contains the technical state and inventory of the Pokémon Showdown AI repository. It documents what has been implemented, the file structures, the heuristics mechanics, and the data stored on disk.

---

## 1. Project Directory Structure

```
├── CONTEXT.md
├── README.md
├── README_2.md
├── SETUP.md
├── pyproject.toml
├── uv.lock
├── data/
│   ├── 1_vs_1/
│   │   ├── benchmarks_all_10k/
│   │   │   ├── gen1randombattle/ ... gen9randombattle/
│   │   │   └── gen9randombattle/v13_testing/
│   │   ├── benchmarks_testing/
│   │   └── logs/
│   ├── 2_vs_2/
│   └── models/
├── docs/
│   ├── development_tools.md
│   └── pytorch-cpu-gpu-setup.md
├── pokechamp/
├── pokemon-showdown/
├── scratch/
└── src/
    ├── p01_heuristics/
    │   ├── s01_singles/
    │   │   ├── agents/
    │   │   │   ├── baselines/
    │   │   │   │   ├── safe_one_step_player.py
    │   │   │   │   └── true_simple_heuristic.py
    │   │   │   ├── internal/
    │   │   │   │   ├── v1.py ... v14.py
    │   │   │   │   ├── s01_agents_reference.md
    │   │   │   │   ├── v12_explanation.md
    │   │   │   │   └── v13_explanation.md
    │   │   │   └── llm/
    │   │   ├── core/
    │   │   │   ├── base.py
    │   │   │   ├── common.py
    │   │   │   └── factory.py
    │   │   └── evaluation/
    │   │       ├── engine/
    │   │       │   ├── benchmark.py
    │   │       │   └── worker.py
    │   │       ├── online_bot/
    │   │       │   └── run_online_bot.py
    │   │       └── reporting/
    │   └── s02_doubles/
    │       ├── agents/
    │       │   ├── baselines/
    │       │   └── v1.py ... v5.py
    │       ├── core/
    │       │   └── battle_manager.py
    │       └── evaluation/
    │           └── engine/
    │               └── benchmark.py
    ├── p02_search/
    │   └── s01_singles/
    │       └── agents/
    │           └── internal/
    │               └── v7_minimax.py
    ├── p03_ml_baseline/
    │   ├── s01_download/
    │   ├── s02_eda/
    │   ├── s03_training/
    │   └── s04_agent/
    │       ├── ml_advanced.py
    │       └── ml_baseline.py
    ├── p04_rl_models/
    │   ├── s01_env/
    │   │   ├── pokemon_env.py
    │   │   └── vectorizer.py
    │   ├── s02_training/
    │   │   ├── train_p1_base.py
    │   │   ├── train_p1_5_tune.py
    │   │   ├── train_p2_transfer.py
    │   │   └── train_p3_gauntlet.py
    │   └── s03_evaluation/
    │       ├── benchmark_rl.py
    │       ├── generate_rl_report.py
    │       └── run_benchmarks.py
    └── p05_scripts/
        ├── p05_launch_custom_servers.sh
        ├── p05_start_fixed_servers.sh
        └── seguretat_tfm.sh
```

---

## 2. Inventory of Current Modules & Components

### A. Singles Heuristic Framework (`src/p01_heuristics/s01_singles/`)
* **Agents (`agents/internal/`):** Implements rule-based agents `v1` to `v14`.
  * **Reference Doc (`s01_agents_reference.md`):** Comprehensive guide on strategy genealogy, implementation key logic, and comparison of bot-vs-bot (`v13`) vs. human-vs-bot (`v14`) dynamics.
  * **`v1` to `v6`:** Greedy, damage-focused heuristics.
  * **`v7` to `v11`:** Strategic rule layers incorporating entry hazard setup/removal, stat-boosting moves, item/ability/screen modifiers, status moves, Volt Switch/U-turn pivots, and low-HP sack behavior.
  * **`v12`:** Hybrid agent adding matchup-based Team Preview sorting, matchup-based fainted switch-in selection, and Generation 9 Terastallization evaluations.
  * **`v13`:** Predictive agent adding lazy-loaded Showdown random battle sets database lookups (Gens 1–9), move- and stat-aware matchup damage simulation, choice-lock detection, setup sweeper phazing, smart HP recovery below 60%, and conservative Tera usage.
  * **`v14`:** Championship agent adding team preview role classification, double-switch prediction/pivots, defensive bait-and-switch Tera, boots detection, status absorption switches, PP tracking, win-condition preservation, Yomi Layer 2 opponent tendency tracking, turns 1-3 scouting priorities, 16-step exact damage calculation, and a 1-ply endgame solver.
* **Baselines (`agents/baselines/`):** Wrappers for `random`, `max_power`, `safe_one_step_player.py`, and `true_simple_heuristic.py`.
* **Core Utilities (`core/`):**
  * `base.py`: Declares `BaseHeuristic1v1` class and tracks in-battle strategic counters.
  * `common.py`: Math helpers for type effectiveness, raw damage calculations, and speed brackets.
  * `factory.py`: Instantiates agents from string labels.
* **Evaluation Engine (`evaluation/`):**
  * `benchmark.py` & `worker.py`: Parallelized, multi-port master-worker framework with resume-by-rerun logic.
  * `reporting/`: Scripts converting raw CSV logs to heatmap plots and Elo lists.
  * `online_bot/run_online_bot.py`: Hook to deploy heuristic agents on the public Smogon server.

### B. Doubles Heuristic Framework (`src/p01_heuristics/s02_doubles/`)
* **Agents (`agents/`):** Implements rule-based agents `v1` to `v5`. Uses a score-then-combine action coordination architecture.
* **Core (`core/`):** Orchestrates local showdown interactions via `battle_manager.py`.
* **Evaluation (`evaluation/`):** Independent parallel matrix benchmarking suite.

### C. Adversarial Search Framework (`src/p02_search/`)
* **Agent (`s01_singles/agents/internal/v7_minimax.py`):** Implements 1-ply Minimax. Evaluates the immediate game tree (1 turn ahead) by simulating all valid model actions against predicted opponent actions and selecting the maximin option.

### D. Machine Learning Imitation Pipeline (`src/p03_ml_baseline/`)
* **`s01_download/`:** Hugging Face expert replay downloader.
* **`s02_eda/`:** Behavioral analysis and graphing scripts.
* **`s03_training/`:** Tabular features extractor and training scripts for XGBoost models.
* **`s04_agent/`:** Deploys trained XGBoost models as live players (`MLBaselineAgent`, `MLAdvancedAgent`).

### E. Reinforcement Learning Pipeline (`src/p04_rl_models/`)
* **Environment (`s01_env/`):**
  * `vectorizer.py`: Flattens a Showdown `Battle` state into a numeric tensor.
  * `pokemon_env.py`: Gymnasium interface with action masking (indexes 0-3 for moves, 4-9 for switches).
* **Training Scripts (`s02_training/`):** Curriculum scripts (`train_p1_base`, `train_p1_5_tune`, `train_p2_transfer`, `train_p3_gauntlet`).
* **Evaluation (`s03_evaluation/`):** Verification and comparative graphing suite for trained RL checkpoints.

### F. Shell Utilities (`src/p05_scripts/`)
* **`p05_launch_custom_servers.sh`:** Spawns a user-defined number of local Showdown Node.js instances sequentially on ports `8000+` and handles cleanups.
* **`p05_start_fixed_servers.sh`:** Legacy launcher for 6 fixed server ports.

---

## 3. Data & Benchmark Assets (`data/`)

### A. 1v1 Singles 10k Benchmark Matrix
* **Location:** `data/1_vs_1/benchmarks_all_10k/`
* **Format Folders:** Subfolders `gen1randombattle` through `gen9randombattle`.
* **Details:** Matchup CSVs (e.g. `v12_vs_abyssal.csv`, `simple_heuristic_vs_max_power.csv`) containing 10,000 completed games for each matchup.
* **V13 Validation:** Matchup logs for `v13` vs all opponents in Gen 9 reside under `data/1_vs_1/benchmarks_all_10k/gen9randombattle/v13_testing/`.

### B. 2v2 Doubles Benchmark Data
* **Location:** `data/2_vs_2/benchmarks/`
* **Details:** Saved CSV results generated by running multi-port doubles benchmarks.

---

## 4. Platform Setup and Configuration
* **Centralized Python Tooling:** Virtual environment managed by `uv` utilizing Python 3.12. Code formatting, checking, and type-checks are driven by Ruff (`ruff format .`, `ruff check .`) and Ty (`ty check`).
* **Offline Local Server Architecture:** Local Smogon `pokemon-showdown` instance configured to disable login servers (`loginserver = null`) and bound to offline multi-port runs (ports 8000+).
