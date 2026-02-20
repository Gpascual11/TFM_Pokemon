# 1-vs-1 Heuristic Simulations

We built a framework for testing heuristic-based Pokémon battling agents in
Generation 9 Random Battle (singles). The system supports multiple heuristic
versions, configurable opponents, multi-process parallel execution, and
structured CSV output for downstream analysis.

## Features

- **Four heuristic versions** (`v1`, `v2`, `v3`, `v4`) with increasing
  sophistication — from simple max-damage to expert-level strategies with
  KO detection, defensive pivoting, and weather/terrain awareness.
- **Flexible opponent selection** — fight against `RandomPlayer`,
  `MaxBasePowerPlayer`, `SimpleHeuristicsPlayer` (poke-env baselines),
  or play against any existing heuristic version (e.g. `--opponent v2`).
- **Multi-process execution** — one child process per Showdown server,
  with automatic work splitting and result merging.
- **Rich CSV output** — battle outcomes, team composition, fainted/remaining
  counts, HP totals, and move tracking for analysis.

## Setup

### Prerequisites

- Python 3.10+
- [poke-env](https://github.com/hsahovic/poke-env) (installed via `uv` or `pip`)
- A local [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) server

### Starting Showdown Servers

We use one server per port for parallel execution. Start them with the
helper script from the project root:

```bash
./src/start_sim.sh
```

Or manually:

```bash
node pokemon-showdown start --port 8000 --no-security
node pokemon-showdown start --port 8001 --no-security
# ... etc.
```

### Running Simulations

```bash
# V5 vs RandomPlayer (single server)
uv run python src/testing_heuristics/1_vs_1/run_heuristic.py \
  --version v5 --total-games 1000 --ports 8000

# V4 vs SimpleHeuristicsPlayer (4 servers in parallel)
uv run python src/testing_heuristics/1_vs_1/run_heuristic.py \
  --version v4 \
  --total-games 10000 \
  --batch-size 256 \
  --concurrent-battles 16 \
  --ports 8000 8001 8002 8003 \
  --opponent simple_heuristic
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--version` | *required* | Heuristic version (`v1`, `v2`, `v3`, `v4`) |
| `--total-games` | `10000` | Total battles to simulate |
| `--batch-size` | `500` | Battles per async batch |
| `--concurrent-battles` | `16` | Max concurrent battles per process |
| `--ports` | `8000` | Showdown server ports (multiple → multi-process) |
| `--opponent` | `random` | `random`, `self`, `max_power`, `simple_heuristic`, or any heuristic e.g. `v2` |
| `--data-dir` | `data` | Output directory for CSVs |
| `--log-level` | `INFO` | Logging verbosity |

## Logic Overview

### Heuristic Versions

We implemented four progressively more advanced heuristic strategies, all
built on a shared Template Method base class (`BaseHeuristic1v1`):

| Version | Strategy | Key Capabilities |
|---------|----------|-------------------|
| **V1** | Max damage | `base_power × effectiveness × STAB` — pure damage proxy |
| **V2** | Stats-based | Physical/special split, burn penalty, toxic/speed pivoting |
| **V3** | V2 + tracking | Same as V2, plus per-battle move-usage recording |
| **V4** | Expert | KO detection, danger pivoting, weather/terrain modifiers, priority boost |
| **V5** | V4 + accuracy | Full V4 logic with explicit accuracy weighting and relaxed switch thresholds |
| **V6** | V3 + field | V3 with weather/terrain/priority scoring (no KO detection) |

### Decision Pipeline

We designed a three-phase pipeline implemented via Template Method in `base.py`:

1. **Pre-move hook** (`_pre_move_hook`) — V4/V5 scan for guaranteed KO moves first.
2. **Select action** (`_select_action`) — main heuristic: damage estimation + switch logic.
3. **Fallback** — `choose_random_move()` when no action is selected.

### Architecture

```
run_heuristic.py          CLI entry point
├── BattleManager          Async battle loop + CSV extraction
├── ProcessLauncher        Multi-process orchestration
├── HeuristicFactory       Version string → Player class
└── heuristics/
    ├── v1.py              Simple max-damage
    ├── v2.py              Stats + switching
    ├── v3.py              V2 + move tracking
    ├── v4.py              Expert (KO, danger, weather, terrain)
    ├── v5.py              V4 + accuracy weighting, relaxed switching
    └── v6.py              V3 + weather/terrain/priority field bonuses
```

### CSV Output Columns

| Column | Description |
|--------|-------------|
| `battle_id` | Unique battle identifier |
| `heuristic` | Heuristic version used |
| `opponent_type` | Opponent type (e.g. `simple_heuristic`) |
| `winner` | Username of the winner |
| `won` | `1` if our heuristic won, `0` otherwise |
| `turns` | Number of turns in the battle |
| `team_us` / `team_opp` | Pipe-separated species lists |
| `fainted_us` / `fainted_opp` | Number of fainted Pokémon |
| `remaining_pokemon_us` / `opp` | Surviving Pokémon count |
| `total_hp_us` / `opp` | Sum of HP fractions of survivors |
| `moves_used` | Pipe-separated move ids (V4, V5 only) |
