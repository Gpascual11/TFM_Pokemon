# Benchmark & Worker Engine Architecture (`src/p00_core/engine/`)

This document details the architectural design, concurrency handling, dynamic timeout scaling, crash recovery mechanisms, and telemetry schema of the parallel evaluation engine (`benchmark.py` and `worker.py`) used for large-scale paradigm comparisons in the Pokémon Showdown Gen 9 Random Battle reinforcement learning environment.

---

## 1. System Overview & Purpose

The evaluation suite is divided into an asynchronous orchestrator (`benchmark.py`) and isolated, short-lived subprocess workers (`worker.py`):

```
                       ┌─────────────────────────────────────────┐
                       │      run_paradigm_comparison_10k.sh     │
                       │   (Shell Gauntlet Loop & Retry Guard)   │
                       └────────────────────┬────────────────────┘
                                            ▼
                       ┌─────────────────────────────────────────┐
                       │              benchmark.py               │
                       │   (Async Port Queue & Batch Scheduler)  │
                       └──────────┬───────────────────┬──────────┘
                                  │                   │
                ┌─────────────────▼───┐           ┌───▼─────────────────┐
                │ worker.py (Batch 1) │           │ worker.py (Batch N) │
                │ Port: 8000          │           │ Port: 8000+N        │
                └──────────┬──────────┘           └──────────┬──────────┘
                           │                                 │
                   ┌───────▼───────┐                 ┌───────▼───────┐
                   │ _tmp_p8000.csv│                 │ _tmp_p800N.csv│
                   └───────┬───────┘                 └───────┬───────┘
                           │                                 │
                           └──────────────┬──────────────────┘
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Final Merged CSV (e.g. 10k)   │
                         │ data/benchmarks/all_10k/...csv  │
                         └─────────────────────────────────┘
```

### Why Subprocess Isolation (`worker.py`)?
Executing thousands of consecutive battles within a single long-lived Python process can cause severe memory bloat and resource exhaustion due to:
1. Object accumulation in complex tree-search hierarchies (`Minimax` nodes, `MCTS` rollout trees).
2. Residual background threads from third-party libraries (`poke_env`, async event loops, LLM client connections).

By dispatching battles in discrete mini-batches (`worker.py`), the operating system completely reclaims all allocated RAM, socket handles, and child threads when each subprocess exits.

---

## 2. Bidirectional & Matrix Tournament Architecture

In the shell driver (`run_paradigm_comparison_10k.sh`), the tournament evaluation matrix is defined using two core environment variables:

```bash
ALL_AGENTS=${ALL_AGENTS:-"v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 v13 v14 v15 v16 v17 v18 ml_advanced random max_power abyssal one_step safe_one_step simple_heuristic"}
NEW_AGENTS=${NEW_AGENTS:-"v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 v13 v14 v15 v16 v17 v18 ml_advanced random max_power abyssal one_step safe_one_step simple_heuristic"}
N_BATTLES=${N_BATTLES:-10000}
```

### Separation of `NEW_AGENTS` vs `ALL_AGENTS`
- **`NEW_AGENTS` (Outer Loop / Player 1 `_us`)**: Defines which agent initiates the benchmark run and evaluates its decision-making policy.
- **`ALL_AGENTS` (Inner Loop / Player 2 `_opp`)**: Defines the gauntlet of opponents tested against `Player 1`.

### Bidirectional Evaluation (20,000 Games per Matchup Pair)
When both `NEW_AGENTS` and `ALL_AGENTS` list all $N=25$ paradigms ($25 \times 25 = 625$ total matrix pairs):
1. When `NEW_AGENTS="v17"` and `ALL_AGENTS="ml_advanced"`, `benchmark.py` computes **10,000 games of `v17` (us) vs `ml_advanced` (opp)** and saves them to `v17_vs_ml_advanced.csv`.
2. When `NEW_AGENTS="ml_advanced"` and `ALL_AGENTS="v17"`, `benchmark.py` computes **10,000 games of `ml_advanced` (us) vs `v17` (opp)** and saves them to `ml_advanced_vs_v17.csv`.

Because Pokémon Showdown battles are asymmetric regarding starting leads, RNG seeds, and player turn priorities, evaluating both $A \text{ vs } B$ and $B \text{ vs } A$ provides exactly **20,000 bidirectional evaluation games (10,000 per side)** for unbiased statistical analysis.

---

## 3. Crash Recovery & Auto-Resumption (`while True` Loop)

The evaluation engine is built to run unattended inside a terminal multiplexer (`tmux`). It guarantees zero data loss and exact resumption via an auto-checkpointing control loop in `benchmark.py`:

```python
while True:
    already_done = 0
    if out_csv.exists():
        df = pd.read_csv(out_csv)
        already_done = len(df)

    n_to_run = target_battles - already_done
    if n_to_run <= 0:
        return already_done, total_new_overall

    # Distribute n_to_run across available asynchronous workers...
```

### Key Mechanisms:
1. **Instant Skip on Completion**: If a file (`v1_vs_v2.csv`) already contains 10,000 rows, `n_to_run` evaluates to `0`, and `benchmark.py` immediately exits with code `0` in under 0.1 seconds without spawning any subprocesses.
2. **Partial Progress Calculation**: If an execution was interrupted (`Ctrl+C`, power outage, or memory spike) after completing 4,320 games of `v18_vs_v16.csv`, `benchmark.py` reads the existing CSV, computes `n_to_run = 10000 - 4320 = 5680`, and runs *only* the remaining 5,680 games.
3. **Immediate Atomic Append**: As soon as each worker batch finishes (`_tmp_*.csv`), `benchmark.py` gathers the results, appends them directly to `out_csv` via `pd.concat([existing_df, new_df])`, and flushes to disk before starting the next batch.
4. **Self-Healing on Worker Failure**: If one out of eight parallel workers experiences a timeout or crashes midway through a batch, `benchmark.py` merges all successful rows from the surviving workers into `out_csv`. On the next iteration of `while True:`, it automatically spawns replacement workers to run precisely the games that failed, repeating until `already_done == 10000`.

---

## 4. Dynamic Timeouts & Execution Speed Across Paradigms

Computational cost varies by up to three orders of magnitude across evaluated agent paradigms:

| Paradigm Family | Representative Agents | Algorithm Description | Average Time per Game | Average Time per 10k Matchup (25 conc) |
| :--- | :--- | :--- | :---: | :---: |
| **Simple Heuristics** | `v1`, `v2`, `v3`, `v4`, `random`, `max_power` | Static rule evaluations and single-turn type effectiveness scoring. | **~0.01 – 0.1s** | ~1 – 3 minutes |
| **Imitation Learning (XGBoost)** | `ml_advanced` | Tree-ensemble evaluation for dynamic switch/stay policy routing + heuristic fallback. | **~0.1 – 0.2s** | ~3 – 5 minutes |
| **Minimax Tree Search** | `v15`, `v16` | Multi-turn depth lookahead with iterative deepening and alpha-beta pruning. | **~1.0 – 2.0s** | ~20 – 40 minutes |
| **Monte Carlo Tree Search** | `v17`, `v18` | Rollout simulations ($N$ iterations per decision) through game state branches. | **~2.0 – 4.0s** | ~45 – 90 minutes |

### Dynamic Timeout Formula
To prevent complex tree searches (`v16–v18`) from prematurely timing out while still catching frozen subprocesses during high CPU contention, `benchmark.py` dynamically calculates timeouts based on batch size:

```python
batch_timeout = max(7200, int(n_battles * 40))
```
- For a standard batch of `100 battles`, `batch_timeout = max(7200, 4000) = 7200 seconds` (**2 hours per batch**).
- For smaller final completion batches (`e.g., 10 battles`), it allows up to **40 seconds per battle** before triggering worker cleanup and re-queueing.

---

## 5. Telemetry Schema & Attribute Verification (73 Columns)

Every finished battle outputs exactly **73 standardized columns** (`StatsBattle`), capturing full decision dynamics and agent-specific tracking metrics:

### Core Battle Telemetry
- `battle_id`, `format`, `heuristic` (`Player 1`), `opponent` (`Player 2`), `winner`, `won` (`1` if us, `0` if opp).
- `turns`, `decisions_us/opp`, `fallback_moves_us/opp`, `error_moves_us/opp`.
- `fainted_us/opp`, `remaining_pokemon_us/opp`, `total_hp_us/opp`.
- `team_us/opp`, `side_conditions_us/opp`, `voluntary_switches_us/opp`, `forced_switches_us/opp`.
- Move statistics (`crit`, `miss`, `supereffective`, `hp_perc`, `hazard_sets/removals`, `setup_uses`, `ko_checks`, `matchup_switches`).
- Guard counters (`ko_guards_us/opp`, `loop_guards_us/opp`, `total_turns_us/opp`).

### Specialized Paradigm Telemetry
- **XGBoost / Imitation Learning (`ml_advanced`)**:
  - `xgb_switches_us/opp`: Number of switch actions dictated by the XGBoost policy.
  - `xgb_stays_us/opp`: Number of turns where XGBoost evaluated the board and elected to stay.
  - `xgb_prob_sum_us/opp`: Cumulative probability confidence sum across all XGBoost decisions.
- **Minimax / MCTS Tree Search (`v15–v18`)**:
  - `search_diff_us/opp`: Number of turns where tree search lookahead diverged from and overrode the base heuristic recommendation.
  - `search_switches_us/opp`: Number of voluntary switches triggered by MCTS/Minimax evaluation.
  - `search_moves_us/opp`: Number of attack moves triggered by tree search.
  - `endgame_solves_us/opp`: Number of exact depth-to-terminal endgame solves executed.

### Terastallization Attribute Extraction (`Fix 6`)
To maintain complete backwards compatibility across older `poke_env` forks (where terastallized flags were stored under `.is_terastallized`) and newer custom classes (where `Pokemon` objects strictly use `.terastallized` / `._terastallized`), `worker.py` uses the following universal extraction check:

```python
def _is_tera(mon: Any) -> bool:
    return bool(getattr(mon, "terastallized", getattr(mon, "_terastallized", False)))

"terastallized_us": 1 if hasattr(b, "team") and b.team and any(_is_tera(mon) for mon in b.team.values()) else 0,
"terastallized_opp": 1 if hasattr(b, "opponent_team") and b.opponent_team and any(_is_tera(mon) for mon in b.opponent_team.values()) else 0,
```
This guarantees that all existing historical baselines and all future evaluation runs consistently record exact terastallization activations across every agent paradigm.

---

## 6. Execution Instructions (`tmux`)

To execute the complete 20,000-game bidirectional matrix without risk of interruption:

```bash
# 1. Start a new detached session
tmux new -s tfm_10k

# 2. Launch the self-healing paradigm comparison script
uv run bash src/p00_core/scripts/runs_benchmark/run_paradigm_comparison_10k.sh

# 3. Detach from tmux session safely: Press Ctrl+B, then press D
```

To re-attach later and monitor progress:
```bash
tmux a -t tfm_10k
```
To check remaining game counts from any external terminal:
```bash
uv run python -c "
from pathlib import Path
out_dir = Path('data/benchmarks/all_10k/gen9randombattle')
csvs = sorted(out_dir.glob('*.csv'))
done = sum(1 for c in csvs if c.name != 'matchup_performance.csv' and sum(1 for _ in open(c, 'rb')) >= 10001)
print(f'Completed 10k Matchups: {done} / 625 ({done/625*100:.1f}%)')
"
```
