# Baseline 1: Maskable PPO + Heuristics Ensemble

This directory contains the full Reinforcement Learning pipeline for the Pokémon Showdown AI project. The goal is to train a neural network that learns to play Pokémon well enough to beat smarter rule-based opponents.

The core model is **Maskable PPO** (Proximal Policy Optimization with invalid-action masking), trained using a **progressive 4-phase curriculum strategy**.

---

## File Overview

| File | Purpose |
|---|---|
| `rl_env.py` | Core RL environment: state encoding, action mapping, reward shaping, deadlock prevention |
| `vectorizer.py` | Converts a raw `Battle` object into a flat float tensor the neural net can read |
| `train_parallel.py` | Phase 1: trains PPO against `RandomPlayer` across parallel servers |
| `train_phase1_5.py`| Phase 1.5: bridges the gap by training against `MaxBasePowerPlayer` |
| `train_phase2.py` | Phase 2: resumes training from Phase 1.5 weights against `SimpleHeuristicsPlayer` |
| `train_phase3.py` | Phase 3: The Gauntlet. Trains against a mixed pool of opponents with aggressive evaluation |
| `evaluate_all.py` | Benchmarks both the standalone PPO and the Ensemble against 9 customized opponents |
| `train.py` | Quickstart single-threaded training script |

---

## The Curriculum Strategy (How & Why)

Training happens in four distinct phases to prevent the agent from hitting "training walls" or falling into catastrophic forgetting.

### Phase 1: The Fundamentals against `RandomPlayer` (`train_parallel.py`)
The model starts with no prior knowledge. It trains against a `RandomPlayer`. 
**Why:** This opponent is so weak that the model easily learns the basic rules of the game: switch to a favourable type matchup, use high-power moves, and never use disabled moves. 

### Phase 2 (1.5): Defensive Basics against `MaxBasePowerPlayer` (`train_phase1_5.py`)
Training resumes against an opponent that only clicks the highest damaging move available.
**Why:** If we jump straight from Random to Heuristics, the agent gets overwhelmed. `MaxBP` acts as a perfect bridge, forcing the agent to learn how to survive strong attacks and prioritize defense.

### Phase 3 (2.0): Tactical Warfare against `SimpleHeuristicsPlayer` (`train_phase2.py`)
Training resumes against an opponent that calculates type matchups and STAB.
**Why:** This pushes the agent beyond survival to actively predicting enemy switches and counter-attacking. However, training exclusively against this opponent can cause the agent to "forget" how to play defensively (Catastrophic Forgetting).

### Phase 4 (3.0): The Gauntlet (`train_phase3.py`)
The final phase trains the agent against a mixed pool of *all three opponents simultaneously* across parallel servers.
**Why:** This forces generalization. To prevent stalling (farming side-objectives without winning), the `GauntletEnvWrapper` intercepts rewards:
- **Victory:** `+100` (up from +30)
- **Stall Penalty:** `-0.1` per turn taken
This phase utilizes an `EvalCallback` to monitor performance on a dedicated evaluation server, stopping early if the agent peaks and begins to overfit.

---

## State Vectorization (`vectorizer.py`)

Neural networks cannot read text. `StateVectorizer.embed_battle()` parses the board into a **117-dimensional float tensor** (all values `[0.0, 1.0]`).
- **Active Pokémon (x2):** 35 values each (HP, 19 typings, 7 statuses, 8 stat boosts).
- **Team HP:** 6 values (HP fractions).
- **Enemy Team:** 7 values (Revealed HP fractions + estimated unrevealed alive count).
- **Environment:** Active Weather + Active Terrain encoding.

---

## Action Space and Masking (`rl_env.py`)

The agent outputs an integer between **0 and 9**:
- **0–3:** Use Move 1 through Move 4
- **4–9:** Switch to Team Member 1 through 6

To prevent the agent from picking an illegal move (which crashes the simulator), `PokemonMaskedEnvWrapper.action_masks()` returns a 10-length binary array. If a move is disabled or a Pokémon is fainted, its index is set to `0`. `MaskablePPO` forces the probability of that index to `0.0`.

---

## Reward Shaping

Dense per-turn rewards are calculated as a **delta** (change in state):
- Faint enemy: `+2.0`
- Deal Damage: `+1.0 × fraction`
- Lose Pokémon / Take Damage: `-2.0 / -1.0 × fraction`
- Super Effective Move Available: `+0.2` (encourages holding advantages)
- Enemy Hazard Setup: `+0.5` per hazard (encourages setting Spikes/Stealth Rock)

---

## The Ensemble: PPO + Heuristic Soft-Voting

For evaluation (`evaluate_all.py`), the PPO logic is blended with a hardcoded heuristic.
1. **PPO** outputs a neural-net probability array: `[0.4, 0.1, 0.3...]`
2. **Heuristic** outputs an independent scoring array.
3. The arrays are multiplied by an `alpha` weight (e.g., 0.5) and added together.
The PPO contributes long-term strategy, while the Heuristic covers precise turn-to-turn tactical math.
