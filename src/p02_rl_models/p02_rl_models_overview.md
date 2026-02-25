# p02_rl_models: Reinforcement Learning Pipeline

This directory contains the full Reinforcement Learning pipeline. The goal is to train a neural network that learns high-level strategy and tactical adaptations to beat expert heuristics.

## Directory Structure

- **`s01_env/`**: The core Gymnasium environment and state vectorization logic.
- **`s02_training/`**: The curriculum training scripts (Phase 1 through Gauntlet).
- **`s03_evaluation/`**: Benchmarking tools, the performance gauntlet, and visual reports.

---

## The Core Pipeline

### 1. State Mapping (`s01_env/vectorizer.py`)
Neural networks read arrays of numbers. Our vectorizer converts a complex `Battle` object into a **flat float tensor** representing HP, typings, status boosts, and field conditions.

### 2. Action Spaces (`s01_env/pokemon_env.py`)
The agent maps its outputs to an action index (0-9):
- **0–3**: Attack with Move 1-4.
- **4–9**: Switch to an available Pokémon in the team.
**Action Masking** is used to prevent the agent from attempting illegal actions (like switching to a fainted Pokémon).

### 3. Progressive Training (`s02_training/`)
We use a **4-Phase Curriculum**:
1. **Foundations (p1_base)**: Learn basics against `RandomPlayer`.
2. **Survival (p1_5_tune)**: Learn defensive fundamentals against `MaxBasePowerPlayer`.
3. **Tactics (p2_transfer)**: Learn advanced play against `SimpleHeuristicsPlayer`.
4. **The Gauntlet (p3_gauntlet)**: Generalize by playing against ALL opponents simultaneously.

---

## How to Run

Please see the guide files in each subdirectory for detailed instructions:
- See `s02_training/p02_s02_training_guide.md` to start a training session.
- See `s03_evaluation/p02_s03_evaluation_guide.md` for benchmarking and visual reports.
