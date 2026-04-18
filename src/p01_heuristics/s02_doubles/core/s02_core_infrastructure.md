# core: Heuristic Infrastructure (Doubles)

Support tools for the doubles format.

- `base.py`: The `BaseHeuristic2v2` class. Implements the **Score-then-Combine** pattern to resolve the complexity of simultaneous action selection (Slot 0 + Slot 1).
- `battle_manager.py`: Orchestrates parallel batched battles. Features advanced extraction logic for 30+ metrics including HP percentages, side conditions, and survival tracking.
- `common.py`: Shared doubles-specific math utilities (damage approximation, speed tiers).
- `process_launcher.py`: High-performance orchestrator that spawns multiple server instances and merges CSV results.

## Decision Pattern: Score-then-Combine
1. **Scoring**: Each legal order (Move/Switch) for each active slot is assigned a numerical weight.
2. **Joining**: `DoubleBattleOrder.join_orders` generates all legal pairings (protecting against double-switching to the same target).
3. **Selection**: The engine selects the pair that maximizes the sum of weights.
