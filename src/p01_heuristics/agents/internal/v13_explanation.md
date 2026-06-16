# Heuristic V13: The Prediction Master

Heuristic V13 (`HeuristicV13`), codenamed **The Prediction Master**, represents a significant leap forward in the evolutionary chain of rule-based singles heuristic agents. Built upon the solid foundation of `HeuristicV12` (the previous state-of-the-art), V13 shifts from a purely reactive, rule-based approach to a **predictive, information-aware strategy**.

By integrating lazy-loaded Showdown random battle set databases across all generations (Gen 1-9), Heuristic V13 predicts the opponent's movesets, stats, abilities, and items before they are even revealed in battle. This allows V13 to perform highly accurate, stat-aware matchup damage estimations, exploit choice-locked opponents, react to setup sweepers, sustain itself via smart recovery, and select optimal switch-ins without fallback bugs.

In preliminary validation tournaments, Heuristic V13 achieved:
- **90% Win Rate** (9/10 games) in direct head-to-head play against **Heuristic V12** in Gen 9 Random Battles.
- **100% Win Rate** (10/10 games) against the baseline **Random** player.
- Flawless runtime execution (zero crashes/deadlocks) against search-based `abyssal` and other heuristics.

---

## 1. Key Competitive Performance Metrics

| Metric | Heuristic V13 vs. Heuristic V12 | Heuristic V13 vs. Random |
| :--- | :---: | :---: |
| **Win Rate** | **90.0%** (9/10) | **100.0%** (10/10) |
| **Fainted Differential** | **+2.30** | **+4.80** |

*Note: In head-to-head validation, V13 consistently out-predicted V12, taking advantage of setup-sweeper reactions and move predictions to secure dominant wins with several Pokémon remaining.*

---

## 2. Core Architectural Pillars of Heuristic V13

Heuristic V13 refines the core loops of V12 and introduces several novel predictive layers:

### A. Lazy-Loaded Showdown Sets Database
V13 loads Pokémon Showdown's official random battle sets data (`sets.json` and `data.json`) for the active generation on demand. 
1. **Opponent Tracking**: When an opponent Pokémon is sent out, V13 queries the database to retrieve its possible moves, abilities, items, and stats.
2. **Dynamic Updates**: As the opponent reveals moves or abilities during the battle, V13 filters the predicted set to narrow down the exact variant being played.

### B. Move- and Stat-Aware Matchup Estimation (`_estimate_matchup`)
V12 estimated matchups using basic type-effectiveness matching. V13 calculates a highly detailed matchup score:
1. **Max Damage Expected**: Calculates the maximum damage fraction the opponent can inflict on us using their predicted/revealed moveset, factoring in STAB, weather, terrain, and stat stages.
2. **Max Damage Inflicted**: Simulates the maximum damage fraction we can deal to the opponent using our moveset against their predicted base stats and typing.
3. **Speed Advantage**: Rewards the outspeeding Pokémon with an initiative bonus.
4. **Final Matchup Formula**: Integrates the damage-given vs. damage-taken ratio, HP percentages, and speed to arrive at a highly precise matchup rating.

### C. Safe Bench Switch-In Logic (Fixed Fallback Bug)
In V12, if all bench options had a matchup score below `-1.0`, the agent fell back to an arbitrary default, sometimes switching in a highly vulnerable teammate.
- **V13 Fix**: V13 evaluates all available bench switches and **always** picks the one with the highest calculated matchup score, regardless of any arbitrary threshold. This guarantees that the best possible counter-pick is deployed onto the field.

### D. Exploiting Choice Lock
If an opponent Pokémon has a Choice item (Choice Band, Choice Specs, Choice Scarf) and has used a move, V13 locks the opponent's predicted moveset to *only* that move.
- **Positional Advantage**: If the opponent is locked into an ineffective move (e.g. choice-locked into an Electric move against our Ground-type teammate), V13 awards this matchup an extra bonus, prompting a switch-in or a free setup turn.

### E. Setup Sweeper Reactions
If the active opponent has accumulated positive stat boosts (e.g., Swords Dance, Dragon Dance, Calm Mind) and represents a sweep threat:
1. **Phazing/Haze**: V13 prioritizes moves like Haze, Whirlwind, Roar, or Dragon Tail to reset or force out the sweeper.
2. **Status**: V13 immediately attempts to burn (Will-O-Wisp) physical sweepers or paralyze (Thunder Wave) fast sweepers to neutralize the threat.

### F. Smart Recovery and Draining Logic
To maximize longevity, V13 monitors its HP:
- **Heal Condition**: If HP is below 60% and we are in a neutral or positive matchup, V13 prioritizes recovery moves (Recover, Roost, Slack Off, Soft-Boiled) or high-damage draining moves (Giga Drain, Drain Punch).
- **Tempo Preservation**: It will not waste turns recovering if the opponent can outspeed and deal more damage than the recovery provides.

### G. Dynamic Hazard Placement
Entry hazards are placed dynamically:
- **Turn 1 Priority**: If a hazard setter leads and the opponent has fainted or switched, hazards are laid.
- **Predicted Switch Turns**: If V13 predicts the opponent will switch (due to a terrible matchup score for the opponent's active Pokémon), V13 uses the free turn to set up Stealth Rock/Spikes.

### H. Conservative Terastallization
V13 Terastallization is highly disciplined:
- Tera is **never** triggered on status moves or when the active Pokémon's HP is below 30% (preventing wasting the team's Terastallize action on a Pokémon about to faint).

---

## 3. Key Differentiators: V13 vs. V12

| Feature | Heuristic V13 (Prediction Master) | Heuristic V12 (Meta Master) |
| :--- | :--- | :--- |
| **Opponent Move Prediction** | **Dynamic Sets Lookup (Gens 1-9)** | None (Only react to revealed moves) |
| **Matchup Scoring** | **Move/Stat-Aware Damage Simulation** | Type Effectiveness + Speed check |
| **Switch-in Fallback Bug** | **Fixed** (Always chooses optimal bench) | Buggy (Fell back to default if < -1.0) |
| **Choice Lock Exploitation** | **Yes** (Identifies and setups on locked moves) | No |
| **Sweeper Reactions** | **Phazing / Haze / Status Priority** | Generic damage calculation |
| **Smart Recovery** | **Priority Roost/Recover/Drain < 60% HP** | Evaluated as generic moves |
| **Tera Conservation** | **Yes** (Disabled < 30% HP or on status) | No (Could waste Tera on dying mon) |

---

## 4. Feature Comparison Matrix

| Feature | Heuristic V13 | Heuristic V12 | Abyssal (Pokechamp) | Simple Heuristic |
| :--- | :---: | :---: | :---: | :---: |
| **Sets Lookup Database** | **Yes** | No | No | No |
| **Choice Lock Awareness** | **Yes** | No | No | No |
| **Setup Sweeper Counters** | **Yes** | No | No | No |
| **Smart Longevity/Recovery** | **Yes** | No | No | No |
| **Matchup Lead Selection** | **Yes** | Yes | No | No |
| **Correct Fainted Switch** | **Yes** (Perfect) | Yes (Buggy fallback) | No (Randomized) | No (Randomized) |
| **Sack Logic (HP $\le 20\%$)** | **Yes** | Yes | No | No |
| **Tight Setup & Hazards** | **Yes** | Yes | No (Naive) | No (Naive) |
| **Item & Screen Awareness** | **Yes** | Yes | No | No |
| **Ability Immunities Checked** | **Yes** | Yes | No | No |
| **Trick Room Speed Reversal** | **Yes** | Yes | No | No |
| **Volt Switch/U-turn Pivot** | **Yes** | Yes | No | No |
| **Terastallize Logic** | **Yes** (Conservative) | Yes | Yes (Offensive only) | Yes (Offensive only) |
