# Testing Heuristics: Game Logic and Heuristic Design

This document explains how Pokémon Showdown battles work at a turn level, how we interface with the game via **poke-env**, and what **heuristics** we implemented for singles (1v1) and doubles (2v2).

---

## 1. Game Logic: How Battles Work

### 1.1 Turn Structure

A **turn** in Pokémon (and in Showdown) follows a fixed sequence:

1. **Request phase**  
   The server sends each player the current battle state and asks for an action. In our setup, the Python client receives a **battle object** with:
   - Our team and opponent team (including active Pokémon and bench).
   - For each active slot: **available moves** and **available switches**.
   - Current **weather**, **terrain**, **turn number**, and known info (e.g. HP, types, status).

2. **Decision phase**  
   Each player must choose, **per active Pokémon**:
   - **Either** one legal **move** (and, in doubles, a **target**: opponent slot 1 or 2, or “all adjacent” for spread moves).
   - **Or** one **switch**: replace that active Pokémon with a non-fainted bench Pokémon.

3. **Resolution phase**  
   The server resolves both sides’ actions (speed order, moves, damage, KOs, etc.), updates the state, and may trigger **forced switches** (e.g. when a Pokémon faints).

4. **Next turn or end**  
   If one side has no Pokémon left, the battle ends. Otherwise, the server sends a new request (possibly with **force switch**; see below).

So from the agent’s point of view: **each “step” is one request → one decision (one order per active slot) → wait for the next request.**

### 1.2 Forced Switches

When an active Pokémon **faints**, that slot is empty and must be filled before the next normal turn. The server sets **force switch** for that slot and only offers **switch** choices (no moves). Rules:

- **Doubles**: We have two slots. Zero, one, or both can be forced. We must pick **one distinct bench Pokémon per forced slot** (we cannot send the same Pokémon into both slots).
- Our code checks `battle.force_switch` and, when true, only considers `battle.available_switches[i]` for each slot `i`, and never picks the same Pokémon for two slots.

So: **turns** are request–response cycles; **switches** are either voluntary (we choose to switch) or **forced** (we must replace a fainted active).

### 1.3 Moves and Targets (Doubles)

- **Single-target moves**: We must choose target **1** or **2** (opponent’s left or right active).
- **Spread moves** (e.g. Earthquake, Dazzling Gleam): They hit “all adjacent foes” and do not take a target index; damage is typically reduced (e.g. 0.75×) per target in our damage formula.
- **Status / support moves**: Many have no target (e.g. Protect, Swords Dance, Tailwind). Some target an ally or foe; the battle object exposes legality.

Our heuristics only choose among **legal** options: `battle.available_moves[slot]` and `battle.available_switches[slot]` already respect game rules (PP, sleep, etc.).

### 1.4 What We Do Not Control

- **Speed** and turn order: the server resolves it.
- **Exact damage** and secondary effects: we only **estimate** damage; the real outcome can differ (crits, rolls, abilities, etc.).
- **Opponent’s choice**: in self-play or v1 vs v2, the opponent is another instance of our code (or random); we never see their decision before submitting ours.

So the “logic of the game” we implement is: **given the state and legal actions, output one order per active slot (move + optional target, or switch)**. The rest is handled by the server.

---

## 2. How We Made It Work: poke-env and Our Code

### 2.1 Environment: Pokémon Showdown + poke-env

- We run a **local Pokémon Showdown** server (Node.js). Battles are run in the **gen9randomdoublesbattle** (or **gen9randombattle** for singles) format.
- **poke-env** is a Python client that:
  - Connects via WebSocket to the server.
  - Parses incoming messages and builds a **battle** object (team, opponent team, active Pokémon, available moves/switches, force switch, weather, turn, etc.).
  - Asks our **Player** subclass for a decision by calling `choose_move(battle)` once per request.
  - Sends our decision back as a **BattleOrder** (or **DoubleBattleOrder** in doubles).

So: **one `choose_move(battle)` call = one turn’s decision for our side.**

### 2.2 Battle State We Use

From `battle` we use in particular:

| Concept | In code |
|--------|---------|
| Our active Pokémon (doubles) | `battle.active_pokemon[0]`, `battle.active_pokemon[1]` |
| Opponent active Pokémon | `battle.opponent_active_pokemon[0]`, `[1]` |
| Moves we can use this turn (per slot) | `battle.available_moves[slot]` |
| Bench Pokémon we can switch to (per slot) | `battle.available_switches[slot]` |
| Must we switch (e.g. after KO)? | `battle.force_switch` (list of bools per slot) |
| Turn number | `battle.turn` |
| Weather / terrain | `battle.weather`, `battle.terrain` |
| Teams (for logging) | `battle.team`, `battle.opponent_team` |

Each Pokémon object exposes things like **species**, **types**, **current_hp**, **max_hp**, **base_stats**, **stats** (if known), **fainted**, and **damage_multiplier(move)** for type effectiveness.

### 2.3 Submitting Our Decision

- **Singles**: We return a single **BattleOrder**, e.g. `self.create_order(move)` or `self.create_order(switch_pokemon)`.
- **Doubles**: We return a **DoubleBattleOrder** made of two orders (one per slot), e.g.  
  `DoubleBattleOrder(self.create_order(move1, move_target=2), self.create_order(switch_pokemon))`.

So: **turns** and **switches** “work” because we only ever submit legal orders that the server accepts; force switch is handled by only choosing from `available_switches` when `force_switch[i]` is true.

---

## 3. Heuristics We Applied

We implemented **rule-based** agents (heuristics) that score actions and pick the best one(s). No learning yet; the same rules run every time.

### 3.1 Damage Estimation (Shared Idea)

All our damage-based heuristics use a **simplified damage formula** to compare moves:

- **Physical**: use attacker’s Attack and defender’s Defense.
- **Special**: use attacker’s Sp. Atk and defender’s Sp. Def.
- **Type multiplier**: `defender.damage_multiplier(move)` (e.g. 2.0 for super effective, 0.5 for resisted).
- **STAB**: 1.5× if the move’s type matches one of the attacker’s types, else 1.0×.
- **Weather**: e.g. Sun boosts Fire and weakens Water; Rain does the opposite (we apply these in code).
- **Spread moves**: we multiply by 0.75 to approximate “hit both foes.”

So we get an **estimated damage** per (move, attacker, defender, battle). It is not exact (no crits, no full damage formula), but it’s good enough to rank moves.

### 3.2 Singles Heuristics (1v1)

- **v1 (MaxDamage)**: Pick the move that maximizes the simple damage score (base power × type effectiveness × STAB). No switching logic; if the only option is switch (e.g. after KO), we rely on poke-env’s default/random.
- **Later singles versions** (e.g. v2–v5): Add status awareness (Burn, Paralysis), defensive switching when threatened, and richer move scoring. The core is still: **one active Pokémon, one order per turn** (move or switch).

Singles are simpler than doubles because there is only one active slot and no target choice.

### 3.3 Doubles Heuristic v1: Per-Slot Greedy + Defensive Switch

**Idea**: Treat each of our two slots **independently**. For each slot, choose the move (and target) that scores highest; for force switch, choose the “safest” switch.

**Flow:**

1. **Force switch**  
   If `battle.force_switch` is true for any slot:
   - For each slot that must switch, we choose from `available_switches[slot]`.
   - We **never pick the same bench Pokémon for both slots** (we keep a `selected_indices` set).
   - We choose the switch that minimizes “worst type matchup”: for each candidate, we look at the maximum type multiplier the opponents have against it and pick the Pokémon with the **smallest** such multiplier (most defensive).

2. **Normal turn (no force switch)**  
   For slot 0 and slot 1 separately:
   - For each legal move and each legal target (opponent 1 or 2), we compute:
     - **Damage score**: `_score_doubles_move(move, me, target_opp, battle)` ≈ damage × accuracy, with a **+1000 bonus** if estimated damage ≥ target’s current HP (guaranteed KO).
     - Priority moves get a 2× score multiplier.
   - We pick the (move, target) with the highest score for that slot.
   - We build a **DoubleBattleOrder** from the two slot decisions.

**Heuristics applied:**
- **Damage maximization** per slot.
- **KO bonus**: large extra score when we can KO the target.
- **Priority bonus**: prefer high-priority moves.
- **Defensive switching**: on force switch, minimize exposure to opponents’ types (type-effectiveness minimization).

v1 does **not** consider: Protect, voluntary switches when not forced, spread moves specially, or coordination between the two slots (e.g. not double-targeting the same foe when one hit would KO).

### 3.4 Doubles Heuristic v2: Joint-Action Scoring and Coordination

**Idea**: Don’t decide each slot in isolation. **Enumerate candidate actions per slot**, then **score pairs of actions (slot0, slot1)** and pick the best pair. Add explicit handling of Protect, voluntary switches, spread moves, and coordination.

**Flow:**

1. **Force switch**  
   Same as v1: for each forced slot, choose a defensive switch from `available_switches`, without reusing the same Pokémon. v2 uses a **switch threat score** (how badly the opponents’ types hit this Pokémon + a small penalty for very low HP) and picks the **lowest** score.

2. **Normal turn: joint action**
   - **Enumerate actions per slot** (`_enumerate_slot_actions`):
     - **Emergency defense**: If we have a Protect-like move and (HP ≤ 30% or weakness ≥ 4×), add Protect (or similar) as a candidate.
     - **Voluntary switch**: If we have switches and (HP ≤ 25% or weakness ≥ 4×), add the best defensive switch.
     - **Offensive moves**: For each move, if it’s spread we add one action (no target); if single-target we add one action per opponent. We keep top 8 by score and deduplicate.
     - **Status/support moves**: Scored with `_score_status_move` (see below).
   - **Score every pair** (a0, a1) with `_score_joint_actions`:
     - Base = sum of per-action scores for a0 and a1.
     - **KO bonuses**: +250 per slot that gets a KO; +400 if we get two KOs on **different** targets (split KOs).
     - **Focus penalty**: If both slots single-target the **same** opponent:
       - If one slot alone already KOs, we apply a **focus penalty** (overkill).
       - If both together still don’t KO, we penalize (spread would be better).
       - If both are needed for the KO, small bonus.
     - **Spread synergy**: If we use a spread move and it pressures both foes, we add a bonus.
   - **Conflict check**: We reject pairs where both actions are switch and they switch to the **same** Pokémon (illegal).
   - We return the **DoubleBattleOrder** for the best (a0, a1).

**Heuristics applied:**
- **Joint action space**: best **pair** of actions, not two independent choices.
- **KO coordination**: reward double KOs and split KOs; penalize overkill and useless focus.
- **Spread moves**: explicit scoring and a synergy bonus when they pressure both foes.
- **Protect / defensive moves**: high score when we are low HP or very weak to the current board (4× weakness or HP ≤ 30%).
- **Voluntary switching**: when threatened (low HP or high weakness), consider switching out.
- **Threat targeting**: when scoring single-target moves, we add a bonus for targeting Pokémon that are super effective against us (`_opponent_threat_multiplier`), so we prefer to KO threats first.
- **Status/support moves**: hand-tuned scores for Fake Out, Tailwind, Trick Room, Protect, Thunder Wave, recovery, etc., and a base score for generic status; Protect gets a big boost when we’re in danger.

So v2’s “logic” is: **same game (turns, switches, moves, targets), but the decision is a joint (slot0, slot1) choice with coordination and defensive rules.**

### 3.5 Summary Table

| Aspect | v1 (doubles) | v2 (doubles) |
|--------|----------------|--------------|
| **Turn/switch rules** | Same (force switch → switch only; else move or switch) | Same |
| **Damage formula** | Same (estimate + weather + spread 0.75) | Same |
| **Decision unit** | Per slot, independent | Pair of actions (slot0, slot1) |
| **KO bonus** | +1000 if move KOs target | +250 per KO, +400 split KOs |
| **Focus** | No coordination | Penalize double-target overkill; reward spread |
| **Protect** | Not considered | Consider when low HP or 4× weak |
| **Voluntary switch** | Only on force switch | Consider when low HP or 4× weak |
| **Spread moves** | Treated as single-target in practice | Scored vs both foes; synergy bonus |
| **Threat targeting** | No | Bonus for hitting foes that threaten us |
| **Status moves** | Only via damage/accuracy | Explicit scores (Fake Out, Tailwind, etc.) |

---

## 4. Where This Lives in the Repo

- **Singles**: `src/testing_heuristics/1_vs_1/` — e.g. `test_heuristic_v1.py` (MaxDamage), later versions with status and switching.
- **Doubles**: `src/testing_heuristics/2_vs_2/` — `testing_heuristic_v1.py` (per-slot greedy), `testing_heuristic_v2.py` (joint action, Protect, spread, coordination).
- **Running**: We use **async** entrypoints: connect to Showdown, run `player.battle_against(opponent, n_battles=...)`, and after each batch we extract results (winner, turns, teams, moves used) and write CSVs. See the READMEs in `1_vs_1` and `2_vs_2` for exact commands and outputs.

This document summarizes **how the game logic (turns, switches, moves, targets) works**, **how we hook into it with poke-env**, and **what heuristics we applied** in our testing agents.
