# CSV Schema: Battle Output Columns

Every matchup CSV (`{agent}_vs_{opponent}.csv`) produced by the benchmark engine contains 46 columns per battle. This document describes each column, its source, and how to interpret it.

---

## 1. Identity & Outcome

| Column | Type | Description |
|--------|------|-------------|
| `battle_id` | str | Unique battle identifier from Showdown |
| `format` | str | Battle format (e.g., `gen9randombattle`) |
| `heuristic` | str | Primary agent label (row player) |
| `opponent` | str | Opponent agent label (column player) |
| `winner` | str | Username of the winner |
| `won` | int | 1 if the primary agent won, 0 otherwise |
| `turns` | int | Total turns in the battle |
| `timestamp` | str | ISO timestamp when the battle was recorded |

---

## 2. Decision Quality

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `decisions_us` | int | BaseHeuristic1v1 | Total times `choose_move` was called for the agent |
| `decisions_opp` | int | BaseHeuristic1v1 | Total times `choose_move` was called for opponent |
| `fallback_moves_us` | int | BaseHeuristic1v1 | Times agent had no plan → fell back to random move |
| `fallback_moves_opp` | int | BaseHeuristic1v1 | Times opponent fell back to random |
| `error_moves_us` | int | BaseHeuristic1v1 | Times agent logic crashed (exception caught) |
| `error_moves_opp` | int | BaseHeuristic1v1 | Times opponent logic crashed |

**Interpretation**: A well-implemented agent should have `fallback_moves = 0` and `error_moves = 0`. Non-zero values indicate the agent couldn't decide (fallback) or crashed internally (error). Compare `decisions - fallback - error` to get "deliberate decisions."

---

## 3. Team State (End of Battle)

| Column | Type | Description |
|--------|------|-------------|
| `fainted_us` | int | Number of agent's Pokemon that fainted |
| `remaining_pokemon_us` | int | Agent's Pokemon still alive |
| `total_hp_us` | float | Sum of HP fractions of alive Pokemon (0.0 to ~6.0) |
| `hp_perc_us` | float | Average HP fraction across all 6 Pokemon (0.0 to 1.0) |
| `fainted_opp` | int | Opponent's fainted Pokemon |
| `remaining_pokemon_opp` | int | Opponent's Pokemon still alive |
| `total_hp_opp` | float | Sum of HP fractions of opponent's alive Pokemon |
| `hp_perc_opp` | float | Average HP fraction of opponent's team |
| `team_us` | str | Detailed team state: `species(item:X,ability:Y,status:Z)` pipe-separated |
| `team_opp` | str | Same for opponent |
| `side_conditions_us` | str | Active hazards/screens on agent's side (e.g., `STEALTH_ROCK\|SPIKES(2)`) |
| `side_conditions_opp` | str | Active hazards/screens on opponent's side |

**Interpretation**: `hp_perc_us - hp_perc_opp` measures "domination" — how decisively the agent won/lost. Close to 0 = tight game, large positive = crushing win.

---

## 4. Tactical Tracking

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `voluntary_switches_us` | int | StatsBattle | Agent chose to switch (not forced by faint) |
| `forced_switches_us` | int | StatsBattle | Switches caused by faints |
| `move_stats_us` | str | StatsBattle | Moves used with counts: `bugbuzz:5\|airslash:3` |
| `move_stats_opp` | str | StatsBattle | Same for opponent |

**Interpretation**: `voluntary_switches` measures proactive pivoting. V7/V8 should show more voluntary switches than V1-V3 (which barely switch). `move_stats` proves which moves the agent actually used — look for `stealthrock`, `swordsdance`, `defog` in V7/V8's output.

---

## 5. RNG & Luck Tracking

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `crit_us` | int | StatsBattle | Critical hits the agent landed |
| `crit_opp` | int | StatsBattle | Critical hits the opponent landed on agent |
| `miss_us` | int | StatsBattle | Times the agent's moves missed |
| `miss_opp` | int | StatsBattle | Times the opponent's moves missed |
| `supereffective_us` | int | StatsBattle | Super-effective hits the agent landed |
| `supereffective_opp` | int | StatsBattle | Super-effective hits the opponent landed |

**Interpretation**: Use `(crit_us - crit_opp)` and `(miss_opp - miss_us)` to measure "luck advantage." Over 10k games these should average to near-zero. Individual battles with extreme luck can be identified and filtered for clean analysis.

---

## 6. Strategy Tracking (V7/V8 Only)

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `hazard_sets_us` | int | V7/V8 logic | Times agent deliberately set entry hazards |
| `hazard_sets_opp` | int | V7/V8 logic | Times opponent set hazards |
| `hazard_removals_us` | int | V7/V8 logic | Times agent used Defog/Rapid Spin |
| `hazard_removals_opp` | int | V7/V8 logic | Times opponent removed hazards |
| `setup_uses_us` | int | V7/V8 logic | Times agent used setup moves (Swords Dance, etc.) |
| `setup_uses_opp` | int | V7/V8 logic | Times opponent used setup moves |
| `ko_checks_us` | int | V7/V8 pre_move_hook | Times agent detected and executed a guaranteed KO |
| `ko_checks_opp` | int | V7/V8 pre_move_hook | Times opponent executed a guaranteed KO |
| `matchup_switches_us` | int | V7/V8 switch logic | Times agent switched based on matchup score |
| `matchup_switches_opp` | int | V7/V8 switch logic | Times opponent switched on matchup |

**Interpretation**: These columns are **always 0** for V1-V6 and baselines (they don't have those code paths). Non-zero values in V7/V8 prove the strategy logic is actively firing. Compare these against win rate to measure each strategy's contribution.

---

## 7. Backward Compatibility

The new strategy columns (Section 6) are appended at the end of the CSV. Tools that read only the first N columns will continue to work. The `DictWriter` ensures that agents without strategy tracking (V1-V6, baselines) simply write `0` for those fields.

---

## 8. Example Analysis Queries

```python
import pandas as pd

df = pd.read_csv("v7_vs_abyssal.csv")

# Win rate
print(f"Win rate: {df['won'].mean():.1%}")

# Average strategy actions per game
print(f"Hazards set: {df['hazard_sets_us'].mean():.2f} per game")
print(f"Setup moves: {df['setup_uses_us'].mean():.2f} per game")
print(f"KO checks: {df['ko_checks_us'].mean():.2f} per game")

# Luck-adjusted analysis
df['luck_score'] = (df['crit_us'] - df['crit_opp']) + (df['miss_opp'] - df['miss_us'])
print(f"Avg luck advantage: {df['luck_score'].mean():.3f}")

# Win rate excluding lucky games
neutral = df[df['luck_score'].abs() <= 1]
print(f"Luck-neutral win rate: {neutral['won'].mean():.1%}")
```
