"""Heuristic V6 Doubles: Environmental Awareness and Priority Scoring.

Advanced version of the stat-based heuristic that incorporates weather
effects (Sun/Rain), terrain boosts (Electric/Grassy/Psychic), and move
priority modifiers into the final score calculation.
"""

from __future__ import annotations

from poke_env.player.battle_order import SingleBattleOrder
from poke_env.battle.move import Move
from poke_env.battle.pokemon import Pokemon as PokemonClass

from .v2 import HeuristicV2Doubles
from ..core.common import calculate_base_damage, get_status_name

_OPP1 = 1
_OPP2 = 2
_EMPTY = 0


class HeuristicV6Doubles(HeuristicV2Doubles):
    """V2 switching + weather/terrain/priority move scoring per slot."""

    @property
    def tracks_moves(self) -> bool:
        return True

    def _score_order(
        self, order: SingleBattleOrder, pokemon, slot: int, battle
    ) -> float:
        action = order.order

        if isinstance(action, PokemonClass):
            my_status = get_status_name(pokemon)
            return self._score_switch(action, pokemon, slot, battle, my_status)

        if not isinstance(action, Move):
            return -1.0

        target = order.move_target

        # Penalise ally-targeting orders
        if target < 0:
            return 0.0

        my_status = get_status_name(pokemon)
        opps = battle.opponent_active_pokemon or []

        # Base damage against actual target
        if target == _EMPTY:
            living = [o for o in opps if o is not None]
            score = max(
                (calculate_base_damage(action, pokemon, o, my_status) for o in living),
                default=0.0,
            )
        else:
            idx = target - 1
            if idx < 0 or idx >= len(opps) or opps[idx] is None:
                return 0.0
            score = calculate_base_damage(action, pokemon, opps[idx], my_status)

        # Weather modifiers
        if battle.weather:
            w = str(battle.weather).upper()
            t = action.type.name
            if "SUN" in w:
                if t == "FIRE":
                    score *= 1.5
                elif t == "WATER":
                    score *= 0.5
            elif "RAIN" in w:
                if t == "WATER":
                    score *= 1.5
                elif t == "FIRE":
                    score *= 0.5

        # Terrain modifiers
        if battle.fields:
            boosts = {"ELECTRIC": "ELECTRIC", "GRASSY": "GRASS", "PSYCHIC": "PSYCHIC"}
            for field in battle.fields:
                fn = str(field).upper()
                for tk, tt in boosts.items():
                    if tk in fn and action.type.name == tt:
                        score *= 1.3

        # Conservative priority boost
        if action.entry.get("priority", 0) > 0:
            score *= 1.2

        return score
