# Minimax Search Paradigm — Evaluation & Results

This document summarizes the evaluation of the 1-Ply Adversarial Minimax agents against the championship heuristic baseline (`v14`).

## 1. Experimental Setup

* **Base Model:** **`v15_minimax`** (HeuristicV15Minimax) — Base 1-ply minimax using a simplified HP/matchup evaluator.
* **Upgraded Model:** **`v16_minimax`** (HeuristicV16Minimax) — Upgraded 1-ply minimax incorporating `v14` action-specific bonuses (setup, hazards, hazard removal, and recovery).
* **Evaluation Metric:** Head-to-head win rate (WR%) over 1,000 games per matchup.

---

## 2. Matchup Win Rates (1,000 Games)

| Agent | Opponent | Win Rate (WR%) | Games Played | Speed (Sec/Game) |
|---|---|---|---|---|
| **`v15` (Base Minimax)** | `v14` (Championship Heuristic) | **42.1%** | 1,000 / 1,000 | 0.02 |
| **`v16` (Upgraded Minimax)** | `v14` (Championship Heuristic) | **45.2%** | 1,000 / 1,000 | 0.02 |

---

## 3. Thesis Key Insights & Discussion

1. **The Impact of Rule Preservation:**
   * Transitioning from the base HP evaluator (`v15`) to the rule-guided evaluator (`v16`) yielded a **+3.1% win rate improvement** (45.2% vs. 42.1%) against `v14`.
   * This shows that lookahead search alone is not enough; it must be paired with evaluator functions that value positional setups (like hazards and stat boosts) to avoid myopic blunders and ensure strategic continuity.

2. **Computational Efficiency:**
   * Unlike MCTS, 1-ply Minimax does not run in-process simulator rollouts. It uses analytical damage calculations. Because of this, it is exceptionally fast—completing matches in **0.02 seconds per game** (100 times faster than MCTS).
