# TFM Pokémon — AI Paradigm Comparison for Competitive Battles

Research platform for comparing AI decision-making paradigms in **gen9randombattle** (Pokémon Showdown), built as a Master's thesis (TFM) in Data Science.

---

## Research Question

> *Which AI paradigm gets closest to human-level play in a complex partially-observable stochastic game, using gen9randombattle as the benchmark domain?*

The thesis is a **paradigm comparison study** — measuring how 4 distinct AI decision-making paradigms scale under identical hidden-information, stochastic environment conditions.

---

## Master AI Paradigms Summary

| Paradigm | Agents | Architecture & Decision Engine | Status |
|---|---|---|---|
| **Rule-based Heuristics** | `v1`–`v14` | 14 progressive agents: STAB, type effectiveness, entry hazards, status moves, Showdown DB set prediction, 16-step exact damage calculation, Yomi tracking, and endgame solver. | ✅ Complete |
| **Adversarial Search** | `v15`–`v17` | Multi-ply Minimax search with alpha-beta pruning, speed-aware sequential turn resolution, and hybrid heuristic state evaluations. | ✅ Complete |
| **Information Set MCTS** | `v18`–`v20` | Information Set MCTS (IS-MCTS) with opponent state sampling via `LocalSim` rollout engine. | ✅ Complete |
| **Imitation Learning** | `v21`–`v22` | XGBoost classifier trained on 1,800+ Elo human replays, predicting high-level battle decisions with hybrid heuristic fallbacks. | ✅ Complete |
| **Reinforcement Learning** | `v23+` | Deep Reinforcement Learning (PPO / MaskablePPO) framework built on custom Gymnasium battle wrappers. | ⚠️ Framework ready |

All 22 agents are evaluated head-to-head in a unified round-robin benchmark matrix (10,000 games per matchup).

---

## Detailed Paradigm Architectures

### 1. Heuristic Progression (`v1`–`v14`)
- **`v1` (Random):** Uniform random move selection baseline.
- **`v2–v4` (Greedy & Type Awareness):** STAB calculation, type effectiveness matrices, and basic KO checks.
- **`v5–v8` (Field & Status Control):** Entry hazards (Stealth Rock, Spikes), stat boosts/stat drop tracking, pivot moves (U-turn, Volt Switch), and status infliction.
- **`v9–v11` (Opponent Modeling):** Choice item lock tracking, setup counter-play, and move prediction.
- **`v12` (Tactical Enhancements):** Team preview ordering, Terastallization timing, and matchup-based switching rules.
- **`v13` (Showdown Database Integration):** Full Showdown sets DB lookups to predict unrevealed opponent movesets, EV spreads, and items.
- **`v14` (Championship Heuristic):** 16-step exact damage roll calculations, Yomi opponent switch tracking, role assignment (sweeper, wall, pivot), and exact 2v2/1v1 endgame solvers.

### 2. Adversarial Minimax Search (`v15`–`v17`)
- **`v15` (1-Ply Minimax):** Evaluates depth-1 decision trees incorporating Showdown sets DB predictions.
- **`v16` (2-Ply Minimax):** Deeper game tree exploration considering opponent counter-responses.
- **`v17` (Hybrid Minimax):** Combines `v14`'s comprehensive evaluation function with Minimax tree search and dynamic pruning.

### 3. Information Set MCTS (`v18`–`v20`)
- **`v18` (Pure MCTS):** Monte Carlo Tree Search using standard rollout policies.
- **`v19` (IS-MCTS):** Information Set MCTS designed specifically for imperfect-information games; samples probable hidden opponent teams per simulation.
- **`v20` (Hybrid IS-MCTS):** Combines IS-MCTS state rollouts with `v14` heuristic evaluation at leaf nodes.

### 4. Imitation Learning (`v21`–`v22`)
- **`v21` (Pure XGBoost IL):** Machine learning classifier trained on 1,800+ Elo high-level human replays.
- **`v22` (Hybrid XGBoost IL):** Combines XGBoost probabilities with heuristic safety fallbacks to prevent invalid or suicidal moves.

---

## Telemetry & Advanced Data Tracking

Every benchmark game records up to 70 telemetry metrics per battle row, including:

- **Battle Identifiers:** `battle_id`, `format`, `heuristic`, `opponent`, `winner`, `won`, `turns`, `timestamp`.
- **Search Telemetry:** `search_diff_us`, `search_diff_opp`, `search_switches_us`, `search_moves_us`.
- **Machine Learning Telemetry:** `xgb_switches_us`, `xgb_stays_us`, `xgb_prob_sum_us`.
- **Safety & Guard Telemetry:** `ko_guards_us`, `loop_guards_us`, `fallback_moves_us`, `error_moves_us`.
- **Battle Stats:** `hazard_sets_us`, `hazard_removals_us`, `setup_uses_us`, `ko_checks_us`, `terastallized_us`.

---

## Infrastructure & Hardware Telemetry Monitor

- **Battle Engine:** Local Node.js Pokémon Showdown instances running on dedicated ports (8000–8040).
- **Hardware Target:** AMD Ryzen 7 5700X3D (8 Cores / 16 Threads, 96MB L3 Cache), 30 GB DDR4 RAM, NVMe SSD.
- **Parallel Concurrency:** 8 parallel Showdown servers × 15–25 concurrency (~200 simultaneous battles).
- **Master Telemetry & Security Monitor (`seguretat_tfm.sh`):**
  - **Hardware Safety:** Continuous CPU thermal tracking (Panic shutdown at 92°C), RAM PageCache flush at 27.5GB.
  - **Interactive Telegram Bot:** Native 25s Long Polling listener supporting `/now`, `/session`, `/summary`, `/log`, `/pause`, `/resume`, `/pokemon`, `/meme`.
  - **Automated Morning Reports:** Daily 09:00 AM recap of overnight games completed, system health, and storage status.

---

## Repository Structure

```
TFM_Pokemon/
├── THESIS_PLAN.md              ← Full thesis roadmap and phase-by-phase guide
├── SETUP.md                    ← Installation instructions
├── pyproject.toml              ← Dependencies (poke-env pinned to 0.11.x)
├── paradigm_eval.log           ← Active master benchmark execution log
│
├── pokechamp/                  ← pokechamp repo (LLM agents + LocalSim for MCTS)
│   └── poke_env/player/local_simulation.py   ← MCTS rollout engine
├── pokemon-showdown/           ← Local battle simulator server
│
├── src/
│   ├── p00_core/               ← Unified core: engine, common utilities, reporting, online bot, and launcher scripts
│   │   ├── core/               ← Shared heuristic engine types and factory
│   │   ├── engine/             ← Benchmark runners (benchmark.py, worker.py, run_single.py)
│   │   ├── scripts/            ← Showdown server setup & launch utilities (seguretat_tfm.sh)
│   │   └── online_bot/         ← Public Showdown server deployment hook
│   ├── p01_heuristics/         ← Rule-based agents (v1–v14) & validate_heuristics.ipynb
│   ├── p02_imitation_learning/ ← Imitation learning (v21, v22) & validate_imitation.ipynb
│   ├── p03_minmax/             ← Minimax search agents (v15–v17) & validate_minmax.ipynb
│   ├── p04_mcts/               ← MCTS agent planning (v18–v20) & validate_mcts.ipynb
│   └── p05_ppo_drl/            ← Deep Reinforcement Learning pipeline
│
└── data/
    └── benchmarks/
        └── all_10k/            ← Master 10k round-robin benchmark CSVs (320+ files)
```

---

## Setup & Quick Start

See [`SETUP.md`](SETUP.md) for full installation instructions.

```bash
# 1. Install Python 3.12 & sync dependencies
uv python install 3.12
uv sync

# 2. Build local Pokemon Showdown server
cd pokemon-showdown && npm install && node build && cd ..

# 3. Launch Master Benchmark Evaluation
bash src/p00_core/scripts/runs_benchmark/run_paradigm_comparison_10k.sh

# 4. Launch Master Telemetry & Security Monitor (optional)
bash src/p00_core/scripts/seguretat_tfm.sh
```

---

## Key Technical Decisions

| Decision | Rationale |
|---|---|
| **gen9randombattle exclusively** | Controlled format — heuristics, IL pipeline, and Showdown DB all calibrated for this format. |
| **poke-env pinned to 0.11.0** | Tested across 2.5M+ games; 0.15 introduced breaking API changes. |
| **LocalSim from pokechamp fork** | Standard poke-env has no local simulator; pokechamp adds it for fast MCTS rollouts. |
| **Information Set MCTS over Minimax** | Correctly handles Pokémon's hidden information; Minimax assumes full knowledge. |
| **Bot-vs-bot as primary benchmark** | Reproducible, 10k games in ~12 min; online games are validation only. |

---

## Docs & Evaluation Notebooks

| Document / Notebook | Description & Contents |
|---|---|
| [`THESIS_PLAN.md`](THESIS_PLAN.md) | Research question, paradigm comparison, phase-by-phase implementation plan |
| [`SETUP.md`](SETUP.md) | Full installation guide (Python, Showdown, extras, poke-env version notes) |
| [`CONTEXT.md`](CONTEXT.md) | Detailed module inventory and benchmark data catalog |
| `src/p01_heuristics/validate_heuristics.ipynb` | Heuristic progression analysis (v1–v14 win-rates, HP differentials, switch rates) |
| `src/p02_imitation_learning/validate_imitation.ipynb` | XGBoost IL model evaluation, feature importance, decision rates |
| `src/p03_minmax/validate_minmax.ipynb` | Minimax search depth, alpha-beta pruning efficiency, evaluation correlation |
| `src/p04_mcts/validate_mcts.ipynb` | IS-MCTS convergence, endgame solves, and simulation rollout efficiency |

---

## Author & Developer Info

- **Author & Lead Developer:** Gerard Pascual Fontanilles (`@Gpascual11` / `@sirp`)
- **Repository:** [TFM_Pokemon (GitHub)](https://github.com/Gpascual11/TFM_Pokemon)
- **Degree:** Master's Thesis (TFM) in Data Science
