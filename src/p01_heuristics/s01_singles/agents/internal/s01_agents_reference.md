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
└── V12 (standalone, V11 + teampreview lead + fainted switch + Terastallize)
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

### Key Differentiators

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

### Strategy Tracking

V7 through V12 record per-battle strategy counters (available in CSV output):
- `hazard_sets`: Times entry hazards were set.
- `hazard_removals`: Times hazards were removed.
- `setup_uses`: Times boost moves were used.
- `ko_checks`: Times a guaranteed KO was detected and executed.
- `matchup_switches`: Times a switch was triggered by matchup score.

These are always 0 for V1-V6 (they don't have those code paths).
