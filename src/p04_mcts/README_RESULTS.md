# Shallow MCTS — lab notes

Gauntlet agents are **`v18`–`v20`**. Early lab tables in this file used other names (`v17_mcts`); map those labels onto the 28-agent matrix by CSV stem.

Search: **100 simulations × 5-turn LocalSim**, root UCB. n = **1,000** in the gen9 gauntlet.

LocalSim is the in-process rollout engine. For the thesis ranking use the 28-agent CSVs and [`../p00_core/reporting/heuristics_and_imitation_thesis_analysis.md`](../p00_core/reporting/heuristics_and_imitation_thesis_analysis.md).

## Older n=1k lab rows (historical names)

| Label in this note | Opponent | WR% | n | s/game |
|---|---|---|---|---|
| `v17` (base MCTS, lab name) | `v14` | 41.0 | 1,000 | 1.91 |
| `v18` (upgraded leaf, lab name) | `v14` | 43.0 | 1,000 | 2.02 |

In the full matrix, v20’s lift comes from disagreeing less with v14 (PUCT prior).
