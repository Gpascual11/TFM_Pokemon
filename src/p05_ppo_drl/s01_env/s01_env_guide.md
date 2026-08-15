# s01_env: observation and Discrete(14) actions

`PokemonMaskedEnv` is poke-env `SinglesEnv` with `strict=False`, format `gen9randombattle`.

## Actions (`actions.py`)

Slots, kept in lockstep for masks, `action_to_order`, and `order_to_action` (so a v12 opponent keeps Tera):

| Index | Meaning |
|---|---|
| 0–3 | Move i |
| 4–7 | Move i + Terastallize (`battle.can_tera`) |
| 8–13 | Switch to team slot i (`list(battle.team.values())`) |

Switch identity is the **Pokémon object** in `available_switches`. Struggle/recharge occupy slot 0 because they are not in `pokemon.moves`. Forced-switch fallback leaves the fainted active’s slot masked.

Eval players (`PPOPlayer`) call `action_to_order` on every decision, including force-switch.

## Observation (`vectorizer.py`)

Code **obs_size = 346**. Claim zips are **328**. Loading 328 copies the first-layer weights; the extra 18 dims start at 0 (revealed-team matchup, best-matchup flag, tera move/def, switch-in hazard). Phase 1/1.5 zips are 318.

328-d features in [0, 1]: active HP/types/status/boosts, 4-move type+BP+PP, STAB×type-eff vs the opponent, boost-aware move damage, 6 switch matchups vs the active foe, bench HP, fainted flags, lead one-hots, weather/field/side conditions, can_tera / already-tera / tera-type one-hots, speed comparison, force_switch, trapped.
