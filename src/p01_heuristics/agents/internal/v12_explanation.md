# Heuristic V12: The Meta Master

Heuristic V12 (`HeuristicV12`), codenamed **The Meta Master**, represents the pinnacle of the rule-based heuristic agents developed for the 1v1 Singles Pokémon Showdown framework. It is an evolutionary hybrid agent that integrates and refines all previous heuristic optimizations (from V1 through V11) and introduces advanced game-state meta-tactics, including Team Preview Lead Selection, Matchup-Based Fainted Switch-in Selection, and Gen 9 Terastallization evaluation.

In comprehensive tournament benchmarks (running 10,000 games per matchup across all 9 generations, totaling over 29 million games), Heuristic V12 emerged as the **Tier 0 Meta Leader**. It achieved a **1817 Bradley-Terry ELO** in Generation 9 (highest among all rule-based agents and baselines) and **1846 ELO** in Generation 1, clearly outperforming the two primary search and rule-based baselines: **Abyssal** (from Pokechamp) and **Simple Heuristic** (a local native clone).

This document provides a detailed breakdown of how Heuristic V12 works under the hood and analyzes the structural and strategic reasons why it consistently outperforms these baselines.

---

## 1. Key Competitive Performance Metrics (Gen 9)

| Metric | Heuristic V12 vs. Abyssal | Heuristic V12 vs. Simple Heuristic | Heuristic V12 vs. Random | Heuristic V12 vs. Max Power |
| :--- | :---: | :---: | :---: | :---: |
| **Win Rate** | **59.9%** | **59.8%** | **98.6%** | **90.3%** |
| **Fainted Differential** | **+0.68** | **+0.70** | **+4.26** | **+2.62** |
| **Bradley-Terry ELO** | **1817** (V12) vs. **1758** (Abyssal) | **1817** (V12) vs. **1752** (Simple Heuristic) | — | — |

*Note: A positive fainted differential of **+0.68 / +0.70** indicates that, on average, Heuristic V12 defeats these strong baselines with more than half a Pokémon remaining, representing a significant competitive gap.*

---

## 2. Core Architectural Pillars of Heuristic V12

Heuristic V12's decision logic is organized into several sequential layers, executed at every decision boundary.

### A. Team Preview & Lead Selection (`teampreview`)
Before the battle starts, if Team Preview is active, Heuristic V12 evaluates the optimal starting Pokémon:
1. **Opponent Team Known**: It calculates the matchup score of each teammate against every member of the opponent's team previewed roster using the `_estimate_matchup` helper. It computes the **average matchup score** for each teammate.
2. **Sorting**: Teammates are sorted in descending order of their average matchup score. If scores are equal, they are sorted by base Speed descending.
3. **Command**: It returns the team order string (e.g., `/team 312456`), leading with the teammate that has the highest overall average advantage.

*Impact*: This prevents leading into a disadvantageous type matchup on Turn 1, giving Heuristic V12 immediate positional control.

### B. Matchup-Based Fainted Switch-in Selection
When Heuristic V12 is forced to switch (either because its active Pokémon fainted or due to a forced switch effect like Whirlwind/Roar), it selects the switch-in teammate that has the best matchup score against the active opponent:
- If the opponent Pokémon is active and not fainted, it evaluates `self._get_best_switch(battle, opp)`.
- If both Pokémon fainted simultaneously (double faint), it evaluates `self._get_best_switch_double_faint(battle)`, which averages matchups against the opponent's remaining unfainted roster.

*Impact*: This ensures that every entry onto the field is optimized defensively and offensively, keeping momentum.

### C. Priority KO Pre-Check Hook (`_pre_move_hook`)
Before evaluating standard moves, Heuristic V12 runs a priority KO check:
1. It identifies all available priority moves (moves with `priority > 0` and `base_power > 0`).
2. It calculates expected damage fraction, factoring in STAB, type effectiveness, physical/special stats ratios, and expected hits.
3. If a priority move is guaranteed to KO the opponent (estimated damage is at least twice the opponent's remaining HP fraction to ensure a safe margin), it immediately executes that move.

*Impact*: This allows Heuristic V12 to secure KOs on low-HP targets before they can strike, neutralizing faster threats and conserving its own HP.

### D. Weather and Terrain Modifiers
Unlike baseline agents that assume neutral field conditions, V12 incorporates field modifiers into move scoring:
- **Weather**: Multiplies Fire-type moves by 1.5x and Water-type moves by 0.5x in Sun; multiplies Water-type moves by 1.5x and Fire-type moves by 0.5x in Rain.
- **Terrain**: Multiplies matching-type moves by 1.3x under Electric, Grassy, or Psychic terrains.

### E. Defensive Switching & V3 Defensive Pivot (`_should_switch`)
Heuristic V12 monitors safety triggers to decide if it must switch:
- **Toxic Escape**: If poisoned (TOX) and has stayed in for more than 2 turns (`status_counter > 2`), it switches out to reset the Toxic damage counter.
- **Speed Check / Outclassed Check**: If the opponent is faster and Heuristic V12's strongest move does less than 30HP damage (`WEAK_MOVE_THRESHOLD`), it recognizes it is outclassed and switches out.
- **Stat Boost Checks**: If its defenses are lowered by $\le -3$, or its primary attacking stat is lowered by $\le -3$, it pivots.
- **Matchup Score Threshold**: If the matchup score falls below `-2` (`SWITCH_OUT_MATCHUP_THRESHOLD`), it switches.

### F. Low-HP Sack Logic (`SAC_HP_THRESHOLD = 0.2`)
To prevent wasting turns, V12 implements **Sack Logic**:
- If the active Pokémon's HP is $\le 20\%$ and it is in a bad matchup, instead of switching it out (which would allow the opponent a free hit on the incoming teammate), V12 keeps it in to attack or use status moves.
- The low-HP Pokémon is allowed to faint ("sacked"), providing Heuristic V12 with a **free switch-in** where it can bring in its best counter-pick without taking damage.

### G. Pivot Moves (Volt Switch / U-turn)
If Heuristic V12 decides it must switch out, it checks if it possesses a pivot move (like Volt Switch or U-turn) and if it outspeeds the opponent. If the pivot move deals neutral or better damage, it chooses to use the pivot move instead of a raw switch.

*Impact*: This inflicts damage and breaks opponent Sturdy/Focus Sashes while transitioning to a counter-pick.

### H. Tight Hazards & Setup on Free Turns
Entry hazards (Stealth Rock, Spikes) and setup moves (Swords Dance, Dragon Dance) are powerful but risky. Baselines often waste turns using them while getting attacked and KO'ed. Heuristic V12 enforces **Tight Action Rules**:
- **Free Turns Only**: It only sets hazards or uses setup moves if it **outspeeds** the opponent AND **resists** the opponent's STAB types (`_resists_opp_stab`).
- This guarantees setup/hazards are only used when the opponent has no immediate offensive pressure.

### I. Tactical Status Moves
If Heuristic V12's damaging moves are weak (`max_score < 40`) and the opponent has high HP ($\ge 70\%$), it checks for status-inflicting moves to cripple the target:
- **Toxic/Poison**: Prioritized (Score 3) to stall out bulky walls, unless the target is Steel or Poison.
- **Will-O-Wisp (Burn)**: Prioritized (Score 2) against physical attackers to halve their damage output.
- **Thunder Wave (Paralysis)**: Prioritized (Score 1) if the opponent is faster, slowing them down.

### J. Gen 9 Terastallization Logic
Heuristic V12 evaluates Terastallization before attacking:
1. It calculates `offensive_tera_score` (type effectiveness of the chosen move).
2. It calculates defensive effectiveness before and after Terastallizing against the opponent's STAB types.
3. If Terastallizing improves the net offensive-to-defensive ratio ($> 1.0$), it triggers it.

### K. Gen-Aware Adaptation
V12 adapts its strategy based on the Showdown generation format:
- **Gen 1**: Disables all hazard and setup logic (as entry hazards did not exist and setup was mechanically different).
- **Paralysis Speed Penalty**: Adjusts the speed multiplier to 0.25x in Gen 1-6 and 0.5x in Gen 7+ to match changing game rules.

---

## 3. Why V12 Beats Abyssal and Simple Heuristic Baselines

The tournament data shows a clear competitive gap between Heuristic V12 and the baselines. The reasons for this dominance are structural:

### 1. The Fainted Switch-in Randomization Bug in Baselines
- **The Issue**: In both `Abyssal` and `Simple Heuristic` (`TrueSimpleHeuristicsPlayer`), when their active Pokémon faints, `battle.active_pokemon` is set to `None`. In their decision loop:
  ```python
  if active is None or opponent is None:
      return self.choose_random_move(battle)
  ```
  This causes them to return `choose_random_move()`. During a forced switch after fainting, the only valid moves are switches. Consequently, they **randomly pick a teammate** to switch in.
- **V12's Advantage**: Heuristic V12 explicitly handles fainted switch-ins:
  ```python
  if force_switch or me is None or me.fainted or not battle.available_moves:
      if battle.available_switches:
          # Selects teammate with the absolute best matchup
  ```
  By bringing in a calculated counter-pick instead of a random Pokémon, V12 maintains offensive momentum and prevents the baselines from exploiting their fainted turns.

### 2. Tempo and Action Economy: Tight Setup vs. Naive Setup
- **The Issue**: `Abyssal` and `Simple Heuristic` check for setup and hazard opportunities naively. If they have Stealth Rock and the opponent has $\ge 3$ Pokémon, they will click Stealth Rock even if they are outsped and about to be KO'ed.
- **V12's Advantage**: V12's **"Free Turns Only"** constraint ensures it never throws away a turn (and a Pokémon) just to lay hazards or setup. This discipline keeps V12's damage-dealing rate much higher and avoids fatal tempo losses.

### 3. Sack Logic vs. Wasted Switch-in Damage
- **The Issue**: When a baseline's active Pokémon is low on HP (e.g., 5% HP) and in a disadvantageous matchup, it will switch it out. The incoming teammate is forced to absorb a hit on the switch, and the 5% HP Pokémon remains in the back, usually fainting to hazards or a priority move later.
- **V12's Advantage**: V12's Sack Logic recognizes that at $\le 20\%$ HP, switching is mathematically worse than letting the Pokémon faint. By staying in to deal chip damage or inflict status, V12 forces the opponent to spend a turn KO'ing it, which awards V12 a **free switch-in** for its next counter-pick.

### 4. Advanced Game-State Awareness (Trick Room, Screens, Immunities, Items)
- **The Issue**: Baselines calculate damage using a basic formula containing only base power, STAB, and type effectiveness. They are blind to:
  - Screens (Reflect / Light Screen) halving damage.
  - Bulky items (Assault Vest) or offensive items (Life Orb, Choice Band).
  - Trick Room speed reversal.
  - Ability-based immunities (e.g., attacking a Flash Fire Pokémon with a Fire-type move).
- **V12's Advantage**: V12 includes all of these factors in its scoring formula, preventing it from making catastrophic errors (like clicking Earth Power against a Levitate Pokémon or choosing a physical move into Reflect when a special move is available).

### 5. Lead Optimization
- **The Issue**: Baselines do not optimize their starting lead in Team Preview, leading to random start matchups.
- **V12's Advantage**: V12 leads with its statistically best average matchup, starting the game with a positional advantage.

---

## 4. Feature Comparison Matrix

| Feature | Heuristic V12 (The Meta Master) | Abyssal (Pokechamp) | Simple Heuristic (poke-env) |
| :--- | :---: | :---: | :---: |
| **Matchup-Based Lead Selection** | **Yes** | No | No |
| **Best Matchup Fainted Switch-in** | **Yes** (Strategic) | No (Randomized) | No (Randomized) |
| **Sack Logic (HP $\le 20\%$)** | **Yes** (Stay and fight) | No (Switches out) | No (Switches out) |
| **Tight Setup & Hazards** | **Yes** (Free turns only) | No (Naive) | No (Naive) |
| **Item & Screen Awareness** | **Yes** | No | No |
| **Ability Immunities Checked** | **Yes** | No | No |
| **Trick Room Awareness** | **Yes** (Reverses speed) | No | No |
| **Status Moves Utility** | **Yes** (Toxic/WoW/TWave) | No | No |
| **Pivot Moves (Volt Switch/U-turn)** | **Yes** (Tempo switches) | No | No |
| **Priority KO Check** | **Yes** | No | No |
| **Terastallization Evaluation** | **Yes** (Offensive & Defensive) | Yes (Offensive only) | Yes (Offensive only) |
| **Gen-Aware Adapting** | **Yes** | No | No |
