# TFM Pokémon — Bot-vs-bot paradigm comparison on gen9randombattle

Master's thesis (TFM) in Data Science. Local Pokémon Showdown agents are compared in **`gen9randombattle`**: same simulator, same format, bot vs bot.

This README describes the study that ran. `THESIS_PLAN.md` is the June 2026 planning document.

---

## Research question

> In gen9randombattle, which of these families wins a bot-vs-bot round-robin: hand-written heuristics, 1-ply minimax, shallow Monte Carlo search, or imitation of human stay/switch decisions?

Rankings are bot strength under these budgets. Humans appear in a separate v14 ladder sample.

---

## Protocol

| Family | IDs | Method | Gauntlet |
|---|---|---|---|
| Heuristics | `v1`–`v14` | Hand-written move and switch rules | 10,000 games / directed matchup |
| 1-ply minimax | `v15`–`v17` | One-turn maximin after KO / endgame shortcuts | 10,000 |
| Shallow MCTS | `v18`–`v20` | Root UCB over legal actions; 100 × 5-turn **LocalSim** rollouts | **1,000** (compute budget) |
| Imitation | `v21`, `v22` | XGBoost stay/switch from 1800+ Elo human replays. v21 executes with v14. v22 ranks moves from candidate attributes (BP, STAB, type effectiveness) | 10,000 |
| PPO | separate experiment | Behavioural cloning from **v8**, then MaskablePPO vs **v12** → **34.1%** (n=10k). See [`src/p05_ppo_drl/RESULTS.md`](src/p05_ppo_drl/RESULTS.md) | — |
| Baselines | `random`, `max_power`, `abyssal`, `simple_heuristic`, `one_step`, `safe_one_step` | External / poke-env references. `one_step` and `safe_one_step` both use `SafeOneStepPlayer` | 10,000 |

**28 labels** in the gen9 matrix (22 internal + 6 baselines), both seats (`A_vs_B` and `B_vs_A`). CSVs: `data/benchmarks/all_10k/gen9randombattle/`.

Ratings on that matrix are **Bradley-Terry**, reported on an Elo-like scale.

---

## Agents

### Heuristics `v1`–`v14`

| ID | Method |
|---|---|
| **v1** | Greedy max `base power × type effectiveness × STAB` |
| **v2–v6** | Damage math (stats, weather/terrain, boosts) and light switching. Cluster is almost flat |
| **v7** | Boost-aware damage and Abyssal-style matchup switching |
| **v8** | v7 plus conservative priority KO and known-ability immunities |
| **v9** | Hazards and setup on free turns |
| **v10** | Status, low-HP sack, U-turn / Volt Switch |
| **v11** | v9 + v10, with generation-aware tweaks |
| **v12** | Terastallization and matchup-based fainted switch-in |
| **v13** | Recovery, choice-lock, phazing, conservative Tera; matchup damage from **revealed** moves |
| **v14** | Yomi / scouting / 1-ply endgame; approximate damage range (85–100% of max). Opponent HP from poke-env is often a percentage |

Most of v7–v14 subclass `BaseHeuristic1v1` directly. Treat the ladder as related bots with stacked capabilities.

### Search `v15`–`v20`

- **v15–v17:** 1-ply maximin with a heuristic leaf. Opponent replies are revealed moves (plus a generic switch). v16/v17 add more v14-style bonuses; v17 also biases toward the v14 action.
- **v18–v20:** For each legal action, UCB at the **root**; each iteration runs a 5-turn pokechamp `LocalSim` rollout and backs up that child. v20 uses a PUCT prior toward the v14 action.
- KO and endgame rules fire first; search scores the remaining turns.

### Imitation `v21`–`v22`

- Train: human `gen9randombattle` replays, Elo **1800+**, stay vs switch, `GroupShuffleSplit` by `battle_id`.
- **v21** = `HeuristicV14` plus that classifier (XGB on a minority of turns).
- **v22** = the same stay/switch head; move ranking from a second model on candidate attributes (base power, STAB, type effectiveness).
- Evaluate vs **bots**.

### PPO

**BC from V8 + PPO vs HeuristicV12, 34.1% (3405/10000).** Separate from the 28-agent table.

---

## Headline result

**Hand-written heuristics lead the gauntlet.** v12 is the bot-vs-bot ceiling. 1-ply minimax, shallow MCTS, and IL sit below it. PPO lands near the **v8 vs v12** floor (~33%).

MCTS cells use 1,000 games (± ~3 pp); other cells use 10,000 (± ~1 pp).

---

## Repository

```
TFM_Pokemon/
├── README.md                 ← this file
├── SETUP.md                  ← install Showdown, uv, poke-env
├── CONTEXT.md                ← module inventory
├── THESIS_PLAN.md            ← June 2026 plan
├── src/
│   ├── p00_core/             engine, factory, reporting, launch scripts
│   ├── p01_heuristics/       v1–v14
│   ├── p02_imitation_learning/  v21, v22
│   ├── p03_minmax/           v15–v17
│   ├── p04_mcts/             v18–v20
│   └── p05_ppo_drl/          BC + PPO (separate experiment)
├── data/benchmarks/all_10k/gen9randombattle/   28×28 CSVs
├── pokechamp/                LocalSim fork (MCTS rollouts)
└── pokemon-showdown/         local battle server
```

`report/` is the LaTeX thesis (edit separately).

---

## Setup

See [`SETUP.md`](SETUP.md).

```bash
uv python install 3.12
uv sync
cd pokemon-showdown && npm install && node build && cd ..

# Optional: full gen9 round-robin (resumes if CSVs already have enough rows)
bash src/p00_core/scripts/runs_benchmark/run_paradigm_comparison_10k.sh
```

```bash
uv run ruff format .
uv run ruff check .
uv run ty check src/
uv run python src/...   # always from repo root
```

poke-env is pinned to **0.11.x**.

---

## Docs

| File | Role |
|---|---|
| [`SETUP.md`](SETUP.md) | Install |
| [`CONTEXT.md`](CONTEXT.md) | Paths and modules |
| [`src/p00_core/reporting/heuristics_and_imitation_thesis_analysis.md`](src/p00_core/reporting/heuristics_and_imitation_thesis_analysis.md) | Results argument (gauntlet) |
| [`src/p05_ppo_drl/RESULTS.md`](src/p05_ppo_drl/RESULTS.md) | PPO claim and curriculum |
| [`src/p00_core/reporting/elo/elo_reporting.md`](src/p00_core/reporting/elo/elo_reporting.md) | Bradley-Terry Elo |

---

## Author

Gerard Pascual Fontanilles (`@Gpascual11` / `@sirp`) — Master's Thesis (TFM) in Data Science. [GitHub](https://github.com/Gpascual11/TFM_Pokemon).
