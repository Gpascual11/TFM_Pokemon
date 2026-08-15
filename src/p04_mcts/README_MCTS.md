# Shallow Monte Carlo search (v18–v20)

Root UCB with LocalSim rollouts. Agents: `HeuristicV18MCTS` / `v19` / `v20`, inheriting `HeuristicV14`.

Each turn, after KO / endgame shortcuts:

1. List legal moves + switches as **root** children.
2. For 100 iterations: pick a child by UCB1, run a **5-turn LocalSim** rollout, back up the score to that child.
3. Play the most-visited child.

Determinization copies **revealed** moves. Rollouts use pokechamp `LocalSim` (`pokechamp/poke_env/player/local_simulation.py`).

- **v18:** greedy rollout + HP-style leaf.
- **v19:** positional leaf and extra v14 overrides before the tree.
- **v20:** PUCT prior toward the v14 action; leaves use the v19-style scorer.

## Protocol

Any gauntlet matchup involving v18/v19/v20 uses **n = 1,000** and lower concurrency.

Results argument: [`../p00_core/reporting/heuristics_and_imitation_thesis_analysis.md`](../p00_core/reporting/heuristics_and_imitation_thesis_analysis.md).
