# agents: Strategy Implementations (Doubles)

Specialized logic for the 2-active-Pokémon format.

## Versions
- `v1.py`: Independent per-slot greedy logic. No coordination.
- `v2.py`: Stat-aware damage and defensive switching.
- `v3.py`: Environmental awareness (Weather/Terrain) and Priority moves.
- `v4.py`: Tactical Synergy (Focus Fire and Protect strategy).
- `v5.py`: Apex Heuristic (Predictive KOs, Efficiency, and Threat targeting).
- `v6.py`: Optimization for survival; values HP preservation and status mitigation higher than v5.

## Performance Benchmarking
Agents are evaluated using a **10,000-game match-up matrix** across multiple generations (Gen 4–9).
- **Primary Metric**: Win Rate (%) against peers and baselines (`random`, `max_power`, `simple_heuristic`).
- **Secondary Metrics**: Turn duration, fainted Pokémon count, and HP survival percentage.
- **Tools**: Benchmarking is driven by `s02_doubles/evaluation/engine/benchmark.py`.
