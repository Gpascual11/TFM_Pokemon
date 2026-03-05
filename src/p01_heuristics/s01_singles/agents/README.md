# 🧠 Agents — Pokémon Battle Intelligence

This directory houses the logic for all 1v1 agents, categorized by their implementation strategy.

## 🏗️ Hierarchy

- **`internal/`**: Custom rule-based heuristics developed for this project.
    - `v1`: Max-damage greedy baseline.
    - `v2`: Adds defensive switching and toxic reset.
    - `v3`: Adds move tracking.
    - `v4`: Adds field awareness (Weather/Terrain).
    - `v5`: Adds KO-prediction and stat-boost awareness.
    - `v6`: Full Expert System with strategic weightings.
- **`baselines/`**: Standard rule-based agents imported from `poke_env` or the Pokechamp project.
    - `abyssal`: High-quality type-aware heuristic.
    - `safe_one_step`: Reliable 1-step lookahead without ML dependencies.
- **`llm/`**: Connectors for Large Language Model agents.
    - Integrates with the `pokechamp` repository via the Unified Factory.

## 🧱 Extension
To add a new agent:
1. Create a `.py` file in the appropriate subfolder.
2. Inherit from `..core.base.BaseHeuristic1v1`.
3. Register the agent in `agents/__init__.py`.
4. The high-performance benchmark engine will automatically support it.
