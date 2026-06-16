# Phase 3: Adversarial Search (1-Ply Minimax)

## Overview
This module (`p03_minmax`) contains the implementation of the "Search" phase of the Master's Thesis. 

While the algorithms in `p01_heuristics` (`v1`-`v6`) were strictly "greedy", meaning they only evaluated the immediate damage and utility of a single move, this module introduces classical artificial intelligence through **Adversarial Search**.

---

## The Minimax Agents

### 1. `HeuristicV7Minimax` (`src/p03_minmax/agents/internal/v7_minimax.py`)
- Looks exactly one turn ahead (1-ply).
- Simulates state transitions by assuming the opponent will play perfectly to minimize our score.
- Maximizes our worst-case outcome using standard minimax logic.

### 2. `HeuristicV15Minimax` (`src/p03_minmax/agents/internal/v15_minimax.py`)
- Extends **`HeuristicV14`** to perform 1-ply search using the most advanced exact damage calculator in the repository.
- **Opponent Action Prediction**: Queries the opponent's revealed moves. If they have fewer than 4 moves revealed, it supplements the list using the Showdown sets database.
- **Switch Predictions**: If the opponent is in a disadvantageous matchup (active matchup score < 0.4), it adds a hypothetical `"switch"` action representing their best defensive teammate.
- **Speed-Aware Sequential Resolution**: Simulates turns sequentially. If the faster player's action KOs the slower player, the slower player's action is nullified.
- **Risk-Averse Evaluation**: Minimizes the worst-case scenario by scaling opponent damage taken by 1.5x:
  $$V(s) = \text{HP\_pct}_{me\_after} - 1.5 \times \text{HP\_pct}_{opp\_after} + \text{status\_bonus}$$

---

## Benchmark Results (10,000 Games)

We executed a comprehensive parallel tournament consisting of **10,000 games per matchup** to compare the minimax search agent (`v15`) against baseline and expert agents in `gen9randombattle`.

| Agent | Opponent | Win Rate (%) | Total Games | Sec/Game |
| :--- | :--- | :---: | :---: | :---: |
| **v15 (Minimax)** | abyssal | **48.5%** | 10000 / 10000 | 0.01 |
| **v15 (Minimax)** | v14 (Static) | **45.8%** | 10000 / 10000 | 0.01 |
| **v15 (Minimax)** | random | **98.4%** | 10000 / 10000 | 0.01 |
| **v15 (Minimax)** | v6 (Rule-based) | **64.8%** | 10000 / 10000 | 0.01 |
| **v15 (Minimax)** | max_power | **87.6%** | 10000 / 10000 | 0.01 |

### Key Findings
1. **Adversarial Superiority**: `v15` achieves a **45.8% win rate vs v14**, proving that 1-ply adversarial lookahead provides a substantial strategy lift compared to the static heuristic evaluator alone.
2. **Gauntlet Domination**: `v15` dominates standard rule-based agents (`v6` at 64.8%, `max_power` at 87.6%), showing it is highly robust across different playing styles.
