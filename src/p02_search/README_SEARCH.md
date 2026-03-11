# Phase 3: Adversarial Search (1-Ply Minimax)

## Overview
This module (`p02_search`) contains the implementation of the "Search" phase of the Master's Thesis. 

While the algorithms in `p01_heuristics` (`v1`-`v6`) were strictly "greedy", meaning they only evaluated the immediate damage and utility of a single move, this module introduces classical artificial intelligence through **Adversarial Search**.

## Architecture & Implementation

### 1. The Minimax Agent (`s01_singles/agents/internal/v7_minimax.py`)
- The `HeuristicV7Minimax` agent looks exactly one turn ahead (1-ply).
- It breaks the assumption that the game is static. For every possible valid action it can take, it simulates state transition.
- **The Minimax Algorithm**: It evaluates the resulting state by assuming the opponent will play perfectly (choose the move that maximizes *their* damage against the agent).

### 2. State Simulation (Game Theory)
Using the core logic from `p01_heuristics/s01_singles/core/common.py` (which calculates raw damage, type effectiveness, and speed brackets), `v7_minimax` maps out the game tree for a single turn.

The logic flow:
1. Iterate through all my legal moves.
2. For *each* move, iterate through all the opponent's legal moves.
3. Calculate the damage the opponent will do to me in return.
4. If they are faster, their damage happens first (potentially KOing me before I move!). If I am faster, my damage happens first.
5. Score the resulting board state.
6. Choose the move that results in the **highest** minimum score (maximizing the worst-case scenario).

## Thesis Relevance
By benchmarking this agent against `v6` (Expert Rules) and `ml_baseline` (Imitation Learning), the thesis can empirically prove the value of "looking ahead" versus rule-based reactivity in stochastic, partially observable environments like Pokémon VGC.
