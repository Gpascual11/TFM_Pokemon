# evaluation: Performance Benchmarking

This directory contains the tools to evaluate the final performance of the trained RL models against expert heuristics.

## Main Tools

### `run_benchmarks.py`
The primary evaluation suite. It tests two types of agents against a gauntlet of 9 different opponents (Random, MaxBP, and Heuristics v1-v6).

1.  **Pure PPO**: The neural network making 100% of the decisions.
2.  **Ensemble Agent**: A "Hybrid" player that blends the PPO's overall strategy with the Heuristic's tactical math using a weighted average (`alpha`).

---

## How to Run

To run a full benchmark of your latest model:

```bash
# Evaluate the model against all 9 opponents
python p02_rl_models/evaluation/run_benchmarks.py
```

### How it Works
The script loads the `.zip` model from your training directory and spins up multiple parallel battles. It generates a **Win Rate Table** (using `tabulate`) that looks like this:

| Opponent | Pure PPO | Ensemble |
| :--- | :--- | :--- |
| Random | 99% | 100% |
| Custom-V4 | 45% | 62% |
| ... | ... | ... |

---

## Implementation Detail: The Ensemble
The `EnsemblePlayer` class in `run_benchmarks.py` implements "Soft Voting". It takes the probability distribution from the PPO and the priority scores from the Heuristic, combines them, applies the Action Mask, and chooses the most likely "best" action.
