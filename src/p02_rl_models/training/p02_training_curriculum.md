# training: Curriculum RL Management

This directory contains the scripts for training the MaskablePPO model through its different learning phases.

## The Phases

1.  **`train_p1_base.py`**: The entry point. Trains against a `RandomPlayer`. The goal is to learn which moves do damage.
2.  **`train_p1_5_tune.py`**: Fine-tuning against `MaxBasePowerPlayer`. The goal is to learn that typing and survival matter.
3.  **`train_p2_transfer.py`**: Transfer learning against `SimpleHeuristics`. The goal is to learn complex switching and prediction.
4.  **`train_p3_gauntlet.py`**: The final "mastery" phase where the opponent changes every game.

---

## How to Run

### Step 1: Start the simulator
Ensure you have the Pokémon Showdown server running (locally or in a container). You can use the helpers in `p03_scripts/`.

### Step 2: Run a training phase
All scripts support `--timesteps` and `--ports`.

```bash
# Example: Run Phase 1 for 1 Million steps across 4 parallel server ports
python p02_rl_models/training/train_p1_base.py --timesteps 1000000 --ports 8000 8001 8002 8003
```

### Resuming
Most scripts support a `--resume` flag to continue from the last saved checkpoint instead of starting fresh.

---

## Technical Details

We use **Stable-Baselines3 (SB3)** with the `sb3-contrib` extension for Action Masking. 
- **Algorithm**: MaskablePPO
- **Architecture**: [256, 256] Multi-Layer Perceptron (MLP).
- **Parallelism**: `SubprocVecEnv` is used to run multiple battles in parallel, significantly speed up training on multi-core CPUs.
