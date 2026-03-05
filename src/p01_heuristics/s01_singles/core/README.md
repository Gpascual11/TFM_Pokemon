# 🧱 Core — The Singles Engine Foundation

This directory contains the shared infrastructure used by all heuristic agents and evaluation tools.

## 🗝️ Key Components

### 1. Unified `AgentFactory` (`factory.py`)
The central hub for agent instantiation. It allows creating any agent (Internal Heuristics, Poke-env Baselines, or LLM-based agents) using a simple string identifier.

**Usage:**
```python
from core.factory import AgentFactory
agent = AgentFactory.create("v6", battle_format="gen9randombattle")
```

### 2. Base Heuristic Template (`base.py`)
Defines the `BaseHeuristic1v1` abstract class. All internal agents inherit from this to ensure a consistent interface for move selection, logging, and history management.

### 3. Common Utilities (`common.py`)
Shared logic for:
- **Stat Retrieval**: Safe fallback from battle stats to base stats.
- **Damage Estimation**: Standard physical/special formula used across multiple versions.
- **Speed Calculation**: Accounting for Paralysis modifiers.

## ⚙️ Design Philosophy
The core is designed to be **stateless** and **extensible**. By centralizing damage logic and stat retrieval here, we ensure that improvements to the damage model (like adding Terrain awareness in `common.py`) can be propagated to all agents if desired.
