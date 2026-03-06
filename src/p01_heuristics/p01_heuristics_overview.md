# p01_heuristics: Rule-Based Game Logic and Heuristic Design

This directory contains the rule-based agents (heuristics) developed for the Pokémon Showdown AI. These agents serve as both baselines for performance and as the "teachers" for Reinforcement Learning training.

## Directory Structure

- **`s01_singles/`**: Implemented heuristics and evaluation pipeline for 1v1 battles (Gen 9 Singles).
- **`s02_doubles/`**: Design notes and early guides for 2v2 battles (Gen 9 Doubles).
- **`backup/`**: Archived experiments and analysis notebooks.

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

In `s01_singles/`, the code is split into:

- **`agents/`**: Strategy implementations (v1–v6), baselines, and LLM labels.
- **`core/`**: Shared infrastructure:
    - `base.py`: Abstract base class for rule-based singles players (`BaseHeuristic1v1`).
    - `common.py`: Math utilities (damage estimation, speed tiers, status helpers).
    - `factory.py`: Instantiates agents by string label (e.g. `"v6"`, `"abyssal"`, `"pokechamp"`).
    - `battle_manager.py`: Handles single-process simulation loops.
    - `process_launcher.py`: Distributes simulations across multiple ports/processes.
- **`evaluation/`**: Benchmark engine (`engine/`), reporting scripts (`reporting/`), and docs.

---

## 3. Heuristic Generations (v1 - v6)

Singles heuristics in `s01_singles/agents/internal/` evolve as follows:

- **v1**: Primary Power — greedy on base power × effectiveness × STAB, no structured switching.
- **v2**: Physical/Special Split — shared damage estimator with basic defensive pivoting (Toxic escape + weak-damage/outsped switch).
- **v3**: Defensive Stability — V2 logic plus per-battle move tracking for analysis.
- **v4**: Field-Aware Damage Overhaul — burn-aware damage with Weather/Terrain modifiers and simple danger-based pivoting.
- **v5**: Boost-Aware Field Expert — V4 plus stat-boost-aware damage, KO pre-check, and relaxed pivot rules.
- **v6**: Priority & Peak Field Awareness — V3-style defence with Weather/Terrain modifiers and priority move valuation.

---

## How to Run

For Singles (`s01_singles/`), see:

- `s01_singles/README.md` for a high-level overview and quick-start commands.
- `s01_singles/docs/CLI_REFERENCE.md` for all available `uv` commands and CLI flags.
- `s01_singles/docs/DATA_LAYOUT.md` for where benchmark CSVs are written under `data/1_vs_1/`.

For Doubles (`s02_doubles/`), the current state is documented in `s02_doubles/s02_doubles_guide.md` and focuses on design rather than a full implementation.
