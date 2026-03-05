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

## New Computer: GPU Setup & Optimization

As of March 2026, the project has migrated to a new machine with an **RTX 2080 GPU** and a **16-core CPU**. We have optimized the RL pipeline to maximize this hardware's throughput.

### 1. High-Parallelism Strategy (10 Servers)
Pokémon Showdown (Node.js) is single-threaded. To prevent the simulator from bottlenecking the GPU, we now use **10 independent servers** on 10 ports (8000–8009) rather than 1 server with many workers.
*   **Why**: 10 independent OS processes provide better I/O throughput than internal Node.js workers.
*   **Result**: Drastically higher FPS (Frames Per Second) during training.

### 2. Server Configuration (`config.js`)
To support this many instances, we have "gutted" the standard Showdown configuration:
*   **Workers**: Set `network: 1` and `simulator: 1` per server instance.
*   **Services**: Disabled all non-battle features (`verifier`, `friends`, `artemis`, `repl`) to prevent `ECONNRESET` and `EPIPE` crashes.
*   **Race Conditions**: Modified the launch script (`src/p03_scripts/p03_launch_custom_servers.sh`) to initialize the first server fully before starting others, preventing race conditions on shared config files (`chatrooms.json`).

### 3. Environment & Execution
We now strictly use **`uv`** for dependency management to ensure correct CUDA (cu124) support.

> [!IMPORTANT]
> **Module-Style Execution**: Always run training as a module from the project root to handle relative imports.
> ```bash
> # Recommended Launch Command (10 servers)
> uv run python -m src.p02_rl_models.s02_training.train_p1_base --timesteps 1000000 --ports 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009
> ```

---

## Guide Links

Please see the detailed guide files for step-by-step instructions:
- [Training Guide](file:///home/sirp/Documents/MUDS/TFM_Pokemon/src/p02_rl_models/s02_training/p02_s02_training_guide.md) – How to manage phases and checkpoints.
- [Evaluation Guide](file:///home/sirp/Documents/MUDS/TFM_Pokemon/src/p02_rl_models/s03_evaluation/p02_s03_evaluation_guide.md) – Benchmarking and visual reports.
- [Setup Guide](file:///home/sirp/Documents/MUDS/TFM_Pokemon/SETUP.md) – Full environment recreation.
