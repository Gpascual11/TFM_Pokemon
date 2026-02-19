## Overview

This folder contains all our **singles (1 vs 1)** experiments. For game logic (turns, switches) and how our heuristics are designed, see **[TESTING_HEURISTICS.md](../TESTING_HEURISTICS.md)** in the parent folder.
We use `poke-env` to play the `gen9randombattle` format on a local Pokémon
Showdown server, and we log the results to CSV so we can study turn counts,
win rates, move usage, and team composition.

## What battles look like

- **Format**: `gen9randombattle` (Showdown’s random singles).
- **Teams**: Showdown randomly generates both teams each battle.
  You do **not** hardcode Pokémon or moves; they come from the random format.
- **Pokémon & attacks**:
  - The heuristics query the battle state through `poke-env`:
    - `battle.active_pokemon`, `battle.opponent_active_pokemon`
    - `battle.available_moves`, `battle.available_switches`
  - Damage is estimated with base power, attack/defense stats, STAB and type
    effectiveness (and sometimes weather/status).

So when we see moves like `earthquake`, `knockoff`, `hydropump` in the
analysis, they are **moves that the agent actually received from random teams**
and decided to use; we do not script specific Pokémon or moves.

## Main components

### `test_env.py`

Small helper to “peek” inside battles:
- prints the active Pokémon, HP, types,
- lists available moves and switches every turn.

We used this file to understand the state that `poke-env` exposes before
we started writing heuristics.

### `test_heuristic_v1.py` … `test_heuristic_v5.py`

Different generations of singles heuristics. The most important ones now:

- `test_heuristic_v4.py`
  - Uses a `GameDataManager` to access stats safely.
  - Estimates damage for each move using:
    - physical vs special split (Atk/Def vs SpA/SpD),
    - burn penalty for physical attackers,
    - STAB and type effectiveness.
  - Switches out when:
    - the Pokémon is badly poisoned (`TOX`) for several turns, or
    - its best move is weak and it is slower than the opponent.
  - For each finished battle, logs a row in a CSV with:
    - `battle_id`, `winner`, `turns`, `won`
    - `team_us`, `team_opp` (species on each side)
    - `fainted_us`, `fainted_opp`
    - `moves_used` (distinct move ids the heuristic actually used).

- `test_heuristic_v5.py`
  - A more advanced heuristic:
    - **Immediate KO check**: if a move is predicted to KO, it takes it,
      giving priority to higher-priority moves.
    - **Strategic switching** when we are in danger:
      - speed disadvantage + bad type matchup,
      - low HP or bad poison over time,
      - switches into a teammate with better resistances.
    - **Move scoring**:
      - damage × accuracy,
      - extra weight for positive priority,
      - field effects: weather (sun/rain) and terrain (electric, grassy, psychic).
  - Logs the same rich per-battle information as v4 into CSV.

All these scripts use the same pattern:

```python
await player.battle_against(opponent, n_battles=BATCH_SIZE)
```

where `player` and `opponent` are `Player` subclasses using our heuristics,
connected to the local Showdown server.

### `01_test/`

This subfolder is where we:
- fix specific heuristic versions (e.g. v4, v5),
- run long experiments,
- store the resulting CSVs and notebooks in a tidy way.

## How to run experiments

From the repo root, with your local Showdown server running:

```bash
uv run python src/testing_heuristics/1_vs_1/01_test/test_heuristic_v4.py
uv run python src/testing_heuristics/1_vs_1/01_test/test_heuristic_v5.py
```

Each script:
- plays `TOTAL_GAMES` Gen9 random battles (self-play: heuristic vs itself),
- writes a CSV under `data/` named like:
  - `tfm_expert_singles_v4_<runid>.csv`
  - `tfm_expert_singles_<runid>.csv` (for v5).

## Analysis and outputs

- `01_test/analysis_singles_heuristics.py`  
  Python module that compares **two singles CSVs**. It:
  - loads both files and tags them with `heuristic` labels,
  - computes per-heuristic stats:
    - `battles`, `mean_turns`, `sd_turns`, `ci_turns` (95% CI), `win_rate_%`,
  - explodes `moves_used` to count how often each move id is used by each
    heuristic,
  - generates plots:
    - turn distribution (histogram + KDE),
    - boxplot of turns per heuristic,
    - win-rate barplot,
    - barplot of top moves.

- `01_test/analysis_singles_heuristics.ipynb`  
  Notebook front-end for the analysis. We simply set:

  ```python
  csv_a = "../../../data/<v5_csv>.csv"
  csv_b = "../../../data/<v4_csv>.csv"
  output_dir = "../../../data/heuristics_compare_v5_vs_v4"
  label_a = "v5"
  label_b = "v4"
  ```

  and run all cells. It:
  - calls `compare_singles_heuristics(...)`,
  - displays the summary table in the notebook,
  - prints top moves,
  - saves all plots into `output_dir`.

## Summary

- The **1_vs_1 folder** holds all our singles heuristics and tools.
- Heuristics operate on **random Gen9 teams** provided by Showdown, making
  decisions based on current Pokémon, stats, types, weather and available moves.
- The scripts generate **rich CSV logs** that summarize each battle and which
  Pokémon and attacks were actually used.
- The analysis code and notebooks turn those logs into **figures and tables**
  that describe how our agents behave and how strong each heuristic is.


