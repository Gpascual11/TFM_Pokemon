## Overview

This folder contains all our **doubles (2 vs 2)** experiments. For a detailed explanation of **game logic (turns, switches, targets)** and **how our heuristics work**, see **[TESTING_HEURISTICS.md](../TESTING_HEURISTICS.md)** in the parent folder.
We use `poke-env` to play the `gen9randomdoublesbattle` format on a local
Pokémon Showdown server, and we log results to compare different heuristics:
how often they win, how fast they finish games, and which moves and Pokémon
they like to use.

## What battles look like

- **Format**: `gen9randomdoublesbattle` (Showdown’s random doubles).
- **Teams**: both sides receive random teams from Showdown at the start of
  each battle. You do **not** predefine specific Pokémon or moves.
- **Pokémon & attacks** are accessed via `poke-env`:
  - `battle.active_pokemon` (two active allies),
  - `battle.opponent_active_pokemon` (two active foes),
  - `battle.available_moves[slot]` and `battle.available_switches[slot]` per slot.

Our heuristics use those objects to:
- approximate expected damage,
- reason about targets (which opponent to hit),
- consider spread moves, Protect, Fake Out, Tailwind, etc.,
- choose between attacking and switching.

## Main components

### `testing_heuristic_v1.py`

The **v1 doubles heuristic** (baseline):

- For each of our two active slots:
  - considers all available moves and both enemy targets,
  - estimates damage using stats, STAB and type effectiveness,
  - gives a massive bonus if a move is predicted to KO its target,
  - picks the `(move, target)` combination with highest score.
- If `battle.force_switch` is active:
  - selects defensive switches using type match-ups:
    - `_get_best_switch_from_list` looks for the teammate with the smallest
      worst weakness to opponents’ types,
    - avoids switching the same bench Pokémon into both positions.
- Logs per-battle data to `data/tfm_doubles_v1_<runid>.csv` with:
  - `battle_id`, `winner`, `turns`, `won`
  - `team_us`, `team_opp`
  - `fainted_us`, `fainted_opp`
  - `moves_used` (distinct move ids v1 actually used).

### `testing_heuristic_v2.py`

The **v2 doubles heuristic** (joint-action reasoning):

- Uses `_choose_joint_best_actions`:
  - builds a list of candidate actions for each slot (attacks, Protect, switches),
  - scores **pairs of actions** `(slot1_action, slot2_action)` instead of
    picking each slot independently.
- The joint score:
  - rewards:
    - double KOs,
    - split KOs (each slot KOing a different target),
    - meaningful spread-damage pressure on both foes,
  - penalizes:
    - redundant double-targeting when one hit is enough to KO,
  - prefers:
    - hitting opponents that threaten us the most by type.
- Uses Protect and switching more carefully when we are weak to the current
  board position.
- Logs per-battle data to `data/tfm_doubles_v2_<runid>.csv` with the same
  fields as v1:
  - `battle_id`, `winner`, `turns`, `won`
  - `team_us`, `team_opp`
  - `fainted_us`, `fainted_opp`
  - `moves_used` (distinct move ids v2 actually used).

### `testing_heuristic_v3_v1_vs_v2.py`

This script pits **v1 vs v2 directly**:

- half the battles with v1 as `player` and v2 as `opponent`,
- half the battles with v2 as `player` and v1 as `opponent`.

It produces a CSV of head-to-head outcomes:
- `winner`
- `player_heuristic`, `opponent_heuristic`
- `turns`

This tells us **which heuristic is stronger in cross-play**, not just
when playing against itself.

### `collect_rl_data_doubles.py` — RL-ready data from both heuristics

This script runs **v1 vs v2** and logs **per-turn state, actions, and damage info**
so an RL agent can learn from expert play (e.g. “this damage is useful against
this type”, type multipliers, HP state, battle outcome).

- **Output CSVs** (in `data/`):
  - **`rl_turns_<runid>.csv`**: one row per turn per slot:
    - **State**: `turn`, `remaining_us`, `remaining_opp`, `weather`, `terrain`,
      `our_species_0/1`, `our_types_0/1`, `our_hp_frac_0/1`,
      `opp_species_0/1`, `opp_types_0/1`, `opp_hp_frac_0/1`.
    - **Action**: `heuristic` (v1|v2), `slot`, `action_type` (move|switch),
      `move_id`, `move_target`, `switch_species`.
    - **Damage/type**: `estimated_damage`, `type_multiplier` (e.g. 2.0 = super
      effective) — so the machine can learn type effectiveness from data.
    - **Outcome**: `battle_winner` (us|opp|draw), `total_turns`.
  - **`rl_battles_<runid>.csv`**: one row per battle: `battle_id`, `winner`,
    `turns`, `team_us`, `team_opp`.

- **How to use for RL**:
  - Use state columns as **observation features** (or to align with
    `TFMDoublesEnv.embed_battle`).
  - Use `move_id` / `move_target` / `action_type` as **action labels** for
    imitation or behavior cloning.
  - Use `estimated_damage` and `type_multiplier` as **auxiliary targets** or
    reward shaping (e.g. prefer moves with higher expected damage vs current
    target).
  - Use `battle_winner` and `total_turns` for **outcome-based rewards** or
    filtering (e.g. only learn from won battles).

Run (with server up):

```bash
uv run python src/testing_heuristics/2_vs_2/collect_rl_data_doubles.py
```

Tune `TOTAL_GAMES` and `BATCH_SIZE` in the script for more/faster data.

**Analysis:** Use the notebook `analysis_rl_data_doubles.ipynb` to explore the
output CSVs: battle outcomes, turn and state distributions, top moves, damage and
type-multiplier stats, and a short heuristic comparison (v1 vs v2). Set
`turns_csv` and `battles_csv` to your `rl_turns_*.csv` and `rl_battles_*.csv`, then
run all cells; plots are saved under `output_dir`.

## How to run doubles experiments

From the repo root, with the Showdown server running:

```bash
# v1 self-play
uv run python src/testing_heuristics/2_vs_2/testing_heuristic_v1.py

# v2 self-play
uv run python src/testing_heuristics/2_vs_2/testing_heuristic_v2.py

# (optional) v1 vs v2 head-to-head
uv run python src/testing_heuristics/2_vs_2/testing_heuristic_v3_v1_vs_v2.py
```

We then get CSVs in `data/` like:
- `tfm_doubles_v1_<runid>.csv`
- `tfm_doubles_v2_<runid>.csv`
- `tfm_doubles_v1_vs_v2_<runid>.csv` (for v1 vs v2).

## Analysis and outputs

### `analysis_double.py` (or `backup/analysis_double.py`)

Older helper for basic **singles vs doubles** comparison using only
`turns` and `won` from CSVs.

### `analysis_doubles_heuristics.py`

Newer module dedicated to **v1 vs v2 doubles heuristic comparison**.

  Main entry point:

  ```python
  from analysis_doubles_heuristics import compare_doubles_heuristics

  summary, moves_counts, species_counts = compare_doubles_heuristics(
      csv_a=\"../../data/tfm_doubles_v1_1234.csv\",
      csv_b=\"../../data/tfm_doubles_v2_5678.csv\",
      label_a=\"v1\",
      label_b=\"v2\",
      output_dir=\"../../data/heuristics_doubles_v1_vs_v2\",
  )
  ```

  It produces:
  - `summary` with:
    - `heuristic`, `battles`, `mean_turns`, `sd_turns`,
      `ci_turns` (95% CI), `win_rate_%`.
  - `moves_counts`:
    - long-form counts of moves: (`heuristic`, `move_id`, `count`).
  - `species_counts`:
    - long-form counts of Pokémon on your side: (`heuristic`, `species`, `count`).

  And saves plots into `output_dir`:
  - `turn_distribution_doubles.png`
  - `turn_boxplot_doubles.png`
  - `win_rates_doubles.png`
  - `top_moves_doubles.png`
  - `top_species_doubles.png`

### `analysis_doubles_heuristics.ipynb`

Notebook front-end for doubles comparison. We set:

  ```python
  csv_a = \"../../data/tfm_doubles_v1_1234.csv\"
  csv_b = \"../../data/tfm_doubles_v2_5678.csv\"
  output_dir = \"../../data/heuristics_doubles_v1_vs_v2\"
  label_a = \"v1\"
  label_b = \"v2\"
  ```

  and run all cells to:
  - display the summary stats table for v1 vs v2,
  - show top-20 moves and top-20 Pokémon,
  - automatically save all comparison images into `output_dir`.

## How this works “inside the game”

- We are always playing **true Showdown random doubles**:
  - teams, Pokémon, items and moves come from the format, not from hardcoded
    lists.
  - every turn, the agent sees:
    - which two allies and two foes are on the field,
    - their HP%, types, statuses, known moves, etc.,
    - which moves and switches are currently legal (including targets).
- The heuristics **approximate game concepts**:
  - **Damage** via a simplified damage formula and type multipliers.
  - **Speed / danger** via status, weaknesses and HP thresholds.
  - **Coordination** (v2) via joint scoring of both actions, KO synergy,
    focus penalties, and spread-move value.
- The CSV logs and analysis scripts then let us answer questions like:
  - “How much stronger is v2 vs v1?” (win rates, head-to-head results),
  - “Which moves do our heuristics lean on most?” (top moves),
  - “Which Pokémon tend to appear on our side and how often?” (top species),
  - “Do they finish games faster or slower?” (turn distributions).

## Summary

- The **2_vs_2 folder** implements and evaluates our doubles heuristics
  in a realistic `gen9randomdoublesbattle` environment.
- v1 and v2 differ in how they select moves and coordinate both slots.
- Scripts generate **rich per-battle logs** capturing which Pokémon and
  attacks were actually used in those random games.
- The analysis module and notebook convert those logs into **figures and
  summary tables** that describe and compare the heuristics.


