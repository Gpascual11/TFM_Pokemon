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
└── V8  (standalone, V7 + item/ability/screen/Trick Room)
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

### Key Differentiators

**V1-V3-V6 cluster**: All use the same damage formula (`calculate_base_damage` from `common.py`). They differ only in switching triggers and move tracking. Benchmark results confirm they perform equivalently (~50% against each other, ~30% vs strong baselines).

**V4-V5**: Use boost-aware damage and weather/terrain modifiers. Smart switching selects the best defensive type matchup instead of slot 0.

**V7-V8**: Game-changing additions that target Abyssal-level play:
- **Hazard awareness**: Sets Stealth Rock/Spikes, removes with Defog/Rapid Spin
- **Setup moves**: Uses Swords Dance/Dragon Dance when at full HP + positive matchup
- **KO priority**: Pre-checks for guaranteed knockouts (priority moves first)
- **Matchup estimation**: Evaluates type advantage + speed + HP for switching decisions

**V8 exclusively adds**:
- Item modifiers (Life Orb 1.3×, Choice Band/Specs 1.5×, Assault Vest)
- Ability immunities (Flash Fire, Levitate, Water Absorb, etc.)
- Screen awareness (Reflect/Light Screen halve expected damage)
- Trick Room speed reversal
- Choice-lock exploitation (free setup when opponent is locked)

### Strategy Tracking

V7 and V8 record per-battle strategy counters (available in CSV output):
- `hazard_sets`: Times entry hazards were set
- `hazard_removals`: Times hazards were removed
- `setup_uses`: Times boost moves were used
- `ko_checks`: Times a guaranteed KO was detected and executed
- `matchup_switches`: Times a switch was triggered by matchup score

These are always 0 for V1-V6 (they don't have those code paths).
