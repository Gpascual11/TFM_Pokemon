# 🧠 AGENTS: Intelligence & Strategy

This directory contains every agent implementation available in the 1v1 Singles framework. They are categorized by their underlying technology: Rules, Baselines, or LLMs.

---

## 🔎 Agent Families Overview

| Family | Labels (examples) | Implementation source | Typical use |
|--------|-------------------|------------------------|-------------|
| **Internal Heuristics** | `v1`–`v6` | `agents/internal/` (`HeuristicV1`–`HeuristicV6`) | Main research agents; all inherit from `BaseHeuristic1v1` and use shared math in `core/common.py`. |
| **poke-env Baselines** | `random`, `max_power`, `simple_heuristic` | `poke_env.player.*` + `agents/baselines/true_simple_heuristic.py` | Standard reference bots from `poke-env` (plus a local copy of `SimpleHeuristicsPlayer`). |
| **Pokechamp Baselines** | `abyssal`, `one_step`, `safe_one_step` | external `pokechamp` repo + `agents/baselines/safe_one_step_player.py` | Rule-based agents from PokéChamp. `one_step` and `safe_one_step` both map to `SafeOneStepPlayer` to avoid LocalSim hangs. |
| **Pokechamp LLM Agents** | `pokechamp`, `pokellmon`, `llm_vgc` | external `pokechamp` repo via `AgentFactory` | Minimax + LLM agents; configured via `--player_backend`, `--player_prompt_algo`, `--temperature`, etc. in the benchmark CLI. |

All of these can be requested by **string label** (e.g. `v6`, `abyssal`, `pokechamp`) via `AgentFactory.create(...)` or the benchmark `--agents / --opponents` flags.

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

### ⛈️ V4: Field-Aware Damage Refinement

- **Logic**: Refines damage with burn-aware physical/special scaling and integrates Weather/Terrain modifiers (Sun/Rain, Electric/Grassy/Psychic terrain).
- **Defence**: Uses a basic danger check to pivot out of obviously bad positions.

### ☀️ V5: Boost-Aware Field Expert

- **Logic**: Extends V4 by accounting for in-battle stat boosts in the damage formula (attack/defence stages) while still applying Weather/Terrain modifiers.
- **Defence**: Adds a KO pre-check and relaxed pivoting rules (Toxic escape, speed/damage thresholds, low-HP safety switches).

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

Now your new agent is automatically compatible with the parallel benchmark engine defaults (it will be picked up whenever `--agents/--opponents` are omitted, alongside all registered baselines but excluding LLM agents).
