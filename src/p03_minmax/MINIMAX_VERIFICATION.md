# Minimax 1-Ply Lookahead Verification

This document details the diagnostic validation of the **`v15_minimax`** (HeuristicV15Minimax) agent. It explains the simultaneous-move resolution mechanics, provides the tracing output from mock battle simulations, and discusses the computational complexity constraints of expanding search depth.

---

## 1. Trace Verification Output

To verify that the minimax algorithm is functioning as intended, we run a simulated battle trace:

```bash
uv run python scratch/test_minimax_trace.py
```

### Scenario 1: Iron Valiant (us, slower) vs Chien-Pao (opponent, faster)
* **Our action**: Close Combat (BP 120, FIGHTING) — Guarantees KO if it hits.
* **Opponent action**: Icicle Crash (BP 85, ICE) — Deals 180 damage (non-KO).

**Sequential Resolution Simulation**:
1. Opponent is faster, hits first with Icicle Crash (180 damage).
2. We survive with 110/290 HP (fraction: `0.379`).
3. We hit back with Close Combat, KOing Chien-Pao (0 HP, fraction: `0.0`).

**Score Calculation**:
$$Utility = \text{HP\_pct}_{me} - 1.5 \times \text{HP\_pct}_{opp}$$
$$Utility = 0.379 - 1.5 \times 0.0 = 0.379$$

---

### Scenario 2: Opponent's move now KOs us (deals 290 damage)
* **Our action**: Close Combat.
* **Opponent action**: Icicle Crash (boosted to deal 290 damage, exact KO).

**Sequential Resolution Simulation**:
1. Opponent is faster, KOs us with Icicle Crash.
2. We faint (`0` HP), which nullifies our Close Combat attack.

**Score Calculation**:
$$Utility = \text{HP\_pct}_{me} - 1.5 \times \text{HP\_pct}_{opp}$$
$$Utility = 0.0 - 1.5 \times 1.0 = -1.500$$

---

## 2. Computational Limits of Search Depth (Why 1-Ply?)

Pokémon is a simultaneous-move game with a very high branching factor:
* **Action Space**: On any given turn, each player has up to **9 legal actions** (4 moves + 5 switches).
* **Joint Actions**: A single turn represents a simultaneous decision matrix of up to **81 combinations** ($9 \times 9$).

### Branching Factor Growth:
* **1-Ply (1 Turn)**: $81$ joint action combinations.
* **2-Ply (2 Turns)**: $81^2 = 6,561$ joint action combinations.
* **3-Ply (3 Turns)**: $81^3 = 531,441$ joint action combinations.

### Runtime Performance Constraint:
The `v14` damage calculator runs 16-step exact damage calculations for each candidate move. Running these calculations across $6,561$ leaf nodes at 2-ply would take **5–10 seconds per turn** in Python. 

This violates Showdown's turn timer limits (15–20 seconds total) and makes running large-scale benchmarks (10,000 games) computationally prohibitive.

### Future Work:
To bypass the exponential branching factor of minimax, Phase 4 introduces **Monte Carlo Tree Search (MCTS)**. MCTS selectively samples promising branches using rollouts rather than exhaustively search all joint action combinations, enabling deeper lookahead within the same turn-time budget.
