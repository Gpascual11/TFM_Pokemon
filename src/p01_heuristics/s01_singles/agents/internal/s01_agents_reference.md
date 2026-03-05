# agents: Strategy Implementations (Singles)

This folder contains the actual decision logic for all heuristic versions.

## Strategy Genealogy
- `v1.py`: **The Civilian.** Only knows about Base Power.
- `v2.py`: **The Fighter.** Learns about stats and basic status.
- `v3.py`: **The Tracker.** Adds memory of used moves per battle.
- `v4.py`: **The Strategist.** Comprehensive damage formula (Weather/Terrain).
- `v5.py`: **The Expert.** High-precision stat-boost tracking.
- `v6.py`: **The Champion.** Combines all previous features into the final stable baseline.
