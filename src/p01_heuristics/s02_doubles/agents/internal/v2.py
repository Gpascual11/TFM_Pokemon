"""Heuristic V2 Doubles: Conservative Switching and Type Awareness.

Extends V1 by introducing a defensive switch-out mechanism. Compares the
effectiveness of the current matchup against potential switches, prioritizing
safety when facing major type disadvantages.

This version is designed to minimize risk by identifying situations where a
Pokémon is significantly vulnerable to opponent types and swapping it for a
teammate with better resistance.
"""

from __future__ import annotations

from poke_env.player.battle_order import SingleBattleOrder
from poke_env.environment.move import Move
from poke_env.environment.pokemon import Pokemon as PokemonClass

from ...core.base import BaseHeuristic2v2
from ...core.common import calculate_base_damage, get_status_name

_OPP1 = 1
_OPP2 = 2
_EMPTY = 0


class HeuristicV2Doubles(BaseHeuristic2v2):
    """V1 damage evaluation plus conservative defensive switching."""

    def _score_order(
        self, order: SingleBattleOrder, pokemon, slot: int, battle
    ) -> float:
        action = order.order

        if isinstance(action, PokemonClass):
            my_status = get_status_name(pokemon)
            return self._score_switch(action, pokemon, slot, battle, my_status)

        if not isinstance(action, Move):
            return -1.0
        if action.base_power <= 1:
            return 0.0

        target = order.move_target

        # Penalise ally-targeting orders
        if target < 0:
            return 0.0

        my_status = get_status_name(pokemon)
        opps = battle.opponent_active_pokemon or []

        # Base damage against actual target
        if target == _EMPTY:
            # Spread move — score by best opponent effectiveness
            living = [o for o in opps if o is not None]
            if not living:
                return 0.0
            return self._best_damage_against_opponents(
                action, pokemon, living, my_status
            )

        idx = target - 1
        if idx < 0 or idx >= len(opps) or opps[idx] is None:
            return 0.0
        return calculate_base_damage(action, pokemon, opps[idx], my_status)

    def _score_switch(
        self, switch, current_mon, slot: int, battle, attacker_status: str
    ) -> float:
        """Assign a defensive score to a potential switch-in.

        A switch is favored if the current Pokémon is at risk and the teammate
        has better type matchups against the active opponents.
        """
        opps = [o for o in battle.opponent_active_pokemon if o is not None]
        if not opps:
            return 0.1

        # Calculate vulnerability of current mon
        vuln = max(
            (max(current_mon.damage_multiplier(t) for t in o.types) for o in opps),
            default=1.0,
        )

        # Calculate defensive utility of switch
        resists = max(
            (max(switch.damage_multiplier(t) for t in o.types) for o in opps),
            default=2.0,
        )

        # Favors switch if vuln is high and switch is safer
        if vuln >= 2.0 and resists <= 1.0:
            return 50.0  # Significant priority boost

        return -0.5
