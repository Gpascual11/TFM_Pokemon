# agents: Strategy Implementations (Singles)

This folder contains the actual decision logic for all heuristic versions.

## Strategy Genealogy

### Inheritance Map

```
BaseHeuristic1v1
├── V1 (standalone)
│   └── V2
│       └── V3
│           └── V6  (V3 + weather/terrain/priority)
├── V4  (standalone, V3 logic + field mods + smart switching)
├── V5  (standalone, V4 + stat-boost awareness)
├── V7  (standalone, strategic battler: hazards, setup, matchup switching)
├── V8  (standalone, V7 + item/ability/screen/Trick Room)
├── V9  (standalone, V7 boost core + tight hazards & setup on free turns)
├── V10 (standalone, V8 core + status moves + sack logic + Volt Switch/U-turn pivot)
├── V11 (standalone, hybrid V9 + V10 + Gen adaptation)
├── V12 (standalone, V11 + teampreview lead + fainted switch + Terastallize)
└── V13 (standalone, V12 + Showdown sets prediction + stat-aware matchups + choice exploit + sweeper reaction + smart recovery + dynamic hazards)
    └── V14 (V13 + Yomi 2 profiling + turns 1-3 scouting + 16-step exact damage calculation + 1-ply endgame solver)
```

### Version Descriptions

| Version | Codename | Key Logic | Switching Strategy |
|---------|----------|-----------|-------------------|
| **V1** | The Civilian | Max `bp × eff × stab` | None |
| **V2** | The Fighter | Stats-based damage (atk/def) + burn penalty | TOX escape + outsped pivot |
| **V3** | The Tracker | V2 + per-battle move tracking | Same as V2 |
| **V4** | The Field Expert | V3 damage + weather/terrain + accuracy × priority | V3 triggers + smart type-based target |
| **V5** | The Boost Master | V4 + stat-boost-aware damage (in-battle stages) | V3 triggers + smart type-based target |
| **V6** | The Stable Peak | V3 damage + weather/terrain/priority (lightweight) | V3 triggers (slot 0) |
| **V7** | The Strategist | V5 damage + hazards + setup moves + KO check | Matchup score-based (Abyssal formula) |
| **V8** | The Meta Reader | V7 + item/ability/screen/Trick Room awareness | Matchup + Trick Room reversal |
| **V9** | The Optimizer | V7 boost core + tight hazards/setup on free turns | Same as V7 |
| **V10** | The Disruptor | V8 core + status moves (Toxic/WoW/TWave) | V8 matchup + ≤20% HP sack logic + Volt Switch/U-turn pivot |
| **V11** | The Adaptable | Hybrid (V9 + V10) + Gen-Aware adaptations | Same as V10 |
| **V12** | The Meta Master | V11 + Gen 9 Terastallization | V11 + Matchup-based Lead (teampreview) & Matchup-based Fainted switch-in |
| **V13** | The Prediction Master | V12 + Showdown database sets (Gens 1-9) + Sweeper reaction + Smart recovery/draining + Dynamic hazards + Conservative Tera | V12 + Move- & Stat-Aware matchup damage calculations + Choice-lock exploitation + Fixed bench switch fallback bug |
| **V14** | The Championship Master | V13 + Yomi 2 Opponent Profiling + Turns 1-3 Scouting + 16-Step Damage Calc + 1-Ply Endgame Solver | V13 + Opponent Tendency-Aware switch-prediction + Safe Endgame Switch-outs |

---

## Bot-vs-Bot vs. Human-vs-Bot Dynamics (V13 vs. V14)

When analyzing the performance of these agents, it is critical to separate how they perform against **other static algorithms (bots)** versus how they perform against **highly skilled human players**.

### Why V13 is the Perfect Bot-Beater
* **Pure Aggression:** V13 plays a highly aggressive, "greedy" style. It does not waste turns trying to guess if the opponent is bluffing, nor does it spend early turns scouting.
* **Exploiting Bot Predictability:** Because other heuristic bots always play with static, non-adaptive rules, they never double-switch, bluff, or strategically throw matchups. V13's simple, high-pressure damage calculations punish this simplicity perfectly.
* **No Wasted Tempo:** V13 attacks immediately from turn 1. Against a bot, which will not punish a lack of information, this gives V13 a massive tempo advantage.

### Why V14 is the Perfect Human-Beater
Humans play with high psychological complexity, adapting to your playstyle, bluffing choices, and attempting to predict and counter your switches. V14 is engineered specifically to beat human players by introducing defensive safety and mind-game countering:
* **Yomi Layer 2 Profiling:** V14 tracks if the human is playing aggressively (`PREDICTIVE`) or safely (`CONSERVATIVE`). This prevents it from being out-predicted and punishes human double-switches.
* **Early-Game Scouting Phase:** On turns 1-3, V14 prioritizes pivot/utility moves (`Protect`, `U-turn`, `Knock Off`) to identify the human's secret items (e.g. Choice Scarf/Specs) and sets without risking a knockout.
* **Defensive Tera Baiting:** When a human player identifies a guaranteed KO, they almost always go for it. V14 identifies this, uses Terastallization defensively to change type weaknesses to resistances, and baits the human into wasting a turn.
* **Endgame Solver:** Prevents human players from executing precise sequence-based checkmates in the late game by simulating all 1-ply matchup outcomes.

*Note: In bot-vs-bot games (like V14 vs V13), V14's advanced human-oriented mechanics (like scouting and baiting) can occasionally result in "over-respecting" the predictable bot, making V13 slightly more efficient in direct bot-vs-bot simulations. However, on the public Showdown ladder against real people, V13's predictability is easily exploited, whereas V14's adaptability makes it much harder to beat.*

---

## Key Differentiators

**V1-V3-V6 cluster**: All use the same damage formula (`calculate_base_damage` from `common.py`). They differ only in switching triggers and move tracking. Benchmark results confirm they perform equivalently (~50% against each other, ~30% vs strong baselines).

**V4-V5**: Use boost-aware damage and weather/terrain modifiers. Smart switching selects the best defensive type matchup instead of slot 0.

**V7-V8**: Game-changing additions that target Abyssal-level play:
- **Hazard awareness**: Sets Stealth Rock/Spikes, removes with Defog/Rapid Spin.
- **Setup moves**: Uses Swords Dance/Dragon Dance when at full HP + positive matchup.
- **KO priority**: Pre-checks for guaranteed knockouts (priority moves first).
- **Matchup estimation**: Evaluates type advantage + speed + HP for switching decisions.

**V8 exclusively adds**:
- Item modifiers (Life Orb 1.3×, Choice Band/Specs 1.5×, Assault Vest).
- Ability immunities (Flash Fire, Levitate, Water Absorb, etc.).
- Screen awareness (Reflect/Light Screen halve expected damage).
- Trick Room speed reversal.
- Choice-lock exploitation (free setup when opponent is locked).

**V9 exclusively adds**:
- **Tight Hazards/Setup**: Entry hazards and setup boosts are executed *only* on free turns (when we outspeed and resist opponent's STAB) to prevent lost tempo.

**V10 exclusively adds**:
- **Status moves**: Uses Toxic, Will-O-Wisp, and Thunder Wave to cripple specific defensive and offensive threats.
- **Sack logic**: Prevents switching out low-HP (≤20%) teammates to avoid wasted turns, opting to let them faint for a free switch-in.
- **Pivot moves**: Volt Switch and Volt/U-turn are preferred over raw switches when they deal neutral+ damage.

**V11 exclusively adds**:
- **Hybrid design**: Combines V9's tight hazards/setup with V10's tactical status, sack, and pivot moves.
- **Gen-Aware Adaptation**: Disables hazards/setup in Gen 1, and adjusts the Paralysis speed multiplier (reducing speed by 75% in Gen 1-6, and 50% in Gen 7+).

**V12 exclusively adds**:
- **Matchup-Based Lead Selection**: Overrides `teampreview` to order team from best average matchup to worst average matchup against opponent previewed team.
- **Matchup-Based Fainted Switch-in**: Inspects the active opponent pokemon and switches in the best possible type matchup counter.
- **Gen 9 Terastallization**: Evaluates offensive and defensive benefits before terastallizing.

**V13 exclusively adds**:
- **Showdown Random Battle Set Lookup**: Predicts opponent moves, abilities, and tera types across Gens 1-9 using static databases.
- **Move- and Stat-Aware Matchup Estimation**: Evaluates matchups using simulated damage metrics, incorporating stats, predicted moves, STAB, weather, and terrain.
- **Exploiting Choice Lock**: Detects choice-locked opponents and awards switch-ins matchup bonuses.
- **Setup Sweeper Reactions**: Prioritizes Haze/phazing/status when opponents set up boosts.
- **Smart Recovery**: Cleanses and heals via Recovery moves when safe.
- **Conservative Terastallization**: Avoids wasting Tera on status moves or low-HP Pokémon.

**V14 exclusively adds**:
- **Yomi Layer 2 Opponent Tendency Profiling**: Tracks opponent switches to determine if they play `PREDICTIVE` (frequent switches) or `CONSERVATIVE` (stays in). If conservative, V14 disables switch predictions to avoid wasting moves on coverage or double-switches.
- **Early-Game Scouting Phase**: Prioritizes utility/pivot moves (U-turn, Volt Switch, Protect, Knock Off) on turns 1–3 to reveal opponent items and sets safely.
- **16-Step Damage Calculations**: Evaluates the minimum and maximum random rolls to secure guaranteed KOs and avoid risk.
- **Endgame Lookahead Solver**: Active when both sides have <= 2 Pokémon, simulating 1-ply match outcomes to secure victory paths.

---

## Strategy Tracking

V7 through V14 record per-battle strategy counters (available in CSV output):
- `hazard_sets`: Times entry hazards were set.
- `hazard_removals`: Times hazards were removed.
- `setup_uses`: Times boost moves were used.
- `ko_checks`: Times a guaranteed KO was detected and executed.
- `matchup_switches`: Times a switch was triggered by matchup score.

These are always 0 for V1-V6 (they don't have those code paths).
