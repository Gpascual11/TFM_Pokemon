# Project Context: Pokémon Showdown AI Research Platform

Inventory of modules. For the scientific description of the study, use [`README.md`](README.md).

---

## 1. Directory structure

```
├── CONTEXT.md
├── README.md
├── SETUP.md
├── THESIS_PLAN.md            ← June 2026 plan
├── pyproject.toml
├── uv.lock
├── data/
│   ├── benchmarks/           ← all_10k (gen9 28-agent matrix); other gens use smaller agent sets
│   ├── huggingface_cache/
│   ├── imitation_learning_expert_replays/
│   └── testing/
├── docs/
├── pokechamp/                ← LocalSim + Abyssal / LLM helpers
├── pokemon-showdown/
└── src/
    ├── p00_core/
    ├── p01_heuristics/       v1–v14
    ├── p02_imitation_learning/  v21, v22
    ├── p03_minmax/           v15–v17 (1-ply maximin)
    ├── p04_mcts/             v18–v20 (root UCB + LocalSim)
    └── p05_ppo_drl/          BC + PPO (separate experiment)
```

---

## 2. Modules

### A. Heuristics (`src/p01_heuristics/`)

`v1`–`v14` under `agents/internal/`. Labels vs code: see README (v1 is greedy STAB damage; hazards and setup from v9; v12 is Tera and fainted switch-in; v13/v14 score matchups from revealed moves).

Baselines: `random`, `max_power`, `abyssal`, `simple_heuristic`, `SafeOneStepPlayer` for both `one_step` and `safe_one_step`.

### B. Core (`src/p00_core/`)

- `core/`: `BaseHeuristic1v1`, `common.py`, `factory.py`
- `engine/`: `benchmark.py`, `worker.py` (resume-by-row-count)
- `reporting/`: plots + **Bradley-Terry** Elo (`elo_ranking.py`)
- `online_bot/`: public Showdown hook
- `scripts/`: Showdown launchers, `run_paradigm_comparison_10k.sh` (MCTS n=1000)

The worker injects `TFM_Pokemon/pokechamp` onto `sys.path`. Gauntlet runs go through the worker.

### C. Minimax (`src/p03_minmax/`)

`v15`, `v16`, `v17` inherit `HeuristicV14`. **1-ply** exhaustive maximin.

### D. MCTS (`src/p04_mcts/`)

`v18`–`v20`: UCB over **root** children, 100 simulations, 5-turn LocalSim rollout. Determinization copies revealed moves.

### E. Imitation (`src/p02_imitation_learning/`)

Download 1800+ Elo `gen9randombattle` replays → features → XGBoost stay/switch. Live agents: `v21_xgboost.py` (hybrid on v14), `v22_pure_il.py` (macro XGB + attribute-based move model).

### F. PPO (`src/p05_ppo_drl/`)

**BC from V8 + PPO** vs HeuristicV12, n=10k, **34.1%**. Observation is 328-d on the claim zip; the live vectorizer is 346-d. Stubs: `train_p2_transfer`, `train_p3_gauntlet`.

---

## 3. Benchmark data

- **Gen9 matrix:** `data/benchmarks/all_10k/gen9randombattle/` — 28×28 directed CSVs. Non-MCTS cells 10,000 rows; any matchup involving v18/v19/v20 is 1,000.
- Other generations under `all_10k/` use **smaller agent sets**.

---

## 4. Tooling

Python 3.12 via `uv`. `ruff` + `ty`. Local Showdown with `loginserver = null`, ports 8000+.
