# s01_baselines_guide: Technical Rationale for Custom Baselines

In the `s01_singles` framework, we use specialized versions of certain baseline players. This document explains why these custom implementations exist and what problems they solve.

---

## 1. `true_simple_heuristic.py`
**Alias**: `simple_heuristic`

### Why it exists
While `poke-env` provides a `SimpleHeuristicsPlayer`, it is often insufficient for modern research for several reasons:
- **Gen 9 Support**: The built-in player does not natively handle **Terastallization** logic in its move scoring.
- **Opacity**: Having the logic as a library import makes it difficult to debug exactly why an agent chose a specific move during a benchmark.

### What it solves
The "True" implementation brings the source code directly into our repository, allowing us to:
1.  **Explicitly Add Terastallization**: Line 45 (`_should_terastallize`) adds logic to check if changing type will improve offensive and defensive matchups simultaneously.
2.  **Custom Scoring**: We can fine-tune the `SPEED_TIER_COEFFICIENT` and `HP_FRACTION_COEFFICIENT` to make the baseline more or less aggressive.
3.  **Transparency**: Every decision is visible in the local code, making it a reliable "White Box" baseline.

---

## 2. `safe_one_step_player.py`
**Aliases**: `one_step`, `safe_one_step`

### Why it exists
This agent is a critical fix for stability issues encountered when using code from the `pokechamp` research repository.
- **The "LocalSim" Problem**: The original `OneStepPlayer` depends on a local simulator and a complex "prompts" architecture.
- **The "Hang" Bug**: If the Gen 9 Pokedex cache is empty or the moveset JSON is missing, the original code enters a blocking state (it "hangs") waiting for data that never arrives.

### What it solves
The "Safe" version is a **non-blocking** implementation:
1.  **Zero Dependencies**: It uses only standard `poke-env` types and avoids all external simulation or prompt libraries.
2.  **Pure Mathematical Scoring**: It uses a deterministic formula (`base_power * STAB * type effectiveness * accuracy`) to score moves.
3.  **Benchmark Stability**: This ensures that massive simulations (e.g., 10,000 game sweeps) can run to completion without freezing or requiring manual intervention.

---

## Usage in Framework
Both of these agents are registered in the `AgentFactory` and are used by default in all generation-sweeps to provide a robust and stable performance baseline.
