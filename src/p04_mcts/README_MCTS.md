# Phase 4: Monte Carlo Tree Search (MCTS)

## Overview & Context

While Phase 2 implemented a **1-ply Minimax Search** (`v15_minimax`), it suffered from two key limitations:
1. **Horizon Effect**: Looking only 1 turn ahead prevents the agent from valuing setup moves (e.g., Stealth Rock, Dragon Dance) that have long-term payoffs but zero immediate damage.
2. **Information Asymmetry**: Pokémon is a game of **partial observability** (hidden opponent moves, items, abilities, and bench Pokémon). Minimax is designed for perfect-information games, forcing us to make deterministic assumptions.

To solve both limitations, Phase 4 introduces **Information Set Monte Carlo Tree Search (IS-MCTS)** (`v16_mcts`).

---

## Why MCTS is Suited for Pokémon

MCTS does not search the entire game tree exhaustively. Instead, it uses stochastic simulations (rollouts) to selectively explore the most promising paths. This enables a much deeper lookahead (e.g., 3–5 turns) within the same execution time budget.

### 1. Handling Hidden Information (IS-MCTS)
Instead of searching a single deterministic tree, Information Set MCTS runs simulations by sampling "puzzles" of the opponent's state:
```
Information Set MCTS Algorithm:
For each simulation iteration:
  1. DETERMINIZATION: Sample a plausible opponent team & sets from the Showdown database
     (matching revealed species, unrevealed team counts, and common sets).
  2. TREE SEARCH: Run selection, expansion, simulation, and backpropagation
     using this deterministic sampled state.
  3. AGGREGATE: Average the action values across all different determinizations.
```
This aggregates scores across multiple possible opponent states, creating a mathematically sound probability distribution over moves that naturally accounts for opponent uncertainty.

### 2. High-Speed Rollouts via LocalSim
Exhaustive lookahead using the Node.js Showdown server is too slow (taking seconds per game). 
To make MCTS possible in real-time (under the 15-second turn timer), we use **`LocalSim`** (`pokechamp/poke_env/player/local_simulation.py`).
* **`LocalSim`** is a 1,700-line Python implementation of a local battle simulator.
* It allows us to execute `LocalSim.step(action_us, action_opp)` entirely in-process, running hundreds of simulations in milliseconds.

---

## MCTS Algorithmic Steps

The MCTS agent will run the following loop for a fixed number of iterations (e.g., 200 rollouts) on every turn:

1. **Selection**: Starting at the root node, traverse down the tree selecting action pairs using **UCB1** (Upper Confidence Bound) to balance exploitation and exploration:
   $$UCB1 = \bar{X}_j + C \times \sqrt{\frac{\ln N}{n_j}}$$
2. **Expansion**: Once a leaf node is reached, if it is not terminal, expand it by adding child nodes for all legal joint action pairs.
3. **Simulation (Rollout)**: From the expanded node, simulate the battle using a fast rollout policy (either random choices or a basic damage-based heuristic) using `LocalSim` until the battle ends or a maximum turn depth is reached.
4. **Backpropagation**: Propagate the final battle utility score (HP fraction difference or victory/defeat) back up the path to update the visit count and mean value of all traversed nodes.

---

## Planned Implementation Details

* **File Location**: `src/p04_mcts/agents/internal/v16_mcts.py`
* **Agent Class**: `HeuristicV16MCTS(HeuristicV14)`
* **Simulator Integration**:
  ```python
  # Inject pokechamp path to import LocalSim
  import sys
  from pathlib import Path
  sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent / "pokechamp"))
  
  from poke_env.player.local_simulation import LocalSim
  ```
