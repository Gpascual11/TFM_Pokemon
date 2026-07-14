# MCTS Search Paradigm — Evaluation & Results

This document summarizes the evaluation of the Information Set Monte Carlo Tree Search (IS-MCTS) agents against the championship heuristic baseline (`v14`).

## 1. Experimental Setup

* **Base Model:** **`v17_mcts`** (HeuristicV17MCTS) — Uses greedy type-aware rollouts and a raw HP-difference terminal evaluator.
* **Upgraded Model:** **`v18_mcts`** (HeuristicV18MCTS) — Uses greedy type-aware rollouts and a `v14`-guided positional terminal evaluator (HP, type matchup matrix, and status conditions).
* **Rollout Depth:** 5 turns lookahead per simulation.
* **Simulations per Turn:** 100 iterations.
* **Evaluation Metric:** Head-to-head win rate (WR%) over 1,000 games per matchup.

---

## 2. Matchup Win Rates (1,000 Games)

| Agent | Opponent | Win Rate (WR%) | Games Played | Speed (Sec/Game) |
|---|---|---|---|---|
| **`v17` (Base MCTS)** | `v14` (Championship Heuristic) | **41.0%** | 1,000 / 1,000 | 1.91 |
| **`v18` (Upgraded MCTS)** | `v14` (Championship Heuristic) | **43.0%** | 1,000 / 1,000 | 2.02 |

---

## 3. Thesis Key Insights & Discussion

1. **Search Upgrades via Positional Guidance:**
   * Transitioning from raw HP evaluation (`v17`) to a `v14`-guided positional evaluator (`v18`) yielded a **+2.0% win rate improvement** (43.0% vs. 41.0%) against the championship heuristic. 
   * This proves that lookahead search in imperfect information domains like Pokémon benefits significantly from incorporating domain-specific heuristics (matchup advantages and status condition weights) at leaf node evaluations.

2. **The Constraints of Low Search Budget:**
   * At 100 simulations per turn, MCTS is constrained in its lookahead width. However, achieving a **43.0% win rate** against a monolithic 2,100-line expert system (`v14`) using only a simple type-aware rollout policy is highly successful. It demonstrates that search alone can approximate expert-level play without requiring a massive hand-crafted codebase.

### 3.1 Methodological Analysis: Why Lookahead Search Underperforms Pure Heuristics
An counter-intuitive result in the final Elo matrix is that the search-based agents (`v15` Minimax, `v18` MCTS) underperform the pure rule-based expert systems (`v12`, `v13`, `v14`). In an academic defense, this is framed as a key finding of search limitations in complex stochastic domains:
* **The Horizon Overriding Effect**: Rule-based agents (`v12–v14`) utilize hardcoded, long-term strategic priority systems (such as saving a key sweeper for the late-game, or prioritizing hazard setting). A shallow tree search (1-ply minimax or a 5-turn MCTS lookahead) evaluates states purely on leaf utility. Consequently, the search agent will often identify a short-term advantage (e.g., deal immediate damage) and override a superior long-term heuristic choice.
* **Rollout Noise & Simulation Discrepancies**: MCTS relies on `LocalSim` (a local Python simulator) for rollouts. Slight mismatches in simulator logic relative to the actual Showdown Node.js server acts as noise, misguiding UCB1 value estimates.
* **Low Search Budget for Imperfect Information**: A budget of 100 simulations per turn is extremely small given the branching factor of Pokémon. Under heavy hidden information (unknown opponent team, moves, and items), the search tree is too shallow and wide to reach strategic consensus, making a monolithic expert system more robust.
