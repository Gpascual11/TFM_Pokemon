# 2-vs-2 Heuristic Simulations

We built a framework for testing heuristic-based Pokémon battling agents in
Generation 9 Random Doubles Battle. The system mirrors the 1v1 framework
with all the same infrastructure — multi-process execution, flexible opponents,
CSV output — adapted for the doubles format.

## Features

- **Three heuristic versions** (`v1`, `v2`, `v6`) with increasing sophistication
  — from simple max-damage to field-aware strategies.
- **Correct doubles targeting** — we use `battle.valid_orders` (poke-env's
  pre-validated per-slot orders) so move targets are always legal and spread
  moves, ally-targeting moves, and opponent-targeting moves are handled
  automatically.
- **Flexible opponent selection** — fight against `RandomPlayer`,
  `MaxBasePowerPlayer`, `SimpleHeuristicsPlayer`, or any other heuristic version.
- **Multi-process execution** — one child process per Showdown server with
  automatic work-splitting and result merging.
- **Rich CSV output** — battle outcomes, team composition, fainted/remaining
  counts, HP totals.

## Setup

### Prerequisites

- Python 3.10+
- [poke-env](https://github.com/hsahovic/poke-env) (installed via `uv` or `pip`)
- A local [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) server

### Starting Showdown Servers

```bash
node pokemon-showdown start --port 8000 --no-security
node pokemon-showdown start --port 8001 --no-security
# ... one per port you plan to use
```

### Running Simulations

```bash
# V6 vs RandomPlayer (single server)
uv run python src/testing_heuristics/2_vs_2/run_heuristic.py \
  --version v6 --total-games 1000 --ports 8000

# V1 vs MaxBasePowerPlayer (4 servers in parallel)
uv run python src/testing_heuristics/2_vs_2/run_heuristic.py \
  --version v1 \
  --total-games 10000 \
  --batch-size 256 \
  --concurrent-battles 16 \
  --ports 8000 8001 8002 8003 \
  --opponent max_power
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--version` | *required* | Heuristic version (`v1`, `v2`, `v6`) |
| `--total-games` | `10000` | Total battles to simulate |
| `--batch-size` | `500` | Battles per async batch |
| `--concurrent-battles` | `16` | Max concurrent battles per process |
| `--ports` | `8000` | Showdown server ports (multiple → multi-process) |
| `--opponent` | `random` | `random`, `self`, `max_power`, `simple_heuristic`, or any heuristic e.g. `v2` |
| `--data-dir` | `data` | Output directory for CSVs |
| `--log-level` | `INFO` | Logging verbosity |

## Logic Overview

### Heuristic Versions

We implemented three progressively more advanced heuristic strategies using
a **score-then-combine** approach: poke-env provides pre-validated per-slot
orders (`battle.valid_orders`), we score each independently, then combine
using `DoubleBattleOrder.join_orders` and pick the highest-scored pair.

| Version | Strategy | Key Capabilities |
|---------|----------|-------------------|
| **V1** | Max damage | `base_power × actual_effectiveness × STAB` per slot — no switching |
| **V2** | Stats-based | Physical/special split, burn penalty, defensive switching (toxic/walled/outsped) |
| **V6** | V2 + field | V2 switching + weather/terrain/priority modifiers on the base damage score |

### Doubles Decision Pipeline

Each turn, `choose_doubles_move` in `base.py` runs:

1. **Fetch valid orders** — `battle.valid_orders` returns two lists of
   `SingleBattleOrder` objects (one list per active slot), with correct move
   targets pre-computed by poke-env.
2. **Score each candidate** — `_score_order(order, pokemon, slot, battle)`
   is called for every candidate. Ally-targeting orders (`move_target < 0`)
   are penalised; opponent-targeting orders are scored by the actual target's
   type effectiveness.
3. **Combine with `join_orders`** — `DoubleBattleOrder.join_orders` filters
   out duplicates (e.g. both slots switching to the same Pokémon) and produces
   all valid (slot0, slot1) pairs.
4. **Pick the best pair** — `max(pairs, key=score0 + score1)` selects the
   highest combined-score combination.
5. **Fallback** — `choose_random_doubles_move()` on any exception.

### Why `valid_orders` instead of manual targeting?

In doubles, move targets are non-trivial:
- Normal moves can target an ally, opponent 1, or opponent 2 (`target < 0` = our side).
- Spread moves (Earthquake, Surf) use `EMPTY_TARGET_POSITION = 0` and hit all adjacent.
- Dynamax, Z-move, and Tera variants add more entries per move.

We delegate all of this to poke-env's `valid_orders` property, which handles
the full targeting matrix for the current battle state.

### Architecture

```
run_heuristic.py          CLI entry point
├── BattleManager          Async doubles battle loop + CSV extraction
├── ProcessLauncher        Multi-process orchestration
├── HeuristicFactory       Version string → Player class
└── heuristics/
    ├── v1.py              Simple max-damage (target-aware)
    ├── v2.py              Stats + switching
    └── v6.py              V2 + weather/terrain/priority field bonuses
```

### CSV Output Columns

| Column | Description |
|--------|-------------|
| `battle_id` | Unique battle identifier |
| `heuristic` | Heuristic version used |
| `opponent_type` | Opponent type (e.g. `random`) |
| `winner` | Username of the winner |
| `won` | `1` if our heuristic won, `0` otherwise |
| `turns` | Number of turns in the battle |
| `team_us` / `team_opp` | Pipe-separated species lists (all 6) |
| `fainted_us` / `fainted_opp` | Number of fainted Pokémon |
| `remaining_pokemon_us` / `opp` | Surviving Pokémon count |
| `total_hp_us` / `opp` | Sum of HP fractions of survivors |
