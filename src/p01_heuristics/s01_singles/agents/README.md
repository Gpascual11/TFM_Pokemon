# 🧠 AGENTS: Intelligence & Strategy

This directory contains every agent implementation available in the 1v1 Singles framework. They are categorized by their underlying technology: Rules, Baselines, or LLMs.

---

## 🏛️ 1. Internal Heuristics (`internal/`)

These represent the core research output of the project. They follow an evolutionary path, where each version attempts to solve a specific weakness identified in the previous one.

### 🐣 V1: The Seed

- **Logic**: Selects the move with the highest base power.
- **Weakness**: Completely ignores types, STAB, and switching.
- **Switching**: Only switches if randomly prompted.

### 🐍 V2: Damage Awareness

- **Logic**: Introduces the `calculate_base_damage` helper. It factors in Type Effectiveness (x2, x4, x0.5) and STAB (x1.5).
- **Weakness**: Very fragile. Once it gets into a bad matchup, it stays in until it faints.

### 🛡️ V3: The Defensive Pivot (Foundational)

- **Logic**: Introduced the "Defense Hook."
- **Toxic Escape**: If poisoned (TOX) for more than 2 turns, it swaps out to reset the damage counter.
- **Speed Check**: If the opponent is faster AND the agent's best move does < 20HP damage, it switches to a better teammate.
- **Note**: This switching logic is so stable that V4, V5, and V6 still use it as their base.

### ⛈️ V4: Damage Refinement

- **Logic**: Adds Status check to damage calculation. If Burned (BRN), physical moves have their power halved in the math.
- **Weakness**: Still unaware of the environment (weather/terrain).

### ☀️ V5: Weather & Terrain Expert

- **Logic**: Multiplies move power based on field state.
- **Sun**: Fire moves (1.5x) / Water moves (0.5x).
- **Rain**: Water moves (1.5x) / Fire moves (0.5x).
- **Terrain**: Boosts moves matching the terrain (Electric, Grassy, Psychic) by 1.3x.

### 🏆 V6: Priority & Final Polishing

- **Logic**: Adds a **1.2x multiplier to Priority Moves** (Quick Attack, Shadow Sneak, etc.). This makes the agent "prefer" moves that hit first, allowing it to secure KOs on low-HP targets before being hit back.

---

## 🏎️ 2. Baselines (`baselines/`)

Standard implementations used for benchmarking to ensure our heuristics are actually improving.

- **`random`**: The baseline for $0\%$ intelligence.
- **`max_power`**: Chooses the highest base power move.
- **`simple_heuristic`**: A local version of the `abyssal` algorithm. It includes Gen 9 Terastallization logic.
- **`abyssal` / `one_step`**: Legacy agents from the `pokechamp` repository. They use damage estimation but lack the stability of our V3 defensive pivot.

---

## 🤖 3. LLM Agents (`llm/`)

These agents use Large Language Models (LLMs) to reason about the battle.

- **Architecture**: They take the current battle state as text, send it to **Ollama**, and parse the reasoning.
- **Logging**: Unlike heuristics, these agents emit "Thinking" files which explain *why* a move was chosen. These are found in `evaluation/results/LLM/`.

---

## 🏗️ How to add a new Agent

1. Create a new file in `internal/v7.py` (or similar).
2. Inherit from `BaseHeuristic1v1`.
3. Implement `_select_action(self, battle)`.
4. Register the agent in `agents/__init__.py`.
5. Update `AgentFactory.available_internal()` in `core/factory.py`.

Now your new agent is automatically compatible with the parallel benchmark engine!
