# 🧠 Doubles Agents Reference: Heuristics & Baselines

This document provides a detailed technical breakdown of the strategies and logic used by each agent in the Double Battle (2v2) ecosystem. This reference is intended for developers looking to understand the "why" behind specific agent behaviors.

---

## 🏗️ Heuristic Evolution (The "V" Series)

All internal heuristics follow the **Score-then-Combine** pattern defined in `BaseHeuristic2v2`. They evaluate actions for each slot and then find the pair of actions with the highest collective impact.

### 🔴 Heuristic V1: Greedy Damage

- **Implementation**: `src/p01_heuristics/s02_doubles/agents/internal/v1.py`
- **Concept**: Maximum immediate pressure.
- **Logic**:
  - Calculates potential damage for every legal move against both opponents.
  - Returns the highest score using `base_power * type_effectiveness * STAB`.
  - Penalizes self-targeting moves (score = 0).
- **Targeting**: It automatically identifies which of the two active opponents receives more damage and directs the move there.
- **Weaknesses**:
  - No switching logic (will stay in even if hard-countered).
  - No status move awareness (prioritizes 40BP Tackle over 100% accurate Sleep Powder).
  - Frequently wastes moves on protected targets.

### 🟠 Heuristic V2: Strategic Switching

- **Implementation**: `src/p01_heuristics/s02_doubles/agents/internal/v2.py`
- **Concept**: Adds survival instincts to V1.
- **Logic**:
  - Inherits V1's damage scoring for offensive turns.
  - **Defensive Pivoting**: If the current Pokémon is at a severe type disadvantage (being hit for 2x or 4x damage by both opponents), it triggers a switch evaluation.
  - **Matchup Analysis**: It scans the benched Pokémon. If a teammate is found that resists the opponent's primary types, it receives a +50.0 priority boost, often overriding a high-damage but risky attack.
- **Weaknesses**: Still ignores field conditions and non-damaging utility moves.

### 🟣 Heuristic V6: Environmental Expert

- **Implementation**: `src/p01_heuristics/s02_doubles/agents/internal/v6.py`
- **Concept**: Advanced VGC-style tactical awareness and synergy.
- **Logic**:
  - **Weather Modifiers**: Actively checks `battle.weather`. Boosts Water (Rain) or Fire (Sun) moves by 1.5x. This makes the agent prefer "Hydro Pump" in rain even if it has a higher-BP coverage move.
  - **Terrain Integration**: Detects active fields (Electric, Grassy, Psychic, Misty) and scales move power by 1.3x for matching types.
  - **Priority Optimization**: Moves with priority (Quick Attack, Fake Out, Extreme Speed) receive a 1.2x multiplier. This helps the agent "clean up" weakened opponents before they can strike back.
  - **Status Buffs/Debuffs**: Increased scoring for moves that lower opponent stats if the opponent is a primary threat.

---

## 🔵 Specialized Baselines

### `vgc` (The Meta Specialist)

- **Concept**: A handcrafted heuristic designed specifically for the 2v2 competitive format (VGC).
- **Key Tactics**:
  - **Speed Control**: Prioritizes moves that modify speed (Tailwind, Icy Wind, String Shot). In Doubles, moving first with both Pokémon is often an instant win.
  - **Spread Management**: Optimized scoring for spread moves (Rock Slide, Dazzling Gleam). It understands that hitting two targets for 75% damage each (150% total) is often better than hitting one for 100%.
  - **Support Awareness**: Values status moves like `Protect` or `Helping Hand` higher than a greedy attacker would.

### `abyssal` (Abyssal Baseline)

- **Implementation**: `src/p01_heuristics/s02_doubles/agents/baselines/abyssal_doubles.py`
- **Concept**: A robust, rule-based agent ported from the PokéChamp project.
- **Logic**: Uses a weighted scoring system based on:
  - **Relative HP**: Prefers hitting opponents with low HP to secure KOs.
  - **Speed Tiers**: Knows when it will move first.
  - **Type Coverage**: Sophisticated multi-move evaluation.
- **Role**: This is our "gold standard" baseline. If a new heuristic cannot beat Abyssal consistently, it is not ready for competitive use.

### `one_step` (Lookahead)

- **Concept**: Minimal simulation.
- **Logic**: It doesn't just look at BP; it looks at the *result* of the turn. It picks the move that results in the highest remaining team HP and lowest opponent HP in the next immediate state.

---

## 🤖 LLM & AI Agents

These agents use the `benchmark_llm.py` runner to generate thinking logs.

### `pokechamp` (LLM Minimax)

- **Concept**: State Value Evaluation.
- **Logic**: Instead of hard-coded scores, it uses an LLM to "look" at the battle and say: *"This board state is an 8/10 for us."* The Minimax algorithm then uses these 8/10 evaluations to navigate a tree of possible moves. This allows it to handle "bluffs" and complex setup strategies.

### `pokellmon` (Pure Generative Strategy)

- **Concept**: Language-based Reasoning.
- **Process**:
  1. The battle state is transcribed into a human-readable prompt.
  2. The LLM generates a "Thought" process (Chain-of-Thought).
  3. The LLM outputs a single command (e.g., `move thunderbolt 1`).
- **Advantage**: It can adapt to weird teams or gimmicks that a rule-based heuristic has never seen before.

---

## 📊 Performance Cheat Sheet

| Agent | Speed | Logic Depth | Best Against |
| :--- | :--- | :--- | :--- |
| `v1` | ⚡ Ultra Fast | 🟢 Shallow | Random / Beginners |
| `v2` | ⚡ Fast | 🟡 Defensive | Glass Cannons / Fast Attackers |
| `v6` | 🔵 Moderate | 🟠 Tactical | Most rule-based baselines |
| `vgc` | 🔵 Moderate | 🔴 Expert | Meta-teams / Speed-reliant teams |
| `abyssal`| 🔵 Moderate | 🔴 Expert | General Matchups |
| `LLMs` | 🐌 Slow | 🟣 Philosophical | Unpredictable, niche strategies |

---

## 🧪 Testing New Agents

If you are implementing a new agent:

1. Extend `BaseHeuristic2v2` or `Player`.
2. Add it to the `AgentFactory` in `core/factory.py`.
3. Benchmark it against `abyssal` and `v6` to measure progress.
