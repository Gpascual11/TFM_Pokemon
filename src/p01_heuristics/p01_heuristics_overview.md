# p01_heuristics: Rule-Based Game Logic and Heuristic Design

This directory contains the rule-based agents (heuristics) developed for the Pokémon Showdown AI. These agents serve as both baselines for performance and as the "teachers" for Reinforcement Learning training.

## Directory Structure

- **`s01_singles/`**: Heuristics for 1v1 battles (Gen 9 Singles).
- **`s02_doubles/`**: Heuristics for 2v2 battles (Gen 9 Doubles).
- **`backup/`**: Archived experiments and early analysis notebooks.

---

## 1. Game Logic: How Battles Work

### 1.1 Turn Structure
A **turn** in Pokémon follows a fixed sequence:
1. **Request phase**: The server sends the current battle state and legal actions.
2. **Decision phase**: The agent chooses a **move** or a **switch** for each active slot.
3. **Resolution phase**: Actions resolve based on speed, priorities, and RNG.
4. **Forced switches**: Occurs when a Pokémon faints.

### 1.2 Decision Pipeline
All heuristics follow a general scoring pipeline:
1. **Scoring**: Each legal action is assigned a numeric value based on damage, status, or utility.
2. **Normalization**: Scores are compared (and sometimes coordinate in doubles).
3. **Execution**: The highest-scoring legal order is submitted.

---

## 2. Shared Core Components
Each sub-module (`s01_singles`, `s02_doubles`) is split into:
- **`agents/`**: The specific strategy implementations (v1–v6).
- **`core/`**: Shared infrastructure:
    - `base.py`: Abstract base classes for players.
    - `common.py`: Math utilities (damage estimation, speed checking).
    - `factory.py`: Instantiates agents by version string (e.g., "v6").
    - `battle_manager.py`: Handles simulation loops.

---

## 3. Heuristic Generations (v1 - v6)
- **v1**: Simple Max-Damage greedy selection.
- **v2-v3**: Adds basic defensive switching and status awareness.
- **v4-v5**: Expert-level damage formulas (weather, terrain, stat boosts) and danger-aware pivoting.
- **v6**: The current state-of-the-art combined logic with field awareness.

---

## How to Run
Please refer to the `README.md` inside `s01_singles/` or `s02_doubles/` for specific execution commands and parameter details.
