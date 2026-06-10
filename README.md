# TFM Pokémon — AI Paradigm Comparison for Competitive Battles

Research platform for comparing AI decision-making paradigms in **gen9randombattle** (Pokémon Showdown), built as a Master's thesis (TFM) in Data Science.

---

## Research Question

> *Which AI paradigm gets closest to human-level play in a complex partially-observable stochastic game, using gen9randombattle as the benchmark domain?*

The thesis is a **paradigm comparison study** — not an attempt to build the best bot in the world, but to rigorously measure how different AI approaches scale to a game with hidden information, stochastic outcomes, and a large action space.

---

## Five AI Paradigms

| Paradigm | Implementation | Status |
|---|---|---|
| **Rule-based heuristics** | v1–v14 (14 agents, progressively stronger) | ✅ Done |
| **Adversarial search** | v15 Minimax + v16 Information Set MCTS | 🔨 Building |
| **Imitation learning** | XGBoost trained on 1800+ Elo human replays | ⚠️ Fix needed (wrong format) |
| **Reinforcement learning** | PPO (MaskablePPO, curriculum training) | ⚠️ Bug to fix |
| **LLM reasoning** | pokellmon (chain-of-thought, via pokechamp) | 📋 Planned |

All paradigms are evaluated head-to-head in 10,000-game benchmarks under a unified framework.

---

## Heuristic Agent Progression (v1–v14)

| Agent | Strategy added |
|---|---|
| `v1` | Random baseline |
| `v2–v4` | Greedy damage selection, type effectiveness, STAB |
| `v5–v8` | Entry hazards, stat boosts, status moves, pivot moves |
| `v9–v11` | Opponent modeling, choice lock detection, setup counter-play |
| `v12` | Team preview sorting, Terastallization, matchup-based switches |
| `v13` | Showdown sets DB, exact damage estimation, smart recovery |
| `v14` | Team roles, Yomi opponent tracking, exact 16-step damage rolls, endgame solver |

**Online validation (v14):** 40.8% win rate across 98 games vs real humans on the Showdown ladder (~1151 Elo). A naive bot achieves ~5%.

---

## Adversarial Search

### v15 — Minimax
1-ply game tree using v14's evaluator. Improvements over a naive minimax:
- Uses the Showdown sets database to predict unrevealed opponent moves
- Speed-aware damage resolution (sequential, not simultaneous)
- Switches included as minimax options

### v16 — Information Set MCTS
Monte Carlo Tree Search with opponent state sampling. Why it fits Pokémon better than minimax:
- Pokémon is a **partially-observable** game — opponent's full team and moves are hidden
- MCTS samples probable opponent configurations from the Showdown DB per simulation
- Uses `LocalSim` (from the pokechamp repo) as the rollout engine — no server needed
- This is the correct algorithm class for imperfect-information games

---

## Infrastructure

- **Battle server:** Local Pokemon Showdown instances (Node.js)
- **Client library:** poke-env `0.11.0` (pinned — see `SETUP.md`)
- **Concurrency:** 8 servers × 25 concurrent games = 200 simultaneous battles
- **Throughput:** ~2.5 million games in 50 hours on this machine
- **Hardware:** Ryzen 7 5700X3D · 32 GB RAM · RTX 2080 (CUDA 12.8)
- **Python:** 3.12 managed via `uv`

---

## Repository Structure

```
TFM_Pokemon/
├── THESIS_PLAN.md              ← Full thesis roadmap and phase-by-phase guide
├── SETUP.md                    ← Installation instructions
├── pyproject.toml              ← Dependencies (poke-env pinned to 0.11.x)
│
├── pokechamp/                  ← pokechamp repo (LLM agents + LocalSim for MCTS)
│   └── poke_env/player/local_simulation.py   ← MCTS rollout engine
├── pokemon-showdown/           ← Local battle simulator server
│
├── src/
│   ├── p01_heuristics/
│   │   ├── s01_singles/        ← v1–v14 agents + benchmark engine + online bot
│   │   └── s02_doubles/        ← v1–v5 doubles agents (exploratory)
│   ├── p02_search/
│   │   └── s01_singles/        ← v15 minimax (building), v16 MCTS (planned)
│   ├── p03_ml_baseline/        ← Imitation learning: download → extract → train → agent
│   ├── p04_rl_models/          ← PPO: environment, curriculum training, evaluation
│   └── p05_scripts/            ← Showdown server launch scripts
│
└── data/
    ├── 1_vs_1/
    │   ├── benchmarks_all_10k/gen9randombattle/   ← 326 benchmark CSVs (v1–v12)
    │   └── logs_v14/battle_history.csv            ← Online bot results
    └── models/                 ← PPO checkpoints
```

---

## Setup

See [`SETUP.md`](SETUP.md) for full installation instructions.

**Quick start (heuristics + benchmarks only — no GPU required):**
```bash
uv python install 3.12
uv sync                          # base deps: poke-env, xgboost, pandas, etc.
cd pokemon-showdown && npm install && node build && cd ..
bash src/p05_scripts/p05_launch_custom_servers.sh 8
```

**For RL training (GPU):**
```bash
uv sync --extra gpu --index https://download.pytorch.org/whl/cu128
```

**For pokechamp LLM agents:**
```bash
uv sync --extra pokechamp
```

---

## Key Technical Decisions

| Decision | Rationale |
|---|---|
| **gen9randombattle exclusively** | Controlled format — heuristics, IL pipeline, and Showdown DB all calibrated for this format |
| **poke-env pinned to 0.11.0** | 2.5M+ games on this version; 0.15 has breaking API changes |
| **LocalSim from pokechamp fork** | Standard poke-env has no local simulator; pokechamp adds it for MCTS rollouts |
| **Information Set MCTS over minimax** | Correctly handles Pokémon's hidden information; minimax assumes full knowledge |
| **Bot-vs-bot as primary benchmark** | Reproducible, 10k games in ~12 min; online games are validation only |
| **No VGC / no gen9ou** | Different action space / requires team-building — out of thesis scope |

---

## Benchmark Results (gen9randombattle, 10k games each)

All results in `data/1_vs_1/benchmarks_all_10k/gen9randombattle/` (326 CSV files).

The complete paradigm comparison matrix (v15, v16 MCTS, XGBoost IL, PPO) is pending — see [`THESIS_PLAN.md`](THESIS_PLAN.md) for the full roadmap.

---

## Developer Tools

```bash
uv run ruff format .    # auto-format
uv run ruff check .     # lint
uv run ty check src/    # type check

# Always run from project root with uv:
uv run python src/...
```

---

## Docs

| File | Contents |
|---|---|
| [`THESIS_PLAN.md`](THESIS_PLAN.md) | Research question, paradigm comparison, phase-by-phase implementation plan |
| [`SETUP.md`](SETUP.md) | Full installation guide (Python, Showdown, extras, poke-env version notes) |
| [`CONTEXT.md`](CONTEXT.md) | Detailed module inventory and benchmark data catalog |
| `src/p01_heuristics/s01_singles/agents/internal/s01_agents_reference.md` | Strategy genealogy v1–v14 |
| `src/p04_rl_models/s02_training/p02_s02_training_guide.md` | PPO curriculum guide |
| `src/p03_ml_baseline/README_ML_BASELINE.md` | Imitation learning pipeline |
