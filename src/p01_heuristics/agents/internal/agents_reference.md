# agents: Strategy Implementations (Singles)

This folder contains the actual decision logic for all heuristic versions.

## Strategy Genealogy

### Inheritance Map

```
BaseHeuristic1v1
├── V1 (greedy bp × type × STAB)
│   └── V2 → V3 → V6
├── V4, V5  (standalone field / boost variants)
├── V7  (boost-aware damage + matchup switching)
├── V8  (V7 + priority KO + known-ability immunity)
├── V9  (tight hazards & setup on free turns)
├── V10 (status, sack, pivots)
├── V11 (V9 + V10 + gen-aware)
├── V12 (Tera + fainted switch-in)
├── V13 (recovery / choice-lock / phazing; revealed-move matchups)
└── V14 (Yomi, scouting, approx. min/max damage, 1-ply endgame)
```

Most of V7–V14 **subclass `BaseHeuristic1v1` directly**. The table is a feature story.

### Version Descriptions

| Version | Codename | Key Logic | Switching Strategy |
|---------|----------|-----------|-------------------|
| **V1** | The Civilian | Max `bp × eff × stab` | None |
| **V2** | The Fighter | Stats-based damage (atk/def) + burn penalty | TOX escape + outsped pivot |
| **V3** | The Tracker | V2 + per-battle move tracking | Same as V2 |
| **V4** | The Field Expert | V3 damage + weather/terrain + accuracy × priority | V3 triggers + smart type-based target |
| **V5** | The Boost Master | V4 + stat-boost-aware damage (in-battle stages) | V3 triggers + smart type-based target |
| **V6** | The Stable Peak | V3 damage + weather/terrain/priority (lightweight) | V3 triggers (slot 0) |
| **V7** | The Strategist | Boost-aware damage + matchup switching | Matchup score-based (Abyssal formula) |
| **V8** | Priority KO | V7 + priority KO + known-ability immunity | Same as V7 |
| **V9** | The Optimizer | Tight hazards/setup on free turns | Same as V7 |
| **V10** | The Disruptor | Status, sack ≤20% HP, Volt Switch/U-turn | V8-style matchup + sack + pivot |
| **V11** | The Adaptable | Hybrid (V9 + V10) + gen-aware | Same as V10 |
| **V12** | Tera | Gen 9 Tera + fainted switch-in | Matchup-based fainted switch-in |
| **V13** | Revealed-move matchups | Recovery, choice-lock, phazing | Stat-aware matchups from revealed moves |
| **V14** | Championship extras | Yomi, T1–3 scouting, approx. damage range (0.85–1.0×), 1-ply endgame | Tendency-aware switches |

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

**V7-V8**: Matchup switching and (V8) priority KO / known immunities.

**V8 exclusively adds**:
- Conservative priority KO (wide overkill margin).
- Ability immunities only when the ability is already known.

**V9 exclusively adds**:
- **Tight Hazards/Setup**: Entry hazards and setup boosts *only* on free turns.

**V10 exclusively adds**:
- Status (Toxic / Will-O-Wisp / Thunder Wave), sack at ≤20% HP, Volt Switch / U-turn.

**V11 exclusively adds**:
- Hybrid of V9 tempo + V10 tactics, plus gen-aware hazard/paralysis tweaks.

**V12 exclusively adds**:
- **Matchup-Based Fainted Switch-in**.
- **Gen 9 Terastallization**.

**V13 exclusively adds**:
- Recovery, choice-lock, sweeper reactions, conservative Tera.
- Matchup damage from **revealed** moves.

**V14 exclusively adds**:
- Yomi tendency profiling and turns 1–3 scouting.
- Approximate damage **range** (`score * 0.85`, `score`). Opponent HP from poke-env is often a percentage.
- 1-ply endgame solver when both sides have ≤2 Pokémon.

---

## Strategy Tracking

V7 through V14 record per-battle strategy counters (available in CSV output):
- `hazard_sets`: Times entry hazards were set.
- `hazard_removals`: Times hazards were removed.
- `setup_uses`: Times boost moves were used.
- `ko_checks`: Times a guaranteed KO was detected and executed.
- `matchup_switches`: Times a switch was triggered by matchup score.

These are always 0 for V1-V6 (they don't have those code paths).
